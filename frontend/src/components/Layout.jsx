import { Outlet } from 'react-router-dom'
import Navbar from './Navbar.jsx'

export default function Layout({ theme, onToggleTheme }) {
  return (
    <div className="app-layout">
      <Navbar onToggleTheme={onToggleTheme} theme={theme} />
      <div className="app-layout-main"><Outlet /></div>
    </div>
  )
}
