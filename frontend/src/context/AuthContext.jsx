import { useEffect, useState } from 'react'
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
  const data = response.status === 205 ? null : await response.json()

  if (!response.ok) {
    const validationMessage = data && typeof data === 'object'
      ? Object.values(data).flat().join(' ')
      : ''
    throw new Error(validationMessage || 'Authentication request failed')
  }

  return data
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

  return (
    <AuthContext.Provider value={{ user, loading, register, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}
