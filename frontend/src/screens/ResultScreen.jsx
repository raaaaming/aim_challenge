import { useEffect, useState } from 'react'
import { api } from '../lib/api'

/** Supabase Storage 이미지가 없을 때 쓰는 그라디언트 폴백 */
function ImageBlock({ src, name }) {
  const [failed, setFailed] = useState(false)
  const ok = src && !failed
  return (
    <div className="relative h-64 w-full overflow-hidden bg-sea-800 sm:h-80">
      {ok ? (
        <img src={src} alt={name} onError={() => setFailed(true)}
             className="h-full w-full object-cover" />
      ) : (
        <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-sea-700 via-sea-800 to-sea-950">
          <span className="text-5xl opacity-40">🌊</span>
        </div>
      )}
      <div className="absolute inset-x-0 bottom-0 h-2/3 bg-gradient-to-t from-sea-950 via-sea-950/70 to-transparent" />
    </div>
  )
}

function ScoreBar({ axis, value }) {
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <span className="truncate text-[11px] font-medium text-sea-200">{axis.label}</span>
        <span className="shrink-0 text-[11px] font-bold tabular-nums text-white">{value.toFixed(1)}</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10">
        <div className="h-full rounded-full bg-gradient-to-r from-sea-400 to-sea-200"
             style={{ width: `${(value / 10) * 100}%` }} />
      </div>
      <div className="mt-1 flex justify-between text-[9px] text-sea-400">
        <span className="truncate">{axis.low?.split(' (')[0]}</span>
        <span className="truncate text-right">{axis.high?.split(' (')[0]}</span>
      </div>
    </div>
  )
}

