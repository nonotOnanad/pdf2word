import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../App'

vi.mock('../api', () => ({
  convertPdf: vi.fn(),
  ApiError: class ApiError extends Error {
    constructor(code, message) { super(message); this.code = code }
  },
}))
import { convertPdf } from '../api'

afterEach(() => vi.clearAllMocks())

function makePdf(name = 'doc.pdf', sizeBytes = 1000) {
  return new File([new Uint8Array(sizeBytes)], name, { type: 'application/pdf' })
}

describe('App', () => {
  it('shows privacy copy', () => {
    render(<App />)
    expect(screen.getByText(/your files are never stored/i)).toBeInTheDocument()
  })

  it('converts a file and shows download button', async () => {
    convertPdf.mockResolvedValue({ blob: new Blob(['x']), filename: 'doc.docx' })
    render(<App />)
    const input = screen.getByTestId('file-input')
    await userEvent.upload(input, makePdf())
    await waitFor(() =>
      expect(screen.getByRole('link', { name: /download/i })).toBeInTheDocument(),
    )
  })

  it('rejects oversized file client-side', async () => {
    render(<App />)
    const input = screen.getByTestId('file-input')
    await userEvent.upload(input, makePdf('big.pdf', 21 * 1024 * 1024))
    expect(await screen.findByText(/max file size is 20 mb/i)).toBeInTheDocument()
    expect(convertPdf).not.toHaveBeenCalled()
  })

  it('shows API error message', async () => {
    const { ApiError } = await import('../api')
    convertPdf.mockRejectedValue(new ApiError('SCANNED', "This looks like a scanned PDF — OCR isn't supported yet."))
    render(<App />)
    await userEvent.upload(screen.getByTestId('file-input'), makePdf())
    expect(await screen.findByText(/scanned pdf/i)).toBeInTheDocument()
  })
})
