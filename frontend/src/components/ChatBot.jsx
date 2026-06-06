import { useState, useRef, useEffect } from 'react'
import { sendMessage } from '../api/chat'
import { useAuthStore } from '../store/authStore'
import '../styles/chatbot.css'

export default function ChatBot({ isOpen, onClose }) {
  const { isLoggedIn } = useAuthStore()
  const [messages, setMessages] = useState([
    { role: 'assistant', text: '안녕하세요! 오늘 뉴스에 대해 궁금한 것을 질문해보세요.' }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (!isOpen) return null

  const handleSend = async () => {
    if (!input.trim() || loading) return
    const question = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', text: question }])
    setLoading(true)
    try {
      const data = await sendMessage(question)
      setMessages(prev => [...prev, {
        role: 'assistant',
        text: data.answer,
        sources: data.sources
      }])
    } catch (e) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        text: '답변을 가져오는 중 오류가 발생했어요. 다시 시도해주세요.'
      }])
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

  return (
    <div className="chatbot__overlay" onClick={onClose}>
      <div className="chatbot__panel" onClick={e => e.stopPropagation()}>

        <div className="chatbot__header">
          <span className="chatbot__header-title">뉴스 챗봇</span>
          <button className="chatbot__header-close" onClick={onClose}>✕</button>
        </div>

        <div className="chatbot__messages">
          {messages.map((msg, i) => (
            <div key={i} className={`chatbot__message--${msg.role}`}>
              <p className={`chatbot__message-text${msg.role === 'user' ? '--user' : ''}`}>
                {msg.text}
              </p>
              {msg.sources && msg.sources.length > 0 && (
                <p className="chatbot__message-sources">
                  출처: {msg.sources.map(s => s.source_name).join(', ')}
                </p>
              )}
            </div>
          ))}
          {loading && (
            <div className="chatbot__loading">답변 생성 중...</div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="chatbot__input-area">
          <input
            className="chatbot__input"
            type="text"
            placeholder="질문을 입력하세요..."
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
  )
}