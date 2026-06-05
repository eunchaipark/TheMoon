import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const api = axios.create({ baseURL: BASE_URL })

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export const sendMessage = async (question) => {
  const sessionId = localStorage.getItem('session_id') || crypto.randomUUID()
  localStorage.setItem('session_id', sessionId)
  const { data } = await api.post('/chat', { question, session_id: sessionId })
  return data
}