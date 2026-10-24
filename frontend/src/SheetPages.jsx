import { useCallback, useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { useAuth } from './context/useAuth.js'

const difficultyStyles = { Easy: 'easy', Medium: 'medium', Hard: 'hard' }

function SheetProgress({ tracked, total }) {
  const percent = total ? Math.round((tracked / total) * 100) : 0
  return (
    <div className="sheet-progress">
      <div className="sheet-progress-label"><span>{tracked}/{total} tracked</span><span>{percent}%</span></div>
      <div className="progress-track"><span style={{ width: `${percent}%` }} /></div>
    </div>
  )
}

export function SheetExplorer() {
  const { authenticatedRequest } = useAuth()
  const [sheets, setSheets] = useState([])
  const [filter, setFilter] = useState('featured')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    authenticatedRequest('/api/sheets/')
      .then((data) => {
        if (active) setSheets(data)
      })
      .catch((requestError) => {
        if (active) setError(requestError.message)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [authenticatedRequest])

  const visibleSheets = filter === 'featured' ? sheets.filter((sheet) => sheet.is_featured) : sheets

  return (
    <main className="sheets-page">
      <div className="sheets-content">
        <section className="sheets-intro">
          <p className="eyebrow">CURATED PRACTICE</p>
          <h1>Choose a path.<br />Build the habit.</h1>
          <p>Start with a trusted interview sheet and add its problems to your personal revision queue in one click.</p>
        </section>
        <div className="section-heading sheets-section-heading">
          <div><p className="eyebrow">THE LIBRARY</p><h2>Explore DSA sheets</h2></div>
          <div className="sheet-filter" aria-label="Filter sheets">
            <button className={filter === 'featured' ? 'active' : ''} onClick={() => setFilter('featured')} type="button">Featured</button>
            <button className={filter === 'all' ? 'active' : ''} onClick={() => setFilter('all')} type="button">All sheets</button>
          </div>
        </div>
        {loading && <div className="empty-state">Loading curated sheets...</div>}
        {error && <div className="empty-state error-state">{error}</div>}
        {!loading && !error && visibleSheets.length === 0 && (
          <div className="empty-state">
            <strong>No sheets found.</strong>
            <p>Seed your curated library with <code>python manage.py seed_sheets</code> from the backend folder.</p>
            {filter === 'featured' && sheets.length > 0 && <button className="secondary-button" onClick={() => setFilter('all')} type="button">Browse all sheets</button>}
          </div>
        )}
        {!loading && !error && visibleSheets.length > 0 && (
          <div className="sheet-card-grid">
            {visibleSheets.map((sheet) => (
              <article className="sheet-card" key={sheet.id}>
                {sheet.cover_image_url
                  ? <img alt="" className="sheet-cover" src={sheet.cover_image_url} />
                  : <div className="sheet-cover sheet-cover-placeholder" aria-hidden="true"><span>{sheet.title.slice(0, 1)}</span></div>}
                <div className="sheet-card-body">
                  <div className="sheet-card-title"><div><p className="eyebrow">{sheet.author || 'CURATED SHEET'}</p><h3>{sheet.title}</h3></div>{sheet.is_featured && <span className="featured-badge">FEATURED</span>}</div>
                  <p className="sheet-card-description">{sheet.description}</p>
                  <SheetProgress tracked={sheet.tracked_count} total={sheet.total_problems} />
                  <div className="sheet-card-footer"><span>{sheet.total_problems} problems</span><a className="primary-button" href={`/sheets/${sheet.slug}`}>Explore <span>↗</span></a></div>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </main>
  )
}

export function SheetDetail({ slug }) {
  const { authenticatedRequest } = useAuth()
  const [sheet, setSheet] = useState(null)
  const [selected, setSelected] = useState(new Set())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const loadSheet = useCallback(async () => {
    const data = await authenticatedRequest(`/api/sheets/${encodeURIComponent(slug)}/`)
    setSheet(data)
  }, [authenticatedRequest, slug])

  useEffect(() => {
    let active = true
    authenticatedRequest(`/api/sheets/${encodeURIComponent(slug)}/`)
      .then((data) => {
        if (active) setSheet(data)
      })
      .catch((requestError) => {
        if (active) setError(requestError.message)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [authenticatedRequest, slug])

  const toggleSelected = (problemId) => {
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(problemId)) next.delete(problemId)
      else next.add(problemId)
      return next
    })
  }

  const trackProblems = async (path, payload) => {
    setSubmitting(true)
    try {
      const result = await authenticatedRequest(`/api/sheets/${encodeURIComponent(slug)}/${path}/`, {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      toast.success(`Added ${result.added_count} ${result.added_count === 1 ? 'problem' : 'problems'} to your revision queue`)
      setSelected(new Set())
      await loadSheet()
    } catch (requestError) {
      toast.error(requestError.message)
    } finally {
      setSubmitting(false)
    }
  }

  const allProblems = sheet?.categories?.flatMap((category) => category.problems) ?? []
  const trackedCount = sheet?.tracked_count ?? 0
  const totalProblems = sheet?.total_problems ?? allProblems.length

  return (
    <main className="sheets-page sheet-detail-page">
      <div className="sheets-content">
        <a className="back-link" href="/sheets">← All sheets</a>
        {loading && <div className="empty-state">Loading sheet...</div>}
        {error && <div className="empty-state error-state">{error}</div>}
        {!loading && !error && sheet && (
          <>
            <section className="sheet-detail-hero">
              <div className="sheet-detail-copy">
                <p className="eyebrow">{sheet.author || 'CURATED PRACTICE'}</p>
                <h1>{sheet.title}</h1>
                <p>{sheet.description}</p>
                <SheetProgress tracked={trackedCount} total={totalProblems} />
                <div className="sheet-detail-actions">
                  <button className="primary-button" disabled={submitting || trackedCount === totalProblems} onClick={() => trackProblems('track-all', {})} type="button">
                    {submitting ? 'Adding...' : trackedCount === totalProblems ? 'All problems tracked' : 'Track All Problems'}
                  </button>
                  <span>{totalProblems} problems · {sheet.categories.length} patterns</span>
                </div>
              </div>
              {sheet.cover_image_url && <img className="sheet-detail-cover" alt="" src={sheet.cover_image_url} />}
            </section>
            <div className="sheet-problem-heading"><div><p className="eyebrow">BY PATTERN</p><h2>Problems in this sheet</h2></div><span className="result-count">{trackedCount}/{totalProblems} tracked</span></div>
            <div className="sheet-category-list">
              {sheet.categories.map((category) => (
                <details className="sheet-category" key={category.name} open>
                  <summary><span>{category.name}</span><span className="category-count">{category.problems.length} problems</span></summary>
                  <div className="sheet-problem-list">
                    {category.problems.map(({ problem, is_tracked_by_user: isTracked }) => (
                      <article className={`sheet-problem-row ${isTracked ? 'is-tracked' : ''}`} key={problem.id}>
                        <label className="sheet-problem-select">
                          <input
                            aria-label={`${isTracked ? 'Tracked' : 'Select'} ${problem.title}`}
                            checked={isTracked || selected.has(problem.id)}
                            disabled={isTracked || submitting}
                            onChange={() => toggleSelected(problem.id)}
                            type="checkbox"
                          />
                          <span className="custom-checkbox" aria-hidden="true">{isTracked ? '✓' : selected.has(problem.id) ? '✓' : ''}</span>
                        </label>
                        <div className="sheet-problem-main"><span className="sheet-problem-order">{String(problem.leetcode_id).padStart(3, '0')}</span><a href={problem.link} rel="noreferrer" target="_blank">{problem.title} <span aria-hidden="true">↗</span></a></div>
                        <span className={`difficulty-label ${difficultyStyles[problem.difficulty]}`}>{problem.difficulty}</span>
                        <span className="sheet-tracked-label">{isTracked ? 'In your queue' : 'Not tracked'}</span>
                      </article>
                    ))}
                  </div>
                </details>
              ))}
            </div>
          </>
        )}
      </div>
      {selected.size > 0 && (
        <div className="sheet-bulk-bar">
          <span>{selected.size} problem{selected.size === 1 ? '' : 's'} selected</span>
          <button className="primary-button" disabled={submitting} onClick={() => trackProblems('track-selected', { problem_ids: [...selected] })} type="button">
            {submitting ? 'Adding...' : 'Track Selected'}
          </button>
        </div>
      )}
    </main>
  )
}
