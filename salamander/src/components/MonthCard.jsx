import { API } from '../lib/api'
import { useEffect, useRef, useState } from 'react'


const W = 1080
const H = 1350
const FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'

function toRgb(color) {
    const probe = document.createElement('canvas')
    probe.width = 1
    probe.height = 1
    const ctx = probe.getContext('2d', { willReadFrequently: true })
    ctx.fillStyle = '#000000'
    ctx.fillStyle = color
    ctx.fillRect(0, 0, 1, 1)
    const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data
    return [r, g, b]
}

function pickSlices(candidates, bg) {
    const picked = []
    candidates.forEach((color) => {
        if (!color) return
        const rgb = toRgb(color)
        const distance = (p) => Math.hypot(p.rgb[0] - rgb[0], p.rgb[1] - rgb[1], p.rgb[2] - rgb[2])
        if (picked.every((p) => distance(p) >= 12)) picked.push({ color, rgb })
    })
    const base = picked.length
    const bgRgb = toRgb(bg)
    for (let i = 0; picked.length < 5; i++) {
        const mixed = picked[i % base].rgb.map((v, k) => Math.round(v * 0.5 + bgRgb[k] * 0.5))
        picked.push({ color: `rgb(${mixed.join(', ')})`, rgb: mixed })
    }
    return picked.slice(0, 5).map((p) => p.color)
}

function readTheme() {
    const style = getComputedStyle(document.body)
    const get = (name, fallback) => style.getPropertyValue(name).trim() || fallback
    const bg = get('--bg', '#16302b')
    return {
        bg,
        surface: get('--surface', '#1f433b'),
        surfaceAlt: get('--surface-alt', '#2a5248'),
        text: get('--text', '#f4efe4'),
        muted: get('--text-muted', '#a9c2b8'),
        primary: get('--primary', '#e8b04a'),
        onPrimary: get('--text-on-primary', '#16302b'),
        shadow: get('--shadow', 'rgba(0, 0, 0, 0.35)'),
        slices: pickSlices([
            get('--primary', '#e8b04a'), get('--status-want', '#9b7fd1'), get('--status-finished', '#5fae7a'),
            get('--warning', '#d6a14a'), get('--status-dnf', '#d96a5a'), get('--status-reading', '#4cc0cc'),
            get('--danger', '#d96a5a'), get('--text', '#f4efe4'),
        ], bg),
    }
}

function localDay() {
    const d = new Date()
    const pad = (n) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function loadImage(url) {
    return new Promise((resolve) => {
        if (!url) return resolve(null)
        const img = new Image()
        img.crossOrigin = 'anonymous'
        img.onload = () => resolve(img)
        img.onerror = () => resolve(null)
        img.src = url
    })
}

function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath()
    ctx.moveTo(x + r, y)
    ctx.arcTo(x + w, y, x + w, y + h, r)
    ctx.arcTo(x + w, y + h, x, y + h, r)
    ctx.arcTo(x, y + h, x, y, r)
    ctx.arcTo(x, y, x + w, y, r)
    ctx.closePath()
}

function fitText(ctx, text, maxWidth) {
    if (ctx.measureText(text).width <= maxWidth) return text
    let t = text
    while (t.length > 1 && ctx.measureText(t + '…').width > maxWidth) t = t.slice(0, -1)
    return t + '…'
}

function timeText(t) {
    if (!t || t.average_days === null) return 'Not enough dates yet'
    if (t.average_days < 1) return 'Under a day'
    return `${t.average_days} days`
}

function paintBase(ctx, t, data, bandH, subtitle) {
    ctx.fillStyle = t.bg
    ctx.fillRect(0, 0, W, H)
    ctx.fillStyle = t.primary
    ctx.fillRect(0, 0, W, bandH)
    ctx.fillStyle = t.surfaceAlt
    ctx.fillRect(0, bandH, W, 10)
    ctx.textBaseline = 'alphabetic'
    ctx.textAlign = 'left'

    ctx.fillStyle = t.onPrimary
    ctx.globalAlpha = 0.8
    ctx.font = `600 34px ${FONT}`
    ctx.fillText('MONTH IN BOOKS', 80, 110)
    ctx.globalAlpha = 1
    ctx.font = `700 84px ${FONT}`
    ctx.fillText(data.label, 80, 205)
    if (subtitle) {
        ctx.globalAlpha = 0.85
        ctx.font = `italic 500 44px ${FONT}`
        ctx.fillText(subtitle, 80, 265)
        ctx.globalAlpha = 1
    }
}

