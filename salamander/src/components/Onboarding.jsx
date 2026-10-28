import { useState } from 'react'

const GENRE_OPTIONS = [
    'fantasy', 'science fiction', 'mystery', 'thriller', 'romance', 'horror',
  'historical fiction', 'literary fiction', 'biography', 'memoir',
  'young adult', 'childrens', 'poetry', 'graphic novel', 'self help',
  'history', 'science', 'philosophy', 'religion', 'business',
  'true crime', 'crime fiction', 'humor', 'cooking', 'travel',
  'psychology', 'politics', 'sports', 'nonfiction', 'social science', 'art',
]

const MIN_GENRES_STUDY = 3

function Onboarding({ userId, onComplete, required = false }) {
    const minGenres = required ? MIN_GENRES_STUDY : 1
    const [selectedGenres, setSelectedGenres] = useState([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')

    function toggleGenre(genre) {
        setSelectedGenres((prev) =>
            prev.includes(genre) ? prev.filter((g) => g !== genre) : [...prev, genre]
        )
    }

    async function handleSubmit() {
        setLoading(true)
        setError('')

        try {
            const response = await fetch('http://localhost:8000/recommendations/onboarding', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ selected_genres: selectedGenres }),
            })
            
            if (!response.ok) {
                throw new Error('Failed to get recommendations')
            }

            const data = await response.json()

            await fetch('http://localhost:8000/complete-onboarding', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId, selected_genres: selectedGenres }),
            })

            onComplete(data.recommendations)
        } catch (err) {
            console.error('Onboarding request failed:', err)
            setError('Something went wrong. Please try again.')
        } finally {
            setLoading(false)
        }
    }

    async function handleSkip() {
        setLoading(true)
        setError('')

        try {
            const response = await fetch('http://localhost:8000/recommendations/onboarding', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({}),
            })

            const data = await response.json()

            await fetch('http://localhost:8000/complete-onboarding', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId, selected_genres: [] }),
            })

            onComplete(data.recommendations)
        } catch (err) {
            console.error('Onboarding request failed:', err)
            setError('Something went wrong. Please try again.')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div>
            <h2>What do you like to read?</h2>
            <p>{required
                    ? `Pick at least ${MIN_GENRES_STUDY} genres to get tailored recommendations.`
                    : 'Pick a few genres to get tailored recommendations, or skip for now.'}
            </p>

            {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', margin: '16px 0' }}>
                {GENRE_OPTIONS.map((genre) => (
                    <button
                        key={genre}
                        type="button"
                        onClick={() => toggleGenre(genre)}
                        style={{
                            padding: '6px 12px',
                            borderRadius: '16px',
                            border: selectedGenres.includes(genre) ? '2px solid var(--primary)' : '1px solid var(--border)',
                            background: selectedGenres.includes(genre) ? 'var(--surface-alt)' : 'var(--surface)',
                            cursor: 'pointer',
                        }}
                    >
                        {genre}
                    </button>
                ))}
            </div>

            <button onClick={handleSubmit} disabled={loading || selectedGenres.length < minGenres}>
                {loading ? 'Loading...' : 'Get Recommendations'}
            </button>
            {required &&  selectedGenres.length < minGenres && (
                <span style={{ marginLeft: '8px' }}>
                    {minGenres - selectedGenres.length} more to go
                </span>
            )}
            {!required && (
                <button onClick={handleSkip} disabled={loading} style={{ marginLeft: '8px' }}>
                    Skip for now
                </button>)
            }
        </div>
    )
}

export default Onboarding