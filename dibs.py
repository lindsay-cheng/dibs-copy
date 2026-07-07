#!/usr/bin/env python3
"""Dibs — poll SimplifyJobs listings, email new roles matching your watchlist.

Run by GitHub Actions on a schedule. First run seeds state silently; every run
after emails the new matches, then records only the IDs it successfully sent.
"""
import json
import os
import re
import smtplib
import urllib.request
from email.message import EmailMessage
from pathlib import Path

import yaml

LISTINGS_URL = (
    "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships"
    "/dev/.github/scripts/listings.json"
)
STATE_FILE = Path("state.json")
CONFIG_FILE = Path("config.yaml")


def normalize(name: str) -> str:
    """Lowercase, drop corp suffixes, strip punctuation, collapse whitespace."""
    name = name.lower()
    name = re.sub(r"\b(inc|llc|corp|corporation|ltd|co)\b", "", name)
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def fetch_listings() -> list:
    with urllib.request.urlopen(LISTINGS_URL, timeout=60) as r:
        return json.load(r)


def load_watchlist(cfg: dict) -> list:
    """[(normalized_company, [role_keywords_lower]), ...]. Empty roles = all."""
    out = []
    for item in cfg.get("companies") or []:
        if isinstance(item, str):
            name, roles = item, []
        else:
            name, roles = item["name"], item.get("roles") or []
        comp = normalize(name)
        if not comp:
            continue  # a name that normalizes to "" would match everything
        out.append((comp, [r.lower() for r in roles]))
    return out


def matches(listing: dict, watchlist: list) -> bool:
    company = normalize(listing.get("company_name", ""))
    title = (listing.get("title") or "").lower()
    for comp, roles in watchlist:
        if comp in company and (not roles or any(k in title for k in roles)):
            return True
    return False


def load_state():
    """Set of seen IDs, or None on the very first run (no state file yet)."""
    if STATE_FILE.exists():
        return set(json.loads(STATE_FILE.read_text()))
    return None


def save_state(ids: set) -> None:
    STATE_FILE.write_text(json.dumps(sorted(ids), indent=0))


def format_body(new: list) -> str:
    lines = []
    for l in sorted(new, key=lambda x: (x.get("company_name") or "").lower()):
        loc = ", ".join(l.get("locations") or []) or "location N/A"
        term = ", ".join(l.get("terms") or []) or ""
        lines.append(f"{l.get('company_name')} — {l.get('title')}")
        lines.append(f"  {loc}" + (f"  ({term})" if term else ""))
        lines.append(f"  {l.get('url', '')}")
        lines.append("")
    return "\n".join(lines)


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
    listings = fetch_listings()  # raises on fetch failure -> job fails, retry next run
    active = [l for l in listings if l.get("active") and l.get("is_visible")]
    seen = load_state()

    if seen is None:
        save_state({l["id"] for l in active})
        print(f"First run: seeded {len(active)} listings, no email.")
        return

    new = [l for l in active if l["id"] not in seen and matches(l, watchlist)]
    if not new:
        print("No new matches.")
        return

    send_email(new)  # notify-before-persist: only record what we actually sent
    seen |= {l["id"] for l in new}
    save_state(seen)
    print(f"Emailed {len(new)} new listing(s).")


if __name__ == "__main__":
    main()
