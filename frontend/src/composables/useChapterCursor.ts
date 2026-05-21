import { ref } from 'vue'

// A2: 统一章节游标。chapterNum 是主游标，setCursor 把 humanizer 范围一起拉到同一章，
// 避免「在 ChapterStep 选第 5 章，但 HumanizerStep 还停留在 1-1」这种多源不同步。
// outlineBatchStart 不在 setCursor 里联动 —— 它是「下一个尚未生成的细纲批次起点」，
// 跟阅读/编辑哪一章是两件事。
export function useChapterCursor() {
  const chapterNum = ref(1)
  const savedChapterNum = ref<number | null>(null)
  const outlineBatchStart = ref(1)
  const humanizerStart = ref(1)
  const humanizerEnd = ref(1)

  function setCursor(num: number) {
    if (!num || num < 1) return
    chapterNum.value = num
    if (humanizerStart.value > num || humanizerEnd.value < num) {
      humanizerStart.value = num
      humanizerEnd.value = num
    }
  }

  return { chapterNum, savedChapterNum, outlineBatchStart, humanizerStart, humanizerEnd, setCursor }
}
