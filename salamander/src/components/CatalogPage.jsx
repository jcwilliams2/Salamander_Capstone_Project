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

function CatalogPage({ userId }) {
    const [query, setQuery] = useState('')
    const [search, setSearch] = useState({ q: '', items: [], failed: false })
    const [page, setPage] = useState(1)
    const [browse, setBrowse] = useState({ page: 0, items: [], total: 0, failed: false })

    const trimmed = query.trim()
    const searching = trimmed.length >= 2
    const searchReady = searching && search.q === trimmed
    const browseReady = browse.page === page
    const totalPages = Math.max(1, Math.ceil(browse.total / PAGE_SIZE))

    useEffect(() => {
        if (trimmed.length < 2) return

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
    }, [trimmed, userId])

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

    return (
        <div>
            <h2>Catalog</h2>
            <input
                type="search"
                placeholder="Search by title or author"
                aria-label="Search the catalog"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                style={{ width: '60%', padding: '8px', marginBottom: '16px' }}
            />

            {searching ? (
                <>
                    {!searchReady && <p>Searching...</p>}
                    {searchReady && search.failed && <p style={{ color: 'red' }}>Search failed. Please try again.</p>}
                    {searchReady && !search.failed && search.items.length === 0 && <p>No books found for "{trimmed}".</p>}
                    {searchReady && !search.failed && <BookGrid books={search.items} userId={userId} />}
                </>
            ) : (
                <>
                    {!browseReady && <p>Loading catalog...</p>}
                    {browseReady && browse.failed && <p style={{ color: 'red' }}>Couldn't load the catalog. Please try again.</p>}
                    {browseReady && !browse.failed && <BookGrid books={browse.items} userId={userId} />}
                    <div style={{ margin: '16px 0' }}>
                        <button onClick={() => goToPage(page - 1)} disabled={page <= 1}>Previous</button>
                        <span style={{ margin: '0 12px' }}>Page {page} of {totalPages}</span>
                        <button onClick={() => goToPage(page + 1)} disabled={page >= totalPages}>Next</button>
                    </div>
                </>
            )}
        </div>
    )
}

export default CatalogPage