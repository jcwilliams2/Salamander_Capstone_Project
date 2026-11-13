import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { API } from '../lib/api'

const box ={
    maxWidth: '960px',
    margin: '16px auto',
    padding: '16px',
    textAlign: 'left',
    background: 'var(--surface-alt)',
    color: 'var(--text)',
    border: '1px solid var(--border)',
    borderRadius: '12px',
    boxShadow: '0 2px 8px var(--shadow)',
}
const muted = { color: 'var(--text-muted)', margin: '4px 0 0', fontSize: '0.9em' }

function DigestBanner({ userId }) {
    const [digest, setDigest] = useState(null)

    useEffect(() => {
        const controller = new AbortController()
        fetch(`${API}/digest/${userId}`, { signal: controller.signal })
            .then(async (res) => {
                const data = await res.json().catch(() => null)
                if (!res.ok || !data || !('digest' in data)) throw new Error(`Unexpected response (${res.status})`)
                setDigest(data.digest)
            })
            .catch((err) => {
                if (err.name === 'AbortError') return
                console.error('Failed to load your digest', err)
            })
        return () => controller.abort()
    }, [userId])

    function dismiss() {
        const id = digest.id
        setDigest(null)
        fetch(`${API}/digest/${id}/seen`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId }),
        }).catch((err) => console.error('Failed to dismiss your digest', err))
    }

    if (!digest) return null

    const previous = digest.previous_score == null ? null : Math.round(digest.previous_score * 100)

    return (
        <aside style={box} aria-label="Your reading variety digest">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px' }}>
                <strong>Your reading variety digest</strong>
                <button type="button" onClick={dismiss}>Dismiss</button>
            </div>
            <p style={{ margin: '8px 0 0' }}>{digest.headline}</p>
            <p style={muted}>
                Variety score {digest.score_percent}
                {previous !== null && ` (was ${previous} last time)`}
                {' '}· based on {digest.books_considered} finished or stopped books. It describes how far apart your books 
                sit from each other. A higher or lower score isn't better or worse.
            </p>
            {digest.picks?.length > 0 && (
                <>
                    <p style={{ margin: '12px 0 8px' }}>If you're curious, a few books that differ from what you've been reading:</p>
                    <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: '12px' }}>
                        {digest.picks.map((pick) => (
                            <li key={pick.id} style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                                {pick.cover_url && (
                                    <img src={pick.cover_url} alt="" width="48" height="72"
                                        style={{ objectFit: 'cover', borderRadius: '4px', flexShrink: 0}} />
                                )}
                                <div style={{ flex: 1, minWidth: 0 }}>
                                    <Link to={`/book/${pick.id}`} style={{ color: 'var(--link)', fontWeight: 600 }}>{pick.title}</Link>
                                    {pick.author && <span style={{ color: 'var(--text-muted)' }}> by {pick.author}</span>}
                                    {pick.explanation && <p style={muted}>{pick.explanation}</p>}
                                </div>
                            </li>
                        ))}
                    </ul>
                </>
            )}
        </aside>
    )
}

export default DigestBanner