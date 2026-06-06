import { useState, useEffect, useRef, useCallback } from 'react'
import Header from '../components/Header'
import NewsCard from '../components/NewsCard'
import ChatBot from '../components/ChatBot'
import MyPage from '../components/MyPage'
import FAB from '../components/FAB.jsx'
import { useAuthStore } from '../store/authStore'
import { getRecommendedFeed, getTrendingFeed, getLatestFeed } from '../api/feed'
import '../styles/main.css'

const BADGE_CLASS = {
  '정치': 'main__latest-item-badge--politics',
  '경제': 'main__latest-item-badge--economy',
  '사회': 'main__latest-item-badge--society',
}

export default function Main() {
  const { isLoggedIn, openAuthModal } = useAuthStore()

  const [recommended, setRecommended] = useState([])
  const [trending, setTrending] = useState([])
  const [latest, setLatest] = useState([])
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(true)
  const [loading, setLoading] = useState(false)
  const [chatOpen, setChatOpen] = useState(false)
  const [mypageOpen, setMypageOpen] = useState(false)

  const observerRef = useRef(null)
  const bottomRef = useRef(null)

  const loadLatest = useCallback(async (pageNum) => {
    if (loading) return
    setLoading(true)
    try {
      const data = await getLatestFeed(pageNum)
      if (data.length === 0) {
        setHasMore(false)
      } else {
        setLatest(prev => pageNum === 1 ? data : [...prev, ...data])
        setPage(pageNum)
      }
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [loading])

  useEffect(() => {
    const init = async () => {
      if (isLoggedIn) {
        getRecommendedFeed().then(setRecommended).catch(console.error)
      }
      getTrendingFeed().then(setTrending).catch(console.error)
      await loadLatest(1)
    }
    init()
  }, [isLoggedIn])

  const handleObserver = useCallback((entries) => {
    const target = entries[0]
    if (target.isIntersecting && hasMore && !loading) {
      loadLatest(page + 1)
    }
  }, [hasMore, loading, page, loadLatest])

  useEffect(() => {
    observerRef.current = new IntersectionObserver(handleObserver, { threshold: 0.5 })
    if (bottomRef.current) observerRef.current.observe(bottomRef.current)
    return () => observerRef.current?.disconnect()
  }, [handleObserver])

  return (
    <div className="main">
      <Header />

      <div className="main__content">

        {isLoggedIn ? (
          <section className="main__section">
            <div className="main__section-title">
              <span className="main__section-title--star">★</span>
              나를 위한 추천
            </div>
            <div className="main__card-grid">
              {recommended.map(article => (
                <NewsCard key={article.article_id} article={article} showSimilarity />
              ))}
            </div>
          </section>
        ) : (
          <div className="main__login-banner">
            <p className="main__login-banner-title">로그인하면 맞춤 뉴스를 추천해드려요</p>
            <p className="main__login-banner-sub">관심 카테고리 기반으로 나만의 뉴스 피드를 만들어보세요</p>
            <button className="main__login-banner-btn" onClick={openAuthModal}>
              로그인하기
            </button>
          </div>
        )}

        <section className="main__section">
          <div className="main__section-title">
            🔥 지금 화제
          </div>
          <div className="main__card-grid">
            {trending.map(article => (
              <NewsCard key={article.article_id} article={article} showPressCount />
            ))}
          </div>
        </section>

        <section className="main__section">
          <div className="main__section-title">
            📰 최신 뉴스
          </div>
          <div className="main__latest-list">
            {latest.map(article => (
              <div
                key={article.article_id}
                className="main__latest-item"
                onClick={() => window.open(article.url, '_blank')}
              >
                <span className={`main__latest-item-badge ${BADGE_CLASS[article.category_name]}`}>
                  {article.category_name}
                </span>
                <div className="main__latest-item-content">
                  <p className="main__latest-item-title">{article.title}</p>
                  <span className="main__latest-item-meta">
                    {article.source_name} · {article.published_ago}
                  </span>
                </div>
                <span className="main__latest-item-icon">↗</span>
              </div>
            ))}
          </div>
          <div ref={bottomRef} className="main__bottom-trigger">
            {loading && <span className="main__loading-text">불러오는 중...</span>}
            {!hasMore && <span className="main__loading-text">모든 뉴스를 불러왔어요</span>}
          </div>
        </section>

      </div>

      <FAB
        onChatOpen={() => setChatOpen(true)}
        onMypageOpen={() => setMypageOpen(true)}
      />

      <ChatBot isOpen={chatOpen} onClose={() => setChatOpen(false)} />
      <MyPage isOpen={mypageOpen} onClose={() => setMypageOpen(false)} />
    </div>
  )
}