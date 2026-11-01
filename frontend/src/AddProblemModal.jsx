import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import toast from 'react-hot-toast'
import { useAuth } from './context/useAuth.js'

const confidenceLabels = {
  1: 'Forgot completely',
  2: 'Struggled a lot',
  3: 'Solved with hints',
  4: 'Minor difficulty',
  5: 'Instant recall',
}

const patternOptions = [
  'Arrays',
  'Two Pointers',
  'Sliding Window',
  'Stack',
  'Binary Search',
  'Linked List',
  'Trees',
  'Tries',
  'Heap/Priority Queue',
  'Backtracking',
  'Graphs',
  'Dynamic Programming',
  'Greedy',
  'Intervals',
  'Math & Geometry',
  'Bit Manipulation',
  '1-D DP',
  '2-D DP',
  'Advanced Graphs',
  'Monotonic Stack',
  'Hash Table',
  'String',
  'Divide and Conquer',
  'Union Find',
  'Topological Sort',
]

export default function AddProblemModal({ onClose, onAdded }) {
  const { authenticatedRequest } = useAuth()
  const reduceMotion = useReducedMotion()
  const formRef = useRef(null)
  const [tab, setTab] = useState('url')
  const [url, setUrl] = useState('')
  const [preview, setPreview] = useState(null)
  const [confidence, setConfidence] = useState(3)
  const [manual, setManual] = useState({
    title: '',
    difficulty: 'Medium',
    patterns: [],
    notes: '',
  })
  const [loadingPreview, setLoadingPreview] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    document.body.classList.add('modal-open')
    const closeOnEscape = (event) => {
      if (event.key === 'Escape' && !submitting) onClose()
    }
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.body.classList.remove('modal-open')
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [onClose, submitting])

  const fetchPreview = async (event) => {
    event.preventDefault()
    setError('')
    setLoadingPreview(true)
    try {
      const result = await authenticatedRequest('/api/problems/preview-url/', {
        method: 'POST',
        body: JSON.stringify({ url }),
      })
      setPreview(result)
      setManual((current) => ({
        ...current,
        title: result.title,
        difficulty: result.difficulty,
        patterns: result.pattern_names,
      }))
    } catch (requestError) {
      setPreview(null)
      setError(requestError.message)
    } finally {
      setLoadingPreview(false)
    }
  }

  const addProblem = async (event) => {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    const payload = {
      url,
      initial_confidence: confidence,
    }
    if (tab === 'manual') {
      payload.title = manual.title
      payload.difficulty = manual.difficulty
      payload.pattern_names = manual.patterns
      payload.notes = manual.notes
    }

    try {
      const progress = await authenticatedRequest('/api/problems/add-from-url/', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      if (progress.added) {
        toast.success('Problem added to your revision queue')
      } else {
        toast.success('This problem is already in your revision queue')
      }
      onAdded()
      onClose()
    } catch (requestError) {
      setError(requestError.message)
      toast.error(requestError.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <motion.div
      animate={{ opacity: 1 }}
      className="review-modal-backdrop"
      exit={{ opacity: 0 }}
      initial={reduceMotion ? false : { opacity: 0 }}
      onClick={(event) => {
        if (event.target === event.currentTarget && !submitting) onClose()
      }}
      role="presentation"
      transition={{ duration: reduceMotion ? 0 : 0.18 }}
    >
      <motion.section
        animate={{ opacity: 1, y: 0, scale: 1 }}
        aria-labelledby="add-problem-title"
        aria-modal="true"
        className="review-modal add-problem-modal"
        exit={{ opacity: 0, y: 16, scale: 0.98 }}
        initial={reduceMotion ? false : { opacity: 0, y: 16, scale: 0.98 }}
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        transition={{ duration: reduceMotion ? 0 : 0.2 }}
      >
        <p className="eyebrow">GROW YOUR REVISION QUEUE</p>
        <h2 id="add-problem-title">Add a problem</h2>
        <p className="review-modal-subtitle">Import a LeetCode problem or add your own notes and pattern labels.</p>

        <div className="add-problem-tabs" role="tablist" aria-label="Problem entry method">
          <button
            aria-selected={tab === 'url'}
            className={tab === 'url' ? 'active' : ''}
            onClick={() => { setTab('url'); setError('') }}
            role="tab"
            type="button"
          >
            Paste URL
          </button>
          <button
            aria-selected={tab === 'manual'}
            className={tab === 'manual' ? 'active' : ''}
            onClick={() => { setTab('manual'); setError('') }}
            role="tab"
            type="button"
          >
            Manual Entry
          </button>
        </div>

        <form className="add-problem-form" onSubmit={tab === 'url' ? fetchPreview : addProblem} ref={formRef}>
          <label>
            LeetCode problem URL
            <input
              autoComplete="url"
              onChange={(event) => { setUrl(event.target.value); setPreview(null) }}
              placeholder="https://leetcode.com/problems/two-sum/"
              required
              type="url"
              value={url}
            />
          </label>

          {tab === 'manual' && (
            <div className="add-problem-manual-fields">
              <label>
                Title
                <input
                  maxLength={255}
                  onChange={(event) => setManual({ ...manual, title: event.target.value })}
                  required
                  value={manual.title}
                />
              </label>
              <label>
                Difficulty
                <select
                  onChange={(event) => setManual({ ...manual, difficulty: event.target.value })}
                  value={manual.difficulty}
                >
                  {['Easy', 'Medium', 'Hard'].map((difficulty) => <option key={difficulty}>{difficulty}</option>)}
                </select>
              </label>
              <fieldset className="add-problem-pattern-fieldset">
                <legend>Patterns</legend>
                <span className="add-problem-pattern-grid">
                  {[...new Set([...patternOptions, ...manual.patterns])].map((pattern) => (
                    <label className="add-problem-pattern-option" key={pattern}>
                      <input
                        checked={manual.patterns.includes(pattern)}
                        onChange={(event) => setManual((current) => ({
                          ...current,
                          patterns: event.target.checked
                            ? [...current.patterns, pattern]
                            : current.patterns.filter((name) => name !== pattern),
                        }))}
                        type="checkbox"
                      />
                      {pattern}
                    </label>
                  ))}
                </span>
              </fieldset>
              <label>
                Notes
                <textarea
                  maxLength={10000}
                  onChange={(event) => setManual({ ...manual, notes: event.target.value })}
                  placeholder="Add a reminder for your next review"
                  rows={3}
                  value={manual.notes}
                />
              </label>
            </div>
          )}

          {tab === 'url' && (
            <button className="secondary-button add-problem-fetch" disabled={loadingPreview || !url.trim()} type="submit">
              {loadingPreview ? 'Fetching problem…' : 'Fetch Problem'}
            </button>
          )}
        </form>

        {error && <p className="add-problem-error" role="alert">{error}</p>}

        {tab === 'url' && preview && (
          <article className="add-problem-preview">
            <div className="card-topline">
              <span className={`difficulty-dot ${preview.difficulty.toLowerCase()}`} />
              <span className="difficulty-label">{preview.difficulty}</span>
              <span className="question-number">#{preview.leetcode_id}</span>
            </div>
            <h3>{preview.title}</h3>
            <p>{preview.pattern_names.length ? preview.pattern_names.join(' · ') : 'No pattern tags'}</p>
            {preview.is_tracked && <span className="add-problem-hint">Already in your revision queue</span>}
          </article>
        )}

        <div className="add-problem-confidence">
          <label htmlFor="initial-confidence">Initial confidence: {confidence}/5</label>
          <input
            id="initial-confidence"
            max="5"
            min="1"
            onChange={(event) => setConfidence(Number(event.target.value))}
            type="range"
            value={confidence}
          />
          <span className="add-problem-hint">{confidenceLabels[confidence]}</span>
        </div>

        <div className="review-modal-actions">
          <button className="secondary-button" disabled={submitting} onClick={onClose} type="button">Cancel</button>
          <button
            className="primary-button"
            disabled={submitting || loadingPreview || (tab === 'url' && (!preview || preview.is_tracked))}
            onClick={(event) => {
              if (tab === 'manual') formRef.current?.requestSubmit()
              else addProblem(event)
            }}
            type="button"
          >
            {submitting ? 'Adding…' : 'Add to Revisions'}
          </button>
        </div>
      </motion.section>
    </motion.div>
  )
}

export function AddProblemModalLayer({ open, onClose, onAdded }) {
  return (
    <AnimatePresence>
      {open && <AddProblemModal key="add-problem" onAdded={onAdded} onClose={onClose} />}
    </AnimatePresence>
  )
}
