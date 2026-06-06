// TODO: 백엔드 구성 후 주석 해제
// import axios from 'axios'
// const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
// const api = axios.create({ baseURL: BASE_URL })
// api.interceptors.request.use(config => {
//   const token = localStorage.getItem('token')
//   if (token) config.headers.Authorization = `Bearer ${token}`
//   return config
// })

const DUMMY_RECOMMENDED = [
  {
    article_id: 1,
    category_name: '경제',
    title: '삼성전자 3분기 영업이익 10조 돌파',
    source_name: '매일경제',
    published_ago: '1시간 전',
    similarity: 0.92,
    url: '#'
  },
  {
    article_id: 2,
    category_name: '경제',
    title: '한국은행 기준금리 동결 결정',
    source_name: '연합뉴스',
    published_ago: '2시간 전',
    similarity: 0.88,
    url: '#'
  },
  {
    article_id: 3,
    category_name: '경제',
    title: '코스피 2600선 회복 시도',
    source_name: '한국경제',
    published_ago: '3시간 전',
    similarity: 0.81,
    url: '#'
  },
]

const DUMMY_TRENDING = [
  {
    article_id: 4,
    category_name: '정치',
    title: '국회 예산안 처리 논의 본격화',
    source_name: '연합뉴스',
    published_ago: '30분 전',
    press_count: 6,
    url: '#'
  },
  {
    article_id: 5,
    category_name: '사회',
    title: '수도권 폭우 피해 복구 작업 진행',
    source_name: '매일경제',
    published_ago: '1시간 전',
    press_count: 4,
    url: '#'
  },
  {
    article_id: 6,
    category_name: '사회',
    title: '대학병원 응급실 과부하 심화',
    source_name: 'SBS',
    published_ago: '2시간 전',
    press_count: 3,
    url: '#'
  },
]

const DUMMY_LATEST = [
  { article_id: 7,  category_name: '정치', title: '대통령실 국정 운영 방향 발표', source_name: '연합뉴스', published_ago: '4분 전', url: '#' },
  { article_id: 8,  category_name: '경제', title: '원달러 환율 1350원대 진입', source_name: '한국경제', published_ago: '7분 전', url: '#' },
  { article_id: 9,  category_name: '사회', title: '전국 폭염 경보 확대 발령', source_name: 'SBS', published_ago: '11분 전', url: '#' },
  { article_id: 10, category_name: '정치', title: '여야 원내대표 회동 결과 발표', source_name: '경향신문', published_ago: '15분 전', url: '#' },
  { article_id: 11, category_name: '경제', title: 'SK하이닉스 신규 투자 계획 공개', source_name: '매일경제', published_ago: '22분 전', url: '#' },
  { article_id: 12, category_name: '사회', title: '서울 지하철 운행 정상화', source_name: '연합뉴스', published_ago: '35분 전', url: '#' },
]

export const getRecommendedFeed = async () => {
  return DUMMY_RECOMMENDED
}

export const getTrendingFeed = async () => {
  return DUMMY_TRENDING
}

export const getLatestFeed = async (page = 1, limit = 20) => {
  if (page > 1) return []
  return DUMMY_LATEST
}