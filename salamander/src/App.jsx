import { useState, useEffect } from 'react'
import { supabase } from './lib/supabaseClient'
import Signup from './components/Signup'
import Login from './components/Login'
import Onboarding from './components/Onboarding'
import VoteControls from './components/VoteControls'
import StatusSelector from './components/StatusSelector'
import './App.css'

function App() {
  const [session, setSession] = useState(null)
  const [showSignup, setShowSignup] = useState(true)
  const [onboardingComplete, setOnboardingComplete] = useState(false)
  const [onboardingChecked, setOnboardingChecked] = useState(false)
  const [recommendations, setRecommendations] = useState([])

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session))
    
    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
      if (!session) {
        setOnboardingComplete(false)
        setOnboardingChecked(false)
        setRecommendations([])
      }
    })

    return () => listener.subscription.unsubscribe()
  }, [])

  useEffect(() => {
    if (!session) return

    fetch(`http://localhost:8000/user-onboarding-status/${session.user.id}`)
      .then((res) => res.json())
      .then((data) => {
        setOnboardingComplete(data.onboarding_completed)
      })
      .catch((err) => console.error('Failed to check onboarding status', err))
      .finally(() => setOnboardingChecked(true))
  }, [session])

  useEffect(() => {
    if (!onboardingComplete || recommendations.length > 0) return

    fetch('http://localhost:8000/recommendations/returning-no-history')
      .then((res) => res.json())
      .then((data) => setRecommendations(data.recommendations))
      .catch((err) => console.error('Failed to load returning-user feed', err))
  }, [onboardingComplete, recommendations.length])

  function handleOnboardingComplete(recs) {
    setRecommendations(recs)
    setOnboardingComplete(true)
  }

  if (!session) {
    return showSignup ? (
      <Signup onSuccess={() => {}} switchToLogin={() => setShowSignup(false)} />
    ) : (
      <Login onSuccess={() => {}} switchToSignup={() => setShowSignup(true)} />
    )
  }

  if (!onboardingChecked) {
    return <p>Loading...</p>
  }

  if (!onboardingComplete) {
    return <Onboarding userId={session.user.id} onComplete={handleOnboardingComplete} />
  }

  return (
      <div>
        <p>Logged in as {session.user.email}</p>
        <button onClick={() => supabase.auth.signOut()}>Log out</button>

        <h2>Your recommendations</h2>
        {recommendations.map((book) => (
          <div key={book.id || book.isbn} style={{ marginBottom: '12px' }}>
            {book.cover_url &&  (
              <img src={book.cover_url} alt={book.title} style={{ height: '120px' }} />
            )}
            <div>
              <strong>{book.title}</strong> by {book.author}
            </div>
            <p style={{ fontSize: '0.9em', color: '#666' }}>{book.explanation}</p>
            {book.id && (
              <>
                <VoteControls userId={session.user.id} bookId={book.id} />
                <StatusSelector userId={session.user.id} bookId={book.id} />
              </>
            )}
          </div>
        ))}
      </div>
    )
}

export default App
