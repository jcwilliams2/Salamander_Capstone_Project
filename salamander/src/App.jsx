import { useState, useEffect } from 'react'
import { supabase } from './lib/supabaseClient'
import Signup from './components/Signup'
import Login from './components/Login'
import './App.css'

function App() {
  const [session, setSession] = useState(null)
  const [showSignup, setShowSignup] = useState(true)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session))
    
    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
    })

    return () => listener.subscription.unsubscribe()
  }, [])

  if (session) {
    return (
      <div>
        <p>Logged in as {session.user.email}</p>
        <button onClick={() => supabase.auth.signOut()}>Log out</button>
      </div>
    )
  }

  return showSignup ? (
    <Signup onSuccess={() => {}} switchToLogin={() => setShowSignup(false)} />
  ) : (
    <Login onSuccess={() => {}} switchToSignup={() => setShowSignup(true)} />
  )
}

export default App
