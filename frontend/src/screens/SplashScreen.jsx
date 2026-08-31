import { useEffect, useState } from 'react'

/**
 * 첫 시작 화면.
 *  - 서비스 이름 '포항항' 을 화면 중앙보다 약간 위(-8vh)에 띄운다.
 *  - 1.6초 동안 가짜 로딩을 돌린 뒤 곧바로 채팅 화면으로 넘어간다.
 */
const LOADING_MS = 1600

const STEPS = ['포항 여행지 20곳 불러오는 중', '취향 지표 10개 준비 중', '상담원 깨우는 중']

export default function SplashScreen({ onDone }) {
  const [progress, setProgress] = useState(0)
  const [leaving, setLeaving] = useState(false)

  useEffect(() => {
    const started = Date.now()
    const tick = setInterval(() => {
      const p = Math.min(100, ((Date.now() - started) / LOADING_MS) * 100)
      setProgress(p)
    }, 30)
    const out = setTimeout(() => setLeaving(true), LOADING_MS)
    const done = setTimeout(() => onDone(), LOADING_MS + 380)
    return () => { clearInterval(tick); clearTimeout(out); clearTimeout(done) }
  }, [onDone])

  const step = STEPS[Math.min(STEPS.length - 1, Math.floor((progress / 100) * STEPS.length))]

  return (
    <div
      className={`relative h-full w-full overflow-hidden bg-gradient-to-b from-sea-950 via-sea-900 to-sea-800
                  transition-all duration-[380ms] ${leaving ? 'opacity-0 scale-[1.03]' : 'opacity-100'}`}
    >
      {/* 바다 물결 */}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-1/3 opacity-40">
        <div className="animate-wave h-full w-[200%]">
          <svg viewBox="0 0 1440 320" className="h-full w-full" preserveAspectRatio="none">
            <path fill="#3286fb" fillOpacity="0.5"
              d="M0,192L48,197C96,203,192,213,288,197C384,181,480,139,576,144C672,149,768,203,864,213C960,224,1056,192,1152,170C1248,149,1344,139,1392,133L1440,128L1440,320L0,320Z" />
          </svg>
        </div>
      </div>
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-1/4 opacity-30">
        <div className="animate-wave h-full w-[200%]" style={{ animationDelay: '-2.5s' }}>
          <svg viewBox="0 0 1440 320" className="h-full w-full" preserveAspectRatio="none">
            <path fill="#8ec8ff" fillOpacity="0.45"
              d="M0,224L60,213.3C120,203,240,181,360,192C480,203,600,245,720,250.7C840,256,960,224,1080,208C1200,192,1320,192,1380,192L1440,192L1440,320L0,320Z" />
          </svg>
        </div>
      </div>

      {/* 중앙보다 약간 위 */}
      <div className="absolute inset-0 flex flex-col items-center justify-center" style={{ transform: 'translateY(-8vh)' }}>
        <div className="animate-floatUp text-center">
          <div className="mb-4 flex justify-center">
            <span className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-white/10 text-3xl ring-1 ring-white/20">
              ⚓
            </span>
          </div>
          <h1 className="text-6xl font-black tracking-[-0.04em] text-white drop-shadow-[0_4px_24px_rgba(0,0,0,.45)] sm:text-7xl">
            포항항
          </h1>
          <p className="mt-3 text-sm font-medium tracking-wide text-sea-200/90">
            대화로 찾는 나의 포항 여행지
          </p>
        </div>

        {/* 가짜 로딩 */}
        <div className="animate-floatUp mt-12 w-56" style={{ animationDelay: '.15s' }}>
          <div className="h-1 w-full overflow-hidden rounded-full bg-white/15">
            <div className="h-full rounded-full bg-gradient-to-r from-sea-300 to-white transition-[width] duration-100 ease-linear"
                 style={{ width: `${progress}%` }} />
          </div>
          <p className="mt-3 text-center text-[11px] font-medium tracking-wide text-sea-200/70">
            {step}…
          </p>
        </div>
      </div>
    </div>
  )
}
