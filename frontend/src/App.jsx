import { useCallback, useState } from 'react'
import SplashScreen from './screens/SplashScreen.jsx'
import ChatScreen from './screens/ChatScreen.jsx'
import ResultScreen from './screens/ResultScreen.jsx'

/**
 * 화면 전환:  splash → (가짜 로딩 1.6초 후 바로) chat → (임베드 클릭) result
 */
export default function App() {
  const [screen, setScreen] = useState('splash')
  const [sessionId, setSessionId] = useState(null)

  const toChat = useCallback(() => setScreen('chat'), [])
  const toResult = useCallback((sid) => { setSessionId(sid); setScreen('result') }, [])
  const restart = useCallback(() => { setSessionId(null); setScreen('chat') }, [])

  return (
    <div className="mx-auto h-full w-full max-w-[520px] overflow-hidden bg-sea-950 shadow-2xl sm:my-0">
      {screen === 'splash' && <SplashScreen onDone={toChat} />}
      {screen === 'chat' && <ChatScreen key={sessionId ?? 'chat'} onFinish={toResult} />}
      {screen === 'result' && <ResultScreen sessionId={sessionId} onRestart={restart} />}
    </div>
  )
}