function paintFooter(ctx, t) {
    ctx.fillStyle = t.muted
    ctx.font = `600 30px ${FONT}`
    ctx.textAlign = 'right'
    ctx.fillText('Salamander', W - 80, H - 36)
    ctx.textAlign = 'left'
}

function drawTitleTile(ctx, t, x, y, w, h, title, fontSize) {
    ctx.fillStyle = t.surfaceAlt
    ctx.fillRect(x, y, w, h)
    ctx.fillStyle = t.text
    ctx.font = `600 ${fontSize}px ${FONT}`
    ctx.textAlign = 'center'
    let line = ''
    let ly = y + h * 0.35
    ;(title || 'Untitled').split(' ').forEach((word) => {
        const test = line ? `${line} ${word}` : word
        if (ctx.measureText(test).width > w - 16 && line) {
            ctx.fillText(line, x + w / 2, ly)
            line = word
            ly += fontSize * 1.3
        } else {
            line = test
        }
    })
    if (ly < y + h - 8) ctx.fillText(line, x + w / 2, ly)
    ctx.textAlign = 'left'
}

function paintCover(ctx, t, img, book, x, y, w, h, radius, tileFont) {
    ctx.save()
    ctx.shadowColor = t.shadow
    ctx.shadowBlur = 18
    ctx.shadowOffsetY = 6
    ctx.fillStyle = t.surface
    roundRect(ctx, x, y, w, h, radius)
    ctx.fill()
    ctx.restore()
    ctx.save()
    roundRect(ctx, x, y, w, h, radius)
    ctx.clip()
    if (img) ctx.drawImage(img, x, y, w, h)
    else drawTitleTile(ctx, t, x, y, w, h, book.title, tileFont)
    ctx.restore()
}

function sliceFill(ctx, t, slice, i) {
    if (slice.genre === 'Other') {
        ctx.fillStyle = t.muted
        ctx.globalAlpha = 0.6
    } else {
        ctx.fillStyle = t.slices[i % t.slices.length]
        ctx.globalAlpha = 1
    }
}

function draw(canvas, data, images) {
    const ctx = canvas.getContext('2d')
    const t = readTheme()
    paintBase(ctx, t, data, 250, null)

    ctx.fillStyle = t.primary
    ctx.font = `800 260px ${FONT}`
    ctx.fillText(String(data.finished), 80, 505)
    const numberWidth = ctx.measureText(String(data.finished)).width
    ctx.fillStyle = t.muted
    ctx.font = `500 56px ${FONT}`
    ctx.fillText(data.finished === 1 ? 'book finished' : 'books finished', 80 + numberWidth + 30, 505)

    ctx.fillStyle = t.muted
    ctx.font = `600 30px ${FONT}`
    ctx.fillText('TOP GENRES', 80, 600)
    let x = 80
    ctx.font = `600 38px ${FONT}`
    if (data.top_genres.length === 0) {
        ctx.fillStyle = t.muted
        ctx.fillText('No genres recorded', 80, 670)
    }
    data.top_genres.forEach((g) => {
        const label = fitText(ctx, g.genre, 400)
        const w = ctx.measureText(label).width + 56
        if (x + w > W - 80) return
        ctx.fillStyle = t.surfaceAlt
        roundRect(ctx, x, 630, w, 70, 35)
        ctx.fill()
        ctx.fillStyle = t.text
        ctx.fillText(label, x + 28, 677)
        x += w + 20
    })

    ctx.fillStyle = t.muted
    ctx.font = `600 30px ${FONT}`
    ctx.fillText('AVERAGE TIME TO FINISH', 80, 790)
    ctx.fillStyle = t.text
    ctx.font = `700 56px ${FONT}`
    ctx.fillText(timeText(data.time_to_finish), 80, 855)

    const coverW = 220
    const coverH = 330
    const gap = (W - 160 - coverW * 4) / 3
    data.books.forEach((b, i) => {
        paintCover(ctx, t, images[i], b, 80 + i * (coverW + gap), 930, coverW, coverH, 14, 26)
    })

    paintFooter(ctx, t)
}

