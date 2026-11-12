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
  const [revisionSheetOpen, setRevisionSheetOpen] = useState(false)
  const [selectedProblemIds, setSelectedProblemIds] = useState([])
  const [generatingSheet, setGeneratingSheet] = useState(false)
  const [removingId, setRemovingId] = useState(null)
  const { authenticatedRequest } = useAuth()
  const { data, loading, error } = useRequest('/api/problems/tracked/', reloadKey)
  const isValidResponse = Array.isArray(data)
  const problems = isValidResponse ? data : []
  const recentlySynced = problems
    .filter(({ recently_synced }) => recently_synced)
    .sort((left, right) => new Date(right.accepted_at) - new Date(left.accepted_at))
  const otherTracked = problems.filter(({ recently_synced }) => !recently_synced)

  useEffect(() => {
    const reload = () => setReloadKey((key) => key + 1)
    window.addEventListener('recalldsa:leetcode-synced', reload)
    return () => window.removeEventListener('recalldsa:leetcode-synced', reload)
  }, [])

  const toggleProblemSelection = (problemId, selected) => {
    setSelectedProblemIds((current) => {
      if (!selected) return current.filter((id) => id !== problemId)
      if (current.length >= 5 || current.includes(problemId)) return current
      return [...current, problemId]
    })
  }

  const generateRevisionSheet = async () => {
    setGeneratingSheet(true)
    try {
      const result = await authenticatedRequest('/api/problems/revision-sheet/', {
        method: 'POST',
        body: JSON.stringify({ problem_ids: selectedProblemIds }),
      })
      if (!Array.isArray(result?.problems) || result.problems.length !== selectedProblemIds.length) {
        throw new Error('The server returned an incomplete revision sheet. Please try again.')
      }
      await downloadRevisionSheet(result.problems)
      setRevisionSheetOpen(false)
      setSelectedProblemIds([])
      toast.success('Revision sheet PDF downloaded')
    } catch (requestError) {
      toast.error(requestError.message)
    } finally {
      setGeneratingSheet(false)
    }
  }

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

  const renderProblemCard = ({ id, problem, source, recently_synced: recentlySyncedProblem }) => (
    <article className="problem-card" key={id}>
      <div className="card-topline">
        <span className="difficulty-label">{problem.difficulty}</span>
        <span className="question-number">#{problem.leetcode_id}</span>
        {(source === 'leetcode_sync' || recentlySyncedProblem) && <span className="leetcode-source-label">LeetCode</span>}
      </div>
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
  )

  return (
    <main className="route-page">
      <div className="problem-page-heading">
        <PageHeading eyebrow="YOUR LIBRARY" title="Tracked problems" description="Problems you have practiced and added to your personal recall history." />
        <div className="problem-heading-actions">
          <button
            className="secondary-button"
            disabled={loading || problems.length === 0}
            onClick={() => setRevisionSheetOpen(true)}
            type="button"
          >
            Revision sheet
          </button>
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
      </div>
      {loading && <div className="empty-state">Loading your problems...</div>}
      {error && <div className="empty-state error-state" role="alert">{error}</div>}
      {!loading && !error && !isValidResponse && <div className="empty-state error-state" role="alert">The tracked problems response had an unexpected format.</div>}
      {!loading && !error && isValidResponse && problems.length === 0 && <div className="empty-state">No problems tracked yet. Start with a curated <Link to="/sheets">DSA sheet</Link> or browse your <Link to="/dashboard">dashboard</Link>.</div>}
      {!loading && !error && isValidResponse && recentlySynced.length > 0 && (
        <section aria-labelledby="recently-synced-title" className="tracked-problem-section">
          <div className="section-heading">
            <div><p className="eyebrow">LEETCODE IMPORT</p><h2 id="recently-synced-title">Recently synced</h2></div>
            <span className="result-count">{recentlySynced.length} problem{recentlySynced.length === 1 ? '' : 's'}</span>
          </div>
          <div className="problem-grid">{recentlySynced.map(renderProblemCard)}</div>
        </section>
      )}
      {!loading && !error && isValidResponse && otherTracked.length > 0 && (
        <section aria-labelledby="all-tracked-title" className="tracked-problem-section">
          {recentlySynced.length > 0 && <div className="section-heading"><div><p className="eyebrow">YOUR LIBRARY</p><h2 id="all-tracked-title">All other tracked problems</h2></div><span className="result-count">{otherTracked.length} problem{otherTracked.length === 1 ? '' : 's'}</span></div>}
          <div className="problem-grid">{otherTracked.map(renderProblemCard)}</div>
        </section>
      )}
      <AddProblemModalLayer
        onAdded={() => setReloadKey((key) => key + 1)}
        onClose={() => setAddModalOpen(false)}
        open={addModalOpen}
      />
      {revisionSheetOpen && (
        <RevisionSheetDialog
          generating={generatingSheet}
          onClose={() => {
            if (!generatingSheet) setRevisionSheetOpen(false)
          }}
          onGenerate={generateRevisionSheet}
          onSelectAll={() => setSelectedProblemIds(problems.slice(0, 5).map(({ problem }) => problem.id))}
          onToggle={toggleProblemSelection}
          problems={problems}
          selectedIds={selectedProblemIds}
        />
      )}
    </main>
  )
}

