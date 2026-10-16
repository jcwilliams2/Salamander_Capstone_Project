import { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LabelList } from 'recharts'

const API = 'http://localhost:8000'
const RECENT_PLACEMENT = 'top'

const BAR = '#2a78d6'
const INK = '#0b0b0b'
const INK_2 = '#52514e'
const GRID = '#e6e5e1'

const axisTick = { fill: INK_2, fontSize: 12 }
const hoverCursor = { fill: 'rgba(0, 0, 0, 0.05)' }

function RecentCover({ url, title }) {
    const [failed, setFailed] = useState(false)
    if (!url || failed) {
        return (
            <div style={{ height: '180px', width: '120px', border: `1px solid ${GRID}`, borderRadius: '4px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: INK_2, fontSize: '0.85em' }}>
                No cover
            </div>
        )
    }
    return (
        <img
            src={url}
            alt={title}
            onError={() => setFailed(true)}
            style={{ height: '180px', width: '120px', objectFit: 'cover', borderRadius: '4px', boxShadow: '0 2px 8px rgba(0, 0, 0, 0.18)' }}
        />
    )
}

function RecentReads({ userId }) {
    const [books, setBooks] = useState([])

    useEffect(() => {
        const controller = new AbortController()
        fetch(`${API}/recent-finished/${userId}?limit=3`, { signal: controller.signal })
            .then((res) => {
                if (!res.ok) throw new Error(`Unexpected response (${res.status})`)
                    return res.json()
            })
            .then((data) => setBooks(Array.isArray(data?.books) ? data.books : []))
            .catch((err) => {
                if (err.name === 'AbortError') return
                console.error('Failed to load recent reads', err)
                setBooks([])
            })
        return () => controller.abort()
    }, [userId])

    if (books.length === 0) return null

    return (
        <section style={{ maxWidth: '720px', margin: '24px auto 0', textAlign: 'center' }}>
            <h3 style={{ margin: 0 }}>Recently finished</h3>
            <div style={{ display: 'flex', gap: '28px', justifyContent: 'center', flexWrap: 'wrap', marginTop: '16px' }}>
                {books.map((b) => (
                    <div key={b.id} style={{ width: '140px' }}>
                        <div style={{ display: 'flex', justifyContent: 'center' }}>
                            <RecentCover url={b.cover_url} title={b.title} />
                        </div>
                        <div style={{ marginTop: '8px', fontWeight: 600, color: INK, fontSize: '0.9em' }}>{b.title}</div>
                        <div style={{ color: INK_2, fontSize: '0.85em' }}>{b.author}</div>
                        <div style={{ color: INK_2, fontSize: '0.8em' }}>
                            {new Date(b.finished_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                        </div>
                    </div>
                ))}
            </div>
        </section>
    )
}

function monthName(year, month) {
    return new Date(year, month, 1).toLocaleString('en-US', { month: 'long', year: 'numeric' })
}

function shortMonth(year, month) {
    return new Date(year, month, 1).toLocaleString('en-US', { month: 'short', year: '2-digit' })
}

function yearData(dates) {
    const now = new Date()
    const out = []
    for (let i = 11; i >= 0; i--) {
        const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
        out.push({ y: d.getFullYear(), m: d.getMonth(), label: shortMonth(d.getFullYear(), d.getMonth()), count: 0 })
    }
    dates.forEach((dt) => {
        const row = out.find((r) => r.y === dt.getFullYear() && r.m === dt.getMonth())
        if (row) row.count += 1
    })
    return out
}

function monthData(dates, year, month) {
    const days = new Date(year, month + 1, 0).getDate()
    const out = Array.from({ length: days }, (_, i) => ({ label: String(i + 1), count: 0 }))
    dates.forEach((dt) => {
        if (dt.getFullYear() === year && dt.getMonth() === month) out[dt.getDate() - 1].count += 1
    })
    return out
}

function Tile ({ label, value }) {
    return (
        <div style={{ border: `1px solid ${GRID}`, borderRadius: '8px', padding: '12px 16px', minWidth: '110px' }}>
            <div style={{ fontSize: '1.9em', fontWeight: 600, color: INK }}>{value}</div>
            <div style={{ fontSize: '0.85em', color: INK_2 }}>{label}</div>
        </div>
    )
}

function DataTable({ columns, rows }) {
    return (
        <details style={{ marginTop: '8px', fontSize: '0.85em', color: INK_2 }}>
            <summary style={{ cursor: 'pointer' }}>View as table</summary>
            <table style={{ margin: '8px auto', borderCollapse: 'collapse' }}>
                <thead>
                    <tr>
                        {columns.map((c) => (
                            <th key={c.key} style={{ padding: '4px 12px', textAlign: 'left', borderBottom: `1px solid ${GRID}` }}>{c.label}</th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {rows.map((r, i) => (
                        <tr key={i}>
                            {columns.map((c) => (
                                <td key={c.key} style={{ padding: '4px 12px', textAlign: 'left' }}>{r[c.key]}</td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </details>
    )
}

function ChartSection({ title, subtitle, children }) {
    return (
        <section style={{ maxWidth: '720px', margin: '32px auto 0', textAlign: 'left' }}>
            <h3 style={{ margin: 0 }}>{title}</h3>
            <p style={{ margin: '4px 0 12px', color: INK_2, fontSize: '0.9em' }}>{subtitle}</p>
            {children}
        </section>
    )
}

const smallButton = (active) => ({
    padding: '4px 12px',
    borderRadius: '6px',
    border: `1px solid ${active ? BAR : GRID}`,
    background: active ? BAR : 'transparent',
    color: active ? '#fff' : INK_2,
    cursor: 'pointer',
})

function RangeToggle({ view, onChange }) {
    return (
        <div role="group" aria-label="Time range" style={{ display: 'inline-flex', gap: '4px' }}>
            {[['year', 'Year'], ['month', 'Month']].map(([key, label]) => (
                <button key={key} onClick={() => onChange(key)} aria-pressed={view === key} style={smallButton(view === key)}>
                    {label}
                </button>
            ))}
        </div>
    )
}

function ReadingDashboard({ userId }) {
    const [state, setState] = useState({ loading: true, stats: null, failed: false })
    const [view, setView] = useState('year')
    const [cursor, setCursor] = useState(() => {
        const now = new Date()
        return { y: now.getFullYear(), m: now.getMonth() }
    })

    useEffect(() => {
        const controller = new AbortController()
        fetch(`${API}/reading-stats/${userId}`, { signal: controller.signal })
            .then((res) => {
                if (!res.ok) throw new Error(`Unexpected response (${res.status})`)
                return res.json()
            })
            .then((stats) => setState({ loading: false, stats, failed: false }))
            .catch((err) => {
                if (err.name === 'AbortError') return
                console.error('Failed to load reading stats', err)
                setState({ loading: false, stats: null, failed: true })
            })
        return () => controller.abort()
    }, [userId])

    const { loading, stats, failed } = state

    if (loading) return <p>Loading your reading history...</p>
    if (failed || !stats) return <p style={{ color: 'red' }}>Couldn't load your reading history. Please try again.</p>

    const { status_counts: s, vote_counts: v } = stats
    const genres = stats.genres || []
    const logged = s.finished + s.reading + s.dnf + s.want_to_read

    const dates = (stats.finished_at || []).map((iso) => new Date(iso)).filter((d) => !Number.isNaN(d.getTime()))

    const now = new Date()
    const thisMonthIndex = now.getFullYear() * 12 + now.getMonth()
    const cursorIndex = cursor.y *12 + cursor.m
    const earliest = dates.length ? dates.reduce((a, b) => (a < b ? a : b)) : null
    const earliestIndex = earliest ? earliest.getFullYear() * 12 + earliest.getMonth() : thisMonthIndex
    const canGoBack = cursorIndex > earliestIndex
    const canGoForward = cursorIndex < thisMonthIndex

    function shiftMonth(delta) {
        setCursor(({ y, m }) => {
            const d = new Date(y, m + delta, 1)
            return { y: d.getFullYear(), m: d.getMonth()}
        })
    }

    const isMonthView = view === 'month'
    const chartData = isMonthView ? monthData(dates, cursor.y, cursor.m) : yearData(dates)
    const total = chartData.reduce((sum, r) => sum + r.count, 0)
    const heading = monthName(cursor.y, cursor.m)
    const tableRows = isMonthView
        ? chartData.filter((r) => r.count > 0).map((r) => ({ label: `${new Date(cursor.y, cursor.m, 1).toLocaleString('en-US', { month: 'short' })} ${r.label}`, count: r.count }))
        : chartData

    return (
        <div>
            <h2>Reading History</h2>

            {logged === 0 ? (
                <p>No reading history yet. Set a book's status from Recommendations or the Catalog and your stats will show up here.</p>
            ) : (
                <>
                    {RECENT_PLACEMENT === 'top' && <RecentReads userId={userId} />}
                    <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', flexWrap: 'wrap' }}>
                        <Tile label="Finished" value={s.finished} />
                        <Tile label="Reading" value={s.reading} />
                        <Tile label="Want to Read" value={s.want_to_read} />
                        <Tile label="Did not Finish" value={s.dnf} />
                        <Tile label="Liked" value={v.up} />
                        <Tile label="Disliked" value={v.down} />
                    </div>

                    <ChartSection
                        title="What you read"
                        subtitle="Genres across books you've finished, are reading, or didn't finish."
                    >
                        {genres.length === 0 ? (
                            <p>No genre data yet.</p>
                        ) : (
                            <>
                                <ResponsiveContainer width="100%" height={Math.max(160, genres.length * 36)}>
                                    <BarChart data={genres} layout="vertical" margin={{ top: 4, right: 32, bottom: 4, left: 8 }}>
                                        <XAxis type="number" hide />
                                        <YAxis type="category" dataKey="genre" width={120} tick={{ fill: INK_2, fontSize: 13 }} axisLine={false} tickLine={false} />
                                        <Tooltip cursor={hoverCursor} formatter={(value) => [value, 'Books']} />
                                        <Bar dataKey="count" fill={BAR} radius={[0, 4, 4, 0]} barSize={16} isAnimationActive={false}>
                                            <LabelList dataKey="count" position="right" style={{ fill: INK_2, fontSize: 12 }} />
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                                <DataTable
                                    columns={[{ key: 'genre', label: 'Genre' }, { key: 'count', label: 'Books' }]}
                                    rows={genres}
                                />
                            </>
                        )}
                    </ChartSection>

                    <ChartSection
                        title="Books finished over time"
                        subtitle={isMonthView
                            ? `${total} finished in ${heading}, by day.`
                            : `${total} finished in the last 12 months, by month.`}
                    >
                        <div style={{ display: 'flex', flexWrap: 'wrap', marginBottom: '8px', alignItems: 'center', gap: '8px' }}>
                            <RangeToggle view={view} onChange={setView} />
                            {isMonthView && (
                                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                                    <button onClick={() => shiftMonth(-1)} disabled={!canGoBack} aria-label="Previous month" style={{ ...smallButton(false), opacity: canGoBack ? 1 : 0.4, cursor: canGoBack ? 'pointer' : 'default' }}>‹</button>
                                    <span style={{ minWidth: '130px', textAlign: 'center', color: INK }}>{heading}</span>
                                    <button onClick={() => shiftMonth(1)} disabled={!canGoForward} aria-label="Next month" style={{ ...smallButton(false), opacity: canGoForward ? 1 : 0.4, cursor: canGoForward ? 'pointer' : 'default' }}>›</button>
                                </div>
                            )}
                        </div>

                        <ResponsiveContainer width="100%" height={240}>
                            <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 4, left: 0 }}>
                                <CartesianGrid vertical={false} stroke={GRID} />
                                <XAxis dataKey="label" interval={0} tick={axisTick} axisLine={false} tickLine={false} />
                                <YAxis allowDecimals={false} domain={[0, (max) => Math.max(max, 1)]} tick={axisTick} axisLine={false} tickLine={false} width={28} />
                                <Tooltip
                                    cursor={hoverCursor}
                                    formatter={(value) => [value, 'Finished']}
                                    labelFormatter={(label) => (isMonthView ? `${new Date(cursor.y, cursor.m, 1).toLocaleString('en-US', { month: 'short' })} ${label}` : label)}
                                />
                                <Bar dataKey="count" fill={BAR} radius={[4, 4, 0, 0]} maxBarSize={28} isAnimationActive={false} />
                            </BarChart>
                        </ResponsiveContainer>
                        {total === 0 && <p style={{ color: INK_2, fontSize: '0.9em' }}>No books finished in this period.</p>}
                        <DataTable
                            columns={[{ key: 'label', label: isMonthView ? 'Day' : 'Month' }, { key: 'count', label: 'Finished' }]}
                            rows={tableRows}
                        />
                    </ChartSection>
                    {RECENT_PLACEMENT === 'bottom' && <RecentReads userId={userId} />}
                </>
            )}
        </div>
    )
}

export default ReadingDashboard