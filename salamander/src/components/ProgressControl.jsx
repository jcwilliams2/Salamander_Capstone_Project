import { useState } from 'react'
import { API } from '../lib/api'
import ProgressBar from './ProgressBar'
import { describeProgress } from '../lib/progress'

const muted = { color: 'var(--text-muted)', fontSize: '0.9em' }
const toggle = (on) => ({ fontWeight: on ? 700 : 400, borderColor: on ? 'var(--status-reading)' : undefined })

function ProgressControl({ userId, bookId, pageCount, percent, page, onSaved }) {
    const [editing, setEditing] = useState(false)
    const [mode, setMode] = useState(pageCount ? 'page' : 'percent')
    const [value, setValue] = useState('')
    const [busy, setBusy] = useState(false)
    const [error, setError] = useState('')

    function startEditing() {
        const start = mode === 'page' ? page : percent
        setValue(start == null ? '' : String(start))
        setError('')
        setEditing(true)
    }

    function chooseMode(next) {
        setMode(next)
        const start = next === 'page' ? page : percent
        setValue(start == null ? '' : String(start))
        setError('')
    }

    async function save(e) {
        e.preventDefault()
        const n = Number(value)
        if (value.trim() === '' || !Number.isInteger(n)) {
            setError('Enter a whole number.')
            return
        }
        setBusy(true)
        setError('')
        try {
            const res = await fetch(`${API}/reading-progress`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId, book_id: bookId, [mode]: n }),
            })
            const data = await res.json().catch(() => null)
            if (!res.ok) {
                setError(typeof data?.detail === 'string' ? data.detail : 'Could not save your progress. Please try again.')
                return
            }
            onSaved({ percent: data.progress_percent, page: data.current_page })
            setEditing(false)
        } catch (err) {
            console.error('Failed to save progress', err)
            setError('Could not save your progress. Please try again.')
        } finally {
            setBusy(false)
        }
    }

    return (
        <div style={{ maxWidth: 360 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 6 }}>
                <span style={{ fontWeight: 600, color: 'var(--status-reading)' }}>Your progress</span>
                <span style={muted}>{describeProgress(percent, page, pageCount)}</span>
            </div>
            <ProgressBar percent={percent ?? 0} label="Reading progress" />

            {!editing && (
                <button type="button" onClick={startEditing} style={{ marginTop: 10 }}>Update progress</button>
            )}

            {editing && (
                <form onSubmit={save} noValidate style={{ marginTop: 10 }}>
                    {pageCount ? (
                        <div role="group" aria-label="Enter progress as" style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
                            <button type="button" aria-pressed={mode === 'page'} onClick={() => chooseMode('page')} style={toggle(mode === 'page')}>Page</button>
                            <button type="button" aria-pressed={mode === 'percent'} onClick={() => chooseMode('percent')} style={toggle(mode === 'percent')}>Percent</button>
                        </div>
                    ) : (
                        <p style={{ ...muted, margin: '0 0 8px' }}>We don't have a page count for this book, so enter a percent.</p>
                    )}
                    <label style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                        <span>{mode === 'page' ? `Page (of ${pageCount})` : 'Percent'}</span>
                        <input
                            type="number"
                            inputMode="numeric"
                            min={0}
                            max={mode === 'page' ? pageCount : 100}
                            step={1}
                            value={value}
                            onChange={(e) => setValue(e.target.value)}
                            style={{ width: 90 }}
                        />
                    </label>
                    <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                        <button type="submit" disabled={busy}>{busy ? 'Saving...' : 'Save'}</button>
                        <button type="button" onClick={() => setEditing(false)} disabled={busy}>Cancel</button>
                    </div>
                    {error && <p role="alert" style={{ color: 'var(--danger)', margin: '8px 0 0' }}>{error}</p>}
                </form>
            )}

            {!editing && percent === 100 && (
                <p style={{ ...muted, margin: '8px 0 0' }}>That's the whole book. Set your status to Finished when you're done.</p>
            )}
        </div>
    )
}

export default ProgressControl