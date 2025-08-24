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
}

interface Drawing {
  id: string
  filename: string
  file_type: string
  drawing_type: string
  status: string
  uploaded_at: string
}

interface BOQItem {
  id: string
  item_code: string
  description: string
  unit: string
  quantity: number
  trade: string
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

  useEffect(() => {
    if (projectId) {
      fetchProjectData()
    }
  }, [projectId])

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
                        Ready to process drawings and generate BOQ
                      </p>
                    </div>
                    <button
                      onClick={processDrawings}
                      className="bg-green-600 hover:bg-green-700 text-white px-6 py-3 rounded-lg font-semibold text-lg shadow-md"
                    >
                      🔄 Process All Drawings
                    </button>
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
                disabled={drawings.length === 0}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white px-6 py-3 rounded-lg font-semibold text-lg shadow-md"
              >
                {drawings.length === 0 ? '📋 Upload Drawings First' : '🔄 Generate BOQ'}
              </button>
              {boqItems.length > 0 && (
                <button
                  onClick={downloadBOQExcel}
                  className="bg-green-600 hover:bg-green-700 text-white px-6 py-3 rounded-lg font-semibold text-lg shadow-md"
                >
                  📊 Download Excel
                </button>
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
    </div>
  )
}
