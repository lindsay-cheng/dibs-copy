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

<p align="center"><strong>Get an email when a new internship is posted. Apply early. Stop refreshing the board.</strong></p>

---

Dibs emails you when a new tech internship is posted. It checks
[Simplify](https://github.com/SimplifyJobs/Summer2027-Internships) and
[vansh/ouckah](https://github.com/vanshb03/Summer2027-Internships) every 5
minutes. Fresh postings are at the top of the email. Older finds are below.
If the same role is on both lists, you get one alert. Dibs runs free on GitHub
Actions. You do not need a server or a local install. Use your computer only
if you want to test locally.

**vs. SWEList:** SWEList sends a once-a-day digest. Dibs checks every 5
minutes, so you hear about a posting soon after it goes up.

## Setup (about 5 minutes, all in the browser)

1. **Make your own copy of this repo.** Top right, next to Star, click
   **"Use this template" → Create a new repository**. Use the template, not
   Fork. Your copy keeps settings, the email password, and memory separate
   from the original. You can make the copy private.
2. **Turn on GitHub Actions.** Open the **Actions** tab in your copy and
   enable workflows.
3. **Choose what you hear about.** Open `config.yaml` (pencil icon to edit
   in the browser) and pick one:

   Email every new posting (usual choice):

   ```yaml
   companies: all
   ```

   Or only some companies:

   ```yaml
   companies:
     - Citadel                       # every Citadel role
     - name: Jane Street
       roles: [software]             # optional: only titles with these words
   ```

   Names match loosely (`Jane Street` also matches `Jane Street Capital`).
   Run `python companies.py` locally to write every company name to
   `companies.txt` for exact spellings.
4. **Add your email secrets.** Go to **Settings → Secrets and variables →
   Actions → New repository secret** and add:

   | Secret | Value |
   | --- | --- |
   | `GMAIL_USER` | Gmail address that sends alerts |
   | `GMAIL_APP_PASSWORD` | 16-character [app password](https://support.google.com/accounts/answer/185833) (turn on 2-step verification first) |
   | `RECIPIENT` | where alerts go. Optional. Defaults to `GMAIL_USER` |
5. **Run it once.** Open **Actions → dibs poll → Run workflow**. The first
   run only records what is open now. It does not email a backlog. After
   that, Dibs emails new postings and remembers what it already sent.

That is all. The job runs on GitHub on a timer. You can close the tab.

**Optional: test email before you trust the schedule.** On your machine,
run `pip install -r requirements.txt`, set the same three values, and run
the tests. The script checks the logic and sends one real test email. A bad
app password fails here, not later on the schedule:

```bash
export GMAIL_USER="you@gmail.com"
export GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
export RECIPIENT="you@gmail.com"
python test_dibs.py
```

## Full 5-minute cadence (optional)

The interval is in `.github/workflows/poll.yml` (`cron:` line). It is already
at GitHub's 5-minute minimum. GitHub `schedule:` is best-effort. Under load
it drifts or drops runs, so gaps can be longer than 5 minutes. For a steady
every-5-minutes check, point [cron-job.org](https://cron-job.org) at your
workflow. About five minutes, all in the browser:

1. **Create a token that can trigger the workflow.** On GitHub: profile
   photo → **Settings → Developer settings → Personal access tokens →
   Fine-grained tokens → Generate new token**. Give it a name and an
   expiration you will remember. Under **Repository access**, choose
   **Only select repositories** → your copy. Under **Permissions →
   Repository permissions**, set **Actions** to **Read and write**. Click
   Generate and copy the token. GitHub shows it only once.
2. **Create the cron job.** Sign up at
   [console.cron-job.org](https://console.cron-job.org/signup) (free, no
   card). Click **Create cronjob** and fill in:

   | Field | Value |
   | --- | --- |
   | Title | e.g. `dibs poll` |
   | URL | `https://api.github.com/repos/OWNER/REPO/actions/workflows/poll.yml/dispatches` |
   | Schedule | every 5 minutes (preset, or cron `*/5 * * * *`) |

   Replace `OWNER` and `REPO` with your GitHub username and repo name, as in
   the repo URL. Open **Advanced** and set:

   | Field | Value |
   | --- | --- |
   | Request method | `POST` |
   | Headers | `Accept: application/vnd.github+json` and `Authorization: Bearer YOUR_TOKEN` |
   | Request body | `{"ref":"main"}` (change if your default branch is not `main`) |

   Paste the token from step 1 into the `Authorization` header. Turn on
   failure email in Advanced. If the token expires, that email tells you to
   renew it.
3. **Test it.** In the cron-job.org job list, click the test-run (play)
   icon. It should report success. Within seconds a **dibs poll** run
   appears under **Actions**, triggered by `workflow_dispatch`. If it
   fails: `401` means bad or expired token, `404` means wrong `OWNER`/`REPO`
   or token scope, `422` means the `ref` branch does not exist.
