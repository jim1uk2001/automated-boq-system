import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import axios from 'axios'
import toast from 'react-hot-toast'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface Project {
  id: string
  name: string
  description: string
  status: string
  measurement_standard?: string
}

interface Drawing {
  id: string
  filename: string
  file_type: string
  drawing_type: string
  status: string
  uploaded_at: string
  drawing_number?: string
  drawing_title?: string
  revision_number?: string
}

interface BOQItem {
  id: string
  item_code: string
  description: string
  unit: string
  quantity: number
  trade: string
}

interface CostEstimate {
  total_hours: number
  total_cost: number
  hourly_rate: number
  currency: string
  cost_breakdown: {
    drawing_processing_hours: number
    boq_generation_hours: number
    project_setup_hours: number
    drawing_processing_cost: number
    boq_generation_cost: number
    project_setup_cost: number
  }
}

export function ProjectPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const [project, setProject] = useState<Project | null>(null)
  const [drawings, setDrawings] = useState<Drawing[]>([])
  const [boqItems, setBOQItems] = useState<BOQItem[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'drawings' | 'boq' | 'bidding'>('drawings')
  const [uploading, setUploading] = useState(false)
  const [costEstimate, setCostEstimate] = useState<CostEstimate | null>(null)
  const [hourlyRate, setHourlyRate] = useState(45)
  const [currency, setCurrency] = useState('GBP')
  const [loadingEstimate, setLoadingEstimate] = useState(false)
  const [showPrintPreview, setShowPrintPreview] = useState(false)
  const [estimateApproved, setEstimateApproved] = useState(false)
  const [showApprovalModal, setShowApprovalModal] = useState(false)

  useEffect(() => {
    if (projectId) {
      fetchProjectData()
    }
  }, [projectId])

  useEffect(() => {
    if (costEstimate && drawings.length > 0) {
      const timeoutId = setTimeout(() => {
        getCostEstimate()
      }, 500) // Debounce updates
      return () => clearTimeout(timeoutId)
    }
  }, [hourlyRate, currency])

  const fetchProjectData = async () => {
    try {
      const [projectRes, drawingsRes, boqRes] = await Promise.all([
        axios.get(`${API_URL}/projects/${projectId}`),
        axios.get(`${API_URL}/projects/${projectId}/drawings`),
        axios.get(`${API_URL}/projects/${projectId}/boq`)
      ])
      
      setProject(projectRes.data)
      setDrawings(drawingsRes.data)
      setBOQItems(boqRes.data)
    } catch (error) {
      toast.error('Failed to fetch project data')
      navigate('/')
    } finally {
      setLoading(false)
    }
  }


  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files
    if (!files || files.length === 0) return

    const validTypes = ['.pdf', '.dwg', '.dxf']
    const invalidFiles = Array.from(files).filter(file => 
      !validTypes.some(type => file.name.toLowerCase().endsWith(type))
    )
    
    if (invalidFiles.length > 0) {
      toast.error(`❌ Invalid file types detected. Please upload only PDF, DWG, or DXF files.`)
      return
    }

    const oversizedFiles = Array.from(files).filter(file => file.size > 50 * 1024 * 1024)
    if (oversizedFiles.length > 0) {
      toast.error(`❌ Some files are too large. Maximum file size is 50MB per file.`)
      return
    }

    setUploading(true)
    toast(`📤 Uploading ${files.length} drawing file(s)...`)

    const uploadPromises = Array.from(files).map(async (file) => {
      const formData = new FormData()
      formData.append('file', file)
      
      try {
        const response = await axios.post(
          `${API_URL}/projects/${projectId}/drawings/upload`,
          formData,
          {
            headers: { 'Content-Type': 'multipart/form-data' }
          }
        )
        return response.data
      } catch (error) {
        toast.error(`❌ Failed to upload ${file.name}. Please check the file and try again.`)
        return null
      }
    })

    const results = await Promise.all(uploadPromises)
    const successfulUploads = results.filter(result => result !== null)
    
    if (successfulUploads.length > 0) {
      setDrawings([...drawings, ...successfulUploads])
      toast.success(`✅ Successfully uploaded ${successfulUploads.length} drawing file(s)! Processing will begin automatically.`)
      setTimeout(fetchProjectData, 2000)
    }
    
    setUploading(false)
    event.target.value = ''
  }

  const processDrawings = async () => {
    try {
      await axios.post(`${API_URL}/projects/${projectId}/process`)
      toast.success('Processing started! This may take a few minutes.')
      setTimeout(fetchProjectData, 2000) // Refresh data after 2 seconds
    } catch (error) {
      toast.error('Failed to start processing')
    }
  }

  const generateBOQ = async () => {
    try {
      await axios.post(`${API_URL}/projects/${projectId}/generate-boq`)
      toast.success('BOQ generation started!')
      setTimeout(fetchProjectData, 2000)
    } catch (error) {
      toast.error('Failed to generate BOQ')
    }
  }

  const downloadBOQExcel = async () => {
    try {
      const response = await axios.get(`${API_URL}/projects/${projectId}/boq/excel`, {
        responseType: 'blob'
      })
      
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `${project?.name || 'project'}_boq.xlsx`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      
      toast.success('BOQ Excel downloaded!')
    } catch (error) {
      toast.error('Failed to download BOQ Excel')
    }
  }

  const getCostEstimate = async () => {
    if (!projectId || drawings.length === 0) return
    
    setLoadingEstimate(true)
    try {
      const response = await axios.get(`${API_URL}/projects/${projectId}/quick-estimate`, {
        params: {
          hourly_rate: hourlyRate,
          currency: currency
        },
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      })
      setCostEstimate(response.data)
    } catch (error) {
      toast.error('Failed to get cost estimate')
      console.error('Cost estimate error:', error)
    } finally {
      setLoadingEstimate(false)
    }
  }

  const updateHourlyRate = (newRate: number) => {
    if (newRate >= 1 && newRate <= 500) {
      setHourlyRate(newRate)
    }
  }

  const formatCurrency = (amount: number, curr: string) => {
    const symbols = { GBP: '£', USD: '$', EUR: '€', AED: 'AED ' }
    const symbol = symbols[curr as keyof typeof symbols] || curr + ' '
    return `${symbol}${amount.toFixed(2)}`
  }

  const handlePrintPreview = () => {
    setShowPrintPreview(true)
  }

  const handlePrint = () => {
    window.print()
  }

  const closePrintPreview = () => {
    setShowPrintPreview(false)
  }

  const handleApproveEstimate = () => {
    setEstimateApproved(true)
    setShowApprovalModal(false)
    toast.success('Cost estimate approved! You can now generate the BOQ.')
  }

  const handleRejectEstimate = () => {
    setShowApprovalModal(false)
    toast.error('Cost estimate rejected. Please adjust rates and get a new estimate.')
  }

  const requestApproval = () => {
    if (!costEstimate) {
      toast.error('Please get a cost estimate first')
      return
    }
    setShowApprovalModal(true)
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
    <div>
      <style>{`
        @media print {
          body * {
            visibility: hidden;
          }
          .print-content, .print-content * {
            visibility: visible;
          }
          .print-content {
            position: absolute;
            left: 0;
            top: 0;
            width: 100%;
            background: white;
            font-family: Arial, sans-serif;
          }
          .print-header {
            border-bottom: 2px solid #366092;
            margin-bottom: 20px;
            padding-bottom: 10px;
          }
          .print-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
            page-break-inside: avoid;
          }
          .print-table th,
          .print-table td {
            border: 1px solid #333;
            padding: 8px;
            text-align: left;
            font-size: 10px;
          }
          .print-table th {
            background-color: #366092 !important;
            color: white !important;
            font-weight: bold;
          }
          .print-table tr:nth-child(even) {
            background-color: #f9f9f9;
          }
          .print-page-break {
            page-break-before: always;
          }
          .print-no-break {
            page-break-inside: avoid;
          }
          @page {
            margin: 1in;
            size: A4;
          }
          .no-print {
            display: none !important;
          }
        }
        .print-preview-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.8);
          z-index: 1000;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .print-preview-modal {
          background: white;
          width: 90%;
          height: 90%;
          border-radius: 8px;
          overflow: hidden;
          display: flex;
          flex-direction: column;
        }
        .print-preview-header {
          background: #366092;
          color: white;
          padding: 1rem;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .print-preview-content {
          flex: 1;
          overflow-y: auto;
          padding: 2rem;
          background: white;
        }
        .print-preview-actions {
          padding: 1rem;
          border-top: 1px solid #e5e7eb;
          display: flex;
          justify-content: flex-end;
          gap: 1rem;
        }
      `}</style>
      
      <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <button
            onClick={() => navigate('/')}
            className="text-blue-600 hover:text-blue-800 mb-2"
          >
            ← Back to Dashboard
          </button>
          <h1 className="text-3xl font-bold text-gray-900">{project.name}</h1>
          <p className="text-gray-600">{project.description}</p>
        </div>
        <div className="flex space-x-3">
          <button
            onClick={() => navigate(`/projects/${projectId}/bidding`)}
            className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-md font-medium"
          >
            Manage Bidding
          </button>
        </div>
      </div>

      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {['drawings', 'boq', 'bidding'].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab as any)}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                activeTab === tab
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </nav>
      </div>

      {activeTab === 'drawings' && (
        <div className="space-y-6">
          <div className="bg-white p-6 rounded-lg shadow-md">
            <div className="mb-6">
              <h2 className="text-2xl font-bold text-gray-900 mb-2">📁 Construction Drawings Upload</h2>
              <p className="text-gray-600">Upload your project drawings to automatically generate Bill of Quantities</p>
            </div>
            
            <div className="space-y-6">
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <h3 className="font-semibold text-blue-900 mb-2">📋 Before You Start:</h3>
                <ul className="text-sm text-blue-800 space-y-1">
                  <li>• <strong>Accepted file types:</strong> PDF, AutoCAD DWG, AutoCAD DXF</li>
                  <li>• <strong>Upload method:</strong> You can select one file or multiple files at once</li>
                  <li>• <strong>File requirements:</strong> Ensure drawings include dimensions and revision numbers</li>
                  <li>• <strong>File size limit:</strong> Maximum 50MB per file</li>
                </ul>
              </div>

              <div className="border-2 border-dashed border-blue-300 rounded-lg p-8 bg-blue-50 hover:bg-blue-100 transition-colors">
                <div className="text-center">
                  <div className="mb-4">
                    <svg className="mx-auto h-16 w-16 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                  </div>
                  <label htmlFor="file-upload" className="cursor-pointer">
                    <span className="text-xl font-bold text-gray-900 block mb-2">
                      📂 Click Here to Select Drawing Files
                    </span>
                    <span className="text-lg text-gray-700 block mb-3">
                      Choose single file or multiple files at once
                    </span>
                    <span className="inline-block bg-white text-gray-600 px-4 py-2 rounded-full text-sm font-medium">
                      Supports: PDF • DWG • DXF files
                    </span>
                  </label>
                  <input
                    id="file-upload"
                    type="file"
                    multiple
                    accept=".pdf,.dwg,.dxf"
                    onChange={handleFileUpload}
                    disabled={uploading}
                    className="hidden"
                  />
                </div>
              </div>

              {uploading && (
                <div className="bg-white border rounded-lg p-4">
                  <div className="flex items-center justify-center space-x-2">
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
                    <span className="text-gray-700 font-medium">Uploading files...</span>
                  </div>
                </div>
              )}

              {drawings.length > 0 && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-green-800 font-semibold">
                        ✅ {drawings.length} drawing file(s) uploaded successfully
                      </p>
                      <p className="text-sm text-green-700 mt-1">
                        Ready to get cost estimate and process drawings
                      </p>
                    </div>
                    <div className="flex space-x-3">
                      <button
                        onClick={getCostEstimate}
                        disabled={loadingEstimate}
                        className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white px-6 py-3 rounded-lg font-semibold text-lg shadow-md"
                      >
                        {loadingEstimate ? '⏳ Calculating...' : '💰 Get Cost Estimate'}
                      </button>
                      <button
                        onClick={processDrawings}
                        className="bg-green-600 hover:bg-green-700 text-white px-6 py-3 rounded-lg font-semibold text-lg shadow-md"
                      >
                        🔄 Process All Drawings
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="bg-white rounded-lg shadow-md overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-bold text-gray-900">📋 Your Uploaded Drawings ({drawings.length})</h3>
              {drawings.length > 0 && (
                <p className="text-sm text-gray-600 mt-1">
                  ✅ {drawings.filter(d => d.status === 'processed').length} processed • 
                  ⏳ {drawings.filter(d => d.status === 'processing').length} processing • 
                  ❌ {drawings.filter(d => d.status === 'failed').length} failed
                </p>
              )}
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Filename
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Type
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Drawing Type
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Uploaded
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {drawings.map((drawing) => (
                    <tr key={drawing.id}>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {drawing.filename}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {drawing.file_type.toUpperCase()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {drawing.drawing_type || 'Not classified'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`px-3 py-1 inline-flex text-sm font-semibold rounded-full ${
                          drawing.status === 'processed' ? 'bg-green-100 text-green-800' :
                          drawing.status === 'processing' ? 'bg-yellow-100 text-yellow-800' :
                          drawing.status === 'failed' ? 'bg-red-100 text-red-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {drawing.status === 'processed' ? '✅ Ready' :
                           drawing.status === 'processing' ? '⏳ Processing' :
                           drawing.status === 'failed' ? '❌ Failed' :
                           drawing.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {new Date(drawing.uploaded_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Cost Estimation Section */}
          {drawings.length > 0 && (
            <div className="bg-white p-6 rounded-lg shadow-md">
              <div className="mb-6">
                <h2 className="text-2xl font-bold text-gray-900 mb-2">💰 Project Cost Estimation</h2>
                <p className="text-gray-600">Configure hourly rates and get instant cost estimates for your project</p>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Rate and Currency Controls */}
                <div className="space-y-4">
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                    <h3 className="font-semibold text-blue-900 mb-3">⚙️ Configuration</h3>
                    
                    {/* Hourly Rate Control */}
                    <div className="mb-4">
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Hourly Rate
                      </label>
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => updateHourlyRate(hourlyRate - 5)}
                          className="bg-gray-200 hover:bg-gray-300 text-gray-700 px-3 py-2 rounded-lg font-semibold"
                        >
                          -5
                        </button>
                        <button
                          onClick={() => updateHourlyRate(hourlyRate - 1)}
                          className="bg-gray-200 hover:bg-gray-300 text-gray-700 px-3 py-2 rounded-lg font-semibold"
                        >
                          -1
                        </button>
                        <input
                          type="number"
                          value={hourlyRate}
                          onChange={(e) => updateHourlyRate(Number(e.target.value))}
                          min="1"
                          max="500"
                          className="w-20 px-3 py-2 border border-gray-300 rounded-lg text-center font-semibold"
                        />
                        <button
                          onClick={() => updateHourlyRate(hourlyRate + 1)}
                          className="bg-gray-200 hover:bg-gray-300 text-gray-700 px-3 py-2 rounded-lg font-semibold"
                        >
                          +1
                        </button>
                        <button
                          onClick={() => updateHourlyRate(hourlyRate + 5)}
                          className="bg-gray-200 hover:bg-gray-300 text-gray-700 px-3 py-2 rounded-lg font-semibold"
                        >
                          +5
                        </button>
                      </div>
                    </div>

                    {/* Currency Selection */}
                    <div className="mb-4">
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Currency
                      </label>
                      <select
                        value={currency}
                        onChange={(e) => setCurrency(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg font-semibold"
                      >
                        <option value="GBP">🇬🇧 British Pound (GBP)</option>
                        <option value="USD">🇺🇸 US Dollar (USD)</option>
                        <option value="EUR">🇪🇺 Euro (EUR)</option>
                        <option value="AED">🇦🇪 UAE Dirham (AED)</option>
                      </select>
                    </div>

                    <button
                      onClick={getCostEstimate}
                      disabled={loadingEstimate}
                      className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white px-4 py-2 rounded-lg font-semibold"
                    >
                      {loadingEstimate ? '⏳ Calculating...' : '🔄 Update Estimate'}
                    </button>
                  </div>
                </div>

                {/* Cost Estimate Display */}
                <div className="space-y-4">
                  {costEstimate ? (
                    <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                      <h3 className="font-semibold text-green-900 mb-3">📊 Cost Breakdown</h3>
                      
                      <div className="space-y-3">
                        <div className="flex justify-between items-center py-2 border-b border-green-200">
                          <span className="text-green-800">Drawing Processing:</span>
                          <div className="text-right">
                            <div className="font-semibold text-green-900">
                              {formatCurrency(costEstimate.cost_breakdown.drawing_processing_cost, currency)}
                            </div>
                            <div className="text-sm text-green-700">
                              {costEstimate.cost_breakdown.drawing_processing_hours.toFixed(1)} hours
                            </div>
                          </div>
                        </div>
                        
                        <div className="flex justify-between items-center py-2 border-b border-green-200">
                          <span className="text-green-800">BOQ Generation:</span>
                          <div className="text-right">
                            <div className="font-semibold text-green-900">
                              {formatCurrency(costEstimate.cost_breakdown.boq_generation_cost, currency)}
                            </div>
                            <div className="text-sm text-green-700">
                              {costEstimate.cost_breakdown.boq_generation_hours.toFixed(1)} hours
                            </div>
                          </div>
                        </div>
                        
                        <div className="flex justify-between items-center py-2 border-b border-green-200">
                          <span className="text-green-800">Project Setup:</span>
                          <div className="text-right">
                            <div className="font-semibold text-green-900">
                              {formatCurrency(costEstimate.cost_breakdown.project_setup_cost, currency)}
                            </div>
                            <div className="text-sm text-green-700">
                              {costEstimate.cost_breakdown.project_setup_hours.toFixed(1)} hours
                            </div>
                          </div>
                        </div>
                        
                        <div className="flex justify-between items-center py-3 bg-green-100 rounded-lg px-3 mt-4">
                          <span className="text-green-900 font-bold text-lg">Total Project Cost:</span>
                          <div className="text-right">
                            <div className="font-bold text-green-900 text-xl">
                              {formatCurrency(costEstimate.total_cost, currency)}
                            </div>
                            <div className="text-sm text-green-700">
                              {costEstimate.total_hours.toFixed(1)} total hours @ {formatCurrency(hourlyRate, currency)}/hour
                            </div>
                          </div>
                        </div>

                        {/* Client Approval Section */}
                        <div className="mt-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                          <h4 className="font-semibold text-yellow-900 mb-3">📋 Client Approval Required</h4>
                          {!estimateApproved ? (
                            <div className="space-y-3">
                              <p className="text-yellow-800 text-sm">
                                Before proceeding with BOQ generation, the client must approve this cost estimate.
                                This creates a legally binding agreement for the project scope and cost.
                              </p>
                              <button
                                onClick={requestApproval}
                                className="w-full bg-yellow-600 hover:bg-yellow-700 text-white px-4 py-3 rounded-lg font-semibold text-lg"
                              >
                                ✅ Request Client Approval
                              </button>
                            </div>
                          ) : (
                            <div className="bg-green-100 border border-green-300 rounded-lg p-3">
                              <div className="flex items-center space-x-2">
                                <span className="text-green-600 text-xl">✅</span>
                                <div>
                                  <div className="font-semibold text-green-900">Estimate Approved</div>
                                  <div className="text-sm text-green-700">
                                    Client has approved the cost estimate. You can now generate the BOQ.
                                  </div>
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-center">
                      <div className="text-gray-400 text-lg mb-2">💰 No estimate yet</div>
                      <p className="text-gray-500">Click "Get Cost Estimate" to calculate project costs</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === 'boq' && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-2xl font-bold text-gray-900">📊 Bill of Quantities (BOQ)</h2>
              <p className="text-gray-600 mt-1">Generate professional BOQ from your uploaded drawings</p>
            </div>
            <div className="flex space-x-3">
              <button
                onClick={generateBOQ}
                disabled={drawings.length === 0 || !estimateApproved}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white px-6 py-3 rounded-lg font-semibold text-lg shadow-md"
              >
                {drawings.length === 0 ? '📋 Upload Drawings First' : 
                 !estimateApproved ? '⏳ Awaiting Cost Approval' : '🔄 Generate BOQ'}
              </button>
              {boqItems.length > 0 && (
                <>
                  <button
                    onClick={handlePrintPreview}
                    className="bg-purple-600 hover:bg-purple-700 text-white px-6 py-3 rounded-lg font-semibold text-lg shadow-md"
                  >
                    🖨️ Print Preview
                  </button>
                  <button
                    onClick={downloadBOQExcel}
                    className="bg-green-600 hover:bg-green-700 text-white px-6 py-3 rounded-lg font-semibold text-lg shadow-md"
                  >
                    📊 Download Excel
                  </button>
                </>
              )}
            </div>
          </div>

          <div className="bg-white rounded-lg shadow-md overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Item Code
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Description
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Unit
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Quantity
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Trade
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {boqItems.map((item) => (
                    <tr key={item.id}>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {item.item_code}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-900">
                        {item.description}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {item.unit}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {item.quantity.toFixed(2)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {item.trade}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {boqItems.length === 0 && (
            <div className="text-center py-12">
              <div className="text-gray-400 text-xl mb-3">📋 No BOQ items yet</div>
              <p className="text-gray-500 text-lg">Upload drawings and generate BOQ to see quantities here</p>
              {drawings.length === 0 && (
                <p className="text-blue-600 mt-2 font-medium">👆 Start by uploading your construction drawings above</p>
              )}
            </div>
          )}
        </div>
      )}
      
      {/* Print Preview Modal */}
      {showPrintPreview && (
        <div className="print-preview-overlay">
          <div className="print-preview-modal">
            <div className="print-preview-header">
              <div>
                <h2 className="text-xl font-bold">Print Preview - Bill of Quantities</h2>
                <p className="text-sm opacity-90">Review before printing to ensure proper formatting</p>
              </div>
              <button
                onClick={closePrintPreview}
                className="text-white hover:text-gray-200 text-2xl font-bold"
              >
                ×
              </button>
            </div>
            
            <div className="print-preview-content print-content">
              {/* Print Header */}
              <div className="print-header print-no-break">
                <h1 style={{ fontSize: '24px', fontWeight: 'bold', color: '#366092', marginBottom: '10px' }}>
                  BILL OF QUANTITIES
                </h1>
                <div style={{ fontSize: '16px', marginBottom: '5px' }}>
                  <strong>Project:</strong> {project?.name}
                </div>
                <div style={{ fontSize: '14px', marginBottom: '5px' }}>
                  <strong>Measurement Standard:</strong> {project?.measurement_standard?.toUpperCase()}
                </div>
                <div style={{ fontSize: '12px', color: '#666' }}>
                  Generated: {new Date().toLocaleDateString('en-GB')}
                </div>
              </div>

              {/* Drawing Register */}
              {drawings.length > 0 && (
                <div className="print-no-break" style={{ marginBottom: '30px' }}>
                  <h2 style={{ fontSize: '18px', fontWeight: 'bold', color: '#366092', marginBottom: '15px' }}>
                    DRAWING REGISTER - FOR VERSION CONTROL
                  </h2>
                  <table className="print-table">
                    <thead>
                      <tr>
                        <th>Drawing Number</th>
                        <th>Drawing Title</th>
                        <th>Revision</th>
                        <th>File Type</th>
                        <th>Upload Date</th>
                      </tr>
                    </thead>
                    <tbody>
                      {drawings.map((drawing, index) => (
                        <tr key={drawing.id}>
                          <td>{drawing.drawing_number || `DWG-${index + 1}`}</td>
                          <td>{drawing.drawing_title || drawing.filename}</td>
                          <td>{drawing.revision_number || 'A'}</td>
                          <td>{drawing.file_type.toUpperCase()}</td>
                          <td>{new Date(drawing.uploaded_at).toLocaleDateString('en-GB')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div style={{ 
                    background: '#ffcccc', 
                    padding: '10px', 
                    border: '1px solid #ff0000', 
                    fontSize: '11px',
                    fontWeight: 'bold',
                    color: '#cc0000',
                    marginTop: '10px'
                  }}>
                    IMPORTANT: Contractors must verify they are pricing the correct drawing revisions listed above.
                    Any discrepancies between BOQ quantities and drawing revisions must be reported before bid submission.
                  </div>
                </div>
              )}

              {/* BOQ Items */}
              {boqItems.length > 0 && (
                <div>
                  <h2 style={{ fontSize: '18px', fontWeight: 'bold', color: '#366092', marginBottom: '15px' }}>
                    BILL OF QUANTITIES
                  </h2>
                  <table className="print-table">
                    <thead>
                      <tr>
                        <th style={{ width: '8%' }}>Item No.</th>
                        <th style={{ width: '12%' }}>Item Code</th>
                        <th style={{ width: '40%' }}>Description</th>
                        <th style={{ width: '8%' }}>Unit</th>
                        <th style={{ width: '12%' }}>Quantity</th>
                        <th style={{ width: '15%' }}>Trade</th>
                      </tr>
                    </thead>
                    <tbody>
                      {boqItems.map((item, index) => (
                        <tr key={item.id}>
                          <td style={{ textAlign: 'center' }}>{index + 1}</td>
                          <td>{item.item_code}</td>
                          <td>{item.description}</td>
                          <td style={{ textAlign: 'center' }}>{item.unit}</td>
                          <td style={{ textAlign: 'right' }}>{item.quantity.toFixed(2)}</td>
                          <td>{item.trade}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  
                  <div style={{ 
                    marginTop: '20px', 
                    padding: '15px', 
                    background: '#f9f9f9', 
                    border: '1px solid #ddd',
                    fontSize: '11px'
                  }}>
                    <h3 style={{ fontSize: '14px', fontWeight: 'bold', marginBottom: '10px' }}>
                      INSTRUCTIONS FOR CONTRACTORS:
                    </h3>
                    <ul style={{ margin: 0, paddingLeft: '20px' }}>
                      <li>This BOQ is for quantity reference only</li>
                      <li>Verify all quantities against the drawing revisions listed above</li>
                      <li>Report any discrepancies before bid submission</li>
                      <li>Use the Excel version for pricing and calculations</li>
                    </ul>
                  </div>
                </div>
              )}
            </div>
            
            <div className="print-preview-actions no-print">
              <button
                onClick={closePrintPreview}
                className="px-6 py-2 bg-gray-500 hover:bg-gray-600 text-white rounded-lg font-semibold"
              >
                Close Preview
              </button>
              <button
                onClick={handlePrint}
                className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold"
              >
                🖨️ Print Document
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Client Approval Modal */}
      {showApprovalModal && costEstimate && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <div className="mb-4">
              <h3 className="text-xl font-bold text-gray-900 mb-2">📋 Client Approval Required</h3>
              <p className="text-gray-600 text-sm">
                Please review and approve this cost estimate before proceeding with BOQ generation.
              </p>
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-blue-800">Total Hours:</span>
                  <span className="font-semibold text-blue-900">{costEstimate.total_hours.toFixed(1)} hours</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-blue-800">Hourly Rate:</span>
                  <span className="font-semibold text-blue-900">{formatCurrency(hourlyRate, currency)}/hour</span>
                </div>
                <div className="flex justify-between border-t border-blue-300 pt-2">
                  <span className="text-blue-900 font-bold">Total Cost:</span>
                  <span className="font-bold text-blue-900 text-lg">{formatCurrency(costEstimate.total_cost, currency)}</span>
                </div>
              </div>
            </div>

            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mb-4">
              <p className="text-yellow-800 text-xs">
                <strong>Legal Notice:</strong> By approving this estimate, you agree to the project scope and cost. 
                This creates a binding agreement for the BOQ production services.
              </p>
            </div>

            <div className="flex space-x-3">
              <button
                onClick={handleRejectEstimate}
                className="flex-1 bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg font-semibold"
              >
                ❌ Reject
              </button>
              <button
                onClick={handleApproveEstimate}
                className="flex-1 bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg font-semibold"
              >
                ✅ Approve & Proceed
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
    </div>
  )
}
