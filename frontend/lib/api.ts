const API_BASE = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '')

function apiUrl(path: string): string {
  if (API_BASE) return `${API_BASE}${path}`
  // Keep browser requests same-origin. Next's rewrite proxies /api to the
  // separately running FastAPI service in local and preview environments.
  return path
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

export interface Profile {
  id: string
  name: string
  home_county: string | null
  home_area: string | null
  max_commute_km: number | null
  role_families: string[]
  skills: string[]
  entry_fits: string[]
  employment_types: string[]
  work_modes: string[]
  min_monthly_pay: number | null
  deadline_within_days: number | null
  include_remote: boolean
  created_at: string
  updated_at: string
}

export interface CvField {
  value: string | string[]
  evidence: string
  confidence: number
}

export interface ProfileCv {
  id: number
  filename: string
  chars: number
  created_at: string
  fields: Record<string, CvField>
}

async function request<T>(path: string, init: RequestInit = {}, authenticated = false): Promise<T> {
  const headers = new Headers(init.headers)
  const isFormData = typeof FormData !== 'undefined' && init.body instanceof FormData
  if (init.body && !isFormData && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (authenticated) {
    const token = getToken()
    if (!token) throw new Error('Your session has expired. Please sign in again.')
    headers.set('Authorization', `Bearer ${token}`)
  }
  const targetUrl = apiUrl(path)
  let response: Response
  try {
    response = await fetch(targetUrl, { ...init, headers, cache: 'no-store' })
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


export function fetchProfile(): Promise<Profile> {
  return request('/api/profile', {}, true)
}

export function updateProfile(profile: Partial<Profile>): Promise<Profile> {
  return request('/api/profile', { method: 'PUT', body: JSON.stringify(profile) }, true)
}

export function fetchProfileCv(): Promise<{ cv: ProfileCv | null }> {
  return request('/api/profile/cv', {}, true)
}

export function uploadProfileCv(file: File): Promise<{ cv: ProfileCv; profile: Profile | null; suggestions: Record<string, unknown>; message: string }> {
  const form = new FormData()
  form.append('file', file)
  return request('/api/profile/cv', { method: 'POST', body: form }, true)
}

export function deleteProfileCv(): Promise<{ cv: ProfileCv | null; deleted: boolean }> {
  return request('/api/profile/cv', { method: 'DELETE' }, true)
}

export function fetchCurrentUser(): Promise<{ id: string; email: string; name: string }> {
  return request('/api/auth/me', {}, true)
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
