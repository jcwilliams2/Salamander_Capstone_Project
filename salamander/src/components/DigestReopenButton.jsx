import { useState } from 'react'
import { API } from '../lib/api'

function DigestReopenButton({ userId }) {
    const [message, setMessage] = useState('')
    const [busy, setBusy] = useState(false)

    async function reopen() {
        setBusy(true)
        setMessage('')
        try {
            const res = await fetch(`${API}/digest/reopen`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId }),
            })
            if (res.status === 404) {
                setMessage("You don't have a digest yet. One appears after you've finished or stopped at least 3 books.")
            } else if (!res.ok) {
                throw new Error(`Unexpected response (${res.status})`)
            } else {
                window.dispatchEvent(new Event('digest-reopened'))
                setMessage('Your latest digest is back at the top of the page.')
            }
        } catch (err) {
            console.error('Failed to reopen your digest', err)
            setMessage("Couldn't show your digest just now. Please try again.")
        } finally {
            setBusy(false)
        }
    }

    return (
        <div style={{ marginTop: 12 }}>
            <button type="button" onClick={reopen} disabled={busy}>Show my latest digest again</button>
            {message && <p role="status" style={{ color: 'var(--text-muted)', fontSize: '0.9em', margin: '8px 0 0' }}>{message}</p>}
        </div>
    )
}

export default DigestReopenButton