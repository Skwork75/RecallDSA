import { useCallback, useEffect, useRef, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { useAuth } from '../context/useAuth.js'

const navItems = [
  { label: 'Dashboard', to: '/dashboard', icon: '▦' },
  { label: 'Problems', to: '/problems', icon: '⌘' },
  { label: 'Sheets', to: '/sheets', icon: '▤' },
  { label: 'Revisions', to: '/revisions', icon: '◷' },
  { label: 'Assessments', to: '/assessments', icon: '◇' },
  { label: 'Analytics', to: '/analytics', icon: '▥' },
]

function Brand() {
  return (
    <span className="brand-lockup">
      <span className="brand-mark">R</span>
      <span>Recall<span>DSA</span></span>
    </span>
  )
}

function UserDropdown({ user, onClose }) {
  const { logout } = useAuth()
  const navigate = useNavigate()
  const menuRef = useRef(null)

  useEffect(() => {
    const closeOnOutsideClick = (event) => {
      if (!menuRef.current?.contains(event.target)) onClose()
    }
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('pointerdown', closeOnOutsideClick)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('pointerdown', closeOnOutsideClick)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [onClose])

  const signOut = async () => {
    try {
      await logout()
      navigate('/login', { replace: true })
    } catch (error) {
      toast.error(error.message || 'Unable to sign out.')
    }
  }

  return (
    <div className="navbar-user-menu" ref={menuRef} role="menu" aria-label="User menu">
      <div className="navbar-user-summary">
        <span className="navbar-avatar">{user?.username?.charAt(0).toUpperCase() || 'U'}</span>
        <span><strong>{user?.username || 'Your account'}</strong><small>{user?.email || 'Personal workspace'}</small></span>
      </div>
      <NavLink onClick={onClose} role="menuitem" to="/profile">Profile</NavLink>
      <NavLink onClick={onClose} role="menuitem" to="/settings">Settings</NavLink>
      <NavLink onClick={onClose} role="menuitem" to="/settings/integrations">Integrations</NavLink>
      <button onClick={signOut} role="menuitem" type="button">Sign out</button>
    </div>
  )
}

export default function Navbar({ theme, onToggleTheme }) {
  const { user, authenticatedRequest } = useAuth()
  const hamburgerRef = useRef(null)
  const [dueCount, setDueCount] = useState(0)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)

  const refreshDueCount = useCallback(() => {
    authenticatedRequest('/api/revisions/due-today/')
      .then((revisions) => {
        if (!Array.isArray(revisions)) throw new Error('Unexpected response while loading due reviews.')
        setDueCount(revisions.length)
      })
      .catch((error) => {
        toast.error(error.message || 'Unable to load due reviews.')
      })
  }, [authenticatedRequest])

  useEffect(() => {
    refreshDueCount()
    window.addEventListener('recalldsa:revisions-updated', refreshDueCount)
    return () => {
      window.removeEventListener('recalldsa:revisions-updated', refreshDueCount)
    }
  }, [refreshDueCount])

  useEffect(() => {
    document.body.classList.toggle('drawer-open', drawerOpen)
    if (!drawerOpen) return
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') {
        setDrawerOpen(false)
        hamburgerRef.current?.focus()
      }
    }
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.body.classList.remove('drawer-open')
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [drawerOpen])

  const closeDrawer = () => setDrawerOpen(false)
  const closeUserMenu = () => setUserMenuOpen(false)
  const isDark = theme === 'dark'

  return (
    <header className="app-navbar">
      <NavLink aria-label="RecallDSA dashboard" className="navbar-brand" to="/dashboard">
        <Brand />
      </NavLink>

      <nav aria-label="Primary navigation" className="navbar-links">
        {navItems.map((item) => (
          <NavLink className={({ isActive }) => `navbar-link${isActive ? ' active' : ''}`} key={item.to} to={item.to}>
            <span aria-hidden="true">{item.icon}</span>{item.label}
          </NavLink>
        ))}
      </nav>

      <div className="navbar-actions">
        <NavLink aria-label={`${dueCount} reviews due`} className="notification-button tooltip-target" data-tooltip={`${dueCount} reviews due`} title={`${dueCount} reviews due`} to="/revisions">
          <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" /></svg>
          {dueCount > 0 && <span className="notification-count">{dueCount > 99 ? '99+' : dueCount}</span>}
        </NavLink>
        <button aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'} className="navbar-icon-button theme-button tooltip-target" data-tooltip={isDark ? 'Switch to light mode' : 'Switch to dark mode'} onClick={onToggleTheme} title={isDark ? 'Switch to light mode' : 'Switch to dark mode'} type="button">
          <span aria-hidden="true">{isDark ? '☀' : '☾'}</span>
        </button>
        <div className="navbar-user">
          <button aria-expanded={userMenuOpen} aria-haspopup="menu" className="navbar-user-trigger" onClick={() => setUserMenuOpen((open) => !open)} type="button">
            <span className="navbar-avatar">{user?.username?.charAt(0).toUpperCase() || 'U'}</span>
            <span className="navbar-user-name">{user?.username || 'Account'}</span>
            <span aria-hidden="true">⌄</span>
          </button>
          {userMenuOpen && <UserDropdown onClose={closeUserMenu} user={user} />}
        </div>
        <button aria-expanded={drawerOpen} aria-label={drawerOpen ? 'Close navigation menu' : 'Open navigation menu'} className={`navbar-icon-button hamburger-button${drawerOpen ? ' is-open' : ''}`} data-tooltip={drawerOpen ? 'Close menu' : 'Open menu'} onClick={() => setDrawerOpen((open) => !open)} ref={hamburgerRef} type="button">
          <span /><span /><span />
        </button>
      </div>

      {drawerOpen && (
        <>
          <button aria-label="Close navigation menu" className="drawer-backdrop" onClick={closeDrawer} type="button" />
          <nav aria-label="Mobile navigation" className="mobile-drawer">
            <div className="mobile-drawer-heading"><Brand /><button aria-label="Close menu" onClick={closeDrawer} type="button">×</button></div>
            {navItems.map((item) => (
              <NavLink className={({ isActive }) => `navbar-link${isActive ? ' active' : ''}`} key={item.to} onClick={closeDrawer} to={item.to}>
                <span aria-hidden="true">{item.icon}</span>{item.label}
                {item.to === '/revisions' && dueCount > 0 && <span className="drawer-count">{dueCount}</span>}
              </NavLink>
            ))}
            <div className="mobile-drawer-secondary">
              <NavLink onClick={closeDrawer} to="/import/leetcode">Import from LeetCode</NavLink>
              <NavLink onClick={closeDrawer} to="/profile">Profile</NavLink>
              <NavLink onClick={closeDrawer} to="/settings">Settings</NavLink>
              <NavLink onClick={closeDrawer} to="/settings/integrations">Integrations</NavLink>
            </div>
            <button className="mobile-theme-button" onClick={onToggleTheme} type="button">{isDark ? '☀ Switch to light mode' : '☾ Switch to dark mode'}</button>
          </nav>
        </>
      )}
    </header>
  )
}
