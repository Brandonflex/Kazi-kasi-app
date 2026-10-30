'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  ArrowRight, BadgeCheck, BriefcaseBusiness, Check, ChevronRight, CircleHelp,
  FileText, LoaderCircle, LogOut, MapPin, Plus, Save, ShieldCheck, Sparkles,
  Trash2, Upload, UserRound, X,
} from 'lucide-react'
import {
  deleteProfileCv, fetchCurrentUser, fetchProfile, fetchProfileCv, isAuthenticated,
  logout, updateProfile, uploadProfileCv, type Profile, type ProfileCv,
} from '@/lib/api'
import { PageLoading } from '@/components/page-loading'

const sections = [
  { id: 'overview', label: 'Overview', icon: UserRound },
  { id: 'skills', label: 'Skills and roles', icon: Sparkles },
  { id: 'experience', label: 'Experience', icon: BriefcaseBusiness },
  { id: 'preferences', label: 'Job preferences', icon: MapPin },
  { id: 'account', label: 'Account', icon: ShieldCheck },
] as const

type SectionId = typeof sections[number]['id']

const families = [
  ['it', 'Technology'], ['finance', 'Finance'], ['admin', 'Administration'],
  ['operations', 'Operations'], ['sales', 'Sales'], ['marketing', 'Marketing'],
  ['hr', 'People and HR'], ['programme', 'Programmes'], ['customer', 'Customer support'],
  ['legal', 'Legal'], ['health', 'Healthcare'], ['education', 'Education'],
]
const counties = [
  'Baringo', 'Bomet', 'Bungoma', 'Busia', 'Elgeyo-Marakwet', 'Embu', 'Garissa', 'Homa Bay',
  'Isiolo', 'Kajiado', 'Kakamega', 'Kericho', 'Kiambu', 'Kilifi', 'Kirinyaga', 'Kisii',
  'Kisumu', 'Kitui', 'Kwale', 'Laikipia', 'Lamu', 'Machakos', 'Makueni', 'Mandera',
  'Marsabit', 'Meru', 'Migori', 'Mombasa', "Murang'a", 'Nairobi', 'Nakuru', 'Nandi',
  'Narok', 'Nyamira', 'Nyandarua', 'Nyeri', 'Samburu', 'Siaya', 'Taita-Taveta', 'Tana River',
  'Tharaka-Nithi', 'Trans Nzoia', 'Turkana', 'Uasin Gishu', 'Vihiga', 'Wajir', 'West Pokot',
]
const roleLevels = [
  ['open_to_freshers', 'Open to fresh graduates'],
  ['some_experience', 'Some experience'],
  ['experienced', 'Experienced roles'],
]
const workTypes = [
  ['full_time', 'Full-time'], ['part_time', 'Part-time'], ['contract', 'Contract'],
  ['internship', 'Internship'], ['attachment', 'Attachment'], ['temporary', 'Temporary'],
  ['volunteer', 'Volunteer'],
]
const workModes = [['onsite', 'On-site'], ['hybrid', 'Hybrid'], ['remote', 'Remote']]

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || 'KK'
}

function fieldValue(cv: ProfileCv | null, key: string): string | string[] | undefined {
  return cv?.fields?.[key]?.value
}

function completion(profile: Profile, email: string, cv: ProfileCv | null) {
  const checks = [
    Boolean(profile.name.trim()), Boolean(email), Boolean(profile.home_county),
    profile.role_families.length > 0, profile.skills.length > 0, Boolean(cv),
  ]
  return { done: checks.filter(Boolean).length, total: checks.length, percent: Math.round(checks.filter(Boolean).length / checks.length * 100) }
}

function TogglePill({ checked, label, onClick }: { checked: boolean; label: string; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} aria-pressed={checked}
      className={`inline-flex min-h-10 items-center gap-2 rounded-lg border px-3.5 text-sm transition-colors ${checked ? 'border-[#777] bg-[#1d1d1d] text-white' : 'border-[#292929] bg-[#0a0a0a] text-[#a3a3a3] hover:border-[#525252] hover:text-white'}`}>
      {checked && <Check size={14} aria-hidden="true" />}{label}
    </button>
  )
}

