import { useEffect, useState } from 'react'
import { API } from '../lib/api'
import { describeProgress } from '../lib/progress'
import ProgressBar from './ProgressBar'
import BookLink from './BookLink'

function Cover({ url, title }) {
    const [failed, setFailed] = useState(false)
    if (!url || failed) {
        return (
            <div style={{ height: '180px', width: '120px', border: '1px solid var(--border)', borderRadius: '4px', display: 'flex', alignItems: 'center', 
                justifyContent: 'center', color: 'var(--text-muted)', fontSize: '0.85em' }}>
                No cover
            </div>
        )
    }
    return (
        <img
            src={url}
            alt={title}
            onError={() => setFailed(true)}
            style={{ height: '180px', width: '120px', objectFit: 'cover', borderRadius: '4px', boxShadow: '0 2px 8px var(--shadow)' }}
        />
    )
}

function CurrentlyReading({ userId, refreshKey = 0 }) {
    const [books, setBooks] = useState([])

    useEffect(() => {
        const controller = new AbortController()
        fetch(`${API}/currently-reading/${userId}`, { signal: controller.signal })
            .then((res) => {
                if (!res.ok) throw new Error(`Unexpected response (${res.status})`)
                return res.json()
            })
            .then((data) => setBooks(Array.isArray(data?.books) ? data.books : []))
            .catch((err) => {
                if (err.name === 'AbortError') return
                console.error('Failed to load currently reading', err)
                setBooks([])
            })
        return () => controller.abort()
    }, [userId, refreshKey])

    if (books.length === 0) return null

    return (
        <section style={{ maxWidth: '720px', margin: '24px auto 0', textAlign: 'center', }}>
            <h3 style={{ margin: 0 }}>Currently reading</h3>
            <div style={{ display: 'flex', gap: '28px', justifyContent: 'center', flexWrap: 'wrap', marginTop: '16px' }}>
                {books.map((b) => (
                    <div key={b.id} style={{ width: '140px', display: 'flex', flexDirection: 'column' }}>
                        <div style={{ display: 'flex', justifyContent: 'center' }}>
                            <BookLink id={b.id}><Cover url={b.cover_url} title={b.title} /></BookLink>
                        </div>
                        <div style={{ marginTop: '8px', fontWeight: 600, color: 'var(--text)', fontSize: '0.9em' }}>
                            <BookLink id={b.id}>{b.title}</BookLink>
                        </div>
                        <div style={{ color: 'var(--text-muted)', fontSize: '0.85em', marginBottom: '8px' }}>{b.author}</div>
                        <div style={{ marginTop: 'auto' }}>
                            <ProgressBar percent={b.progress_percent ?? 0} label={`Progress on ${b.title}`} />
                            <div style={{ color: 'var(--text-muted)', fontSize: '0.8em', marginTop: '4px' }}>
                                {describeProgress(b.progress_percent, b.current_page, b.page_count)}
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </section>
    )
}

export default CurrentlyReading