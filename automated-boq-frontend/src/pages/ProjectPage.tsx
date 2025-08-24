import React, { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'

interface Project {
  id: string
  name: string
  description?: string
  measurement_standard: string
  status: string
}

interface Drawing {
  id: string
  filename: string
  file_type: string
  status: string
}

interface BOQItem {
  id: string
  item_code: string
  description: string
  unit: string
  quantity: number
  category: string
}

interface CostEstimate {
  estimated_hours: number
  total_cost: number
}

export default function ProjectPage() {
  const { projectId } = useParams()
  const token = localStorage.getItem('token')
  const [project, setProject] = useState<Project | null>(null)
  const [drawings, setDrawings] = useState<Drawing[]>([])
  const [boqItems, setBOQItems] = useState<BOQItem[]>([])
  const [uploading, setUploading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [costEstimate, setCostEstimate] = useState<CostEstimate | null>(null)
  const [hourlyRate, setHourlyRate] = useState(45)
  const [currency, setCurrency] = useState('GBP')
  const [showPrintPreview, setShowPrintPreview] = useState(false)
  const [estimateApproved, setEstimateApproved] = useState(false)
  const [estimateRejected, setEstimateRejected] = useState(false)

  useEffect(() => {
    if (projectId && token) {
      fetchProjectData()
    }
  }, [projectId, token])

  useEffect(() => {
    if (drawings.length > 0) {
      getCostEstimate()
    }
  }, [drawings, hourlyRate, currency])

  useEffect(() => {
    let timeoutId: NodeJS.Timeout | undefined
    if (estimateApproved || estimateRejected) {
      timeoutId = setTimeout(() => {
        setEstimateApproved(false)
        setEstimateRejected(false)
      }, 3000)
    }
    return () => {
      if (timeoutId) clearTimeout(timeoutId)
    }
  }, [estimateApproved, estimateRejected])

  const fetchProjectData = async () => {
    try {
      const [projectRes, drawingsRes, boqRes] = await Promise.all([
        fetch(`http://localhost:8000/projects/${projectId}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        }),
        fetch(`http://localhost:8000/projects/${projectId}/drawings`, {
          headers: { 'Authorization': `Bearer ${token}` }
        }),
        fetch(`http://localhost:8000/projects/${projectId}/boq`, {
          headers: { 'Authorization': `Bearer ${token}` }
        })
      ])

      if (projectRes.ok) setProject(await projectRes.json())
      if (drawingsRes.ok) setDrawings(await drawingsRes.json())
      if (boqRes.ok) setBOQItems(await boqRes.json())
    } catch (error) {
      console.error('Error fetching project data:', error)
    }
  }

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || [])
    if (files.length === 0) return

    const invalidFiles = files.filter((file: File) => {
      const validTypes = ['application/pdf', 'application/dwg', 'application/dxf', 'image/vnd.dwg', 'image/vnd.dxf']
      const validExtensions = ['.pdf', '.dwg', '.dxf']
      const hasValidType = validTypes.includes(file.type)
      const hasValidExtension = validExtensions.some(ext => file.name.toLowerCase().endsWith(ext))
      return !hasValidType && !hasValidExtension
    })

    if (invalidFiles.length > 0) {
      alert(`Invalid file types detected: ${invalidFiles.map((f: File) => f.name).join(', ')}. Please upload only PDF, DWG, or DXF files.`)
      return
    }

    setUploading(true)
    try {
      const uploadPromises = files.map(async (file: File) => {
        const formData = new FormData()
        formData.append('file', file)

        const response = await fetch(`http://localhost:8000/projects/${projectId}/drawings/upload`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`
          },
          body: formData
        })

        if (!response.ok) {
          const errorData = await response.text()
          throw new Error(`Failed to upload ${file.name}: ${errorData}`)
        }

        return await response.json()
      })

      const uploadedDrawings = await Promise.all(uploadPromises)
      setDrawings(prev => [...prev, ...uploadedDrawings])
      
      event.target.value = ''
    } catch (error) {
      console.error('Upload error:', error)
      alert(`Upload failed: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }finally {
      setUploading(false)
    }
  }


  const generateBOQ = async () => {
    setGenerating(true)
    try {
      await fetch(`http://localhost:8000/projects/${projectId}/generate-boq`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      })
      await fetchProjectData()
    } catch (error) {
      console.error('BOQ generation error:', error)
    } finally {
      setGenerating(false)
    }
  }

  const downloadBOQExcel = async () => {
    try {
      const response = await fetch(`http://localhost:8000/projects/${projectId}/boq/download?format=excel`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      
      if (response.ok) {
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.style.display = 'none'
        a.href = url
        a.download = `${project?.name || 'project'}_boq.xlsx`
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)
      }
    } catch (error) {
      console.error('Download error:', error)
    }
  }


  const getCostEstimate = async () => {
    try {
      const response = await fetch(
        `http://localhost:8000/projects/${projectId}/quick-estimate?hourly_rate=${hourlyRate}&currency=${currency}`,
        {
          headers: { 'Authorization': `Bearer ${token}` }
        }
      )
      
      if (response.ok) {
        const estimate = await response.json()
        setCostEstimate(estimate)
      }
    } catch (error) {
      console.error('Cost estimate error:', error)
    }
  }

  const updateHourlyRate = (newRate: number) => {
    setHourlyRate(newRate)
  }

  const formatCurrency = (amount: number, currencyCode: string) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currencyCode
    }).format(amount || 0)
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
    setEstimateRejected(false)
  }

  const handleRejectEstimate = () => {
    setEstimateRejected(true)
    setEstimateApproved(false)
  }


  if (!project) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading project...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-white shadow-lg rounded-lg overflow-hidden">
          <div className="bg-gradient-to-r from-blue-600 to-blue-800 px-6 py-4">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-white">{project.name}</h1>
                <p className="text-blue-100 mt-1">
                  {project.description || 'Construction project with automated BOQ generation'}
                </p>
              </div>
              <div className="text-right">
                <div className="text-blue-100 text-sm">Measurement Standard</div>
                <div className="text-white font-semibold">{project.measurement_standard}</div>
              </div>
            </div>
          </div>

          <div className="p-6">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              <div className="lg:col-span-2">
                <div className="space-y-6">
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
                    <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center">
                      📋 Upload Construction Drawings
                    </h2>
                    
                    <div className="mb-4">
                      <h3 className="text-lg font-semibold text-gray-800 mb-2">Instructions:</h3>
                      <ul className="text-sm text-gray-600 space-y-1">
                        <li>• <strong>Supported formats:</strong> PDF, DWG, DXF files</li>
                        <li>• <strong>Multiple uploads:</strong> Select multiple files at once or upload one by one</li>
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
                            Supports: PDF, DWG, DXF files
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
                            <p className="text-green-600 text-sm mt-1">
                              Ready for processing and BOQ generation
                            </p>
                          </div>
                        </div>
                        
                        <div className="mt-4 space-y-2">
                          {drawings.map((drawing) => (
                            <div key={drawing.id} className="flex items-center justify-between bg-white p-3 rounded border">
                              <div className="flex items-center space-x-3">
                                <span className="text-green-600 font-bold">✅</span>
                                <div>
                                  <p className="font-medium text-gray-900">{drawing.filename}</p>
                                  <p className="text-sm text-gray-500">
                                    {drawing.file_type?.toUpperCase()} • {drawing.status || 'Ready'}
                                  </p>
                                </div>
                              </div>
                              <span className="text-green-600 text-sm font-medium">Ready</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {boqItems.length > 0 && (
                    <div className="bg-white border rounded-lg overflow-hidden">
                      <div className="bg-gray-50 px-6 py-4 border-b">
                        <h3 className="text-lg font-semibold text-gray-900">Generated Bill of Quantities</h3>
                        <p className="text-sm text-gray-600 mt-1">
                          {boqItems.length} items extracted from uploaded drawings
                        </p>
                      </div>
                      
                      <div className="overflow-x-auto">
                        <table className="min-w-full divide-y divide-gray-200">
                          <thead className="bg-gray-50">
                            <tr>
                              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Item Code</th>
                              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Description</th>
                              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Unit</th>
                              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Quantity</th>
                              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Category</th>
                            </tr>
                          </thead>
                          <tbody className="bg-white divide-y divide-gray-200">
                            {boqItems.slice(0, 10).map((item) => (
                              <tr key={item.id}>
                                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{item.item_code}</td>
                                <td className="px-6 py-4 text-sm text-gray-900">{item.description}</td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{item.unit}</td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{item.quantity?.toFixed(2) || '0.00'}</td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{item.category}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      
                      {boqItems.length > 10 && (
                        <div className="bg-gray-50 px-6 py-3 text-center">
                          <p className="text-sm text-gray-600">
                            Showing 10 of {boqItems.length} items. Download Excel file to view all items.
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              <div className="space-y-6">
                {costEstimate && (
                  <div className="bg-white border rounded-lg p-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">💰 Cost Estimation</h3>
                    
                    <div className="space-y-4">
                      <div className="flex items-center space-x-4">
                        <label className="text-sm font-medium text-gray-700">Hourly Rate:</label>
                        <div className="flex items-center space-x-2">
                          <select
                            value={currency}
                            onChange={(e) => setCurrency(e.target.value)}
                            className="border border-gray-300 rounded px-2 py-1 text-sm"
                          >
                            <option value="GBP">GBP (£)</option>
                            <option value="USD">USD ($)</option>
                            <option value="EUR">EUR (€)</option>
                            <option value="AED">AED (د.إ)</option>
                          </select>
                          <input
                            type="number"
                            value={hourlyRate}
                            onChange={(e) => updateHourlyRate(Number(e.target.value))}
                            className="border border-gray-300 rounded px-3 py-1 w-20 text-sm"
                            min="1"
                            step="1"
                          />
                        </div>
                      </div>

                      <div className="bg-blue-50 rounded-lg p-4">
                        <div className="space-y-2">
                          <div className="flex justify-between">
                            <span className="text-sm text-gray-600">Estimated Hours:</span>
                            <span className="font-medium">{costEstimate.estimated_hours?.toFixed(1) || '0.0'} hours</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-sm text-gray-600">Hourly Rate:</span>
                            <span className="font-medium">{formatCurrency(hourlyRate, currency)}/hour</span>
                          </div>
                          <div className="border-t pt-2 flex justify-between">
                            <span className="font-semibold text-gray-900">Total Cost:</span>
                            <span className="font-bold text-blue-600 text-lg">
                              {formatCurrency(costEstimate.total_cost, currency)}
                            </span>
                          </div>
                        </div>
                      </div>

                      <div className="flex space-x-2">
                        <button
                          onClick={handleApproveEstimate}
                          className={`flex-1 px-4 py-2 rounded text-sm font-medium transition-colors ${
                            estimateApproved 
                              ? 'bg-green-600 text-white' 
                              : 'bg-green-100 text-green-700 hover:bg-green-200'
                          }`}
                        >
                          {estimateApproved ? '✅ Approved' : '👍 Approve'}
                        </button>
                        <button
                          onClick={handleRejectEstimate}
                          className={`flex-1 px-4 py-2 rounded text-sm font-medium transition-colors ${
                            estimateRejected 
                              ? 'bg-red-600 text-white' 
                              : 'bg-red-100 text-red-700 hover:bg-red-200'
                          }`}
                        >
                          {estimateRejected ? '❌ Rejected' : '👎 Reject'}
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                <div className="bg-white border rounded-lg p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">🔧 Actions</h3>
                  
                  <div className="space-y-3">
                    <button
                      onClick={generateBOQ}
                      disabled={drawings.length === 0 || generating}
                      className="w-full bg-blue-600 text-white px-4 py-3 rounded-lg font-medium hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                    >
                      {generating ? (
                        <span className="flex items-center justify-center">
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                          Generating BOQ...
                        </span>
                      ) : (
                        '📊 Generate BOQ from Drawings'
                      )}
                    </button>

                    {boqItems.length > 0 && (
                      <>
                        <button
                          onClick={downloadBOQExcel}
                          className="w-full bg-green-600 text-white px-4 py-3 rounded-lg font-medium hover:bg-green-700 transition-colors"
                        >
                          📥 Download BOQ (Excel)
                        </button>

                        <button
                          onClick={handlePrintPreview}
                          className="w-full bg-purple-600 text-white px-4 py-3 rounded-lg font-medium hover:bg-purple-700 transition-colors"
                        >
                          🖨️ Print Preview
                        </button>
                      </>
                    )}
                  </div>
                </div>

                <div className="bg-gray-50 border rounded-lg p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">📈 Project Status</h3>
                  
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-600">Drawings Uploaded:</span>
                      <span className="font-medium text-green-600">{drawings.length}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-600">BOQ Items Generated:</span>
                      <span className="font-medium text-blue-600">{boqItems.length}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-600">Project Status:</span>
                      <span className="font-medium text-gray-900">{project.status}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {showPrintPreview && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full mx-4 max-h-[90vh] overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="text-lg font-semibold">Print Preview - BOQ</h3>
              <div className="flex space-x-2">
                <button
                  onClick={handlePrint}
                  className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
                >
                  🖨️ Print
                </button>
                <button
                  onClick={closePrintPreview}
                  className="bg-gray-500 text-white px-4 py-2 rounded hover:bg-gray-600"
                >
                  Close
                </button>
              </div>
            </div>
            
            <div className="p-6 overflow-y-auto max-h-[calc(90vh-120px)]">
              <div className="print:block">
                <div className="text-center mb-6">
                  <h1 className="text-2xl font-bold">Bill of Quantities</h1>
                  <h2 className="text-xl text-gray-600 mt-2">{project.name}</h2>
                  <p className="text-gray-500 mt-1">Generated on {new Date().toLocaleDateString()}</p>
                </div>

                {boqItems.length > 0 ? (
                  <table className="w-full border-collapse border border-gray-300">
                    <thead>
                      <tr className="bg-gray-100">
                        <th className="border border-gray-300 px-4 py-2 text-left">Item Code</th>
                        <th className="border border-gray-300 px-4 py-2 text-left">Description</th>
                        <th className="border border-gray-300 px-4 py-2 text-left">Unit</th>
                        <th className="border border-gray-300 px-4 py-2 text-right">Quantity</th>
                        <th className="border border-gray-300 px-4 py-2 text-left">Category</th>
                      </tr>
                    </thead>
                    <tbody>
                      {boqItems.map((item) => (
                        <tr key={item.id}>
                          <td className="border border-gray-300 px-4 py-2">{item.item_code}</td>
                          <td className="border border-gray-300 px-4 py-2">{item.description}</td>
                          <td className="border border-gray-300 px-4 py-2">{item.unit}</td>
                          <td className="border border-gray-300 px-4 py-2 text-right">{item.quantity?.toFixed(2) || '0.00'}</td>
                          <td className="border border-gray-300 px-4 py-2">{item.category}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="text-center text-gray-500 py-8">No BOQ items to display</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