function RevisionSheetDialog({ problems, selectedIds, onToggle, onSelectAll, onClose, onGenerate, generating }) {
  useEffect(() => {
    document.body.classList.add('modal-open')
    const closeOnEscape = (event) => {
      if (event.key === 'Escape' && !generating) onClose()
    }
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.body.classList.remove('modal-open')
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [generating, onClose])

  return (
    <div className="revision-sheet-backdrop" onClick={onClose}>
      <section
        aria-labelledby="revision-sheet-title"
        aria-modal="true"
        className="revision-sheet-dialog"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
      >
        <div className="revision-sheet-dialog-heading">
          <div>
            <p className="eyebrow">PDF EXPORT</p>
            <h2 id="revision-sheet-title">Choose problems</h2>
            <p>Select up to 5 tracked problems for your revision sheet.</p>
          </div>
          <button aria-label="Close revision sheet dialog" className="dialog-close-button" disabled={generating} onClick={onClose} type="button">×</button>
        </div>
        <div className="revision-sheet-selection-tools">
          <span>{selectedIds.length} of 5 selected</span>
          <button disabled={generating || problems.length === 0} onClick={onSelectAll} type="button">
            {problems.length > 5 ? 'Select first 5' : 'Select all'}
          </button>
        </div>
        <p className="revision-sheet-generation-note">
          The first local generation can take a little while. Generated content is saved for future sheets.
        </p>
        <div className="revision-sheet-problem-list">
          {problems.map(({ problem }) => {
            const selected = selectedIds.includes(problem.id)
            return (
              <label className="revision-sheet-problem-option" key={problem.id}>
                <input
                  checked={selected}
                  disabled={generating || (!selected && selectedIds.length >= 5)}
                  onChange={(event) => onToggle(problem.id, event.target.checked)}
                  type="checkbox"
                />
                <span>
                  <strong>{problem.title}</strong>
                  <small>{problem.difficulty} · LeetCode #{problem.leetcode_id}</small>
                </span>
              </label>
            )
          })}
        </div>
        <div className="revision-sheet-dialog-actions">
          <button className="secondary-button" disabled={generating} onClick={onClose} type="button">Cancel</button>
          <button className="primary-button" disabled={generating || selectedIds.length === 0} onClick={onGenerate} type="button">
            {generating ? 'Generating PDF…' : `Create PDF (${selectedIds.length})`}
          </button>
        </div>
      </section>
    </div>
  )
}

async function downloadRevisionSheet(problems) {
  const { jsPDF } = await import('jspdf')
  const pdf = new jsPDF({ format: 'a4', unit: 'mm' })
  const pageWidth = pdf.internal.pageSize.getWidth()
  const pageHeight = pdf.internal.pageSize.getHeight()
  const margin = 17
  const contentWidth = pageWidth - margin * 2
  let cursorY = margin

  const addText = (text, { size = 10, font = 'normal', color = [35, 45, 62], gap = 1.5 } = {}) => {
    pdf.setFont('helvetica', font)
    pdf.setFontSize(size)
    pdf.setTextColor(...color)
    const lines = pdf.splitTextToSize(String(text || 'Not provided'), contentWidth)
    const lineHeight = size * 0.42
    for (const line of lines) {
      if (cursorY + lineHeight > pageHeight - margin) {
        pdf.addPage()
        cursorY = margin
      }
      pdf.text(line, margin, cursorY)
      cursorY += lineHeight
    }
    cursorY += gap
  }

  addText('RecallDSA · Revision sheet', { size: 18, font: 'bold', color: [35, 45, 62], gap: 2 })
  addText(`Generated ${new Date().toLocaleDateString()} · ${problems.length} problem${problems.length === 1 ? '' : 's'}`, {
    size: 9,
    color: [100, 112, 132],
    gap: 5,
  })

  problems.forEach((problem, index) => {
    if (index > 0) {
      pdf.addPage()
      cursorY = margin
    }
    addText(`${index + 1}. ${problem.title}  ·  ${problem.difficulty}  ·  LeetCode #${problem.leetcode_id}`, {
      size: 15,
      font: 'bold',
      color: [43, 58, 135],
      gap: 3,
    })
    addText('Problem description', { size: 11, font: 'bold', gap: 1 })
    addText(problem.description, { size: 10, gap: 4 })
    addText('Python solution', { size: 11, font: 'bold', gap: 1 })
    const solution = problem.python_solution.replace(/^```(?:python)?\s*/i, '').replace(/\s*```$/, '')
    addText(solution, { size: 9, font: 'normal', color: [34, 79, 67], gap: 4 })
    addText('Explanation', { size: 11, font: 'bold', gap: 1 })
    addText(problem.explanation, { size: 10, gap: 4 })
    addText('Test cases', { size: 11, font: 'bold', gap: 1 })
    problem.test_cases.forEach((testCase, testIndex) => {
      addText(`Test ${testIndex + 1}`, { size: 10, font: 'bold', gap: 0.5 })
      addText(`Input: ${testCase.input}`, { size: 9, font: 'normal', gap: 0.5 })
      addText(`Expected output: ${testCase.expected_output}`, { size: 9, gap: 2 })
    })
  })

  pdf.save('recalldsa-revision-sheet.pdf')
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
