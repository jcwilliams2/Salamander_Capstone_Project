import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { API } from '../lib/api'

const card = {
    flex: '1 1 280px',
    minWidth: 0,
    padding: '16px',
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: '12px',
    boxShadow: '0 2px 8px var(--shadow)',
}
const muted = { color: 'var(--text-muted)', fontSize: '0.9em' }
const chip = { background: 'var(--surface-alt)', color: 'var(--text)', padding: '2px 10px', borderRadius: '999px', fontSize: '0.85em' }

function useBook(id) {
    const [result, setResult] = useState({ key: null, status: 'loading', book: null })
    useEffect(() => {
        if (!id) return
        let cancelled = false
        fetch(`${API}/books/${encodeURIComponent(id)}`)
            .then(async (res) => {
                if (res.status === 404) return { status: 'missing', book: null }
                const data = await res.json().catch(() => null)
                if (!res.ok || !data?.id) throw new Error(`Unexpected response (${res.status})`)
                return { status: 'ready', book: data }
            })
            .catch((err) => {
                console.error('Failed to load book', err)
                return {status: 'error', book: null }
            })
            .then((outcome) => {
                if (!cancelled) setResult({ key: id, ...outcome })
            })
        return () => { cancelled = true }
    }, [id])
    if (!id) return { status: 'empty', book: null }
    return result.key === id ? result : { status: 'loading', book: null }
}

function useComparison(a, b) {
    const key = `${a}|${b}`
    const active = Boolean(a && b && a !== b)
    const [result, setResult] = useState({ key: null, status: 'loading', data: null })
    useEffect(() => {
        if (!active) return
        let cancelled = false
        fetch(`${API}/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`)
            .then(async (res) => {
                const data = await res.json().catch(() => null)
                if (!res.ok || typeof data?.comparable !== 'boolean') throw new Error(`Unexpected response (${res.status})`)
                return { status: 'ready', data }
            })
            .catch((err) => {
                console.error('Failed to compare books', err)
                return { status: 'error', data: null }
            })
            .then((outcome) => {
                if (!cancelled) setResult({ key, ...outcome })
            })
        return () => { cancelled = true }
    }, [a, b, active, key])
    if (!active) return { status: 'idle', data: null }
    return result.key === key ? result : { status: 'loading', data: null }
}

