export const apiBase = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1').replace(/\/+$/, '')

export async function readHealth(signal: AbortSignal) {
  const response = await fetch(apiBase + '/health', {signal, cache: 'no-store', credentials: 'omit'})
  if (!response.ok || (await response.json())?.status !== 'ok') throw new Error('API unavailable')
}
