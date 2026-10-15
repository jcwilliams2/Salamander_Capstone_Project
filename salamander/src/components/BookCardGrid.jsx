import { useState } from 'react'
import VoteControls from './VoteControls'
import StatusSelector from './StatusSelector'

function Cover({ url, title }) {
    const [failed, setFailed] = useState(false)
    if (!url || failed) {
        return (
            <div style={{ height: '180px', width: '120px', margin: '0 auto', border: '1px solid #ccc', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                No cover
            </div>
        )
    }
    return <img src={url} alt={title} onError={() => setFailed(true)} style={{ height: '180px' }} />
}

function BookCardGrid({ books, userId, onStatusChange }) {
    return (
        <div
            style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
                gap: '24px',
                maxWidth: '960px',
                margin: '0 auto',
                textAlign: 'center',
            }}
        >
            {books.map((book) => (
                <div 
                    key={book.id || book.isbn} 
                    style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}
                    onChange={(e) => {
                        if (e.target.tagName === 'SELECT') onStatusChange?.(book, e.target.value)
                    }}
                >
                    <Cover url={book.cover_url} title={book.title} />
                    <div><strong>{book.title}</strong></div>
                    <div>{book.author}</div>
                    <p style={{ fontSize: '0.9em', color: '#666' }}>{book.explanation}</p>
                    {book.id && (
                        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginTop: 'auto' }}>
                            <VoteControls userId={userId} bookId={book.id} initialVote={book.vote} />
                            <StatusSelector userId={userId} bookId={book.id} initialStatus={book.status} />
                        </div>
                    )}
                </div>
            ))}
        </div>
    )
}

export default BookCardGrid