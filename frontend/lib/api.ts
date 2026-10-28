const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

export interface Job {
  id: string;
  title: string;
  employer: string;
  location: string;
  salary_min?: number;
  salary_max?: number;
  match_score: number;
  match_reasons: string[];
  deadline?: string;
  posted?: string;
  url: string;
}

export interface JobDetail {
  id: string;
  title: string;
  employer: string;
  location: string;
  description: string;
  salary_min?: number;
  salary_max?: number;
  deadline?: string;
  posted?: string;
  source_url: string;
  requirements: string[];
  benefits: string[];
}

export interface JobsResponse {
  jobs: Job[];
  total: number;
  limit: number;
  offset: number;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
}

export async function fetchJobs(limit = 20, offset = 0): Promise<JobsResponse> {
  const res = await fetch(`${API_BASE}/api/jobs?limit=${limit}&offset=${offset}`);
  if (!res.ok) throw new Error('Failed to fetch jobs');
  return res.json();
}

export async function fetchJob(jobId: string): Promise<JobDetail> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}`);
  if (!res.ok) throw new Error('Failed to fetch job');
  return res.json();
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/health`);
    return res.ok;
  } catch {
    return false;
  }
}

// Auth functions
export async function register(email: string, password: string, name: string): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, name })
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Registration failed');
  }
  const data = await res.json();
  localStorage.setItem('token', data.access_token);
  return data;
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Login failed');
  }
  const data = await res.json();
  localStorage.setItem('token', data.access_token);
  return data;
}

export function logout() {
  localStorage.removeItem('token');
}

export function getToken(): string | null {
  return localStorage.getItem('token');
}

export function isAuthenticated(): boolean {
  return !!getToken();
}
