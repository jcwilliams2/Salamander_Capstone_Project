import { useState } from 'react'

const UP_COLOR = '#0b9c40'
const DOWN_COLOR = '#d40f0f'

function ThumbUPIcon({ active }) {
    const color = active ? UP_COLOR : 'black'
    return (
        <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill={active ? color : 'none'}
            stroke={color}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
        >
            <g transform="rotate(180 12 12)">
                <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zM17 2h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3" />
            </g>
        </svg>
    )
}

function ThumbDownIcon({ active }) {
    const color = active ? DOWN_COLOR : 'black'
    return (
        <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill={active ? color : 'none'}
            stroke={color}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
        >
            <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zM17 2h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3" />
        </svg>
    )
}

function VoteControls({ userId, bookId, initialVote = 0 }) {
    const [vote, setVote] = useState(initialVote)
    const [loading, setLoading] = useState(false)

    async function castVote(newVote) {
        const finalVote = vote === newVote ? 0 : newVote
        setLoading(true)
        try {
            await fetch('http://localhost:8000/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId, book_id: bookId, vote: finalVote }),
            })
            setVote(finalVote)
        } catch (err) {
            console.error('Failed to record vote', err)
        } finally {
            setLoading(false)
        }
    }

    const buttonStyle = {
        background: 'none',
        border: 'none',
        padding: '4px',
        cursor: 'pointer',
        opacity: loading ? 0.5 : 1,
    }

    return (
        <div style={{ display: 'flex', gap: '8px' }}>
            <button
                onClick={() => castVote(1)}
                disabled={loading}
                aria-label="Upvote"
                style={buttonStyle}
            >
                <ThumbUPIcon active={vote === 1} />
            </button>
            <button
                onClick={() => castVote(-1)}
                disabled={loading}
                aria-label="Downvote"
                style={buttonStyle}
            >
                <ThumbDownIcon active={vote === -1} />
            </button>
        </div>
    )
}

export default VoteControls