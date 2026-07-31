#!/usr/bin/env python3
"""Dibs — poll internship listings, email new roles matching your watchlist.

Run by GitHub Actions on a schedule. First run seeds state silently; every run
after emails the new matches, then records only the IDs it successfully sent.
"""
import json
import os
import re
import smtplib
import time
import urllib.request
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yaml

# (display name, state key, listings.json URL). Order matters: first wins on
# same-run URL collisions (Simplify preferred over vansh).
SOURCES = [
    (
        "Simplify",
        "simplify",
        "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships"
        "/dev/.github/scripts/listings.json",
    ),
    (
        "vansh",
        "vansh",
        "https://raw.githubusercontent.com/vanshb03/Summer2027-Internships"
        "/dev/.github/scripts/listings.json",
    ),
]
STATE_KEYS = tuple(k for _, k, _ in SOURCES)
STATE_FILE = Path("state.json")
CONFIG_FILE = Path("config.yaml")


def normalize(name: str) -> str:
    """Lowercase, drop corp suffixes, strip punctuation, collapse whitespace."""
    name = name.lower()
    name = re.sub(r"\b(inc|llc|corp|corporation|ltd|co)\b", "", name)
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def fingerprint(url: str | None) -> str | None:
    """Stable apply-URL key for cross-source dedup. None if URL unusable."""
    if not url:
        return None
    u = url.strip()
    p = urlparse(u)
    host, path = p.netloc.lower(), p.path.rstrip("/").lower()
    q = parse_qs(p.query)
    m = re.search(r"ashbyhq\.com/([^/]+)/([0-9a-f-]{36})", u, re.I)
    if m:
        return f"ashby:{m.group(1).lower()}:{m.group(2).lower()}"
    m = re.search(r"lever\.co/([^/]+)/([0-9a-f-]{36})", u, re.I)
    if m:
        return f"lever:{m.group(1).lower()}:{m.group(2).lower()}"
    if q.get("gh_jid"):
        return f"ghjid:{q['gh_jid'][0]}"
    m = re.search(r"/jobs/(\d+)", path)
    if m:
        return f"jobs:{host}:{m.group(1)}"
    if host or path:
        return f"url:{host}{path}"
    return None


def _tag(raw: list, label: str, key: str) -> list:
    out = []
    for item in raw:
        l = dict(item)
        l["source"] = label
        l["_key"] = key
        if not l.get("terms") and l.get("season"):
            l["terms"] = [l["season"]]
        out.append(l)
    return out


def fetch_listings() -> list:
    """Fetch all sources. One failure is skipped; all failing raises."""
    out, failed = [], []
    for label, key, url in SOURCES:
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                out.extend(_tag(json.load(r), label, key))
        except Exception as e:
            print(f"WARN: {label} fetch failed: {e}")
            failed.append(label)
    if len(failed) == len(SOURCES):
        raise RuntimeError(f"all sources failed: {failed}")
    return out


def load_watchlist(cfg: dict) -> list | str:
    """[(normalized_company, [role_keywords_lower]), ...], or the "all" sentinel.
    A top-level `companies: all` (bare string) means match every company."""
    companies = cfg.get("companies")
    if isinstance(companies, str) and companies.strip().lower() == "all":
        return "all"
    out = []
    for item in companies or []:
        if isinstance(item, str):
            name, roles = item, []
        else:
            name, roles = item["name"], item.get("roles") or []
        comp = normalize(name)
        if not comp:
            continue  # a name that normalizes to "" would match everything
        out.append((comp, [r.lower() for r in roles]))
    return out


def matches(listing: dict, watchlist: list | str) -> bool:
    if watchlist == "all":
        return True
    company = normalize(listing.get("company_name", ""))
    title = (listing.get("title") or "").lower()
    for comp, roles in watchlist:
        if comp in company and (not roles or any(k in title for k in roles)):
            return True
    return False


def _empty_state() -> dict:
    return {k: set() for k in STATE_KEYS} | {"fingerprints": set()}


def load_state():
    """State dict, or None on the very first run (no state file yet).

    Legacy format was a bare JSON array of Simplify UUIDs.
    """
    if not STATE_FILE.exists():
        return None
    data = json.loads(STATE_FILE.read_text())
    if isinstance(data, list):
        st = _empty_state()
        st["simplify"] = set(data)
        return st
    st = _empty_state()
    for k in STATE_KEYS:
        st[k] = set(data.get(k) or [])
    st["fingerprints"] = set(data.get("fingerprints") or [])
    return st


def save_state(state: dict) -> None:
    obj = {k: sorted(state[k]) for k in STATE_KEYS}
    obj["fingerprints"] = sorted(state["fingerprints"])
    STATE_FILE.write_text(json.dumps(obj, indent=0))


