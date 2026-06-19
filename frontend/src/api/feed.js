import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const api = axios.create({ baseURL: BASE_URL })

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export const getRecommendedFeed = async (page = 1, excludeIds = []) => {
  const user = JSON.parse(localStorage.getItem('user') || '{}')
  const params = { user_id: user.user_id, page, limit: 12 }
  if (excludeIds.length > 0) params.exclude_ids = excludeIds.join(',')
  const { data } = await api.get('/feed/recommended', { params })
  return data
}

export const getTrendingFeed = async () => {
  const { data } = await api.get('/feed/trending')
  return data
}

export const getLatestFeed = async (page = 1, limit = 20, categoryId = null) => {
  const params = { page, limit }
  if (categoryId) params.category_id = categoryId
  const { data } = await api.get('/feed/articles', { params })
  return data
}

export const getOtherPressFeed = async (articleId) => {
  const { data } = await api.get(`/feed/trending/${articleId}/others`)
  return data
}

export const connectSSE = (userId, onMessage) => {
  const es = new EventSource(`${BASE_URL}/feed?user_id=${userId}`)
  es.onmessage = (e) => {
    try {
      const articles = JSON.parse(e.data)
      onMessage(articles)
    } catch (_) {}
  }
  es.onerror = () => es.close()
  return es
}