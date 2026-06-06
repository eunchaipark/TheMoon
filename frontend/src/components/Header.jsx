import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import AuthModal from './AuthModal'
import '../styles/header.css'
import TheMoonLogo from '../assets/theMoon_Logo.png'

export default function Header() {
  const navigate = useNavigate()
  const { isLoggedIn, user, logout } = useAuthStore()
  const [authOpen, setAuthOpen] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  return (
    <>
      <header className="header">
        <span className="header__logo" onClick={() => navigate('/')}>
          <img src={TheMoonLogo} alt="TheMoon 로고" style={{ height: '80px'}} />
        </span>
        <div className="header__auth">
          {isLoggedIn ? (
            <>
              <span className="header__auth-nickname">{user?.nickname}</span>
              <button className="header__btn--outline" onClick={handleLogout}>로그아웃</button>
            </>
          ) : (
            <button className="header__btn--primary" onClick={() => setAuthOpen(true)}>로그인</button>
          )}
        </div>
      </header>

      <AuthModal isOpen={authOpen} onClose={() => setAuthOpen(false)} />
    </>
  )
}