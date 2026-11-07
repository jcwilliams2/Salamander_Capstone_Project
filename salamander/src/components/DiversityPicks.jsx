import { API } from '../lib/api'
import { useState, useEffect } from 'react'
import BookCardGrid from './BookCardGrid'


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
        <div style={{ marginTop: '72px', marginBottom: '30px' }}>
            <h2 style={{ marginBottom: '6px' }}>Something different</h2>
            {state.items.length === 0 ? (
                <p style={{ color: 'var(--text-muted)' }}>
                    Suggestions beyond your usual reading will appear here once you've marked a few books as finished.
                </p>
            ) : (
                <>
                    <p style={{ color: 'var(--text-muted)', marginBottom: '27px' }}>A few picks that branch out from what you've been reading.</p>
                    <BookCardGrid books={state.items} userId={userId} />
                </>
            )}
        </div>
    )
}

export default DiversityPicks