import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

const API = 'http://localhost:8000'

const SCALE = ['Strongly disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly agree']

const ITEMS = [
    { id: 'r1', text: 'The books recommended to me matched my reading interests.' },
    { id: 'r2', text: 'I would be interested in reading many of the recommended books.' },
    { id: 'r3', text: 'The recommendations fit the tastes I told the app about.' },
    { id: 'n1', text: 'The app recommended books I had not heard of before.' },
    { id: 'n2', text: "The recommendations introduced me to authors or genres I don't usually read." },
    { id: 'n3', text: 'I discovered books I would not have found on my own.' },
    { id: 'd1', text: 'The recommended books covered a variety of genres and topics.' },
    { id: 'd2', text: 'The recommended books were by a variety of different authors.' },
    { id: 'd3', text: 'The recommendations felt too similar to each other.' },
    { id: 'd4', text: 'The list offered a good mix of familiar and unfamiliar books.' },
    { id: 's1', text: 'Overall, I am satisfied with the recommendations I received.' },
    { id: 's2', text: 'The recommendations helped me decide what to read next.' },
    { id: 's3', text: 'I would use an app like this to find books to read.' },
    { id: 'attn', text: 'To show you are paying attention, please select "Agree" for this item.' },
]

function shuffled(list) {
    const copy = [...list]
    for (let i = copy.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1))
        ;[copy[i], copy[j]] = [copy[j], copy[i]]
    }
    return copy
}

function SurveyPage({ userId }) {
    const [progress, setProgress] = useState(null)
    const [items] = useState(() => shuffled(ITEMS))
    const [answers, setAnswers] = useState({})
    const [busy, setBusy] = useState(false)
    const [error, setError] = useState('')
    const [done, setDone] = useState(false)

    useEffect(() => {
        fetch(`${API}/study/progress/${userId}`)
            .then((res) => res.json())
            .then(setProgress)
            .catch((err) => {
                console.error('Failed to load survey progress', err)
                setProgress({ failed: true })
            })
    }, [userId])

    async function submit(e) {
        e.preventDefault()
        setBusy(true)
        setError('')
        try {
            const res = await fetch(`${API}/study/survey`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId, answers }),
            })
            const data = await res.json().catch(() => ({}))
            if (!res.ok) throw new Error(data.detail || 'Could not submit your answers.')
            setDone(true)
        } catch (err) {
            setError(err.message)
        } finally {
            setBusy(false)
        }
    }

    if (!progress) return <p>Loading...</p>
    if (progress.failed) return <p style={{ color: 'red' }}>We couldn't load the survey. Please refresh the page.</p>

    if (done || progress.survey_done) {
        return (
            <div style={{ maxWidth: '640px', margin: '32px auto', textAlign: 'center' }}>
                <h2>Thank you</h2>
                <p>Your responses have been recorded and your session is complete. You can now close this page.</p>
            </div>
        )
    }

    if (progress.rated < progress.required) {
        return (
            <div style={{ maxWidth: '640px', margin: '32px auto', textAlign: 'center' }}>
                <h2>Almost there</h2>
                <p>
                    Please mark {progress.required - progress.rated} more book
                    {progress.required - progress.rated === 1 ? '' : 's'} before the survey, using the vote buttons on
                    the books you see.
                </p>
                <Link to="/">Back to my recommendations</Link>
            </div>
        )
    }

    const complete = Object.keys(answers).length === items.length

    return (
        <form onSubmit={submit} style={{ maxWidth: '720px', margin: '0 auto', textAlign: 'left' }}>
            <h2 style={{ textAlign: 'center' }}>A few questions</h2>
            <p>
                Think about the books recommended to you in this app. For each statement, choose how much you agree.
                There are no right or wrong answers.
            </p>

            {items.map((item, index) => (
                <fieldset key={item.id} style={{ margin: '16px 0', border: '1px solid #ddd', borderRadius: '8px' }}>
                    <legend>{index + 1}. {item.text}</legend>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px' }}>
                        {SCALE.map((label, i) => (
                            <label key={label}>
                                <input
                                    type="radio"
                                    name={item.id}
                                    value={i + 1}
                                    checked={answers[item.id] === i + 1}
                                    onChange={() => setAnswers((prev) => ({ ...prev, [item.id]: i + 1 }))}
                                />{' '}
                                {label}
                            </label>
                        ))}
                    </div>
                </fieldset>
            ))}

            {error && <p style={{ color: 'red' }}>{error}</p>}
            <div style={{ textAlign: 'center' }}>
                <button type="submit" disabled={!complete || busy}>
                    {busy ? 'Submitting...' : 'Submit'}
                </button>
                {!complete && <p>{items.length - Object.keys(answers).length} questions left</p>}
            </div>
        </form>
    )
}

export default SurveyPage