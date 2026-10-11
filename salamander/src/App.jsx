import { useState, useEffect, useRef } from 'react'
import { supabase } from './lib/supabaseClient'
import { EXPLORE_LEVELS } from './lib/exploreLevels'
import Signup from './components/Signup'
import Login from './components/Login'
import Onboarding from './components/Onboarding'
import { Routes, Route, NavLink, Navigate } from 'react-router-dom'
import CatalogPage from './components/CatalogPage'
import BookCardGrid from './components/BookCardGrid'
import DiversityPicks from './components/DiversityPicks'
import ExplorationControl from './components/ExplorationControl'
import './App.css'

const navStyle = ({ isActive }) => ({ fontWeight: isActive ? 'bold' : 'normal'})

function App() {
  const [session, setSession] = useState(null)
  const [showSignup, setShowSignup] = useState(true)
  const [onboardingComplete, setOnboardingComplete] = useState(false)
  const [onboardingChecked, setOnboardingChecked] = useState(false)
  const [recommendations, setRecommendations] = useState([])
  const [explore, setExplore] = useState(0)
  const requestId = useRef(0)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session))
    
    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
      if (!session) {
        setOnboardingComplete(false)
        setOnboardingChecked(false)
        setRecommendations([])
        setExplore(0)
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
    if (!session || !onboardingComplete || recommendations.length > 0) return

    fetch(`http://localhost:8000/recommendations/personalized/${session.user.id}`)
      .then(async (res) => {
        const data = await res.json().catch(() => null)
        if (!res.ok || !Array.isArray(data?.recommendations)) {
          throw new Error(`Unexpected response (${res.status})`)
        }
        setRecommendations(data.recommendations)
      })
      .catch((err) => console.error('Failed to load recommendations', err))
  }, [session, onboardingComplete, recommendations.length])

  function handleOnboardingComplete(recs) {
    setRecommendations(recs)
    setOnboardingComplete(true)
  }

  function handleExploreChange(index) {
    setExplore(index)
    const mine = ++requestId.current
    fetch(`http://localhost:8000/recommendations/personalized/${session.user.id}?explore=${EXPLORE_LEVELS[index].value}`)
      .then(async (res) => {
        const data = await res.json().catch(() => null)
        if (!res.ok || !Array.isArray(data?.recommendations)) {
          throw new Error(`Unexpected response (${res.status})`)
        }
        if (mine === requestId.current) setRecommendations(data.recommendations)
      })
      .catch((err) => console.error('Failed to update recommendations', err))
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
        <nav style={{ display: 'flex', gap: '16px', alignItems: 'center', justifyContent: 'center', marginBottom: '16px' }}>
          <strong>Salamander</strong>
          <NavLink to="/" end style={navStyle}>Recommendations</NavLink>
          <NavLink to="/catalog" style={navStyle}>Catalog</NavLink>
          <span>{session.user.email}</span>
          <button onClick={() => supabase.auth.signOut()}>Log out</button>
        </nav>
        
        <Routes>
          <Route
            path="/"
            element={
              <div>
                <h2>Your Recommendations</h2>
                {recommendations.some((b) => b.id) && (
                  <ExplorationControl level={explore} onChange={handleExploreChange} />
                )}
                <BookCardGrid books={recommendations} userId={session.user.id} />
                <DiversityPicks userId={session.user.id} />
              </div>
            }
          />
          <Route path="/catalog" element={<CatalogPage userId={session.user.id} />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    )
}

export default App
