import { useState, useRef, useEffect } from 'react'
import '../styles/fab.css'

const BTN_SIZE = 55
const BTN_GAP = 10
const TOTAL_HEIGHT = BTN_SIZE * 2 + BTN_GAP
const PADDING_RIGHT = 35
const PADDING_BOTTOM = 60

export default function FAB({ onChatOpen, onMypageOpen }) {
  const [topY, setTopY] = useState(window.innerHeight - TOTAL_HEIGHT - PADDING_BOTTOM)
  const dragging = useRef(false)
  const dragStartY = useRef(0)
  const startTopY = useRef(0)
  const hasDragged = useRef(false)

  const clamp = (val) => Math.min(
    Math.max(val, PADDING_BOTTOM),
    window.innerHeight - TOTAL_HEIGHT - PADDING_BOTTOM
  )

  useEffect(() => {
    const onMouseMove = (e) => {
      if (!dragging.current) return
      hasDragged.current = true
      setTopY(clamp(startTopY.current + e.clientY - dragStartY.current))
    }
    const onMouseUp = () => { dragging.current = false }
    const onTouchMove = (e) => {
      if (!dragging.current) return
      hasDragged.current = true
      setTopY(clamp(startTopY.current + e.touches[0].clientY - dragStartY.current))
    }
    const onTouchEnd = () => { dragging.current = false }

    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
    window.addEventListener('touchmove', onTouchMove)
    window.addEventListener('touchend', onTouchEnd)
    return () => {
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
      window.removeEventListener('touchmove', onTouchMove)
      window.removeEventListener('touchend', onTouchEnd)
    }
  }, [])

  const handleMouseDown = (e) => {
    hasDragged.current = false
    dragStartY.current = e.clientY
    startTopY.current = topY
    dragging.current = true
  }

  const handleTouchStart = (e) => {
    hasDragged.current = false
    dragStartY.current = e.touches[0].clientY
    startTopY.current = topY
    dragging.current = true
  }

  return (
    <div
      className="fab"
      style={{ top: topY, right: PADDING_RIGHT }}
      onMouseDown={handleMouseDown}
      onTouchStart={handleTouchStart}
    >
      <button
        className="fab__btn"
        onClick={() => { if (!hasDragged.current) onMypageOpen() }}
        aria-label="마이페이지"
      >
        👤
      </button>
      <button
        className="fab__btn fab__btn--chat"
        onClick={() => { if (!hasDragged.current) onChatOpen() }}
        aria-label="챗봇 열기"
      >
        💬
      </button>
    </div>
  )
}