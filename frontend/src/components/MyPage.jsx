import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { getCategoryPrefs, updateCategoryPrefs } from '../api/user'
import '../styles/mypage.css'

const CATEGORIES = [
  { id: 1, name: '정치' },
  { id: 2, name: '경제' },
  { id: 3, name: '사회' },
]

export default function MyPage({ isOpen, onClose }) {
  const navigate = useNavigate()
  const { isLoggedIn, user } = useAuthStore()
  const [prefs, setPrefs] = useState({ 1: 5, 2: 5, 3: 5 })
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (isOpen && isLoggedIn) {
      getCategoryPrefs()
        .then(data => {
          const map = {}
          data.forEach(p => { map[p.category_id] = p.weight })
          setPrefs(map)
        })
        .catch(console.error)
    }
  }, [isOpen, isLoggedIn])

  if (!isOpen) return null

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateCategoryPrefs(prefs)
      onClose()
    } catch (e) {
      console.error(e)
    } finally {
      setSaving(false)
    }
  }

  const avatarLetter = user?.nickname?.[0] || user?.email?.[0] || '?'

  return (
    <div className="mypage__overlay" onClick={onClose}>
      <div className="mypage__panel" onClick={e => e.stopPropagation()}>

        <div className="mypage__header">
          <span className="mypage__header-title">마이페이지</span>
          <button className="mypage__header-close" onClick={onClose}>✕</button>
        </div>

        {isLoggedIn ? (
          <>
            <div className="mypage__profile">
              <div className="mypage__profile-avatar">{avatarLetter}</div>
              <div>
                <p className="mypage__profile-name">{user?.nickname}</p>
                <p className="mypage__profile-email">{user?.email}</p>
              </div>
            </div>

            <p className="mypage__section-title">관심 카테고리 설정</p>
            <div className="mypage__prefs">
              {CATEGORIES.map(cat => (
                <div key={cat.id} className="mypage__pref-item">
                  <span className="mypage__pref-label">{cat.name}</span>
                  <div className="mypage__pref-control">
                    <input
                      className="mypage__pref-slider"
                      type="range"
                      min="1"
                      max="10"
                      value={prefs[cat.id] || 5}
                      onChange={e => setPrefs(prev => ({ ...prev, [cat.id]: Number(e.target.value) }))}
                    />
                    <span className="mypage__pref-value">{prefs[cat.id] || 5}</span>
                  </div>
                </div>
              ))}
            </div>

            <button
              className="mypage__save-btn"
              onClick={handleSave}
              disabled={saving}
            >
              {saving ? '저장 중...' : '저장하기'}
            </button>
          </>
        ) : (
          <div className="mypage__login-msg">
            <p className="mypage__login-msg-text">로그인이 필요해요</p>
            <button
              className="mypage__login-msg-btn"
              onClick={() => { onClose(); navigate('/login') }}
            >
              로그인하기
            </button>
          </div>
        )}

      </div>
    </div>
  )
}