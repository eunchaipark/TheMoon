import { useState, useEffect } from 'react'

let listeners = []
let state = {
  isLoggedIn: false,
  user: null,
  token: null,
  authModalOpen: false,
}

function setState(newState) {
  state = { ...state, ...newState }
  listeners.forEach(listener => listener(state))
}

export function useAuthStore() {
  const [, forceUpdate] = useState(0)

  useEffect(() => {
    const listener = () => forceUpdate(n => n + 1)
    listeners.push(listener)

    // 초기화: localStorage에서 로그인 상태 복원
    const token = localStorage.getItem('token')
    const user = localStorage.getItem('user')
    if (token && user) {
      setState({ isLoggedIn: true, user: JSON.parse(user), token })
    }

    return () => {
      listeners = listeners.filter(l => l !== listener)
    }
  }, [])

  const login = (user, token) => {
    localStorage.setItem('token', token)
    localStorage.setItem('user', JSON.stringify(user))
    setState({ isLoggedIn: true, user, token, authModalOpen: false })
  }

  const logout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    setState({ isLoggedIn: false, user: null, token: null })
  }

  const openAuthModal = () => setState({ authModalOpen: true })
  const closeAuthModal = () => setState({ authModalOpen: false })

  return { ...state, login, logout, openAuthModal, closeAuthModal }
}