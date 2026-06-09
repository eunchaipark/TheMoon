import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const api = axios.create({baseURL: BASE_URL})

api.interceptors.request.use(config => {
    const token = localStorage.getItem('token')
    if (token) config.headers.Authorization = `Bearer ${token}`
    return config
})

export const getCategoryPrefs = async () => {
    const {data} = await api.get('/users/prefs/categories')
    return data
}

export const updateCategoryPrefs = async (prefs) => {
    const payload = Object.entries(prefs).map(([category_id, weight]) => ({
        category_id: Number(category_id),
        weight
    }))
    const {data} = await api.post('/users/prefs/categories', payload)
    return data
}