import { useState, useEffect } from 'react'
import VoteControls from './VoteControls'
import StatusSelector from './StatusSelector'

const API = 'http://localhost:8000'
const PAGE_SIZE = 24

function Cover({ url, title }) {
    const [failed, setFailed] = useState(false)
    if (!url || failed) {
        return (
            <div style={{ height: '160px', border: '1px solid #ccc', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                No cover
            </div>
        )
    }
    return <img src={url} alt={title} onError={() => setFailed(true)} style={{ height: '160px' }} />
}

function BookGrid({ books, userId}) {

    return (
        <div
            style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(170px, 1fr))',
                gap: '16px',
                textAlign: 'center',
            }}
        >
            {books.map((book) => (
                <div key={book.id}>
                    <Cover url={book.cover_url} title={book.title} />
                    <div><strong>{book.title}</strong></div>
                    <div>{book.author}</div>
                    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                        <VoteControls userId={userId} bookId={book.id} initialVote={book.vote} />
                        <StatusSelector userId={userId} bookId={book.id} initialStatus={book.status} />
                    </div>
                </div>
            ))}
        </div>
    )
}

function Pager({ page, totalPages, onGo }) {
    return (
        <div style={{ margin: '16px 0' }}>
            <button onClick={() => onGo(page - 1)} disabled={page <= 1}>Previous</button>
            <span style={{ margin: '0 12px' }}>Page {page} of {totalPages}</span>
            <button onClick={() => onGo(page + 1)} disabled={page >= totalPages}>Next</button>
        </div>
    )
}

function GenreChips({ options, selected, onToggle, onClear }) {
    if (options.length === 0) return null
    return (
        <div style={{ margin: '0 0 16px' }}>
            <div
                role="group"
                aria-label="Filter by genre"
                style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', justifyContent: 'center' }}
            >
                {options.map(({ genre, count }) => {
                    const active = selected.includes(genre)
                    return (
                        <button
                            key={genre}
                            type="button"
                            aria-pressed={active}
                            onClick={() => onToggle(genre)}
                            style={{ 
                                padding: '4px 12px',
                                borderRadius: '999px',
                                cursor: 'pointer',
                                border: active ? '2px solid #2b6cb0' : '1px solid #999',
                                background: active ? '#2b6cb0' : 'transparent',
                                color: active ? '#fff' : 'inherit',
                                fontWeight: active ? 600 : 400,
                            }}
                        >
                            {active ? '✓ ' : ''}{genre} ({count})
                        </button>
                    )
                })}
            </div>
            {selected.length > 0 && (
                <p style={{ marginTop: '12px' }}>
                    Filtering by: <strong>{selected.join(', ')}</strong>{' '}
                    <button type="button" onClick={onClear}>Clear filters</button>
                </p>
            )}
        </div>
    )
}

