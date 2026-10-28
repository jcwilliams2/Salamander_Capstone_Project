import { useState, useEffect, useRef } from 'react'
import { THEMES, applyTheme, getCachedTheme, cacheTheme } from '../theme/themes'

const API = 'http://localhost:8000'

export default function ThemePicker({ userId }) {
    const [theme, setTheme] = useState(getCachedTheme)
    const chosenByUser = useRef(false)

    useEffect(() => {
        const controller = new AbortController()
        fetch(`${API}/user-settings/${userId}`, { signal: controller.signal })
            .then((res) => {
                if (!res.ok) throw new Error(`Unexpected response (${res.status})`)
                return res.json()
            })
            .then((data) => {
                if (chosenByUser.current) return
                const applied = applyTheme(data.theme)
                cacheTheme(applied)
                setTheme(applied)
            })
            .catch((err) => {
                if (err.name === 'AbortError') return
                console.error('Failed to load theme', err)
            })
        return () => controller.abort()
    }, [userId])

    function choose(e) {
        chosenByUser.current = true
        const applied = applyTheme(e.target.value)
        cacheTheme(applied)
        setTheme(applied)

        fetch(`${API}/user-settings/theme`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, theme: applied }),
        })
            .then((res) => {
                if (!res.ok) throw new Error(`Unexpected response (${res.status})`)
            })
            .catch((err) => console.error('Failed to save theme', err))
    }

    return (
        <label style={{ display: 'inline-flex', gap: 6, alignItems: 'center', color: 'var(--text-muted)', fontSize: 14 }}>
            Theme
            <select
                value={theme}
                onChange={choose}
                style={{
                    background: 'var(--input-bg)', color: 'var(--text)',
                    border: '1px solid var(--border)', borderRadius: 6, padding: '4px 8px',
                }}
            >
                {Object.entries(THEMES).map(([id, t]) => (
                    <option key={id} value={id}>{t.label}</option>
                ))}
            </select>
        </label>
    )
}