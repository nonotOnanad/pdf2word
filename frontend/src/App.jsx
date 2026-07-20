import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { convertPdf } from './api'

const MAX_SIZE_BYTES = 20 * 1024 * 1024

export default function App() {
  const [status, setStatus] = useState('idle') // idle | converting | done | error
  const [error, setError] = useState('')
  const [download, setDownload] = useState(null) // { url, filename }

  const reset = () => {
    if (download) URL.revokeObjectURL(download.url)
    setDownload(null)
    setError('')
    setStatus('idle')
  }

  const handleFile = useCallback(async (file) => {
    reset()
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError("That file isn't a PDF.")
      setStatus('error')
      return
    }
    if (file.size > MAX_SIZE_BYTES) {
      setError('Max file size is 20 MB.')
      setStatus('error')
      return
    }
    setStatus('converting')
    try {
      const { blob, filename } = await convertPdf(file)
      setDownload({ url: URL.createObjectURL(blob), filename })
      setStatus('done')
    } catch (e) {
      setError(e.message || 'Something went wrong.')
      setStatus('error')
    }
  }, [download])

  const onDrop = useCallback((accepted) => handleFile(accepted[0]), [handleFile])
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: false,
  })

  return (
    <main className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6">
      <h1 className="text-3xl font-bold text-slate-800 mb-2">PDF to Word</h1>
      <p className="text-slate-500 mb-8">
        Convert PDFs to editable .docx — free. Your files are never stored.
      </p>

      <div
        {...getRootProps()}
        className={`w-full max-w-lg border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition
          ${isDragActive ? 'border-blue-500 bg-blue-50' : 'border-slate-300 bg-white'}`}
      >
        <input {...getInputProps()} data-testid="file-input" />
        {status === 'converting' ? (
          <p className="text-slate-600 animate-pulse">Converting…</p>
        ) : (
          <p className="text-slate-600">
            Drag a PDF here, or click to choose a file (max 20 MB, 100 pages)
          </p>
        )}
      </div>

      {status === 'done' && download && (
        <a
          href={download.url}
          download={download.filename}
          className="mt-6 px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700"
        >
          Download {download.filename}
        </a>
      )}

      {status === 'error' && (
        <p className="mt-6 text-red-600" role="alert">{error}</p>
      )}
    </main>
  )
}
