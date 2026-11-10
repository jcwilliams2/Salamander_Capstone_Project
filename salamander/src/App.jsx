import { API } from './lib/api'
import { useState, useEffect, useRef } from 'react'
import { supabase } from './lib/supabaseClient'
import { EXPLORE_LEVELS } from './lib/exploreLevels'
import Signup from './components/Signup'
import Login from './components/Login'
import Onboarding from './components/Onboarding'
import { Routes, Route, NavLink, Navigate, useLocation } from 'react-router-dom'
import WantToReadPage from './components/WantToReadPage'
import CatalogPage from './components/CatalogPage'
import BookCardGrid from './components/BookCardGrid'
import DiversityPicks from './components/DiversityPicks'
import ExplorationControl from './components/ExplorationControl'
import ReadingDashboard from './components/ReadingDashboard'
import LibraryPage from './components/LibraryPage'
import BookPage from './components/BookPage'
import StudyEntry from './components/StudyEntry'
import SurveyPage from './components/SurveyPage'
import ThemePicker from './components/ThemePicker'
import { applyTheme, DEFAULT_THEME } from './theme/themes'

const navStyle = ({ isActive }) => ({ fontWeight: isActive ? 'bold' : 'normal'})

function App() {
  const [session, setSession] = useState(null)
  const [showSignup, setShowSignup] = useState(true)
  const [studyMode, setStudyMode] = useState(() => new URLSearchParams(window.location.search).has('study'))
  const [onboardingComplete, setOnboardingComplete] = useState(false)
  const [onboardingChecked, setOnboardingChecked] = useState(false)
  const [recommendations, setRecommendations] = useState([])
  const [explore, setExplore] = useState(0)
  const [arm, setArm] = useState(null)
  const [armChecked, setArmChecked] = useState(false)
  const requestId = useRef(0)
  const onHome = useLocation().pathname === '/'
  const userId = session?.user.id
  const isAnonymous = Boolean(session?.user.is_anonymous)
  const armReady = !isAnonymous || armChecked

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session))
    
    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
      if (!session) {
        setOnboardingComplete(false)
        setOnboardingChecked(false)
        setRecommendations([])
        setExplore(0)
        setArm(null)
        setArmChecked(false)
      }
    })

    return () => listener.subscription.unsubscribe()
  }, [])

  useEffect(() => {
    if (!session) return

    fetch(`${API}/user-onboarding-status/${session.user.id}`)
      .then((res) => res.json())
      .then((data) => {
        setOnboardingComplete(data.onboarding_completed)
      })
      .catch((err) => console.error('Failed to check onboarding status', err))
      .finally(() => setOnboardingChecked(true))
  }, [session])

  useEffect(() => {
    if (!userId || !isAnonymous) return

    fetch(`${API}/study/arm/${userId}`)
      .then(async (res) => {
        const data = await res.json().catch(() => null)
        if (!res.ok || !data?.arm) throw new Error(`Unexpected response (${res.status})`)
        const index = EXPLORE_LEVELS.findIndex((l) => l.value === data.explore)
      setArm(data.arm)
      setExplore(index >= 0 ? index: 0)
      })
      .catch((err) => console.error('Failed to get study arm', err))
      .finally(() => setArmChecked(true))
  }, [userId, isAnonymous])

  useEffect(() => {
    if (!session || !armReady || !onboardingComplete || !onHome) return

    const mine = ++requestId.current
    fetch(`${API}/recommendations/personalized/${session.user.id}?explore=${EXPLORE_LEVELS[explore].value}`)
      .then(async (res) => {
        const data = await res.json().catch(() => null)
        if (!res.ok || !Array.isArray(data?.recommendations)) {
          throw new Error(`Unexpected response (${res.status})`)
        }
        if (mine === requestId.current) setRecommendations(data.recommendations)
      })
      .catch((err) => console.error('Failed to load recommendations', err))
      // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, armReady, onboardingComplete, onHome])

  useEffect(() => {
    if (isAnonymous) applyTheme(DEFAULT_THEME)
  }, [isAnonymous])

  function handleOnboardingComplete(recs) {
    setRecommendations(recs)
    setOnboardingComplete(true)
  }

  function handleExploreChange(index) {
    setExplore(index)
    const mine = ++requestId.current
    fetch(`${API}/recommendations/personalized/${session.user.id}?explore=${EXPLORE_LEVELS[index].value}`)
      .then(async (res) => {
        const data = await res.json().catch(() => null)
        if (!res.ok || !Array.isArray(data?.recommendations)) {
          throw new Error(`Unexpected response (${res.status})`)
        }
        if (mine === requestId.current) setRecommendations(data.recommendations)
      })
      .catch((err) => console.error('Failed to update recommendations', err))
  }

  function handleRecommendationStatusChange(book, status) {
    if (status === 'want_to_read') {
      setRecommendations((prev) => prev.filter((b) => b.id !== book.id))
    }
  }

  if (!session) {
    if (studyMode) {
      return <StudyEntry onStarted={() => {}} onLogin={() => setStudyMode(false)} />
    }
    return (
      <div>
        {showSignup ? (
          <Signup onSuccess={() => {}} switchToLogin={() => setShowSignup(false)} />
        ) : (
          <Login onSuccess={() => {}} switchToSignup={() => setShowSignup(true)} />
        )}
        <p style={{ textAlign: 'center' }}>
          <button type="button" onClick={() => setStudyMode(true)}>Take part in the study</button>
        </p>
      </div>
    )
  }

  if (!armReady) {
    return <p>Loading...</p>
  }

  if (isAnonymous && !arm) {
    return <p>We couldn't start your session. Please refresh the page and try again.</p>
  }

  if (!onboardingChecked) {
    return <p>Loading...</p>
  }

  if (!onboardingComplete) {
    return <Onboarding userId={session.user.id} onComplete={handleOnboardingComplete} required={isAnonymous} />
  }

  return (
      <div>
        <nav className="app-nav">
          <strong>Salamander</strong>
          <NavLink to="/" end style={navStyle}>Recommendations</NavLink>
          <NavLink to="/catalog" style={navStyle}>Catalog</NavLink>
          {!isAnonymous && <NavLink to="/library" style={navStyle}>Library</NavLink>}
          <NavLink to="/want-to-read" style={navStyle}>Want to Read</NavLink>
          <NavLink to="/history" style={navStyle}>Reading History</NavLink>
          {isAnonymous && <NavLink to="/survey" style={navStyle}>Finish & take survey</NavLink>}
          <span className="nav-email" title={session.user.email}>{session.user.email}</span>
          {!isAnonymous && <ThemePicker userId={session.user.id} />}
          {!session.user.is_anonymous && <button onClick={() => supabase.auth.signOut()}>Log out</button>}
        </nav>
        
        <Routes>
          <Route
            path="/"
            element={
              <div>
                <h2>Your Recommendations</h2>
                {recommendations.some((b) => b.id) && (!isAnonymous || arm === 'B') && (
                  <ExplorationControl level={explore} onChange={handleExploreChange} />
                )}
                {isAnonymous && (
                  <p style={{ maxWidth: '640px', margin: '0 auto 16px', textAlign: 'center' }}>
                    Browse your recommendations and mark at least 10 books using the vote buttons. When you're
                    done, choose "Finish & take survey" in the menu.
                  </p>
                )}
                <BookCardGrid books={recommendations} userId={session.user.id} onStatusChange={handleRecommendationStatusChange} />
                <DiversityPicks userId={session.user.id} />
              </div>
            }
          />
          <Route path="/catalog" element={<CatalogPage userId={session.user.id} />} />
          <Route path="/want-to-read" element={<WantToReadPage userId={session.user.id} />} />
          {!isAnonymous && <Route path="/library" element={<LibraryPage userId={session.user.id} />} />}
          <Route path="/book/:id" element={<BookPage userId={session.user.id} />} />
          <Route path="/history" element={<ReadingDashboard userId={session.user.id} showGoal={!isAnonymous} />} />
          <Route path="/survey" element={<SurveyPage userId={session.user.id} />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    )
}

export default App
