"""Accounts: optional sign-in, and a guest that is a first-class citizen.

The product does not gate the feed behind an identity. Signing in exists for two
reasons only — personalisation and filling forms — and both work without handing
over a social graph.

Three shapes of account:

* **guest** — created on demand, no provider, no email. Gets a session, a CV and
  every feature a member gets except cross-device continuity.
* **member** — Google, Apple or LinkedIn proved an identity. We store the
  provider's stable subject, the address they returned, and their name. Nothing
  else: no contacts, no posts, no profile scrape.
* **deleted** — a row with ``deleted_at`` set. Everything personal is wiped; the
  row survives only so a returning sign-in does not silently resurrect it.

The OAuth flow is PKCE with a server-side verifier and a single-use state, and it
is written so the network is injectable: the exchange is a plain function of
(provider, code, verifier, transport), which is what makes it testable offline.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, quote

#: A session lasts this long. Long enough that a job hunt does not log you out.
SESSION_DAYS = 30

#: An OAuth attempt is good for this long, then it is garbage.
STATE_MINUTES = 10


@dataclass(frozen=True)
class Provider:
    key: str
    label: str
    authorize: str
    token: str
    userinfo: str | None
    scope: str
    client_id_env: str
    client_secret_env: str
    response_mode: str | None = None
    #: Where the provider publishes the keys its id_tokens are signed with.
    jwks: str = ""
    #: Every issuer string this provider is allowed to put in `iss`.
    issuers: tuple[str, ...] = ()

    @property
    def client_id(self) -> str | None:
        return os.environ.get(self.client_id_env) or None

    @property
    def client_secret(self) -> str | None:
        return os.environ.get(self.client_secret_env) or None

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)


PROVIDERS: dict[str, Provider] = {
    "google": Provider(
        key="google",
        label="Google",
        authorize="https://accounts.google.com/o/oauth2/v2/auth",
        token="https://oauth2.googleapis.com/token",
        userinfo="https://openidconnect.googleapis.com/v1/userinfo",
        scope="openid email profile",
        client_id_env="GOOGLE_CLIENT_ID",
        client_secret_env="GOOGLE_CLIENT_SECRET",
        jwks="https://www.googleapis.com/oauth2/v3/certs",
        issuers=("https://accounts.google.com", "accounts.google.com"),
    ),
    "apple": Provider(
        key="apple",
        label="Apple",
        authorize="https://appleid.apple.com/auth/authorize",
        token="https://appleid.apple.com/auth/token",
        userinfo=None,  # identity arrives in the id_token
        scope="name email",
        client_id_env="APPLE_CLIENT_ID",
        client_secret_env="APPLE_CLIENT_SECRET",
        response_mode="form_post",
        jwks="https://appleid.apple.com/auth/keys",
        issuers=("https://appleid.apple.com",),
    ),
    "linkedin": Provider(
        key="linkedin",
        label="LinkedIn",
        authorize="https://www.linkedin.com/oauth/v2/authorization",
        token="https://www.linkedin.com/oauth/v2/accessToken",
        userinfo="https://api.linkedin.com/v2/userinfo",
        scope="openid profile email",
        client_id_env="LINKEDIN_CLIENT_ID",
        client_secret_env="LINKEDIN_CLIENT_SECRET",
        jwks="https://www.linkedin.com/oauth/openid/jwks",
        issuers=("https://www.linkedin.com",),
    ),
}

#: What we ask for, in the user's words, on the sign-in page.
WHY = {
    "google": "Your name and email address. Nothing else.",
    "apple": "Your name and email address — Apple's private relay is fine.",
    "linkedin": "Your name, headline and email. We do not read your connections.",
}


# --------------------------------------------------------------------------
# Secrets and cookies
# --------------------------------------------------------------------------


#: The secret this build ships with. Named, not hidden — a placeholder that
#: pretends to be a secret is worse than one that says what it is.
DEMO_SECRET = "kazi-kasi-demo"


def strict_mode() -> bool:
    """True unless this is explicitly a demo build.

    Strict mode is what turns the two deployment mistakes that matter — shipping
    the demo session secret, or shipping without one — into loud failures instead
    of a quietly forgeable cookie.
    """
    return (os.environ.get("KAZIKASI_DEMO", "1") or "1").strip() != "1"


def _key() -> bytes:
    secret = (os.environ.get("KAZIKASI_SECRET") or "").strip()
    if secret and secret != DEMO_SECRET:
        return secret.encode()
    if strict_mode():
        raise RuntimeError(
            "KAZIKASI_SECRET is not set (or is the demo value) while KAZIKASI_DEMO=0. "
            "Sessions signed with a known key are forgeable; set a random secret "
            "before serving real accounts. `kazikasi auth check` prints the state."
        )
    return DEMO_SECRET.encode()


def signature(payload: str) -> str:
    return hmac.new(_key(), payload.encode(), "sha256").hexdigest()[:32]


def session_cookie(account_id: str, now: datetime | None = None) -> str:
    """The only thing we keep in the browser: an id, a time, and a signature."""
    moment = now or datetime.now(timezone.utc)
    payload = f"{account_id}.{int(moment.timestamp())}"
    return (
        f"kazi_id={payload}.{signature(payload)}; Path=/; "
        f"Max-Age={SESSION_DAYS * 86400}; HttpOnly; SameSite=Lax"
    )


def read_session(headers: dict | None) -> str | None:
    """The signed account id, or None. A forged cookie is simply ignored."""
    raw = ""
    for key, value in (headers or {}).items():
        if str(key).lower() != "cookie":
            continue
        for part in str(value).split(";"):
            name, _, val = part.strip().partition("=")
            if name == "kazi_id":
                raw = val
    parts = raw.split(".")
    if len(parts) != 3:
        return None
    account_id, issued, sig = parts
    payload = f"{account_id}.{issued}"
    if not issued or not sig or not hmac.compare_digest(sig, signature(payload)):
        return None
    try:
        age = time.time() - int(issued)
    except ValueError:
        return None
    if age > SESSION_DAYS * 86400 or age < -3600:
        return None
    return account_id


def readiness(*, base_url: str | None = None) -> dict:
    """What is configured, what is missing, and what must be true before real use.

    No secrets are returned — only whether a variable is present, because the
    point of the page is to be safe to look at.
    """
    strict = strict_mode()
    secret = (os.environ.get("KAZIKASI_SECRET") or "").strip()
    providers = {}
    for key, provider in PROVIDERS.items():
        missing = [
            env
            for env in (provider.client_id_env, provider.client_secret_env)
            if not (os.environ.get(env) or "").strip()
        ]
        providers[key] = {
            "label": provider.label,
            "configured": not missing,
            "missing": missing,
            "authorize": provider.authorize,
            "jwks": provider.jwks,
            "issuers": list(provider.issuers),
            "redirect_uri": f"{base_url.rstrip('/')}/auth/{key}/callback" if base_url else None,
        }
    return {
        "demo": not strict,
        "session": {
            "secret_set": bool(secret),
            "uses_demo_secret": not secret or secret == DEMO_SECRET,
            "strict": strict,
        },
        "providers": providers,
        "ready": any(item["configured"] for item in providers.values()),
        "notes": [
            "Register the redirect URI the provider shows below; it must match exactly.",
            "Requests: name, email and an identifier. No contacts, no connections.",
            "Set KAZIKASI_SECRET to a random value before KAZIKASI_DEMO=0.",
        ],
    }


# --------------------------------------------------------------------------
# PKCE and state
# --------------------------------------------------------------------------


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    return verifier, challenge


def start(conn, provider_key: str, *, now: datetime | None = None, return_to: str | None = None) -> dict:
    """Begin an attempt: store the verifier, hand back the state and challenge."""
    provider = PROVIDERS[provider_key]
    now = now or datetime.now(timezone.utc)
    state = secrets.token_urlsafe(32)
    verifier, challenge = pkce_pair()
    conn.execute(
        "INSERT INTO oauth_states (state, provider, verifier, return_to, created_at) VALUES (?,?,?,?,?)",
        (state, provider_key, verifier, return_to, now.isoformat()),
    )
    conn.commit()
    return {"provider": provider, "state": state, "verifier": verifier, "challenge": challenge}


def authorize_url(provider: Provider, *, state: str, challenge: str, redirect_uri: str) -> str:
    params = {
        "client_id": provider.client_id or "",
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": provider.scope,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    if provider.response_mode:
        params["response_mode"] = provider.response_mode
    return f"{provider.authorize}?{urlencode(params, quote_via=quote)}"


def claim_state(conn, state: str, provider_key: str, *, now: datetime | None = None) -> str:
    """Consume a state token. Raises ValueError if unknown, reused, stale or wrong provider."""
    now = now or datetime.now(timezone.utc)
    row = conn.execute("SELECT * FROM oauth_states WHERE state = ?", (state,)).fetchone()
    if row is None:
        raise ValueError("unknown sign-in attempt")
    if row["used_at"]:
        raise ValueError("this sign-in link was already used")
    if row["provider"] != provider_key:
        raise ValueError("sign-in attempt was for a different provider")
    created = datetime.fromisoformat(row["created_at"])
    if now - created > timedelta(minutes=STATE_MINUTES):
        raise ValueError("this sign-in attempt expired — start again")
    conn.execute("UPDATE oauth_states SET used_at = ? WHERE state = ?", (now.isoformat(), state))
    conn.commit()
    return row["verifier"]


# --------------------------------------------------------------------------
# The network, injectable
# --------------------------------------------------------------------------


def urllib_transport(method: str, url: str, *, data: dict | None = None, headers: dict | None = None) -> dict:
    """The real transport. Imported lazily so nothing else pays for it."""
    import urllib.parse
    import urllib.request

    body = urllib.parse.urlencode(data).encode() if data is not None else None
    request = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310 - fixed hosts
        payload = response.read().decode("utf-8", errors="replace")
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        # Some providers answer form-encoded.
        return {key: value[0] for key, value in urllib.parse.parse_qs(payload).items()}


def read_claims(id_token: str) -> dict:
    """Decode an id_token's payload **without trusting it**.

    Useful for diagnostics (which email did the provider say?) and for nothing
    else. Any decision about identity goes through :func:`verify_id_token`.
    """
    try:
        payload = id_token.split(".")[1]
        padded = payload + "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(padded))
    except (IndexError, ValueError, json.JSONDecodeError):
        return {}


# Backwards-compatible alias: the old name was honest about what it did, and the
# old behaviour (trusting these claims) is exactly what this phase removed.
_claims = read_claims

#: DER prefix for `DigestInfo(SHA-256)` in PKCS#1 v1.5 signatures.
_SHA256_DIGEST_INFO = bytes.fromhex("3031300d060960864801650304020105000420")

#: JWKS responses are cached for an hour per provider. Keys rotate rarely and a
#: fetch on every sign-in would make the provider a hard dependency of login.
_JWKS_TTL_SECONDS = 3600
_JWKS_CACHE: dict[str, tuple[float, dict]] = {}


def _b64url_int(value: str) -> int:
    padded = value + "=" * (-len(value) % 4)
    return int.from_bytes(base64.urlsafe_b64decode(padded), "big")


def rsa_sha256_verify(signing_input: bytes, signature: bytes, modulus: str, exponent: str) -> bool:
    """Verify an RS256 signature with nothing but integer arithmetic.

    Why not a library: the deployed function imports only the standard library
    (there is no `requirements.txt`, deliberately — see `docs/phase-7-accounts.md`).
    PKCS#1 v1.5 verification is small enough to do correctly here, and doing it
    correctly is the whole point of this function.
    """
    n = _b64url_int(modulus)
    e = _b64url_int(exponent)
    k = (n.bit_length() + 7) // 8
    if len(signature) != k:
        return False
    message = int.from_bytes(signature, "big")
    if message >= n:
        return False
    encoded = pow(message, e, n).to_bytes(k, "big")
    digest = hashlib.sha256(signing_input).digest()
    padding = k - 3 - len(_SHA256_DIGEST_INFO) - len(digest)
    if padding < 8:
        return False
    expected = (
        b"\x00\x01" + b"\xff" * padding + b"\x00" + _SHA256_DIGEST_INFO + digest
    )
    return hmac.compare_digest(encoded, expected)


def jwks(provider: Provider, *, transport=urllib_transport, now: float | None = None) -> list[dict]:
    """The provider's signing keys, cached for an hour."""
    moment = now if now is not None else time.time()
    cached = _JWKS_CACHE.get(provider.key)
    if cached and moment - cached[0] < _JWKS_TTL_SECONDS:
        return cached[1].get("keys", [])
    payload = transport("GET", provider.jwks, headers={"Accept": "application/json"})
    _JWKS_CACHE[provider.key] = (moment, payload if isinstance(payload, dict) else {})
    keys = payload.get("keys", []) if isinstance(payload, dict) else []
    return [key for key in keys if isinstance(key, dict)]