function RequestPrompt({ query, userId, onAdded }) {
    const [state, setState] = useState({ phase: 'looking', candidate: null, message: '' })

    useEffect(() => {
        const controller = new AbortController()
        fetch(`${API}/catalog/lookup?q=${encodeURIComponent(query)}`, { signal: controller.signal })
            .then((res) => res.json())
            .then((data) => 
                setState({ phase: data.candidate ? 'found' : 'none', candidate: data.candidate || null, message: '' })
            )
            .catch((err) => {
                if (err.name === 'AbortError') return
                console.error('Catalog lookup failed', err)
                setState({ phase: 'none', candidate: null, message: '' })
            })
        return () => controller.abort()
    }, [query])

    function confirm() {
        setState((prev) => ({ ...prev, phase: 'adding' }))
        fetch(`${API}/catalog/request`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, isbn: state.candidate.isbn }),
        })
            .then(async (res) => {
                const data = await res.json().catch(() => ({}))
                if (!res.ok) throw new Error(data.detail || 'Request failed')
                return data
            })
            .then((data) => {
                if (data.status === 'added' || data.status === 'exists') {
                    setState((prev) => ({ ...prev, phase: 'added' }))
                    onAdded(data.book?.title)
                } else {
                    setState((prev) => ({ ...prev, phase: 'failed', message: data.message || "We couldn't add that book." }))
                }
            })
            .catch((err) => setState((prev) => ({ ...prev, phase: 'failed', message: err.message })))
    }

    const { phase, candidate, message } = state
    if (phase === 'none' || phase === 'dismissed') return null
    if (phase === 'looking') return <p style={{ fontStyle: 'italic' }}>Checking other sources...</p>

    return (
        <div style={{ border: '1px solid #999', borderRadius: '8px', padding: '16px', maxWidth: '420px', margin: '16px auto', textAlign: 'center' }}>
            <p>
                This book isn't in the Salamander catalog yet. We found a match elsewhere. Would you like to add it?
            </p>
            <Cover url={candidate.cover_url} title={candidate.title} />
            <div><strong>{candidate.title}</strong></div>
            <div>{candidate.author}</div>
            {phase === 'adding' && <p>Adding this book. It can take a few seconds...</p>}
            {phase === 'added' && <p>Added. Updating your results...</p>}
            {phase === 'failed' && <p style={{ color: 'red' }}>{message}</p>}
            {(phase === 'found' || phase === 'failed') && (
                <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', marginTop: '12px' }}>
                    <button type="button" onClick={confirm}>{phase === 'failed' ? 'Try again' : 'Add to catalog'}</button>
                    <button type="button" onClick={() => setState((prev) => ({ ...prev, phase: 'dismissed' }))}>No thanks</button>
                </div>
            )}
        </div>
    )
}