function drawCovers(canvas, data, images) {
    const ctx = canvas.getContext('2d')
    const t = readTheme()
    paintBase(ctx, t, data, 300, `${data.finished} ${data.finished === 1 ? 'book' : 'books'} finished`)

    const areaX = 80
    const areaY = 350
    const areaW = W - 160
    const areaH = H - areaY - 110
    const gap = 20
    const n = data.covers.length

    let best = { cols: 1, w: 0 }
    for (let cols = 1; cols <= n; cols++) {
        const rows = Math.ceil(n / cols)
        const w = Math.min((areaW - gap * (cols - 1)) / cols, (areaH - gap * (rows - 1)) / rows / 1.5, 320)
        if (w > best.w) best = { cols, w }
    }
    const { cols, w } = best
    const h = w * 1.5
    const rows = Math.ceil(n / cols)
    const startX = areaX + (areaW - (cols * w + gap * (cols - 1))) / 2
    const startY = areaY + (areaH - (rows * h + gap * (rows - 1))) / 2

    data.covers.forEach((b, i) => {
        const x = startX + (i % cols) * (w + gap)
        const y = startY + Math.floor(i / cols) * (h + gap)
        paintCover(ctx, t, images[i], b, x, y, w, h, Math.max(6, w * 0.06), Math.max(14, w / 9))
    })

    if (data.finished > n) {
        ctx.fillStyle = t.muted
        ctx.font = `600 30px ${FONT}`
        ctx.fillText(`+${data.finished - n} more`, 80, H - 36)
    }
    paintFooter(ctx, t)
}

function drawWrapup(canvas, data, images) {
    const ctx = canvas.getContext('2d')
    const t = readTheme()
    paintBase(ctx, t, data, 300, 'reading wrap-up')

    ctx.fillStyle = t.muted
    ctx.font = `600 28px ${FONT}`
    ctx.fillText('BOOKS READ', 80, 355)
    const gap = 24
    const coverW = (W - 160 - gap * 3) / 4
    const coverH = coverW * 1.5
    const coverY = 375
    data.books.forEach((b, i) => {
        const x = 80 + i * (coverW + gap)
        paintCover(ctx, t, images[i], b, x, coverY, coverW, coverH, 12, 24)
        ctx.textAlign = 'center'
        ctx.font = `600 26px ${FONT}`
        ctx.fillStyle = t.muted
        if (b.genre) ctx.fillText(fitText(ctx, b.genre, coverW), x + coverW / 2, coverY + coverH + 40)
        if (b.liked) {
            ctx.fillStyle = t.primary
            ctx.fillText('♥ liked', x + coverW / 2, coverY + coverH + 78)
        }
        ctx.textAlign = 'left'
    })

    let nextY = 845
    const gp = data.goal_progress
    if (gp) {
        ctx.fillStyle = t.muted
        ctx.font = `600 28px ${FONT}`
        ctx.fillText(`READING GOAL PROGRESS (${gp.year})`, 80, nextY)
        const barY = nextY + 22
        const barH = 56
        const barW = W - 160
        ctx.save()
        roundRect(ctx, 80, barY, barW, barH, barH / 2)
        ctx.clip()
        ctx.fillStyle = t.surfaceAlt
        ctx.fillRect(80, barY, barW, barH)
        if (gp.percent > 0) {
            ctx.fillStyle = t.primary
            ctx.fillRect(80, barY, Math.max(barH, (barW * gp.percent) / 100), barH)
        }
        ctx.restore()
        ctx.fillStyle = t.text
        ctx.font = `600 32px ${FONT}`
        ctx.fillText(`${gp.finished} of ${gp.goal} books`, 80, barY + barH + 44)
        ctx.fillStyle = t.muted
        ctx.textAlign = 'right'
        ctx.fillText(`${gp.percent}%`, W - 80, barY + barH + 44)
        ctx.textAlign = 'left'
        nextY = barY + barH + 44 + 58
    }

    ctx.fillStyle = t.muted
    ctx.font = `600 28px ${FONT}`
    ctx.fillText('GENRE BREAKDOWN', 80, nextY)
    const mix = data.genre_mix || []
    const total = mix.reduce((sum, s) => sum + s.count, 0)
    const top = nextY + 25
    const avail = H - 80 - top
    const outer = Math.min(130, avail / 2)
    const inner = outer * 0.6
    const cx = 80 + outer
    const cy = top + outer + 5
    if (total === 0) {
        ctx.fillStyle = t.muted
        ctx.font = `500 32px ${FONT}`
        ctx.fillText('No genres recorded', 80, top + 50)
    } else {
        let angle = -Math.PI / 2
        mix.forEach((s, i) => {
            const sweep = (s.count / total) * Math.PI * 2
            ctx.beginPath()
            ctx.arc(cx, cy, outer, angle, angle + sweep)
            ctx.arc(cx, cy, inner, angle + sweep, angle, true)
            ctx.closePath()
            sliceFill(ctx, t, s, i)
            ctx.fill()
            ctx.globalAlpha = 1
            ctx.strokeStyle = t.bg
            ctx.lineWidth = 4
            ctx.stroke()
            angle += sweep
        })
        const rowH = Math.min(48, (outer * 2) / mix.length)
        const legendX = 80 + outer * 2 + 60
        mix.forEach((s, i) => {
            const y = cy - (mix.length * rowH) / 2 + rowH * (i + 0.7)
            sliceFill(ctx, t, s, i)
            roundRect(ctx, legendX, y - 22, 24, 24, 5)
            ctx.fill()
            ctx.globalAlpha = 1
            ctx.fillStyle = t.text
            ctx.font = `600 28px ${FONT}`
            ctx.fillText(fitText(ctx, s.genre, 380), legendX + 40, y)
            ctx.fillStyle = t.muted
            ctx.textAlign = 'right'
            ctx.fillText(`${s.percent}%`, W - 80, y)
            ctx.textAlign = 'left'
        })
    }
    paintFooter(ctx, t)
}

