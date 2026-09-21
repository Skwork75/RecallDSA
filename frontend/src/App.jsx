import { useEffect, useMemo, useState } from 'react'
import { useAuth } from './context/useAuth.js'

const difficultyStyles = { Easy: 'easy', Medium: 'medium', Hard: 'hard' }

function Logo() {
  return <div className="brand-lockup"><span className="brand-mark">R</span><span>Recall<span>DSA</span></span></div>
}

function ThemeToggle({ theme, onToggle }) {
  const isDark = theme === 'dark'
  return <button aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'} className="theme-toggle" onClick={onToggle} title={isDark ? 'Switch to light mode' : 'Switch to dark mode'} type="button"><span aria-hidden="true">{isDark ? '☀' : '☾'}</span><span>{isDark ? 'Light' : 'Night'}</span></button>
}

function ProfilePanel({ profile, onClose }) {
  return <div className="profile-popover" role="dialog" aria-label="User profile">
    <div className="profile-popover-header"><div><p className="eyebrow">YOUR PROFILE</p><h2>{profile.user.username}</h2></div><button className="close-profile" onClick={onClose} type="button" aria-label="Close profile">×</button></div>
    <p className="profile-email">{profile.user.email || 'No email address added'}</p>
    <div className="profile-summary"><strong>{profile.solved_problems.length}</strong><span>solved problems</span></div>
    <div className="solved-list"><p className="eyebrow">SOLVED PROBLEMS</p>{profile.solved_problems.length === 0 ? <p className="profile-empty">No solved problems yet. Mark one from your library.</p> : profile.solved_problems.map((progress) => <div className="solved-item" key={progress.id}><span className="solved-check">✓</span><div><strong>{progress.problem.title}</strong><small>{progress.problem.pattern?.p_name || 'Uncategorized pattern'} · {progress.problem.difficulty}</small></div></div>)}</div>
  </div>
}

function ReviewPrompt({ problem, onClose, onSubmit, submitting }) {
  const [confidence, setConfidence] = useState(null)

  return (
    <div className="review-modal-backdrop" onClick={onClose} role="presentation">
      <div className="review-modal" onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true" aria-label="Recall rating">
        <p className="eyebrow">RECALL CHECK</p>
        <h2>After a user marks a problem solved or revised, ask how well they remember the approach.</h2>
        <p className="review-modal-subtitle">This rating becomes the input for your revision scheduling system.</p>
        <div className="rating-row" aria-label="Rate your recall confidence">
          {[1, 2, 3, 4, 5].map((value) => (
            <button
              key={value}
              className={`rating-option ${confidence === value ? 'selected' : ''}`}
              onClick={() => setConfidence(value)}
              type="button"
            >
              {value}
            </button>
          ))}
        </div>
        <div className="review-meta">
          <span>{problem?.title}</span>
          <strong>{confidence ? `Confidence: ${confidence}/5` : 'Select your rating'}</strong>
        </div>
        <button className="primary-button review-submit" disabled={!confidence || submitting} onClick={() => onSubmit(confidence)} type="button">
          {submitting ? 'Saving review...' : 'Save recall rating'}
        </button>
      </div>
    </div>
  )
}

