import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <main className="not-found-page">
      <p className="eyebrow">404 · PAGE NOT FOUND</p>
      <h1>That path isn’t in your practice plan.</h1>
      <p>It may have moved, or the link may be incorrect.</p>
      <Link className="primary-button" to="/">Back to RecallDSA</Link>
    </main>
  )
}
