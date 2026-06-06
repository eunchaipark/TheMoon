// TODO: 백엔드 구성 후 실제 API로 교체

export const sendMessage = async (question) => {
  // 더미 챗봇 응답
  return {
    answer: `"${question}"에 대한 답변입니다. 백엔드 연결 후 실제 뉴스 기반 답변이 제공됩니다.`,
    sources: [
      { source_name: '연합뉴스' },
      { source_name: '매일경제' }
    ]
  }
}