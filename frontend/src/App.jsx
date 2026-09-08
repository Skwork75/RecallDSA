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
  const { user, logout } = useAuth()
  const [questions, setQuestions] = useState([])
  const [query, setQuery] = useState('')
  const [difficulty, setDifficulty] = useState('All')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

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

  const filteredQuestions = useMemo(() => questions.filter((question) => {
    const matchesDifficulty = difficulty === 'All' || question.difficulty === difficulty
    const searchable = `${question.title} ${question.pattern?.p_name ?? ''} ${question.leetcode_id}`.toLowerCase()
    return matchesDifficulty && searchable.includes(query.toLowerCase())
  }), [difficulty, query, questions])
  const firstName = user?.username?.split(/[._-]/)[0] || 'there'

  return (
    <main className="dashboard-page">
      <header className="topbar"><Logo /><div className="topbar-actions"><ThemeToggle onToggle={onToggle} theme={theme} /><div className="user-chip"><span>{user?.username?.charAt(0).toUpperCase()}</span><strong>{user?.username}</strong></div><button className="logout-button" onClick={logout} type="button">Sign out</button></div></header>
      <div className="dashboard-content">
        <section className="welcome-row"><div><p className="eyebrow">YOUR NEXT REP</p><h1>Ready when you are, {firstName}.</h1><p className="subheading">A small, steady review keeps your instincts sharp.</p></div><div className="streak-badge"><span>✦</span><div><strong>0 day</strong><small>current streak</small></div></div></section>
        <section className="metrics-row"><div className="metric-card metric-featured"><span className="metric-icon">◎</span><strong>{questions.length}</strong><small>problems in library</small><div className="metric-line" /></div><div className="metric-card"><span className="metric-icon">◌</span><strong>0</strong><small>due for review</small><a href="#library">Start a review <span>↗</span></a></div><div className="metric-card"><span className="metric-icon">↗</span><strong>0%</strong><small>weekly progress</small><div className="progress-track"><span /></div></div></section>
        <section className="library-section" id="library">
          <div className="section-heading"><div><p className="eyebrow">YOUR LIBRARY</p><h2>Problem patterns</h2></div><span className="result-count">{filteredQuestions.length} shown</span></div>
          <div className="library-tools"><label className="search-field"><span aria-hidden="true">⌕</span><input onChange={(event) => setQuery(event.target.value)} placeholder="Search problems or patterns" value={query} /></label><div className="filter-group" aria-label="Filter by difficulty">{['All', 'Easy', 'Medium', 'Hard'].map((option) => <button className={difficulty === option ? 'active' : ''} key={option} onClick={() => setDifficulty(option)} type="button">{option}</button>)}</div></div>
          {loading && <div className="empty-state">Loading your problem library...</div>}
          {error && <div className="empty-state error-state">{error}</div>}
          {!loading && !error && filteredQuestions.length === 0 && <div className="empty-state">No problems match this view yet.</div>}
          {!loading && !error && filteredQuestions.length > 0 && <div className="problem-grid">{filteredQuestions.map((question) => <article className="problem-card" key={question.id ?? question.q_id}><div className="card-topline"><span className={`difficulty-dot ${difficultyStyles[question.difficulty]}`} /><span className="difficulty-label">{question.difficulty}</span><span className="question-number">#{String(question.leetcode_id).padStart(4, '0')}</span></div><h3>{question.title}</h3><p className="pattern-label">{question.pattern?.p_name || 'Uncategorized pattern'}</p><div className="card-footer"><span className="review-status">○ Not reviewed</span>{question.link && <a href={question.link} rel="noreferrer" target="_blank">Open problem <span>↗</span></a>}</div></article>)}</div>}
        </section>
      </div>
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