function BookPicker({ label, excludeId, onPick }) {
    const [text, setText] = useState('')
    const [found, setFound] = useState({ q: '', results: [] })
    const q = text.trim()

    useEffect(() => {
        if (q.length < 2) return
        const controller = new AbortController()
        const timer = setTimeout(() => {
            fetch(`${API}/catalog/search?q=${encodeURIComponent(q)}`, { signal: controller.signal })
                .then(async (res) => {
                    const data = await res.json().catch(() => null)
                    if (!res.ok || !Array.isArray(data?.results)) throw new Error(`Unexpected response (${res.status})`)
                    setFound({ q, results: data.results })
                })
                .catch((err) => {
                    if (err.name === 'AbortError') return
                    console.error('Failed to search the catalog', err)
                })
        }, 300)
        return () => {
            clearTimeout(timer)
            controller.abort()
        }
    }, [q])

    const ready = q.length >= 2 && found.q === q
    const results = ready ? found.results.filter((b) => b.id !== excludeId).slice(0, 8) : []

    return (
        <div>
            <label style={{ display: 'block', marginBottom: '8px' }}>
                <span style={{ ...muted, display: 'block', marginBottom: '4px' }}>{label}</span>
                <input
                    type="search"
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder="Search by title or author"
                    style={{ width: '100%', boxSizing: 'border-box' }}
                />
            </label>
            {q.length >=2 && !ready && <p style={muted}>Searching...</p>}
            {ready && results.length === 0 && <p style={muted}>No books found.</p>}
            {results.length > 0 && (
                <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: '8px' }}>
                    {results.map((book) => (
                        <li key={book.id}>
                            <button
                                type="button"
                                onClick={() => onPick(book.id)}
                                style={{ display: 'flex', gap: '10px', alignItems: 'center', width: '100%', textAlign: 'left' }}
                            >
                                {book.cover_url && (
                                    <img src={book.cover_url} alt="" width="32" height="48"
                                        style={{ objectFit: 'cover', borderRadius: '3px', flexShrink: 0 }} />
                                )}
                                <span style={{ minWidth: 0 }}>
                                    <strong>{book.title}</strong>
                                    {book.author && <span style={muted}> by {book.author} </span>}
                                </span>
                            </button>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    )
}

function Slot({ name, id, excludeId, onPick, onClear }) {
    const { status, book } = useBook(id)
    return (
        <div style={card}>
            {status === 'empty' && <BookPicker label={`Choose ${name}`} excludeId={excludeId} onPick={onPick} />}
            {status === 'loading' && <p style={muted}>Loading...</p>}
            {(status === 'missing' || status === 'error') && (
                <>
                    <p>{status === 'missing' ? "We couldn't find that book." : 'Something went wrong loading this book.'}</p>
                    <button type="button" onClick={onClear}>Choose another</button>
                </>
            )}
            {status === 'ready' && (
                <div style={{ display: 'flex', gap: '14px', alignItems: 'flex-start' }}>
                    {book.cover_url && (
                        <Link to={`/book/${book.id}`} style={{ flexShrink: 0}}>
                            <img src={book.cover_url} alt={book.title} width="90" height="135"
                                style={{ objectFit: 'cover', borderRadius: '6px', boxShadow: '0 2px 8px var(--shadow)', display: 'block' }} />
                        </Link>
                    )}
                    <div style={{ minWidth: 0 }}>
                        <div style={muted}>{name}</div>
                        <Link to={`/book/${book.id}`} style={{ fontWeight: 600 }}>{book.title}</Link>
                        {book.author && <div style={muted}>by {book.author}</div>}
                        <button type="button" onClick={onClear} style={{ marginTop: '10px' }}>Change</button>
                    </div>
                </div>
            )}
        </div>
    )
}

function Chips({ title, tags }) {
    if (!tags?.length) return null
    return (
        <div style={{ marginTop: '12px' }}>
            <div style={{ ...muted, marginBottom: '6px' }}>{title}</div>
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                {tags.map((t) => <span key={t} style={chip}>{t}</span>)}
            </div>
        </div>
    )
}

function Comparison({ a, b }) {
    const { status, data } = useComparison(a, b)
    if (status === 'idle') return null
    if (status === 'loading') return <p style={muted}>Comparing...</p>
    if (status === 'error') return <p>Something went wrong comparing these books. Please try again.</p>
    if (!data.comparable) {
        const names = data.missing.map((m) => data.books[m].title).join(' and ')
        return <p>We can't compare {names} yet—there isn't enough information about {data.missing.length > 1 ? 'them' : 'it'} to measure similarity.</p>
    }
    const titleA = data.books.a.title
    const titleB = data.books.b.title
    return (
        <section style={{ ...card, flex: 'none' }} aria-live="polite">
            <p style={{ margin: 0 }}>{data.summary}</p>
            <p style={{ ...muted, margin: '6px 0 0' }}>
                Similarity {data.similarity} (1 means identical).
            </p>
            <Chips title="Genres they share" tags={data.shared_tags} />
            <Chips title={`Only in ${titleA}`} tags={data.only_a} />
            <Chips title={`Only in ${titleB}`} tags={data.only_b} />
        </section>
    )
}

function ComparePage() {
    const [params, setParams] = useSearchParams()
    const a = params.get('a') || ''
    const b = params.get('b') || ''

    function setSlot(name, value) {
        const next = new URLSearchParams(params)
        if (value) next.set(name, value)
        else next.delete(name)
        setParams(next)
    }

    return (
        <section style={{ maxWidth: '820px', margin: '0 auto', textAlign: 'left', color: 'var(--text)' }}>
            <h2 style={{ textAlign: 'center' }}>Compare two books</h2>
            <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', marginBottom: '16px' }}>
                <Slot name="Book A" id={a} excludeId={b} onPick={(id) => setSlot('a', id)} onClear={() => setSlot('a', '')} />
                <Slot name="Book B" id={b} excludeId={a} onPick={(id) => setSlot('b', id)} onClear={() => setSlot('b', '')} />
            </div>
            {a && b && a === b
                ? <p>Pick two different books to compare.</p>
                : <Comparison a={a} b={b} />}
        </section>
    )
}

export default ComparePage