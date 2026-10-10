// Connector proofs for vercel-web/api/sat.js — no network, no creds.
// Stubs firebase-admin + fetch, then asserts backend resolution order:
// ?api= hint → RTDB presence → SAT_API env → honest 503. Plus PIN gate.
const Module = require("module");
const path = require("path");

const handler = require(path.join(__dirname, "..", "vercel-web", "api", "sat.js"));

let presenceVal = null;
let fetched = [];
const fakeAdmin = {
  apps: [],
  initializeApp() { fakeAdmin.apps.push({}); },
  credential: { cert: () => ({}) },
  database: () => ({
    ref: () => ({ once: async () => ({ val: () => presenceVal }) }),
  }),
};
const origLoad = Module._load;
Module._load = function (req, parent, isMain) {
  if (req === "firebase-admin") return fakeAdmin;
  return origLoad.call(this, req, parent, isMain);
};
global.fetch = async (url, init) => {
  fetched.push(url);
  return { status: 200, headers: { get: () => "application/json" }, text: async () => '{"ok":true}' };
};

const req = (query = {}, headers = {}, method = "GET", body = null) => ({
  query, headers, method, body, url: "/api/sat/status?" + new URLSearchParams(query).toString(),
});
const res = () => {
  const r = { code: 0, body: null, headers: {} };
  r.status = (c) => ((r.code = c), r);
  r.setHeader = (k, v) => (r.headers[k] = v);
  r.send = (b) => ((r.body = b), r);
  r.json = (b) => ((r.body = JSON.stringify(b)), r);
  return r;
};

(async () => {
  let pass = 0;
  const ok = (name, cond, extra = "") => {
    console.log((cond ? "PASS " : "FAIL ") + name + (extra ? " — " + extra : ""));
    if (cond) pass++;
    else process.exitCode = 1;
  };
  const fresh = { online: true, tunnel_url: "https://presence.cfargotunnel.com", ts: Date.now() / 1000 };

  // 1. PIN gate
  process.env.SAT_PIN = "1234";
  let r = res();
  await handler(req({}, {}), r);
  ok("pin gate 401", r.code === 401, "code=" + r.code);
  delete process.env.SAT_PIN;

  // 2. ?api= hint wins (stable user hostname, not just trycloudflare)
  presenceVal = fresh;
  process.env.SAT_FIREBASE_SA = JSON.stringify({ project_id: "x" });
  process.env.SAT_DB_URL = "https://x.firebaseio.com";
  fetched = [];
  r = res();
  await handler(req({ api: "https://saturday-agentic-ai.cfargotunnel.com", path: "status" }, {}), r);
  ok("hint wins", r.code === 200 && fetched[0].startsWith("https://saturday-agentic-ai.cfargotunnel.com/"), fetched[0]);

  // 3. presence discovery when no hint
  fetched = [];
  r = res();
  await handler(req({ path: "status" }, {}), r);
  ok("presence discovery", r.code === 200 && fetched[0].startsWith("https://presence.cfargotunnel.com/"), fetched[0]);

  // 4. stale presence + static env fallback
  handler._testReset();
  presenceVal = { online: true, tunnel_url: "https://old.example.com", ts: Date.now() / 1000 - 9999 };
  process.env.SAT_API = "https://static.example.com";
  fetched = [];
  r = res();
  await handler(req({ path: "status" }, {}), r);
  ok("stale presence falls to env", r.code === 200 && fetched[0].startsWith("https://static.example.com/"), fetched[0]);

  // 5. nothing anywhere → honest 503 (laptop asleep), not a hang
  handler._testReset();
  delete process.env.SAT_API;
  presenceVal = null;
  fetched = [];
  r = res();
  await handler(req({ path: "status" }, {}), r);
  ok("503 asleep truth", r.code === 503 && /asleep|presence/i.test(r.body), String(r.body).slice(0, 80));

  console.log(`CONNECTOR ${pass}/5 GREEN`);
})();
