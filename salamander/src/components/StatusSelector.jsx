import { API } from '../lib/api'
import { useState } from 'react'

const STATUS_OPTIONS = [
    { value: 'want_to_read', label: 'Want to Read' },
    { value: 'reading', label: 'Reading' },
    { value: 'finished', label: 'Finished' },
    { value: 'dnf', label: 'Did Not Finish' },
]

const STATUS_COLOR = {
    want_to_read: 'var(--status-want)',
    reading: 'var(--status-reading)',
    finished: 'var(--status-finished)',
    dnf: 'var(--status-dnf)',
}

function StatusSelector({ userId, bookId, initialStatus = '', status: controlledStatus, onStatusChange }) {
    const [ownstatus, setOwnStatus] = useState(initialStatus)
    const [loading, setLoading] = useState(false)
    const status = controlledStatus ?? ownstatus

    async function handleChange(e) {
        const newStatus = e.target.value
        setLoading(true)
        try {
            const res = newStatus === ''
                ? await fetch(`${API}/reading-status`, {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: userId, book_id: bookId }),
                })
                : await fetch(`${API}/reading-status`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: userId, book_id: bookId, status: newStatus }),
                })
            if (!res.ok) throw new Error(`Unexpected response (${res.status})`)
            setOwnStatus(newStatus)
            if (onStatusChange) onStatusChange(newStatus)
        } catch (err) {
            console.error('Failed to update status', err)
        } finally {
            setLoading(false)
        }
    }

    return (
        <select 
            value={status}
            onChange={handleChange} 
            disabled={loading}
            style={status ? { borderLeft: `5px solid ${STATUS_COLOR[status]}` } : undefined}
        >
            <option value="">Set status</option>
            {STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
        </select>
    )
}

export default StatusSelector