const API_BASE = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '')

function apiUrl(path: string): string {
  if (API_BASE) return `${API_BASE}${path}`
  if (process.env.NODE_ENV !== 'production') return `http://localhost:8001${path}`
  throw new Error('The Kazi-Kasi API is not configured. Set NEXT_PUBLIC_API_URL for this deployment.')
}

export interface Job {
  id: string
  title: string
  employer: string
  location: string
  salary_min?: number | null
  salary_max?: number | null
  match_score: number
  match_reasons: string[]
  deadline?: string | null
  posted?: string | null
  url: string
}

export interface JobDetail extends Job {
  description: string
  source_url: string
  requirements: string[]
  benefits: string[]
}

export interface JobsResponse {
  jobs: Job[]
  total: number
  limit: number
  offset: number
}

export interface AuthResponse {
  access_token: string
  token_type: string
}

async function request<T>(path: string, init: RequestInit = {}, authenticated = false): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  if (authenticated) {
    const token = getToken()
    if (!token) throw new Error('Your session has expired. Please sign in again.')
    headers.set('Authorization', `Bearer ${token}`)
  }
  let response: Response
  try {
    response = await fetch(apiUrl(path), { ...init, headers, cache: 'no-store' })
  } catch {
    throw new Error('Could not reach Kazi-Kasi. Check your connection and try again.')
  }
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const message = typeof payload?.detail === 'string' ? payload.detail : `Request failed (${response.status})`
    if (response.status === 401 && authenticated && typeof window !== 'undefined') {
      logout()
      window.location.replace('/auth')
    }
    throw new Error(message)
  }
  return payload as T
}

export function fetchJobs(limit = 20, offset = 0): Promise<JobsResponse> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  return request(`/api/jobs?${params}`, {}, true)
}

export function fetchJob(jobId: string): Promise<JobDetail> {
  return request(`/api/jobs/${encodeURIComponent(jobId)}`, {}, true)
}

export async function checkHealth(): Promise<boolean> {
  try {
    await request('/api/health')
    return true
  } catch {
    return false
  }
}

export async function register(email: string, password: string, name: string): Promise<AuthResponse> {
  const data = await request<AuthResponse>('/api/auth/register', {
    method: 'POST', body: JSON.stringify({ email, password, name }),
  })
  if (typeof window !== 'undefined') window.localStorage.setItem('token', data.access_token)
  return data
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const data = await request<AuthResponse>('/api/auth/login', {
    method: 'POST', body: JSON.stringify({ email, password }),
  })
  if (typeof window !== 'undefined') window.localStorage.setItem('token', data.access_token)
  return data
}

export function logout(): void {
  if (typeof window !== 'undefined') window.localStorage.removeItem('token')
}

export function getToken(): string | null {
  return typeof window === 'undefined' ? null : window.localStorage.getItem('token')
}

export function isAuthenticated(): boolean {
  return Boolean(getToken())
}
