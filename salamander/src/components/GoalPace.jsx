import { API } from '../lib/api'
import { useEffect, useState } from 'react'


function localDateISO() {
    const d = new Date()
    const mm = String(d.getMonth() + 1).padStart(2, '0')
    const dd = String(d.getDate()).padStart(2, '0')
    return `${d.getFullYear()}-${mm}-${dd}`
}

const card = {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 12,
    padding: '16px 20px',
    margin: '24px 0',
    textAlign: 'left',
}

function timeToFinishText(t) {
    if (!t || !t.books_counted) return 'Average time to finish: not enough data yet'
    const books = `${t.books_counted} ${t.books_counted === 1 ? 'book' : 'books'}`
    if (t.average_days < 1) return `Average time to finish: under a day (${books})`
    const days = Math.round(t.average_days)
    return `Average time to finish: ${days} ${days === 1 ? 'day': 'days'} (${books})`
}

export default function GoalPace({ userId, refreshKey = 0 }) {
    const [data, setData] = useState(null)
    const [failed, setFailed] = useState(false)
    const [editing, setEditing] = useState(false)
    const [draft, setDraft] = useState('')
    const [error,setError] = useState('')
    const [saving, setSaving] = useState(false)
    const [reloadKey, setReloadKey] = useState(0)

    useEffect(() => {
        let cancelled = false
        fetch(`${API}/reading-pace/${userId}?today=${localDateISO()}`)
            .then((res) => {
                if (!res.ok) throw new Error(String(res.status))
                return res.json()
            })
            .then((json) => {
                if (!cancelled) { setData(json); setFailed(false) }
            })
            .catch((e) => {
                if (!cancelled) { console.error('reading pace failed', e); setFailed(true) }
            })
        return () => { cancelled = true }
    }, [userId, reloadKey, refreshKey])

    async function saveGoal(goal) {
        setSaving(true)
        setError('')
        try {
            const res = await fetch(`${API}/reading-goal`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId, year: data.year, goal }),
            })
            if (!res.ok) {
                const body = await res.json().catch(() => ({}))
                throw new Error(body.detail || 'Could not save your goal.')
            }
            setEditing(false)
            setReloadKey((k) => k + 1)
        } catch (e) {
            setError(e.message)
        } finally {
            setSaving(false)
        }
    }

    function submit(e) {
        e.preventDefault()
        const text = draft.trim()
        if (!/^\d+$/.test(text) || Number(text) < 1) {
            setError('Enter a whole number of 1 or more, or cancel for no goal.')
            return
        }
        saveGoal(Number(text))
    }

    if (failed) {
        return <section style={card}><span style={{ color: 'var(--danger)' }}>Couldn't load your reading goal right now.</span></section>
    }
    if (!data) return null

    const { year, goal, finished, pace, time_to_finish } = data

    if (editing) {
        return (
            <section style={card} aria-label={`${year} reading goal`}>
                <form onSubmit={submit} style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                    <label>
                        Books to read in {year}{' '}
                        <input type="text" inputMode="numeric" value={draft} onChange={(e) => setDraft(e.target.value)}
                            style={{ width: 80 }} autoFocus />
                    </label>
                    <button type="submit" disabled={saving}>Save</button>
                    <button type="button" onClick={() => { setEditing(false); setError('') }}>Cancel</button>
                </form>
                {error && <p style={{ color: 'var(--danger)', margin: '8px 0 0' }}>{error}</p>}
            </section>
        )
    }

    if (goal == null || !pace) {
        return (
            <section style={card} aria-label={`${year} reading goal`}>
                <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap', justifyContent: 'space-between' }}>
                    <span><strong>{finished}</strong>{finished === 1 ? ' book' : ' books'} finished in {year}</span>
                    <button onClick={() => { setDraft(''); setError(''); setEditing(true) }}>
                        Set a {year} reading goal (optional)
                    </button>
                </div>
                <p style={{ margin: '12px 0 0', color: 'var(--text-muted)' }}>{timeToFinishText(time_to_finish)}</p>
            </section>
        )
    }

    const pct = Math.min(100, Math.round((finished / goal) * 100))
    const plural = pace.amount === 1 ? 'book' : 'books'
    let message, color
    if (pace.status === 'complete') { message = `Goal reached! 🎉`; color = 'var(--success)' }
    else if (pace.status === 'ahead') { message = `Ahead by ${pace.amount} ${plural}`; color = 'var(--success)' }
    else if (pace.status === 'behind') { message = `Behind by ${pace.amount} ${plural}`; color = 'var(--warning)' }
    else { message = 'On track'; color = 'var(--text)' }

    const expectedWhole =
        pace.status === 'ahead' ? finished - pace.amount
        : pace.status === 'behind' ? finished + pace.amount
        : finished

    return (
        <section style={card} aria-label={`${year} reading goal`}>
            <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
                <strong>{finished} of {goal} books in {year}</strong>
                <strong style={{ color }}>{message}</strong>
            </div>
            <div role="progressbar" aria-valuemin={0} aria-valuemax={goal} aria-valuenow={Math.min(finished, goal)}
                style={{ background: 'var(--surface-alt)', borderRadius: 999, height: 10, margin: '12px 0', overflow: 'hidden' }}>
                    <div style={{ width: `${pct}%`, height: '100%', background: 'var(--primary)' }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
                {pace.status !== 'complete'
                    ? <span style={{ color: 'var(--text-muted)' }}>Expected by now: {expectedWhole} (month {pace.month} of 12)</span>
                    : <span />}
                <span style={{ display: 'flex', gap: 8 }}>
                    <button onClick={() => { setDraft(String(goal)); setError(''); setEditing(true) }}>Edit goal</button>
                    <button onClick={() => saveGoal(null)} disabled={saving}>Remove goal</button>
                </span>
            </div>
            <p style={{ margin: '12px 0 0', color: 'var(--text-muted)' }}>{timeToFinishText(time_to_finish)}</p>
            {error && <p style={{ color: 'var(--danger)', margin: '8px 0 0' }}>{error}</p>}
        </section>
    )
}