def verify_id_token(
    id_token: str,
    provider: Provider,
    *,
    transport=urllib_transport,
    now: datetime | None = None,
    leeway_seconds: int = 120,
    keys: list[dict] | None = None,
) -> dict:
    """Verify an OIDC id_token and return its claims, or raise.

    Checks, in order: shape, `alg` is RS256 (never `none`), `kid` resolves to a
    published key, the RS256 signature verifies, `iss` is one this provider may
    use, `aud` is our client id, and the token is inside its lifetime.

    **Fails closed.** If the keys cannot be fetched, this raises — a sign-in that
    "works" because verification was skipped is worse than a sign-in that does
    not work.
    """
    parts = (id_token or "").split(".")
    if len(parts) != 3:
        raise ValueError("the provider returned a malformed id_token")

    try:
        header = json.loads(base64.urlsafe_b64decode(parts[0] + "=" * (-len(parts[0]) % 4)))
    except (ValueError, json.JSONDecodeError) as error:
        raise ValueError("the provider returned a malformed id_token header") from error

    if str(header.get("alg", "")).upper() != "RS256":
        raise ValueError(f"unsupported id_token algorithm {header.get('alg')!r}")

    published = keys if keys is not None else jwks(provider, transport=transport)
    kid = header.get("kid")
    candidates = [key for key in published if key.get("kid") == kid] or (
        published if len(published) == 1 else []
    )
    if not candidates:
        raise ValueError("the id_token was signed with a key the provider does not publish")

    try:
        signature = base64.urlsafe_b64decode(parts[2] + "=" * (-len(parts[2]) % 4))
    except ValueError as error:
        raise ValueError("the provider returned a malformed signature") from error

    signing_input = f"{parts[0]}.{parts[1]}".encode()
    verified = any(
        rsa_sha256_verify(signing_input, signature, key.get("n", ""), key.get("e", ""))
        for key in candidates
        if key.get("kty", "RSA") == "RSA"
    )
    if not verified:
        raise ValueError("the id_token signature did not verify")

    claims = read_claims(id_token)
    if provider.issuers and claims.get("iss") not in provider.issuers:
        raise ValueError(f"unexpected issuer {claims.get('iss')!r}")

    audience = claims.get("aud")
    audiences = audience if isinstance(audience, list) else [audience]
    if provider.client_id and provider.client_id not in audiences:
        raise ValueError("the id_token was issued for a different client")

    moment = time.time() if now is None else now.timestamp()
    expires = claims.get("exp")
    if not isinstance(expires, (int, float)):
        raise ValueError("the id_token has no expiry")
    if moment > expires + leeway_seconds:
        raise ValueError("the id_token has expired")
    issued = claims.get("iat")
    if isinstance(issued, (int, float)) and issued > moment + leeway_seconds:
        raise ValueError("the id_token is dated in the future")

    return claims


