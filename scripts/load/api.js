// P11 load test for the api (k6). Read-only, public demo endpoints only: no AI calls, no writes.
//   k6 run -e BASE=https://docify.work -e VUS=50 -e DURATION=10m scripts/load/api.js
// Expect (prod): api HPA 2 -> 3 within ~2 min of load, back to 2 about 5 min after it stops; 0 errors.
import http from "k6/http";
import { check, sleep } from "k6";

const BASE = __ENV.BASE || "https://staging.docify.work";
const VUS = Number(__ENV.VUS || 50);
const DURATION = __ENV.DURATION || "10m";
const WS = __ENV.WS || "demo";

export const options = {
  scenarios: {
    api: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "1m", target: VUS },
        { duration: DURATION, target: VUS },
        { duration: "30s", target: 0 },
      ],
      gracefulRampDown: "10s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<1500"],
    checks: ["rate>0.99"],
  },
  summaryTrendStats: ["avg", "med", "p(90)", "p(95)", "max"],
};

const QUERIES = ["setup", "install", "api", "config", "test", "auth", "deploy", "readme"];

export function setup() {
  const r = http.get(`${BASE}/api/workspaces/${WS}/docs`);
  check(r, { "docs list 200": (x) => x.status === 200 });
  const ids = r.status === 200 ? r.json().map((d) => d.id) : [];
  return { ids };
}

export default function (data) {
  const roll = Math.random();
  let r;
  if (roll < 0.35 && data.ids.length) {
    r = http.get(`${BASE}/api/docs/${data.ids[Math.floor(Math.random() * data.ids.length)]}`, { tags: { name: "doc" } });
  } else if (roll < 0.6) {
    r = http.get(`${BASE}/api/workspaces/${WS}/docs`, { tags: { name: "docs" } });
  } else if (roll < 0.8) {
    const q = QUERIES[Math.floor(Math.random() * QUERIES.length)];
    r = http.get(`${BASE}/api/workspaces/${WS}/search?scope=docs&q=${q}`, { tags: { name: "search_docs" } });
  } else if (roll < 0.9) {
    r = http.get(`${BASE}/api/workspaces/${WS}/repos`, { tags: { name: "repos" } });
  } else {
    r = http.get(`${BASE}/api/version`, { tags: { name: "version" } });
  }
  check(r, { "status 200": (x) => x.status === 200 });
  sleep(0.5 + Math.random());
}
