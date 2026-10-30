'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { login, register } from '@/lib/api'
import { LoaderCircle } from 'lucide-react'

export default function AuthPage() {
  const router = useRouter()
  const [isLogin, setIsLogin] = useState(true)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [sessionExpired, setSessionExpired] = useState(false)

  useEffect(() => {
    setSessionExpired(new URLSearchParams(window.location.search).get('reason') === 'session-expired')
  }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      if (isLogin) {
        await login(email, password)
      } else {
        await register(email, password, name)
      }
      router.push('/feed')
    } catch (err: any) {
      const message = err.message || 'Authentication failed'
      setError(isLogin && message === 'Invalid email or password'
        ? "We couldn't find an account with those credentials. If you just created this account and this keeps happening, the account service may not be saving registrations. Please don't create a duplicate account."
        : message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="min-h-screen bg-[#000000] flex items-center justify-center px-6">
      <div className="max-w-md w-full">
        <div className="text-center mb-8">
          <a href="/" className="text-2xl font-semibold text-white">
            Kazi-Kasi
          </a>
        </div>

        <div className="p-8 rounded-md border border-[#1f1f1f] bg-[#0a0a0a]">
          <h1 className="text-2xl font-semibold mb-6 text-white">
            {isLogin ? 'Sign in' : 'Create account'}
          </h1>

          {sessionExpired && <div className="mb-5 rounded-md border border-[#333] bg-[#111] p-3 text-sm leading-5 text-[#bbb]" role="status">Your previous session could not be verified. Sign in with your existing account; you do not need to create another one.</div>}

          <form onSubmit={handleSubmit} className="space-y-4">
            {!isLogin && (
              <div>
                <label htmlFor="name" className="block text-sm text-[#a3a3a3] mb-2">Name</label>
                <input
                  id="name"
                  type="text"
                  autoComplete="name"
                  maxLength={100}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required={!isLogin}
                  className="w-full px-4 py-2.5 bg-[#000000] border border-[#1f1f1f] rounded-md text-sm focus:border-[#2f2f2f] focus:outline-none transition-all text-white"
                  placeholder="John Doe"
                />
              </div>
            )}

            <div>
              <label htmlFor="email" className="block text-sm text-[#a3a3a3] mb-2">Email</label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                maxLength={254}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-4 py-2.5 bg-[#000000] border border-[#1f1f1f] rounded-md text-sm focus:border-[#2f2f2f] focus:outline-none transition-all text-white"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm text-[#a3a3a3] mb-2">Password</label>
              <input
                id="password"
                type="password"
                autoComplete={isLogin ? 'current-password' : 'new-password'}
                maxLength={256}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={isLogin ? 1 : 10}
                className="w-full px-4 py-2.5 bg-[#000000] border border-[#1f1f1f] rounded-md text-sm focus:border-[#2f2f2f] focus:outline-none transition-all text-white"
                placeholder="••••••••"
              />
            </div>

            {error && (
              <div className="p-3 rounded-md bg-red-500/10 border border-red-500/30">
                <p className="text-sm text-red-400">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full px-5 py-2.5 bg-white text-black font-medium rounded-md hover:bg-[#ededed] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? <span className="inline-flex items-center gap-2"><LoaderCircle size={16} className="animate-soft-spin" />{isLogin ? 'Signing in' : 'Creating account'}</span> : isLogin ? 'Sign in' : 'Create account'}
            </button>
          </form>

          <div className="mt-6 text-center">
            <p className="text-sm text-[#737373]">
              {isLogin ? "Don't have an account?" : 'Already have an account?'}{' '}
              <button
                onClick={() => {
                  setIsLogin(!isLogin)
                  setError('')
                }}
                className="text-white hover:underline"
              >
                {isLogin ? 'Sign up' : 'Sign in'}
              </button>
            </p>
          </div>
        </div>
      </div>
    </main>
  )
}
