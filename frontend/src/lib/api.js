const BASE = import.meta.env.VITE_API_BASE ?? ''

async function req(path, opts) {
  const r = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!r.ok) throw new Error((await r.text()) || r.statusText)
  return r.json()
}

export const api = {
  startMatch: () => req('/api/match/start', { method: 'POST' }),
  matchState: (session_id) => req(`/api/match/${session_id}`),
  choose: (session_id, winner_id, loser_id, elapsed_ms) =>
    req('/api/match/choose', {
      method: 'POST',
      body: JSON.stringify({ session_id, winner_id, loser_id, elapsed_ms }),
    }),
  result: (session_id) => req(`/api/result/${session_id}`),
  cardUrl: (session_id) => `${BASE}/api/result/${session_id}/card.json`,
  health: () => req('/api/health'),
}
