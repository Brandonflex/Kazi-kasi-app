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
<<<<<<< HEAD
    title: 'DevOps Engineer',
    company: 'Microsoft ADC',
    location: 'Nairobi, Kenya',
    status: 'wishlist',
    salary: 'KES 300K - 450K',
    url: 'https://careers.microsoft.com'
  },
  {
    id: '5',
=======
>>>>>>> f8b0e13 (Fix build errors: tsconfig path alias, tracker page syntax)
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
  { id: 'wishlist', label: 'Wishlist' },
  { id: 'applied', label: 'Applied' },
  { id: 'interview', label: 'Interview' },
  { id: 'offer', label: 'Offer' },
  { id: 'rejected', label: 'Rejected' },
  { id: 'hired', label: 'Hired' }
]

export default function TrackerPage() {
  const [applications] = useState<Application[]>(mockApplications)
  const [viewMode, setViewMode] = useState<'board' | 'list'>('board')

  const getColumnApps = (status: string) => 
    applications.filter(app => app.status === status)

  return (
    <main className="min-h-screen bg-[#000000]">
      {/* Header */}
      <header className="border-b border-[#1f1f1f] sticky top-0 z-10 bg-[#000000]/80 backdrop-blur-sm">
        <div className="max-w-[1800px] mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <a href="/" className="text-xl font-semibold text-white">
              Kazi-Kasi
            </a>
            <nav className="hidden md:flex gap-6">
              <a href="/feed" className="text-[#a3a3a3] hover:text-white transition-colors">Jobs</a>
              <a href="/tracker" className="text-white font-medium">Tracker</a>
              <a href="/profile" className="text-[#a3a3a3] hover:text-white transition-colors">Profile</a>
            </nav>
          </div>
          <div className="flex items-center gap-2">
            <button 
              onClick={() => setViewMode('board')}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
                viewMode === 'board' ? 'bg-white text-black' : 'text-[#a3a3a3] hover:text-white'
              }`}
            >
              Board
            </button>
            <button 
              onClick={() => setViewMode('list')}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
                viewMode === 'list' ? 'bg-white text-black' : 'text-[#a3a3a3] hover:text-white'
              }`}
            >
              List
            </button>
          </div>
        </div>
      </header>

      {/* Stats Overview */}
      <section className="border-b border-[#1f1f1f] bg-[#0a0a0a]">
        <div className="max-w-[1800px] mx-auto px-6 py-8">
          <div className="mb-6">
            <h2 className="text-2xl font-semibold mb-2 text-white">Application Tracker</h2>
            <p className="text-sm text-[#737373]">Track your job applications across all stages</p>
          </div>
          
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
            {statusColumns.map((col) => {
              const count = getColumnApps(col.id).length
              return (
                <div key={col.id} className="p-3 rounded-md border border-[#1f1f1f] bg-[#000000]">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-2xl font-semibold text-white">{count}</span>
                  </div>
                  <div className="text-xs text-[#737373] uppercase tracking-wide">{col.label}</div>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      {/* Kanban Board View */}
      {viewMode === 'board' && (
        <section className="max-w-[1800px] mx-auto px-6 py-8">
          <div className="grid grid-cols-1 md:grid-cols-6 gap-3">
            {statusColumns.map((col) => (
              <div key={col.id} className="flex flex-col">
                <div className="flex items-center justify-between mb-3 px-2">
                  <h3 className="font-medium text-sm text-white">
                    {col.label}
                  </h3>
                  <span className="text-xs text-[#737373]">
                    {getColumnApps(col.id).length}
                  </span>
                </div>
                
                <div className="space-y-2 min-h-[500px]">
                  {getColumnApps(col.id).map((app) => (
                    <a
                      key={app.id}
                      href={app.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block p-3 rounded-md border border-[#1f1f1f] bg-[#0a0a0a] hover:border-[#2f2f2f] transition-all"
                    >
                      <h4 className="font-medium text-sm mb-1.5 text-white">
                        {app.title}
                      </h4>
                      <p className="text-xs text-[#a3a3a3] mb-1.5">{app.company}</p>
                      <p className="text-xs text-[#737373] mb-2">{app.location}</p>
                      
                      {app.salary && (
                        <div className="text-xs text-white font-medium mb-2">{app.salary}</div>
                      )}
                      
                      {app.notes && (
                        <p className="text-xs text-[#737373] italic border-t border-[#1f1f1f] pt-2 mt-2">
                          {app.notes}
                        </p>
                      )}
                      
                      <div className="flex items-center justify-between text-xs text-[#737373] mt-2">
                        <span>{new Date(app.appliedDate).toLocaleDateString()}</span>
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
        <section className="max-w-5xl mx-auto px-6 py-8">
          <div className="space-y-2">
            {applications.map((app) => (
              <a
                key={app.id}
                href={app.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block p-5 rounded-md border border-[#1f1f1f] bg-[#0a0a0a] hover:border-[#2f2f2f] transition-all"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex-1">
                    <h3 className="text-lg font-medium mb-1.5 text-white">
                      {app.title}
                    </h3>
                    <div className="flex items-center gap-2 text-sm text-[#a3a3a3]">
                      <span className="font-medium text-[#ededed]">{app.company}</span>
                      <span className="text-[#1f1f1f]">•</span>
                      <span>{app.location}</span>
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1.5">
                    <span className="px-2.5 py-1 rounded text-xs font-medium border border-[#1f1f1f] text-[#a3a3a3]">
                      {app.status.charAt(0).toUpperCase() + app.status.slice(1)}
                    </span>
                    {app.salary && (
                      <span className="text-sm text-white font-medium">{app.salary}</span>
                    )}
                  </div>
                </div>
                
                {app.notes && (
                  <p className="text-sm text-[#737373] italic mb-2">{app.notes}</p>
                )}
                
                <div className="flex items-center justify-between text-xs text-[#737373]">
                  <span>Applied {new Date(app.appliedDate).toLocaleDateString()}</span>
                  <span>View on company site</span>
                </div>
              </a>
            ))}
          </div>
        </section>
      )}
    </main>
  )
}