function AuthScreen({ theme, onToggle }) {
  const { login, register } = useAuth()
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ username: '', email: '', password: '' })
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const isRegister = mode === 'register'

  const switchMode = (nextMode) => {
    setMode(nextMode)
    setError('')
    setForm({ username: '', email: '', password: '' })
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      if (isRegister) await register(form)
      else await login({ username: form.username, password: form.password })
    } catch (submitError) {
      setError(submitError.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="auth-page">
      <div className="auth-atmosphere" aria-hidden="true" />
      <nav className="auth-nav"><Logo /><div className="auth-nav-actions"><span className="nav-note">A calmer way to keep what you solve</span><ThemeToggle onToggle={onToggle} theme={theme} /></div></nav>
      <div className="auth-layout">
        <section className="auth-intro">
          <p className="eyebrow">THE PRACTICE LOOP</p>
          <h1>Remember the pattern, not just the answer.</h1>
          <p className="intro-copy">Turn solved problems into durable intuition with a focused revision space built for the way technical memory actually works.</p>
          <div className="signal-list">
            <div><span>01</span><p>Revisit problems when recall is starting to fade.</p></div>
            <div><span>02</span><p>See the patterns behind your growing problem set.</p></div>
            <div><span>03</span><p>Build a practice habit that compounds.</p></div>
          </div>
        </section>
        <section className="auth-panel">
          <div className="auth-panel-header"><p className="eyebrow">YOUR WORKSPACE</p><h2>{isRegister ? 'Create your account' : 'Welcome back'}</h2><p>{isRegister ? 'Start building a memory for every pattern.' : 'Pick up your practice where you left off.'}</p></div>
          <div className="auth-tabs" role="tablist" aria-label="Authentication options">
            <button className={mode === 'login' ? 'active' : ''} onClick={() => switchMode('login')} type="button">Sign in</button>
            <button className={isRegister ? 'active' : ''} onClick={() => switchMode('register')} type="button">Create account</button>
          </div>
          <form className="auth-form" onSubmit={handleSubmit}>
            <label>Username<input autoComplete="username" onChange={(event) => setForm({ ...form, username: event.target.value })} placeholder="e.g. alex.codes" required value={form.username} /></label>
            {isRegister && <label>Email address<input autoComplete="email" onChange={(event) => setForm({ ...form, email: event.target.value })} placeholder="you@example.com" required type="email" value={form.email} /></label>}
            <label>Password<input autoComplete={isRegister ? 'new-password' : 'current-password'} minLength={isRegister ? 8 : undefined} onChange={(event) => setForm({ ...form, password: event.target.value })} placeholder={isRegister ? 'At least 8 characters' : 'Enter your password'} required type="password" value={form.password} /></label>
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="primary-button" disabled={submitting} type="submit">{submitting ? 'Please wait...' : isRegister ? 'Create my workspace' : 'Enter workspace'}<span aria-hidden="true">↗</span></button>
          </form>
          <p className="secure-note"><span aria-hidden="true">◈</span> Your password is securely hashed by Django.</p>
        </section>
      </div>
      <footer className="auth-footer">RECALLDSA <span>•</span> DELIBERATE PRACTICE FOR LONG-TERM RECALL</footer>
    </main>
  )
}

