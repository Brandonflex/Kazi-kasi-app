'use client'

import { useState } from 'react'

interface Job {
  id: string
  title: string
  company: string
  location: string
  type: string
  salary: string
  posted: string
  match_score: number
  why_match: string
  url: string
  tags: string[]
  remote: boolean
  urgent: boolean
  logo?: string
}

const mockJobs: Job[] = [
  {
    id: '1',
    title: 'Senior Software Engineer',
    company: 'Safaricom PLC',
    location: 'Nairobi, Kenya',
    type: 'Full-time',
    salary: 'KES 250K - 350K',
    posted: '2 days ago',
    match_score: 94,
    why_match: 'Strong match: Python, FastAPI, cloud infrastructure',
    url: '/feed/1',
    tags: ['Python', 'FastAPI', 'Cloud'],
    remote: false,
    urgent: true,
    logo: 'S'
  },
  {
    id: '2',
    title: 'Full Stack Developer',
    company: 'Andela',
    location: 'Remote - Kenya',
    type: 'Full-time',
    salary: 'KES 180K - 280K',
    posted: '5 days ago',
    match_score: 89,
    why_match: 'Full stack experience, React/Node.js stack',
    url: '/feed/1',
    tags: ['React', 'Node.js', 'Full Stack'],
    remote: true,
    urgent: false,
    logo: 'A'
  },
  {
    id: '3',
    title: 'Backend Engineer',
    company: 'Cellulant',
    location: 'Nairobi, Kenya',
    type: 'Full-time',
    salary: 'KES 200K - 300K',
    posted: '1 day ago',
    match_score: 87,
    why_match: 'API development, database design experience',
    url: '/feed/1',
    tags: ['Backend', 'APIs', 'PostgreSQL'],
    remote: false,
    urgent: true,
    logo: 'C'
  },
  {
    id: '4',
    title: 'Platform Engineer',
    company: 'Microsoft ADC',
    location: 'Nairobi, Kenya',
    type: 'Full-time',
    salary: 'KES 300K - 450K',
    posted: '3 days ago',
    match_score: 82,
    why_match: 'Cloud infrastructure, DevOps experience',
    url: '/feed/1',
    tags: ['Azure', 'Kubernetes', 'DevOps'],
    remote: false,
    urgent: false,
    logo: 'M'
  }
]

