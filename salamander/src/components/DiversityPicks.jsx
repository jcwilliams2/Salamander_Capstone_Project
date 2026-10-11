import { useState, useEffect } from 'react'
import VoteControls from './VoteControls'
import StatusSelector from './StatusSelector'

const API = 'http://localhost:8000'

function Cover({ url, title }) {
    const [failed, setFailed] = useState(false)
    if (!url || failed) return null
    return <img src={url} alt={title} onError={() => setFailed(true)} style={{ height: '120px' }} />
}

function DiversityPicks({ userId }) {
    const [state, setState] = useState({ loaded: false, items: [] })

    useEffect(() => {
        const controller = new AbortController()
        fetch(`${API}/recommendations/diversity/${userId}`, { signal: controller.signal })
            .then(async (res) => {
                const data = await res.json().catch(() => null)
                if (!res.ok || !Array.isArray(data?.suggestions)) {
                    throw new Error(`Unexpected response (${res.status})`)
                }
                setState({ loaded: true, items: data.suggestions })
            })
            .catch((err) => {
                if (err.name === 'AbortError') return
                console.error('Failed to load diversity suggestions', err)
                setState({ loaded: true, items: [] })
            })
        return () => controller.abort()
    }, [userId])

    if (!state.loaded) return null

    return (
        <div style={{ marginTop: '32px' }}>
            <h2>Something different</h2>
            {state.items.length === 0 ? (
                <p style={{ color: '#666' }}>
                    Suggestions beyond your usual reading will appear here once you've marked a few books as finished.
                </p>
            ) : (
                <>
                    <p style={{ color: '#666' }}>
                        A few picks that branch out from what you've been reading.
                    </p>
                    {state.items.map((book) => (
                        <div key={book.id} style={{ marginBottom: '12px' }}>
                            <Cover url={book.cover_url} title={book.title} />
                            <div><strong>{book.title}</strong> by {book.author}</div>
                            <p style={{ fontSize: '0.9em', color: '#666' }}>{book.explanation}</p>
                            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                                <VoteControls userId={userId} bookId={book.id} />
                                <StatusSelector userId={userId} bookId={book.id} />
                            </div>
                        </div>
                    ))}
                </>
            )}
        </div>
    )
}

export default DiversityPicks