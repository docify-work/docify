# Docify — everything we did in this session (1–2 Nov 2026), in simple English

Written for Ganesh (and Supriya) after the overnight run. Short sections, plain words.
Technical details live in `docs/Docify_Master_Doc.md` (decisions D56–D66, session log §27).

---

## 1. AWS account, money and safety

- **Logged the command line into the Docify AWS account** (two profiles: `docify` for the project account,
  `docify-mgmt` for the billing/management account).
- **Earned the AWS credits:** did the 5 "Explore AWS" activities → **$200 credits total**
  ($100 expire 12 Oct 2027, $100 expire 30 Oct 2027).
- **Moved everything to the Mumbai region (ap-south-1)**, as your PDF plan said: upgraded to the Paid plan
  (needed for Mumbai), turned on advanced features, and allowed Mumbai in the organisation's region policy.
- **Card protection (your rule: nothing should hit the card):**
  - a budget that e-mails you if the card is charged even 1 cent;
  - a budget that tracks how fast the $200 credits are used;
  - cost-anomaly alerts above $1;
  - an **automatic action that stops the server at 90 % of the credits**;
  - the server also **switches itself off every night at 23:00 IST** (it worked on 1 Nov at 23:00:56).
- **Root account MFA** set up; DNS for `docify.work` moved to AWS (Route 53); e-mail sending (SES) set up.
- **SES "production access" was requested but AWS denied it** — e-mails only reach verified addresses for now.
- Cost so far: **$0 on the card**. Real AI usage is about one cent. The one-hour EKS lab cost ≈ $0.25 of credits.

## 2. The app went live (Phases 8–10)

- **Phase 8:** Terraform built the whole AWS setup: network, one `t4g.large` server running k3s (small
  Kubernetes), CloudFront, S3, SQS queues, Lambda webhooks, ECR, alerts. **Start** button (GitHub Actions)
  wakes the server in ~2 minutes.
- **Phase 9:** GitOps with Argo CD: **staging** (`staging.docify.work`) and **prod** (`docify.work`).
  Every merge builds an image and deploys to staging automatically; prod needs an approval ("Promote").
  GitHub login, Google login and the GitHub Apps were set up (the prod App is public so friends can connect repos).
- **AI provider = Amazon Bedrock** (Nova models + Titan embeddings), paid from the AWS credits, not the card.
  Only Amazon's own models are allowed (Claude on Bedrock would be billed differently).
- **Phase 10 monitoring:** Grafana dashboards, 10 alert rules, alerts go to your e-mail.
  We proved it with a real error burst: the "API 5xx" alert fired and the e-mail was delivered.
- **Test project `tip-splitter`** (your small HTML app on Vercel) is connected; PRs on it update Docify's docs
  and changelog automatically.

## 3. Chat can now answer "who made this and when?"

- Before: "who created this new feature" → *"I couldn't find this in the indexed code."*
- Now Docify also stores the **git history** (who committed what, when, which PR, which files) and uses it
  in chat. Example on prod: *"The Reset button was created by Ganesh-Mk on 2026-11-01"* with clickable commit links.
- Follow-up questions like "who created **this** feature" use the previous question to know what "this" means.

## 4. Scaling, chaos and recovery (Phases 11–13)

- **Load test (k6) on prod:** 50 users for 10 minutes → 30,668 requests, **0 errors**, 95 % under 107 ms.
  The API grew from 2 to 3 copies and shrank back.
- **Burst test:** 500 background jobs → workers went 0 → 3 → 0 by themselves (KEDA). No AI cost (fake jobs).
- **EKS lab (one evening):** the same app ran on Amazon EKS + RDS database, added servers when needed (3 → 5),
  then everything was **deleted the same night**. We hit a real-world problem (cheap "spot" servers were taken
  back by AWS) and fixed it by allowing 7 server types.
- **Break-it tests (with write-ups in `docs/incidents/`):** killed an API pod (0 failed requests), killed a worker
  mid-job (job still finished exactly once), stopped the database for 60 s (recovered by itself), shipped a broken
  release (nothing broke; rolled back with `git revert`), forced errors (alert e-mail arrived).
- **Restore drill:** the nightly backup was restored and checked in **20 seconds** (target: 30 minutes).
- **Security review** (`docs/Security_Review.md`) and a **Postgres monitoring dashboard** were added.
- **Phase 14 docs:** README, cost report, demo script, resume bullets.

## 5. Overnight work (2 Nov) — what you asked before sleeping

### 5.1 Untested items, now tested
- **Trivy security gate:** opened a test PR that added an old library with 6 known critical vulnerabilities →
  CI **blocked** it as designed. PR closed, branch deleted.
- **"Manual change is undone by Argo"** — proven during the database test (Argo put the database back in 4 s).
- **23:00 auto-stop** and **Start button** — proven.

