module.exports = async function handler(req, res) {
  const t = (process.env.SAT_TOKEN || "");
  const a = (process.env.SAT_API || "");
  return res.status(200).json({ ok: true, sat_api_set: Boolean(a.trim()),
                                sat_token_len: t.trim().length });
};
