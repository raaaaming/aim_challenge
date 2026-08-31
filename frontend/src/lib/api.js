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
  startChat: () => req('/api/chat/start', { method: 'POST' }),
  sendChat: (session_id, message) =>
    req('/api/chat', { method: 'POST', body: JSON.stringify({ session_id, message }) }),
  result: (session_id) => req(`/api/result/${session_id}`),
  health: () => req('/api/health'),
}
