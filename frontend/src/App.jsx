import { useCallback, useEffect, useState } from 'react'
import SplashScreen from './screens/SplashScreen.jsx'
import MatchScreen from './screens/MatchScreen.jsx'
import ResultScreen from './screens/ResultScreen.jsx'

/**
 * 화면 전환:  splash → (가짜 로딩 1.6초 후 바로) match → (12라운드 종료) result
 *
 * 진행 상태(화면 + 세션 id)를 sessionStorage 에 저장해, 폰 화면이 꺼졌다
 * 다시 켜지며 페이지가 새로 로드돼도 스플래시로 돌아가지 않고 이어서 진행한다.
 * (백엔드의 대결 세션은 메모리에 살아있으므로 id 로 다시 이어붙인다.)
 */
const KEY = 'pohang.session'
const saved = (() => {
  try { return JSON.parse(sessionStorage.getItem(KEY)) || {} } catch { return {} }
})()

export default function App() {
  const [screen, setScreen] = useState(saved.screen ?? 'splash')
  const [sessionId, setSessionId] = useState(saved.sessionId ?? null)
  // 최초 마운트가 '진행 중인 대결 복원'인지 (재시작 시엔 null 이어야 새 게임)
  const [resumeId, setResumeId] = useState(saved.screen === 'match' ? saved.sessionId : null)
  const [runId, setRunId] = useState(0)

  useEffect(() => {
    if (screen === 'splash') sessionStorage.removeItem(KEY)
    else sessionStorage.setItem(KEY, JSON.stringify({ screen, sessionId }))
  }, [screen, sessionId])

  const toMatch = useCallback(() => setScreen('match'), [])
  const toResult = useCallback((sid) => { setSessionId(sid); setScreen('result') }, [])
  const restart = useCallback(() => {
    setResumeId(null)
    setSessionId(null)
    setRunId((n) => n + 1)
    setScreen('match')
  }, [])

  return (
    <div className="mx-auto h-full w-full max-w-[520px] overflow-hidden bg-sea-950 shadow-2xl sm:my-0">
      {screen === 'splash' && <SplashScreen onDone={toMatch} />}
      {screen === 'match' && (
        <MatchScreen key={runId} resumeId={resumeId} onSession={setSessionId} onFinish={toResult} />
      )}
      {screen === 'result' && <ResultScreen sessionId={sessionId} onRestart={restart} />}
    </div>
  )
}
