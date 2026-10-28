'use client'

import { useState } from 'react'

interface Application {
  id: string
  title: string
  company: string
  location: string
  status: 'wishlist' | 'applied' | 'interview' | 'offer' | 'rejected' | 'hired'
  appliedDate: string
  salary?: string
  url: string
  notes?: string
}

const mockApplications: Application[] = [
  {
    id: '1',
    title: 'Senior Software Engineer',
    company: 'Safaricom PLC',
    location: 'Nairobi, Kenya',
    status: 'interview',
    appliedDate: '2024-01-15',
    salary: 'KES 250K - 350K',
    url: 'https://careers.safaricom.co.ke',
    notes: 'Second round scheduled for Friday'
  },
  {
    id: '2',
    title: 'Full Stack Developer',
    company: 'Andela',
    location: 'Remote - Kenya',
    status: 'applied',
    appliedDate: '2024-01-18',
    salary: 'KES 180K - 280K',
    url: 'https://andela.com/careers'
  },
  {
    id: '3',
    title: 'Backend Engineer',
    company: 'Cellulant',
    location: 'Nairobi, Kenya',
    status: 'applied',
    appliedDate: '2024-01-20',
    salary: 'KES 200K - 300K',
    url: 'https://www.cellulant.com/careers'
  },
  {
    id: '4',
    title: 'DevOps Engineer',
    company: 'Microsoft ADC',
    location: 'Nairobi, Kenya',
    status: 'wishlist',
    salary: 'KES 300K - 450K',
    url: 'https://careers.microsoft.com'
  },
  {
    id: '5',
    title: 'Platform Engineer',
    company: 'Twiga Foods',
    location: 'Nairobi, Kenya',
    status: 'offer',
    appliedDate: '2024-01-10',
    salary: 'KES 280K - 380K',
    url: 'https://twigafoods.com/careers'
  }
]

const statusColumns = [
  { id: 'wishlist', label: 'Wishlist', color: '#a0a0a0' },
  { id: 'applied', label: 'Applied', color: '#1e90ff' },
  { id: 'interview', label: 'Interview', color: '#E9A23B' },
  { id: 'offer', label: 'Offer', color: '#2dd4a8' },
  { id: 'rejected', label: 'Rejected', color: '#666' },
  { id: 'hired', label: 'Hired', color: '#2dd4a8' }
]

