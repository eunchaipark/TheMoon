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

export const getSessions = async () => {
  const { data } = await api.post('/chat/sessions')
  return data
}

export const getHistory = async (sessionId) => {
  const { data } = await api.get(`/chat/history/${sessionId}`)
  return data
}

export const createSessionId = () => crypto.randomUUID()