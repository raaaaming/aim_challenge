import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,          // 모든 인터페이스 바인딩 (LAN·터널 노출)
    port: 5174,
    allowedHosts: true,  // 터널 호스트명(*.loca.lt 등) 차단 방지 — 개발용
    proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } },
  },
})
