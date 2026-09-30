import { useState } from 'react'

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

    return (
        <div style={{ display: 'flex', gap: '8px' }}>
            <button
                onClick={() => castVote(1)}
                disabled={loading}
                style={{
                    fontWeight: vote === 1 ? 'bold' : 'normal',
                    color: vote === 1 ? 'green' : 'black',
                }}
            >
                like
            </button>
            <button
                onClick={() => castVote(-1)}
                disabled={loading}
                style={{
                    fontWeight: vote === -1 ? 'bold' : 'normal',
                    color: vote === -1 ? 'red' : 'black',
                }}
            >
                unlike
            </button>
        </div>
    )
}

export default VoteControls