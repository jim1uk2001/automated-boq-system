import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import axios from 'axios'
import toast from 'react-hot-toast'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface Project {
  id: string
  name: string
  description: string
}

interface Bid {
  id: string
  contractor_id: string
  contractor_name: string
  contractor_company: string
  total_amount: number
  status: string
  submitted_at: string
}

interface BidEvaluation {
  project_id: string
  winning_bid_id: string
  ranked_bids: Array<{
    bid_id: string
    contractor_name: string
    contractor_company: string
    total_amount: number
    rank: number
  }>
  evaluation_date: string
}

export function BiddingPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const [project, setProject] = useState<Project | null>(null)
  const [bids, setBids] = useState<Bid[]>([])
  const [evaluation, setEvaluation] = useState<BidEvaluation | null>(null)
  const [loading, setLoading] = useState(true)
  const [evaluating, setEvaluating] = useState(false)

  useEffect(() => {
    if (projectId) {
      fetchBiddingData()
    }
  }, [projectId])

  const fetchBiddingData = async () => {
    try {
      const [projectRes, bidsRes] = await Promise.all([
        axios.get(`${API_URL}/projects/${projectId}`),
        axios.get(`${API_URL}/projects/${projectId}/bids`)
      ])
      
      setProject(projectRes.data)
      setBids(bidsRes.data)

      try {
        const evaluationRes = await axios.get(`${API_URL}/projects/${projectId}/evaluation`)
        setEvaluation(evaluationRes.data)
      } catch (error) {
      }
    } catch (error) {
      toast.error('Failed to fetch bidding data')
      navigate('/')
    } finally {
      setLoading(false)
    }
  }

  const evaluateBids = async () => {
    setEvaluating(true)
    try {
      const response = await axios.post(`${API_URL}/projects/${projectId}/evaluate-bids`)
      setEvaluation(response.data)
      toast.success('Bids evaluated successfully!')
    } catch (error) {
      toast.error('Failed to evaluate bids')
    } finally {
      setEvaluating(false)
    }
  }

  const downloadBidComparison = async () => {
    try {
      const response = await axios.get(`${API_URL}/projects/${projectId}/bid-comparison/excel`, {
        responseType: 'blob'
      })
      
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `${project?.name || 'project'}_bid_comparison.xlsx`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      
      toast.success('Bid comparison downloaded!')
    } catch (error) {
      toast.error('Failed to download bid comparison')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  if (!project) {
    return <div>Project not found</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <button
            onClick={() => navigate(`/projects/${projectId}`)}
            className="text-blue-600 hover:text-blue-800 mb-2"
          >
            ← Back to Project
          </button>
          <h1 className="text-3xl font-bold text-gray-900">Bidding Management</h1>
          <p className="text-gray-600">{project.name}</p>
        </div>
        <div className="flex space-x-3">
          {bids.length > 0 && !evaluation && (
            <button
              onClick={evaluateBids}
              disabled={evaluating}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white px-4 py-2 rounded-md font-medium"
            >
              {evaluating ? 'Evaluating...' : 'Evaluate Bids'}
            </button>
          )}
          {evaluation && (
            <button
              onClick={downloadBidComparison}
              className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-md font-medium"
            >
              Download Comparison
            </button>
          )}
        </div>
      </div>

      {/* Bid Evaluation Results */}
      {evaluation && (
        <div className="bg-white p-6 rounded-lg shadow-md border-l-4 border-green-500">
          <h2 className="text-xl font-semibold mb-4 text-green-800">Bid Evaluation Results</h2>
          <div className="space-y-4">
            <div className="bg-green-50 p-4 rounded-md">
              <h3 className="font-medium text-green-800 mb-2">🏆 Winning Bid</h3>
              {evaluation.ranked_bids.length > 0 && (
                <div className="text-green-700">
                  <div className="font-semibold">{evaluation.ranked_bids[0].contractor_name}</div>
                  <div className="text-sm">{evaluation.ranked_bids[0].contractor_company}</div>
                  <div className="text-lg font-bold">${evaluation.ranked_bids[0].total_amount.toLocaleString()}</div>
                </div>
              )}
            </div>
            
            <div>
              <h3 className="font-medium text-gray-800 mb-3">Complete Rankings</h3>
              <div className="space-y-2">
                {evaluation.ranked_bids.map((bid, index) => (
                  <div
                    key={bid.bid_id}
                    className={`flex justify-between items-center p-3 rounded-md ${
                      index === 0 ? 'bg-green-100 border border-green-300' :
                      index === 1 ? 'bg-yellow-50 border border-yellow-300' :
                      index === 2 ? 'bg-orange-50 border border-orange-300' :
                      'bg-gray-50 border border-gray-200'
                    }`}
                  >
                    <div className="flex items-center space-x-3">
                      <span className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                        index === 0 ? 'bg-green-500 text-white' :
                        index === 1 ? 'bg-yellow-500 text-white' :
                        index === 2 ? 'bg-orange-500 text-white' :
                        'bg-gray-400 text-white'
                      }`}>
                        {bid.rank}
                      </span>
                      <div>
                        <div className="font-medium">{bid.contractor_name}</div>
                        <div className="text-sm text-gray-600">{bid.contractor_company}</div>
                      </div>
                    </div>
                    <div className="text-lg font-semibold">
                      ${bid.total_amount.toLocaleString()}
                    </div>
                  </div>
                ))}
              </div>
            </div>
            
            <div className="text-sm text-gray-500">
              Evaluated on {new Date(evaluation.evaluation_date).toLocaleDateString()}
            </div>
          </div>
        </div>
      )}

      {/* Submitted Bids */}
      <div className="bg-white rounded-lg shadow-md overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-medium">Submitted Bids ({bids.length})</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Contractor
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Company
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Total Amount
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Submitted
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {bids.map((bid) => (
                <tr key={bid.id}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {bid.contractor_name}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {bid.contractor_company}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-semibold">
                    ${bid.total_amount.toLocaleString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                      bid.status === 'submitted' ? 'bg-green-100 text-green-800' :
                      bid.status === 'draft' ? 'bg-yellow-100 text-yellow-800' :
                      'bg-gray-100 text-gray-800'
                    }`}>
                      {bid.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(bid.submitted_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {bids.length === 0 && (
        <div className="text-center py-12">
          <div className="text-gray-400 text-lg mb-2">No bids submitted yet</div>
          <p className="text-gray-500">Contractors will submit their bids through the bidding portal</p>
        </div>
      )}
    </div>
  )
}
