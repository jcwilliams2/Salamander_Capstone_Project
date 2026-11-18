import { useState } from 'react'
import { API } from '../lib/api'

const linkButton = { background: 'transparent', border: 'none', padding: 0, color: 'var(--link)', textDecoration: 'underline', cursor: 'pointer', font: 'inherit' }

function PageCountFlag({ userId, bookId, pageCount }) {
    const [open, setOpen] = useState(false)
    const [pages, setPages] = useState('')
    const [note, setNote] = useState('')
    const [busy, setBusy] = useState(false)
    const [error, setError] = useState('')
    const [sent, setSent] = useState(false)

    async function submit(e) {
        e.preventDefault()
        const trimmed = pages.trim()
        const n = Number(trimmed)
        if (trimmed !== '' && !Number.isInteger(n)) {
            setError('Enter a whole number, or leave the page count blank.')
            return
        }
        setBusy(true)
        setError('')
        try {
            const res = await fetch(`${API}/book-flags`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: userId,
                    book_id: bookId,
                    kind: 'page_count',
                    suggested_pages: trimmed === '' ? null : n,
                    note: note.trim() === '' ? null : note,
                }),
            })
            const data = await res.json().catch(() => null)
            if (!res.ok) {
                setError(typeof data?.detail === 'string' ? data.detail : 'Could not send your report. Please try again.')
                return
            }
            setSent(true)
            setOpen(false)
        } catch (err) {
            console.error('Failed to send page count report', err)
            setError('Could not send your report. Please try again.')
        } finally {
            setBusy(false)
        }
    }

    if (sent) return <div style={{ margin: '10px 0 14px', fontSize: 14 }}>Thanks, we'll review this.</div>

    if (!open) {
        return (
            <div style={{ margin: '10px 0 14px', fontSize: 14 }}>
                <button type="button" onClick={() => setOpen(true)} style={linkButton}>
                    {pageCount ? 'Page count look wrong?' : 'Know the page count?'}
                </button>
            </div>
        )
    }

    return (
        <form onSubmit={submit} noValidate style={{ margin: '12px 0 16px', width: '100%', maxWidth: 360, boxSizing: 'border-box', padding: 12, 
            background: 'var(--surface-alt)', border: '1px solid var(--border)', borderRadius: 8
         }}>
            <p style={{ margin: '0 0 10px', fontSize: 14, lineHeight: 1.4, color: 'var(--text-muted)' }}>
                Page counts can differ between editions. Tell us what you see, and the edition if you know it.
            </p>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                <span>Page count</span>
                <input type="number" inputMode="numeric" min={10} max={5000} step={1} value={pages}
                    onChange={(e) => setPages(e.target.value)} style={{ width: 90 }} />
                <span>(optional)</span>
            </label>
            <label style={{ display: 'block', marginBottom: 8 }}>
                <span style={{ display: 'block', marginBottom: 4 }}>Edition or format (optional)</span>
                <input type="text" maxLength={300} value={note} placeholder="e.g. paperback, 2019"
                    onChange={(e) => setNote(e.target.value)} style={{ width: '100%', boxSizing: 'border-box' }} />
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
                <button type="submit" disabled={busy}>{busy ? 'Sending...' : 'Send'}</button>
                <button type="button" onClick={() => setOpen(false)} disabled={busy}>Cancel</button>
            </div>
            {error && <p role="alert" style={{ color: 'var(--danger)', margin: '8px 0 0' }}>{error}</p>}
        </form>
    )
}

export default PageCountFlag