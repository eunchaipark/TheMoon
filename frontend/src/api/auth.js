// TODO: 백엔드 구성 후 실제 API로 교체
// import axios from 'axios'
// const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000' })

export const login = async (email, password) => {
  // 더미 로그인
  if (email && password) {
    return {
      user: { user_id: 1, email, nickname: email.split('@')[0] },
      token: 'dummy_token_12345'
    }
  }
  throw new Error('로그인 실패')
}

export const register = async (payload) => {
  // 더미 회원가입
  return {
    user: { user_id: 2, email: payload.email, nickname: payload.nickname },
    token: 'dummy_token_67890'
  }
}