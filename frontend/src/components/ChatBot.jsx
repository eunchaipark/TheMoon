import { useState, useRef, useEffect } from 'react'
import { sendMessageStream, getSessions, getHistory, createSessionId } from '../api/chat'
import { useAuthStore } from '../store/authStore'
import ReactMarkdown from 'react-markdown'
import '../styles/chatbot.css'

function groupSessionsByDate(sessions) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)

  const groups = { '오늘': [], '어제': [], '이전': [] }
  sessions.forEach(s => {
    const d = new Date(s.updated_at)
    if (d >= today) groups['오늘'].push(s)
    else if (d >= yesterday) groups['어제'].push(s)
    else groups['이전'].push(s)
  })
  return groups
}

function formatSessionTime(dateStr) {
  const d = new Date(dateStr)
  return d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })
}

export default function ChatBot({ isOpen, onClose }) {
  const { isLoggedIn } = useAuthStore()

  const [sessions, setSessions]           = useState([])
  const [activeSession, setActiveSession] = useState(null)
  const [messages, setMessages]           = useState([])
  const [input, setInput]                 = useState('')
  const [loading, setLoading]             = useState(false)
  const [sidebarOpen, setSidebarOpen]     = useState(false)
  const [sessionsLoading, setSessionsLoading] = useState(false)

  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (!isOpen) return
    const savedSession = localStorage.getItem('session_id')
    if (savedSession) {
      setActiveSession(savedSession)
      loadHistory(savedSession)
    } else {
      const newId = createSessionId()
      localStorage.setItem('session_id', newId)
      setActiveSession(newId)
      setMessages([{ role: 'assistant', text: '안녕하세요! 뉴스에 대해 무엇이든 질문해보세요. 실시간 웹 검색과 뉴스 DB를 함께 활용해 답변드립니다.' }])
    }
  }, [isOpen])

  const loadHistory = async (sessionId) => {
    try {
      const history = await getHistory(sessionId)
      if (history.length > 0) {
        setMessages(history.map(h => ({ role: h.role, text: h.message })))
      } else {
        setMessages([{ role: 'assistant', text: '안녕하세요! 뉴스에 대해 무엇이든 질문해보세요. 실시간 웹 검색과 뉴스 DB를 함께 활용해 답변드립니다.' }])
      }
    } catch {
      setMessages([{ role: 'assistant', text: '안녕하세요! 뉴스에 대해 무엇이든 질문해보세요.' }])
    }
  }

  const loadSessions = async () => {
    setSessionsLoading(true)
    try {
      const data = await getSessions()
      setSessions(data)
    } catch {
      setSessions([])
    } finally {
      setSessionsLoading(false)
    }
  }

  const handleOpenSidebar = () => {
    setSidebarOpen(true)
    loadSessions()
  }

  const handleSelectSession = async (sessionId) => {
    setActiveSession(sessionId)
    localStorage.setItem('session_id', sessionId)
    setSidebarOpen(false)
    await loadHistory(sessionId)
  }

  const handleNewChat = () => {
    const newId = createSessionId()
    localStorage.setItem('session_id', newId)
    setActiveSession(newId)
    setMessages([{ role: 'assistant', text: '안녕하세요! 뉴스에 대해 무엇이든 질문해보세요.' }])
    setSidebarOpen(false)
  }

  const handleSend = async () => {
    if (!input.trim() || loading) return
    const question = input.trim()
    setInput('')

    setMessages(prev => [...prev, { role: 'user', text: question }])
    setLoading(true)

    // 스트리밍 메시지 placeholder 추가 (빈 텍스트로 시작)
    setMessages(prev => [...prev, { role: 'assistant', text: '', streaming: true }])

    try {
      await sendMessageStream(
        question,
        activeSession,
        (chunk) => {
          if (chunk === '답변을 생성하고 있어요...') return
          // 청크 단위로 마지막 메시지에 누적
          setMessages(prev => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last?.streaming) {
              updated[updated.length - 1] = { ...last, text: last.text + chunk }
            }
            return updated
          })
        },
        () => {
          // 스트리밍 완료
          setMessages(prev => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last?.streaming) {
              updated[updated.length - 1] = { ...last, streaming: false }
            }
            return updated
          })
        }
      )
    } catch {
      setMessages(prev => {
        const updated = [...prev]
        const last = updated[updated.length - 1]
        if (last?.streaming) {
          updated[updated.length - 1] = {
            role: 'assistant',
            text: '답변을 가져오는 중 오류가 발생했어요. 다시 시도해주세요.',
            streaming: false,
          }
        }
        return updated
      })
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  if (!isOpen) return null

  const sessionGroups = groupSessionsByDate(sessions)

  return (
    <div className="chatbot__overlay" onClick={onClose}>
      <div className="chatbot__panel" onClick={e => e.stopPropagation()}>

        {/* 사이드바 */}
        {sidebarOpen && (
          <div className="chatbot__sidebar">
            <div className="chatbot__sidebar-header">
              <span className="chatbot__sidebar-title">대화 내역</span>
              <button className="chatbot__sidebar-close" onClick={() => setSidebarOpen(false)}>✕</button>
            </div>
            <button className="chatbot__new-chat" onClick={handleNewChat}>+ 새 대화</button>
            <div className="chatbot__sidebar-list">
              {sessionsLoading ? (
                <p className="chatbot__sidebar-empty">불러오는 중...</p>
              ) : sessions.length === 0 ? (
                <p className="chatbot__sidebar-empty">대화 내역이 없어요</p>
              ) : (
                Object.entries(sessionGroups).map(([group, items]) =>
                  items.length > 0 && (
                    <div key={group}>
                      <p className="chatbot__sidebar-group">{group}</p>
                      {items.map(s => (
                        <button
                          key={s.session_id}
                          className={`chatbot__sidebar-item ${activeSession === s.session_id ? 'chatbot__sidebar-item--active' : ''}`}
                          onClick={() => handleSelectSession(s.session_id)}
                        >
                          <span className="chatbot__sidebar-item-time">{formatSessionTime(s.updated_at)}</span>
                          <span className="chatbot__sidebar-item-id">{s.session_id.slice(0, 8)}...</span>
                        </button>
                      ))}
                    </div>
                  )
                )
              )}
            </div>
          </div>
        )}

        {/* 메인 패널 */}
        <div className="chatbot__main">
          <div className="chatbot__header">
            <div className="chatbot__header-left">
              <button className="chatbot__history-btn" onClick={handleOpenSidebar}>☰</button>
              <span className="chatbot__header-title">뉴스 챗봇</span>
              <span className="chatbot__header-badge">AI Agent</span>
            </div>
            <button className="chatbot__header-close" onClick={onClose}>✕</button>
          </div>

          <div className="chatbot__messages">
            {messages.map((msg, i) => (
              <div key={i} className={`chatbot__message--${msg.role}`}>
                {msg.role === 'user' ? (
                  <p className="chatbot__message-text--user">{msg.text}</p>
                ) : (
                  <div className="chatbot__message-text">
                    <ReactMarkdown>{msg.text}</ReactMarkdown>
                    {msg.streaming && <span className="chatbot__cursor">▋</span>}
                  </div>
                )}
                {msg.sources && msg.sources.length > 0 && (
                  <div className="chatbot__message-sources">
                    <span className="chatbot__sources-label">출처</span>
                    {msg.sources.map((s, idx) => (
                      <a key={idx} href={s.url} target="_blank" rel="noreferrer" className="chatbot__source-link">
                        {s.source_name}
                      </a>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {loading && !messages[messages.length - 1]?.streaming && (
              <div className="chatbot__loading">도구 선택 중...</div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="chatbot__input-area">
            <input
              className="chatbot__input"
              type="text"
              placeholder="뉴스 DB + 실시간 웹 검색으로 답변해드려요..."
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={loading}
            />
            <button
              className="chatbot__send-btn"
              onClick={handleSend}
              disabled={loading || !input.trim()}
            >
              전송
            </button>
          </div>
        </div>

      </div>
    </div>
  )
}