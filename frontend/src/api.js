const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export class ApiError extends Error {
  constructor(code, message) {
    super(message)
    this.code = code
  }
}

// credentials:'include' is required so the cross-origin session cookie
// (frontend on Vercel, API on Render) is sent with every request.
const withCreds = (opts = {}) => ({ credentials: 'include', ...opts })

export async function convertPdf(file) {
  const form = new FormData()
  form.append('file', file)

  let resp
  try {
    resp = await fetch(`${API_URL}/api/convert`, withCreds({ method: 'POST', body: form }))
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

// --- auth ---

export async function getMe() {
  const resp = await fetch(`${API_URL}/api/auth/me`, withCreds())
  if (resp.status === 401) return null
  if (!resp.ok) throw new ApiError('ME_FAILED', 'Could not load your account.')
  return resp.json() // { email, id, tier }
}

export async function requestMagicLink(email) {
  await fetch(`${API_URL}/api/auth/request-link`, withCreds({
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  }))
  return true // backend always 200 to avoid account enumeration
}

export async function logout() {
  await fetch(`${API_URL}/api/auth/logout`, withCreds({ method: 'POST' }))
}

// --- billing ---

export async function startCheckout(plan = 'monthly') {
  const resp = await fetch(`${API_URL}/api/billing/checkout`, withCreds({
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plan }),
  }))
  if (!resp.ok) throw new ApiError('CHECKOUT', 'Could not start checkout.')
  const { url } = await resp.json()
  return url
}

export async function openBillingPortal() {
  const resp = await fetch(`${API_URL}/api/billing/portal`, withCreds({ method: 'POST' }))
  if (!resp.ok) throw new ApiError('PORTAL', 'Could not open the billing portal.')
  const { url } = await resp.json()
  return url
}