export default function ResultScreen({ sessionId, onRestart }) {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  const [showSource, setShowSource] = useState(false)

  useEffect(() => {
    api.result(sessionId).then(setData).catch(() => setErr('결과를 불러오지 못했어요.'))
  }, [sessionId])

  if (err) {
    return <div className="flex h-full items-center justify-center bg-sea-950 p-6 text-center text-sea-200">{err}</div>
  }
  if (!data) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 bg-sea-950">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-sea-500 border-t-transparent" />
        <p className="text-[13px] text-sea-300">추천 결과를 정리하고 있어요…</p>
      </div>
    )
  }

  const d = data.description
  const axmap = Object.fromEntries((data.axes ?? []).map((a) => [a.key, a]))

  return (
    <div className="scroll-thin h-full overflow-y-auto bg-sea-950 pb-10">
      <ImageBlock src={data.image_url} name={data.place_name} />

      {/* 타이틀 */}
      <div className="-mt-20 px-5">
        <div className="animate-floatUp">
          <div className="mb-2 flex flex-wrap items-center gap-1.5">
            {(d.keywords ?? []).slice(0, 4).map((k) => (
              <span key={k} className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-medium text-sea-100 ring-1 ring-white/10">
                #{k}
              </span>
            ))}
          </div>
          <p className="text-[13px] font-semibold text-sea-300">{d.headline}</p>
          {/* 여행지_20_포항.csv 의 place_name 원문 그대로 */}
          <h1 className="mt-1 text-[30px] font-black leading-tight tracking-[-0.03em] text-white">
            {data.place_name}
          </h1>
          {data.fit_score > 0 && (
            <div className="mt-3 inline-flex items-center gap-2 rounded-full bg-sea-500/20 px-3 py-1.5 ring-1 ring-sea-400/30">
              <span className="text-[11px] font-semibold text-sea-100">취향 일치도</span>
              <span className="text-[13px] font-black tabular-nums text-white">{data.fit_score}%</span>
            </div>
          )}
        </div>
      </div>

      {/* 재생성된 소개글 */}
      <div className="mt-6 space-y-4 px-5">
        <p className="animate-floatUp text-[14px] leading-[1.75] text-sea-100">{d.intro}</p>

        {(d.highlights ?? []).map((h, i) => (
          <div key={i} className="animate-floatUp glass rounded-2xl p-4 ring-1 ring-white/10"
               style={{ animationDelay: `${0.05 * (i + 1)}s` }}>
            <p className="mb-1.5 text-[12px] font-bold text-sea-300">{h.title}</p>
            <p className="text-[13.5px] leading-relaxed text-sea-50">{h.body}</p>
          </div>
        ))}

        {d.good_for && (
          <div className="animate-floatUp rounded-2xl bg-gradient-to-br from-sea-600/30 to-sea-800/30 p-4 ring-1 ring-sea-400/20">
            <p className="mb-1.5 text-[12px] font-bold text-sea-200">이런 분께 잘 맞아요</p>
            <p className="text-[13.5px] leading-relaxed text-white">{d.good_for}</p>
          </div>
        )}
      </div>

      {/* 내 취향과 맞은 지점 */}
      {data.matched_axes?.length > 0 && (
        <div className="mt-8 px-5">
          <h2 className="mb-3 text-[13px] font-bold text-white">이래서 이곳을 골랐어요</h2>
          <div className="space-y-2">
            {data.matched_axes.map((c) => (
              <div key={c.axis} className="glass rounded-xl p-3 ring-1 ring-white/10">
                <div className="mb-1 flex items-center justify-between">
                  <span className="text-[12px] font-semibold text-sea-100">{c.label}</span>
                  <span className="rounded bg-white/10 px-1.5 py-0.5 text-[10px] tabular-nums text-sea-200">
                    나 {c.user_value} · 이곳 {c.place_value}
                  </span>
                </div>
                <p className="text-[11.5px] leading-relaxed text-sea-300">{c.reason}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 10축 점수 */}
      <div className="mt-8 px-5">
        <h2 className="mb-3 text-[13px] font-bold text-white">이 여행지의 취향 점수</h2>
        <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
          {(data.axes ?? []).map((a) => (
            <ScoreBar key={a.key} axis={a} value={Number(data.scores[a.key])} />
          ))}
        </div>
      </div>

      {/* 재생성 근거 원문 */}
      <div className="mt-8 px-5">
        <button onClick={() => setShowSource((v) => !v)}
                className="w-full rounded-xl bg-white/5 px-4 py-3 text-left text-[12px] font-semibold text-sea-300 ring-1 ring-white/10">
          설명 재생성에 사용한 원문 보기 {showSource ? '▲' : '▼'}
        </button>
        {showSource && (
          <div className="mt-2 space-y-2 rounded-xl bg-black/20 p-4 text-[11.5px] leading-relaxed text-sea-300 ring-1 ring-white/5">
            <p><b className="text-sea-200">summary</b> · {data.source_fields.summary}</p>
            <p><b className="text-sea-200">embedding_text</b> · {data.source_fields.embedding_text}</p>
            {data.source_fields.evidence_texts.map((e, i) => (
              <p key={i}><b className="text-sea-200">evidence_text_{i + 1}</b> · {e}</p>
            ))}
          </div>
        )}
      </div>

      {/* 차점자 */}
      {data.runner_ups?.length > 0 && (
        <div className="mt-8 px-5">
          <h2 className="mb-3 text-[13px] font-bold text-white">이런 곳도 잘 맞아요</h2>
          <div className="flex flex-wrap gap-2">
            {data.runner_ups.map((r) => (
              <span key={r.place_id} className="rounded-full bg-white/8 px-3 py-1.5 text-[11.5px] text-sea-100 ring-1 ring-white/10">
                {r.place_name} <span className="tabular-nums text-sea-400">{r.fit_score}%</span>
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="mt-10 px-5">
        <button onClick={onRestart}
                className="w-full rounded-2xl bg-white/10 py-3.5 text-[14px] font-bold text-white ring-1 ring-white/15 transition hover:bg-white/15">
          처음부터 다시 찾아보기
        </button>
      </div>
    </div>
  )
}
