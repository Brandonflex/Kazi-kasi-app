'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { login, register } from '@/lib/api'

export default function AuthPage() {
  const router = useRouter()
  const [isLogin, setIsLogin] = useState(true)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

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
      setError(err.message || 'Authentication failed')
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

          <form onSubmit={handleSubmit} className="space-y-4">
            {!isLogin && (
              <div>
                <label className="block text-sm text-[#a3a3a3] mb-2">Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required={!isLogin}
                  className="w-full px-4 py-2.5 bg-[#000000] border border-[#1f1f1f] rounded-md text-sm focus:border-[#2f2f2f] focus:outline-none transition-all text-white"
                  placeholder="John Doe"
                />
              </div>
            )}

            <div>
              <label className="block text-sm text-[#a3a3a3] mb-2">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-4 py-2.5 bg-[#000000] border border-[#1f1f1f] rounded-md text-sm focus:border-[#2f2f2f] focus:outline-none transition-all text-white"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label className="block text-sm text-[#a3a3a3] mb-2">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
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
              {loading ? 'Please wait...' : isLogin ? 'Sign in' : 'Create account'}
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
