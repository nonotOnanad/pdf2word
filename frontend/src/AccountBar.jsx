import { useEffect, useState } from 'react'
import { getMe, logout, openBillingPortal, requestMagicLink, startCheckout } from './api'

export default function AccountBar() {
  const [me, setMe] = useState(null)      // { email, tier } | null
  const [loading, setLoading] = useState(true)
  const [showLogin, setShowLogin] = useState(false)
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')

  useEffect(() => {
    getMe().then(setMe).catch(() => setMe(null)).finally(() => setLoading(false))
    if (new URLSearchParams(window.location.search).get('upgraded') === '1') {
      setNotice('Thanks — your subscription is now active.')
    }
  }, [])

  const submitEmail = async (e) => {
    e.preventDefault()
    if (!email) return
    setBusy(true)
    try {
      await requestMagicLink(email)
      setSent(true)
    } finally {
      setBusy(false)
    }
  }

  const doLogout = async () => {
    await logout()
    setMe(null)
    setShowLogin(false)
    setSent(false)
  }

  const goCheckout = async (plan) => {
    setBusy(true)
    try {
      window.location.href = await startCheckout(plan)
    } catch {
      setNotice('Could not start checkout. Please try again.')
      setBusy(false)
    }
  }

  const goPortal = async () => {
    setBusy(true)
    try {
      window.location.href = await openBillingPortal()
    } catch {
      setNotice('Could not open the billing portal.')
      setBusy(false)
    }
  }

  const btn = 'px-3 py-1.5 rounded-md text-sm font-medium'

  return (
    <header className="w-full max-w-3xl flex items-center justify-end gap-3 py-4">
      {notice && <p role="status" className="text-sm text-emerald-700 mr-auto">{notice}</p>}

      {loading ? (
        <span className="text-sm text-slate-400" aria-busy="true">…</span>
      ) : me ? (
        <div className="flex items-center gap-3">
          <span data-testid="account-email" className="text-sm text-slate-600">{me.email}</span>
          {me.tier === 'pro' ? (
            <>
              <span className="px-2 py-0.5 text-xs font-semibold rounded bg-emerald-100 text-emerald-700">Pro</span>
              <button className={`${btn} bg-slate-100 text-slate-700 hover:bg-slate-200`}
                      onClick={goPortal} disabled={busy}>Manage subscription</button>
            </>
          ) : (
            <button className={`${btn} bg-blue-600 text-white hover:bg-blue-700`}
                    onClick={() => goCheckout('monthly')} disabled={busy}>Upgrade to Pro</button>
          )}
          <button className={`${btn} text-slate-500 hover:text-slate-700`} onClick={doLogout}>Sign out</button>
        </div>
      ) : showLogin ? (
        sent ? (
          <p role="status" className="text-sm text-slate-600">Check your email for a sign-in link.</p>
        ) : (
          <form onSubmit={submitEmail} className="flex items-center gap-2">
            <input aria-label="email" type="email" required value={email}
                   onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com"
                   className="px-3 py-1.5 border border-slate-300 rounded-md text-sm" />
            <button type="submit" disabled={busy}
                    className={`${btn} bg-blue-600 text-white hover:bg-blue-700`}>Email me a link</button>
          </form>
        )
      ) : (
        <button className={`${btn} bg-slate-100 text-slate-700 hover:bg-slate-200`}
                onClick={() => setShowLogin(true)}>Sign in</button>
      )}
    </header>
  )
}
