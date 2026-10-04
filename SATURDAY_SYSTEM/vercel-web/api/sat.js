// SATURDAY front door — Vercel serverless proxy to the home tunnel.
//
// Why: the tunnel URL/token live on the PC; the browser can't know them.
// This function holds both as Vercel env vars (server-side, never shipped
// to the browser) and relays same-origin /api/* calls. Open the site =
// instantly live, no pasting, token never exposed.
//
// Env (Vercel → Settings → Environment Variables):
//   SAT_API    https://<stable-tunnel-host>   (required)
//   SAT_TOKEN  <dashboard token>               (required)
//   SAT_PIN    <any string you invent>         (optional but STRONGLY advised:
//              anyone with the site URL can otherwise press buttons)
//
// Hobby limits are honest: functions time out (~60s), so instant commands
// (status, sense, bot moves, heal) fly; multi-minute brain/research runs
// belong to direct mode or the local CLI.

function cleanQuery(search) {
  const q = new URLSearchParams(search || "");
  q.delete("pin");
  q.delete("path");
  const s = q.toString();
  return s ? "?" + s : "";
}

module.exports = async function handler(req, res) {
  try {
    const pin = req.headers["x-sat-pin"] || (req.query && req.query.pin) || "";
    if (process.env.SAT_PIN && pin !== process.env.SAT_PIN) {
      return res.status(401).json({ error: "pin required" });
    }
    let base = (process.env.SAT_API || "").trim().replace(/\/$/, "");
    // Explicit backend wins (HUD passes its stored tunnel URL through).
    // This makes the proxy immune to stale env values after URL rotation.
    try {
      const hint = req.query && req.query.api ? String(req.query.api) : "";
      if (/^https:\/\/[a-z0-9.-]+\.trycloudflare\.com$/i.test(hint.trim())) {
        base = hint.trim();
      }
    } catch (e) { /* env fallback */ }
    const token = (process.env.SAT_TOKEN || "").trim();
    if (!base) {
      return res.status(503).json({ error: "backend not linked (SAT_API missing)" });
    }
    // path comes from the vercel.json rewrite (/api/sat/:path* -> ?path=)
    // or legacy [...sat] query form.
    let sub = "";
    if (req.query && typeof req.query.path === "string" && req.query.path) {
      sub = req.query.path.replace(/^\/+/, "");
    } else if (Array.isArray(req.query && req.query.sat)) {
      sub = req.query.sat.join("/");
    }
    const target = base + "/" + sub + cleanQuery(req.url.split("?")[1] || "");
    const init = {
      method: req.method,
      headers: { "Content-Type": "application/json" },
    };
    if (token) init.headers["X-Saturday-Token"] = token;
    if (req.method !== "GET" && req.method !== "HEAD" && req.body) {
      init.body = typeof req.body === "string" ? req.body : JSON.stringify(req.body);
    }
    const upstream = await fetch(target, init);
    const text = await upstream.text();
    res.status(upstream.status);
    res.setHeader("Content-Type", upstream.headers.get("content-type") || "application/json");
    return res.send(text);
  } catch (e) {
    return res.status(502).json({ error: "tunnel unreachable: " + String((e && e.message) || e).slice(0, 160) });
  }
};
