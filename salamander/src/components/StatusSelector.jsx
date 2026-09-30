import { useState } from 'react'

const STATUS_OPTIONS = [
    { value: 'want_to_read', label: 'Want to Read' },
    { value: 'reading', label: 'Reading' },
    { value: 'finished', label: 'Finished' },
    { value: 'dnf', label: 'Did Not Finish' },
]

function StatusSelector({ userId, bookId, initialStatus = '' }) {
    const [status, setStatus] = useState(initialStatus)
    const [loading, setLoading] = useState(false)

    async function handleChange(e) {
        const newStatus = e.target.value
        setLoading(true)
        try {
            if (newStatus === '') {
                await fetch('http://localhost:8000/reading-status', {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: userId, book_id: bookId }),
                })
            } else {
                await fetch('http://localhost:8000/reading-status', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: userId, book_id: bookId, status: newStatus }),
                })
            }
            setStatus(newStatus)
        } catch (err) {
            console.error('Failed to update status', err)
        } finally {
            setLoading(false)
        }
    }

    return (
        <select value={status} onChange={handleChange} disabled={loading}>
            <option value="">Set status</option>
            {STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
        </select>
    )
}

export default StatusSelector