function CatalogPage({ userId }) {
    const [query, setQuery] = useState('')
    const [search, setSearch] = useState({ q: '', items: [], failed: false })
    const [page, setPage] = useState(1)
    const [browse, setBrowse] = useState({ page: 0, items: [], total: 0, failed: false })
    const [genreOptions, setGenreOptions] = useState([])
    const [selected, setSelected] = useState([])
    const [filtered, setFiltered] = useState({ key: '', items: [], total: 0, failed: false })
    const [refresh, setRefresh] = useState(0)

    const trimmed = query.trim()
    const searching = trimmed.length >= 2
    const filtering = selected.length > 0
    const searchReady = searching && search.q === trimmed
    const browseReady = browse.page === page
    const totalPages = Math.max(1, Math.ceil(browse.total / PAGE_SIZE))
    const filterKey = `${selected.join(',')}|${searching ? trimmed : ''}|${page}`
    const filterReady = filtering && filtered.key === filterKey
    const filterPages = Math.max(1, Math.ceil(filtered.total / PAGE_SIZE))

    useEffect(() => {
        fetch(`${API}/catalog/genres`)
            .then((res) => res.json())
            .then((data) => setGenreOptions(Array.isArray(data.genres) ? data.genres : []))
            .catch((err) => console.error('Genre list failed', err))
    }, [])

    useEffect(() => {
        if (trimmed.length < 2 || filtering) return

        const controller = new AbortController()
        const timer = setTimeout(() => {
            fetch(`${API}/catalog/search?q=${encodeURIComponent(trimmed)}&user_id=${userId}`, { signal: controller.signal })
                .then((res) => res.json())
                .then((data) => 
                    setSearch({ q: trimmed, items: Array.isArray(data.results) ? data.results : [], failed: false })
                )
                .catch((err) => {
                    if (err.name === 'AbortError') return
                    console.error('Catalog search failed', err)
                    setSearch({ q: trimmed, items: [], failed: true })
                })
        }, 700)
        
        return () => {
            clearTimeout(timer)
            controller.abort()
        }
    }, [trimmed, userId, filtering, refresh])

    useEffect(() => {
        if (!filtering) return

        const controller = new AbortController()
        const key = filterKey
        const timer = setTimeout(() => {
            const params = new URLSearchParams({
                genres: selected.join(","),
                q: searching ? trimmed : '',
                page,
                page_size: PAGE_SIZE,
                user_id: userId,
            })
            fetch(`${API}/catalog/filter?${params}`, { signal: controller.signal })
                .then((res) => res.json())
                .then((data) => 
                    setFiltered({
                        key,
                        items: Array.isArray(data.results) ? data.results : [],
                        total: data.total ?? 0,
                        failed: false,
                    })
                )
                .catch((err) => {
                    if (err.name === 'AbortError') return
                    console.error('Catalog filter failed', err)
                    setFiltered({ key, items: [], total: 0, failed: true })
                })
        }, searching ? 700 : 0)

        return () => {
            clearTimeout(timer)
            controller.abort()
        }
    }, [filterKey, userId])

    useEffect(() => {
        const controller = new AbortController()
        fetch(`${API}/catalog/browse?page=${page}&page_size=${PAGE_SIZE}&user_id=${userId}`, { signal: controller.signal })
            .then((res) => res.json())
            .then((data) =>
                setBrowse({
                    page,
                    items: Array.isArray(data.results) ? data.results : [],
                    total: data.total ?? 0,
                    failed: false,
                })
            )
            .catch((err) => {
                if (err.name === 'AbortError') return
                console.error('Catalog browse failed', err)
                setBrowse((prev) => ({ ...prev, page, items: [], failed: true }))
            })
        return () => controller.abort()
    }, [page, userId])

    function goToPage(next) {
        setPage(next)
        window.scrollTo(0, 0)
    }

    function toggleGenre(genre) {
        setSelected((prev) => (prev.includes(genre) ? prev.filter((g) => g !== genre) : [...prev, genre]))
        setPage(1)
    }

    function clearGenres(){
        setSelected([])
        setPage(1)
    }

    function handleQuery(e) {
        setQuery(e.target.value)
        if (filtering) setPage(1)
    }

    return (
        <div>
            <h2>Catalog</h2>
            <input
                type="search"
                placeholder="Search by title or author"
                aria-label="Search the catalog"
                value={query}
                onChange={handleQuery}
                style={{ width: '60%', padding: '8px', marginBottom: '16px' }}
            />

            <GenreChips options={genreOptions} selected={selected} onToggle={toggleGenre} onClear={clearGenres} />

            {filtering ? (
                <>
                    {!filterReady && <p>Filtering...</p>}
                    {filterReady && filtered.failed && <p style={{ color: 'red' }}>Couldn't apply the filter. Please try again.</p>}
                    {filterReady && !filtered.failed && filtered.items.length === 0 && (
                        <p>No books match {selected.join(' or ')}{searching ? ` for "${trimmed}"` : ''}.</p>
                    )}
                    {filterReady && !filtered.failed && <BookGrid books={filtered.items} userId={userId} />}
                    <Pager page={page} totalPages={filterPages} onGo={goToPage} />
                </>
            ) : searching ? (
                <>
                    {!searchReady && <p>Searching...</p>}
                    {searchReady && search.failed && <p style={{ color: 'red' }}>Search failed. Please try again.</p>}
                    {searchReady && !search.failed && search.items.length === 0 && (
                        <>
                            <p>No books found for "{trimmed}".</p>
                            <RequestPrompt
                                key={trimmed}
                                query={trimmed}
                                userId={userId}
                                onAdded={(title) => { if (title) setQuery(title); setRefresh((r) => r + 1) }}
                            />
                        </>
                    )}
                    {searchReady && !search.failed && <BookGrid books={search.items} userId={userId} />}
                </>
            ) : (
                <>
                    {!browseReady && <p>Loading catalog...</p>}
                    {browseReady && browse.failed && <p style={{ color: 'red' }}>Couldn't load the catalog. Please try again.</p>}
                    {browseReady && !browse.failed && <BookGrid books={browse.items} userId={userId} />}
                    <Pager page={page} totalPages={totalPages} onGo={goToPage} />
                </>
            )}
        </div>
    )
}

export default CatalogPage