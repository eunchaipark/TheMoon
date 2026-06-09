import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const api = axios.create({ baseURL: BASE_URL })

export const login = async (email, password) => {
  const { data } = await api.post('/users/login', { email, password })
  return data
}

export const register = async (payload) => {
  const { data } = await api.post('/users/register', payload)
  return data
}