export default function FeedPage() {
  const [sortBy, setSortBy] = useState('match')
  const [filterRemote, setFilterRemote] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  const filteredJobs = mockJobs.filter(job => {
    if (filterRemote && !job.remote) return false
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      return (
        job.title.toLowerCase().includes(query) ||
        job.company.toLowerCase().includes(query) ||
        job.tags.some(tag => tag.toLowerCase().includes(query))
      )
    }
    return true
  })

  const sortedJobs = [...filteredJobs].sort((a, b) => {
    if (sortBy === 'match') return b.match_score - a.match_score
    if (sortBy === 'recent') return 1
    return 0
  })

  return (
    <main className="min-h-screen bg-[#0a0a0a]">
      {/* Header */}
      <header className="border-b border-[#2a2a2a] bg-[#111111] sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <a href="/" className="font-display text-2xl font-bold">
              Kazi<span className="text-[#E9A23B]">-Kasi</span>
            </a>
            <nav className="hidden md:flex gap-6">
              <a href="/feed" className="text-[#E9A23B] font-medium">Feed</a>
              <a href="/tracker" className="text-[#a0a0a0] hover:text-[#f5f5f5] transition-colors">Tracker</a>
              <a href="/profile" className="text-[#a0a0a0] hover:text-[#f5f5f5] transition-colors">Profile</a>
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <button className="px-4 py-2 border border-[#2a2a2a] hover:border-[#E9A23B]/50 rounded-lg transition-all text-sm">
              Upload CV
            </button>
            <button className="w-10 h-10 rounded-full bg-[#E9A23B]/20 flex items-center justify-center hover:bg-[#E9A23B]/30 transition-all">
              <span className="text-[#E9A23B] font-semibold text-sm">JD</span>
            </button>
          </div>
        </div>
      </header>

      {/* Search & Filters */}
      <section className="border-b border-[#2a2a2a] bg-[#111111]">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex flex-col md:flex-row gap-4 mb-4">
            {/* Search Bar */}
            <div className="flex-1 relative">
              <svg className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-[#a0a0a0]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by title, company, or skill..."
                className="w-full pl-12 pr-4 py-3 bg-[#0a0a0a] border border-[#2a2a2a] rounded-lg focus:border-[#E9A23B]/50 focus:outline-none transition-all"
              />
            </div>
            
            {/* Sort & Filter Controls */}
            <div className="flex gap-3">
              <select 
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="px-4 py-3 bg-[#0a0a0a] border border-[#2a2a2a] rounded-lg text-sm focus:border-[#E9A23B]/50 focus:outline-none transition-all"
              >
                <option value="match">Best Match</option>
                <option value="recent">Most Recent</option>
                <option value="closing">Closing Soon</option>
              </select>
              
              <button
                onClick={() => setFilterRemote(!filterRemote)}
                className={`px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                  filterRemote 
                    ? 'bg-[#E9A23B] text-[#0a0a0a]' 
                    : 'bg-[#0a0a0a] border border-[#2a2a2a] text-[#a0a0a0] hover:border-[#E9A23B]/50'
                }`}
              >
                Remote Only
              </button>
            </div>
          </div>
          
          <div className="flex items-center justify-between text-sm">
            <p className="text-[#a0a0a0]">
              <span className="font-semibold text-[#f5f5f5]">{sortedJobs.length}</span> jobs matched to your profile
            </p>
            <div className="flex items-center gap-2 text-[#a0a0a0]">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              <span>Updated just now</span>
            </div>
          </div>
        </div>
      </section>

      {/* Job List */}
      <section className="max-w-7xl mx-auto px-6 py-8">
        <div className="space-y-3">
          {sortedJobs.map((job) => (
            <a
              key={job.id}
              href={job.url}
              className="block p-6 rounded-xl border border-[#2a2a2a] bg-[#111111] hover:border-[#E9A23B]/50 hover:bg-[#1a1a1a] transition-all group"
            >
              <div className="flex items-start gap-4">
                {/* Company Logo */}
                <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-[#E9A23B]/20 to-[#E9A23B]/5 flex items-center justify-center flex-shrink-0 border border-[#E9A23B]/20">
                  <span className="text-[#E9A23B] font-bold text-lg">{job.logo}</span>
                </div>
                
                {/* Job Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-display text-lg font-semibold group-hover:text-[#E9A23B] transition-colors">
                          {job.title}
                        </h3>
                        {job.urgent && (
                          <span className="px-2 py-0.5 text-xs font-semibold bg-red-500/20 text-red-400 rounded">
                            URGENT
                          </span>
                        )}
                        {job.remote && (
                          <span className="px-2 py-0.5 text-xs font-semibold bg-[#2dd4a8]/20 text-[#2dd4a8] rounded">
                            REMOTE
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 text-sm text-[#a0a0a0]">
                        <span className="font-medium text-[#f5f5f5]">{job.company}</span>
                        <span className="text-[#2a2a2a]">•</span>
                        <span>{job.location}</span>
                        <span className="text-[#2a2a2a]">•</span>
                        <span>{job.type}</span>
                      </div>
                    </div>
                    
                    {/* Match Score & Salary */}
                    <div className="text-right flex-shrink-0 ml-4">
                      <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#E9A23B]/10 border border-[#E9A23B]/30 mb-2">
                        <span className="text-sm font-bold text-[#E9A23B]">{job.match_score}%</span>
                        <span className="text-xs text-[#a0a0a0]">match</span>
                      </div>
                      <div className="text-sm font-semibold text-[#2dd4a8]">{job.salary}</div>
                      <div className="text-xs text-[#a0a0a0] mt-1">{job.posted}</div>
                    </div>
                  </div>
                  
                  {/* Match Reason */}
                  <p className="text-sm text-[#a0a0a0] mb-3">
                    <span className="font-medium text-[#E9A23B]">Why it matches:</span> {job.why_match}
                  </p>
                  
                  {/* Tags */}
                  <div className="flex items-center gap-2 flex-wrap">
                    {job.tags.map((tag) => (
                      <span key={tag} className="px-3 py-1 text-xs rounded-full border border-[#2a2a2a] bg-[#0a0a0a] text-[#a0a0a0]">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </a>
          ))}
        </div>
        
        {sortedJobs.length === 0 && (
          <div className="text-center py-16">
            <svg className="w-16 h-16 text-[#2a2a2a] mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-[#a0a0a0]">No jobs match your filters</p>
          </div>
        )}
      </section>
    </main>
  )
}
