export default function Home() {
  return (
    <main className="min-h-screen">
      {/* Header */}
      <header className="border-b border-[#2a2a2a] bg-[#111111]/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <a href="/" className="font-display text-2xl font-bold">
            Kazi<span className="text-[#E9A23B]">-Kasi</span>
          </a>
          <div className="flex items-center gap-6">
            <a href="/feed" className="text-[#a0a0a0] hover:text-[#f5f5f5] transition-colors text-sm">Find Jobs</a>
            <a href="/tracker" className="text-[#a0a0a0] hover:text-[#f5f5f5] transition-colors text-sm">Tracker</a>
            <button className="px-5 py-2 border border-[#2a2a2a] hover:border-[#E9A23B]/50 rounded-lg transition-all text-sm">
              Sign In
            </button>
            <button className="px-5 py-2 bg-[#E9A23B] hover:bg-[#E9A23B]/90 text-[#0a0a0a] font-semibold rounded-lg transition-all text-sm">
              Get Started
            </button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative overflow-hidden border-b border-[#2a2a2a]">
        <div className="absolute inset-0 bg-gradient-to-br from-[#0a0a0a] via-[#111111] to-[#0a0a0a]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-[#E9A23B]/5 via-transparent to-transparent" />
        
        <div className="relative max-w-7xl mx-auto px-6 py-24 md:py-32">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-[#E9A23B]/30 bg-[#E9A23B]/10 mb-8">
              <div className="w-2 h-2 rounded-full bg-[#E9A23B] animate-pulse" />
              <span className="text-sm font-medium text-[#E9A23B]">Now matching 284 jobs in Kenya</span>
            </div>
            
            <h1 className="font-display text-5xl md:text-7xl font-bold leading-[1.05] mb-6">
              Find your next
              <span className="block text-[#E9A23B]">career move</span>
            </h1>
            
            <p className="text-xl text-[#a0a0a0] leading-relaxed mb-12 max-w-2xl">
              Kazi-Kasi understands your skills, experience, and goals, then surfaces opportunities you would actually apply to. No more scrolling through irrelevant postings.
            </p>
            
            <div className="flex flex-col sm:flex-row gap-4 mb-8">
              <a href="/feed" className="px-8 py-4 bg-[#E9A23B] hover:bg-[#E9A23B]/90 text-[#0a0a0a] font-semibold rounded-lg transition-all hover:scale-105 text-center">
                Browse Matching Jobs
              </a>
              <button className="px-8 py-4 border border-[#2a2a2a] hover:border-[#E9A23B]/50 rounded-lg transition-all">
                Upload Your CV
              </button>
            </div>
            
            <div className="flex items-center gap-6 text-sm text-[#a0a0a0]">
              <div className="flex items-center gap-2">
                <svg className="w-4 h-4 text-[#2dd4a8]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                <span>Smart job matching</span>
              </div>
              <div className="flex items-center gap-2">
                <svg className="w-4 h-4 text-[#2dd4a8]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                <span>Application tracker</span>
              </div>
              <div className="flex items-center gap-2">
                <svg className="w-4 h-4 text-[#2dd4a8]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                <span>WhatsApp alerts</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Stats Bar */}
      <section className="border-b border-[#2a2a2a] bg-[#111111]">
        <div className="max-w-7xl mx-auto px-6 py-12">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            <div>
              <div className="font-display text-4xl font-bold text-[#E9A23B] mb-2">284</div>
              <div className="text-sm text-[#a0a0a0] uppercase tracking-wider">Live Jobs</div>
            </div>
            <div>
              <div className="font-display text-4xl font-bold text-[#2dd4a8] mb-2">47</div>
              <div className="text-sm text-[#a0a0a0] uppercase tracking-wider">Closing This Week</div>
            </div>
            <div>
              <div className="font-display text-4xl font-bold text-[#1e90ff] mb-2">15</div>
              <div className="text-sm text-[#a0a0a0] uppercase tracking-wider">Sources Tracked</div>
            </div>
            <div>
              <div className="font-display text-4xl font-bold text-[#f5f5f5] mb-2">92%</div>
              <div className="text-sm text-[#a0a0a0] uppercase tracking-wider">Match Accuracy</div>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="max-w-7xl mx-auto px-6 py-24">
        <div className="mb-16">
          <h2 className="font-display text-4xl md:text-5xl font-bold mb-4">
            How it works
          </h2>
          <p className="text-xl text-[#a0a0a0] max-w-2xl">
            Three steps to find jobs that actually match.
          </p>
        </div>
        
        <div className="grid md:grid-cols-3 gap-8">
          <div className="relative">
            <div className="w-12 h-12 rounded-full bg-[#E9A23B]/20 border border-[#E9A23B]/30 flex items-center justify-center mb-6">
              <span className="text-[#E9A23B] font-bold text-xl">1</span>
            </div>
            <h3 className="font-display text-xl font-semibold mb-3">Upload your CV</h3>
            <p className="text-[#a0a0a0] leading-relaxed">
              We extract your skills, experience, and qualifications automatically. Takes 30 seconds.
            </p>
          </div>

          <div className="relative">
            <div className="w-12 h-12 rounded-full bg-[#2dd4a8]/20 border border-[#2dd4a8]/30 flex items-center justify-center mb-6">
              <span className="text-[#2dd4a8] font-bold text-xl">2</span>
            </div>
            <h3 className="font-display text-xl font-semibold mb-3">Get matched</h3>
            <p className="text-[#a0a0a0] leading-relaxed">
              Our algorithm scores every job against your profile. See exactly why each opportunity matches.
            </p>
          </div>

          <div className="relative">
            <div className="w-12 h-12 rounded-full bg-[#1e90ff]/20 border border-[#1e90ff]/30 flex items-center justify-center mb-6">
              <span className="text-[#1e90ff] font-bold text-xl">3</span>
            </div>
            <h3 className="font-display text-xl font-semibold mb-3">Track applications</h3>
            <p className="text-[#a0a0a0] leading-relaxed">
              Move jobs through stages as you progress. Get daily WhatsApp digests for new matches.
            </p>
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="border-t border-[#2a2a2a] bg-[#111111]">
        <div className="max-w-7xl mx-auto px-6 py-24">
          <div className="mb-16">
            <h2 className="font-display text-4xl md:text-5xl font-bold mb-4">
              Built for Kenyan job seekers
            </h2>
            <p className="text-xl text-[#a0a0a0] max-w-2xl">
              Every feature designed around how you actually search for work.
            </p>
          </div>
          
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            <div className="p-8 rounded-xl border border-[#2a2a2a] bg-[#0a0a0a] hover:border-[#E9A23B]/50 transition-all group">
              <div className="w-12 h-12 rounded-lg bg-[#E9A23B]/10 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <svg className="w-6 h-6 text-[#E9A23B]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
              <h3 className="font-display text-xl font-semibold mb-3">Smart Matching</h3>
              <p className="text-[#a0a0a0] leading-relaxed">
                Jobs ranked by actual fit, not just keywords. Constraints first, then relevance, then utility.
              </p>
            </div>

            <div className="p-8 rounded-xl border border-[#2a2a2a] bg-[#0a0a0a] hover:border-[#2dd4a8]/50 transition-all group">
              <div className="w-12 h-12 rounded-lg bg-[#2dd4a8]/10 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <svg className="w-6 h-6 text-[#2dd4a8]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                </svg>
              </div>
              <h3 className="font-display text-xl font-semibold mb-3">Kanban Tracker</h3>
              <p className="text-[#a0a0a0] leading-relaxed">
                Track every application across stages. Board view or list view. Notes, salary tracking, deadlines.
              </p>
            </div>

            <div className="p-8 rounded-xl border border-[#2a2a2a] bg-[#0a0a0a] hover:border-[#1e90ff]/50 transition-all group">
              <div className="w-12 h-12 rounded-lg bg-[#1e90ff]/10 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <svg className="w-6 h-6 text-[#1e90ff]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <h3 className="font-display text-xl font-semibold mb-3">WhatsApp Alerts</h3>
              <p className="text-[#a0a0a0] leading-relaxed">
                Daily job digests delivered to your WhatsApp. Never miss a closing deadline again.
              </p>
            </div>

            <div className="p-8 rounded-xl border border-[#2a2a2a] bg-[#0a0a0a] hover:border-[#E9A23B]/50 transition-all group">
              <div className="w-12 h-12 rounded-lg bg-[#E9A23B]/10 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <svg className="w-6 h-6 text-[#E9A23B]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>
              <h3 className="font-display text-xl font-semibold mb-3">CV Auto-Extract</h3>
              <p className="text-[#a0a0a0] leading-relaxed">
                Upload a PDF and we pull out skills, experience, and qualifications. No manual data entry.
              </p>
            </div>

            <div className="p-8 rounded-xl border border-[#2a2a2a] bg-[#0a0a0a] hover:border-[#2dd4a8]/50 transition-all group">
              <div className="w-12 h-12 rounded-lg bg-[#2dd4a8]/10 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <svg className="w-6 h-6 text-[#2dd4a8]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <h3 className="font-display text-xl font-semibold mb-3">Cover Letters</h3>
              <p className="text-[#a0a0a0] leading-relaxed">
                Generate tailored cover letters based on your profile and the specific job requirements.
              </p>
            </div>

            <div className="p-8 rounded-xl border border-[#2a2a2a] bg-[#0a0a0a] hover:border-[#1e90ff]/50 transition-all group">
              <div className="w-12 h-12 rounded-lg bg-[#1e90ff]/10 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <svg className="w-6 h-6 text-[#1e90ff]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              </div>
              <h3 className="font-display text-xl font-semibold mb-3">Location Aware</h3>
              <p className="text-[#a0a0a0] leading-relaxed">
                County-level matching across Kenya. Filter by remote, hybrid, or on-site. Distance scoring.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-[#2a2a2a] bg-gradient-to-br from-[#0a0a0a] via-[#111111] to-[#0a0a0a]">
        <div className="max-w-3xl mx-auto px-6 py-24 text-center">
          <h2 className="font-display text-4xl md:text-5xl font-bold mb-6">
            Ready to find your <span className="text-[#E9A23B]">next role?</span>
          </h2>
          <p className="text-xl text-[#a0a0a0] mb-8">
            Join thousands of Kenyan professionals using smart matching to find jobs that fit.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <a href="/feed" className="px-8 py-4 bg-[#E9A23B] hover:bg-[#E9A23B]/90 text-[#0a0a0a] font-semibold rounded-lg transition-all hover:scale-105">
              Start Matching Jobs
            </a>
            <button className="px-8 py-4 border border-[#2a2a2a] hover:border-[#E9A23B]/50 rounded-lg transition-all">
              Upload Your CV
            </button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[#2a2a2a] bg-[#111111]">
        <div className="max-w-7xl mx-auto px-6 py-12">
          <div className="grid md:grid-cols-4 gap-8 mb-8">
            <div>
              <a href="/" className="font-display text-xl font-bold mb-4 block">
                Kazi<span className="text-[#E9A23B]">-Kasi</span>
              </a>
              <p className="text-sm text-[#a0a0a0]">
                Smart job matching for Kenyan professionals.
              </p>
            </div>
            <div>
              <h4 className="font-semibold text-sm uppercase tracking-wider text-[#a0a0a0] mb-4">Product</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="/feed" className="text-[#a0a0a0] hover:text-[#f5f5f5] transition-colors">Job Feed</a></li>
                <li><a href="/tracker" className="text-[#a0a0a0] hover:text-[#f5f5f5] transition-colors">Application Tracker</a></li>
                <li><a href="/profile" className="text-[#a0a0a0] hover:text-[#f5f5f5] transition-colors">Profile</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-sm uppercase tracking-wider text-[#a0a0a0] mb-4">Resources</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="#" className="text-[#a0a0a0] hover:text-[#f5f5f5] transition-colors">Blog</a></li>
                <li><a href="#" className="text-[#a0a0a0] hover:text-[#f5f5f5] transition-colors">Career Guide</a></li>
                <li><a href="#" className="text-[#a0a0a0] hover:text-[#f5f5f5] transition-colors">Salary Data</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-sm uppercase tracking-wider text-[#a0a0a0] mb-4">Company</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="#" className="text-[#a0a0a0] hover:text-[#f5f5f5] transition-colors">About</a></li>
                <li><a href="#" className="text-[#a0a0a0] hover:text-[#f5f5f5] transition-colors">Contact</a></li>
                <li><a href="#" className="text-[#a0a0a0] hover:text-[#f5f5f5] transition-colors">Privacy</a></li>
              </ul>
            </div>
          </div>
          <div className="pt-8 border-t border-[#2a2a2a] text-center text-sm text-[#a0a0a0]">
            &copy; 2024 Kazi-Kasi. Built for Kenyan job seekers.
          </div>
        </div>
      </footer>
    </main>
  )
}
