// TODO: 백엔드 구성 후 실제 API로 교체

export const getCategoryPrefs = async () => {
  return [
    { category_id: 1, weight: 5 },
    { category_id: 2, weight: 5 },
    { category_id: 3, weight: 5 },
  ]
}

export const updateCategoryPrefs = async (prefs) => {
  return { success: true }
}