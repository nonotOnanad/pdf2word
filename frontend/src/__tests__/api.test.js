import { describe, it, expect, vi, afterEach } from 'vitest'
import { convertPdf, ApiError } from '../api'

afterEach(() => vi.restoreAllMocks())

const fakeFile = new File([new Uint8Array([1, 2, 3])], 'report.pdf', {
  type: 'application/pdf',
})

describe('convertPdf', () => {
  it('returns blob and filename on success', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'Content-Disposition': 'attachment; filename="report.docx"' }),
      blob: async () => new Blob(['docx-bytes']),
    }))
    const { blob, filename } = await convertPdf(fakeFile)
    expect(filename).toBe('report.docx')
    expect(blob.size).toBeGreaterThan(0)
  })

  it('throws ApiError with code on API error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ code: 'SCANNED', message: 'This looks like a scanned PDF — OCR isn\'t supported yet.' }),
      { status: 422, headers: { 'Content-Type': 'application/json' } },
    )))
    await expect(convertPdf(fakeFile)).rejects.toMatchObject({ code: 'SCANNED' })
  })

  it('throws ApiError with NETWORK code when fetch fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('failed')))
    await expect(convertPdf(fakeFile)).rejects.toBeInstanceOf(ApiError)
  })
})
