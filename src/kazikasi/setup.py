"""Go-live: what is configured, what is not, and what to paste where.

Every deployment of this thing has the same conversation. *"It says I need a
variable."* Which variable, in which field, with what value, and what will change
once it is there? The answers live in six different consoles and one README.

This module turns them into **one page, computed from the running process**. Not
prose that ages: a snapshot of which variables exist, which provider is wired,
whether the corpus is real, and what the cron tick would do if it fired right now.

Two rules:

* **Presence, never values.** The page answers "is `KAZIKASI_SECRET` set?", never
  "what is it?". A secret that renders is a secret that leaks through a proxy log,
  a screenshot, or a shared link.
* **Every missing step names its next click** — the console URL to open, the exact
  redirect URI to paste, and the field in Vercel it goes into. A checklist that
  says "configure OAuth" is a riddle; this one says which box.

The state is derived, never stored: change a variable, redeploy, reload.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

from . import accounts, bundle as bundle_module, metrics
from . import db as database

#: What each state means, in the tone the renderer uses.
STATE_TONE = {
    "done": "good",
    "missing": "warn",
    "optional": "muted",
    "deferred": "muted",
}
STATE_LABEL = {
    "done": "set",
    "missing": "missing",
    "optional": "optional",
    "deferred": "not yet",
}

#: The three variables that make sessions safe. All three, or none.
SESSION_ENV = ("KAZIKASI_SECRET", "KAZIKASI_DEMO", "KAZIKASI_BASE_URL")


def _has(name: str) -> bool:
    return bool((os.environ.get(name) or "").strip())


@dataclass
class Paste:
    """A value the person copies into a console or a variable row."""

    label: str
    value: str


@dataclass
class Step:
    id: str
    title: str
    state: str
    why: str
    env: tuple[str, ...] = ()
    paste: tuple[Paste, ...] = ()
    link: tuple[str, str] | None = None  # (label, href)
    note: str = ""
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "state": self.state,
            "why": self.why,
            "env": list(self.env),
            "paste": [{"label": item.label, "value": item.value} for item in self.paste],
            "link": ({"label": self.link[0], "href": self.link[1]} if self.link else None),
            "note": self.note,
            "detail": self.detail,
        }


@dataclass
class Plan:
    steps: list[Step] = field(default_factory=list)
    instance: dict = field(default_factory=dict)
    troubleshooting: list[dict] = field(default_factory=list)

    @property
    def required(self) -> list[Step]:
        return [step for step in self.steps if step.state != "deferred" and step.state != "optional"]

    @property
    def done(self) -> int:
        return sum(1 for step in self.steps if step.state == "done")

    @property
    def outstanding(self) -> list[Step]:
        return [step for step in self.steps if step.state == "missing"]

    @property
    def live(self) -> bool:
        """True when nothing mandatory is missing."""
        return not self.outstanding

    def to_dict(self) -> dict:
        return {
            "live": self.live,
            "done": self.done,
            "total": len(self.steps),
            "steps": [step.to_dict() for step in self.steps],
            "instance": self.instance,
            "troubleshooting": self.troubleshooting,
        }


def _redirect(key: str, base_url: str) -> str:
    return f"{base_url.rstrip('/')}/auth/{key}/callback"


def _provider_blocks(base_url: str) -> dict:
    readiness = accounts.readiness(base_url=base_url)
    for key, provider in readiness["providers"].items():
        provider.setdefault("redirect_uri", _redirect(key, base_url))
    return readiness["providers"]


def plan(
    conn,
    *,
    now: datetime | None = None,
    synthetic: bool,
    strict: bool,
    base_url: str = "https://kazi-kasi-app.vercel.app",
) -> Plan:
    """The whole go-live picture, from the process that is serving this request."""
    momentum = now or datetime.now(timezone.utc)
    providers = _provider_blocks(base_url)
    session = accounts.readiness(base_url=base_url)["session"]
    summary = metrics.stats(conn, now=momentum)

    steps: list[Step] = []

    # 1 — sessions ---------------------------------------------------------
    session_env = tuple(name for name in SESSION_ENV if not _has(name))
    steps.append(
        Step(
            id="session",
            title="Session secret and production mode",
            state="done" if (session["secret_set"] and not session["uses_demo_secret"]) else "missing",
            why=(
                "A cookie signed with the demo secret is a cookie anyone can forge. "
                "Until this is set, sign-in is decoration."
            ),
            env=SESSION_ENV,
            note=(
                "Each variable is its own row in Vercel: Settings → Environment "
                "Variables → Add another. There is no bulk-paste box."
            ),
            detail=(
                f"secret set: {session['secret_set']} · demo secret in use: "
                f"{session['uses_demo_secret']} · strict: {strict}"
            ),
        )
    )

    # 2 — Google -----------------------------------------------------------
    google = providers["google"]
    steps.append(
        Step(
            id="google",
            title="Google sign-in",
            state="done" if google["configured"] else "missing",
            why="The one provider worth doing first: no company page, no paid account.",
            env=("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"),
            paste=(Paste("Authorised redirect URI", google["redirect_uri"]),),
            link=("Open Google Cloud credentials", "https://console.cloud.google.com/apis/credentials"),
            note=(
                "In Google Cloud: create a project → APIs & Services → Credentials → "
                "Create credentials → OAuth client ID → Web application, then paste the "
                "redirect URI above into Authorised redirect URIs. While the consent "
                "screen is in Testing, add your own address as a test user."
            ),
            detail="" if google["configured"] else "missing: " + ", ".join(google["missing"]),
        )
    )

    # 3 — LinkedIn ---------------------------------------------------------
    linkedin = providers["linkedin"]
    steps.append(
        Step(
            id="linkedin",
            title="LinkedIn sign-in",
            state="done" if linkedin["configured"] else "optional",
            why=(
                "Useful for people who live on LinkedIn, but the developer console "
                "demands a Company Page you administer before the app can exist."
            ),
            env=("LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET"),
            paste=(Paste("Authorised redirect URL", linkedin["redirect_uri"]),),
            link=("Open LinkedIn app console", "https://www.linkedin.com/developers/apps/new"),
            note=(
                "The “LinkedIn Page” field on that form wants the URL of a Company Page "
                "you administer — not the callback. Create one at "
                "linkedin.com/company/setup/new, then type its name back into the field "
                "and pick it from the list. Skip this entirely until Google works."
            ),
            detail="" if linkedin["configured"] else "missing: " + ", ".join(linkedin["missing"]),
        )
    )

    # 4 — Apple ------------------------------------------------------------
    apple = providers["apple"]
    steps.append(
        Step(
            id="apple",
            title="Apple sign-in",
            state="done" if apple["configured"] else "deferred",
            why=(
                "Needs a paid Apple Developer account and a rotating client secret. "
                "Deferred on purpose: the audience is Android-first."
            ),
            env=("APPLE_CLIENT_ID", "APPLE_CLIENT_SECRET"),
            note="Revisit when there is an iOS app or a paying cohort on iPhones.",
        )
    )

    # 5 — storage ----------------------------------------------------------
    store = _store()
    steps.append(
        Step(
            id="storage",
            title="Real storage",
            state="done" if not synthetic else "missing",
            why=(
                "Without a store, every cold start rebuilds the synthetic corpus: "
                "nothing anyone saves survives, and the vacancies are invented."
            ),
            env=("DATABASE_URL", "KAZIKASI_BUNDLE"),
            note=(
                "Either one works. DATABASE_URL (Neon or Supabase, free tier is enough) "
                "makes the sweep and the outbox persistent. KAZIKASI_BUNDLE points at a "
                "published sweep file and is read-only, but it is real vacancies."
            ),
            detail=store["detail"],
        )
    )

    # 6 — delivery ---------------------------------------------------------
    whatsapp = _has("WHATSAPP_TOKEN") and _has("WHATSAPP_PHONE_NUMBER_ID")
    sms = _has("AT_USERNAME") and _has("AT_API_KEY")
    steps.append(
        Step(
            id="delivery",
            title="A transport that can actually send",
            state="done" if (whatsapp or sms) else "optional",
            why=(
                "The digest, the closing alert and saved searches all end in one "
                "message. No transport means the tick refuses with 503 rather than "
                "pretending it sent something."
            ),
            env=("WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "AT_USERNAME", "AT_API_KEY"),
            note=(
                "WhatsApp Cloud API for the digest, Africa's Talking as the SMS "
                "fallback. One of them is enough to start; the fallback is what saves a "
                "number that is not on WhatsApp."
            ),
            detail=f"whatsapp: {'set' if whatsapp else 'unset'} · sms: {'set' if sms else 'unset'}",
        )
    )

    # 7 — the clock --------------------------------------------------------
    cron = _has("CRON_SECRET")
    steps.append(
        Step(
            id="cron",
            title="The scheduled tick",
            state="done" if cron else "optional",
            why=(
                "A digest nobody triggers is not a product. Without this, the endpoint "
                "answers 503 and no scheduled message ever goes out."
            ),
            env=("CRON_SECRET",),
            paste=(Paste("Vercel cron path", "/api/cron/run"), Paste("Schedule (UTC)", "0 15 * * *")),
            note=(
                "Any long random string. Vercel sends it as a bearer token automatically "
                "when the variable exists; the schedule above is 18:00 EAT."
            ),
        )
    )

    instance = {
        "build": (os.environ.get("VERCEL_GIT_COMMIT_SHA") or "")[:7] or "dev",
        "schema": database.SCHEMA_VERSION,
        "live_jobs": summary["live_jobs"],
        "sources": len(summary["jobs_per_source"]),
        "synthetic": synthetic,
        "strict": strict,
        "corpus": {
            "source": bundle_module.STATE.get("source", "synthetic"),
            "built_at": bundle_module.STATE.get("built_at"),
            "count": bundle_module.STATE.get("count", 0),
            "error": bundle_module.STATE.get("error"),
        },
        "tick": _tick(synthetic=synthetic, cron=cron, transport=whatsapp or sms),
        "checked_at": momentum.isoformat(),
    }

    return Plan(
        steps=steps,
        instance=instance,
        troubleshooting=[
            {
                "symptom": "Google Cloud shows “403. That’s an error. Your client does not have permission to get URL /”.",
                "cause": (
                    "That is Google’s own page, not this app: the console could not decide "
                    "which project or account to open — usually two accounts signed in at once."
                ),
                "fix": (
                    "Open a private window, sign in with a single Google account, then go "
                    "straight to console.cloud.google.com/projectcreate. If it persists, the "
                    "account is a work or school account with Cloud disabled; use a personal one."
                ),
            },
            {
                "symptom": "LinkedIn says “Please input a valid LinkedIn Page URL or type to search by company name.”",
                "cause": (
                    "The field wants a Company Page you administer. The callback URL from "
                    "this page belongs in the Auth tab, after the app exists — not there."
                ),
                "fix": (
                    "Create a page at linkedin.com/company/setup/new (name, industry, size, "
                    "website), then type the page name into the field and pick it. Or skip "
                    "LinkedIn until Google sign-in works."
                ),
            },
            {
                "symptom": "A new variable changed nothing on the live site.",
                "cause": "Variables apply to a build, not to the running one.",
                "fix": "Deployments → the top entry → ⋯ → Redeploy. Then reload /api/setup.",
            },
        ],
    )


def _store() -> dict:
    url_set = _has("DATABASE_URL")
    bundle_set = _has("KAZIKASI_BUNDLE")
    if url_set:
        return {"detail": "DATABASE_URL is set."}
    if bundle_set and bundle_module.STATE.get("source") == "bundle":
        age = bundle_module.STATE.get("built_at") or "unknown build time"
        return {"detail": f"Reading a bundle built {age} ({bundle_module.STATE.get('count', 0)} roles)."}
    if bundle_set:
        return {
            "detail": "KAZIKASI_BUNDLE is set but the bundle did not load: "
            + str(bundle_module.STATE.get("error") or "no reason recorded")
        }
    return {"detail": "Neither DATABASE_URL nor KAZIKASI_BUNDLE is set."}


def _tick(*, synthetic: bool, cron: bool, transport: bool) -> dict:
    """What the cron endpoint would do if it fired right now — in order."""
    if not cron:
        return {"runs": False, "answer": "503 cron not configured", "needs": "CRON_SECRET"}
    if synthetic and os.environ.get("KAZIKASI_ALLOW_SYNTHETIC_SEND") != "1":
        return {
            "runs": False,
            "answer": "409 refusing to send",
            "needs": "real storage (DATABASE_URL or KAZIKASI_BUNDLE)",
        }
    if not transport:
        return {
            "runs": False,
            "answer": "503 no transport configured",
            "needs": "WHATSAPP_TOKEN + WHATSAPP_PHONE_NUMBER_ID, or AT_USERNAME + AT_API_KEY",
        }
    return {"runs": True, "answer": "200 delivery attempted", "needs": ""}
