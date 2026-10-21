import { useCallback, useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import { useAuth } from './context/useAuth.js'
import { formatTime } from './assessmentUtils.js'

const difficultyStyles = { Easy: 'easy', Medium: 'medium', Hard: 'hard' }

function AssessmentHeader({ title = 'Weekly assessment' }) {
  return (
    <header className="assessment-page-header">
      <a href="/" className="sheet-brand-link"><span className="brand-lockup"><span className="brand-mark">R</span><span>Recall<span>DSA</span></span></span></a>
      <div><a className="sheet-nav-link" href="/">Dashboard</a><a className="sheet-nav-link" href="/assessments/history">Assessment history</a></div>
      <strong>{title}</strong>
    </header>
  )
}

export function AssessmentResults({ assessment }) {
  const missed = assessment.problems.filter((entry) => entry.status !== 'solved')

  return (
    <section className="assessment-results">
      <p className="eyebrow">ASSESSMENT COMPLETE</p>
      <h2>{assessment.score_percentage}% <span>score</span></h2>
      <p>{assessment.problems.filter((entry) => entry.status === 'solved').length} of {assessment.total_problems} problems solved.</p>
      <div className="assessment-breakdown">
        <h3>Pattern breakdown</h3>
        {assessment.pattern_breakdown.map((pattern) => (
          <div className="assessment-breakdown-row" key={pattern.name}>
            <span>{pattern.name}</span>
            <strong>{pattern.solved}/{pattern.total}</strong>
          </div>
        ))}
      </div>
      <div className="assessment-missed">
        <h3>Problems to revisit</h3>
        {missed.length === 0
          ? <p>Excellent work—you solved every problem.</p>
          : missed.map(({ id, problem }) => (
            <a href={problem.link} key={id} rel="noreferrer" target="_blank">
              {problem.title} <span>{problem.pattern?.p_name || 'Uncategorized'} · {problem.difficulty}</span>
            </a>
          ))}
      </div>
    </section>
  )
}

export function AssessmentCard() {
  const { authenticatedRequest } = useAuth()
  const [assessment, setAssessment] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    authenticatedRequest('/api/assessments/current/')
      .then((data) => { if (active) setAssessment(data) })
      .catch((requestError) => { if (active) setError(requestError.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [authenticatedRequest])

  return (
    <section className="assessment-section">
      <div className="section-heading">
        <div><p className="eyebrow">WEEKLY ASSESSMENT</p><h2>Check your recall</h2></div>
        <a className="assessment-history-link" href="/assessments/history">View history ↗</a>
      </div>
      {loading && <div className="empty-state">Loading your assessment...</div>}
      {error && <div className="empty-state error-state">{error}</div>}
      {!loading && !error && !assessment && (
        <div className="empty-state">There are no tracked problems to include yet. Add problems to your revision queue to get started.</div>
      )}
      {!loading && assessment && (
        <article className="assessment-card assessment-card-feature">
          <div>
            <p className="eyebrow">{assessment.status === 'completed' ? 'READY TO REVIEW' : 'PERSONALIZED FOR YOUR REVISION QUEUE'}</p>
            <h3>{assessment.status === 'completed' ? 'This week’s assessment is complete' : 'Your weekly assessment is ready'}</h3>
            <p>{assessment.total_problems} problems · {assessment.time_limit_minutes} minutes</p>
            {assessment.status === 'completed' && <strong className="assessment-card-score">{assessment.score_percentage}% score</strong>}
          </div>
          <a className="primary-button" href="/assessments/current">
            {assessment.status === 'completed' ? 'View Results' : assessment.status === 'in_progress' ? 'Continue Assessment' : 'Start Assessment'}
          </a>
        </article>
      )}
    </section>
  )
}

export function AssessmentView() {
  const { authenticatedRequest } = useAuth()
  const [assessment, setAssessment] = useState(null)
  const [activeIndex, setActiveIndex] = useState(0)
  const [secondsLeft, setSecondsLeft] = useState(0)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const finishing = useRef(false)

  const finish = useCallback(async () => {
    if (!assessment || assessment.status !== 'in_progress' || finishing.current) return
    finishing.current = true
    setSubmitting(true)
    try {
      const result = await authenticatedRequest(`/api/assessments/${assessment.id}/complete/`, { method: 'POST' })
      setAssessment(result)
    } catch (requestError) {
      finishing.current = false
      setError(requestError.message)
      toast.error(requestError.message)
    } finally {
      setSubmitting(false)
    }
  }, [assessment, authenticatedRequest])

  useEffect(() => {
    let active = true
    authenticatedRequest('/api/assessments/current/')
      .then((data) => { if (active) setAssessment(data) })
      .catch((requestError) => { if (active) setError(requestError.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [authenticatedRequest])

  useEffect(() => {
    if (!assessment?.started_at || assessment.status !== 'in_progress') return undefined
    const updateTimer = () => {
      const deadline = new Date(assessment.started_at).getTime() + assessment.time_limit_minutes * 60_000
      const remaining = Math.max(0, Math.ceil((deadline - Date.now()) / 1000))
      setSecondsLeft(remaining)
      if (remaining === 0) finish()
    }
    updateTimer()
    const timer = window.setInterval(updateTimer, 1000)
    return () => window.clearInterval(timer)
  }, [assessment?.id, assessment?.started_at, assessment?.status, assessment?.time_limit_minutes, finish])

  const start = async () => {
    if (!assessment) return
    setSubmitting(true)
    setError('')
    try {
      const started = await authenticatedRequest(`/api/assessments/${assessment.id}/start/`, { method: 'POST' })
      setAssessment(started)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSubmitting(false)
    }
  }

  const answer = async (status) => {
    const entry = assessment?.problems[activeIndex]
    if (!entry || submitting) return
    setSubmitting(true)
    try {
      const updated = await authenticatedRequest(`/api/assessments/${assessment.id}/submit-answer/`, {
        method: 'POST',
        body: JSON.stringify({ problem_id: entry.problem.id, status }),
      })
      setAssessment((current) => ({
        ...current,
        problems: current.problems.map((item) => item.id === updated.id ? updated : item),
      }))
      if (activeIndex < assessment.problems.length - 1) setActiveIndex(activeIndex + 1)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSubmitting(false)
    }
  }

  const activeEntry = assessment?.problems[activeIndex]

  return (
    <main className="assessment-page">
      <AssessmentHeader />
      <div className="assessment-page-content">
        {loading && <div className="empty-state">Loading assessment...</div>}
        {error && <div className="empty-state error-state" role="alert">{error}</div>}
        {!loading && !error && !assessment && <div className="empty-state">No assessment is available this week. <a href="/">Return to your dashboard</a>.</div>}
        {assessment?.status === 'scheduled' && (
          <section className="assessment-start-panel">
            <p className="eyebrow">YOUR WEEKLY CHECK-IN</p>
            <h1>Ready to test your recall?</h1>
            <p>{assessment.total_problems} problems · {assessment.time_limit_minutes} minutes. Your timer starts when you begin.</p>
            <button className="primary-button" disabled={submitting} onClick={start} type="button">{submitting ? 'Starting...' : 'Start Assessment'}</button>
          </section>
        )}
        {assessment?.status === 'in_progress' && (
          <section className="assessment-test">
            <div className="assessment-test-heading">
              <div><p className="eyebrow">PROBLEM {activeIndex + 1} OF {assessment.total_problems}</p><h1>Weekly assessment</h1></div>
              <strong className={`assessment-countdown ${secondsLeft < 60 ? 'time-warning' : ''}`} aria-live="polite">{formatTime(secondsLeft)}</strong>
            </div>
            <nav className="assessment-problem-nav" aria-label="Assessment problem navigation">
              {assessment.problems.map((entry, index) => (
                <button className={`${index === activeIndex ? 'active' : ''} ${entry.status !== 'unanswered' ? 'answered' : ''}`} key={entry.id} onClick={() => setActiveIndex(index)} type="button" aria-label={`Problem ${index + 1}, ${entry.status}`}>
                  {index + 1}
                </button>
              ))}
            </nav>
            {activeEntry && (
              <article className="assessment-question">
                <div className="assessment-card-header"><span className={`difficulty-dot ${difficultyStyles[activeEntry.problem.difficulty]}`} /><span className="difficulty-label">{activeEntry.problem.difficulty}</span><span className="question-number">{activeEntry.problem.pattern?.p_name || 'Uncategorized'}</span></div>
                <h2>{activeEntry.problem.title}</h2>
                <p>Try the problem, then record whether you solved it from memory.</p>
                <a className="assessment-problem-link" href={activeEntry.problem.link} rel="noreferrer" target="_blank">Open problem ↗</a>
                <div className="assessment-answer-actions">
                  <button className={`assessment-answer solved ${activeEntry.status === 'solved' ? 'selected' : ''}`} disabled={submitting} onClick={() => answer('solved')} type="button">✓ Solved</button>
                  <button className={`assessment-answer missed ${activeEntry.status === 'missed' ? 'selected' : ''}`} disabled={submitting} onClick={() => answer('missed')} type="button">✗ Missed</button>
                </div>
              </article>
            )}
            <div className="assessment-test-footer">
              <button className="secondary-button" disabled={activeIndex === 0} onClick={() => setActiveIndex(activeIndex - 1)} type="button">Previous</button>
              <button className="secondary-button" disabled={activeIndex >= assessment.total_problems - 1} onClick={() => setActiveIndex(activeIndex + 1)} type="button">Next</button>
              <button className="primary-button" disabled={submitting} onClick={finish} type="button">{submitting ? 'Submitting...' : 'Complete Assessment'}</button>
            </div>
          </section>
        )}
        {assessment?.status === 'completed' && <AssessmentResults assessment={assessment} />}
      </div>
    </main>
  )
}

export function AssessmentHistory() {
  const { authenticatedRequest } = useAuth()
  const [assessments, setAssessments] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    authenticatedRequest('/api/assessments/history/')
      .then((data) => { if (active) setAssessments(data) })
      .catch((requestError) => { if (active) setError(requestError.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [authenticatedRequest])

  return (
    <main className="assessment-page">
      <AssessmentHeader title="Assessment history" />
      <div className="assessment-page-content">
        <div className="section-heading"><div><p className="eyebrow">YOUR PROGRESS</p><h1>Assessment history</h1></div><a className="back-link" href="/">← Dashboard</a></div>
        {loading && <div className="empty-state">Loading assessment history...</div>}
        {error && <div className="empty-state error-state" role="alert">{error}</div>}
        {!loading && !error && assessments.length === 0 && <div className="empty-state">Your completed assessments will appear here.</div>}
        <div className="assessment-history-list">
          {assessments.map((assessment) => (
            <button className={`assessment-history-item ${selected?.id === assessment.id ? 'selected' : ''}`} key={assessment.id} onClick={() => setSelected(assessment)} type="button">
              <span>{new Date(assessment.created_at).toLocaleDateString()}</span>
              <strong>{assessment.status === 'completed' ? `${assessment.score_percentage}%` : assessment.status.replace('_', ' ')}</strong>
              <small>{assessment.total_problems} problems</small>
            </button>
          ))}
        </div>
        {selected?.status === 'completed' && <AssessmentResults assessment={selected} />}
      </div>
    </main>
  )
}
