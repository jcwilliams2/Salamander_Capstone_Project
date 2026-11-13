import { useState, useEffect } from 'react'
import { API } from '../lib/api'

function DigestFrequencyPicker({ userId }) {
    const [state, setState] = useState({ options: [], frequency: '' })

    useEffect(() => {
        const controller = new AbortController()
        fetch(`${API}/digest-settings/${userId}`, { signal: controller.signal })
            .then(async (res) => {
                const data = await res.json().catch(() => null)
                if (!res.ok || !Array.isArray(data?.options)) throw new Error(`Unexpected response (${res.status})`)
                setState({ options: data.options, frequency: data.frequency })
            })
            .catch((err) => {
                if (err.name === 'AbortError') return
                console.error('Failed to load digest settings', err)
            })
        return () => controller.abort()
    }, [userId])

    function change(event) {
        const next = event.target.value
        const previous = state.frequency
        setState((s) => ({ ...s, frequency: next }))
        fetch(`${API}/digest-settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, frequency: next }),
        })
            .then((res) => {
                if (!res.ok) throw new Error(`Unexpected response (${res.status})`)
            })
            .catch((err) => {
                console.error('Failed to save digest setting', err)
                setState((s) => ({ ...s, frequency: previous }))
            })
    }

    if (state.options.length === 0) return null

    return (
        <label style={{ display: 'inline-flex', gap: 6, alignItems: 'center', color: 'var(--text-muted)', fontSize: 14 }}>
            Send me a digest
            <select value={state.frequency} onChange={change} aria-label="How often to get your variety digest">
                {state.options.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                ))}
            </select>
        </label>
    )
}

export default DigestFrequencyPicker