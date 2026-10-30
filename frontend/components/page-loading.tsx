'use client'

export function PageLoading({ variant = 'profile' }: { variant?: 'profile' | 'feed' | 'tracker' }) {
  const count = variant === 'profile' ? 3 : variant === 'tracker' ? 4 : 5
  return (
    <main className="min-h-screen bg-black" aria-busy="true" aria-label={`Loading ${variant}`}>
      <header className="border-b border-[#202020]">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4">
          <div className="skeleton h-5 w-28 rounded" />
          <div className="hidden gap-6 sm:flex">
            <div className="skeleton h-4 w-12 rounded" />
            <div className="skeleton h-4 w-16 rounded" />
            <div className="skeleton h-4 w-14 rounded" />
          </div>
          <div className="skeleton h-9 w-9 rounded-full" />
        </div>
      </header>
      <section className="mx-auto max-w-6xl px-5 py-10 sm:py-14">
        <div className="skeleton mb-3 h-3 w-24 rounded" />
        <div className="skeleton mb-3 h-9 w-64 max-w-full rounded" />
        <div className="skeleton mb-8 h-4 w-96 max-w-full rounded" />
        {variant === 'profile' && <div className="skeleton mb-8 h-12 w-full rounded-xl" />}
        <div className="grid gap-4 sm:grid-cols-2">
          {Array.from({ length: count }).map((_, index) => (
            <div key={index} className="rounded-2xl border border-[#202020] p-5">
              <div className="skeleton mb-4 h-4 w-32 rounded" />
              <div className="skeleton mb-2 h-3 w-full rounded" />
              <div className="skeleton mb-5 h-3 w-3/4 rounded" />
              <div className="skeleton h-9 w-28 rounded-lg" />
            </div>
          ))}
        </div>
      </section>
    </main>
  )
}
