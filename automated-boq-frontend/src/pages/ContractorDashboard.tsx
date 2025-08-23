import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import toast from 'react-hot-toast'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface Project {
  id: string
  name: string
  description: string
  status: string
  client_name: string
  client_company: string
  boq_items_count: number
}

interface Bid {
  id: string
  project_id: string
  project_name: string
  total_amount: number
  status: string
  submitted_at: string
}

export function ContractorDashboard() {
  const navigate = useNavigate()
  const [availableProjects, setAvailableProjects] = useState<Project[]>([])
  const [myBids, setMyBids] = useState<Bid[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'available' | 'mybids'>('available')

  useEffect(() => {
    fetchDashboardData()
  }, [])

  const fetchDashboardData = async () => {
    try {
      const [projectsRes, bidsRes] = await Promise.all([
        axios.get(`${API_URL}/projects/available-for-bidding`),
        axios.get(`${API_URL}/contractor/bids`)
      ])
      
      setAvailableProjects(projectsRes.data)
      setMyBids(bidsRes.data)
    } catch (error) {
      toast.error('Failed to fetch dashboard data')
    } finally {
      setLoading(false)
    }
  }

  const downloadBOQTemplate = async (projectId: string, projectName: string) => {
    try {
      const response = await axios.get(`${API_URL}/projects/${projectId}/boq/excel`, {
        responseType: 'blob'
      })
      
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `${projectName}_boq_template.xlsx`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      
      toast.success('BOQ template downloaded!')
    } catch (error) {
      toast.error('Failed to download BOQ template')
    }
  }

  const startBidding = (projectId: string) => {
    navigate(`/projects/${projectId}/bidding`)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Contractor Dashboard</h1>
        <p className="text-gray-600">Find projects to bid on and manage your submissions</p>
      </div>

      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {['available', 'mybids'].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab as any)}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                activeTab === tab
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {tab === 'available' ? 'Available Projects' : 'My Bids'}
            </button>
          ))}
        </nav>
      </div>

      {activeTab === 'available' && (
        <div className="space-y-6">
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {availableProjects.map((project) => (
              <div
                key={project.id}
                className="bg-white p-6 rounded-lg shadow-md border hover:shadow-lg transition-shadow"
              >
                <div className="flex justify-between items-start mb-3">
                  <h3 className="text-lg font-semibold text-gray-900">{project.name}</h3>
                  <span className={`px-2 py-1 text-xs rounded-full ${
                    project.status === 'open_for_bidding' ? 'bg-green-100 text-green-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    Open for Bidding
                  </span>
                </div>
                
                <p className="text-gray-600 text-sm mb-4 line-clamp-2">{project.description}</p>
                
                <div className="space-y-2 text-sm text-gray-500 mb-4">
                  <div>Client: {project.client_name}</div>
                  <div>Company: {project.client_company}</div>
                  <div>BOQ Items: {project.boq_items_count}</div>
                </div>
                
                <div className="flex space-x-2">
                  <button
                    onClick={() => downloadBOQTemplate(project.id, project.name)}
                    className="flex-1 bg-blue-600 hover:bg-blue-700 text-white px-3 py-2 rounded-md text-sm font-medium"
                  >
                    Download BOQ
                  </button>
                  <button
                    onClick={() => startBidding(project.id)}
                    className="flex-1 bg-green-600 hover:bg-green-700 text-white px-3 py-2 rounded-md text-sm font-medium"
                  >
                    Submit Bid
                  </button>
                </div>
              </div>
            ))}
          </div>

          {availableProjects.length === 0 && (
            <div className="text-center py-12">
              <div className="text-gray-400 text-lg mb-2">No projects available for bidding</div>
              <p className="text-gray-500">Check back later for new bidding opportunities</p>
            </div>
          )}
        </div>
      )}

      {activeTab === 'mybids' && (
        <div className="space-y-6">
          <div className="bg-white rounded-lg shadow-md overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-medium">My Bid Submissions ({myBids.length})</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Project
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Bid Amount
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Submitted
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {myBids.map((bid) => (
                    <tr key={bid.id}>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {bid.project_name}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-semibold">
                        ${bid.total_amount.toLocaleString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                          bid.status === 'submitted' ? 'bg-green-100 text-green-800' :
                          bid.status === 'draft' ? 'bg-yellow-100 text-yellow-800' :
                          bid.status === 'won' ? 'bg-blue-100 text-blue-800' :
                          bid.status === 'lost' ? 'bg-red-100 text-red-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {bid.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {new Date(bid.submitted_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        <button
                          onClick={() => navigate(`/projects/${bid.project_id}/bidding`)}
                          className="text-blue-600 hover:text-blue-900"
                        >
                          View Details
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {myBids.length === 0 && (
            <div className="text-center py-12">
              <div className="text-gray-400 text-lg mb-2">No bids submitted yet</div>
              <p className="text-gray-500">Start bidding on available projects to see your submissions here</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
