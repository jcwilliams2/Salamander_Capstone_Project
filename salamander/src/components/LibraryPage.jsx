import { useEffect, useState } from 'react'

const API = 'http://localhost:8000'

const SORTS = [
    { key: 'status', label: 'Status' },
    { key: 'year_newest', label: 'Newest added' },
    { key: 'year_oldest', label: 'Oldest added' },
]

const STATUS = {
    reading: { label: 'Reading', color: 'var(--status-reading)' },
    want_to_read: { label: 'Want to Read', color: 'var(--status-want)' },
    finished: { label: 'Finished', color: 'var(--status-finished)' },
    dnf: { label: 'Did not finish', color: 'var(--status-dnf)' },
}

function yearAdded(ts) {
    if (!ts) return null
    const d = new Date(ts)
    return Number.isNaN(d.getTime()) ? null : d.getFullYear()
}

function groupBooks(books, sort) {
    const groups = []
    for (const b of books) {
        const label = sort === 'status'
            ? (STATUS[b.status]?.label || 'Other')
            : String(yearAdded(b.added_at) ?? 'Unknown date')
        const last = groups[groups.length - 1]
        if (last && last.label === label) last.books.push(b)
        else groups.push({ label, books: [b] })
    }
    return groups
}

function Cover({ url, title}) {
    const [failed, setFailed] = useState(false)
    const box = { height: 135, width: 90, flexShrink: 0, borderRadius: 4}
    if (!url || failed) {
        return (
            <div style={{ ...box, border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '0.8em', textAlign: 'center' }}>
                No cover
            </div>
        )
    }
    return (
        <img src={url} alt={title} onError={() => setFailed(true)}
            style={{ ...box, objectFit: 'cover', boxShadow: '0 2px 8px var(--shadow)' }} />
    )
}

function LibraryCard({ book }) {
    const status = STATUS[book.status] || { label: book.status, color: 'var(--border)' }
    const year = yearAdded(book.added_at)

    return (
        <article style={{ display: 'flex', gap: 14, padding: 12, background: 'var(--surface)', border: '1px solid var(--border)', borderLeft: `5px solid ${status.color}`, borderRadius: 10, textAlign: 'left' }}>
            <Cover url={book.cover_url} title={book.title} />
            <div style={{ minWidth: 0 }}>
                <div style={{ fontWeight: 600 }}>{book.title}</div>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.9em' }}>{book.author}</div>
                <div style={{ marginTop: 10, fontWeight: 600, color: status.color }}>{status.label}</div>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.85em' }}>
                    {year ? `Added ${year}` : 'Added date unknown'}
                </div>
            </div>
        </article>
    )
}

const headingButton = {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: 0,
    border: 'none',
    background: 'transparent',
    boxShadow: 'none',
    font: 'inherit',
    color: 'inherit',
    textAlign: 'left',
    cursor: 'pointer',
}

const sortButton = (active) => ({
    padding: '4px 12px',
    borderRadius: 6,
    border: `1px solid ${active ? 'var(--primary)' : 'var(--border)'}`,
    background: active ? 'var(--primary)' : 'transparent',
    color: active ? 'var(--text-on-primary)' : 'var(--text-muted)',
    cursor: 'pointer',
})

export default function LibraryPage({ userId }) {
    const [sort, setSort] = useState('status')
    const [data, setData] = useState(null)
    const [failed, setFailed] = useState(false)
    const [collapsed, setCollapsed] = useState(() => new Set())

    useEffect(() => {
        const controller = new AbortController()
        fetch(`${API}/library/${userId}?sort=${sort}`, { signal: controller.signal })
            .then((res) => {
                if (!res.ok) throw new Error (`Unexpected response (${res.status})`)
                return res.json()
            })
            .then((json) => { setData(json); setFailed(false) })
            .catch((err) => {
                if (err.name === 'AbortError') return
                console.error('Failed to load library', err)
                setFailed(true)
            })
        return () => controller.abort()
    }, [userId, sort])

    if (failed) return <p style={{ color: 'var(--danger)' }}>Couldn't load your library. Please try again.</p>
    if (!data) return <p>Loading your library...</p>

    const groups = groupBooks(data.books, data.sort)

    function toggleGroup(label) {
        setCollapsed((prev) => {
            const next = new Set(prev)
            if (next.has(label)) next.delete(label)
            else next.add(label)
            return next
        })
    }

    return (
        <div style={{ maxWidth: 1240, margin: '0 auto' }}>
            <h2>Library</h2>
            <p style={{ color: 'var(--text-muted)', margin: '0 0 16px' }}>
                {data.total} {data.total === 1 ? 'book' : 'books'}
            </p>

            <div role="group" aria-label="Sort library" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 24 }}>
                <span style={{ color: 'var(--text-muted)' }}>Sort by</span>
                {SORTS.map((s) => (
                    <button key={s.key} onClick={() => setSort(s.key)} aria-pressed={sort === s.key} style={sortButton(sort === s.key)}>
                        {s.label}
                    </button>
                ))}
            </div>

            {data.total === 0 ? (
                <p>Your library is empty. Set a book's status from Recommendations or the Catalog and it will show up here.</p>
            ) : (
                <>
                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginBottom: 12 }}>
                        <button onClick={() => setCollapsed(new Set(groups.map((g) => g.label)))} style={sortButton(false)}>Collapse all</button>
                        <button onClick={() => setCollapsed(new Set())} style={sortButton(false)}>Expand all</button>
                    </div>
                    {groups.map((g, i) => {
                        const isOpen = !collapsed.has(g.label)
                        const panelId = `library-group-${i}`
                        return (
                            <section key={`${g.label}-${i}`} style={{ marginBottom: 28, textAlign: 'left' }}>
                                <h3 style={{ margin: '0 0 12px' }}>
                                    <button type="button" onClick={() => toggleGroup(g.label)} aria-expanded={isOpen} aria-controls={panelId} style={headingButton}>
                                        <span aria-hidden="true" style={{ display: 'inline-block', width: '1em' }}>{isOpen ? '▾' : '▸'}</span>
                                        <span>{g.label}</span>
                                        <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>({g.books.length})</span>
                                    </button>
                                </h3>
                                {isOpen && (
                                    <div id={panelId} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 16 }}>
                                        {g.books.map((b) => <LibraryCard key={b.id} book={b} />)}
                                    </div>
                                )}
                            </section>
                        )
                    })} 
                </>
            )}
        </div>
    )
}