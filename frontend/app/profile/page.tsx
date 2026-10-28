'use client'

import { useState } from 'react'

export default function ProfilePage() {
  const [cvFile, setCvFile] = useState<File | null>(null)
  const [cvError, setCvError] = useState('')
  const [activeTab, setActiveTab] = useState('overview')

  const skills = ['Python', 'FastAPI', 'React', 'PostgreSQL', 'AWS', 'Docker', 'Git', 'TypeScript', 'Node.js', 'REST APIs']
  const experience = [
    { role: 'Software Engineer', company: 'TechCorp Kenya', duration: '2 years', location: 'Nairobi' },
    { role: 'Junior Developer', company: 'StartupHub', duration: '1 year', location: 'Remote' }
  ]

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
              <a href="/feed" className="text-[#a3a3a3] hover:text-white transition-colors">Jobs</a>
              <a href="/tracker" className="text-[#a3a3a3] hover:text-white transition-colors">Tracker</a>
              <a href="/profile" className="text-white font-medium">Profile</a>
            </nav>
          </div>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-6 py-10">
        {/* Profile Header */}
        <div className="flex items-start gap-5 mb-10">
          <div className="w-20 h-20 rounded-full bg-[#0a0a0a] border border-[#1f1f1f] flex items-center justify-center flex-shrink-0">
            <span className="text-[#a3a3a3] font-medium text-2xl">JS</span>
          </div>
          <div className="flex-1">
            <h1 className="text-2xl font-semibold mb-1.5 text-white">Your profile</h1>
            <p className="text-sm text-[#a3a3a3] mb-2">Add your role and preferred location to personalize matches.</p>
            <div className="flex items-center gap-3 text-sm">
              <span className="px-2.5 py-1 rounded border border-[#1f1f1f] text-[#a3a3a3] text-xs">
                Profile preview
              </span>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-8 border-b border-[#1f1f1f]">
          {['overview', 'experience', 'skills', 'preferences'].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2.5 text-sm font-medium transition-all border-b-2 ${
                activeTab === tab
                  ? 'text-white border-white'
                  : 'text-[#737373] border-transparent hover:text-white'
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
            <div className="md:col-span-2 p-6 rounded-md border border-[#1f1f1f] bg-[#0a0a0a]">
              <h2 className="text-lg font-semibold mb-4 text-white">CV / Resume</h2>
              
              <input
                id="cv-upload"
                type="file"
                accept="application/pdf,.pdf"
                className="sr-only"
                onChange={(event) => {
                  const file = event.target.files?.[0]
                  setCvError('')
                  if (!file) return
                  if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
                    setCvError('Choose a PDF file to continue.')
                    event.target.value = ''
                    return
                  }
                  if (file.size > 5 * 1024 * 1024) {
                    setCvError('That PDF is larger than 5 MB. Choose a smaller file.')
                    event.target.value = ''
                    return
                  }
                  setCvFile(file)
                }}
              />
              <div className="border border-dashed border-[#2f2f2f] rounded-md p-8 text-center">
                <p className="text-[#a3a3a3] mb-1.5 text-sm">Choose a CV PDF to improve matching</p>
                <p className="text-xs text-[#737373] mb-4">PDF format, up to 5 MB. File stays on this device.</p>
                <label
                  htmlFor="cv-upload"
                  className="inline-block cursor-pointer px-4 py-2 bg-white text-black text-sm font-medium rounded-md hover:bg-[#ededed] transition-colors"
                >
                  {cvFile ? 'Choose another PDF' : 'Choose PDF'}
                </label>
                {cvFile && <p className="mt-4 text-sm text-white" aria-live="polite">Selected: {cvFile.name} · {(cvFile.size / (1024 * 1024)).toFixed(2)} MB</p>}
                {cvError && <p className="mt-3 text-sm text-red-400" role="alert">{cvError}</p>}
                <p className="mt-3 text-xs text-[#737373]">CV upload and extraction are not connected yet.</p>
              </div>
            </div>

            {/* Quick Stats */}
            <div className="p-6 rounded-md border border-[#1f1f1f] bg-[#0a0a0a]">
              <h2 className="text-lg font-semibold mb-4 text-white">Activity</h2>
              <div className="space-y-4">
                <div>
                  <div className="text-2xl font-semibold text-white mb-1">—</div>
                  <div className="text-xs text-[#737373]">Application data not connected</div>
                </div>
                <div>
                  <div className="text-2xl font-semibold text-white mb-1">—</div>
                  <div className="text-xs text-[#737373]">Interview data not connected</div>
                </div>
                <div>
                  <div className="text-2xl font-semibold text-white mb-1">—</div>
                  <div className="text-xs text-[#737373]">Connect the job feed to see matches</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'experience' && (
          <div className="p-6 rounded-md border border-[#1f1f1f] bg-[#0a0a0a]">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-white">Work Experience</h2>
              <button className="px-3 py-1.5 bg-white text-black text-sm font-medium rounded-md hover:bg-[#ededed] transition-colors">
                Add Experience
              </button>
            </div>
            
            <div className="space-y-3">
              {experience.map((exp, i) => (
                <div key={i} className="p-4 rounded-md border border-[#1f1f1f] bg-[#000000]">
                  <div className="flex items-start justify-between mb-1.5">
                    <div>
                      <h3 className="font-medium text-white">{exp.role}</h3>
                      <p className="text-sm text-[#a3a3a3]">{exp.company}</p>
                    </div>
                    <span className="text-sm text-[#737373]">{exp.duration}</span>
                  </div>
                  <p className="text-sm text-[#737373]">{exp.location}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'skills' && (
          <div className="p-6 rounded-md border border-[#1f1f1f] bg-[#0a0a0a]">
            <h2 className="text-lg font-semibold mb-6 text-white">Your Skills</h2>
            <div className="flex flex-wrap gap-2 mb-6">
              {skills.map((skill) => (
                <span key={skill} className="px-3 py-1.5 rounded border border-[#1f1f1f] bg-[#000000] text-[#a3a3a3] text-sm hover:border-[#2f2f2f] transition-all">
                  {skill}
                </span>
              ))}
            </div>
            <button className="px-3 py-1.5 border border-[#1f1f1f] rounded-md text-sm text-[#a3a3a3] hover:border-[#2f2f2f] transition-all">
              + Add Skill
            </button>
          </div>
        )}

        {activeTab === 'preferences' && (
          <div className="p-6 rounded-md border border-[#1f1f1f] bg-[#0a0a0a]">
            <h2 className="text-lg font-semibold mb-6 text-white">Job Preferences</h2>
            
            <div className="space-y-6">
              <div>
                <label className="block text-sm text-[#a3a3a3] mb-2">Location Preference</label>
                <input
                  type="text"
                  defaultValue="Nairobi, Kenya (Remote OK)"
                  className="w-full px-3 py-2 bg-[#000000] border border-[#1f1f1f] rounded-md text-sm focus:border-[#2f2f2f] focus:outline-none text-white"
                />
              </div>
              
              <div>
                <label className="block text-sm text-[#a3a3a3] mb-2">Minimum Salary (KES/month)</label>
                <input
                  type="text"
                  defaultValue="150,000"
                  className="w-full px-3 py-2 bg-[#000000] border border-[#1f1f1f] rounded-md text-sm focus:border-[#2f2f2f] focus:outline-none text-white"
                />
              </div>
              
              <div>
                <label className="block text-sm text-[#a3a3a3] mb-2">Job Type</label>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" defaultChecked className="w-4 h-4" />
                    <span className="text-white text-sm">Full-time</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" className="w-4 h-4" />
                    <span className="text-white text-sm">Contract</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" defaultChecked className="w-4 h-4" />
                    <span className="text-white text-sm">Remote</span>
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
