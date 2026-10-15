import { useState, useEffect } from 'react'
import BookCardGrid from './BookCardGrid'

const API = 'http://localhost:8000'

function WantToReadPage({ userId }) {
    const [state, setState] = useState({ loading: true, books: [], failed: false })


    useEffect(() => {
        const controller = new AbortController()
        fetch(`${API}/want-to-read/${userId}`, { signal: controller.signal })
            .then((res) => {
                if (!res.ok) throw new Error(`Unexpected response (${res.status})`)
                return res.json()
            })
            .then((data) => 
                setState({
                    loading: false,
                    books: Array.isArray(data.results) ? data.results : [],
                    failed: false,
                })
            )
            .catch((err) => {
                if (err.name === 'AbortError') return
                console.error('Failed to load Want to Read list', err)
                setState({ loading: false, books: [], failed: true })
            })
        return () => controller.abort()
    }, [userId])

    function handleStatusChange(book, status) {
        if (status === 'want_to_read') return
        setState((prev) => ({ ...prev, books: prev.books.filter((b) => b.id !== book.id) }))
    }

    const {loading, books, failed } = state
    
    const genreCounts = {}
    books.forEach((b) => (b.genre_tags || []).forEach((g) => {
        genreCounts[g] = (genreCounts[g] || 0) +  1
    }))
    const topGenres = Object.entries(genreCounts).sort((a, b) => b[1] - a[1]).slice(0, 5)

    return (
        <div>
            <h2>Want to Read{!loading && !failed ? ` (${books.length})` : ''}</h2>

            {loading && <p>Loading your list...</p>}
            {!loading && failed && <p style={{ color: 'red' }}>Couldn't load your list. Please try again.</p>}

            {!loading && !failed && books.length === 0 && (
                <p>Nothing to see here yet. Set a book's status to "Want to Read" from Recommendations or the Catalog and it will show up here.</p>
            )}

            {!loading && !failed && books.length > 0 && (
                <>
                    {topGenres.length > 0 && (
                        <p style={{ color: '#666' }}>
                            Most common genres in your list:{' '}
                            {topGenres.map(([genre, count]) => `${genre} (${count})`).join(' . ')}
                        </p>
                    )}
                    <BookCardGrid books={books} userId={userId} onStatusChange={handleStatusChange} />
                </>
            )}
        </div>
    )
}

export default WantToReadPage