const VIEWS = [
    { key: 'summary', label: 'Summary', download: 'Download summary card', suffix: '' },
    { key: 'covers', label: 'All covers', download: 'Download covers card', suffix: '-covers' },
    { key: 'wrapup', label: 'Wrap-up', download: 'Download wrap-up card', suffix: '-wrapup' },
]

const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

function monthOptions(range, year) {
    const lo = year === range.from.year ? range.from.month : 1
    const hi = year === range.to.year ? range.to.month : 12
    const out = []
    for (let m = lo; m <= hi; m++) out.push(m)
    return out
}

export default function MonthCard({ userId, refreshKey = 0 }) {
    const canvasRef = useRef(null)
    const [data, setData] = useState(null)
    const [choice, setChoice] = useState(null)
    const [failed, setFailed] = useState(false)
    const [exportError, setExportError] = useState(false)
    const [view, setView] = useState('summary')
    const [themeTick, setThemeTick] = useState(0)

    useEffect(() => {
        let cancelled = false
        const params = new URLSearchParams({ today: localDay(), tz_offset: String(new Date().getTimezoneOffset()) })
        if (choice) {
            params.set('year', String(choice.year))
            params.set('month', String(choice.month))
        }
        fetch(`${API}/monthly-summary/${userId}?${params}`)
            .then((res) => {
                if (!res.ok) throw new Error('bad response')
                return res.json()
            })
            .then((json) => {
                if (!cancelled) {
                    setData(json)
                    setFailed(false)
                }
            })
            .catch(() => {
                if (!cancelled) setFailed(true)
            })
        return () => {
            cancelled = true
        }
    }, [userId, refreshKey, choice])

    useEffect(() => {
        const observer = new MutationObserver(() => setThemeTick((n) => n + 1))
        observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'style'] })
        return () => observer.disconnect()
    }, [])

    useEffect(() => {
        if (!data || data.finished === 0 || !canvasRef.current) return
        let cancelled = false
        const list = view === 'covers' ? data.covers : data.books
        Promise.all(list.map((b) => loadImage(b.cover_url))).then((images) => {
            if (cancelled || !canvasRef.current) return
            if (view === 'covers') drawCovers(canvasRef.current, data, images)
            else if (view === 'wrapup') drawWrapup(canvasRef.current, data, images)
            else draw(canvasRef.current, data, images)
        })
        return () => {
            cancelled = true
        }
    }, [data, view, themeTick])

    function pickYear(year) {
        const options = monthOptions(data.range, year)
        const month = Math.min(Math.max(data.month, options[0]), options[options.length - 1])
        setChoice({ year, month })
    }

    function pickMonth(month) {
        setChoice({ year: data.year, month })
    }

    function download() {
        setExportError(false)
        canvasRef.current.toBlob((blob) => {
            if (!blob) {
                setExportError(true)
                return
            }
            const url = URL.createObjectURL(blob)
            const link = document.createElement('a')
            link.href = url
            link.download = `month-in-books${VIEWS.find((v) => v.key === view).suffix}-${data.year}-${String(data.month).padStart(2, '0')}.png`
            link.click()
            URL.revokeObjectURL(url)
        }, 'image/png')
    }

    const card = {
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: '12px',
        padding: '1rem 1.25rem',
        marginBottom: '1rem',
    }

    const selectStyle = {
        padding: '4px 8px',
        borderRadius: '6px',
        border: '1px solid var(--border)',
        background: 'var(--surface)',
        color: 'var(--text)',
    }

    const toggle = (active) => ({
        padding: '4px 12px',
        borderRadius: '6px',
        border: `1px solid ${active ? 'var(--primary)' : 'var(--border)'}`,
        background: active ? 'var(--primary)' : 'transparent',
        color: active ? 'var(--text-on-primary)' : 'var(--text-muted)',
        cursor: 'pointer',
    })

    if (failed) return <div style={card}><p style={{ margin: 0 }}>Couldn't load your monthly summary.</p></div>
    if (!data) return <div style={card}><p style={{ margin: 0 }}>Loading your monthly summary...</p></div>

    const years = []
    for (let y = data.range.to.year; y >= data.range.from.year; y--) years.push(y)
    const countFor = (y, m) => (data.months.find((r) => r.year === y && r.month === m) || { count: 0 }).count
    const current = VIEWS.find((v) => v.key === view)

    return (
        <div style={card}>
            <h2 style={{ marginTop: 0 }}>Month in Books</h2>
            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
                <label>
                    Month{' '}
                    <select value={data.month} onChange={(e) => pickMonth(Number(e.target.value))} style={selectStyle}>
                        {monthOptions(data.range, data.year).map((m) => (
                            <option key={m} value={m}>{MONTH_NAMES[m - 1]} ({countFor(data.year, m)})</option>
                        ))}
                    </select>
                </label>
                <label>
                    Year{' '}
                    <select value={data.year} onChange={(e) => pickYear(Number(e.target.value))} style={selectStyle}>
                        {years.map((y) => <option key={y} value={y}>{y}</option>)}
                    </select>
                </label>
            </div>
            {data.finished === 0 ? (
                <p style={{ margin: 0 }}>
                    No finished books in {data.label} yet. Pick another month above, or mark a book as finished to build this month's card.
                </p>
            ) : (
                <>
                    <div role="group" aria-label="Card style" style={{ display: 'flex', gap: '4px', marginBottom: '0.75rem' }}>
                        {VIEWS.map((v) => (
                            <button key={v.key} type="button" onClick={() => setView(v.key)} aria-pressed={view === v.key} style={toggle(view === v.key)}>
                                {v.label}
                            </button>
                        ))}
                    </div>
                    <canvas
                        ref={canvasRef}
                        width={W}
                        height={H}
                        role="img"
                        aria-label={`Month in Books ${current.label.toLowerCase()} card for ${data.label}: ${data.finished} books finished`}
                        style={{ width: '100%', maxWidth: '360px', height: 'auto', borderRadius: '8px', display: 'block', margin: '0 auto' }}
                    />
                    <button type="button" onClick={download} style={{ marginTop: '0.75rem' }}>
                        {current.download}
                    </button>
                    {exportError && <p>Couldn't create the image. Please try again.</p>}
                </>
            )}
        </div>
    )
}