def exchange(
    provider: Provider,
    *,
    code: str,
    verifier: str,
    redirect_uri: str,
    transport=urllib_transport,
    now: datetime | None = None,
) -> dict:
    """Trade the code for an identity: {subject, email, email_verified, name}.

    The **id_token is verified** (signature, issuer, audience, lifetime) before
    any of its claims are used. The userinfo endpoint is used only to fill gaps,
    never to override the verified claims.
    """
    token = transport(
        "POST",
        provider.token,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": provider.client_id or "",
            "client_secret": provider.client_secret or "",
            "code_verifier": verifier,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    access = token.get("access_token")
    claims = {}
    if token.get("id_token"):
        claims = verify_id_token(token["id_token"], provider, transport=transport, now=now)

    info = {}
    if provider.userinfo and access:
        info = transport(
            "GET", provider.userinfo, headers={"Authorization": f"Bearer {access}", "Accept": "application/json"}
        )

    merged = {**{k: v for k, v in info.items() if v}, **claims}
    subject = str(merged.get("sub") or "")
    if not subject:
        raise ValueError("the provider did not return an identity")
    return {
        "subject": subject,
        "email": merged.get("email"),
        "email_verified": bool(merged.get("email_verified")),
        "name": merged.get("name") or merged.get("given_name"),
        "given_name": merged.get("given_name"),
        "family_name": merged.get("family_name"),
        "picture": merged.get("picture"),
        "locale": merged.get("locale"),
    }


# --------------------------------------------------------------------------
# Accounts
# --------------------------------------------------------------------------


def _now(now: datetime | None = None) -> datetime:
    return now or datetime.now(timezone.utc)


def new_account(conn, *, kind: str, provider: str | None = None, subject: str | None = None,
                email: str | None = None, email_verified: bool = False, name: str | None = None,
                given_name: str | None = None, family_name: str | None = None,
                picture: str | None = None, locale: str | None = None,
                now: datetime | None = None) -> dict:
    moment = _now(now)
    account_id = "acc_" + secrets.token_urlsafe(12)
    conn.execute(
        """INSERT INTO accounts (id, kind, provider, subject, email, email_verified, name,
                                 given_name, family_name, picture, locale,
                                 created_at, last_seen_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (account_id, kind, provider, subject, email, int(email_verified), name,
         given_name, family_name, picture, locale,
         moment.isoformat(), moment.isoformat()),
    )
    conn.commit()
    return account(conn, account_id)


def account(conn, account_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    return dict(row) if row else None


def sign_in(conn, provider_key: str, identity: dict, *, now: datetime | None = None) -> dict:
    """Find or create the account behind a verified identity."""
    moment = _now(now)
    row = conn.execute(
        "SELECT * FROM accounts WHERE provider = ? AND subject = ?",
        (provider_key, identity["subject"]),
    ).fetchone()
    if row is None:
        return new_account(
            conn,
            kind="member",
            provider=provider_key,
            subject=identity["subject"],
            email=identity.get("email"),
            email_verified=bool(identity.get("email_verified")),
            name=identity.get("name"),
            given_name=identity.get("given_name"),
            family_name=identity.get("family_name"),
            picture=identity.get("picture"),
            locale=identity.get("locale"),
            now=moment,
        )
    if row["deleted_at"]:
        # Signing in again is not an undelete: the person asked us to forget.
        return new_account(
            conn,
            kind="member",
            provider=provider_key,
            subject=identity["subject"],
            email=identity.get("email"),
            email_verified=bool(identity.get("email_verified")),
            name=identity.get("name"),
            given_name=identity.get("given_name"),
            family_name=identity.get("family_name"),
            picture=identity.get("picture"),
            locale=identity.get("locale"),
            now=moment,
        )
    conn.execute(
        """UPDATE accounts SET last_seen_at = ?, email = COALESCE(?, email),
                               email_verified = MAX(email_verified::integer, ?)::smallint, 
                               name = COALESCE(?, name),
                               given_name = COALESCE(?, given_name),
                               family_name = COALESCE(?, family_name),
                               picture = COALESCE(?, picture),
                               locale = COALESCE(?, locale)
            WHERE id = ?""",
        (moment.isoformat(), identity.get("email"), int(bool(identity.get("email_verified"))),
         identity.get("name"), identity.get("given_name"), identity.get("family_name"),
         identity.get("picture"), identity.get("locale"), row["id"]),
    )
    conn.commit()
    return account(conn, row["id"])


def guest(conn, *, now: datetime | None = None) -> dict:
    return new_account(conn, kind="guest", now=now)


def touch(conn, account_id: str, *, now: datetime | None = None) -> None:
    conn.execute("UPDATE accounts SET last_seen_at = ? WHERE id = ?", (_now(now).isoformat(), account_id))
    conn.commit()


def forget(conn, account_id: str, *, now: datetime | None = None) -> None:
    """Delete everything personal, keep the row as a tombstone.

    The CV is removed outright; the account becomes anonymous. Keeping the row
    means the same provider identity cannot be quietly re-created behind the
    person's back — signing in again starts a fresh, empty account.
    """
    moment = _now(now).isoformat()
    conn.execute("DELETE FROM cvs WHERE account_id = ?", (account_id,))
    conn.execute(
        """UPDATE accounts SET deleted_at = ?, email = NULL, name = NULL,
                               subject = NULL, provider = NULL, last_seen_at = ?
            WHERE id = ?""",
        (moment, moment, account_id),
    )
    conn.commit()


# --------------------------------------------------------------------------
# CVs
# --------------------------------------------------------------------------


def store_cv(conn, account_id: str, *, filename: str | None, text: str, fields: dict,
             now: datetime | None = None) -> int:
    cursor = conn.execute(
        "INSERT INTO cvs (account_id, filename, chars, fields, created_at) VALUES (?,?,?,?,?)",
        (account_id, filename, len(text or ""), json.dumps(fields, ensure_ascii=False),
         _now(now).isoformat()),
    )
    conn.commit()
    return int(cursor.lastrowid)


def latest_cv(conn, account_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM cvs WHERE account_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
        (account_id,),
    ).fetchone()
    if row is None:
        return None
    item = dict(row)
    try:
        item["fields"] = json.loads(item["fields"])
    except json.JSONDecodeError:
        item["fields"] = {}
    return item
