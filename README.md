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

<p align="center"><strong>Get an email the moment a new internship is posted, before the pile-up, instead of refreshing a job board.</strong></p>

---

Dibs sends you an email every time a new tech internship gets posted. It
watches the [SimplifyJobs internship listings](https://github.com/SimplifyJobs/Summer2026-Internships)
every 5 minutes and emails you whatever's new — fresh postings up top, older
ones it found late below. It runs for free on GitHub Actions, so there's no
server and nothing to install. Your computer is only needed if you want to
test things locally.

**vs. SWEList:** SWEList emails a once-a-day digest of new postings. Dibs
checks every 5 minutes, so you hear about a posting minutes after it goes up
instead of the next morning.

## Setup — about 5 minutes, all in the browser

1. **Make your own copy of this repo.** Top-right, next to the Star button,
   click **"Use this template" → Create a new repository**. Use the template,
   not Fork. Your copy keeps your settings, email password, and memory separate
   from the original. Make it private if you want.
2. **Turn on GitHub Actions.** In your copy, open the **Actions** tab and click
   the button to enable workflows.
3. **Choose what you hear about.** Open `config.yaml` (the pencil icon edits it
   in the browser) and pick one:

   Email you about every new posting — the usual choice:

   ```yaml
   companies: all
   ```

   Or only specific companies:

   ```yaml
   companies:
     - Citadel                       # every Citadel role
     - name: Jane Street
       roles: [software]             # optional: only titles containing these words
   ```

   Names are matched loosely (`Jane Street` also matches `Jane Street Capital`).
   Run `python companies.py` locally to write every company name to
   `companies.txt` for exact spellings.
4. **Add your email secrets.** Go to **Settings → Secrets and variables →
   Actions → New repository secret** and add three secrets:

   | Secret | Value |
   | --- | --- |
   | `GMAIL_USER` | the Gmail address to send alerts from |
   | `GMAIL_APP_PASSWORD` | a 16-character [app password](https://support.google.com/accounts/answer/185833) (your account needs 2-step verification on) |
   | `RECIPIENT` | where alerts go. Optional; defaults to `GMAIL_USER` |
5. **Run it once.** Back in **Actions**, open the **dibs poll** workflow and
   click **Run workflow**. This first run only records what's currently open —
   it doesn't email you, so you don't get one giant backlog. After that, Dibs
   emails you whenever a new posting appears, and remembers what it sent so you
   never get the same role twice.

That's it. Everything runs on GitHub's servers on a timer; you can close the
tab.

**Optional: confirm your email works before trusting the schedule.** Locally,
`pip install -r requirements.txt`, set the same three values, and run the
tests. It runs the logic checks and sends you one real test email, so a bad
app password fails loudly here instead of silently at 3am:

```bash
export GMAIL_USER="you@gmail.com"
export GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
export RECIPIENT="you@gmail.com"
python test_dibs.py
```

## Getting the full 5-minute cadence (optional)

The check interval lives in `.github/workflows/poll.yml` (the `cron:` line),
and it's already at GitHub's minimum of 5 minutes. The catch: GitHub's built-in
`schedule:` is best-effort — under load it drifts and drops runs, so you may
see gaps longer than 5 minutes. To get a reliable every-5-minutes check, point
the free site [cron-job.org](https://cron-job.org) at your workflow on a timer.
Takes about five minutes, all in the browser:

1. **Create a token that can trigger the workflow.** On GitHub, click your
   profile photo → **Settings → Developer settings → Personal access tokens →
   Fine-grained tokens → Generate new token**. Name it anything and pick an
   expiration date you'll remember. Under **Repository access** choose **Only
   select repositories** → your copy. Under **Permissions → Repository
   permissions** set **Actions** to **Read and write** (nothing else is needed).
   Click Generate, then copy the token — it's shown only once.
2. **Create the cron job.** Sign up at
   [console.cron-job.org](https://console.cron-job.org/signup) (free, no card),
   click **Create cronjob**, and fill in the top of the form:

   | Field | Value |
   | --- | --- |
   | Title | anything, e.g. `dibs poll` |
   | URL | `https://api.github.com/repos/OWNER/REPO/actions/workflows/poll.yml/dispatches` |
   | Schedule | every 5 minutes (preset, or cron `*/5 * * * *`) |

   Replace `OWNER` and `REPO` with your GitHub username and repo name, exactly
   as they appear in the repo's URL. Then open the **Advanced** tab and fill
   in:

   | Field | Value |
   | --- | --- |
   | Request method | `POST` |
   | Headers | add `Accept: application/vnd.github+json` and `Authorization: Bearer YOUR_TOKEN` |
   | Request body | `{"ref":"main"}` (change it if your default branch isn't `main`) |

   Paste the token from step 1 into the `Authorization` header. While you're in
   Advanced, turn on the failure email notification — if the token ever expires
   the job starts failing, and that email is your heads-up to renew it.
3. **Test it.** In the cron-job.org job list, click the test-run (play) icon.
   It should report success, and within seconds a new **dibs poll** run appears
   in your repo's **Actions** tab, marked as triggered by `workflow_dispatch`.
   If it fails, the status code tells you why: `401` = token wrong or expired,
   `404` = wrong `OWNER`/`REPO` or the token isn't scoped to the repo, `422` =
   the `ref` branch doesn't exist.
