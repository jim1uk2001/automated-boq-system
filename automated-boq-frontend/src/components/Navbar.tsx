import { useAuth } from '../contexts/AuthContext'
import { useNavigate } from 'react-router-dom'

export function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  if (!user) return null

  return (
    <nav className="bg-blue-600 text-white shadow-lg">
      <div className="container mx-auto px-4">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center space-x-4">
            <h1 className="text-xl font-bold">Bojim BOQ Production Software</h1>
            <span className="text-blue-200">|</span>
            <span className="text-blue-200 capitalize">{user.role} Portal</span>
          </div>
          
          <div className="flex items-center space-x-4">
            <div className="text-right">
              <div className="font-medium">{user.name}</div>
              <div className="text-sm text-blue-200">{user.company}</div>
            </div>
            <button
              onClick={handleLogout}
              className="bg-blue-700 hover:bg-blue-800 px-4 py-2 rounded-md text-sm font-medium transition-colors"
            >
              Logout
            </button>
          </div>
        </div>
      </div>
    </nav>
  )
}
