import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import toast, { Toaster } from 'react-hot-toast'
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate, useParams } from 'react-router-dom'
import { useAuth } from './context/useAuth.js'
import { SheetDetail, SheetExplorer } from './SheetPages.jsx'
import { AssessmentCard, AssessmentHistory, AssessmentView } from './AssessmentPages.jsx'
import Layout from './components/Layout.jsx'
import NotFound from './components/NotFound.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'
import {
  AssessmentsPage,
  ProblemDetailPage,
  ProblemsPage,
  RevisionsPage,
  SimpleRoutePage,
} from './RoutePages.jsx'

const AnalyticsPage = lazy(() => import('./AnalyticsPage.jsx'))
const DashboardOverview = lazy(() => import('./DashboardOverview.jsx'))

const difficultyStyles = { Easy: 'easy', Medium: 'medium', Hard: 'hard' }

function Logo() {
  return <div className="brand-lockup"><span className="brand-mark">R</span><span>Recall<span>DSA</span></span></div>
}

function ThemeToggle({ theme, onToggle }) {
  const isDark = theme === 'dark'
  return <button aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'} className="theme-toggle" onClick={onToggle} title={isDark ? 'Switch to light mode' : 'Switch to dark mode'} type="button"><span aria-hidden="true">{isDark ? '☀' : '☾'}</span><span>{isDark ? 'Light' : 'Night'}</span></button>
}

function ConfidenceModal({ problem, onClose, onSubmit, submitting }) {
  const [confidence, setConfidence] = useState(3)
  const labels = {
    1: 'Forgot',
    2: 'Barely',
    3: 'Somewhat',
    4: 'Mostly',
    5: 'Instant',
  }

  return (
    <div className="review-modal-backdrop" onClick={onClose} role="presentation">
      <div className="review-modal" onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true" aria-label="Recall rating">
        <p className="eyebrow">RECALL CHECK</p>
        <h2>How well do you remember this problem?</h2>
        <p className="review-modal-subtitle">Rate this revision so your spaced repetition schedule can update accurately.</p>
        <div className="rating-row" aria-label="Rate your recall confidence">
          {[1, 2, 3, 4, 5].map((value) => (
            <button
              key={value}
              className={`rating-option ${confidence === value ? 'selected' : ''}`}
              onClick={() => setConfidence(value)}
              type="button"
              aria-label={`Rate ${value} stars: ${labels[value]}`}
            >
              ★
            </button>
          ))}
        </div>
        <div className="review-meta">
          <span>{problem?.title}</span>
          <strong>{confidence ? `${labels[confidence]} · ${confidence}/5` : 'Select your rating'}</strong>
        </div>
        <div className="review-rating-labels" aria-live="polite">
          {Object.entries(labels).map(([value, label]) => (
            <span key={value} className={Number(value) === confidence ? 'active' : ''}>{label}</span>
          ))}
        </div>
        <button className="primary-button review-submit" disabled={submitting} onClick={() => onSubmit(confidence)} type="button">
          {submitting ? 'Saving review...' : 'Submit rating'}
        </button>
      </div>
    </div>
  )
}

