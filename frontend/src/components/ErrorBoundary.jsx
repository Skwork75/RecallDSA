import { Component } from 'react'

export default class ErrorBoundary extends Component {
  state = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error, errorInfo) {
    console.error('Application render error:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="loading-screen" role="alert">
          <h1>Something went wrong</h1>
          <p>RecallDSA could not display this page.</p>
          <button className="primary-button" onClick={() => window.location.reload()} type="button">Reload page</button>
        </main>
      )
    }

    return this.props.children
  }
}
