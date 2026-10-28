export default function Home() {
  return (
    <main className="min-h-screen bg-[#000000]">
      {/* Header */}
      <header className="border-b border-[#1f1f1f] sticky top-0 z-50 bg-[#000000]/80 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <a href="/" className="text-xl font-semibold text-white">
            Kazi-Kasi
          </a>
          <div className="flex items-center gap-6">
            <a href="/feed" className="text-[#a3a3a3] hover:text-white transition-colors text-sm">Jobs</a>
            <a href="/tracker" className="text-[#a3a3a3] hover:text-white transition-colors text-sm">Tracker</a>
            <a href="/auth" className="px-4 py-2 text-sm text-[#a3a3a3] hover:text-white transition-colors">
              Sign In
            </a>
            <a href="/auth" className="px-4 py-2 bg-white text-black text-sm font-medium rounded-md hover:bg-[#ededed] transition-colors">
              Get Started
            </a>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="max-w-6xl mx-auto px-6 py-32">
        <div className="max-w-3xl">
          <h1 className="text-5xl md:text-6xl font-bold leading-tight mb-6 text-white">
            Find jobs that actually match
          </h1>
          
          <p className="text-xl text-[#a3a3a3] leading-relaxed mb-10 max-w-2xl">
            Kazi-Kasi understands your skills and experience, then surfaces opportunities you would apply to. No more scrolling through irrelevant postings.
          </p>
          
          <div className="flex flex-col sm:flex-row gap-3">
            <a href="/feed" className="px-6 py-3 bg-white text-black font-medium rounded-md hover:bg-[#ededed] transition-colors text-center">
              Browse Jobs
            </a>
            <a href="/profile" className="px-6 py-3 border border-[#1f1f1f] hover:border-[#2f2f2f] rounded-md transition-colors text-[#a3a3a3] hover:text-white text-center">
              Prepare your profile
            </a>
          </div>
        </div>
      </section>

      {/* Stats Bar */}
      <section className="border-t border-b border-[#1f1f1f]">
        <div className="max-w-6xl mx-auto px-6 py-16">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 md:gap-12">
            <div>
              <div className="text-lg font-semibold text-white mb-2">Relevant roles</div>
              <div className="text-sm text-[#737373]">Ranked around what you actually want.</div>
            </div>
            <div>
              <div className="text-lg font-semibold text-white mb-2">Your constraints</div>
              <div className="text-sm text-[#737373]">Commute and salary shape your matches.</div>
            </div>
            <div>
              <div className="text-lg font-semibold text-white mb-2">Clear reasons</div>
              <div className="text-sm text-[#737373]">See why each job appears in your feed.</div>
            </div>
            <div>
              <div className="text-lg font-semibold text-white mb-2">Kenya-focused</div>
              <div className="text-sm text-[#737373]">Built around local roles and locations.</div>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="max-w-6xl mx-auto px-6 py-32">
        <div className="mb-20">
          <h2 className="text-3xl md:text-4xl font-bold mb-4 text-white">
            How it works
          </h2>
          <p className="text-lg text-[#a3a3a3] max-w-2xl">
            Set your priorities, understand your matches, and keep your search organized.
          </p>
        </div>
        
        <div className="grid md:grid-cols-3 gap-12">
          <div>
            <div className="text-sm text-[#737373] font-medium mb-3">01</div>
            <h3 className="text-xl font-semibold mb-3 text-white">Set your priorities</h3>
            <p className="text-[#a3a3a3] leading-relaxed">
              Choose the roles, locations, commute, and salary that work for you.
            </p>
          </div>

          <div>
            <div className="text-sm text-[#737373] font-medium mb-3">02</div>
            <h3 className="text-xl font-semibold mb-3 text-white">Get matched</h3>
            <p className="text-[#a3a3a3] leading-relaxed">
              Our algorithm scores every job against your profile. See exactly why each opportunity matches.
            </p>
          </div>

          <div>
            <div className="text-sm text-[#737373] font-medium mb-3">03</div>
            <h3 className="text-xl font-semibold mb-3 text-white">Track applications</h3>
            <p className="text-[#a3a3a3] leading-relaxed">
              Move jobs through stages as you progress. Get daily WhatsApp digests for new matches.
            </p>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="border-t border-[#1f1f1f] bg-[#0a0a0a]">
        <div className="max-w-6xl mx-auto px-6 py-32">
          <div className="mb-20">
            <h2 className="text-3xl md:text-4xl font-bold mb-4 text-white">
              Built for Kenyan job seekers
            </h2>
            <p className="text-lg text-[#a3a3a3] max-w-2xl">
              Every feature designed around how you actually search for work.
            </p>
          </div>
          
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            <div>
              <h3 className="text-lg font-semibold mb-2 text-white">Smart Matching</h3>
              <p className="text-[#a3a3a3] leading-relaxed">
                Jobs ranked by actual fit, not just keywords. Constraints first, then relevance, then utility.
              </p>
            </div>

            <div>
              <h3 className="text-lg font-semibold mb-2 text-white">Kanban Tracker</h3>
              <p className="text-[#a3a3a3] leading-relaxed">
                Track every application across stages. Board view or list view. Notes, salary, deadlines.
              </p>
            </div>

            <div>
              <h3 className="text-lg font-semibold mb-2 text-white">Clear match reasons</h3>
              <p className="text-[#a3a3a3] leading-relaxed">
                Understand which parts of your profile shaped each recommendation.
              </p>
            </div>

            <div>
              <h3 className="text-lg font-semibold mb-2 text-white">Your profile, your call</h3>
              <p className="text-[#a3a3a3] leading-relaxed">
                Review and adjust the preferences behind your personalized feed.
              </p>
            </div>

            <div>
              <h3 className="text-lg font-semibold mb-2 text-white">Focused search</h3>
              <p className="text-[#a3a3a3] leading-relaxed">
                Search by title, employer, and the fit reasons that matter to you.
              </p>
            </div>

            <div>
              <h3 className="text-lg font-semibold mb-2 text-white">Location Aware</h3>
              <p className="text-[#a3a3a3] leading-relaxed">
                County-level matching across Kenya. Filter by remote, hybrid, or on-site.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-[#1f1f1f]">
        <div className="max-w-3xl mx-auto px-6 py-32 text-center">
          <h2 className="text-3xl md:text-4xl font-bold mb-6 text-white">
            Ready to find your next role?
          </h2>
          <p className="text-lg text-[#a3a3a3] mb-10">
            Create your profile to start exploring opportunities matched to your priorities.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <a href="/feed" className="px-6 py-3 bg-white text-black font-medium rounded-md hover:bg-[#ededed] transition-colors">
              Start Matching Jobs
            </a>
            <a href="/profile" className="px-6 py-3 border border-[#1f1f1f] hover:border-[#2f2f2f] rounded-md transition-colors text-[#a3a3a3] hover:text-white text-center">
              Prepare your profile
            </a>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[#1f1f1f]">
        <div className="max-w-6xl mx-auto px-6 py-16">
          <div className="grid md:grid-cols-4 gap-12 mb-12">
            <div>
              <a href="/" className="text-lg font-semibold text-white mb-4 block">
                Kazi-Kasi
              </a>
              <p className="text-sm text-[#737373]">
                Smart job matching for Kenyan professionals.
              </p>
            </div>
            <div>
              <h4 className="text-sm font-medium text-white mb-4">Product</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="/feed" className="text-[#737373] hover:text-white transition-colors">Job Feed</a></li>
                <li><a href="/tracker" className="text-[#737373] hover:text-white transition-colors">Tracker</a></li>
                <li><a href="/profile" className="text-[#737373] hover:text-white transition-colors">Profile</a></li>
              </ul>
            </div>
            <div>
              <h4 className="text-sm font-medium text-white mb-4">Resources</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="#" className="text-[#737373] hover:text-white transition-colors">Blog</a></li>
                <li><a href="#" className="text-[#737373] hover:text-white transition-colors">Career Guide</a></li>
                <li><a href="#" className="text-[#737373] hover:text-white transition-colors">Salary Data</a></li>
              </ul>
            </div>
            <div>
              <h4 className="text-sm font-medium text-white mb-4">Company</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="#" className="text-[#737373] hover:text-white transition-colors">About</a></li>
                <li><a href="#" className="text-[#737373] hover:text-white transition-colors">Contact</a></li>
                <li><a href="#" className="text-[#737373] hover:text-white transition-colors">Privacy</a></li>
              </ul>
            </div>
          </div>
          <div className="pt-8 border-t border-[#1f1f1f] text-center text-sm text-[#737373]">
            &copy; 2024 Kazi-Kasi. Built for Kenyan job seekers.
          </div>
        </div>
      </footer>
    </main>
  )
}
