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


def _key() -> bytes:
    return (os.environ.get("KAZIKASI_SECRET") or "kazi-kasi-demo").encode()


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


def _claims(id_token: str) -> dict:
    """Read the id_token's claims.

    The token came from our own server-to-server call to the provider's token
    endpoint over TLS, which is the trust boundary; we do not re-verify the
    signature here because we do not have the provider's keys offline. This is
    recorded rather than hidden: see `docs/phase-7-accounts.md`.
    """
    try:
        payload = id_token.split(".")[1]
        padded = payload + "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(padded))
    except (IndexError, ValueError, json.JSONDecodeError):
        return {}


def exchange(
    provider: Provider,
    *,
    code: str,
    verifier: str,
    redirect_uri: str,
    transport=urllib_transport,
) -> dict:
    """Trade the code for an identity: {subject, email, email_verified, name}."""
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
    claims = _claims(token.get("id_token") or "")

    info = {}
    if provider.userinfo and access:
        info = transport(
            "GET", provider.userinfo, headers={"Authorization": f"Bearer {access}", "Accept": "application/json"}
        )

    merged = {**claims, **{k: v for k, v in info.items() if v}}
    subject = str(merged.get("sub") or "")
    if not subject:
        raise ValueError("the provider did not return an identity")
    return {
        "subject": subject,
        "email": merged.get("email"),
        "email_verified": bool(merged.get("email_verified")),
        "name": merged.get("name") or merged.get("given_name"),
    }


# --------------------------------------------------------------------------
# Accounts
# --------------------------------------------------------------------------


def _now(now: datetime | None = None) -> datetime:
    return now or datetime.now(timezone.utc)


def new_account(conn, *, kind: str, provider: str | None = None, subject: str | None = None,
                email: str | None = None, email_verified: bool = False, name: str | None = None,
                now: datetime | None = None) -> dict:
    moment = _now(now)
    account_id = "acc_" + secrets.token_urlsafe(12)
    conn.execute(
        """INSERT INTO accounts (id, kind, provider, subject, email, email_verified, name,
                                 created_at, last_seen_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (account_id, kind, provider, subject, email, int(email_verified), name,
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
            now=moment,
        )
    conn.execute(
        """UPDATE accounts SET last_seen_at = ?, email = COALESCE(?, email),
                               email_verified = MAX(email_verified, ?), name = COALESCE(?, name)
            WHERE id = ?""",
        (moment.isoformat(), identity.get("email"), int(bool(identity.get("email_verified"))),
         identity.get("name"), row["id"]),
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
