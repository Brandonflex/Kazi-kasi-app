'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { fetchJob, type JobDetail, isAuthenticated } from '@/lib/api'

export default function JobDetailPage({ params }: { params: { id: string } }) {
  const router = useRouter()
  const [job, setJob] = useState<JobDetail | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push('/auth')
      return
    }
    loadJob()
  }, [params.id, router])

  async function loadJob() {
    try {
      setLoading(true)
      const data = await fetchJob(params.id)
      setJob(data)
    } catch (error) {
      console.error('Failed to load job:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <main className="min-h-screen bg-[#000000]">
        <div className="text-center py-20">
          <p className="text-[#737373]">Loading job details...</p>
        </div>
      </main>
    )
  }

  if (!job) {
    return (
      <main className="min-h-screen bg-[#000000]">
        <div className="text-center py-20">
          <p className="text-[#737373]">Job not found</p>
        </div>
      </main>
    )
  }

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
        </div>
      </header>

      {/* Breadcrumb */}
      <div className="max-w-4xl mx-auto px-6 py-6">
        <a href="/feed" className="text-sm text-[#737373] hover:text-white transition-colors flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back to jobs
        </a>
      </div>

      {/* Job Header */}
      <section className="max-w-4xl mx-auto px-6 pb-8">
        <div className="p-6 rounded-md border border-[#1f1f1f] bg-[#0a0a0a]">
          <div className="flex items-start justify-between mb-4">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-sm text-[#737373]">Posted {job.posted || 'Recently'}</span>
                {job.deadline && (
                  <>
                    <span className="text-[#1f1f1f]">•</span>
                    <span className="text-sm text-[#737373]">Closes {job.deadline}</span>
                  </>
                )}
              </div>
              <h1 className="text-3xl font-semibold mb-2 text-white">{job.title}</h1>
              <div className="flex items-center gap-2 text-sm text-[#a3a3a3]">
                <span className="font-medium text-[#ededed]">{job.employer}</span>
                <span className="text-[#1f1f1f]">•</span>
                <span>{job.location}</span>
              </div>
            </div>
            <div className="text-right flex-shrink-0 ml-6">
              {job.salary_min && job.salary_max && (
                <>
                  <div className="text-2xl font-semibold text-white mb-0.5">
                    KES {job.salary_min.toLocaleString()} - {job.salary_max.toLocaleString()}
                  </div>
                  <div className="text-sm text-[#737373]">Per month</div>
                </>
              )}
            </div>
          </div>

          <div className="flex gap-2">
            {job.source_url ? (
              <a
                href={job.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 text-center px-5 py-2.5 bg-white text-black font-medium rounded-md hover:bg-[#ededed] transition-colors"
              >
                Apply on Company Site
              </a>
            ) : (
              <span className="flex-1 text-center px-5 py-2.5 bg-[#1a1a1a] text-[#737373] font-medium rounded-md">
                Application link unavailable
              </span>
            )}
            <button className="px-5 py-2.5 border border-[#1f1f1f] hover:border-[#2f2f2f] rounded-md transition-all text-[#a3a3a3] hover:text-white">
              Save
            </button>
          </div>
        </div>
      </section>

      {/* Job Description */}
      <section className="max-w-4xl mx-auto px-6 pb-8">
        <div className="p-6 rounded-md border border-[#1f1f1f] bg-[#0a0a0a]">
          <h2 className="text-lg font-semibold mb-4 text-white">About the Role</h2>
          <div className="text-sm text-[#a3a3a3] leading-relaxed">
            {job.description || 'No description available.'}
          </div>
        </div>
      </section>

      {/* Requirements */}
      {job.requirements && job.requirements.length > 0 && (
        <section className="max-w-4xl mx-auto px-6 pb-8">
          <div className="p-6 rounded-md border border-[#1f1f1f] bg-[#0a0a0a]">
            <h2 className="text-lg font-semibold mb-4 text-white">Requirements</h2>
            <ul className="space-y-2">
              {job.requirements.map((req, i) => (
                <li key={i} className="flex items-start gap-3 text-sm text-[#a3a3a3]">
                  <svg className="w-4 h-4 text-white flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4" />
                  </svg>
                  {req}
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}

      {/* Benefits */}
      {job.benefits && job.benefits.length > 0 && (
        <section className="max-w-4xl mx-auto px-6 pb-12">
          <div className="p-6 rounded-md border border-[#1f1f1f] bg-[#0a0a0a]">
            <h2 className="text-lg font-semibold mb-4 text-white">Benefits</h2>
            <ul className="space-y-2">
              {job.benefits.map((benefit, i) => (
                <li key={i} className="flex items-start gap-3 text-sm text-[#a3a3a3]">
                  <svg className="w-4 h-4 text-white flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  {benefit}
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}
    </main>
  )
}
