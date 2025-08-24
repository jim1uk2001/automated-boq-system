import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import axios from 'axios'
import toast from 'react-hot-toast'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface User {
  id: string
  email: string
  name: string
  role: 'client' | 'contractor'
  company?: string
}

interface AuthContextType {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<boolean>
  logout: () => void
  register: (userData: RegisterData) => Promise<boolean>
}

interface RegisterData {
  email: string
  password: string
  name: string
  role: 'client' | 'contractor'
  company?: string
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('token')
    const userData = localStorage.getItem('user')
    if (token && userData) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`
      try {
        setUser(JSON.parse(userData))
      } catch (error) {
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        delete axios.defaults.headers.common['Authorization']
      }
    }
    setLoading(false)
  }, [])

  const login = async (email: string, password: string): Promise<boolean> => {
    try {
      const formData = new FormData()
      formData.append('email', email)
      formData.append('password', password)
      
      const response = await axios.post(`${API_URL}/auth/login`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })
      
      const { access_token, user: userData } = response.data
      localStorage.setItem('token', access_token)
      localStorage.setItem('user', JSON.stringify(userData))
      axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`
      setUser(userData)
      toast.success('Login successful!')
      return true
    } catch (error: any) {
      let errorMessage = 'Login failed'
      if (error.response?.data?.detail) {
        if (typeof error.response.data.detail === 'string') {
          errorMessage = error.response.data.detail
        } else if (Array.isArray(error.response.data.detail)) {
          errorMessage = error.response.data.detail.map((err: any) => err.msg || err).join(', ')
        }
      }
      toast.error(errorMessage)
      return false
    }
  }

  const register = async (userData: RegisterData): Promise<boolean> => {
    try {
      await axios.post(`${API_URL}/auth/register`, userData)
      toast.success('Registration successful! Please login.')
      return true
    } catch (error: any) {
      let errorMessage = 'Registration failed'
      if (error.response?.data?.detail) {
        if (typeof error.response.data.detail === 'string') {
          errorMessage = error.response.data.detail
        } else if (Array.isArray(error.response.data.detail)) {
          errorMessage = error.response.data.detail.map((err: any) => err.msg || err).join(', ')
        }
      }
      toast.error(errorMessage)
      return false
    }
  }

  const logout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    delete axios.defaults.headers.common['Authorization']
    setUser(null)
    toast.success('Logged out successfully')
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, register }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
