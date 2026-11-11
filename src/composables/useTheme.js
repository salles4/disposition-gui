import { ref, computed } from 'vue'

// Light or dark color scheme, shared by every page and remembered per browser. Light unless the user picked dark.
const STORAGE_KEY = 'ui_theme'

const readTheme = () => {
  try { return localStorage.getItem(STORAGE_KEY) === 'dark' ? 'dark' : 'light' } catch { return 'light' }
}

const theme = ref(readTheme())

export function useTheme() {
  const isLight = computed(() => theme.value === 'light')
  const toggleTheme = () => {
    theme.value = isLight.value ? 'dark' : 'light'
    try { localStorage.setItem(STORAGE_KEY, theme.value) } catch { /* storage unavailable */ }
  }
  return { isLight, toggleTheme }
}
