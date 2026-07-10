"""Self-checks for Dibs. Run: `python test_dibs.py`.

The logic checks need no framework, network, or credentials: the poll loop is
driven with stubbed listings and a stubbed sender. If you also set GMAIL_USER,
GMAIL_APP_PASSWORD and (optionally) RECIPIENT in your environment, it finishes by
sending one real test email so you can confirm your secrets work before relying
on the schedule. Without those vars that last step is skipped.
"""
import json
import os
import tempfile
import time
from pathlib import Path

import dibs
from dibs import normalize, matches, load_watchlist, posted_ago

_real_send_email = dibs.send_email  # capture before the e2e test stubs it out


# --- matching logic (the part that silently breaks) ---

assert normalize("Jane Street, Inc.") == "jane street"
assert normalize("Two Sigma") == "two sigma"
assert normalize("Costco") == "costco"  # "co" only stripped on word boundary

wl = load_watchlist({"companies": [
    "Stripe",
    {"name": "Google", "roles": ["software", "swe"]},
]})


def _l(company, title):
    return {"company_name": company, "title": title}


assert matches(_l("Stripe Inc.", "Anything"), wl)                 # bare -> any role
assert matches(_l("Google LLC", "Software Engineer Intern"), wl)  # keyword hit
assert not matches(_l("Google", "Product Manager"), wl)           # keyword miss
assert not matches(_l("Airbnb", "Software Engineer"), wl)         # not on list

# companies: all -> sentinel "all", matches everything (no role filter).
assert load_watchlist({"companies": "all"}) == "all"
assert matches(_l("Anything", "Any role"), "all")

# a name that normalizes to "" must never match everything
assert load_watchlist({"companies": ["!!!"]}) == []
assert not matches(_l("Anybody", "Any role"), load_watchlist({"companies": ["!!!"]}))

# posted_ago: unix timestamp -> human age, empty when the field is missing.
now = int(time.time())
assert posted_ago(now - 30 * 60) == "posted 30m ago"
assert posted_ago(now - 2 * 3600) == "posted 2h ago"
assert posted_ago(now - 3 * 86400) == "posted 3d ago"
assert posted_ago(None) == ""
assert posted_ago(0) == ""


# --- end to end: fetch -> filter -> match -> notify -> persist -> dedup ---

def _e2e():
    tmp = Path(tempfile.mkdtemp())
    dibs.STATE_FILE = tmp / "state.json"
    dibs.CONFIG_FILE = tmp / "config.yaml"
    dibs.CONFIG_FILE.write_text(
        "companies:\n  - Citadel\n  - name: Jane Street\n    roles: [software]\n"
    )

    listings = []                       # mutable "data source" the stub returns
    emails = []                         # ids per email the stub "sends"
    dibs.fetch_listings = lambda: listings
    dibs.send_email = lambda new: emails.append([l["id"] for l in new])

    def L(id, company, title, active=True, visible=True):
        return {"id": id, "company_name": company, "title": title,
                "active": active, "is_visible": visible,
                "locations": ["NYC"], "terms": ["Summer 2026"], "url": "http://x"}

    def seen():
        return set(json.loads(dibs.STATE_FILE.read_text()))

    # First run seeds silently: no email, all active+visible ids recorded.
    listings[:] = [
        L("a", "Citadel", "Quant Intern"),
        L("b", "Jane Street", "Software Engineer Intern"),
        L("z", "Airbnb", "Software Engineer Intern"),   # off-watchlist, still seeded
    ]
    dibs.main()
    assert emails == [], "first run must not email"
    assert seen() == {"a", "b", "z"}, "first run seeds every active+visible id"

    # A genuinely new matching role appears -> exactly that one is emailed + saved.
    listings.append(L("c", "Citadel Securities", "Machine Learning Intern"))
    dibs.main()
    assert emails == [["c"]], "only the new match is emailed"
    assert "c" in seen()

    # Same data again -> silent (dedup on stored ids).
    dibs.main()
    assert emails == [["c"]], "must not re-notify unchanged listings"

    # New but inactive / invisible / off-watchlist -> never notify, never persist.
    listings.append(L("d", "Jane Street", "Software Intern", active=False))
    listings.append(L("e", "Jane Street", "Software Intern", visible=False))
    listings.append(L("f", "Airbnb", "Software Engineer Intern"))  # active+visible, off-list
    dibs.main()
    assert emails == [["c"]], "inactive / invisible / off-list never notify"
    # notify-before-persist: only emailed ids are stored, so 'f' stays unseen.
    assert {"d", "e", "f"}.isdisjoint(seen())


_e2e()
print("logic: ok")


# --- optional live email: real Gmail send, only when secrets are set ---

def _live_email():
    if not (os.environ.get("GMAIL_USER") and os.environ.get("GMAIL_APP_PASSWORD")):
        print("email: skipped (set GMAIL_USER + GMAIL_APP_PASSWORD to send a test)")
        return
    demo = [{
        "company_name": "Dibs", "title": "Test email — your setup works",
        "locations": ["your inbox"], "terms": ["Summer 2026"],
        "url": "https://github.com/SimplifyJobs/Summer2026-Internships",
    }]
    _real_send_email(demo)  # raises loudly on a bad app password / login
    print(f"email: sent to {os.environ.get('RECIPIENT') or os.environ['GMAIL_USER']}")


_live_email()
