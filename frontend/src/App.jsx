import { useEffect, useState } from 'react'

function App() {
  const [questions, setQuestions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const fetchQuestions = async () => {
      try {
        const response = await fetch('/api/home/')

        if (!response.ok) {
          throw new Error('Unable to load questions from the API')
        }

        const data = await response.json()
        setQuestions(data)
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }

    fetchQuestions()
  }, [])

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-12 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <section className="rounded-2xl border border-slate-800 bg-slate-900/80 p-8 shadow-2xl shadow-black/20 backdrop-blur">
          <span className="mb-4 inline-flex rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-sm font-medium text-cyan-300">
            RecallDSA Prototype
          </span>
          <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
            Week Questions
          </h1>
          <p className="mt-4 max-w-2xl text-lg text-slate-300">
            These questions are in pattern wise format. You can click on the question link to open it in a new tab. 
          </p>
        </section>

        {loading && (
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 text-slate-300">
            Loading questions...
          </div>
        )}

        {error && (
          <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-6 text-rose-300">
            {error}
          </div>
        )}

        {!loading && !error && questions.length === 0 && (
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 text-slate-300">
            No questions are available yet.
          </div>
        )}

        {!loading && !error && questions.length > 0 && (
          <ul className="grid gap-4 md:grid-cols-2">
            {questions.map((question) => (
              <li
                key={question.id ?? question.q_id}
                className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-lg shadow-black/10"
              >
                <h2 className="text-xl font-semibold text-white">
                  {question.q_name || `Question ${question.q_id}`}
                </h2>
                <p className="mt-2 text-sm text-slate-400">Question ID: {question.q_id}</p>
                {question.q_link ? (
                  <a
                    href={question.q_link}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-4 inline-flex items-center rounded-full border border-slate-700 bg-slate-800 px-4 py-2 text-sm font-medium text-cyan-300 transition hover:border-cyan-400 hover:text-cyan-200"
                  >
                    Open question
                  </a>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

export default App
