'use client'

import { useState } from 'react'

export default function ProfilePage() {
  const [cvUploaded, setCvUploaded] = useState(false)
  const [activeTab, setActiveTab] = useState('overview')

  const skills = ['Python', 'FastAPI', 'React', 'PostgreSQL', 'AWS', 'Docker', 'Git', 'TypeScript', 'Node.js', 'REST APIs']
  const experience = [
    { role: 'Software Engineer', company: 'TechCorp Kenya', duration: '2 years', location: 'Nairobi' },
    { role: 'Junior Developer', company: 'StartupHub', duration: '1 year', location: 'Remote' }
  ]

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
              <a href="/feed" className="text-[#a0a0a0] hover:text-[#f5f5f5] transition-colors">Feed</a>
              <a href="/tracker" className="text-[#a0a0a0] hover:text-[#f5f5f5] transition-colors">Tracker</a>
              <a href="/profile" className="text-[#E9A23B] font-medium">Profile</a>
            </nav>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Profile Header Card */}
        <div className="p-8 rounded-xl border border-[#2a2a2a] bg-[#111111] mb-6">
          <div className="flex items-start gap-6 mb-6">
            <div className="w-24 h-24 rounded-full bg-gradient-to-br from-[#E9A23B]/30 to-[#E9A23B]/10 flex items-center justify-center border-2 border-[#E9A23B]/30">
              <span className="text-[#E9A23B] font-bold text-3xl">JD</span>
            </div>
            <div className="flex-1">
              <h1 className="font-display text-3xl font-bold mb-2">John Doe</h1>
              <p className="text-[#a0a0a0] mb-3">Software Engineer • Nairobi, Kenya</p>
              <div className="flex items-center gap-4 text-sm">
                <span className="px-3 py-1 rounded-full bg-[#2dd4a8]/20 text-[#2dd4a8] text-xs font-semibold">
                  Profile 78% Complete
                </span>
                <span className="text-[#a0a0a0]">Last updated 2 days ago</span>
              </div>
            </div>
          </div>
          
          <div className="flex gap-3">
            <button className="px-6 py-2 bg-[#E9A23B] hover:bg-[#E9A23B]/90 text-[#0a0a0a] font-semibold rounded-lg transition-all text-sm">
              Edit Profile
            </button>
            <button className="px-6 py-2 border border-[#2a2a2a] hover:border-[#E9A23B]/50 rounded-lg transition-all text-sm">
              View Public Profile
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-6 border-b border-[#2a2a2a]">
          {['overview', 'experience', 'skills', 'preferences'].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-6 py-3 text-sm font-medium transition-all border-b-2 ${
                activeTab === tab
                  ? 'text-[#E9A23B] border-[#E9A23B]'
                  : 'text-[#a0a0a0] border-transparent hover:text-[#f5f5f5]'
              }`}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        {activeTab === 'overview' && (
          <div className="grid md:grid-cols-3 gap-6">
            {/* CV Upload */}
            <div className="md:col-span-2 p-6 rounded-xl border border-[#2a2a2a] bg-[#111111]">
              <h2 className="font-display text-xl font-bold mb-4">CV / Resume</h2>
              
              {!cvUploaded ? (
                <div className="border-2 border-dashed border-[#2a2a2a] rounded-lg p-8 text-center hover:border-[#E9A23B]/50 transition-all">
                  <svg className="w-12 h-12 text-[#a0a0a0] mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                  <p className="text-[#a0a0a0] mb-2">Upload your CV to improve matching</p>
                  <p className="text-sm text-[#a0a0a0]/60 mb-4">PDF format, up to 5MB</p>
                  <button 
                    onClick={() => setCvUploaded(true)}
                    className="px-6 py-2 bg-[#E9A23B] hover:bg-[#E9A23B]/90 text-[#0a0a0a] font-semibold rounded-lg transition-all"
                  >
                    Upload CV
                  </button>
                </div>
              ) : (
                <div className="border border-[#2dd4a8]/30 bg-[#2dd4a8]/5 rounded-lg p-4">
                  <div className="flex items-center gap-4">
                    <svg className="w-10 h-10 text-[#2dd4a8]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <div className="flex-1">
                      <p className="font-semibold text-[#2dd4a8]">CV uploaded</p>
                      <p className="text-sm text-[#a0a0a0]">your_cv.pdf • 2.3MB • 12 skills extracted</p>
                    </div>
                    <button 
                      onClick={() => setCvUploaded(false)}
                      className="px-4 py-2 border border-[#2a2a2a] hover:border-[#E9A23B]/50 rounded-lg text-sm transition-all"
                    >
                      Replace
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Quick Stats */}
            <div className="p-6 rounded-xl border border-[#2a2a2a] bg-[#111111]">
              <h2 className="font-display text-xl font-bold mb-4">Activity</h2>
              <div className="space-y-4">
                <div>
                  <div className="text-2xl font-bold text-[#E9A23B] mb-1">12</div>
                  <div className="text-sm text-[#a0a0a0]">Jobs Applied</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-[#2dd4a8] mb-1">3</div>
                  <div className="text-sm text-[#a0a0a0]">Interviews</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-[#1e90ff] mb-1">284</div>
                  <div className="text-sm text-[#a0a0a0]">Matching Jobs</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'experience' && (
          <div className="p-6 rounded-xl border border-[#2a2a2a] bg-[#111111]">
            <div className="flex items-center justify-between mb-6">
              <h2 className="font-display text-xl font-bold">Work Experience</h2>
              <button className="px-4 py-2 bg-[#E9A23B] hover:bg-[#E9A23B]/90 text-[#0a0a0a] font-semibold rounded-lg transition-all text-sm">
                Add Experience
              </button>
            </div>
            
            <div className="space-y-4">
              {experience.map((exp, i) => (
                <div key={i} className="p-4 rounded-lg border border-[#2a2a2a] bg-[#0a0a0a]">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <h3 className="font-semibold text-[#f5f5f5]">{exp.role}</h3>
                      <p className="text-sm text-[#E9A23B]">{exp.company}</p>
                    </div>
                    <span className="text-sm text-[#a0a0a0]">{exp.duration}</span>
                  </div>
                  <p className="text-sm text-[#a0a0a0]">{exp.location}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'skills' && (
          <div className="p-6 rounded-xl border border-[#2a2a2a] bg-[#111111]">
            <h2 className="font-display text-xl font-bold mb-6">Your Skills</h2>
            <div className="flex flex-wrap gap-3 mb-6">
              {skills.map((skill) => (
                <span key={skill} className="px-4 py-2 rounded-full border border-[#2a2a2a] bg-[#0a0a0a] text-[#f5f5f5] text-sm hover:border-[#E9A23B]/50 transition-all cursor-pointer">
                  {skill}
                </span>
              ))}
            </div>
            <button className="px-4 py-2 border border-[#2a2a2a] hover:border-[#E9A23B]/50 rounded-lg text-sm transition-all">
              + Add Skill
            </button>
          </div>
        )}

        {activeTab === 'preferences' && (
          <div className="p-6 rounded-xl border border-[#2a2a2a] bg-[#111111]">
            <h2 className="font-display text-xl font-bold mb-6">Job Preferences</h2>
            
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-[#a0a0a0] mb-2">Location Preference</label>
                <input
                  type="text"
                  defaultValue="Nairobi, Kenya (Remote OK)"
                  className="w-full px-4 py-2 bg-[#0a0a0a] border border-[#2a2a2a] rounded-lg focus:border-[#E9A23B]/50 focus:outline-none"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-[#a0a0a0] mb-2">Minimum Salary (KES/month)</label>
                <input
                  type="text"
                  defaultValue="150,000"
                  className="w-full px-4 py-2 bg-[#0a0a0a] border border-[#2a2a2a] rounded-lg focus:border-[#E9A23B]/50 focus:outline-none"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-[#a0a0a0] mb-2">Job Type</label>
                <div className="flex gap-3">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" defaultChecked className="w-4 h-4 accent-[#E9A23B]" />
                    <span className="text-[#f5f5f5]">Full-time</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" className="w-4 h-4 accent-[#E9A23B]" />
                    <span className="text-[#f5f5f5]">Contract</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" defaultChecked className="w-4 h-4 accent-[#E9A23B]" />
                    <span className="text-[#f5f5f5]">Remote</span>
                  </label>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  )
}
