import { useState } from 'react'

const GENRE_OPTIONS = [
    'fantasy', 'science fiction', 'mystery', 'thriller', 'romance', 'horror',
  'historical fiction', 'literary fiction', 'biography', 'memoir',
  'young adult', 'childrens', 'poetry', 'graphic novel', 'self help',
  'history', 'science', 'philosophy', 'religion', 'business',
  'true crime', 'crime fiction', 'humor', 'cooking', 'travel',
  'psychology', 'politics', 'sports', 'nonfiction'
]

function Onboarding({ onComplete }) {
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
            onComplete(data.recommendations)
        } catch (err) {
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
            onComplete(data.recommendations)
        } catch (err) {
            setError('Something went wrong. Please try again.')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div>
            <h2>What do you like to read?</h2>
            <p>Pick a few genres to get tailored recommendations, or skip for now.</p>

            {error && <p style={{ color: 'red' }}>{error}</p>}

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', margin: '16px 0' }}>
                {GENRE_OPTIONS.map((genre) => (
                    <button
                        key={genre}
                        type="button"
                        onClick={() => toggleGenre(genre)}
                        style={{
                            padding: '6px 12px',
                            borderRadius: '16px',
                            border: selectedGenres.includes(genre) ? '2px solid black' : '1px solid #ccc',
                            background: selectedGenres.includes(genre) ? '#eee' : 'white',
                            cursor: 'pointer',
                        }}
                    >
                        {genre}
                    </button>
                ))}
            </div>

            <button onClick={handleSubmit} disabled={loading || selectedGenres.length === 0}>
                {loading ? 'Loading...' : 'Get Recommendations'}
            </button>
            <button onClick={handleSkip} disabled={loading} style={{ marginLeft: '8px' }}>
                Skip for now
            </button>
        </div>
    )
}

export default Onboarding