export default function TrackerPage() {
  const [applications] = useState<Application[]>(mockApplications)
  const [viewMode, setViewMode] = useState<'board' | 'list'>('board')

  const getColumnApps = (status: string) => 
    applications.filter(app => app.status === status)

  return (
    <main className="min-h-screen bg-[#0a0a0a]">
      {/* Header */}
      <header className="border-b border-[#2a2a2a] bg-[#111111] sticky top-0 z-10">
        <div className="max-w-[1800px] mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <a href="/" className="font-display text-2xl font-bold">
              Kazi<span className="text-[#E9A23B]">-Kasi</span>
            </a>
            <nav className="hidden md:flex gap-6">
              <a href="/feed" className="text-[#a0a0a0] hover:text-[#f5f5f5] transition-colors">Feed</a>
              <a href="/tracker" className="text-[#E9A23B] font-medium">Tracker</a>
              <a href="/profile" className="text-[#a0a0a0] hover:text-[#f5f5f5] transition-colors">Profile</a>
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <button 
              onClick={() => setViewMode('board')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                viewMode === 'board' ? 'bg-[#E9A23B] text-[#0a0a0a]' : 'border border-[#2a2a2a] text-[#a0a0a0]'
              }`}
            >
              Board
            </button>
            <button 
              onClick={() => setViewMode('list')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                viewMode === 'list' ? 'bg-[#E9A23B] text-[#0a0a0a]' : 'border border-[#2a2a2a] text-[#a0a0a0]'
              }`}
            >
              List
            </button>
          </div>
        </div>
      </header>

      {/* Stats Overview */}
      <section className="border-b border-[#2a2a2a] bg-gradient-to-br from-[#111111] via-[#111111] to-[#0a0a0a]">
        <div className="max-w-[1800px] mx-auto px-6 py-8">
          <div className="mb-6">
            <h2 className="font-display text-4xl font-bold mb-2">Application Tracker</h2>
            <p className="text-[#a0a0a0]">Track your job applications across all stages</p>
          </div>
          
          <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
            {statusColumns.map((col) => {
              const count = getColumnApps(col.id).length
              return (
                <div key={col.id} className="p-4 rounded-lg border border-[#2a2a2a] bg-[#111111]">
                  <div className="flex items-center justify-between mb-2">
                    <div className="w-2 h-2 rounded-full" style={{ background: col.color }} />
                    <span className="font-display text-2xl font-bold" style={{ color: col.color }}>{count}</span>
                  </div>
                  <div className="text-xs text-[#a0a0a0] uppercase tracking-wider">{col.label}</div>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      {/* Kanban Board View */}
      {viewMode === 'board' && (
        <section className="max-w-[1800px] mx-auto px-6 py-8">
          <div className="grid grid-cols-1 md:grid-cols-6 gap-4">
            {statusColumns.map((col) => (
              <div key={col.id} className="flex flex-col">
                <div className="flex items-center justify-between mb-4 px-2">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full" style={{ background: col.color }} />
                    <h3 className="font-semibold text-sm uppercase tracking-wider" style={{ color: col.color }}>
                      {col.label}
                    </h3>
                  </div>
                  <span className="text-xs text-[#a0a0a0] bg-[#111111] px-2 py-1 rounded">
                    {getColumnApps(col.id).length}
                  </span>
                </div>
                
                <div className="space-y-3 min-h-[500px]">
                  {getColumnApps(col.id).map((app) => (
                    <a
                      key={app.id}
                      href={app.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block p-4 rounded-lg border border-[#2a2a2a] bg-[#111111] hover:border-[#E9A23B]/50 hover:bg-[#1a1a1a] transition-all group"
                    >
                      <h4 className="font-semibold text-sm mb-2 group-hover:text-[#E9A23B] transition-colors">
                        {app.title}
                      </h4>
                      <p className="text-xs text-[#a0a0a0] mb-2">{app.company}</p>
                      <p className="text-xs text-[#a0a0a0] mb-3">{app.location}</p>
                      
                      {app.salary && (
                        <div className="text-xs text-[#2dd4a8] font-semibold mb-2">{app.salary}</div>
                      )}
                      
                      {app.notes && (
                        <p className="text-xs text-[#a0a0a0] italic border-t border-[#2a2a2a] pt-2 mt-2">
                          {app.notes}
                        </p>
                      )}
                      
                      <div className="flex items-center justify-between text-xs text-[#a0a0a0] mt-2">
                        <span>{new Date(app.appliedDate).toLocaleDateString()}</span>
                        <svg className="w-3 h-3 group-hover:text-[#E9A23B] transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                        </svg>
                      </div>
                    </a>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* List View */}
      {viewMode === 'list' && (
        <section className="max-w-7xl mx-auto px-6 py-8">
          <div className="space-y-3">
            {applications.map((app) => (
              <a
                key={app.id}
                href={app.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block p-6 rounded-xl border border-[#2a2a2a] bg-[#111111] hover:border-[#E9A23B]/50 hover:bg-[#1a1a1a] transition-all group"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1">
                    <h3 className="font-display text-xl font-semibold mb-2 group-hover:text-[#E9A23B] transition-colors">
                      {app.title}
                    </h3>
                    <div className="flex items-center gap-4 text-sm text-[#a0a0a0]">
                      <span>{app.company}</span>
                      <span className="text-[#2a2a2a]">|</span>
                      <span>{app.location}</span>
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <span 
                      className="px-3 py-1 rounded-full text-xs font-semibold border"
                      style={{
                        background: `${statusColumns.find(s => s.id === app.status)?.color}20`,
                        color: statusColumns.find(s => s.id === app.status)?.color,
                        borderColor: `${statusColumns.find(s => s.id === app.status)?.color}30`
                      }}
                    >
                      {app.status.charAt(0).toUpperCase() + app.status.slice(1)}
                    </span>
                    {app.salary && (
                      <span className="text-sm text-[#2dd4a8] font-semibold">{app.salary}</span>
                    )}
                  </div>
                </div>
                
                {app.notes && (
                  <p className="text-sm text-[#a0a0a0] italic mb-3">{app.notes}</p>
                )}
                
                <div className="flex items-center justify-between text-xs text-[#a0a0a0]">
                  <span>Applied {new Date(app.appliedDate).toLocaleDateString()}</span>
                  <span className="flex items-center gap-2 group-hover:text-[#E9A23B] transition-colors">
                    View on company site
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                  </span>
                </div>
              </a>
            ))}
          </div>
        </section>
      )}
    </main>
  )
}
