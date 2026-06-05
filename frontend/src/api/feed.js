import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({ baseURL: BASE_URL })

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export const getRecommendedFeed = async () => {
  const { data } = await api.get('/feed/recommended')
  return data
}

export const getTrendingFeed = async () => {
  const { data } = await api.get('/feed/trending')
  return data
}

export const getLatestFeed = async (page = 1, limit = 20) => {
  const { data } = await api.get('/feed/articles', { params: { page, limit } })
  return data
}