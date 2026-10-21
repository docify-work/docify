// k6 API load test (Master Doc §21, P11): drive the API to show the HPA scaling 2 → 3 → 2.
//
//   k6 run -e BASE=https://staging.docify.work loadtests/api.js
//   k6 run -e BASE=http://localhost:8080 -e VUS=20 -e DURATION=3m loadtests/api.js
//
// Read-only traffic against the public demo workspace (no login, no AI spend):
// workspace, repos, docs list, doc detail and full-text docs search.
import http from "k6/http";
import { check, sleep } from "k6";

const BASE = __ENV.BASE || "http://localhost:8080";
const WS = __ENV.WS || "demo";

export const options = {
  scenarios: {
    ramp: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "1m", target: Number(__ENV.VUS || 50) },
        { duration: __ENV.DURATION || "10m", target: Number(__ENV.VUS || 50) },
        { duration: "1m", target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"], // SLO: < 1% errors
    "http_req_duration{kind:read}": ["p(95)<500"], // SLO: p95 < 500 ms (§16.5)
  },
};

export function setup() {
  const docs = http.get(`${BASE}/api/workspaces/${WS}/docs`).json();
  return { docIds: (docs || []).map((d) => d.id) };
}

export default function (data) {
  const tags = { kind: "read" };
  const r1 = http.get(`${BASE}/api/workspaces/${WS}`, { tags });
  check(r1, { "workspace 200": (r) => r.status === 200 });
  http.get(`${BASE}/api/workspaces/${WS}/repos`, { tags });
  if (data.docIds.length) {
    const id = data.docIds[Math.floor(Math.random() * data.docIds.length)];
    const r2 = http.get(`${BASE}/api/docs/${id}`, { tags });
    check(r2, { "doc 200": (r) => r.status === 200 });
  }
  const r3 = http.get(`${BASE}/api/workspaces/${WS}/search?q=password&scope=docs`, { tags });
  check(r3, { "search 200": (r) => r.status === 200 });
  sleep(Math.random() * 1.5 + 0.5);
}
