import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { useForm, useWatch } from 'react-hook-form'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from './context/useAuth.js'

const settingsTabs = [
  { id: 'preferences', label: 'Preferences' },
  { id: 'notifications', label: 'Notifications' },
  { id: 'appearance', label: 'Appearance' },
  { id: 'integrations', label: 'Integrations' },
  { id: 'account', label: 'Account' },
]

const defaultSettings = {
  daily_problem_goal: 3,
  assessment_day: 'sunday',
  assessment_time_limit: 20,
  email_reminders: true,
  reminder_time: '09:00',
  theme: 'light',
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
  leetcode_username: '',
}

function PageLoadingSkeleton({ label }) {
  return (
    <main className="route-page">
      <div aria-busy="true" aria-label={label} className="page-loading-skeleton" role="status">
        <i className="skeleton page-skeleton-heading" />
        <i className="skeleton page-skeleton-line" />
        <i className="skeleton page-skeleton-card" />
      </div>
    </main>
  )
}

export function ProfilePage() {
  const { authenticatedRequest, updateUser } = useAuth()
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const { register, handleSubmit, reset, formState: { errors } } = useForm()

  useEffect(() => {
    let active = true
    authenticatedRequest('/api/users/profile/')
      .then((data) => {
        if (!active) return
        setProfile(data)
        reset({ username: data.username, email: data.email })
      })
      .catch((requestError) => {
        if (active) setError(requestError.message)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [authenticatedRequest, reset])

  const saveProfile = async (values) => {
    setSaving(true)
    setError('')
    try {
      const updated = await authenticatedRequest('/api/users/profile/', {
        method: 'PUT',
        body: JSON.stringify(values),
      })
      setProfile((current) => ({ ...current, ...updated }))
      updateUser(updated)
      setEditing(false)
    } catch (saveError) {
      setError(saveError.message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <PageLoadingSkeleton label="Loading your profile" />
  if (!profile) return <main className="route-page"><div className="empty-state error-state" role="alert">{error || 'Unable to load your profile.'}</div></main>

  const initials = profile.username.split(/[._\s-]/).filter(Boolean).slice(0, 2).map((part) => part[0].toUpperCase()).join('')
  const joinedDate = new Date(profile.date_joined).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })

  return (
    <main className="route-page user-page">
      <section className="route-page-heading">
        <p className="eyebrow">YOUR ACCOUNT</p>
        <h1>Your profile</h1>
        <p>A quick look at your account and the progress you’ve made.</p>
      </section>

      <section className="profile-card">
        <div aria-hidden="true" className="profile-avatar">{initials || 'U'}</div>
        <div className="profile-identity">
          {editing ? (
            <form className="user-edit-form" onSubmit={handleSubmit(saveProfile)}>
              <label>Username
                <input {...register('username', { required: 'Username is required.', minLength: { value: 2, message: 'Use at least 2 characters.' } })} />
                {errors.username && <span className="field-error">{errors.username.message}</span>}
              </label>
              <label>Email
                <input autoComplete="email" type="email" {...register('email', { validate: (value) => !value || /^\S+@\S+\.\S+$/.test(value) || 'Enter a valid email address.' })} />
                {errors.email && <span className="field-error">{errors.email.message}</span>}
              </label>
              {error && <p className="form-error" role="alert">{error}</p>}
              <div className="user-form-actions">
                <button className="primary-button user-action-button" disabled={saving} type="submit">{saving ? 'Saving...' : 'Save profile'}</button>
                <button className="secondary-button" onClick={() => { reset({ username: profile.username, email: profile.email }); setEditing(false); setError('') }} type="button">Cancel</button>
              </div>
            </form>
          ) : (
            <>
              <h2>{profile.username}</h2>
              <p>{profile.email || 'No email address added'}</p>
              <span>Member since {joinedDate}</span>
            </>
          )}
        </div>
        {!editing && <button className="secondary-button profile-edit-button" onClick={() => setEditing(true)} type="button">Edit profile</button>}
      </section>

      <section aria-label="Learning statistics" className="profile-stats">
        <article><span>Problems solved</span><strong>{profile.stats.problems_solved}</strong><small>In your recall history</small></article>
        <article><span>Problems tracked</span><strong>{profile.stats.problems_tracked}</strong><small>In your review queue</small></article>
        <article><span>Assessments</span><strong>{profile.stats.assessments_completed}</strong><small>Completed assessments</small></article>
      </section>

      <div className="profile-footer"><span>Keep your account details up to date.</span><Link to="/settings">Manage settings <span aria-hidden="true">↗</span></Link></div>
    </main>
  )
}

export function SettingsPage({ onThemeChange }) {
  const { authenticatedRequest, clearAuth } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const initialTab = location.pathname.endsWith('/integrations') ? 'integrations' : 'preferences'
  const [selectedTab, setSelectedTab] = useState(initialTab)
  const activeTab = location.pathname.endsWith('/integrations') ? 'integrations' : selectedTab
  const [loading, setLoading] = useState(true)
  const [settingsError, setSettingsError] = useState('')
  const [settingsMessage, setSettingsMessage] = useState('')
  const [passwordMessage, setPasswordMessage] = useState('')
  const [accountError, setAccountError] = useState('')
  const [working, setWorking] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [connected, setConnected] = useState(false)
  const [pendingDeletePassword, setPendingDeletePassword] = useState(null)
  const { register, handleSubmit, reset, control, formState: { errors } } = useForm({ defaultValues: defaultSettings })
  const passwordForm = useForm()
  const deleteForm = useForm()
  const theme = useWatch({ control, name: 'theme' })
  const leetcodeUsername = useWatch({ control, name: 'leetcode_username' })
  const lastSyncedAt = useWatch({ control, name: 'leetcode_last_synced_at' })

  useEffect(() => {
    let active = true
    authenticatedRequest('/api/users/settings/')
      .then((data) => {
        if (!active) return
        reset({
          ...defaultSettings,
          ...data,
          reminder_time: data.reminder_time?.slice(0, 5) || '09:00',
        })
        setConnected(Boolean(data.leetcode_username))
        onThemeChange(data.theme)
      })
      .catch((requestError) => {
        if (active) setSettingsError(requestError.message)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [authenticatedRequest, onThemeChange, reset])

  const saveSettings = async (values) => {
    setWorking(true)
    setSettingsError('')
    setSettingsMessage('')
    try {
      const saved = await authenticatedRequest('/api/users/settings/', {
        method: 'PUT',
        body: JSON.stringify({ ...values, assessment_time_limit: Number(values.assessment_time_limit), daily_problem_goal: Number(values.daily_problem_goal) }),
      })
      reset({ ...saved, reminder_time: saved.reminder_time?.slice(0, 5) || '09:00' })
      setConnected(Boolean(saved.leetcode_username))
      onThemeChange(saved.theme)
      setSettingsMessage('Settings saved.')
    } catch (saveError) {
      setSettingsError(saveError.message)
    } finally {
      setWorking(false)
    }
  }

  const changeTab = (tab) => {
    setSelectedTab(tab)
    navigate(tab === 'integrations' ? '/settings/integrations' : '/settings', { replace: true })
  }

  const syncLeetCode = async () => {
    setSyncing(true)
    setSettingsError('')
    setSettingsMessage('')
    try {
      const result = await authenticatedRequest('/api/users/sync-leetcode/', { method: 'POST' })
      setSettingsMessage(`Sync complete. ${result.imported_count} new problem${result.imported_count === 1 ? '' : 's'} added.`)
      const updated = await authenticatedRequest('/api/users/settings/')
      reset({ ...updated, reminder_time: updated.reminder_time?.slice(0, 5) || '09:00' })
    } catch (syncError) {
      setSettingsError(syncError.message)
    } finally {
      setSyncing(false)
    }
  }

  const disconnectLeetCode = async () => {
    setWorking(true)
    setSettingsError('')
    setSettingsMessage('')
    try {
      const updated = await authenticatedRequest('/api/users/disconnect-leetcode/', { method: 'POST' })
      reset({ ...updated, reminder_time: updated.reminder_time?.slice(0, 5) || '09:00' })
      setConnected(false)
      setSettingsMessage('LeetCode disconnected.')
    } catch (disconnectError) {
      setSettingsError(disconnectError.message)
    } finally {
      setWorking(false)
    }
  }

  const changePassword = async ({ current_password: currentPassword, new_password: newPassword }) => {
    setWorking(true)
    setAccountError('')
    setPasswordMessage('')
    try {
      const result = await authenticatedRequest('/api/users/change-password/', {
        method: 'POST',
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      })
      passwordForm.reset()
      setPasswordMessage(result.detail)
    } catch (requestError) {
      setAccountError(requestError.message)
    } finally {
      setWorking(false)
    }
  }

  const deleteAccount = async () => {
    if (!pendingDeletePassword) return
    setWorking(true)
    setAccountError('')
    try {
      await authenticatedRequest('/api/users/delete-account/', {
        method: 'DELETE',
        body: JSON.stringify({ password: pendingDeletePassword }),
      })
      clearAuth()
      navigate('/login', { replace: true })
    } catch (requestError) {
      setAccountError(requestError.message)
      setPendingDeletePassword(null)
      deleteForm.reset()
    } finally {
      setWorking(false)
    }
  }

  if (loading) return <PageLoadingSkeleton label="Loading your settings" />

  return (
    <main className="route-page user-page settings-page">
      <section className="route-page-heading">
        <p className="eyebrow">MAKE IT YOURS</p>
        <h1>Settings</h1>
        <p>Shape your practice routine, reminders, and connected services.</p>
      </section>

      <div className="settings-layout">
        <nav aria-label="Settings sections" className="settings-tabs">
          {settingsTabs.map((tab) => <button aria-current={activeTab === tab.id ? 'page' : undefined} className={activeTab === tab.id ? 'active' : ''} key={tab.id} onClick={() => changeTab(tab.id)} type="button">{tab.label}</button>)}
        </nav>

        <div className="settings-panel">
          {activeTab !== 'account' && (
            <form className="settings-form" onSubmit={handleSubmit(saveSettings)}>
              {activeTab === 'preferences' && <>
                <div className="settings-section-heading"><h2>Practice preferences</h2><p>Set a steady target and schedule for your weekly recall check.</p></div>
                <label className="settings-field">Daily problem goal
                  <span className="field-help">How many problems would you like to practice each day?</span>
                  <input type="number" {...register('daily_problem_goal', { required: 'Choose a daily goal.', valueAsNumber: true, min: { value: 1, message: 'The goal must be at least 1.' }, max: { value: 50, message: 'The goal cannot exceed 50.' } })} />
                  {errors.daily_problem_goal && <span className="field-error">{errors.daily_problem_goal.message}</span>}
                </label>
                <label className="settings-field">Assessment day
                  <span className="field-help">Choose the day for your weekly assessment.</span>
                  <select {...register('assessment_day', { required: 'Choose an assessment day.' })}>
                    {['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'].map((day) => <option key={day} value={day}>{day[0].toUpperCase() + day.slice(1)}</option>)}
                  </select>
                </label>
                <label className="settings-field">Assessment duration
                  <span className="field-help">Time allowed for each assessment, in minutes.</span>
                  <input type="number" {...register('assessment_time_limit', { required: 'Choose a duration.', valueAsNumber: true, min: { value: 5, message: 'Use at least 5 minutes.' }, max: { value: 180, message: 'The duration cannot exceed 180 minutes.' } })} />
                  {errors.assessment_time_limit && <span className="field-error">{errors.assessment_time_limit.message}</span>}
                </label>
              </>}

              {activeTab === 'notifications' && <>
                <div className="settings-section-heading"><h2>Notifications</h2><p>Choose when RecallDSA should remind you to practice.</p></div>
                <label className="settings-switch"><span><strong>Email reminders</strong><small>Receive email reminders for due reviews.</small></span><input type="checkbox" {...register('email_reminders')} /><span aria-hidden="true" className="switch-track" /></label>
                <label className="settings-field">Reminder time
                  <span className="field-help">Reminder time in your selected timezone.</span>
                  <input type="time" {...register('reminder_time', { required: 'Choose a reminder time.' })} />
                  {errors.reminder_time && <span className="field-error">{errors.reminder_time.message}</span>}
                </label>
                <label className="settings-field">Timezone
                  <span className="field-help">Use an IANA timezone such as America/New_York.</span>
                  <input placeholder="UTC" {...register('timezone', { required: 'Timezone is required.' })} />
                  {errors.timezone && <span className="field-error">{errors.timezone.message}</span>}
                </label>
              </>}

              {activeTab === 'appearance' && <>
                <div className="settings-section-heading"><h2>Appearance</h2><p>Choose the look that feels right for your workspace.</p></div>
                <div className="theme-options">
                  {['light', 'dark'].map((option) => <label className={`theme-choice${theme === option ? ' selected' : ''}`} key={option}><input type="radio" value={option} {...register('theme')} /><span aria-hidden="true">{option === 'light' ? '☀' : '☾'}</span><strong>{option[0].toUpperCase() + option.slice(1)}</strong><small>{option === 'light' ? 'Bright and clear' : 'Easy on the eyes'}</small></label>)}
                </div>
              </>}

              {activeTab === 'integrations' && <>
                <div className="settings-section-heading"><h2>Integrations</h2><p>Bring your recently accepted LeetCode problems into your RecallDSA history.</p></div>
                <section className="integration-card">
                  <div className="integration-brand"><span aria-hidden="true">LC</span><div><h3>LeetCode</h3><p>Connect your public LeetCode profile by username.</p></div></div>
                  <label className="settings-field">LeetCode username
                    <input autoComplete="off" placeholder="your-leetcode-username" {...register('leetcode_username', { validate: (value) => activeTab !== 'integrations' || Boolean(value?.trim()) || 'Enter your LeetCode username.', maxLength: { value: 100, message: 'Username must be 100 characters or fewer.' }, pattern: { value: /^[A-Za-z0-9_-]*$/, message: 'Use letters, numbers, underscores, or hyphens.' } })} />
                    {errors.leetcode_username && <span className="field-error">{errors.leetcode_username.message}</span>}
                  </label>
                  <p className="integration-status"><span className={connected ? 'status-dot connected' : 'status-dot'} />{connected ? `Connected as ${leetcodeUsername}` : 'Not connected'}</p>
                  <p className="field-help">Sync imports up to 20 recent accepted submissions that match problems in RecallDSA.</p>
                  <div className="user-form-actions">
                    <button className="primary-button user-action-button" disabled={working || syncing} type="submit">{working ? 'Connecting...' : connected ? 'Update connection' : 'Connect LeetCode'}</button>
                    {connected && <button className="secondary-button" disabled={working || syncing} onClick={syncLeetCode} type="button">{syncing ? 'Syncing...' : 'Sync now'}</button>}
                    {connected && <button className="danger-button" disabled={working || syncing} onClick={disconnectLeetCode} type="button">Disconnect</button>}
                  </div>
                  {lastSyncedAt && <p className="field-help">Last synced {new Date(lastSyncedAt).toLocaleString()}</p>}
                </section>
              </>}

              {settingsError && activeTab !== 'integrations' && <p className="form-error" role="alert">{settingsError}</p>}
              {settingsMessage && activeTab !== 'integrations' && <p className="form-success" role="status">{settingsMessage}</p>}
              {activeTab !== 'integrations' && <div className="settings-actions"><button className="primary-button user-action-button" disabled={working} type="submit">{working ? 'Saving...' : 'Save changes'}</button></div>}
              {activeTab === 'integrations' && settingsError && <p className="form-error" role="alert">{settingsError}</p>}
              {activeTab === 'integrations' && settingsMessage && <p className="form-success" role="status">{settingsMessage}</p>}
            </form>
          )}

          {activeTab === 'account' && <div className="account-settings">
            <section className="account-section">
              <div className="settings-section-heading"><h2>Change password</h2><p>Choose a strong password you don’t use elsewhere.</p></div>
              <form className="settings-form" onSubmit={passwordForm.handleSubmit(changePassword)}>
                <label className="settings-field">Current password<input autoComplete="current-password" type="password" {...passwordForm.register('current_password', { required: 'Enter your current password.' })} />{passwordForm.formState.errors.current_password && <span className="field-error">{passwordForm.formState.errors.current_password.message}</span>}</label>
                <label className="settings-field">New password<input autoComplete="new-password" type="password" {...passwordForm.register('new_password', { required: 'Enter a new password.', minLength: { value: 8, message: 'Use at least 8 characters.' } })} />{passwordForm.formState.errors.new_password && <span className="field-error">{passwordForm.formState.errors.new_password.message}</span>}</label>
                <label className="settings-field">Confirm new password<input autoComplete="new-password" type="password" {...passwordForm.register('confirm_password', { required: 'Confirm your new password.', validate: (value) => value === passwordForm.getValues('new_password') || 'Passwords do not match.' })} />{passwordForm.formState.errors.confirm_password && <span className="field-error">{passwordForm.formState.errors.confirm_password.message}</span>}</label>
                {accountError && <p className="form-error" role="alert">{accountError}</p>}
                {passwordMessage && <p className="form-success" role="status">{passwordMessage}</p>}
                <button className="primary-button user-action-button" disabled={working} type="submit">{working ? 'Updating...' : 'Update password'}</button>
              </form>
            </section>
            <section className="account-section danger-zone">
              <div className="settings-section-heading"><h2>Delete account</h2><p>This permanently deletes your account, settings, and learning history.</p></div>
              <form className="settings-form" onSubmit={deleteForm.handleSubmit(({ password }) => setPendingDeletePassword(password))}>
                <label className="settings-field">Confirm with your password<input autoComplete="current-password" type="password" {...deleteForm.register('password', { required: 'Enter your password to delete your account.' })} />{deleteForm.formState.errors.password && <span className="field-error">{deleteForm.formState.errors.password.message}</span>}</label>
                {accountError && <p className="form-error" role="alert">{accountError}</p>}
                <button className="danger-button" disabled={working} type="submit">Continue to delete account</button>
              </form>
            </section>
          </div>}
        </div>
      </div>
      <AnimatePresence>
        {pendingDeletePassword && (
          <DeleteAccountConfirmation
            key="delete-account-confirmation"
            onCancel={() => {
              setPendingDeletePassword(null)
              deleteForm.reset()
            }}
            onConfirm={deleteAccount}
            working={working}
          />
        )}
      </AnimatePresence>
    </main>
  )
}

function DeleteAccountConfirmation({ onCancel, onConfirm, working }) {
  const cancelButtonRef = useRef(null)
  const reduceMotion = useReducedMotion()

  useEffect(() => {
    document.body.classList.add('modal-open')
    cancelButtonRef.current?.focus()
    const closeOnEscape = (event) => {
      if (event.key === 'Escape' && !working) onCancel()
    }
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.body.classList.remove('modal-open')
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [onCancel, working])

  return (
    <motion.div
      animate={{ opacity: 1 }}
      className="confirm-modal-backdrop"
      exit={{ opacity: 0 }}
      initial={reduceMotion ? false : { opacity: 0 }}
      onClick={(event) => {
        if (event.target === event.currentTarget && !working) onCancel()
      }}
      role="presentation"
      transition={{ duration: reduceMotion ? 0 : 0.18 }}
    >
      <motion.section
        animate={{ opacity: 1, y: 0 }}
        aria-describedby="delete-account-description"
        aria-labelledby="delete-account-title"
        aria-modal="true"
        className="confirm-modal"
        exit={{ opacity: 0, y: 12 }}
        initial={reduceMotion ? false : { opacity: 0, y: 12 }}
        role="dialog"
        transition={{ duration: reduceMotion ? 0 : 0.2 }}
      >
        <p className="eyebrow">ACCOUNT DELETION</p>
        <h2 id="delete-account-title">Delete your account?</h2>
        <p id="delete-account-description">This permanently removes your account and learning history. This action cannot be undone.</p>
        <div className="confirm-modal-actions flex-col-reverse sm:flex-row">
          <button className="secondary-button w-full sm:w-auto" disabled={working} onClick={onCancel} ref={cancelButtonRef} type="button">Keep my account</button>
          <button className="danger-button w-full sm:w-auto" disabled={working} onClick={onConfirm} type="button">{working ? 'Deleting...' : 'Delete permanently'}</button>
        </div>
      </motion.section>
    </motion.div>
  )
}