def _mark(state: dict, listing: dict) -> None:
    state[listing["_key"]].add(listing["id"])
    fp = fingerprint(listing.get("url"))
    if fp:
        state["fingerprints"].add(fp)


def _seen(state: dict, listing: dict) -> bool:
    if listing["id"] in state[listing["_key"]]:
        return True
    fp = fingerprint(listing.get("url"))
    return bool(fp and fp in state["fingerprints"])


def posted_ago(ts) -> str:
    """Human 'posted Nh ago' from a unix timestamp, or '' if unavailable."""
    if not ts:
        return ""
    secs = max(0, int(time.time()) - int(ts))
    if secs < 3600:
        return f"posted {secs // 60}m ago"
    if secs < 86400:
        return f"posted {secs // 3600}h ago"
    return f"posted {secs // 86400}d ago"


FRESH_THRESHOLD_SECS = 72 * 3600


def is_fresh(listing: dict) -> bool:
    """True if date_posted is within the last FRESH_THRESHOLD_SECS."""
    ts = listing.get("date_posted")
    return bool(ts) and int(time.time()) - int(ts) <= FRESH_THRESHOLD_SECS


def _render_listings(items: list) -> str:
    lines = []
    for l in sorted(items, key=lambda x: (x.get("company_name") or "").lower()):
        loc = ", ".join(l.get("locations") or []) or "location N/A"
        term = ", ".join(l.get("terms") or []) or ""
        age = posted_ago(l.get("date_posted"))
        detail = "  ".join(p for p in (loc, f"({term})" if term else "", age) if p)
        src = l.get("source") or ""
        head = f"{l.get('company_name')} — {l.get('title')}"
        if src:
            head += f"  [{src}]"
        lines.append(head)
        lines.append(f"  {detail}")
        lines.append(f"  {l.get('url', '')}")
        lines.append("")
    return "\n".join(lines)


def format_body(new: list) -> str:
    fresh = [l for l in new if is_fresh(l)]
    late = [l for l in new if not is_fresh(l)]
    sections = []
    if fresh:
        sections.append("Fresh (posted in last 72h) — apply now\n\n"
                        + _render_listings(fresh).rstrip())
    if late:
        sections.append("Late discoveries / reopened — found late or req reopened\n\n"
                        + _render_listings(late).rstrip())
    return "\n\n".join(sections) + "\n"


def send_email(new: list) -> None:
    user = os.environ["GMAIL_USER"]
    pw = os.environ["GMAIL_APP_PASSWORD"]
    to = os.environ.get("RECIPIENT") or user
    n = len(new)
    msg = EmailMessage()
    msg["Subject"] = f"Dibs: {n} new listing{'s' if n != 1 else ''}"
    msg["From"] = user
    msg["To"] = to
    msg.set_content(format_body(new))
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls()
        s.login(user, pw)
        s.send_message(msg)


def main() -> None:
    cfg = yaml.safe_load(CONFIG_FILE.read_text()) or {}
    watchlist = load_watchlist(cfg)
    listings = fetch_listings()
    active = [l for l in listings if l.get("active") and l.get("is_visible")]
    state = load_state()

    if state is None:
        state = _empty_state()
        for l in active:
            _mark(state, l)
        save_state(state)
        n = sum(len(state[k]) for k in STATE_KEYS)
        print(f"First run: seeded {n} listings, no email.")
        return

    # Upgrade path: silent-seed vansh (+ backfill fps for known Simplify opens).
    if not state["vansh"]:
        for l in active:
            if l["_key"] == "vansh" or l["id"] in state["simplify"]:
                _mark(state, l)
        save_state(state)
        print(f"Bootstrapped vansh ({len(state['vansh'])} ids), no email.")
        return

    candidates = [l for l in active if not _seen(state, l) and matches(l, watchlist)]
    # Same-run URL collapse: first source in SOURCES order wins.
    new, seen_fp = [], set()
    for l in candidates:
        fp = fingerprint(l.get("url"))
        if fp:
            if fp in seen_fp:
                continue
            seen_fp.add(fp)
        new.append(l)

    if not new:
        print("No new matches.")
        return

    send_email(new)  # notify-before-persist: only record what we actually sent
    emailed_fps = {fingerprint(l.get("url")) for l in new} - {None}
    for l in new:
        _mark(state, l)
    # Same job on the other source: record its id too so it never re-alerts.
    for l in active:
        fp = fingerprint(l.get("url"))
        if fp and fp in emailed_fps:
            state[l["_key"]].add(l["id"])
    save_state(state)
    print(f"Emailed {len(new)} new listing(s).")


if __name__ == "__main__":
    main()