### 5.2 New features (live on prod)

**Insights page** (per repository):
- Health score (A–D, with the reasons in a tooltip).
- Commits, contributors, merged PRs, lines of code.
- Commit activity for the last 26 weeks, and a "when people commit" heatmap (day × hour).
- **"Who did what":** each person's share of commits, lines added/removed, files and the folders they work in.
  Click a person to see their recent commits.
- Languages, pull requests (open/merged, average time to merge), "hot files" (changed most often), stars/forks/license.

**Checks page** (flagging on every push / merged PR):
- **Policies** (rules). Built-in ones: *No secrets or API keys* (critical, secrets are hidden/redacted),
  *No AI model names in the product* (your example), *No debug leftovers* (console.log), and optional
  *No TODO/FIXME* and *No hard-coded IP addresses*. Admins can add their own rules (words or regex) and
  **test them live** before saving.
- **Every new commit is checked automatically.** Each finding says **who added the line, in which commit and PR**.
- Actions: acknowledge, resolve, mark false positive, reopen, **assign to a person**, **create an issue**.
- "Scan now" checks the whole current code; the author then comes from GitHub "blame".
- **Tested for real on prod:** a PR on tip-splitter that added "GPT-4o" in the footer and a `console.log` was
  flagged within seconds — both findings pointed at **@Ganesh-Mk** and the exact lines.

**Issues page:**
- Create a bug report, **import a GitHub issue**, or turn a finding into an issue.
- Docify suggests **who most likely caused it** ("Likely responsible"), with a confidence bar and **evidence
  links** (the commit that added the flagged line, who wrote the lines in the files mentioned, who wrote the code
  that matches the bug text, commits whose message matches).
- One click **assigns** the issue to that person; status (open → in progress → resolved/closed) and severity.

**Also:**
- **Overview page** shows open findings, active issues and a "Code health" box.
- The repository menu has an "Insights" shortcut.

### 5.3 UI/UX overhaul
- **New sidebar:** grouped into *Knowledge* (Repositories, Search, Chat), *Code health* (Insights, Checks, Issues)
  and *Workspace* (Jobs, Review, Members, Settings). It has count badges, a smooth sliding highlight with an accent
  bar, a tooltip on every item, and the collapse button at the top.
- **Top bar is cleaner:** the "Ctrl K" hint is gone (the shortcut still works), the theme button moved into the
  account menu (or the sidebar bottom when signed out), and the footer is gone.
- **Animations:** pages fade/slide in, cards and lists appear one after another, numbers count up, bars and
  charts grow in, menus and drawers animate.
- **Less text, more ⓘ tooltips:** explanations sit behind info icons.
- **Responsive:** checked on a 390 px phone width and a 1440 px desktop, in light and dark mode.

### 5.4 Bugs found and fixed during testing
- Scan-now crashed when some findings had an author and others didn't (database insert shape) → fixed + test.
- The GitHub "stats" refresh retried on every page view when GitHub was unreachable → now waits an hour.
- Numbers stayed at 0 in background tabs → fixed.
- GitHub hides issues from our App (it has no "Issues" permission) → public repos are now read anonymously.
- Findings from a merged PR didn't show the PR number → fixed.
- Chart labels were cut off; mobile filter tabs overflowed → fixed.

## 6. Numbers at the end
- Backend tests: **201 passing**. Frontend tests: **48 passing**. CI green.
- Prod + staging healthy (10/10 Argo apps). Card charges: **$0**.

---

# What's left (needs you)

1. **SES production access was denied.** Reply/appeal from the AWS console (Support → the SES case) or re-apply
   later. Until then, sign-up e-mails only reach verified addresses.
2. **AWS CLI login expired** during the night. Run `aws login --profile docify` (and `docify-mgmt`) when you're
   back so I can use AWS again.
3. **Check billing on 2–3 Nov:** Billing → Credits and Cost Explorer should show EC2/Bedrock/EKS/RDS covered by
   credits and **$0.00 net** (Cost Explorer is ~24 h behind).
4. **Record the demo video** using `docs/Demo_Script.md` (I can't record video).
5. **Optional — give the GitHub App the "Issues: read" permission** (GitHub App settings → Permissions). Then the
   installer approves it. This makes GitHub issue import work for **private** repos (public repos already work).
   Later "Issues: write" + "Checks: write" would let Docify post findings back to PRs.
6. **Optional hardening:** separate AWS permissions per pod on k3s (IRSA-style) and image signing (cosign) —
   written up as accepted risks in `docs/Security_Review.md`.
7. The server auto-stops at **23:00 IST**; use **Actions → Start Docify** to wake it for a demo.

Test data left on prod: tip-splitter PR #3 (footer credit + console.log) and GitHub issue #4 were created on
purpose to test the new features; Docify issues #1–#2 in the tip-splitter workspace are from that test. You can
close or delete them.
