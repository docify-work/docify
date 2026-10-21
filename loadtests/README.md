# Load tests (P11)

| Script | What it shows | How |
|---|---|---|
| `api.js` | HPA: api pods 2 → 3 → 2 under read traffic; p95 < 500 ms, < 1% errors | `k6 run -e BASE=https://staging.<domain> loadtests/api.js` |
| `burst.sh` | KEDA: workers 0 → max → 0 for a burst of queue messages (fake AI, no cost) | `scripts/... loadtests/burst.sh <namespace> 500` on the server (SSM session) |

Watch while it runs:

```bash
kubectl -n docify-staging get hpa,scaledobject -w
kubectl -n docify-staging get pods -l app.kubernetes.io/component=worker -w
```

Record results (screenshots of Grafana + the k6 summary) in Master Doc §27.