function SectionHeading({ eyebrow, title, copy }: { eyebrow: string; title: string; copy: string }) {
  return (
    <div className="mb-7">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-[#777]">{eyebrow}</p>
      <h2 className="text-2xl font-semibold tracking-tight text-white sm:text-[28px]">{title}</h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-[#888]">{copy}</p>
    </div>
  )
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-medium text-[#ddd]">{label}</span>
      {children}
      {hint && <span className="mt-2 block text-xs leading-5 text-[#777]">{hint}</span>}
    </label>
  )
}

const inputClass = 'w-full rounded-lg border border-[#2a2a2a] bg-[#090909] px-3.5 py-3 text-sm text-white outline-none transition-colors placeholder:text-[#666] focus:border-[#777] focus:ring-2 focus:ring-white/10'
const selectClass = `${inputClass} appearance-none`

export default function ProfilePage() {
  const router = useRouter()
  const fileInput = useRef<HTMLInputElement>(null)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [email, setEmail] = useState('')
  const [cv, setCv] = useState<ProfileCv | null>(null)
  const [cvSuggestions, setCvSuggestions] = useState<Record<string, unknown>>({})
  const [section, setSection] = useState<SectionId>('overview')
  const [skillInput, setSkillInput] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [deletingCv, setDeletingCv] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace('/auth')
      return
    }
    void loadProfile()
    // Router identity is stable; this loads once for each signed-in visit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router])

  async function loadProfile() {
    setLoading(true)
    setError('')
    try {
      const [savedProfile, user, cvResponse] = await Promise.all([
        fetchProfile(), fetchCurrentUser(), fetchProfileCv(),
      ])
      setProfile(savedProfile)
      setEmail(user.email)
      setCv(cvResponse.cv)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Your profile could not be loaded.')
    } finally {
      setLoading(false)
    }
  }

  function patch<K extends keyof Profile>(key: K, value: Profile[K]) {
    setProfile((current) => current ? { ...current, [key]: value } : current)
    setNotice('')
  }

  async function save() {
    if (!profile) return
    setSaving(true)
    setError('')
    setNotice('')
    try {
      const saved = await updateProfile(profile)
      setProfile(saved)
      setNotice('Profile saved. Your job matches will use these details.')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Your changes could not be saved.')
    } finally {
      setSaving(false)
    }
  }

  async function processFile(file?: File) {
    if (!file) return
    setError('')
    setNotice('')
    if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') {
      setError('Choose a PDF file to continue.')
      return
    }
    if (file.size > 5 * 1024 * 1024) {
      setError('This PDF is larger than 5 MB. Choose a smaller file.')
      return
    }
    setUploading(true)
    try {
      const result = await uploadProfileCv(file)
      setCv(result.cv)
      setCvSuggestions(result.suggestions || {})
      if (result.profile) setProfile(result.profile)
      setNotice(result.message)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The PDF could not be processed.')
    } finally {
      setUploading(false)
      if (fileInput.current) fileInput.current.value = ''
    }
  }

  async function removeCv() {
    if (!cv || !window.confirm('Remove this CV and its extracted details?')) return
    setDeletingCv(true)
    setError('')
    setNotice('')
    try {
      const result = await deleteProfileCv()
      setCv(result.cv)
      setNotice(result.deleted ? 'CV removed. Your saved skills remain in your profile.' : 'No saved CV was found.')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The CV could not be removed.')
    } finally {
      setDeletingCv(false)
    }
  }

  function addSkill(event: React.FormEvent) {
    event.preventDefault()
    if (!profile) return
    const skill = skillInput.trim().replace(/\s+/g, ' ')
    if (!skill || profile.skills.some((item) => item.toLowerCase() === skill.toLowerCase())) return
    if (profile.skills.length >= 40) {
      setError('Keep up to 40 skills in your matching profile.')
      return
    }
    patch('skills', [...profile.skills, skill])
    setSkillInput('')
  }

  function toggleValue(key: 'role_families' | 'skills' | 'entry_fits' | 'employment_types' | 'work_modes', value: string) {
    if (!profile) return
    const current = profile[key] as string[]
    const next = current.includes(value) ? current.filter((item) => item !== value) : [...current, value]
    patch(key, next as Profile[typeof key])
  }

  const score = useMemo(() => profile ? completion(profile, email, cv) : null, [profile, email, cv])
  const activeSection = sections.find((item) => item.id === section)!
  const extractedSkills = fieldValue(cv, 'skills')
  const experience = fieldValue(cv, 'experience')
  const education = fieldValue(cv, 'education')
  const titles = fieldValue(cv, 'titles')
  const location = fieldValue(cv, 'location')
  const suggestedFamilies = Array.isArray(cvSuggestions.role_families) ? cvSuggestions.role_families as string[] : []
  const suggestedCounty = typeof cvSuggestions.home_county === 'string' ? cvSuggestions.home_county : ''
  const hasSuggestions = suggestedFamilies.length > 0 || Boolean(suggestedCounty)

  if (loading || !profile) {
    if (error && !loading) {
      return (
        <main className="min-h-screen bg-black px-5 py-20 text-center">
          <div className="mx-auto max-w-md rounded-2xl border border-[#292929] bg-[#0a0a0a] p-8">
            <CircleHelp className="mx-auto mb-4 text-[#999]" size={24} />
            <h1 className="text-lg font-semibold text-white">Profile unavailable</h1>
            <p className="mt-2 text-sm text-[#888]">{error}</p>
            <button onClick={() => void loadProfile()} className="mt-6 rounded-lg border border-[#3a3a3a] px-4 py-2 text-sm text-white hover:bg-[#171717]">Try again</button>
          </div>
        </main>
      )
    }
    return <PageLoading variant="profile" />
  }

  return (
    <main className="min-h-screen bg-black text-[#ededed]">
      <header className="sticky top-0 z-20 border-b border-[#202020] bg-black/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3.5 sm:px-6">
          <a href="/feed" className="flex items-center gap-2.5" aria-label="Kazi-Kasi jobs">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-[#343434] text-[11px] font-bold tracking-tight text-white">KK</span>
            <span className="text-sm font-semibold tracking-tight text-white">Kazi-Kasi</span>
          </a>
          <nav className="hidden items-center gap-1 sm:flex" aria-label="Main navigation">
            <a href="/feed" className="rounded-lg px-3 py-2 text-sm text-[#888] transition hover:bg-[#151515] hover:text-white">Jobs</a>
            <a href="/tracker" className="rounded-lg px-3 py-2 text-sm text-[#888] transition hover:bg-[#151515] hover:text-white">Tracker</a>
            <a href="/profile" aria-current="page" className="rounded-lg border border-[#292929] bg-[#121212] px-3 py-2 text-sm text-white">Profile</a>
          </nav>
          <div className="flex items-center gap-3">
            <span className="hidden max-w-48 truncate text-xs text-[#777] md:block">{email}</span>
            <div className="flex h-8 w-8 items-center justify-center rounded-full border border-[#383838] bg-[#151515] text-xs font-semibold text-white" aria-label={profile.name}>
              {initials(profile.name)}
            </div>
          </div>
        </div>
        <nav className="mx-auto flex max-w-6xl gap-1 overflow-x-auto px-4 pb-2 sm:hidden" aria-label="Main navigation">
          <a href="/feed" className="rounded-lg px-3 py-2 text-xs text-[#888] hover:bg-[#151515] hover:text-white">Jobs</a>
          <a href="/tracker" className="rounded-lg px-3 py-2 text-xs text-[#888] hover:bg-[#151515] hover:text-white">Tracker</a>
          <a href="/profile" aria-current="page" className="rounded-lg border border-[#292929] bg-[#121212] px-3 py-2 text-xs text-white">Profile</a>
        </nav>
      </header>

      <div className="mx-auto max-w-6xl px-4 pb-20 pt-8 sm:px-6 sm:pt-12">
        <div className="mb-8 flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
          <div className="animate-rise-in">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#777]">Your workspace</p>
            <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">Profile</h1>
            <p className="mt-2 max-w-xl text-sm leading-6 text-[#888]">Build a clear picture of your skills and priorities. These details shape the jobs we rank for you.</p>
          </div>
          <button type="button" onClick={() => void save()} disabled={saving}
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-white px-4 text-sm font-semibold text-black transition hover:bg-[#dedede] disabled:cursor-wait disabled:opacity-60">
            {saving ? <LoaderCircle size={16} className="animate-soft-spin" /> : <Save size={16} />}
            {saving ? 'Saving profile' : 'Save changes'}
          </button>
        </div>

        <div className="mb-6 grid gap-4 sm:grid-cols-[1fr_260px]">
          <section className="rounded-2xl border border-[#252525] bg-[#0a0a0a] p-5 sm:p-6">
            <div className="flex items-start gap-4">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-[#333] bg-[#151515] text-lg font-semibold text-white">{initials(profile.name)}</div>
              <div className="min-w-0 flex-1">
                <h2 className="truncate text-lg font-semibold text-white">{profile.name || 'Your profile'}</h2>
                <p className="mt-1 truncate text-sm text-[#888]">{email}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {profile.home_county && <span className="inline-flex items-center gap-1.5 rounded-md border border-[#2a2a2a] px-2.5 py-1 text-xs text-[#aaa]"><MapPin size={12} />{profile.home_county}, Kenya</span>}
                  {profile.role_families.slice(0, 3).map((family) => <span key={family} className="rounded-md border border-[#2a2a2a] px-2.5 py-1 text-xs text-[#aaa]">{families.find(([key]) => key === family)?.[1] || family}</span>)}
                </div>
              </div>
            </div>
          </section>
          <section className="rounded-2xl border border-[#252525] bg-[#0a0a0a] p-5" aria-label="Profile completeness">
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-medium text-[#ddd]">Profile strength</span>
              <span className="text-sm font-semibold tabular-nums text-white">{score?.percent}%</span>
            </div>
            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-[#242424]" role="progressbar" aria-valuenow={score?.percent} aria-valuemin={0} aria-valuemax={100}>
              <div className="h-full rounded-full bg-white transition-all duration-500" style={{ width: `${score?.percent}%` }} />
            </div>
            <p className="mt-3 text-xs leading-5 text-[#777]">{score?.done} of {score?.total} profile details added</p>
          </section>
        </div>

        {(error || notice) && (
          <div className="mb-5 flex items-start gap-3 rounded-xl border border-[#303030] bg-[#121212] px-4 py-3 text-sm text-[#ccc]" role={error ? 'alert' : 'status'} aria-live="polite">
            {error ? <CircleHelp size={17} className="mt-0.5 shrink-0" /> : <Check size={17} className="mt-0.5 shrink-0" />}
            <span className="flex-1">{error || notice}</span>
            <button type="button" onClick={() => { setError(''); setNotice('') }} aria-label="Dismiss message" className="text-[#888] hover:text-white"><X size={16} /></button>
          </div>
        )}

        <div className="grid items-start gap-6 lg:grid-cols-[220px_minmax(0,1fr)]">
          <aside className="sticky top-[99px] z-10 -mx-4 flex gap-1 overflow-x-auto border-b border-[#202020] bg-black px-4 py-2 lg:top-[73px] lg:mx-0 lg:block lg:space-y-1 lg:overflow-visible lg:border-0 lg:bg-transparent lg:p-0">
            {sections.map((item) => {
              const Icon = item.icon
              const selected = section === item.id
              return (
                <button key={item.id} type="button" onClick={() => setSection(item.id)} aria-current={selected ? 'page' : undefined}
                  className={`inline-flex min-h-10 shrink-0 items-center gap-2.5 rounded-lg px-3 text-sm transition-colors lg:flex lg:w-full ${selected ? 'bg-[#171717] text-white ring-1 ring-inset ring-[#2d2d2d]' : 'text-[#888] hover:bg-[#111] hover:text-white'}`}>
                  <Icon size={16} strokeWidth={1.8} />{item.label}
                  {selected && <ChevronRight size={14} className="ml-auto hidden text-[#777] lg:block" />}
                </button>
              )
            })}
          </aside>

          <section key={section} className="animate-rise-in min-w-0 rounded-2xl border border-[#252525] bg-[#0a0a0a] p-5 sm:p-7" aria-labelledby="section-title">
            <div className="sr-only"><h2 id="section-title">{activeSection.label}</h2></div>

            {section === 'overview' && (
              <>
                <SectionHeading eyebrow="Start here" title="Make your profile work for you" copy="Your profile is the control panel for job matching. Add reliable details, review anything found in your CV, and keep your preferences current." />
                <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
                  <div className="space-y-5">
                    <div className="rounded-xl border border-[#292929] bg-[#080808] p-5">
                      <div className="mb-4 flex items-center gap-2"><UserRound size={16} className="text-[#aaa]" /><h3 className="text-sm font-semibold text-white">Basic details</h3></div>
                      <div className="grid gap-4 sm:grid-cols-2">
                        <Field label="Display name"><input className={inputClass} value={profile.name} maxLength={100} onChange={(e) => patch('name', e.target.value)} autoComplete="name" /></Field>
                        <Field label="Email address" hint="Used for your account. Change it through your sign-in provider."><input className={`${inputClass} cursor-not-allowed text-[#888]`} value={email} readOnly /></Field>
                        <Field label="Home county"><select className={selectClass} value={profile.home_county || ''} onChange={(e) => patch('home_county', e.target.value || null)}><option value="">Choose a county</option>{counties.map((county) => <option key={county}>{county}</option>)}</select></Field>
                        <Field label="Town or area" hint="Optional. Used for a more useful commute estimate."><input className={inputClass} value={profile.home_area || ''} maxLength={120} placeholder="For example, Westlands" onChange={(e) => patch('home_area', e.target.value || null)} /></Field>
                      </div>
                    </div>
                    <div className="rounded-xl border border-[#292929] bg-[#080808] p-5">
                      <div className="mb-3 flex items-center gap-2"><Sparkles size={16} className="text-[#aaa]" /><h3 className="text-sm font-semibold text-white">Your matching profile</h3></div>
                      <p className="mb-4 text-xs leading-5 text-[#777]">Choose the kinds of roles you want. Your skills add a second, more specific signal to matching.</p>
                      <div className="flex flex-wrap gap-2">{families.filter(([key]) => profile.role_families.includes(key)).map(([key, label]) => <span key={key} className="rounded-md border border-[#333] bg-[#141414] px-2.5 py-1.5 text-xs text-[#ddd]">{label}</span>)}{profile.role_families.length === 0 && <span className="text-xs text-[#777]">No role areas selected yet.</span>}</div>
                      <button type="button" onClick={() => setSection('skills')} className="mt-4 inline-flex items-center gap-1 text-xs text-[#aaa] hover:text-white">Edit skills and roles <ArrowRight size={13} /></button>
                    </div>
                  </div>
                  <div className="space-y-5">
                    <CvCard cv={cv} uploading={uploading} deleting={deletingCv} inputRef={fileInput} dragging={dragging} setDragging={setDragging} onFile={processFile} onDelete={() => void removeCv()} />
                    {hasSuggestions && <div className="rounded-xl border border-[#292929] bg-[#080808] p-4"><p className="text-xs font-semibold text-white">Suggestions found in this CV</p><p className="mt-2 text-xs leading-5 text-[#888]">{[suggestedCounty, ...suggestedFamilies.map((key) => families.find(([id]) => id === key)?.[1] || key)].filter(Boolean).join(' · ')}</p><button type="button" onClick={() => { if (suggestedFamilies.length) patch('role_families', suggestedFamilies); if (suggestedCounty) patch('home_county', suggestedCounty); setNotice('CV suggestions added. Review them and save your profile.') }} className="mt-3 text-xs text-[#ccc] underline decoration-[#555] underline-offset-4 hover:text-white">Use these suggestions</button></div>}
                    <div className="rounded-xl border border-[#292929] bg-[#080808] p-5">
                      <div className="mb-3 flex items-center gap-2"><BadgeCheck size={16} className="text-[#aaa]" /><h3 className="text-sm font-semibold text-white">Your data stays yours</h3></div>
                      <p className="text-xs leading-5 text-[#888]">The original PDF is read to extract profile details, then discarded. We keep extracted fields and short evidence snippets so you can review what shaped your matches.</p>
                    </div>
                  </div>
                </div>
              </>
            )}

            {section === 'skills' && (
              <>
                <SectionHeading eyebrow="Matching signals" title="Skills and role interests" copy="Skills from your CV and the ones you add here inform relevance. Role areas help us understand what kind of work you want." />
                <div className="space-y-6">
                  <div className="rounded-xl border border-[#292929] bg-[#080808] p-5">
                    <div className="mb-4 flex items-center justify-between gap-3"><div><h3 className="text-sm font-semibold text-white">Your skills</h3><p className="mt-1 text-xs text-[#777]">{profile.skills.length} saved, up to 40</p></div>{Array.isArray(extractedSkills) && extractedSkills.length > 0 && <span className="rounded-md border border-[#303030] px-2 py-1 text-[11px] text-[#999]">CV evidence available</span>}</div>
                    <div className="mb-4 flex flex-wrap gap-2">{profile.skills.map((skill) => <span key={skill} className="inline-flex items-center gap-1.5 rounded-lg border border-[#333] bg-[#121212] py-1.5 pl-3 pr-1.5 text-sm text-[#ddd]">{skill}<button type="button" onClick={() => patch('skills', profile.skills.filter((item) => item !== skill))} aria-label={`Remove ${skill}`} className="rounded p-1 text-[#777] hover:bg-[#252525] hover:text-white"><X size={13} /></button></span>)}{profile.skills.length === 0 && <p className="text-sm text-[#777]">No skills yet. Add a few or upload a CV to get started.</p>}</div>
                    <form onSubmit={addSkill} className="flex gap-2">
                      <input className={inputClass} value={skillInput} maxLength={50} onChange={(e) => setSkillInput(e.target.value)} placeholder="Add a skill, for example SQL" aria-label="Add a skill" />
                      <button type="submit" className="inline-flex min-h-11 shrink-0 items-center gap-2 rounded-lg border border-[#3a3a3a] px-3 text-sm text-white hover:bg-[#171717]"><Plus size={16} /><span className="hidden sm:inline">Add skill</span></button>
                    </form>
                  </div>
                  <div className="rounded-xl border border-[#292929] bg-[#080808] p-5">
                    <h3 className="mb-1 text-sm font-semibold text-white">Role areas</h3><p className="mb-4 text-xs text-[#777]">Select all areas you would consider.</p>
                    <div className="flex flex-wrap gap-2">{families.map(([key, label]) => <TogglePill key={key} label={label} checked={profile.role_families.includes(key)} onClick={() => toggleValue('role_families', key)} />)}</div>
                  </div>
                  <div className="rounded-xl border border-[#292929] bg-[#080808] p-5">
                    <h3 className="mb-1 text-sm font-semibold text-white">Experience level</h3><p className="mb-4 text-xs text-[#777]">This is a matching filter, not an estimate of your worth.</p>
                    <div className="flex flex-wrap gap-2">{roleLevels.map(([key, label]) => <TogglePill key={key} label={label} checked={profile.entry_fits.includes(key)} onClick={() => toggleValue('entry_fits', key)} />)}</div>
                  </div>
                  {cv && Array.isArray(extractedSkills) && extractedSkills.length > 0 && <p className="text-xs leading-5 text-[#777]">Extracted skills are shown as evidence, not certainty. Remove anything that is not yours. CV detected: {extractedSkills.join(', ')}.</p>}
                </div>
              </>
            )}

            {section === 'experience' && (
              <>
                <SectionHeading eyebrow="Evidence, not assumptions" title="Experience and education" copy="We only show details the text extractor could support. Review the original wording in the evidence line and correct your profile if something was misread." />
                {cv ? (
                  <div className="space-y-4">
                    <div className="flex flex-col justify-between gap-3 rounded-xl border border-[#292929] bg-[#080808] p-4 sm:flex-row sm:items-center">
                      <div className="flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-lg border border-[#303030] bg-[#141414]"><FileText size={17} className="text-[#bbb]" /></span><div><p className="text-sm font-medium text-white">{cv.filename}</p><p className="mt-1 text-xs text-[#777]">Processed {new Date(cv.created_at).toLocaleDateString()}</p></div></div>
                      <button type="button" onClick={() => setSection('overview')} className="text-left text-xs text-[#aaa] hover:text-white">Replace CV <ArrowRight size={13} className="ml-1 inline" /></button>
                    </div>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <EvidenceCard title="Recent role titles" value={titles} cv={cv} field="titles" />
                      <EvidenceCard title="Experience duration" value={experience} cv={cv} field="experience" />
                      <EvidenceCard title="Education" value={education} cv={cv} field="education" />
                      <EvidenceCard title="Location found in CV" value={location} cv={cv} field="location" />
                    </div>
                    <div className="rounded-xl border border-[#292929] bg-[#080808] p-4 text-xs leading-5 text-[#777]">These are extracted highlights, not a complete employment history. Nothing is invented when a CV does not contain clear dates or headings.</div>
                  </div>
                ) : (
                  <div className="rounded-xl border border-dashed border-[#383838] bg-[#080808] px-5 py-12 text-center">
                    <BriefcaseBusiness size={22} className="mx-auto mb-3 text-[#777]" /><h3 className="text-sm font-medium text-white">No experience evidence yet</h3><p className="mx-auto mt-2 max-w-sm text-xs leading-5 text-[#777]">Upload a text-based PDF CV and we will show the experience, education, and role terms we can reliably extract.</p><button type="button" onClick={() => setSection('overview')} className="mt-5 rounded-lg border border-[#3a3a3a] px-4 py-2 text-sm text-white hover:bg-[#171717]">Add a CV</button>
                  </div>
                )}
              </>
            )}

            {section === 'preferences' && (
              <>
                <SectionHeading eyebrow="Your constraints" title="What makes a role workable?" copy="These preferences are saved to your profile and used as ranking constraints. Leave optional filters broad if you want to see more opportunities." />
                <div className="space-y-5">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Field label="Home county"><select className={selectClass} value={profile.home_county || ''} onChange={(e) => patch('home_county', e.target.value || null)}><option value="">Any county</option>{counties.map((county) => <option key={county}>{county}</option>)}</select></Field>
                    <Field label="Town or area"><input className={inputClass} value={profile.home_area || ''} maxLength={120} placeholder="For example, CBD" onChange={(e) => patch('home_area', e.target.value || null)} /></Field>
                    <Field label="Maximum commute" hint="Approximate straight-line distance, not a travel-time estimate."><select className={selectClass} value={profile.max_commute_km ?? ''} onChange={(e) => patch('max_commute_km', e.target.value ? Number(e.target.value) : null)}><option value="">No commute limit</option>{[5, 10, 15, 25, 40, 80].map((km) => <option key={km} value={km}>{km} km</option>)}</select></Field>
                    <Field label="Minimum monthly pay" hint="Optional. Leave blank to include roles where pay is not stated."><div className="relative"><span className="absolute left-3.5 top-3 text-sm text-[#777]">KES</span><input className={`${inputClass} pl-14`} type="number" min="0" step="1000" value={profile.min_monthly_pay ?? ''} placeholder="Not set" onChange={(e) => patch('min_monthly_pay', e.target.value ? Number(e.target.value) : null)} /></div></Field>
                  </div>
                  <div className="rounded-xl border border-[#292929] bg-[#080808] p-5">
                    <h3 className="mb-3 text-sm font-semibold text-white">Work arrangement</h3><div className="flex flex-wrap gap-2">{workModes.map(([key, label]) => <TogglePill key={key} label={label} checked={profile.work_modes.includes(key)} onClick={() => toggleValue('work_modes', key)} />)}</div><label className="mt-4 flex cursor-pointer items-start gap-3 border-t border-[#222] pt-4"><input type="checkbox" className="mt-0.5 h-4 w-4 accent-white" checked={profile.include_remote} onChange={(e) => patch('include_remote', e.target.checked)} /><span><span className="block text-sm text-[#ddd]">Include remote roles</span><span className="mt-1 block text-xs text-[#777]">Remote roles do not use your commute limit.</span></span></label>
                  </div>
                  <div className="rounded-xl border border-[#292929] bg-[#080808] p-5">
                    <h3 className="mb-3 text-sm font-semibold text-white">Employment type</h3><p className="mb-4 text-xs text-[#777]">Select none to include every type.</p><div className="flex flex-wrap gap-2">{workTypes.map(([key, label]) => <TogglePill key={key} label={label} checked={profile.employment_types.includes(key)} onClick={() => toggleValue('employment_types', key)} />)}</div>
                  </div>
                  <Field label="Closing date window" hint="Optional. Hide roles that close later than the time window you can act within."><select className={selectClass} value={profile.deadline_within_days ?? ''} onChange={(e) => patch('deadline_within_days', e.target.value ? Number(e.target.value) : null)}><option value="">No deadline limit</option><option value="7">Within 7 days</option><option value="14">Within 14 days</option><option value="30">Within 30 days</option><option value="90">Within 90 days</option></select></Field>
                </div>
              </>
            )}

            {section === 'account' && (
              <>
                <SectionHeading eyebrow="Account and privacy" title="Your account" copy="Manage the name shown in Kazi-Kasi and understand what is saved when you add a CV." />
                <div className="space-y-4">
                  <div className="rounded-xl border border-[#292929] bg-[#080808] p-5"><h3 className="mb-4 text-sm font-semibold text-white">Personal details</h3><div className="grid gap-4 sm:grid-cols-2"><Field label="Display name"><input className={inputClass} value={profile.name} maxLength={100} onChange={(e) => patch('name', e.target.value)} /></Field><Field label="Sign-in email"><input className={`${inputClass} cursor-not-allowed text-[#888]`} value={email} readOnly /></Field></div></div>
                  <div className="rounded-xl border border-[#292929] bg-[#080808] p-5"><h3 className="mb-2 text-sm font-semibold text-white">CV data</h3><p className="text-xs leading-5 text-[#888]">Kazi-Kasi stores extracted fields and short evidence snippets, not the uploaded PDF itself. You can delete saved CV details at any time. Your manually saved skills remain in your profile after deletion.</p></div>
                  <button type="button" onClick={() => { logout(); router.replace('/auth') }} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-[#333] px-3.5 text-sm text-[#bbb] transition hover:border-[#666] hover:text-white"><LogOut size={15} />Sign out</button>
                </div>
              </>
            )}

            <div className="mt-8 flex flex-col-reverse justify-between gap-3 border-t border-[#222] pt-5 sm:flex-row sm:items-center">
              <span className="text-xs text-[#777]">Changes are private to your account.</span>
              <button type="button" onClick={() => void save()} disabled={saving} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-white px-4 text-sm font-semibold text-black transition hover:bg-[#dedede] disabled:cursor-wait disabled:opacity-60">
                {saving ? <LoaderCircle size={15} className="animate-soft-spin" /> : <Save size={15} />}{saving ? 'Saving' : 'Save profile'}
              </button>
            </div>
          </section>
        </div>
      </div>
      <input ref={fileInput} type="file" accept="application/pdf,.pdf" className="sr-only" onChange={(event) => void processFile(event.target.files?.[0])} aria-label="Choose a PDF CV" />
    </main>
  )
}

function CvCard({ cv, uploading, deleting, inputRef, dragging, setDragging, onFile, onDelete }: {
  cv: ProfileCv | null
  uploading: boolean
  deleting: boolean
  inputRef: React.RefObject<HTMLInputElement | null>
  dragging: boolean
  setDragging: (value: boolean) => void
  onFile: (file?: File) => void
  onDelete: () => void
}) {
  const fieldCount = cv ? Object.keys(cv.fields || {}).length : 0
  return (
    <div className="rounded-xl border border-[#292929] bg-[#080808] p-5" onDragOver={(event) => { event.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); onFile(event.dataTransfer.files?.[0]) }}>
      <div className="mb-4 flex items-start justify-between gap-3"><div><div className="mb-1.5 flex items-center gap-2"><FileText size={16} className="text-[#aaa]" /><h3 className="text-sm font-semibold text-white">CV and resume</h3></div><p className="text-xs leading-5 text-[#777]">A PDF can help us identify skills and experience for your matches.</p></div><span className="rounded-md border border-[#333] px-2 py-1 text-[10px] uppercase tracking-wide text-[#888]">PDF</span></div>
      {cv ? (
        <div className="rounded-lg border border-[#303030] bg-[#111] p-3.5">
          <div className="flex items-start gap-3"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-[#333] bg-[#191919]"><FileText size={16} className="text-[#bbb]" /></span><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium text-white" title={cv.filename}>{cv.filename}</p><p className="mt-1 text-xs text-[#777]">{fieldCount} extracted fields · {cv.chars.toLocaleString()} characters</p></div><span aria-label="Processed" title="Processed"><Check size={15} className="text-[#aaa]" /></span></div>
          <div className="mt-3 flex gap-2 border-t border-[#272727] pt-3"><button type="button" onClick={() => inputRef.current?.click()} disabled={uploading} className="text-xs text-[#bbb] hover:text-white">Replace PDF</button><button type="button" onClick={onDelete} disabled={deleting} className="ml-auto inline-flex items-center gap-1 text-xs text-[#888] hover:text-white disabled:opacity-50">{deleting ? <LoaderCircle size={13} className="animate-soft-spin" /> : <Trash2 size={13} />}Remove</button></div>
        </div>
      ) : (
        <button type="button" onClick={() => inputRef.current?.click()} disabled={uploading} className={`flex min-h-36 w-full flex-col items-center justify-center rounded-lg border border-dashed px-4 py-5 text-center transition-colors ${dragging ? 'border-white bg-[#171717]' : 'border-[#393939] hover:border-[#777] hover:bg-[#101010]'} disabled:cursor-wait`}>
          {uploading ? <LoaderCircle size={20} className="mb-3 animate-soft-spin text-white" /> : <Upload size={20} className="mb-3 text-[#aaa]" />}
          <span className="text-sm font-medium text-white">{uploading ? 'Reading and extracting your PDF' : 'Upload a CV'}</span>
          <span className="mt-1.5 text-xs text-[#777]">Drop a PDF here or browse. Maximum 5 MB.</span>
        </button>
      )}
      {uploading && cv && <div className="mt-3 flex items-center gap-2 text-xs text-[#999]" role="status"><LoaderCircle size={13} className="animate-soft-spin" />Updating your CV details</div>}
      <p className="mt-3 flex items-start gap-1.5 text-[11px] leading-5 text-[#777]"><ShieldCheck size={13} className="mt-0.5 shrink-0" />PDF text is processed securely. The original file is not retained.</p>
    </div>
  )
}

function EvidenceCard({ title, value, cv, field }: { title: string; value: string | string[] | undefined; cv: ProfileCv; field: string }) {
  const display = Array.isArray(value) ? value.join(', ') : value
  const evidence = cv.fields[field]?.evidence
  const confidence = cv.fields[field]?.confidence
  return (
    <div className="rounded-xl border border-[#292929] bg-[#080808] p-4">
      <p className="text-xs font-medium text-[#888]">{title}</p>
      <p className="mt-2 text-sm leading-6 text-white">{display || 'Not found in this CV'}</p>
      {evidence && <p className="mt-3 border-t border-[#222] pt-3 text-xs leading-5 text-[#777]">Evidence: “{evidence}”</p>}
      {confidence !== undefined && <p className="mt-2 text-[10px] uppercase tracking-wide text-[#666]">Extraction confidence {Math.round(confidence * 100)}%</p>}
    </div>
  )
}
