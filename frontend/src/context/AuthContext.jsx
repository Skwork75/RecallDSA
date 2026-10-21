import { useCallback, useEffect, useState } from 'react'
import { AuthContext } from './AuthContext.js'
const storageKey = 'recalldsa-auth'

function getStoredAuth() {
  try {
    return JSON.parse(localStorage.getItem(storageKey)) ?? null
  } catch {
    return null
  }
}

function saveAuth(auth) {
  if (auth) {
    localStorage.setItem(storageKey, JSON.stringify(auth))
  } else {
    localStorage.removeItem(storageKey)
  }
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })
  if (response.status === 204 || response.status === 205) {
    return null
  }

  const contentType = response.headers.get('content-type') || ''
  if (!contentType.includes('application/json') && !contentType.includes('+json')) {
    throw new Error(`The API returned an unexpected response (${response.status}). Check that Django is running and its database migrations are applied.`)
  }

  let data
  try {
    data = await response.json()
  } catch {
    throw new Error(`The API returned invalid JSON (${response.status}). Check the Django server output for the underlying error.`)
  }

  if (!response.ok) {
    const validationMessage = getErrorMessage(data)
    throw new Error(validationMessage || 'Authentication request failed')
  }

  return data
}

function getErrorMessage(value) {
  if (typeof value === 'string') {
    return value
  }
  if (Array.isArray(value)) {
    return value.map(getErrorMessage).filter(Boolean).join(' ')
  }
  if (value && typeof value === 'object') {
    if (value.detail) {
      return getErrorMessage(value.detail)
    }
    return Object.values(value).map(getErrorMessage).filter(Boolean).join(' ')
  }
  return ''
}

export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(getStoredAuth)
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(() => Boolean(getStoredAuth()?.access))

  useEffect(() => {
    if (!auth?.access) {
      return
    }

    request('/api/auth/me/', {
      headers: { Authorization: `Bearer ${auth.access}` },
    })
      .then(setUser)
      .catch(() => {
        setAuth(null)
        saveAuth(null)
      })
      .finally(() => setLoading(false))
  }, [auth?.access])

  const authenticate = async (path, credentials) => {
    const result = await request(path, {
      method: 'POST',
      body: JSON.stringify(credentials),
    })
    setAuth({ access: result.access, refresh: result.refresh })
    saveAuth({ access: result.access, refresh: result.refresh })
    setUser(result.user)
    return result.user
  }

  const register = (credentials) => authenticate('/api/auth/register/', credentials)
  const login = (credentials) => authenticate('/api/auth/login/', credentials)

  const logout = async () => {
    try {
      if (auth?.access && auth?.refresh) {
        await request('/api/auth/logout/', {
          method: 'POST',
          headers: { Authorization: `Bearer ${auth.access}` },
          body: JSON.stringify({ refresh: auth.refresh }),
        })
      }
    } finally {
      setAuth(null)
      setUser(null)
      saveAuth(null)
    }
  }

  const authenticatedRequest = useCallback((path, options = {}) => request(path, {
    ...options,
    headers: {
      Authorization: `Bearer ${auth?.access}`,
      ...options.headers,
    },
  }), [auth?.access])

  return (
    <AuthContext.Provider value={{ user, loading, register, login, logout, authenticatedRequest }}>
      {children}
    </AuthContext.Provider>
  )
}
