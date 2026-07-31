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
from dibs import normalize, matches, load_watchlist, posted_ago, fingerprint

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

# fingerprint: strip tracking, extract board ids, collapse mirrors.
assert fingerprint(
    "https://job-boards.greenhouse.io/virtu/jobs/8624410002?utm_source=x"
) == "jobs:job-boards.greenhouse.io:8624410002"
assert fingerprint(
    "https://jobs.ashbyhq.com/deepgram/dc8693b5-72ce-4ca3-ab15-9c8434d35da1?utm=1"
) == "ashby:deepgram:dc8693b5-72ce-4ca3-ab15-9c8434d35da1"
assert fingerprint(
    "https://jobs.lever.co/palantir/373367a9-3160-49d8-b7af-2efec062fad1"
) == "lever:palantir:373367a9-3160-49d8-b7af-2efec062fad1"
assert fingerprint("https://x.com/careers?gh_jid=7796180003") == "ghjid:7796180003"
assert fingerprint(None) is None
assert fingerprint("") is None


# --- end to end: fetch -> filter -> match -> notify -> persist -> dedup ---

def _e2e():
    tmp = Path(tempfile.mkdtemp())
    dibs.STATE_FILE = tmp / "state.json"
    dibs.CONFIG_FILE = tmp / "config.yaml"
    dibs.CONFIG_FILE.write_text(
        "companies:\n  - Citadel\n  - name: Jane Street\n    roles: [software]\n"
    )

    listings = []                       # mutable "data source" the stub returns
    emails = []                         # full listing dicts per email
    dibs.fetch_listings = lambda: listings
    dibs.send_email = lambda new: emails.append(list(new))

    def L(lid, company, title, source="Simplify", key="simplify",
          active=True, visible=True, url=None):
        return {"id": lid, "company_name": company, "title": title,
                "active": active, "is_visible": visible,
                "locations": ["NYC"], "terms": ["Summer 2027"],
                "url": url or f"http://x/{lid}",
                "source": source, "_key": key}

    def state():
        return json.loads(dibs.STATE_FILE.read_text())

    # First run seeds silently: no email, all active+visible ids + fps recorded.
    listings[:] = [
        L("a", "Citadel", "Quant Intern", url="http://board/jobs/1"),
        L("b", "Jane Street", "Software Engineer Intern", url="http://board/jobs/2"),
        L("z", "Airbnb", "Software Engineer Intern", url="http://board/jobs/3"),
        L("va", "Citadel", "Quant Intern", "vansh", "vansh", url="http://board/jobs/1"),
    ]
    dibs.main()
    assert emails == [], "first run must not email"
    st = state()
    assert set(st["simplify"]) == {"a", "b", "z"}
    assert set(st["vansh"]) == {"va"}
    assert "jobs:board:1" in st["fingerprints"]

    # Genuinely new matching role -> emailed + saved; source tag present.
    listings.append(L("c", "Citadel Securities", "Machine Learning Intern",
                      url="http://board/jobs/9"))
    dibs.main()
    assert len(emails) == 1 and [x["id"] for x in emails[0]] == ["c"]
    assert emails[0][0]["source"] == "Simplify"
    assert "c" in state()["simplify"]
    body = dibs.format_body(emails[0])
    assert "[Simplify]" in body

    # Same data again -> silent (dedup on stored ids).
    dibs.main()
    assert len(emails) == 1, "must not re-notify unchanged listings"

    # Same job via vansh (new id, same apply URL) -> suppressed by fingerprint.
    listings.append(L("v-c", "Citadel Securities", "Machine Learning Intern",
                      "vansh", "vansh", url="http://board/jobs/9"))
    dibs.main()
    assert len(emails) == 1, "cross-source URL match must not re-notify"
    assert "v-c" not in state()["vansh"]  # fp blocks before email; id not persisted

    # Same-run collision: Simplify + vansh both new, same URL -> Simplify only.
    listings.append(L("s1", "Jane Street", "Software Intern New",
                      url="http://board/jobs/42"))
    listings.append(L("v1", "Jane Street", "Software Intern New",
                      "vansh", "vansh", url="http://board/jobs/42"))
    dibs.main()
    assert [x["id"] for x in emails[-1]] == ["s1"], "same-run: Simplify wins"
    assert emails[-1][0]["source"] == "Simplify"
    st = state()
    assert "s1" in st["simplify"] and "v1" in st["vansh"]
    assert "jobs:board:42" in st["fingerprints"]

    # Different URLs, same company/title -> both alert (dupes OK).
    listings.append(L("s2", "Citadel", "Other Intern", url="http://a/jobs/100"))
    listings.append(L("v2", "Citadel", "Other Intern", "vansh", "vansh",
                      url="http://b/jobs/100"))
    dibs.main()
    got = {x["id"] for x in emails[-1]}
    assert got == {"s2", "v2"}, "distinct URLs must both alert"

    # New but inactive / invisible / off-watchlist -> never notify.
    n_before = len(emails)
    listings.append(L("d", "Jane Street", "Software Intern", active=False))
    listings.append(L("e", "Jane Street", "Software Intern", visible=False))
    listings.append(L("f", "Airbnb", "Software Engineer Intern",
                      url="http://board/jobs/77"))
    dibs.main()
    assert len(emails) == n_before
    assert "f" not in state()["simplify"]

    # --- legacy array migration + vansh bootstrap (no email flood) ---
    tmp2 = Path(tempfile.mkdtemp())
    dibs.STATE_FILE = tmp2 / "state.json"
    dibs.CONFIG_FILE = tmp2 / "config.yaml"
    dibs.CONFIG_FILE.write_text("companies: all\n")
    emails.clear()
    dibs.STATE_FILE.write_text(json.dumps(["old-s"]))
    listings[:] = [
        L("old-s", "Acme", "Intern", url="http://board/jobs/50"),
        L("new-v", "Beta", "Intern", "vansh", "vansh", url="http://board/jobs/51"),
        L("dup-v", "Acme", "Intern", "vansh", "vansh", url="http://board/jobs/50"),
    ]
    dibs.main()
    assert emails == [], "vansh bootstrap must not email"
    st = state()
    assert set(st["simplify"]) == {"old-s"}
    assert set(st["vansh"]) == {"new-v", "dup-v"}
    assert "jobs:board:50" in st["fingerprints"]
    assert "jobs:board:51" in st["fingerprints"]

    # After bootstrap, only truly new posts alert.
    listings.append(L("brand", "Acme", "New Role", url="http://board/jobs/99"))
    dibs.main()
    assert [x["id"] for x in emails[-1]] == ["brand"]


_e2e()
print("logic: ok")


# --- optional live email: real Gmail send, only when secrets are set ---

def _live_email():
    if not (os.environ.get("GMAIL_USER") and os.environ.get("GMAIL_APP_PASSWORD")):
        print("email: skipped (set GMAIL_USER + GMAIL_APP_PASSWORD to send a test)")
        return
    demo = [{
        "company_name": "Dibs", "title": "Test email — your setup works",
        "locations": ["your inbox"], "terms": ["Summer 2027"],
        "url": "https://github.com/SimplifyJobs/Summer2027-Internships",
        "date_posted": int(time.time()),
        "source": "Simplify",
    }]
    _real_send_email(demo)  # raises loudly on a bad app password / login
    print(f"email: sent to {os.environ.get('RECIPIENT') or os.environ['GMAIL_USER']}")


_live_email()
