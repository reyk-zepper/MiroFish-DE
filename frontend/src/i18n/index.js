import { createI18n } from 'vue-i18n'
import languages from '../../../locales/languages.json'

const localeFiles = import.meta.glob('../../../locales/!(languages).json', { eager: true })

const messages = {}
const availableLocales = []

for (const path in localeFiles) {
  const key = path.match(/\/([^/]+)\.json$/)[1]
  if (languages[key]) {
    messages[key] = localeFiles[path].default
    availableLocales.push({ key, label: languages[key].label })
  }
}

const browserLocale = navigator.language?.split('-')?.[0]
const defaultLocale = availableLocales.some(locale => locale.key === browserLocale) ? browserLocale : 'de'
const savedLocale = localStorage.getItem('locale') || defaultLocale

const i18n = createI18n({
  legacy: false,
  locale: savedLocale,
  fallbackLocale: 'de',
  messages
})

export { availableLocales }
export default i18n
