import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AccountBar from '../AccountBar'

vi.mock('../api', () => ({
  getMe: vi.fn(),
  requestMagicLink: vi.fn().mockResolvedValue(true),
  logout: vi.fn().mockResolvedValue(undefined),
  startCheckout: vi.fn(),
  openBillingPortal: vi.fn(),
}))
import { getMe, requestMagicLink, startCheckout } from '../api'

afterEach(() => vi.clearAllMocks())
beforeEach(() => { window.history.replaceState({}, '', '/') })

describe('AccountBar', () => {
  it('signed out: shows Sign in, then the email form, then confirmation', async () => {
    getMe.mockResolvedValue(null)
    render(<AccountBar />)
    const signIn = await screen.findByRole('button', { name: /sign in/i })
    await userEvent.click(signIn)
    await userEvent.type(screen.getByLabelText('email'), 'user@example.com')
    await userEvent.click(screen.getByRole('button', { name: /email me a link/i }))
    await waitFor(() =>
      expect(screen.getByText(/check your email/i)).toBeInTheDocument(),
    )
    expect(requestMagicLink).toHaveBeenCalledWith('user@example.com')
  })

  it('signed in free: shows email and Upgrade', async () => {
    getMe.mockResolvedValue({ email: 'free@example.com', tier: 'free' })
    render(<AccountBar />)
    expect(await screen.findByTestId('account-email')).toHaveTextContent('free@example.com')
    expect(screen.getByRole('button', { name: /upgrade to pro/i })).toBeInTheDocument()
  })

  it('signed in pro: shows Pro badge and Manage subscription', async () => {
    getMe.mockResolvedValue({ email: 'pro@example.com', tier: 'pro' })
    render(<AccountBar />)
    expect(await screen.findByText('Pro')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /manage subscription/i })).toBeInTheDocument()
  })

  it('upgrade triggers checkout', async () => {
    getMe.mockResolvedValue({ email: 'free@example.com', tier: 'free' })
    startCheckout.mockResolvedValue('https://checkout.stripe/x')
    render(<AccountBar />)
    const btn = await screen.findByRole('button', { name: /upgrade to pro/i })
    await userEvent.click(btn)
    await waitFor(() => expect(startCheckout).toHaveBeenCalledWith('monthly'))
  })
})
