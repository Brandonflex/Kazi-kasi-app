"""Sign-in hardening: the id_token is verified, and the deployment cannot lie.

This phase replaces one documented shortcut with the real check. The shortcut was
honest — ``exchange()`` read the id_token's claims without verifying its
signature, and `docs/phase-7-accounts.md` said so — but "we trust the TLS channel"
is an argument about a network path, not about a token, and it stops being true
the moment anything else consumes those claims.

What is tested here:

* **RS256 verification** against a published key set, in pure integer arithmetic
  (no third-party crypto in the serverless bundle), including the failure modes
  that matter: ``alg: none``, a tampered payload, an unpublished key, a wrong
  issuer, a wrong audience, an expired token, and a JWKS fetch that fails — which
  must fail *closed*.
* **The deployment's own honesty**: `/auth/ready` and `kazikasi auth check` report
  what is configured without leaking a secret, and strict mode refuses to sign
  sessions with the demo key.

The key material below is a throwaway test key generated for this file. It signs
nothing real.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from datetime import datetime, timedelta, timezone

import pytest

from kazikasi import accounts, cli, serve
from kazikasi.accounts import (
    PROVIDERS,
    rsa_sha256_verify,
    verify_id_token,
)

NOW = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)

# ---- test key (throwaway, 2048-bit, signs nothing real) --------------------
TEST_N = "2WQcfNQx5HIcKERLhg0tugYPepfqoyQbeQzGQTp9G7dNRsTPRWbsCVxAEuQLIc4QsBOk8Vx5p3dqiExZZs-U3i2XCmXvQz7auy3k1z3_vnl_HM5LYzZ59UtEUEvpribc3o0xG-yG1Upujv_R6wqAAPHzIPy0wBQ-dqy5ZB8KAlhnlaqkjKKS_r3_JfGfzj4CHhs7Zi8Iibi_2uw60c3OIxkcgTe7UQIZwKo2rDipScOcvwHO1b39ra4nd-QmsmBz6SObMIn_1lMLPa-uLp9wKOYjSUG1J_s2ldJQChYR_SOvkS1PkKdtEC8f9XbgIFC84Qt0_4LGWFWYN3VWc_JbyQ"
TEST_E = "AQAB"
TEST_D = "CVFSK0OJE-qULGGo_wjnkdaaqT2DsBRnHQwgH0GbhSmZJVRgMfBUY55RnL2rgHptmq5s3m-BQ11J8qebGV4CWneHxslRtQcnpugzq8obgRWCDkEFWC5Ikev09KAcVvuRcfSJS1IbAV9cV8K9Q57Cl8fHDP3n3WfAuaNzmsf9zNXa87tqmbcgNI6WT3b5cbnIAk-UY6NeT8aoM734xvSimPaIdPj6tk-TnuRrkNCQ6fP0iRO-Jk85SyenFuTtvgHzH-lPftHWqNxFG8CtlQue3zkjZ2wQx2sBZZGL04UD0bcdB0WOhuR8M5GZTDfYsoAxEAVaHJiWubTEUGxMIHTYAQ"

DIGEST_INFO = bytes.fromhex("3031300d060960864801650304020105000420")


def _int(value: str) -> int:
    return int.from_bytes(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)), "big")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def sign(claims: dict, *, kid: str = "test-key", alg: str = "RS256", n: int | None = None, d: int | None = None) -> str:
    header = {"alg": alg, "kid": kid, "typ": "JWT"}
    n = n or _int(TEST_N)
    d = d or _int(TEST_D)
    body = _b64(json.dumps(header, separators=(",", ":")).encode()) + "." + _b64(
        json.dumps(claims, separators=(",", ":")).encode()
    )
    digest = hashlib.sha256(body.encode()).digest()
    size = (n.bit_length() + 7) // 8
    padding = size - 3 - len(DIGEST_INFO) - len(digest)
    encoded = b"\x00\x01" + b"\xff" * padding + b"\x00" + DIGEST_INFO + digest
    signature = pow(int.from_bytes(encoded, "big"), d, n).to_bytes(size, "big")
    return body + "." + _b64(signature)


def jwks_payload(kid: str = "test-key") -> dict:
    return {"keys": [{"kty": "RSA", "kid": kid, "use": "sig", "alg": "RS256", "n": TEST_N, "e": TEST_E}]}


def claims(**overrides) -> dict:
    base = {
        "iss": "https://accounts.google.com",
        "aud": "client-123",
        "sub": "subject-1",
        "email": "a@b.co",
        "email_verified": True,
        "name": "A B",
        "iat": int(NOW.timestamp()),
        "exp": int((NOW + timedelta(hours=1)).timestamp()),
    }
    base.update(overrides)
    return base


class Fetcher:
    """A transport that answers from memory and counts calls."""

    def __init__(self, *, keys: dict | None = None, fail: bool = False, token: dict | None = None, userinfo: dict | None = None):
        self.keys = keys if keys is not None else jwks_payload()
        self.fail = fail
        self.token = token or {}
        self.userinfo = userinfo or {}
        self.calls: list[tuple[str, str]] = []

    def __call__(self, method: str, url: str, *, data=None, headers=None):
        self.calls.append((method, url))
        if self.fail:
            raise OSError("network down")
        if url.endswith("/certs") or "keys" in url or "jwks" in url:
            return self.keys
        if "token" in url or url.endswith("accessToken"):
            return self.token
        return self.userinfo


@pytest.fixture(autouse=True)
def clear_jwks_cache():
    accounts._JWKS_CACHE.clear()
    yield
    accounts._JWKS_CACHE.clear()


@pytest.fixture
def conn():
    connection = serve.demo_connection(now=NOW)
    yield connection
    connection.close()


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-123")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret-123")
    monkeypatch.delenv("KAZIKASI_DEMO", raising=False)
    monkeypatch.delenv("KAZIKASI_SECRET", raising=False)
    yield


class TestRsa:
    def test_a_valid_signature_verifies(self):
        body = "header.payload"
        signature = base64.urlsafe_b64decode(sign(claims()).split(".")[2] + "==")
        assert rsa_sha256_verify(body.encode(), signature, TEST_N, TEST_E) is False  # wrong input
        good = sign(claims())
        signing_input, _, encoded = good.rpartition(".")
        assert rsa_sha256_verify(signing_input.encode(), base64.urlsafe_b64decode(encoded + "=="), TEST_N, TEST_E)

    def test_a_flipped_byte_fails(self):
        good = sign(claims())
        signing_input, _, encoded = good.rpartition(".")
        raw = bytearray(base64.urlsafe_b64decode(encoded + "=="))
        raw[10] ^= 0xFF
        assert not rsa_sha256_verify(signing_input.encode(), bytes(raw), TEST_N, TEST_E)

    def test_a_truncated_signature_fails_rather_than_crashing(self):
        assert not rsa_sha256_verify(b"x", b"short", TEST_N, TEST_E)


class TestVerifyIdToken:
    def test_a_good_token_returns_its_claims(self):
        transport = Fetcher()
        result = verify_id_token(sign(claims()), PROVIDERS["google"], transport=transport, now=NOW)
        assert result["sub"] == "subject-1"
        assert result["email"] == "a@b.co"

    def test_alg_none_is_refused(self):
        token = sign(claims(), alg="none")
        with pytest.raises(ValueError, match="algorithm"):
            verify_id_token(token, PROVIDERS["google"], transport=Fetcher(), now=NOW)

    def test_a_tampered_payload_is_refused(self):
        token = sign(claims())
        head, _, sig = token.rpartition(".")
        forged = head.rsplit(".", 1)[0] + "." + _b64(json.dumps(claims(email="evil@x.co")).encode()) + "." + sig
        with pytest.raises(ValueError, match="signature"):
            verify_id_token(forged, PROVIDERS["google"], transport=Fetcher(), now=NOW)

    def test_a_token_signed_by_an_unpublished_key_is_refused(self):
        """A single published key is used even without a `kid`, but the signature
        still has to verify against it — the signature is the security boundary."""
        token = sign(claims())
        wrong_key = jwks_payload()
        wrong_key["keys"][0]["n"] = TEST_N[:-4] + "AAAA"
        with pytest.raises(ValueError, match="signature"):
            verify_id_token(token, PROVIDERS["google"], transport=Fetcher(keys=wrong_key), now=NOW)

    def test_the_wrong_issuer_is_refused(self):
        token = sign(claims(iss="https://evil.example"))
        with pytest.raises(ValueError, match="issuer"):
            verify_id_token(token, PROVIDERS["google"], transport=Fetcher(), now=NOW)

    def test_the_wrong_audience_is_refused(self):
        token = sign(claims(aud="someone-else"))
        with pytest.raises(ValueError, match="different client"):
            verify_id_token(token, PROVIDERS["google"], transport=Fetcher(), now=NOW)

    def test_a_list_audience_is_accepted_when_ours_is_in_it(self):
        token = sign(claims(aud=["other", "client-123"]))
        assert verify_id_token(token, PROVIDERS["google"], transport=Fetcher(), now=NOW)["sub"] == "subject-1"

    def test_an_expired_token_is_refused(self):
        token = sign(claims(exp=int((NOW - timedelta(hours=1)).timestamp())))
        with pytest.raises(ValueError, match="expired"):
            verify_id_token(token, PROVIDERS["google"], transport=Fetcher(), now=NOW)

    def test_a_token_with_no_expiry_is_refused(self):
        payload = claims()
        payload.pop("exp")
        with pytest.raises(ValueError, match="expiry"):
            verify_id_token(sign(payload), PROVIDERS["google"], transport=Fetcher(), now=NOW)

    def test_a_future_token_is_refused(self):
        token = sign(claims(iat=int((NOW + timedelta(hours=2)).timestamp())))
        with pytest.raises(ValueError, match="future"):
            verify_id_token(token, PROVIDERS["google"], transport=Fetcher(), now=NOW)

    def test_a_jwks_failure_fails_closed(self):
        with pytest.raises(OSError):
            verify_id_token(sign(claims()), PROVIDERS["google"], transport=Fetcher(fail=True), now=NOW)

    def test_keys_are_cached_for_an_hour(self):
        transport = Fetcher()
        verify_id_token(sign(claims()), PROVIDERS["google"], transport=transport, now=NOW)
        verify_id_token(sign(claims()), PROVIDERS["google"], transport=transport, now=NOW)
        assert sum(1 for method, url in transport.calls if "certs" in url) == 1

    def test_a_malformed_token_is_refused_politely(self):
        for token in ("", "abc", "a.b", "a.b.c.d"):
            with pytest.raises(ValueError):
                verify_id_token(token, PROVIDERS["google"], transport=Fetcher(), now=NOW)

    def test_apple_and_linkedin_have_their_own_issuers_and_keys(self):
        apple = sign(claims(iss="https://appleid.apple.com", aud="client-123"))
        assert verify_id_token(apple, PROVIDERS["apple"], transport=Fetcher(), now=NOW)["sub"] == "subject-1"
        with pytest.raises(ValueError, match="issuer"):
            verify_id_token(apple, PROVIDERS["google"], transport=Fetcher(), now=NOW)


class TestExchange:
    def test_it_verifies_before_it_trusts(self):
        transport = Fetcher(token={"access_token": "t", "id_token": sign(claims())})
        identity = accounts.exchange(PROVIDERS["google"], code="c", verifier="v", redirect_uri="https://x/cb", transport=transport, now=NOW)
        assert identity == {"subject": "subject-1", "email": "a@b.co", "email_verified": True, "name": "A B"}

    def test_a_forged_id_token_raises(self):
        forged = sign(claims(email="evil@x.co"))
        head, _, sig = forged.rpartition(".")
        forged = head.rsplit(".", 1)[0] + "." + _b64(json.dumps(claims(sub="evil", email="evil@x.co")).encode()) + "." + sig
        transport = Fetcher(token={"access_token": "t", "id_token": forged})
        with pytest.raises(ValueError, match="signature"):
            accounts.exchange(PROVIDERS["google"], code="c", verifier="v", redirect_uri="https://x/cb", transport=transport, now=NOW)

    def test_userinfo_cannot_override_verified_claims(self):
        transport = Fetcher(
            token={"access_token": "t", "id_token": sign(claims(email="real@x.co"))},
            userinfo={"sub": "subject-1", "email": "spoofed@x.co"},
        )
        identity = accounts.exchange(PROVIDERS["google"], code="c", verifier="v", redirect_uri="https://x/cb", transport=transport, now=NOW)
        assert identity["email"] == "real@x.co"

    def test_userinfo_fills_gaps_when_there_is_no_id_token(self):
        transport = Fetcher(token={"access_token": "t"}, userinfo={"sub": "li-1", "email": "a@b.co"})
        identity = accounts.exchange(PROVIDERS["linkedin"], code="c", verifier="v", redirect_uri="https://x/cb", transport=transport, now=NOW)
        assert identity["subject"] == "li-1"


class TestReadiness:
    def test_it_lists_the_variables_that_are_missing(self):
        payload = accounts.readiness(base_url="https://kazi.test")
        google = payload["providers"]["google"]
        assert google["configured"] is True
        assert google["redirect_uri"] == "https://kazi.test/auth/google/callback"
        assert payload["providers"]["apple"]["configured"] is False
        assert "APPLE_CLIENT_ID" in payload["providers"]["apple"]["missing"]

    def test_it_never_returns_a_secret(self, monkeypatch):
        monkeypatch.setenv("KAZIKASI_SECRET", "s3cret-value")
        blob = json.dumps(accounts.readiness())
        assert "s3cret-value" not in blob
        assert json.loads(blob)["session"]["secret_set"] is True

    def test_the_demo_secret_is_flagged(self):
        assert accounts.readiness()["session"]["uses_demo_secret"] is True


class TestStrictMode:
    def test_demo_is_the_default(self, monkeypatch):
        monkeypatch.delenv("KAZIKASI_DEMO", raising=False)
        assert accounts.strict_mode() is False

    def test_strict_mode_refuses_the_demo_secret(self, monkeypatch):
        monkeypatch.setenv("KAZIKASI_DEMO", "0")
        monkeypatch.delenv("KAZIKASI_SECRET", raising=False)
        with pytest.raises(RuntimeError, match="KAZIKASI_SECRET"):
            accounts.session_cookie("acc_1", NOW)

    def test_strict_mode_refuses_the_literal_demo_value(self, monkeypatch):
        monkeypatch.setenv("KAZIKASI_DEMO", "0")
        monkeypatch.setenv("KAZIKASI_SECRET", accounts.DEMO_SECRET)
        with pytest.raises(RuntimeError):
            accounts.session_cookie("acc_1", NOW)

    def test_strict_mode_accepts_a_real_secret(self, monkeypatch):
        monkeypatch.setenv("KAZIKASI_DEMO", "0")
        monkeypatch.setenv("KAZIKASI_SECRET", "a-long-random-value")
        cookie = accounts.session_cookie("acc_1", NOW).split(";")[0]
        assert accounts.read_session({"cookie": cookie}) == "acc_1"

    def test_a_cookie_signed_with_one_secret_fails_under_another(self, monkeypatch):
        monkeypatch.setenv("KAZIKASI_SECRET", "first")
        cookie = accounts.session_cookie("acc_1", NOW).split(";")[0]
        monkeypatch.setenv("KAZIKASI_SECRET", "second")
        assert accounts.read_session({"cookie": cookie}) is None


class TestTheReadyEndpoint:
    def test_it_answers_json(self, conn):
        response = serve.handle(conn, "GET", "/auth/ready", {}, headers={"accept": "application/json"}, demo=True, now=NOW)
        assert response.status == 200
        payload = json.loads(response.body)
        assert set(payload["providers"]) == {"google", "apple", "linkedin"}
        assert "providers" in payload and "session" in payload

    def test_the_signin_page_says_when_nothing_is_connected(self, conn, monkeypatch):
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        body = serve.handle(conn, "GET", "/signin", {}, headers={"accept": "text/html"}, demo=True, now=NOW).body
        assert "No provider is connected" in body

    def test_the_signin_page_stops_saying_it_once_a_provider_is_configured(self, conn):
        body = serve.handle(conn, "GET", "/signin", {}, headers={"accept": "text/html"}, demo=True, now=NOW).body
        assert "No provider is connected" not in body


class TestSyntheticLabelling:
    """Setting KAZIKASI_DEMO=0 must not un-label synthetic vacancies."""

    def test_no_database_means_synthetic(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        assert serve.synthetic_build() is True

    def test_a_database_flips_it(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgres://example")
        assert serve.synthetic_build() is False

    def test_strict_sessions_do_not_change_the_label(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("KAZIKASI_DEMO", "0")
        assert serve.synthetic_build() is True
        assert accounts.strict_mode() is True


class TestTheCheckCommand:
    def test_it_reports_readiness_and_exits_nonzero_when_nothing_is_wired(self, capsys, monkeypatch):
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
        assert cli.main(["auth", "check"]) == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["ready"] is False

    def test_it_exits_zero_when_a_provider_is_configured(self, capsys):
        assert cli.main(["auth", "check"]) == 0
        assert json.loads(capsys.readouterr().out)["providers"]["google"]["configured"] is True

    def test_it_can_probe_the_key_set(self, capsys, monkeypatch):
        monkeypatch.setattr(accounts, "jwks", lambda provider, transport=None: [{"kid": "k"}])
        assert cli.main(["auth", "check", "--live"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["providers"]["google"]["jwks_keys"] == 1
