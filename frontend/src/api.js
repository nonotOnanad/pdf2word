const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export class ApiError extends Error {
  constructor(code, message) {
    super(message)
    this.code = code
  }
}

export async function convertPdf(file) {
  const form = new FormData()
  form.append('file', file)

  let resp
  try {
    resp = await fetch(`${API_URL}/api/convert`, { method: 'POST', body: form })
  } catch {
    throw new ApiError('NETWORK', 'Could not reach the server. Try again in a moment.')
  }

  if (!resp.ok) {
    let code = 'UNKNOWN'
    let message = 'Something went wrong. Please try again.'
    try {
      const body = await resp.json()
      code = body.code || code
      message = body.message || message
    } catch { /* non-JSON error body */ }
    throw new ApiError(code, message)
  }

  const disposition = resp.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename="(.+?)"/)
  const filename = match ? match[1] : 'converted.docx'
  const blob = await resp.blob()
  return { blob, filename }
}
