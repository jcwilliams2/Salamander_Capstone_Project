import { API } from '../lib/api'
import { useEffect, useState } from 'react'


function localDateISO(d = new Date()) {
    const mm = String(d.getMonth() + 1).padStart(2, '0')
    const dd = String(d.getDate()).padStart(2, '0')
    return `${d.getFullYear()}-${mm}-${dd}`
}

function inputDay(ts) {
    if (!ts) return ''
    const d = new Date(ts)
    return Number.isNaN(d.getTime()) ? '' : localDateISO(d)
}

function showDay(ts) {
    if (!ts) return null
    const d = new Date(ts)
    if (Number.isNaN(d.getTime())) return null
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

const card = {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 12,
    padding: '16px 20px',
    margin: '24px 0',
    textAlign: 'left',
}

export default function ReadingLog({ userId, onSaved }) {
    const [books, setBooks] = useState(null)
    const [failed, setFailed] = useState(false)
    const [editingId, setEditingId] = useState(null)
    const [draft, setDraft] = useState({ started: '', finished: '' })
    const [error, setError] = useState('')
    const [saving, setSaving] = useState(false)
    const [reloadKey, setReloadKey] = useState(0)

    useEffect(() => {
        let cancelled = false
        fetch(`${API}/reading-log/${userId}`)
            .then((res) => {
                if (!res.ok) throw new Error(String(res.status))
                return res.json()
            })
            .then((json) => {
                if (!cancelled) { setBooks(Array.isArray(json?.books) ? json.books : []); setFailed(false) }
            })
            .catch((e) => {
                if (!cancelled) { console.error('reading log failed', e); setFailed(true) }
            })
        return () => { cancelled = true }
    }, [userId, reloadKey])

    function startEdit(b) {
        setEditingId(b.id)
        setDraft({ started: inputDay(b.started_at), finished: inputDay(b.finished_at) })
        setError('')
    }

    async function save(b) {
        const body = { user_id: userId, book_id: b.id, today: localDateISO() }
        if (draft.started !== inputDay(b.started_at)) body.started_on = draft.started || null
        if (draft.finished !== inputDay(b.finished_at)) {
            if (!draft.finished) { setError('A finished book needs a finish date.'); return }
            body.finished_on = draft.finished
        }
        if (!('started_on' in body) && !('finished_on' in body)) {setEditingId(null); return }

        setSaving(true)
        setError('')
        try {
            const res = await fetch(`${API}/reading-dates`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            })
            if (!res.ok) {
                const detail = await res.json().catch(() => ({}))
                throw new Error(typeof detail.detail === 'string' ? detail.detail : 'Could not save those dates.')
            }
            setEditingId(null)
            setReloadKey((k) => k + 1)
            if (onSaved) onSaved()
        } catch (e) {
            setError(e.message)
        } finally {
            setSaving(false)
        }
    }

    if (failed) {
        return <p style={{ color: 'var(--danger)' }}>Couldn't load your reading log right now.</p>
    }
    if (!books) return null

    const today = localDateISO()

    return (
        <details style={card}>
            <summary style={{ cursor: 'pointer', fontWeight: 600 }}>
                Reading log: add or fix dates ({books.length} finished)
            </summary>
            <p style={{ color: 'var(--text-muted)', margin: '8px 0 0', fontSize: '0.9em' }}>
                Read these before using Salamander? Set when you started and finished each book. Your goal
                and average time to finish use these dates.
            </p>
            {books.length === 0 ? (
                <p>No finished books yet.</p>
            ) : (
                <div style={{ maxHeight: 420, overflowY: 'auto', marginTop: 12, paddingRight: 8 }}>
                    {books.map((b) => (
                        <div key={b.id} style={{ borderTop: '1px solid var(--border)', padding: '10px 0' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                                <div style={{ flex: '1 1 200px', minWidth: 0 }}>
                                    <strong>{b.title}</strong>
                                    <div style={{ color: 'var(--text-muted)', fontSize: '0.85em' }}>{b.author}</div>
                                </div>
                                {editingId !== b.id && (
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap', fontSize: '0.9em', flex: '0 0 auto', maxWidth: '100%' }}>
                                        <span>Started: {showDay(b.started_at) || 'not set'}</span>
                                        <span>Finished: {showDay(b.finished_at) || 'no date'}</span>
                                        <button onClick={() => startEdit(b)}>Edit dates</button>
                                    </div>
                                )}
                            </div>
                            {editingId === b.id && (
                                <form
                                    onSubmit={(e) => { e.preventDefault(); save(b) }}
                                    style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', marginTop: 10 }}
                                >
                                    <label>
                                        Started{' '}
                                        <input type="date" max={today} value={draft.started}
                                            onChange={(e) => setDraft({ ...draft, started: e.target.value })} />
                                    </label>
                                    <label>
                                        Finished{' '}
                                        <input type="date" max={today} value={draft.finished}
                                            onChange={(e) => setDraft({ ...draft, finished: e.target.value })} />
                                    </label>
                                    <button type="submit" disabled={saving}>Save</button>
                                    <button type="button" onClick={() =>{ setEditingId(null); setError('') }}>Cancel</button>
                                </form>
                            )}
                            {editingId === b.id && error && (
                                <p style={{ color: 'var(--danger)', margin: '8px 0 0' }}>{error}</p>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </details>
    )
}