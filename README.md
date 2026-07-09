<table align="center">
  <tr>
    <td>
<pre>
 ██████╗ ██╗ ██████╗ ███████╗
 ██╔══██╗██║ ██╔══██╗██╔════╝
 ██║  ██║██║ ██████╔╝███████╗
 ██║  ██║██║ ██╔══██╗╚════██║
 ██████╔╝██║ ██████╔╝███████║
 ╚═════╝ ╚═╝ ╚═════╝ ╚══════╝
</pre>
    </td>
  </tr>
</table>

<p align="center"><strong>Get an email the moment a company you care about posts a new internship, before the pile-up, instead of refreshing a job board.</strong></p>

---

Dibs watches the [SimplifyJobs Summer2026](https://github.com/SimplifyJobs/Summer2026-Internships)
listings every 5 minutes, keeps only the ones matching your watchlist, and
emails you the new ones. It runs entirely on GitHub Actions for free. Your
computer is only needed if you want to test things locally.

**vs. SWEList:** SWEList emails every new posting, batched once a day. Dibs adds
per-company filtering, so you get notified about new postings you care about the most, and it checks every 5 minutes instead of daily. Think of it as the filtered,
near-real-time version of the same idea.

## How it works

On each run Dibs downloads the listings, keeps the ones that are active and
visible, matches them against your `config.yaml`, emails you anything new, and
records the IDs it sent in `state.json` so it never emails the same role twice.
Matching is keyed on each listing's stable ID, so edits to a posting never
re-notify you. The first run records everything currently open without emailing,
so you don't get one giant backlog message. Every run after that emails only
genuinely new roles.

## Setup

The whole thing takes about five minutes in the browser. No local install
required.

1. **Make your own copy.** Top-right, next to Star repo button, click
   **"Use this template" → Create a new repository**. Use this template, not
   Fork. Your copy holds your watchlist, your email secrets, and your state,
   all separate from the original. Make it private if you want.
2. **Turn on Actions.** Open the **Actions** tab in your copy and click the
   button to enable workflows.
3. **Pick your companies.** Open `config.yaml` (the pencil icon edits it right
   in the browser) and list the companies you care about:

   ```yaml
   companies:
     - Citadel                   # every Citadel role
     - name: Jane Street
       roles: [software]         # only titles containing these words
   ```

   Names are matched loosely, so `Jane Street` finds `Jane Street Capital`.
   Run `python companies.py` locally to write every company name in the
   data to `companies.txt`, then copy the exact spelling from there. Two things worth knowing: this
   source only tracks the companies in that list, and a company can be listed but have nothing open
   right now. Watching it still works: Dibs emails you when it next posts.
4. **Add your email secrets.** Go to
   **Settings → Secrets and variables → Actions** and add three repository
   secrets:

   | Secret | Value |
   | --- | --- |
   | `GMAIL_USER` | the Gmail address you send from |
   | `GMAIL_APP_PASSWORD` | a 16-character [app password](https://support.google.com/accounts/answer/185833) (your account needs 2-step verification on) |
   | `RECIPIENT` | where alerts go. Optional; defaults to `GMAIL_USER` |

5. **Kick off the first run.** Back in the **Actions** tab, open the
   **dibs poll** workflow and click **Run workflow**. This records what's
   currently open without emailing you. From here on the schedule takes over
   and you get an email whenever a matching role appears.

That's it. Everything runs on GitHub's servers on a timer. You can close the tab.

**Optional: check your email secrets before trusting the schedule.** Locally,
`pip install -r requirements.txt`, then set the same three values and run the
tests:

```bash
export GMAIL_USER="you@gmail.com"
export GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
export RECIPIENT="you@gmail.com"
python test_dibs.py
```

That runs the logic checks and, because the secrets are set, sends you one real
test email. A bad app password fails here loudly instead of silently on a run
at 3am. Without those env vars the test still runs and just skips the email.

## Adjusting the watchlist later

Edit `config.yaml` and commit. Changes apply on the next scheduled run. A company
with no `roles:` list matches all of its postings; add `roles:` to narrow it to
titles containing those words. Matching ignores case and punctuation and drops
Inc/LLC/Corp, so exact capitalization doesn't matter. One caveat: it's a
substring match, so very short names can catch extras (`meta` also matches
"Metabase"). Paste the exact name from `companies.txt` if you see noise.

To hear about every company instead of a curated list, set `companies: all` (a
bare string, no list). It matches every posting with no role filter and
auto-includes companies Simplify adds later, so you never need to re-run
`companies.py` and edit the list. Expect SWEList-style volume.

## Changing how often it checks

The schedule lives in `.github/workflows/poll.yml`, in the `cron:` line, not in
`config.yaml`. GitHub reads the timer from the workflow file. The shortest
interval GitHub allows is 5 minutes, and scheduled runs can drift or be skipped
when GitHub is busy.

## Good to know

- `state.json` is committed back to your repo whenever it changes. Stateless
runners have no other memory between runs.
- If a download fails, Dibs stays quiet and tries again next run. There's no
failure email.
- If nothing matches for about 60 days, GitHub pauses the schedule on quiet
repos. It emails you first, and one click re-enables it.