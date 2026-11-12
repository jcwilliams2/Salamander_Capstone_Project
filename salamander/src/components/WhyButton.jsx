import { useState } from 'react'
import { API } from '../lib/api'

function WhyButton({ userId, bookId }) {
    const [state, setState] = useState({ phase: 'idle', text: '' })

    function toggle() {
        if (state.phase === 'open') {
            setState({ phase: 'idle', text: '' })
            return
        }
        setState({ phase: 'loading', text: '' })
        fetch(`${API}/explain/${encodeURIComponent(bookId)}?user_id=${encodeURIComponent(userId)}`)
            .then(async (res) => {
                const data = await res.json().catch(() => null)
                if (!res.ok || !data?.explanation) throw new Error(`Unexpected response (${res.status})`)
                return data
            })
            .then((data) => setState({ phase: 'open', text: data.explanation }))
            .catch((err) => {
                console.error('Failed to load explanation', err)
                setState({ phase: 'failed', text: '' })
            })
    }

    const label = state.phase === 'loading' ? 'Thinking...' : state.phase === 'open' ? 'Hide' : 'Why would I like this?'

    return (
        <div style={{ marginTop: '8px' }}>
            <button type="button" onClick={toggle} disabled={state.phase === 'loading'} aria-expanded={state.phase === 'open'}>
                {label}
            </button>
            <div aria-live="polite">
                {state.phase === 'open' && (
                    <p style={{ margin: '8px auto 0', maxWidth: '320px', padding: '8px 12px', background: 'var(--surface-alt)', color: 'var(--text)', borderRadius: '8px', fontSize: '0.9em', textAlign: 'left' }}>
                        {state.text}
                    </p>
                )}
                {state.phase === 'failed' && (
                    <p style={{ color: 'var(--danger)', fontSize: '0.9em' }}>Couldn't load an explanation. Please try again.</p>
                )}
            </div>
        </div>
    )
}

export default WhyButton