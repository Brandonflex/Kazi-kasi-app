'use client'

import { useState } from 'react'

const jobData = {
  id: '1',
  title: 'Senior Software Engineer',
  company: 'Safaricom PLC',
  location: 'Nairobi, Kenya',
  type: 'Full-time',
  salary: 'KES 250K - 350K',
  posted: '2 days ago',
  closing: 'In 12 days',
  match_score: 94,
  why_match: 'Strong match on Python, FastAPI, and cloud infrastructure experience. Your 5+ years of backend development aligns perfectly with their requirements.',
  match_details: [
    { skill: 'Python/FastAPI', score: 95, label: 'Strong' },
    { skill: 'Cloud Infrastructure', score: 90, label: 'Strong' },
    { skill: 'PostgreSQL', score: 88, label: 'Strong' },
    { skill: 'API Design', score: 92, label: 'Strong' },
    { skill: 'Team Leadership', score: 78, label: 'Partial' }
  ],
  url: 'https://careers.safaricom.co.ke',
  description: `We are looking for a Senior Software Engineer to join our growing platform team. You will build and maintain critical infrastructure that serves millions of customers across East Africa.

Key responsibilities:
- Design and implement scalable backend services using Python and FastAPI
- Work with cloud infrastructure (AWS/GCP) to ensure 99.9% uptime
- Collaborate with frontend teams on API design and data modeling
- Mentor junior engineers and contribute to technical strategy
- Participate in on-call rotation and incident response

We are building the next generation of mobile financial services, and you would be at the center of it.`,
  requirements: [
    '5+ years backend development experience',
    'Strong Python skills with async framework experience (FastAPI, Django)',
    'Experience with PostgreSQL and database optimization',
    'Familiarity with cloud platforms (AWS preferred)',
    'Git and CI/CD pipeline experience',
    'Excellent written and verbal communication'
  ],
  benefits: [
    'Competitive salary with annual performance bonuses',
    'Comprehensive health insurance for you and family',
    'Flexible work arrangements (hybrid)',
    'Learning and development budget (KES 100K/year)',
    'Equity participation plan',
    '25 days annual leave'
  ]
}

export default function JobDetailPage({ params }: { params: { id: string } }) {
  const [saved, setSaved] = useState(false)

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
        </div>
      </header>

      {/* Breadcrumb */}
      <div className="max-w-5xl mx-auto px-6 py-6">
        <a href="/feed" className="text-[#a0a0a0] hover:text-[#f5f5f5] text-sm flex items-center gap-2 transition-colors">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back to feed
        </a>
      </div>

      {/* Job Header Card */}
      <section className="max-w-5xl mx-auto px-6 pb-8">
        <div className="p-8 rounded-xl border border-[#2a2a2a] bg-[#111111]">
          <div className="flex items-start justify-between mb-6">
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-3">
                <span className="px-3 py-1 rounded-full text-xs font-semibold bg-[#E9A23B]/20 text-[#E9A23B]">
                  {jobData.match_score}% match
                </span>
                <span className="text-sm text-[#a0a0a0]">Posted {jobData.posted}</span>
                <span className="text-sm text-[#a0a0a0]">/ Closes {jobData.closing}</span>
              </div>
              <h1 className="font-display text-4xl font-bold mb-3">{jobData.title}</h1>
              <div className="flex items-center gap-4 text-lg text-[#a0a0a0]">
                <span className="font-semibold text-[#f5f5f5]">{jobData.company}</span>
                <span className="text-[#2a2a2a]">|</span>
                <span>{jobData.location}</span>
                <span className="text-[#2a2a2a]">|</span>
                <span>{jobData.type}</span>
              </div>
            </div>
            <div className="text-right flex-shrink-0 ml-8">
              <div className="text-2xl font-bold text-[#2dd4a8] mb-1">{jobData.salary}</div>
              <div className="text-sm text-[#a0a0a0]">Per month, gross</div>
            </div>
          </div>

          <div className="flex gap-3">
            <a
              href={jobData.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 text-center px-6 py-3 bg-[#E9A23B] hover:bg-[#E9A23B]/90 text-[#0a0a0a] font-semibold rounded-lg transition-all hover:scale-[1.02]"
            >
              Apply on Company Site
            </a>
            <button 
              onClick={() => setSaved(!saved)}
              className={`px-6 py-3 border rounded-lg transition-all ${saved ? 'border-[#2dd4a8] text-[#2dd4a8] bg-[#2dd4a8]/10' : 'border-[#2a2a2a] hover:border-[#2dd4a8]/50'}`}
            >
              {saved ? 'Saved' : 'Save'}
            </button>
          </div>
        </div>
      </section>

      {/* Match Breakdown */}
      <section className="max-w-5xl mx-auto px-6 pb-8">
        <div className="p-8 rounded-xl border border-[#2a2a2a] bg-[#111111]">
          <h2 className="font-display text-xl font-bold mb-6">Why This Matches You</h2>
          <p className="text-[#a0a0a0] mb-6">{jobData.why_match}</p>
          
          <div className="space-y-4">
            {jobData.match_details.map((detail) => (
              <div key={detail.skill} className="flex items-center gap-4">
                <span className="text-sm text-[#f5f5f5] w-44 flex-shrink-0">{detail.skill}</span>
                <div className="flex-1 h-2 rounded-full bg-[#1a1a1a] overflow-hidden">
                  <div 
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${detail.score}%`,
                      background: detail.score >= 85 ? '#2dd4a8' : detail.score >= 70 ? '#E9A23B' : '#a0a0a0'
                    }}
                  />
                </div>
                <span className={`text-sm font-medium w-20 text-right ${
                  detail.score >= 85 ? 'text-[#2dd4a8]' : detail.score >= 70 ? 'text-[#E9A23B]' : 'text-[#a0a0a0]'
                }`}>
                  {detail.label}
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Job Description */}
      <section className="max-w-5xl mx-auto px-6 pb-8">
        <div className="p-8 rounded-xl border border-[#2a2a2a] bg-[#111111]">
          <h2 className="font-display text-xl font-bold mb-6">About the Role</h2>
          <div className="text-[#a0a0a0] leading-relaxed space-y-4">
            {jobData.description.split('\n\n').map((paragraph, i) => (
              <p key={i}>{paragraph}</p>
            ))}
          </div>
        </div>
      </section>

      {/* Requirements */}
      <section className="max-w-5xl mx-auto px-6 pb-8">
        <div className="p-8 rounded-xl border border-[#2a2a2a] bg-[#111111]">
          <h2 className="font-display text-xl font-bold mb-6">Requirements</h2>
          <ul className="space-y-3">
            {jobData.requirements.map((req, i) => (
              <li key={i} className="flex items-start gap-3 text-[#a0a0a0]">
                <svg className="w-5 h-5 text-[#2dd4a8] flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4" />
                </svg>
                {req}
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Benefits */}
      <section className="max-w-5xl mx-auto px-6 pb-12">
        <div className="p-8 rounded-xl border border-[#2a2a2a] bg-[#111111]">
          <h2 className="font-display text-xl font-bold mb-6">Benefits</h2>
          <ul className="space-y-3">
            {jobData.benefits.map((benefit, i) => (
              <li key={i} className="flex items-start gap-3 text-[#a0a0a0]">
                <svg className="w-5 h-5 text-[#E9A23B] flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                {benefit}
              </li>
            ))}
          </ul>
        </div>
      </section>
    </main>
  )
}
