# Docify — resume bullets (P14)

Pick 3–5. Numbers are from the real runs on 2026-11-01/02 (see `docs/incidents/`, Master Doc §27).

- Built and ran **Docify**, an AI documentation + code-chat SaaS for GitHub repos (FastAPI, React, Postgres/pgvector,
  Amazon Bedrock), end to end on AWS for **≈ $26/month** — one Graviton k3s node behind CloudFront, no NAT,
  auto-stop schedule, paid fully from cloud credits with $0 card charges guarded by budgets and an auto-stop action.
- Implemented **GitOps delivery** with Argo CD app-of-apps + Helm: arm64 images built in GitHub Actions with
  **OIDC (no static keys)**, Trivy gate, automatic staging deploys and approval-gated promotion of the tested SHA to prod.
- Designed an **event-driven pipeline** (GitHub webhooks → Lambda → SQS → workers) with row leases, fencing tokens
  and a reconciler; verified a worker killed mid-job is retried and finishes **exactly once**.
- Load-tested with **k6** (50 VUs × 10 min: 30,668 requests, **0 errors, p95 107 ms**); tuned **HPA** (api 2→3→2) and
  **KEDA** SQS scaling (workers **0→3→0** on a 500-message burst).
- Ran **chaos engineering** (pod kill, worker kill, 60 s Postgres outage, bad release, forced 5xx) with incident notes;
  proved alerting end to end (Grafana → SNS e-mail) and a **20-second database restore** (RTO target 30 min).
- Ported the same Helm chart to **EKS + RDS** in a one-evening Terraform lab (Pod Identity, AWS Load Balancer
  Controller, Cluster Autoscaler scale-out 3→5 nodes, spot capacity incident fixed with instance diversification),
  then destroyed it the same night (~$0.25).
- Added RAG chat that answers **"who changed this and when?"** by indexing git history (commits, authors, PRs,
  changed files) next to code embeddings, with clickable citations to lines and commits.
