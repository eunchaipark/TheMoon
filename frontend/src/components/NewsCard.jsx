import { useState } from 'react'
import { createPortal } from 'react-dom'
import { getOtherPressFeed } from '../api/feed'
import '../styles/news-card.css'

const BADGE_CLASS = {
  '정치': 'news-card__badge--politics',
  '경제': 'news-card__badge--economy',
  '사회': 'news-card__badge--society',
}

export default function NewsCard({ article, showSimilarity = false, showPressCount = false, showDescription = false }) {
  const [popupOpen, setPopupOpen] = useState(false)
  const [others, setOthers] = useState(null)
  const [loadingOthers, setLoadingOthers] = useState(false)

  const badgeClass = BADGE_CLASS[article.category_name] || 'news-card__badge--politics'

  const handleClick = () => window.open(article.url, '_blank')

  const handleShowOthers = async (e) => {
    e.stopPropagation()
    setPopupOpen(true)
    if (others === null) {
      setLoadingOthers(true)
      try {
        const data = await getOtherPressFeed(article.article_id)
        setOthers(data)
      } catch {
        setOthers([])
      } finally {
        setLoadingOthers(false)
      }
    }
  }

  const popup = popupOpen && createPortal(
    <div className="news-card__popup-overlay" onClick={() => setPopupOpen(false)}>
      <div className="news-card__popup" onClick={e => e.stopPropagation()}>
        <div className="news-card__popup-header">
          <span className="news-card__popup-title">다른 언론사 보기</span>
          <button className="news-card__popup-close" onClick={() => setPopupOpen(false)}>✕</button>
        </div>
        <div className="news-card__popup-list">
          {loadingOthers ? (
            <p className="news-card__popup-empty">불러오는 중...</p>
          ) : others?.length > 0 ? (
            others.map(a => (
              <a key={a.article_id} href={a.url} target="_blank" rel="noreferrer" className="news-card__popup-item">
                <span className="news-card__popup-source">{a.source_name}</span>
                <span className="news-card__popup-item-title">{a.title}</span>
                <span className="news-card__popup-time">{a.published_ago}</span>
              </a>
            ))
          ) : (
            <p className="news-card__popup-empty">다른 언론사 기사가 없어요</p>
          )}
        </div>
      </div>
    </div>,
    document.body
  )

  return (
    <>
      <div className="news-card" onClick={handleClick}>
        <div className="news-card__top">
          <span className={`news-card__badge ${badgeClass}`}>
            {article.category_name}
          </span>
          {showPressCount && (
            <span className="news-card__press-count">언론사 {article.press_count}곳</span>
          )}
        </div>

        <p className="news-card__title">{article.title}</p>

        {showDescription && article.description && (
          <p className="news-card__description">{article.description}</p>
        )}

        <div className="news-card__bottom">
          <div className="news-card__meta">
            <span>{article.source_name}</span>
            <span>·</span>
            <span>{article.published_ago}</span>
            {showSimilarity && article.similarity && (
              <>
                <span>·</span>
                <span className="news-card__meta-similarity">
                  {Math.round(article.similarity * 100)}% 일치
                </span>
              </>
            )}
          </div>
          {showPressCount && (
            <button className="news-card__other-press" onClick={handleShowOthers}>
              다른 언론사 보기 ▼
            </button>
          )}
        </div>
      </div>
      {popup}
    </>
  )
}