function AuthScreen({ theme, onToggle }) {
  const { login, register } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [form, setForm] = useState({ username: '', email: '', password: '' })
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const isRegister = location.pathname === '/signup'

  const switchMode = (nextMode) => {
    navigate(nextMode === 'register' ? '/signup' : '/login')
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
      const destination = !isRegister && location.state?.from?.pathname
        ? location.state.from.pathname
        : '/dashboard'
      navigate(destination, { replace: true })
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
            <button className={!isRegister ? 'active' : ''} onClick={() => switchMode('login')} type="button">Sign in</button>
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

function Dashboard() {
  const { user, authenticatedRequest } = useAuth()
  const [questions, setQuestions] = useState([])
  const [query, setQuery] = useState('')
  const [difficulty, setDifficulty] = useState('All')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [solvedIds, setSolvedIds] = useState(new Set())
  const [solvingId, setSolvingId] = useState(null)
  const [reviewProblem, setReviewProblem] = useState(null)
  const [todayRevisions, setTodayRevisions] = useState([])
  const [dashboardMetrics, setDashboardMetrics] = useState(null)
  const [dashboardInsights, setDashboardInsights] = useState(null)
  const [dashboardLoading, setDashboardLoading] = useState(true)
  const [dashboardError, setDashboardError] = useState('')

  useEffect(() => {
    const fetchQuestions = async () => {
      try {
        const problemList = await authenticatedRequest('/api/home/')
        setQuestions(problemList)
        const reviewId = Number(new URLSearchParams(window.location.search).get('review'))
        const problemToReview = problemList.find((question) => question.id === reviewId)
        if (problemToReview) {
          setReviewProblem(problemToReview)
          window.history.replaceState({}, '', window.location.pathname)
        }
      } catch (fetchError) { setError(fetchError.message) } finally { setLoading(false) }
    }
    fetchQuestions()
  }, [authenticatedRequest])

  useEffect(() => {
    authenticatedRequest('/api/auth/profile/')
      .then((data) => {
        setSolvedIds(new Set(data.solved_problems.map((progress) => progress.problem.id)))
      })
      .catch((requestError) => toast.error(requestError.message))
  }, [authenticatedRequest, user])

  useEffect(() => {
    if (!user) return

    let active = true
    Promise.all([
      authenticatedRequest('/api/dashboard/stats/'),
      authenticatedRequest('/api/revisions/due-today/'),
      authenticatedRequest('/api/analytics/confidence-trend/'),
      authenticatedRequest('/api/analytics/pattern-strength/'),
      authenticatedRequest('/api/analytics/recommendations/'),
    ]).then(([stats, revisions, confidenceTrend, patternStrength, recommendations]) => {
      if (!active) return
      setDashboardMetrics(stats)
      setTodayRevisions(revisions)
      setDashboardInsights({ confidenceTrend, patternStrength, recommendations })
    }).catch((requestError) => {
      if (active) setDashboardError(requestError.message)
    }).finally(() => {
      if (active) setDashboardLoading(false)
    })
    return () => { active = false }
  }, [authenticatedRequest, user])

  const markSolved = async (problemId, confidence = 3) => {
    setSolvingId(problemId)
    try {
      const response = await authenticatedRequest('/api/revisions/submit-review/', {
        method: 'POST',
        body: JSON.stringify({ problem_id: problemId, confidence_rating: confidence }),
      })
      const nextInterval = Number(response?.interval ?? 0)
      const displayDays = Math.max(1, nextInterval || Math.ceil((new Date(response?.next_review_date).getTime() - Date.now()) / 86400000))
      toast.success(`Next review in ${displayDays} ${displayDays === 1 ? 'day' : 'days'}`)
      setSolvedIds((current) => new Set([...current, problemId]))
      const [nextDue, updatedMetrics] = await Promise.all([
        authenticatedRequest('/api/revisions/due-today/'),
        authenticatedRequest('/api/dashboard/stats/'),
      ])
      setTodayRevisions(nextDue)
      setDashboardMetrics(updatedMetrics)
      setReviewProblem(null)
      window.dispatchEvent(new Event('recalldsa:revisions-updated'))
    } catch (solveError) {
      toast.error(solveError.message)
      setError(solveError.message)
    } finally {
      setSolvingId(null)
    }
  }

  const filteredQuestions = useMemo(() => questions.filter((question) => {
    const matchesDifficulty = difficulty === 'All' || question.difficulty === difficulty
    const searchable = `${question.title} ${question.pattern?.p_name ?? ''} ${question.leetcode_id}`.toLowerCase()
    return matchesDifficulty && searchable.includes(query.toLowerCase())
  }), [difficulty, query, questions])
  const firstName = user?.username?.split(/[._-]/)[0] || 'there'

  return (
    <main className="dashboard-page">
      <div className="dashboard-content" id="overview">
        <Suspense fallback={<div className="overview-loading" role="status">Preparing your dashboard…</div>}>
          <DashboardOverview
            dashboardError={dashboardError}
            dashboardInsights={dashboardInsights}
            dashboardLoading={dashboardLoading}
            dashboardMetrics={dashboardMetrics}
            firstName={firstName}
            onReview={(problem) => setReviewProblem(problem)}
            todayRevisions={todayRevisions}
          />
        </Suspense>
        <section className="library-section" id="library">
          <div className="section-heading"><div><p className="eyebrow">YOUR LIBRARY</p><h2>Problem patterns</h2></div><span className="result-count">{filteredQuestions.length} shown</span></div>
          <div className="library-tools"><label className="search-field"><span aria-hidden="true">⌕</span><input onChange={(event) => setQuery(event.target.value)} placeholder="Search problems or patterns" value={query} /></label><div className="filter-group" aria-label="Filter by difficulty">{['All', 'Easy', 'Medium', 'Hard'].map((option) => <button className={difficulty === option ? 'active' : ''} key={option} onClick={() => setDifficulty(option)} type="button">{option}</button>)}</div></div>
          {loading && <div className="empty-state">Loading your problem library...</div>}
          {error && <div className="empty-state error-state">{error}</div>}
          {!loading && !error && filteredQuestions.length === 0 && <div className="empty-state">No problems match this view yet.</div>}
          {!loading && !error && filteredQuestions.length > 0 && <div className="problem-grid">{filteredQuestions.map((question) => { const solved = solvedIds.has(question.id); return <article className={`problem-card ${solved ? 'solved-card' : ''}`} key={question.id ?? question.q_id}><div className="card-topline"><span className={`difficulty-dot ${difficultyStyles[question.difficulty]}`} /><span className="difficulty-label">{question.difficulty}</span><span className="question-number">#{String(question.leetcode_id).padStart(4, '0')}</span></div><h3>{question.title}</h3><p className="pattern-label">{question.pattern?.p_name || 'Uncategorized pattern'}</p><div className="card-footer"><button className={`solve-button ${solved ? 'is-solved' : ''}`} disabled={solvingId === question.id} onClick={() => setReviewProblem(question)} type="button">{solved ? 'Review' : solvingId === question.id ? 'Saving...' : 'Mark as solved'}</button>{question.link && <a href={question.link} rel="noreferrer" target="_blank">Open problem <span>↗</span></a>}</div></article> })}</div>}
        </section>
      </div>
      {reviewProblem && <ConfidenceModal problem={reviewProblem} onClose={() => setReviewProblem(null)} onSubmit={(confidence) => markSolved(reviewProblem.id, confidence)} submitting={solvingId === reviewProblem.id} />}
    </main>
  )
}

function LandingRedirect() {
  const { isAuthenticated, loading } = useAuth()

  if (loading) return <div className="loading-screen" role="status">Preparing your workspace...</div>
  return <Navigate replace to={isAuthenticated ? '/dashboard' : '/login'} />
}

function AuthRoute({ theme, onToggle }) {
  const { isAuthenticated, loading } = useAuth()
  if (loading) return <div className="loading-screen" role="status">Preparing your workspace...</div>
  if (isAuthenticated) return <Navigate replace to="/dashboard" />
  return <AuthScreen onToggle={onToggle} theme={theme} />
}

function SheetDetailRoute() {
  const { slug } = useParams()
  return <SheetDetail slug={slug} />
}

function AssessmentsIndexPage() {
  return (
    <>
      <AssessmentsPage />
      <div className="route-page"><AssessmentCard /></div>
    </>
  )
}

function AppRoutes({ theme, onToggleTheme }) {
  return (
    <>
      <Toaster position="top-right" toastOptions={{ duration: 3000 }} />
      <Routes>
        <Route element={<LandingRedirect />} path="/" />
        <Route element={<AuthRoute onToggle={onToggleTheme} theme={theme} />} path="/login" />
        <Route element={<AuthRoute onToggle={onToggleTheme} theme={theme} />} path="/signup" />
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout onToggleTheme={onToggleTheme} theme={theme} />}>
            <Route element={<Dashboard />} path="/dashboard" />
            <Route element={<ProblemsPage />} path="/problems" />
            <Route element={<ProblemDetailPage />} path="/problems/:id" />
            <Route element={<SheetExplorer />} path="/sheets" />
            <Route element={<SheetDetailRoute />} path="/sheets/:slug" />
            <Route element={<SimpleRoutePage description="The import route is ready, but the current backend does not expose a LeetCode authorization or sync endpoint yet." eyebrow="PROBLEM INGESTION" title="LeetCode sync" />} path="/import/leetcode" />
            <Route element={<RevisionsPage />} path="/revisions" />
            <Route element={<AssessmentsIndexPage />} path="/assessments" />
            <Route element={<AssessmentView />} path="/assessments/current" />
            <Route element={<AssessmentView />} path="/assessments/:id" />
            <Route element={<AssessmentHistory />} path="/assessments/history" />
            <Route element={<AnalyticsRoute />} path="/analytics" />
            <Route element={<SimpleRoutePage description="Your account details and learning progress." eyebrow="YOUR ACCOUNT" title="Profile" />} path="/profile" />
            <Route element={<SimpleRoutePage action="/settings/integrations" actionLabel="Manage integrations" description="Manage your RecallDSA preferences and connected services." eyebrow="PREFERENCES" title="Settings" />} path="/settings" />
            <Route element={<SimpleRoutePage description="This integration route is ready for a LeetCode connection flow. The current backend does not expose an authorization or import endpoint yet." eyebrow="CONNECTED SERVICES" title="Integrations" />} path="/settings/integrations" />
          </Route>
        </Route>
        <Route element={<NotFound />} path="*" />
      </Routes>
    </>
  )
}

function AnalyticsRoute() {
  return <Suspense fallback={<div className="loading-screen" role="status">Loading analytics...</div>}><AnalyticsPage /></Suspense>
}

function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem('recalldsa-theme') || 'light')

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('recalldsa-theme', theme)
  }, [theme])

  const toggleTheme = () => setTheme((currentTheme) => currentTheme === 'dark' ? 'light' : 'dark')

  return (
    <BrowserRouter>
      <AppRoutes onToggleTheme={toggleTheme} theme={theme} />
    </BrowserRouter>
  )
}

export default App
