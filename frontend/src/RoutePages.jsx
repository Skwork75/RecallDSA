import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import toast from 'react-hot-toast'
import { useAuth } from './context/useAuth.js'
import { AddProblemModalLayer } from './AddProblemModal.jsx'

function useRequest(path, reloadKey = 0) {
  const { authenticatedRequest } = useAuth()
  const [state, setState] = useState({ data: null, loading: true, error: '' })

  useEffect(() => {
    let active = true
    authenticatedRequest(path)
      .then((data) => {
        if (active) setState({ data, loading: false, error: '' })
      })
      .catch((error) => {
        if (active) setState({ data: null, loading: false, error: error.message })
      })
    return () => { active = false }
  }, [authenticatedRequest, path, reloadKey])

  return state
}

export function ProblemsPage() {
  const [reloadKey, setReloadKey] = useState(0)
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [removingId, setRemovingId] = useState(null)
  const { authenticatedRequest } = useAuth()
  const { data, loading, error } = useRequest('/api/problems/tracked/', reloadKey)
  const isValidResponse = Array.isArray(data)
  const problems = isValidResponse ? data : []

  const removeProblem = async (progressId, title) => {
    if (!window.confirm(`Remove "${title}" from your tracked problems?`)) return

    setRemovingId(progressId)
    try {
      await authenticatedRequest(`/api/problems/tracked/${progressId}/`, { method: 'DELETE' })
      toast.success('Problem removed from your list')
      setReloadKey((key) => key + 1)
    } catch (requestError) {
      toast.error(requestError.message)
    } finally {
      setRemovingId(null)
    }
  }

  return (
    <main className="route-page">
      <div className="problem-page-heading">
        <PageHeading eyebrow="YOUR LIBRARY" title="Tracked problems" description="Problems you have practiced and added to your personal recall history." />
        <button
          aria-label="Add problem"
          className="primary-button add-problem-fab"
          onClick={() => setAddModalOpen(true)}
          title="Add problem"
          type="button"
        >
          +
        </button>
      </div>
      {loading && <div className="empty-state">Loading your problems...</div>}
      {error && <div className="empty-state error-state" role="alert">{error}</div>}
      {!loading && !error && !isValidResponse && <div className="empty-state error-state" role="alert">The tracked problems response had an unexpected format.</div>}
      {!loading && !error && isValidResponse && problems.length === 0 && <div className="empty-state">No problems tracked yet. Start with a curated <Link to="/sheets">DSA sheet</Link> or browse your <Link to="/dashboard">dashboard</Link>.</div>}
      {!loading && !error && isValidResponse && problems.length > 0 && (
        <div className="problem-grid">
          {problems.map(({ id, problem }) => (
            <article className="problem-card" key={id}>
              <div className="card-topline"><span className="difficulty-label">{problem.difficulty}</span><span className="question-number">#{problem.leetcode_id}</span></div>
              <h3>{problem.title}</h3>
              <p className="pattern-label">{problem.pattern?.p_name || 'Uncategorized pattern'}</p>
              <div className="card-footer">
                <Link to={`/problems/${problem.id}`}>View details <span>↗</span></Link>
                <div className="problem-card-actions">
                  {problem.link && <a href={problem.link} rel="noreferrer" target="_blank">LeetCode ↗</a>}
                  <button
                    aria-label={`Remove ${problem.title} from your problems`}
                    className="problem-remove-button"
                    disabled={removingId === id}
                    onClick={() => removeProblem(id, problem.title)}
                    type="button"
                  >
                    {removingId === id ? 'Removing…' : 'Remove'}
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
      <AddProblemModalLayer
        onAdded={() => setReloadKey((key) => key + 1)}
        onClose={() => setAddModalOpen(false)}
        open={addModalOpen}
      />
    </main>
  )
}

export function ProblemDetailPage() {
  const { id } = useParams()
  const { data, loading, error } = useRequest('/api/problems/tracked/')
  const entry = data?.find(({ problem }) => String(problem.id) === id)

  return (
    <main className="route-page">
      <Link className="back-link" to="/problems">← All problems</Link>
      {loading && <div className="empty-state">Loading problem...</div>}
      {error && <div className="empty-state error-state" role="alert">{error}</div>}
      {!loading && !error && !entry && <div className="empty-state">This problem isn’t in your reviewed problem list.</div>}
      {entry && <PageHeading eyebrow={entry.problem.pattern?.p_name || 'PROBLEM'} title={entry.problem.title} description={`${entry.problem.difficulty} · LeetCode #${entry.problem.leetcode_id}`} />}
      {entry?.problem.link && <a className="primary-button" href={entry.problem.link} rel="noreferrer" target="_blank">Open on LeetCode ↗</a>}
    </main>
  )
}

export function RevisionsPage() {
  const { data, loading, error } = useRequest('/api/revisions/due-today/')
  const isValidResponse = Array.isArray(data)
  const revisions = isValidResponse ? data : []

  return (
    <main className="route-page">
      <PageHeading eyebrow="SPACED REPETITION" title="Today’s revisions" description="Review the problems that are due today to keep your recall strong." />
      {loading && <div className="empty-state">Loading today’s revisions...</div>}
      {error && <div className="empty-state error-state" role="alert">{error}</div>}
      {!loading && !error && !isValidResponse && <div className="empty-state error-state" role="alert">The due reviews response had an unexpected format.</div>}
      {!loading && !error && isValidResponse && revisions.length === 0 && <div className="empty-state">You’re all caught up. Add problems to your revision queue from <Link to="/sheets">curated sheets</Link>.</div>}
      {!loading && !error && isValidResponse && revisions.length > 0 && (
        <div className="problem-grid">
          {revisions.map(({ id, problem, confidence_rating: confidence, overdue_days: overdueDays }) => (
            <article className="problem-card" key={id}>
              <div className="card-topline"><span className="difficulty-label">{problem.difficulty}</span><span className="question-number">{overdueDays ? `${overdueDays}d overdue` : 'Due today'}</span></div>
              <h3>{problem.title}</h3>
              <p className="pattern-label">{problem.pattern?.p_name || 'Uncategorized pattern'} · Recall {confidence}/5</p>
              <div className="card-footer"><Link to={`/problems/${problem.id}`}>Problem details ↗</Link>{problem.link && <a href={problem.link} rel="noreferrer" target="_blank">Review on LeetCode ↗</a>}</div>
            </article>
          ))}
        </div>
      )}
    </main>
  )
}

export function AssessmentsPage() {
  return (
    <main className="route-page">
      <PageHeading eyebrow="RECALL CHECK" title="Assessments" description="Check how well you remember the problems in your revision queue." />
      <div className="assessment-route-links">
        <Link className="primary-button" to="/assessments/current">Start or continue an assessment</Link>
        <Link className="secondary-button" to="/assessments/history">View assessment history</Link>
      </div>
    </main>
  )
}

export function SimpleRoutePage({ eyebrow, title, description, action, actionLabel }) {
  return (
    <main className="route-page">
      <PageHeading eyebrow={eyebrow} title={title} description={description} />
      {action && <Link className="primary-button" to={action}>{actionLabel}</Link>}
    </main>
  )
}

function PageHeading({ eyebrow, title, description }) {
  return (
    <section className="route-page-heading">
      <p className="eyebrow">{eyebrow}</p>
      <h1>{title}</h1>
      <p>{description}</p>
    </section>
  )
}
