# 2026-11-01/02 — Chaos 5: real 5xx burst → alert e-mail (P10 leftover)

**Env:** staging · **Scripts:** `scripts/chaos/force-5xx.sh break|restore` + `scripts/load/api.js` · **Result:** ✅ alert fired and was e-mailed

**Why a special trick:** stopping Postgres makes readiness fail, so Traefik stops routing and the app's
`docify_http_requests_total` never sees the errors. Instead: `REVOKE SELECT ON documents FROM docify_staging`.
`/api/ready` (SELECT 1) stays OK and pods stay Ready, but every docs request returns 500.

| Time (IST) | Event |
| --- | --- |
| 23:54:37 | REVOKE; k6 with 8 VUs against staging for 14 min |
| ~00:07 | Rule "API 5xx above 5%" goes pending → firing after `for: 10m` (error rate ~79 %) |
| 00:10:15 | GRANT restored; the rule resolves after the 5-min rate window |
| ~00:12 | Grafana → SNS → e-mail: SNS `NumberOfMessagesPublished 1`, `NumberOfNotificationsDelivered 1`, `Failed 0` |

k6: 6,623 requests, 79.45 % failed (as intended).

**Follow-up:** none. The P10 check "forced 5xx burst → alert email" is now fully proven, not only by the receiver test.
