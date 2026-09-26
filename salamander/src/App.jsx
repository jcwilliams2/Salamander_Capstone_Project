import { useState, useEffect } from 'react'
import { supabase } from './lib/supabaseClient'
import Signup from './components/Signup'
import Login from './components/Login'
import Onboarding from './components/Onboarding'
import './App.css'

function App() {
  const [session, setSession] = useState(null)
  const [showSignup, setShowSignup] = useState(true)
  const [onboardingComplete, setOnbardingComplete] = useState(false)
  const [recommendations, setRecommendations] = useState([])

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session))
    
    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
    })

    return () => listener.subscription.unsubscribe()
  }, [])

  function handleOnboardingComplete(recs) {
    setRecommendations(recs)
    setOnbardingComplete(true)
  }

  if (!session) {
    return showSignup ? (
      <Signup onSuccess={() => {}} switchToLogin={() => setShowSignup(false)} />
    ) : (
      <Login onSuccess={() => {}} switchToSignup={() => setShowSignup(true)} />
    )
  }

  if (!onboardingComplete) {
    return <Onboarding onComplete={handleOnboardingComplete} />
  }

  return (
      <div>
        <p>Logged in as {session.user.email}</p>
        <button onClick={() => supabase.auth.signOut()}>Log out</button>

        <h2>Your recommendations</h2>
        {recommendations.map((book) => (
          <div key={book.id} style={{ marginBottom: '12px' }}>
            <strong>{book.title}</strong> by {book.author}
            <p style={{ fontSize: '0.9em', color: '#666' }}>{book.explanation}</p>
          </div>
        ))}
      </div>
    )
}

export default App
