import {useState, useEffect, useRef, useCallback} from 'react'
import Header from '../components/Header'
import NewsCard from '../components/NewsCard'
import ChatBot from '../components/ChatBot'
import MyPage from '../components/MyPage'
import FAB from '../components/FAB.jsx'
import {useAuthStore} from '../store/authStore'
import {getRecommendedFeed, getTrendingFeed, getLatestFeed, connectSSE} from '../api/feed'
import '../styles/main.css'

const BADGE_CLASS = {
    '정치': 'main__latest-item-badge--politics',
    '경제': 'main__latest-item-badge--economy',
    '사회': 'main__latest-item-badge--society',
}

const CATEGORIES = [
    {id: null, name: '전체'},
    {id: 1, name: '정치'},
    {id: 2, name: '경제'},
    {id: 3, name: '사회'},
]

export default function Main() {
    const {isLoggedIn, user, openAuthModal} = useAuthStore()

    const [recommended, setRecommended] = useState([])
    const [recPage, setRecPage] = useState(1)
    const [seenIds, setSeenIds] = useState([])
    const [recLoading, setRecLoading] = useState(false)

    const [trending, setTrending] = useState([])

    const [latest, setLatest] = useState([])
    const [page, setPage] = useState(1)
    const [hasMore, setHasMore] = useState(true)
    const [loading, setLoading] = useState(false)
    const [activeCategory, setActiveCategory] = useState(null)

    const [chatOpen, setChatOpen] = useState(false)
    const [mypageOpen, setMypageOpen] = useState(false)

    const observerRef = useRef(null)
    const bottomRef = useRef(null)
    const sseRef = useRef(null)
    const activeCategoryRef = useRef(null)
    const loadingRef = useRef(false)

    // ── 추천 로드 ─────────────────────────────────
    const loadRecommended = useCallback(async (reset = false) => {
        if (!isLoggedIn || recLoading) return
        setRecLoading(true)
        try {
            const nextPage = reset ? 1 : recPage
            const excludes = reset ? [] : seenIds
            const data = await getRecommendedFeed(nextPage, excludes)
            if (reset) {
                setRecommended(data)
                setSeenIds(data.map(a => a.article_id))
                setRecPage(2)
            } else {
                setRecommended(prev => [...prev, ...data])
                setSeenIds(prev => [...prev, ...data.map(a => a.article_id)])
                setRecPage(p => p + 1)
            }
        } catch (e) {
            console.error(e)
        } finally {
            setRecLoading(false)
        }
    }, [isLoggedIn, recLoading, recPage, seenIds])

    // ── 최신 뉴스 로드 ────────────────────────────
    const loadLatest = useCallback(async (pageNum, catId) => {
        if (loadingRef.current) return
        loadingRef.current = true
        setLoading(true)
        try {
            const data = await getLatestFeed(pageNum, 20, catId)
            if (data.length === 0) {
                setHasMore(false)
            } else {
                setLatest(prev => pageNum === 1 ? data : [...prev, ...data])
                setPage(pageNum)
                setHasMore(true)
            }
        } catch (e) {
            console.error(e)
        } finally {
            loadingRef.current = false
            setLoading(false)
        }
    }, [])

    // ── 카테고리 탭 변경 ──────────────────────────
    const handleCategoryChange = useCallback((catId) => {
        if (catId === activeCategoryRef.current) return
        activeCategoryRef.current = catId
        setActiveCategory(catId)
        setLatest([])
        setPage(1)
        setHasMore(true)
        loadLatest(1, catId)
    }, [loadLatest])

    // ── SSE ───────────────────────────────────────
    useEffect(() => {
        if (isLoggedIn && user) {
            sseRef.current = connectSSE(user.user_id, (newArticles) => {
                if (!Array.isArray(newArticles)) return
                setLatest(prev => {
                    const existingIds = new Set(prev.map(a => a.article_id))
                    const filtered = newArticles.filter(a => !existingIds.has(a.article_id))
                    return [...filtered, ...prev]
                })
            })
        }
        return () => sseRef.current?.close()
    }, [isLoggedIn, user])

    // ── 초기 로드 ─────────────────────────────────
    useEffect(() => {
        const init = async () => {
            if (isLoggedIn) loadRecommended(true)
            getTrendingFeed().then(setTrending).catch(console.error)
            loadLatest(1, null)
        }
        init()
    }, [isLoggedIn])

    // ── 마이페이지 닫힐 때 추천 새로고침 ─────────
    const handleMypageClose = () => {
        setMypageOpen(false)
        if (isLoggedIn) loadRecommended(true)
    }

    // ── 무한 스크롤 ───────────────────────────────
    const handleObserver = useCallback((entries) => {
        const target = entries[0]
        if (target.isIntersecting && hasMore && !loadingRef.current) {
            loadLatest(page + 1, activeCategoryRef.current)
        }
    }, [hasMore, page, loadLatest])

    useEffect(() => {
        observerRef.current = new IntersectionObserver(handleObserver, {threshold: 0.5})
        if (bottomRef.current) observerRef.current.observe(bottomRef.current)
        return () => observerRef.current?.disconnect()
    }, [handleObserver])

    return (
        <div className="main">
            <Header/>
            <div className="main__content">

                {/* 나를 위한 추천 */}
                {isLoggedIn ? (
                    <section className="main__section">
                        <div className="main__section-header">
                            <div className="main__section-title">나를 위한 추천</div>
                            <button
                                className="main__refresh-btn"
                                onClick={() => loadRecommended(true)}
                                disabled={recLoading}
                            >
                                새로고침
                            </button>
                        </div>
                        <div className="main__card-grid">
                            {recommended.map(article => (
                                <NewsCard key={article.article_id} article={article} showSimilarity/>
                            ))}
                        </div>
                        <div className="main__more-wrap">
                            <button
                                className="main__more-btn"
                                onClick={() => loadRecommended(false)}
                                disabled={recLoading}
                            >
                                {recLoading ? '불러오는 중...' : '더 보기'}
                            </button>
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

                {/* 지금 화제 */}
                <section className="main__section">
                    <div className="main__section-title">지금 화제</div>
                    <div className="main__card-grid main__card-grid--3col">
                        {trending.map(article => (
                            <NewsCard key={article.article_id} article={article} showPressCount showDescription/>
                        ))}
                    </div>
                </section>

                {/* 최신 뉴스 */}
                <section className="main__section">
                    <div className="main__section-title">최신 뉴스</div>
                    <div className="main__category-tabs">
                        {CATEGORIES.map(cat => (
                            <button
                                key={cat.id ?? 'all'}
                                className={`main__category-tab ${activeCategory === cat.id ? 'main__category-tab--active' : ''}`}
                                onClick={() => handleCategoryChange(cat.id)}
                            >
                                {cat.name}
                            </button>
                        ))}
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

            <ChatBot isOpen={chatOpen} onClose={() => setChatOpen(false)}/>
            <MyPage isOpen={mypageOpen} onClose={handleMypageClose}/>
        </div>
    )
}