#!/usr/bin/env node
const fs = require('fs')
const path = require('path')

const root = path.resolve(__dirname, '..')
const localesDir = path.join(root, 'locales')
const base = JSON.parse(fs.readFileSync(path.join(localesDir, 'en.json'), 'utf8'))
const de = JSON.parse(fs.readFileSync(path.join(localesDir, 'de.json'), 'utf8'))

function collectKeys(obj, prefix = '') {
  const keys = []
  if (Array.isArray(obj)) {
    obj.forEach((value, index) => {
      const key = `${prefix}[${index}]`
      if (value && typeof value === 'object') keys.push(...collectKeys(value, key))
      else keys.push(key)
    })
    return keys
  }
  if (obj && typeof obj === 'object') {
    Object.keys(obj).forEach((name) => {
      const key = prefix ? `${prefix}.${name}` : name
      const value = obj[name]
      if (value && typeof value === 'object') keys.push(...collectKeys(value, key))
      else keys.push(key)
    })
    return keys
  }
  return [prefix]
}

const enKeys = collectKeys(base).sort()
const deKeys = collectKeys(de).sort()
const missing = enKeys.filter((key) => !deKeys.includes(key))
const extra = deKeys.filter((key) => !enKeys.includes(key))

if (missing.length || extra.length) {
  if (missing.length) console.error('Missing German locale keys:\n' + missing.join('\n'))
  if (extra.length) console.error('Extra German locale keys:\n' + extra.join('\n'))
  process.exit(1)
}

console.log(`Locale validation passed: ${enKeys.length} keys`)
