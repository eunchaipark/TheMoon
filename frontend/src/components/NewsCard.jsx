import '../styles/news-card.css'

const BADGE_CLASS = {
  '정치': 'news-card__badge--politics',
  '경제': 'news-card__badge--economy',
  '사회': 'news-card__badge--society',
}

export default function NewsCard({ article, showSimilarity = false, showPressCount = false }) {
  const badgeClass = BADGE_CLASS[article.category_name] || 'news-card__badge--politics'

  const handleClick = () => {
    window.open(article.url, '_blank')
  }

  return (
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
        <button
          className="news-card__other-press"
          onClick={e => { e.stopPropagation(); article.onShowOthers?.() }}
        >
          다른 언론사 보기 ▼
        </button>
      )}
    </div>
  )
}