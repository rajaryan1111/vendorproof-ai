import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { Dashboard } from './Dashboard'
import { apiBase } from './api'
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
it('shows pending, failure and recovery from the configured API', async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(Response.json({status:'unexpected'})).mockResolvedValueOnce(Response.json({status:'ok'}))
  vi.stubGlobal('fetch',fetcher)
  render(<Dashboard/>)
  expect(screen.getByRole('status').textContent).toBe('Checking connection')
  await screen.findByText('Unavailable')
  fireEvent.click(screen.getByRole('button'))
  await screen.findByText('Connected')
  expect(fetcher).toHaveBeenCalledWith(apiBase + '/health',expect.objectContaining({credentials:'omit'}))
})
