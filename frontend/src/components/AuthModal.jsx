import { useState } from 'react'
import { useAuthStore } from '../store/authStore'
import { login, register } from '../api/auth'
import '../styles/auth-modal.css'

const CATEGORIES = [
  { id: 1, name: '정치' },
  { id: 2, name: '경제' },
  { id: 3, name: '사회' },
]

export default function AuthModal({ isOpen, onClose }) {
  const { login: setLogin } = useAuthStore()
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ email: '', password: '', nickname: '' })
  const [prefs, setPrefs] = useState({ 1: 5, 2: 5, 3: 5 })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  if (!isOpen) return null

  const handleChange = e => {
    setForm(prev => ({ ...prev, [e.target.name]: e.target.value }))
  }

  const handleSubmit = async () => {
    setError('')
    if (!form.email || !form.password) {
      setError('이메일과 비밀번호를 입력해주세요')
      return
    }
    if (mode === 'register' && !form.nickname) {
      setError('닉네임을 입력해주세요')
      return
    }
    setLoading(true)
    try {
      if (mode === 'login') {
        const data = await login(form.email, form.password)
        setLogin(data.user, data.token)
      } else {
        const categoryPrefs = CATEGORIES.map(cat => ({
          category_id: cat.id,
          weight: prefs[cat.id]
        }))
        const data = await register({ ...form, category_prefs: categoryPrefs })
        setLogin(data.user, data.token)
      }
      onClose()
    } catch (e) {
      setError(mode === 'login'
        ? '이메일 또는 비밀번호가 올바르지 않아요'
        : '이미 사용 중인 이메일이에요'
      )
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = e => {
    if (e.key === 'Enter') handleSubmit()
  }

  const switchMode = () => {
    setMode(prev => prev === 'login' ? 'register' : 'login')
    setError('')
    setForm({ email: '', password: '', nickname: '' })
  }

  return (
    <div className="auth-modal__overlay" onClick={onClose}>
      <div className="auth-modal__panel" onClick={e => e.stopPropagation()}>

        <button className="auth-modal__close" onClick={onClose}>✕</button>

        <p className="auth-modal__logo">TheMoon</p>
        <p className="auth-modal__subtitle">
          {mode === 'login' ? '오늘의 뉴스를 한눈에' : '관심 카테고리를 설정하고 시작하세요'}
        </p>

        <div className="auth-modal__form">
          <div className="auth-modal__form-group">
            <label className="auth-modal__form-label">이메일</label>
            <input
              className="auth-modal__form-input"
              type="email"
              name="email"
              placeholder="이메일을 입력하세요"
              value={form.email}
              onChange={handleChange}
              onKeyDown={handleKeyDown}
            />
          </div>

          {mode === 'register' && (
            <div className="auth-modal__form-group">
              <label className="auth-modal__form-label">닉네임</label>
              <input
                className="auth-modal__form-input"
                type="text"
                name="nickname"
                placeholder="닉네임을 입력하세요"
                value={form.nickname}
                onChange={handleChange}
              />
            </div>
          )}

          <div className="auth-modal__form-group">
            <label className="auth-modal__form-label">비밀번호</label>
            <input
              className="auth-modal__form-input"
              type="password"
              name="password"
              placeholder="비밀번호를 입력하세요"
              value={form.password}
              onChange={handleChange}
              onKeyDown={handleKeyDown}
            />
          </div>

          {mode === 'register' && (
            <div>
              <p className="auth-modal__category-title">관심 카테고리 설정</p>
              <div className="auth-modal__category-list">
                {CATEGORIES.map(cat => (
                  <div key={cat.id} className="auth-modal__category-item">
                    <span className="auth-modal__category-label">{cat.name}</span>
                    <div className="auth-modal__category-control">
                      <input
                        className="auth-modal__category-slider"
                        type="range"
                        min="1"
                        max="10"
                        value={prefs[cat.id]}
                        onChange={e => setPrefs(prev => ({ ...prev, [cat.id]: Number(e.target.value) }))}
                      />
                      <span className="auth-modal__category-value">{prefs[cat.id]}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {error && <p className="auth-modal__error">{error}</p>}

          <button
            className="auth-modal__submit-btn"
            onClick={handleSubmit}
            disabled={loading}
          >
            {loading ? '처리 중...' : mode === 'login' ? '로그인' : '회원가입'}
          </button>
        </div>

        <div className="auth-modal__footer">
          <span className="auth-modal__footer-text">
            {mode === 'login' ? '아직 계정이 없으신가요? ' : '이미 계정이 있으신가요? '}
          </span>
          <button className="auth-modal__footer-link" onClick={switchMode}>
            {mode === 'login' ? '회원가입' : '로그인'}
          </button>
        </div>

      </div>
    </div>
  )
}