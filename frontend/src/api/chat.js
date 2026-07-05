import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const api = axios.create({ baseURL: BASE_URL })

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export const sendMessage = async (question, sessionId) => {
  const { data } = await api.post('/chat', { question, session_id: sessionId })
  return data
}

// Kafka + SSE 스트리밍
export const sendMessageStream = async (question, sessionId, onChunk, onDone) => {
  const token = localStorage.getItem('token')

  const response = await fetch(`${BASE_URL}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({ question, session_id: sessionId }),
  })

  if (!response.ok) throw new Error('스트리밍 요청 실패')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    const text = decoder.decode(value)
    const lines = text.split('\n')

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const data = line.slice(6)
      if (data === '[DONE]') {
        onDone?.()
        return
      }
      try {
        const parsed = JSON.parse(data)
        // 처리 중 메시지는 무시
        if (parsed.status === 'processing') continue
        // 청크 누적
        if (parsed.chunk && parsed.status !== 'processing') onChunk(parsed.chunk)
        // 완료
        if (parsed.status === 'done') onDone?.()
        if (parsed.error) throw new Error(parsed.error)
      } catch {}
    }
  }
}

export const getSessions = async () => {
  const { data } = await api.post('/chat/sessions')
  return data
}

export const getHistory = async (sessionId) => {
  const { data } = await api.get(`/chat/history/${sessionId}`)
  return data
}

export const createSessionId = () => crypto.randomUUID()