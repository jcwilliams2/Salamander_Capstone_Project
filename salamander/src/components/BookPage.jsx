import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import VoteControls from './VoteControls'
import StatusSelector from './StatusSelector'
import { API } from '../lib/api'

function Cover({ url, title }) {
    const [failed, setFailed] = useState(false)
    const box = {
        width: '200px',
        height: '300px',
        borderRadius: '8px',
        boxShadow: '0 4px 14px var(--shadow)',
        flexShrink: 0,
    }
    if (!url || failed) {
        return (
            <div style={{ ...box, background: 'var(--surface-alt)', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: '12px', boxSizing: 'border-box' }}>
                {title}
            </div>
        )
    }
    return <img src={url} alt={title} onError={() => setFailed(true)} style={{ ...box, objectFit: 'cover' }} />
}

const TAG_LIMIT = 6

function TagList({ tags }) {
    const [showAll, setShowAll] = useState(false)
    const shown = showAll ? tags : tags.slice(0, TAG_LIMIT)
    const hidden = tags.length - TAG_LIMIT
    return (
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '16px' }}>
            {shown.map((tag) => (
                <span key={tag} style={{ background: 'var(--surface-alt)', color: 'var(--text)', padding: '2px 10px', borderRadius: '999px', fontSize: '0.85em' }}>
                    {tag}
                </span>
            ))}
            {hidden > 0 && (
                <button type="button" onClick={() => setShowAll(!showAll)}
                    style={{ background: 'transparent', color: 'var(--text-muted)', border: 'none', padding: '2px 6px', cursor: 'pointer', fontSize: '0.85em' }}>
                    {showAll ? 'Show fewer' : `+${hidden} more`}
                </button>
            )}
        </div>
    )
}

function BookPage({ userId }) {
    const { id } = useParams()
    const navigate = useNavigate()
    const key = `${id}|${userId ?? ''}`
    const [result, setResult] = useState({ key: null, status: 'loading', book: null })

    useEffect(() => {
        let cancelled = false
        const query = userId ? `?user_id=${encodeURIComponent(userId)}` : ''
        fetch(`${API}/books/${encodeURIComponent(id)}${query}`)
            .then(async (res) => {
                if (res.status === 404) return { status: 'missing', book: null }
                const data = await res.json().catch(() => null)
                if (!res.ok || !data?.id) throw new Error(`Unexpeted response (${res.status})`)
                return { status: 'ready', book: data }
            })
            .catch((err) => {
                console.error('Failed to load book', err)
                return { status: 'ready', book: null }
            })
            .then((outcome) => {
                if (!cancelled) setResult({ key, ...outcome })
            })
        return () => { cancelled = true }
    }, [id, userId, key])

    const state = result.key === key ? result.status : 'loading'
    const book = result.book

    const back = (
        <p style={{ textAlign: 'left', maxWidth: '820px', margin: '0 auto 12px' }}>
            <button type="button" onClick={() => navigate(-1)}>← Back</button>
        </p>
    )

    if (state === 'loading') return <p>Loading...</p>
    if (state === 'missing') {
        return <div>{back}<p>We couldn't find that book. <Link to="/catalog">Browse the catalog</Link></p></div>
    }
    if (state === 'error') {
        return <div>{back}<p>Something went wrong loading this book. Please try again.</p></div>
    }

    return (
        <div style={{ color: 'var(--text)' }}>
            {back}
            <article
                style={{
                    maxWidth: '820px',
                    margin: '0 auto',
                    padding: '24px',
                    background: 'var(--surface)',
                    borderRadius: '12px',
                    boxShadow: '0 2px 10px var(--shadow)',
                    display: 'flex',
                    gap: '28px',
                    flexWrap: 'wrap',
                    textAlign: 'left',
                }}
            >
                <Cover url={book.cover_url} title={book.title} />

                <div style={{ flex: '1 1 320px', minWidth: 0 }}>
                    <h2 style={{ margin: '0 0 4px' }}>{book.title}</h2>
                    {book.author && <div style={{ color: 'var(--text-muted)', marginBottom: '12px' }}>by {book.author}</div>}

                    {book.genre_tags && <TagList key={book.id} tags={book.genre_tags} />}

                    {userId ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap', marginBottom: '16px' }}>
                            <VoteControls userId={userId} bookId={book.id} initialVote={book.vote} />
                            <StatusSelector userId={userId} bookId={book.id} initialStatus={book.status} />
                        </div>
                    ) : (
                        <p style={{ color: 'var(--text-muted)', marginBottom: '16px' }}>
                            Sign in to rate this book or add it to your library.
                        </p>
                    )}

                    {book.synopsis && (
                        <>
                        <h3 style={{ margin: '0 0 6px' }}>Synopsis</h3>
                        <p style={{ lineHeight: 1.5, marginTop: 0 }}>{book.synopsis}</p>
                        </>
                    )}

                    {book.isbn && (
                        <div style={{ color: 'var(--text-muted)', fontSize: '0.85em' }}>ISBN {book.isbn}</div>
                    )}
                </div>
            </article>
        </div>
    )
}

export default BookPage