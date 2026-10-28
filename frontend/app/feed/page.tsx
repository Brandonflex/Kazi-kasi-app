'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { fetchJobs, type Job, isAuthenticated } from '@/lib/api'

export default function FeedPage() {
  const router = useRouter()
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [sortBy, setSortBy] = useState('match')
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push('/auth')
      return
    }
    loadJobs()
  }, [router])

  async function loadJobs() {
    try {
      setLoading(true)
      const data = await fetchJobs(50)
      setJobs(data.jobs)
    } catch (error) {
      console.error('Failed to load jobs:', error)
    } finally {
      setLoading(false)
    }
  }

  const filteredJobs = jobs.filter(job => {
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      return (
        job.title.toLowerCase().includes(query) ||
        job.employer.toLowerCase().includes(query) ||
        job.match_reasons.some(reason => reason.toLowerCase().includes(query))
      )
    }
    return true
  })

  const sortedJobs = [...filteredJobs].sort((a, b) => {
    if (sortBy === 'match') return b.match_score - a.match_score
    return 0
  })

  return (
    <main className="min-h-screen bg-[#000000]">
      {/* Header */}
      <header className="border-b border-[#1f1f1f] sticky top-0 z-10 bg-[#000000]/80 backdrop-blur-sm">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <a href="/" className="text-xl font-semibold text-white">
              Kazi-Kasi
            </a>
            <nav className="hidden md:flex gap-6">
              <a href="/feed" className="text-white font-medium">Jobs</a>
              <a href="/tracker" className="text-[#a3a3a3] hover:text-white transition-colors">Tracker</a>
              <a href="/profile" className="text-[#a3a3a3] hover:text-white transition-colors">Profile</a>
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <button className="w-9 h-9 rounded-full bg-[#0a0a0a] border border-[#1f1f1f] flex items-center justify-center hover:border-[#2f2f2f] transition-all">
              <span className="text-[#a3a3a3] font-medium text-sm">JD</span>
            </button>
          </div>
        </div>
      </header>

      {/* Search & Filters */}
      <section className="border-b border-[#1f1f1f] bg-[#0a0a0a]">
        <div className="max-w-5xl mx-auto px-6 py-6">
          <div className="flex flex-col md:flex-row gap-3 mb-4">
            {/* Search Bar */}
            <div className="flex-1 relative">
              <svg className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#737373]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search jobs..."
                className="w-full pl-11 pr-4 py-2.5 bg-[#000000] border border-[#1f1f1f] rounded-md text-sm focus:border-[#2f2f2f] focus:outline-none transition-all text-white placeholder:text-[#737373]"
              />
            </div>
            
            {/* Sort Controls */}
            <div className="flex gap-2">
              <select 
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="px-4 py-2.5 bg-[#000000] border border-[#1f1f1f] rounded-md text-sm focus:border-[#2f2f2f] focus:outline-none transition-all text-[#a3a3a3]"
              >
                <option value="match">Best Match</option>
                <option value="recent">Recent</option>
                <option value="closing">Closing Soon</option>
              </select>
            </div>
          </div>
          
          <div className="flex items-center justify-between text-sm">
            <p className="text-[#737373]">
              <span className="font-medium text-white">{sortedJobs.length}</span> jobs
            </p>
          </div>
        </div>
      </section>

      {/* Job List */}
      <section className="max-w-5xl mx-auto px-6 py-8">
        {loading ? (
          <div className="text-center py-20">
            <p className="text-[#737373]">Loading jobs...</p>
          </div>
        ) : (
          <div className="space-y-2">
            {sortedJobs.map((job) => (
              <a
                key={job.id}
                href={`/feed/${job.id}`}
                className="block p-5 rounded-md border border-[#1f1f1f] bg-[#0a0a0a] hover:border-[#2f2f2f] transition-all group"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1.5">
                      <h3 className="text-lg font-medium text-white group-hover:text-white">
                        {job.title}
                      </h3>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-[#a3a3a3]">
                      <span className="font-medium text-[#ededed]">{job.employer}</span>
                      <span className="text-[#1f1f1f]">•</span>
                      <span>{job.location}</span>
                    </div>
                  </div>
                  
                  {/* Match Score & Salary */}
                  <div className="text-right flex-shrink-0 ml-4">
                    <div className="text-sm font-medium text-white mb-1">{Math.round(job.match_score * 100)}%</div>
                    {job.salary_min && job.salary_max && (
                      <div className="text-sm text-[#a3a3a3]">
                        KES {job.salary_min.toLocaleString()} - {job.salary_max.toLocaleString()}
                      </div>
                    )}
                    <div className="text-xs text-[#737373] mt-1">{job.posted || 'Recently posted'}</div>
                  </div>
                </div>
                
                {/* Match Reasons */}
                {job.match_reasons.length > 0 && (
                  <p className="text-sm text-[#a3a3a3] mb-3">
                    {job.match_reasons.join(' • ')}
                  </p>
                )}
              </a>
            ))}
          </div>
        )}
        
        {!loading && sortedJobs.length === 0 && (
          <div className="text-center py-20">
            <p className="text-[#737373]">No jobs match your search</p>
          </div>
        )}
      </section>
    </main>
  )
}
