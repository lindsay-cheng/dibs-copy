#!/usr/bin/env python3
"""Write every distinct company name in the data to companies.txt so you can copy
exact spellings into config.yaml. Run once: `python companies.py`.

Lists every company that appears in the source, whether or not it has a role open
right now, since you watch a company to hear about its *future* postings. A name
in the file is not a promise it's currently hiring; a name absent from it means
this source doesn't track that company at all (e.g. it carries no Google roles).
"""
from pathlib import Path

from dibs import fetch_listings

names = sorted(
    {l["company_name"].strip() for l in fetch_listings()}, key=str.lower
)
Path("companies.txt").write_text("\n".join(names) + "\n")
print(f"Wrote {len(names)} company names to companies.txt")
