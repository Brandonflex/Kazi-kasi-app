import type { Metadata } from 'next'
import '../styles/globals.css'

export const metadata: Metadata = {
  title: 'Kazi-Kasi — Smart Job Matching for Kenya',
  description: 'Find jobs that actually match your skills. Kazi-Kasi uses intelligent matching to surface opportunities you would apply to.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[#0a0a0a] text-[#f5f5f5]">
        {children}
      </body>
    </html>
  )
}
