import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'

/** 추천 임베드 — 터치/클릭하면 최종 결과 화면으로 넘어간다. */
function RecommendEmbed({ embed, onOpen }) {
  return (
    <button
      onClick={onOpen}
      className="animate-popIn group mt-2 block w-full overflow-hidden rounded-2xl bg-gradient-to-br from-sea-600 to-sea-800
                 text-left shadow-lg shadow-sea-950/40 ring-1 ring-white/15 transition
                 hover:-translate-y-0.5 hover:shadow-xl active:translate-y-0 active:scale-[.99]"
    >
      <div className="flex items-center gap-3 px-4 pt-4">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/15 text-lg">📍</span>
        <div className="min-w-0">
          <p className="truncate text-[13px] font-bold text-white">{embed.title}</p>
          <p className="truncate text-[11px] text-sea-200">{embed.subtitle}</p>
        </div>
      </div>

      {embed.hints?.length > 0 && (
        <div className="flex flex-wrap gap-1.5 px-4 pt-3">
          {embed.hints.map((h) => (
            <span key={h} className="rounded-full bg-white/12 px-2 py-0.5 text-[10px] font-medium text-sea-100 ring-1 ring-white/10">
              {h}
            </span>
          ))}
        </div>
      )}

      <div className="mt-3.5 flex items-center justify-between border-t border-white/10 px-4 py-3">
        <span className="text-[12px] font-semibold text-white">{embed.cta}</span>
        <span className="text-white transition-transform group-hover:translate-x-1">→</span>
      </div>
    </button>
  )
}

function Bubble({ m, onOpen }) {
  const mine = m.role === 'user'
  return (
    <div className={`animate-floatUp flex ${mine ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[82%] ${mine ? '' : 'flex gap-2'}`}>
        {!mine && (
          <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-sea-500/25 text-[13px] ring-1 ring-white/10">
            ⚓
          </span>
        )}
        <div className="min-w-0">
          <div
            className={
              mine
                ? 'rounded-2xl rounded-br-md bg-sea-500 px-3.5 py-2.5 text-[14px] leading-relaxed text-white shadow'
                : 'glass rounded-2xl rounded-tl-md px-3.5 py-2.5 text-[14px] leading-relaxed text-sea-50 ring-1 ring-white/10'
            }
          >
            <p className="whitespace-pre-wrap break-words">{m.text}</p>
          </div>
          {m.embed && <RecommendEmbed embed={m.embed} onOpen={() => onOpen(m.embed)} />}
        </div>
      </div>
    </div>
  )
}

function Typing() {
  return (
    <div className="flex justify-start gap-2">
      <span className="mt-0.5 flex h-7 w-7 items-center justify-center rounded-full bg-sea-500/25 text-[13px] ring-1 ring-white/10">⚓</span>
      <div className="glass flex items-center gap-1 rounded-2xl rounded-tl-md px-4 py-3.5 ring-1 ring-white/10">
        {[0, 1, 2].map((i) => (
          <span key={i} className="h-1.5 w-1.5 animate-bounce rounded-full bg-sea-200"
                style={{ animationDelay: `${i * 0.14}s` }} />
        ))}
      </div>
    </div>
  )
}

export default function ChatScreen({ onFinish }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(true)
  const [sessionId, setSessionId] = useState(null)
  const [progress, setProgress] = useState({ settled: 0, total: 10 })
  const [error, setError] = useState(null)
  const bottom = useRef(null)
  const boot = useRef(false)

  useEffect(() => {
    if (boot.current) return
    boot.current = true
    ;(async () => {
      try {
        const r = await api.startChat()
        setSessionId(r.session_id)
        setProgress(r.progress)
        // 인사말 → 첫 질문 순서로 자연스럽게 등장
        for (let i = 0; i < r.messages.length; i++) {
          await new Promise((res) => setTimeout(res, i === 0 ? 120 : 520))
          setMessages((prev) => [...prev, { role: 'assistant', ...r.messages[i] }])
        }
      } catch (e) {
        setError('서버에 연결하지 못했어요. 백엔드(uvicorn)가 켜져 있는지 확인해 주세요.')
      } finally {
        setBusy(false)
      }
    })()
  }, [])

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, busy])

  const send = async (text) => {
    const t = (text ?? input).trim()
    if (!t || busy || !sessionId) return
    setInput('')
    setMessages((p) => [...p, { role: 'user', text: t }])
    setBusy(true)
    try {
      const r = await api.sendChat(sessionId, t)
      setProgress(r.progress)
      await new Promise((res) => setTimeout(res, 420))
      for (const m of r.messages) {
        setMessages((p) => [...p, { role: 'assistant', ...m }])
        await new Promise((res) => setTimeout(res, 340))
      }
    } catch (e) {
      setError('메시지를 보내지 못했어요. 잠시 후 다시 시도해 주세요.')
    } finally {
      setBusy(false)
    }
  }

  const pct = Math.round(((progress.settled ?? 0) / (progress.total || 10)) * 100)

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
            취향 파악 {pct}%
          </span>
        </div>
        <div className="mt-2.5 h-[3px] w-full overflow-hidden rounded-full bg-white/10">
          <div className="h-full rounded-full bg-gradient-to-r from-sea-400 to-sea-200 transition-[width] duration-500"
               style={{ width: `${pct}%` }} />
        </div>
      </header>

      {/* 대화 */}
      <div className="scroll-thin flex-1 space-y-3.5 overflow-y-auto px-4 pb-4">
        {messages.map((m, i) => <Bubble key={i} m={m} onOpen={(e) => onFinish(sessionId, e)} />)}
        {busy && <Typing />}
        {error && (
          <div className="rounded-xl bg-red-500/15 px-3.5 py-2.5 text-[13px] text-red-200 ring-1 ring-red-400/25">
            {error}
          </div>
        )}
        <div ref={bottom} />
      </div>

      {/* 입력 */}
      <div className="shrink-0 border-t border-white/10 bg-sea-950/70 px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 backdrop-blur">
        <div className="flex items-end gap-2">
          <textarea
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
            }}
            placeholder="편하게 답해 주세요…"
            className="max-h-28 flex-1 resize-none rounded-2xl bg-white/10 px-4 py-3 text-[14px] text-white
                       placeholder:text-sea-300/50 ring-1 ring-white/10 outline-none transition
                       focus:bg-white/[.14] focus:ring-sea-400/50"
          />
          <button
            onClick={() => send()}
            disabled={busy || !input.trim()}
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-sea-500 text-white
                       transition hover:bg-sea-400 disabled:opacity-35"
            aria-label="보내기"
          >
            ↑
          </button>
        </div>
      </div>
    </div>
  )
}
