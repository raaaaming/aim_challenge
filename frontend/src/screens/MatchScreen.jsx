import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'

/** 여행지 카드 — 탭하면 이 곳을 '더 끌리는 곳'으로 선택. */
function PlaceCard({ card, onPick, disabled }) {
  const [failed, setFailed] = useState(false)
  const ok = card.image_url && !failed
  return (
    <button
      onClick={onPick}
      disabled={disabled}
      className="group relative min-h-0 flex-1 overflow-hidden rounded-3xl text-left ring-1 ring-white/10
                 transition active:scale-[.98] disabled:pointer-events-none"
    >
      {ok ? (
        <img src={card.image_url} alt={card.place_name} onError={() => setFailed(true)}
             className="absolute inset-0 h-full w-full object-cover transition duration-300 group-hover:scale-105" />
      ) : (
        <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-sea-700 via-sea-800 to-sea-950">
          <span className="text-5xl opacity-30">🌊</span>
        </div>
      )}
      <div className="absolute inset-0 bg-gradient-to-t from-sea-950 via-sea-950/55 to-transparent" />
      <div className="relative flex h-full flex-col justify-end p-4">
        <h2 className="text-[21px] font-black leading-tight tracking-[-0.02em] text-white">{card.place_name}</h2>
        <p className="mt-1 line-clamp-1 text-[12px] leading-snug text-sea-200">{card.summary}</p>
        {card.activities?.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {card.activities.map((a) => (
              <span key={a} className="rounded-full bg-sea-400/25 px-2 py-0.5 text-[10.5px] font-semibold text-sea-50 ring-1 ring-sea-300/25">
                {a}
              </span>
            ))}
          </div>
        )}
        {card.good_for && (
          <p className="mt-2 flex items-center gap-1 text-[11px] text-sea-300">
            <span className="opacity-70">🧭</span>
            <span className="truncate">{card.good_for}에게</span>
          </p>
        )}
      </div>
    </button>
  )
}

export default function MatchScreen({ onFinish, onSession, resumeId }) {
  const [pair, setPair] = useState(null)
  const [round, setRound] = useState(1)
  const [total, setTotal] = useState(12)
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState(null)
  const sid = useRef(null)
  const t0 = useRef(0)          // 현재 대결이 화면에 뜬 시각
  const boot = useRef(false)

  useEffect(() => {
    if (boot.current) return
    boot.current = true
    ;(async () => {
      try {
        let r = null
        if (resumeId) {
          try {
            const st = await api.matchState(resumeId)      // 진행 중이던 대결 이어붙이기
            if (st.finished) { onFinish(resumeId); return }
            r = st
          } catch { /* 세션 만료(백엔드 재시작 등) → 새 게임 */ }
        }
        if (!r) r = await api.startMatch()
        sid.current = r.session_id
        onSession?.(r.session_id)
        setTotal(r.total)
        setRound(r.round)
        setPair(r.pair)
        t0.current = performance.now()
      } catch {
        setError('서버에 연결하지 못했어요. 백엔드(uvicorn)가 켜져 있는지 확인해 주세요.')
      } finally {
        setBusy(false)
      }
    })()
  }, [])

  const pick = async (winner, loser) => {
    if (busy || !sid.current) return
    const elapsed = performance.now() - t0.current   // 빠를수록 강한 선호 신호
    setBusy(true)
    try {
      const r = await api.choose(sid.current, winner.place_id, loser.place_id, elapsed)
      if (r.finished) { onFinish(sid.current); return }
      setRound(r.round)
      setPair(r.pair)
      t0.current = performance.now()
    } catch {
      setError('선택을 전송하지 못했어요. 잠시 후 다시 시도해 주세요.')
    } finally {
      setBusy(false)
    }
  }

  const pct = Math.round((round / (total || 12)) * 100)

  return (
    <div className="flex h-full flex-col bg-gradient-to-b from-sea-950 to-sea-900">
      {/* 헤더 + 진행률 */}
      <header className="shrink-0 px-4 pb-3 pt-[max(0.75rem,env(safe-area-inset-top))]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-lg">⚓</span>
            <h1 className="text-[15px] font-extrabold tracking-tight text-white">포항항</h1>
          </div>
          <span className="rounded-full bg-white/10 px-2.5 py-1 text-[10px] font-semibold text-sea-200 ring-1 ring-white/10">
            {round} / {total}
          </span>
        </div>
        <p className="mt-2 text-[12px] text-sea-300">더 끌리는 곳을 골라주세요</p>
        <div className="mt-2 h-[3px] w-full overflow-hidden rounded-full bg-white/10">
          <div className="h-full rounded-full bg-gradient-to-r from-sea-400 to-sea-200 transition-[width] duration-500"
               style={{ width: `${pct}%` }} />
        </div>
      </header>

      {/* 두 곳 대결 */}
      <div className="relative flex min-h-0 flex-1 flex-col gap-3 px-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
        {error && (
          <div className="rounded-xl bg-red-500/15 px-3.5 py-2.5 text-[13px] text-red-200 ring-1 ring-red-400/25">
            {error}
          </div>
        )}
        {!pair && !error && (
          <div className="flex flex-1 items-center justify-center">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-sea-500 border-t-transparent" />
          </div>
        )}
        {pair && (
          <div key={round} className="animate-floatUp flex min-h-0 flex-1 flex-col gap-3">
            <PlaceCard card={pair[0]} disabled={busy} onPick={() => pick(pair[0], pair[1])} />
            <div className="pointer-events-none absolute inset-x-0 top-1/2 z-10 flex -translate-y-1/2 justify-center">
              <span className="flex h-11 w-11 items-center justify-center rounded-full bg-sea-950 text-[13px] font-black text-white ring-2 ring-white/20">
                VS
              </span>
            </div>
            <PlaceCard card={pair[1]} disabled={busy} onPick={() => pick(pair[1], pair[0])} />
          </div>
        )}
      </div>
    </div>
  )
}