function Dashboard({ theme, onToggle }) {
  const { user, logout, authenticatedRequest } = useAuth()
  const [questions, setQuestions] = useState([])
  const [query, setQuery] = useState('')
  const [difficulty, setDifficulty] = useState('All')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [solvedIds, setSolvedIds] = useState(new Set())
  const [profile, setProfile] = useState(null)
  const [profileOpen, setProfileOpen] = useState(false)
  const [solvingId, setSolvingId] = useState(null)
  const [reviewProblem, setReviewProblem] = useState(null)
  const [todayRevisions, setTodayRevisions] = useState([])
  const [weeklyAssessment, setWeeklyAssessment] = useState([])

  useEffect(() => {
    const fetchQuestions = async () => {
      try {
        const response = await fetch('/api/home/')
        if (!response.ok) throw new Error('Unable to load questions from the API')
        setQuestions(await response.json())
      } catch (fetchError) { setError(fetchError.message) } finally { setLoading(false) }
    }
    fetchQuestions()
  }, [])

  useEffect(() => {
    authenticatedRequest('/api/auth/profile/')
      .then((data) => {
        setProfile(data)
        setSolvedIds(new Set(data.solved_problems.map((progress) => progress.problem.id)))
      })
      .catch(() => setProfile({ user, solved_problems: [] }))
  }, [authenticatedRequest, user])

  useEffect(() => {
    if (!user) return

    authenticatedRequest('/api/revisions/today/')
      .then(setTodayRevisions)
      .catch(() => setTodayRevisions([]))

    authenticatedRequest('/api/assessments/weekly/')
      .then(setWeeklyAssessment)
      .catch(() => setWeeklyAssessment([]))
  }, [authenticatedRequest, user])

  const markSolved = async (problemId, confidence = 3) => {
    setSolvingId(problemId)
    try {
      await authenticatedRequest(`/api/problems/${problemId}/solve/`, {
        method: 'POST',
        body: JSON.stringify({ confidence }),
      })
      setSolvedIds((current) => new Set([...current, problemId]))
      const [updatedProfile, nextDue] = await Promise.all([
        authenticatedRequest('/api/auth/profile/'),
        authenticatedRequest('/api/revisions/today/'),
      ])
      setProfile(updatedProfile)
      setTodayRevisions(nextDue)
      setReviewProblem(null)
    } catch (solveError) {
      setError(solveError.message)
    } finally {
      setSolvingId(null)
    }
  }

  const dueForReview = useMemo(() => {
    if (!profile) return 0
    const now = new Date()
    return profile.solved_problems.filter((progress) => {
      if (!progress.next_revision) return false
      return new Date(progress.next_revision) <= now
    }).length
  }, [profile])

  const filteredQuestions = useMemo(() => questions.filter((question) => {
    const matchesDifficulty = difficulty === 'All' || question.difficulty === difficulty
    const searchable = `${question.title} ${question.pattern?.p_name ?? ''} ${question.leetcode_id}`.toLowerCase()
    return matchesDifficulty && searchable.includes(query.toLowerCase())
  }), [difficulty, query, questions])
  const firstName = user?.username?.split(/[._-]/)[0] || 'there'

  return (
    <main className="dashboard-page">
      <header className="topbar"><Logo /><div className="topbar-actions"><ThemeToggle onToggle={onToggle} theme={theme} /><button className="user-chip" onClick={() => setProfileOpen((open) => !open)} type="button" aria-expanded={profileOpen}><span>{user?.username?.charAt(0).toUpperCase()}</span><strong>{user?.username}</strong></button><button className="logout-button" onClick={logout} type="button">Sign out</button>{profileOpen && profile && <ProfilePanel onClose={() => setProfileOpen(false)} profile={profile} />}</div></header>
      <div className="dashboard-content">
        <section className="welcome-row"><div><p className="eyebrow">YOUR NEXT REP</p><h1>Ready when you are, {firstName}.</h1><p className="subheading">A small, steady review keeps your instincts sharp.</p></div><div className="streak-badge"><span>✦</span><div><strong>{profile?.solved_problems?.length ? `${Math.min(profile.solved_problems.length, 7)} day` : '0 day'}</strong><small>current streak</small></div></div></section>
        <section className="metrics-row"><div className="metric-card metric-featured"><span className="metric-icon">◎</span><strong>{questions.length}</strong><small>problems in library</small><div className="metric-line" /></div><div className="metric-card"><span className="metric-icon">◌</span><strong>{dueForReview}</strong><small>due for review</small><a href="#library">Start a review <span>↗</span></a></div><div className="metric-card"><span className="metric-icon">↗</span><strong>{profile ? Math.min(100, Math.round((profile.solved_problems.length / Math.max(questions.length, 1)) * 100)) : 0}%</strong><small>weekly progress</small><div className="progress-track"><span style={{ width: `${profile ? Math.min(100, Math.round((profile.solved_problems.length / Math.max(questions.length, 1)) * 100)) : 0}%` }} /></div></div></section>
        <section className="revision-section">
          <div className="section-heading"><div><p className="eyebrow">TODAY'S REVISION</p><h2>{todayRevisions.length === 0 ? 'Nothing due today' : `You have ${todayRevisions.length} problem${todayRevisions.length === 1 ? '' : 's'} to revise.`}</h2></div><span className="result-count">{todayRevisions.length} due</span></div>
          {todayRevisions.length === 0 ? <div className="empty-state">You are all caught up. Come back later for the next revision cycle.</div> : <div className="revision-list">{todayRevisions.map((progress) => <article className="revision-card" key={progress.id}><div className="revision-card-header"><span className={`difficulty-dot ${difficultyStyles[progress.problem.difficulty]}`} /><span className="difficulty-label">{progress.problem.difficulty}</span></div><h3>{progress.problem.title}</h3><p className="pattern-label">{progress.problem.pattern?.p_name || 'Uncategorized pattern'}</p><div className="revision-card-footer"><button className="primary-button" onClick={() => setReviewProblem({ ...progress.problem, id: progress.problem.id })} type="button">Start Revision</button></div></article>)}</div>}
        </section>
        <section className="assessment-section">
          <div className="section-heading"><div><p className="eyebrow">WEEKLY ASSESSMENT</p><h2>{weeklyAssessment.length === 0 ? 'No assessment set yet' : 'This week’s focus list'}</h2></div><span className="result-count">{weeklyAssessment.length} selected</span></div>
          {weeklyAssessment.length === 0 ? <div className="empty-state">Your weekly assessment will surface your weakest and most overdue problems.</div> : <div className="assessment-grid">{weeklyAssessment.map((progress) => <article className="assessment-card" key={progress.id}><div className="assessment-card-header"><span className={`difficulty-dot ${difficultyStyles[progress.problem.difficulty]}`} /><span className="difficulty-label">{progress.problem.difficulty}</span></div><h3>{progress.problem.title}</h3><p className="pattern-label">{progress.problem.pattern?.p_name || 'Uncategorized pattern'}</p><div className="assessment-card-footer"><button className="primary-button" onClick={() => setReviewProblem({ ...progress.problem, id: progress.problem.id })} type="button">Review this problem</button></div></article>)}</div>}
        </section>
        <section className="library-section" id="library">
          <div className="section-heading"><div><p className="eyebrow">YOUR LIBRARY</p><h2>Problem patterns</h2></div><span className="result-count">{filteredQuestions.length} shown</span></div>
          <div className="library-tools"><label className="search-field"><span aria-hidden="true">⌕</span><input onChange={(event) => setQuery(event.target.value)} placeholder="Search problems or patterns" value={query} /></label><div className="filter-group" aria-label="Filter by difficulty">{['All', 'Easy', 'Medium', 'Hard'].map((option) => <button className={difficulty === option ? 'active' : ''} key={option} onClick={() => setDifficulty(option)} type="button">{option}</button>)}</div></div>
          {loading && <div className="empty-state">Loading your problem library...</div>}
          {error && <div className="empty-state error-state">{error}</div>}
          {!loading && !error && filteredQuestions.length === 0 && <div className="empty-state">No problems match this view yet.</div>}
          {!loading && !error && filteredQuestions.length > 0 && <div className="problem-grid">{filteredQuestions.map((question) => { const solved = solvedIds.has(question.id); return <article className={`problem-card ${solved ? 'solved-card' : ''}`} key={question.id ?? question.q_id}><div className="card-topline"><span className={`difficulty-dot ${difficultyStyles[question.difficulty]}`} /><span className="difficulty-label">{question.difficulty}</span><span className="question-number">#{String(question.leetcode_id).padStart(4, '0')}</span></div><h3>{question.title}</h3><p className="pattern-label">{question.pattern?.p_name || 'Uncategorized pattern'}</p><div className="card-footer"><button className={`solve-button ${solved ? 'is-solved' : ''}`} disabled={solvingId === question.id} onClick={() => setReviewProblem(question)} type="button">{solved ? 'Review' : solvingId === question.id ? 'Saving...' : 'Mark as solved'}</button>{question.link && <a href={question.link} rel="noreferrer" target="_blank">Open problem <span>↗</span></a>}</div></article> })}</div>}
        </section>
      </div>
      {reviewProblem && <ReviewPrompt problem={reviewProblem} onClose={() => setReviewProblem(null)} onSubmit={(confidence) => markSolved(reviewProblem.id, confidence)} submitting={solvingId === reviewProblem.id} />}
    </main>
  )
}

function App() {
  const { user, loading } = useAuth()
  const [theme, setTheme] = useState(() => localStorage.getItem('recalldsa-theme') || 'light')

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('recalldsa-theme', theme)
  }, [theme])

  const toggleTheme = () => setTheme((currentTheme) => currentTheme === 'dark' ? 'light' : 'dark')

  if (loading) return <div className="loading-screen"><Logo /><span>Preparing your workspace...</span></div>
  return user ? <Dashboard onToggle={toggleTheme} theme={theme} /> : <AuthScreen onToggle={toggleTheme} theme={theme} />
}

export default App
