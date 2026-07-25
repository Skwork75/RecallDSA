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
    <div style={styles.container}>
      <h1>RecallDSA Prototype</h1>
      <p>These questions are being loaded from the Django backend API.</p>

      {loading && <p>Loading questions...</p>}
      {error && <p style={styles.error}>{error}</p>}

      {!loading && !error && questions.length === 0 && (
        <p>No questions are available yet.</p>
      )}

      <ul style={styles.list}>
        {questions.map((question) => (
          <li key={question.id ?? question.q_id} style={styles.card}>
            <strong>{question.q_name || `Question ${question.q_id}`}</strong>
            <p>Question ID: {question.q_id}</p>
            {question.q_link ? (
              <a href={question.q_link} target="_blank" rel="noreferrer">
                Open question
              </a>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  )
}

const styles = {
  container: {
    maxWidth: '900px',
    margin: '3rem auto',
    padding: '2rem',
    fontFamily: 'Arial, sans-serif',
  },
  list: {
    listStyle: 'none',
    padding: 0,
    display: 'grid',
    gap: '1rem',
  },
  card: {
    border: '1px solid #ddd',
    borderRadius: '10px',
    padding: '1rem',
    background: '#f9f9f9',
  },
  error: {
    color: 'crimson',
  },
}

export default App
