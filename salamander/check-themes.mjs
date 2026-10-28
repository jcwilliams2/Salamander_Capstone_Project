import { THEMES } from './src/theme/themes.js'

const lum = (hex) => {
  const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map(c => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}
const ratio = (a, b) => {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

// [foreground token, background token, minimum ratio]
const PAIRS = [
  ['text', 'bg', 4.5], ['text', 'surface', 4.5], ['text', 'surfaceAlt', 4.5], ['text', 'inputBg', 4.5],
  ['textMuted', 'bg', 4.5], ['textMuted', 'surface', 4.5],
  ['textOnPrimary', 'primary', 4.5], ['textOnPrimary', 'primaryHover', 4.5],
  ['link', 'bg', 4.5], ['link', 'surface', 4.5],
  ['success', 'bg', 4.5], ['warning', 'bg', 4.5], ['danger', 'bg', 4.5],
  ['statusWant', 'surface', 4.5], ['statusReading', 'surface', 4.5],
  ['statusFinished', 'surface', 4.5], ['statusDnf', 'surface', 4.5],
  ['focusRing', 'bg', 3], ['primary', 'bg', 3], ['textMuted', 'inputBg', 4.5],
]

const names = Object.keys(THEMES)
const reference = new Set(Object.keys(THEMES[names[0]].colors))
let failures = 0

for (const name of names) {
  const { colors, mode } = THEMES[name]
  const keys = new Set(Object.keys(colors))
  const missing = [...reference].filter(k => !keys.has(k))
  const extra = [...keys].filter(k => !reference.has(k))
  const problems = []
  if (missing.length) problems.push('missing: ' + missing.join(', '))
  if (extra.length) problems.push('extra: ' + extra.join(', '))
  if (!['light', 'dark'].includes(mode)) problems.push('mode must be light or dark')
  for (const [fg, bg, min] of PAIRS) {
    if (!colors[fg] || !colors[bg]) continue
    const r = ratio(colors[fg], colors[bg])
    if (r < min) problems.push(`${fg} on ${bg} = ${r.toFixed(2)} (needs ${min})`)
  }
  console.log(` ${name}: ${problems.length ? 'FAIL' : 'OK'}`)
  problems.forEach(p => console.log('    - ' + p))
  if (problems.length) failures++
}
console.log(`\n${failures === 0 ? 'PASS' : 'FAIL'}: ${failures} of ${names.length} themes have problems`)
process.exit(failures ? 1 : 0)