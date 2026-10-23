# KAZI-KASI: TEAM ONBOARDING BRIEF
## Design, Research, UI/UX & 3D Department — First Day Packet

---

**Document:** v1.0 — Full onboarding  
**Date:** 23 October 2026  
**Product:** Kazi-Kasi (kazi-kasi-app.vercel.app)  
**Owner:** Flex Brandon  
**Audience:** Incoming department team (first day, zero context assumed)  
**Read time:** 25 minutes  
**Then:** 6 weeks of execution  

---

## PART 0: WELCOME

You've been contracted to rebuild Kazi-Kasi. Before you design anything, you need to understand three things:

1. **What the product is today** — honestly, not the pitch deck version
2. **What market it serves** — Kenya, specifically, with East Africa next
3. **What "better" actually means** — not prettier, not more features, but *functional, trustworthy, craft-grade*

This document gets you from zero context to ready to execute. Read it in order. Ask questions about anything that isn't clear. The owner expects you to push back when something doesn't make sense — that's better than shipping something you didn't believe in.

---

## PART 1: WHAT IS KAZI-KASI?

### The Product (Plain English)

Kazi-Kasi is a job discovery platform for Kenya. The name is Kiswahili for "fast work."

**What it does:**
- Pulls job listings from multiple Kenyan sources (BrighterMonday, Fuzu, company career pages, government boards, UN jobs, etc.) into one feed
- Ranks those jobs against a user's profile (skills, location, experience, pay floor)
- Lets users save jobs, track applications, and apply externally
- Sends WhatsApp digests of new matching jobs
- Parses uploaded CVs to auto-match against listings
- Tracks job freshness — tells you when a listing was last verified alive

**What it is NOT:**
- Not a job board where employers post directly (yet)
- Not a resume builder (like Mokaru's resume tool)
- Not a LinkedIn-style social network
- Not an ATS (Applicant Tracking System) for employers

**The core insight:** Kenya's job market is fragmented. Jobs live on BrighterMonday, Fuzu, individual company sites, government portals, UN boards, Facebook groups, WhatsApp chains. A job seeker has to check 6-10 sources daily. Kazi-Kasi aggregates, ranks, and freshness-checks them in one place.

### Who Uses It

Three primary personas:

1. **The Fresh Graduate (Amina, 22, Nairobi)** — Just finished university. Limited experience. Needs entry-level roles. Highly mobile. Data-conscious. Applies to everything she's eligible for. Wants clarity on salary ("does this pay enough to live in Nairobi?").

2. **The Mid-Career Switcher (Brian, 31, Mombasa)** — 5-8 years experience. Knows what he's worth. Willing to relocate for the right role. Needs salary transparency and role quality signals. Skeptical of vague job postings.

3. **The Senior Professional (Wanjiru, 38, Nairobi)** — Director/manager level. Passive job seeker. Wants curated, high-quality matches. Cares about company reputation. Time-poor — needs signal, not noise.

### What Already Exists (Technical Stack)

**Backend:** Python 3.11, Flask-like custom HTTP server  
**Database:** SQLite (dev) / PostgreSQL (production via Neon)  
**Deployment:** Vercel  
**Rendering:** Server-side HTML — NO React, NO Next.js, NO frontend framework  
**Styling:** Inline CSS in a Python string (yes, really — one big `STYLE = """..."""` block)  
**Authentication:** OAuth (Google) via PKCE  
**Sources:** 13 aggregators (BrighterMonday, Fuzu, MyJobMag Kenya, JobWebKenya, KenyaJobs, UNJobsKenya, DevexKenya, etc.)  
**CV parsing:** Regex-based keyword extraction (basic, not AI)  
**Feed:** Server-rendered HTML, no client-side state  

**What this means for you as a designer:**
- Every screen you design must work as server-rendered HTML
- CSS-only animations where possible
- No React component libraries
- Performance is critical — this runs on KES 15,000 Android phones on 3G
- You CAN add JS for interactivity, but it must be lightweight and non-blocking

---

## PART 2: CURRENT STATE AUDIT (HONEST)

### What Works (Keep These)

1. **The ranking algorithm** — Matches jobs to user profiles using role families, experience fit, salary floor, commute radius. It's good. Don't throw it away.

2. **The freshness system** — Every job has a last-checked timestamp. Stale jobs are flagged. This is a trust feature. Keep it visible.

3. **Multi-source aggregation** — 13 sources feeding one feed. This is the core value prop. Users don't have to check 10 sites.

4. **The profile system** — Multiple profiles per user (Amina, Brian, Otieno, Wanjiru) with different role families, commute radii, pay floors. Good UX for households where multiple people job-hunt.

5. **WhatsApp digest** — Daily/weekly digests of new matching jobs via WhatsApp. Kenyans live on WhatsApp. This channel is right.

6. **CV parsing** — Extracts name, email, phone, skills, experience, education from uploaded CVs. Basic but functional. Needs to become great, not be replaced.

7. **OAuth sign-in (Google)** — Works. Stores given_name, family_name, picture, locale. Currently underutilized — needs to actually USE this data.

### What Doesn't Work (Fix These)

1. **Visual design** — Currently a beige/cream "warm palette" that looks like a 2020 blog theme. No visual hierarchy. No craft. No personality. The design tokens are defined but never emotionally committed to.

2. **Job cards** — All look identical. No visual differentiation by match quality, freshness, salary, or application stage. A great match and a stale mismatch look the same.

3. **No application tracking** — User saves a job. Then what? There's no "Applied," "Interviewing," "Offer" pipeline. Jobs disappear into a void.

4. **CV parsing is dumb** — Regex keyword extraction. No confidence scores. No OCR for scanned PDFs. No section detection. No match breakdown against specific jobs.

5. **Personalization is cosmetic** — Google sign-in stores name and picture but the UI barely uses them. "Hey [First Name]" is table stakes, not a feature.

6. **No salary transparency** — Most job cards don't show salary. When they do, it's buried. This is the #1 thing job seekers look for (Indeed's own research: 90% of new jobs on Indeed include salary; Kenyan platforms lag hard on this).

7. **Mobile experience** — Not optimized. The same desktop layout squishes down. No mobile-specific patterns. No bottom nav. No swipe gestures.

8. **No 3D, no spatial design, no motion craft** — It's flat HTML. That's fine as a starting point but the brief demands spatial richness.

### What's Missing Entirely (Build These)

1. **Application tracker** — A full pipeline: watchlist → saved → applied → screening → interview → offer → rejected. With notes, follow-ups, recruiter contacts.

2. **Match breakdown** — Transparent scoring: "Your CV matches 3/5 keywords for this role. Missing: React, AWS." (Mokaru pattern.)

3. **Smart search** — Search bar with suggestions pulled from CV data. Not just text matching — semantic suggestions.

4. **Salary estimator** — Even when the job posting doesn't list salary, show market rates for that role/county/experience.

5. **Company pages** — Basic employer profiles with reviews, interview questions, salary data. (Glassdoor pattern.)

6. **Follow-up system** — Smart reminders based on application stage and time elapsed.

7. **Funnel dashboard** — User sees their own conversion: applied 40, screening 8, interview 3, offer 1.

---

## PART 3: THE MARKET — WHAT YOU MUST UNDERSTAND

### Kenya's Job Market (Context You Can't Skip)

- **Population:** 55 million, 75% under age 35
- **Unemployment:** ~7% official (youth unemployment estimated 20-40%)
- **Internet penetration:** ~40%, growing fast
- **Mobile-first:** 80%+ of internet users access only via phone
- **Data costs:** Relatively high. Users are sensitive to page weight.
- **WhatsApp:** The default communication channel. More important than email for many users.
- **M-Pesa:** Mobile money. Most salaries are paid via M-Pesa. Salary in KES, not USD.
- **Languages:** Swahili (national), English (official/business), Sheng (urban youth slang)
- **Counties:** 47 counties. Nairobi is the economic hub but not the only one. Mombasa, Kisumu, Nakuru, Eldoret are significant.
- **Informal economy:** ~83% of employment is informal. Not every "job" has a formal title or posting.
- **Trust deficit:** Job scams are common. Users are skeptical. Transparency is a trust signal.
- **Relationship-driven hiring:** Referrals and personal networks matter more than in Western markets.

### The 15 Platforms You Must Study

You don't need to memorize these. You need to understand the PATTERN each one represents and what to borrow (and what to reject).

#### TIER 1: THE SCALE LEADERS (Study for efficiency, not aesthetics)

**1. Indeed** — 400M monthly visits, 61% market share, $7.4B revenue
- **What they do right:** Salary upfront (the single highest-impact design decision in job search). Horizontal filter chips. Two-column list+detail layout. Stats bar at top of feed. "Apply on Indeed" one-click flow.
- **What they do wrong:** Visually stuck in 2019. Beige-green corporate palette. Cluttered cards. No visual hierarchy between strong and weak matches.
- **What to borrow:** Salary prominence. Filter chip pattern. Stats bar. One-click apply flow.
- **What to reject:** The entire visual system. The generic "job board" feel.

**2. LinkedIn** — 87M monthly visits, 13% market share, $17.8B revenue
- **What they do right:** Profile-based matching (uses your data to surface relevant jobs). Network signals ("3 connections work here"). Professional credibility through endorsements. Save-to-tracker from search results.
- **What they do wrong:** Bloated feed. Blue corporate palette. Influencer noise. Too many features competing for attention.
- **What to borrow:** Data-driven personalization. Professional trust signals. The "save from search" pattern.
- **What to reject:** The feed noise. The "influencer" layer. The heavy nav.

**3. ZipRecruiter** — 39M monthly visits, $449M revenue, 89% gross margin
- **What they do right:** 81% of traffic is mobile — they designed for it. Fast bulk applying. One-post-distributes-everywhere concept for employers. Subscription model (predictable revenue).
- **What they do wrong:** Aggressive employer-side UX. Subscription wall locks out casual users.
- **What to borrow:** Mobile-first patterns. Speed as respect. The apply-in-one-tap flow.
- **What to reject:** The paywall for job seekers.

**4. Glassdoor** — 27M monthly visits, $320M revenue (now merged into Indeed)
- **What they do right:** Salary transparency (actual numbers from real employees). Company culture insights. Interview question databases. Trust through radical transparency.
- **What they do wrong:** Forced-account wall to read reviews. UI that degraded after Indeed merger. Review manipulation.
- **What to borrow:** Transparency as a feature. Salary data from employees, not employers. Interview prep content.
- **What to reject:** The account wall. The manipulation.

**5. Jooble** — 34M monthly visits, 5% market share
- **What they do right:** Clean search interface. Salary filters as first-class citizens. The discipline of what they leave out.
- **What to borrow:** Restraint. The search-first UX.
- **What to reject:** Nothing — study them for minimalism.

#### TIER 2: REGIONAL SPECIALISTS (Study for localization)

**6. JobStreet** — 16.6M visits (Asia Pacific). Regional localization done right. Southeast Asia has similar trust dynamics to East Africa.

**7. Talent.com** — 14.6M visits. Salary comparison tools. Job alerts that don't spam. Clean typography.

**8. Hellowork** — 9.2M visits, fastest growing at 29% YoY. Mobile-first without being mobile-only. Growth comes from speed, not features. **Key insight: they're growing because everyone else is slow.**

**9. Monster** — 7.2M visits. Company profile pages. Career advice content as SEO moat. Brand has aged poorly — study what not to do.

**10. FlexJobs** — 6.6M visits, curated paid. Every listing hand-verified. Scam-free guarantee. **Key insight: trust is the most defensible feature in job search.** Paid users trust the platform because the platform does work they can't do themselves.

#### TIER 3: WORKFLOW INNOVATORS (Study for efficiency patterns)

**11. Mokaru (mokaru.ai)** — THE efficiency benchmark. Study this harder than any other platform.
- Browser extension saves jobs with one click from any job board
- Auto-prep tailors resume to each job using ONLY real experience (never fabricates)
- Match score is TRANSPARENT — shows matching AND missing keywords
- Application tracker: watchlist → saved → applied → screening → interview → offer → rejected
- Per-application: notes, recruiter contact, follow-up reminders, salary as seen, resume version sent
- Resume quality score with specific action items
- Cover letter generation from real experience
- **Key insight:** The job search is a CRM problem. Most platforms treat it as a search problem. Kazi-Kasi should treat it as both.
- **What to borrow:** Every workflow pattern above.
- **What to reject:** The resume builder itself (we're a job platform, not a resume tool). The browser extension (different product category).

**12. Wellfound (formerly AngelList)** — 3.8M visits. Startup culture positioning. Equity/salary transparency. Niche beats generalist.

**13. Welcome to the Jungle** — France. High interview rates. Employer branding that's actually beautiful. Company pages that look like magazine spreads. **Key insight: if a company page is ugly, candidates assume the company is ugly.**

**14. Seek** — 3.3M visits. Regional market dominance through localization. Don't try to be global — be the best in your geography.

**15. RemoteOK** — 752K visits. Fully remote focus. The niche IS the brand.

---

## PART 4: WHAT WE'RE BUILDING — THE VISION

### One-Sentence Vision

> **Kazi-Kasi is the first job platform that feels like it was hand-built by someone who actually understands the Kenyan job market — warm, human, visually rich, spatially immersive — and treats every job seeker like a person with a story, not a data point.**

### The Non-Negotiable Principles

1. **Salary is trust.** Show it on every card, big, upfront. If the posting doesn't have it, show market rates. No hiding, no "competitive salary" cop-outs.

2. **Match is transparent.** When we say "this job matches your profile," show WHY. Matching keywords. Missing keywords. Confidence levels. Never fabricate a match.

3. **The job search is a CRM.** Every application has a stage, a timestamp, a follow-up plan, a recruiter contact. Users should never lose track of where they are in the pipeline.

4. **Speed is respect.** Every extra click is a sign you don't value the user's time. One-click apply when the user has a CV. Fast load times. Minimal friction.

5. **Data privacy as a feature.** We collect data (Google sign-in, CV, applications) — we use it to make the experience better for the user, not to sell to employers. This is a standing promise.

6. **Local is the brand.** We serve Kenya first. We speak Swahili and English and Sheng. We know counties, not just cities. We optimize for 3G, not fiber.

7. **Craft is the differentiator.** The design must feel hand-built, not generated. Typography with character. Color with warmth. Motion with purpose. 3D with hierarchy, not decoration.

### The Anti-Patterns — Hard Constraints

If your design includes any of these, it's wrong:

- ✗ Neon colors or glowing effects
- ✗ "AI-powered" language in the UI (use "smart matching" or just show the match, don't say AI)
- ✗ Generic "modern SaaS" layouts (hero → features → pricing → CTA)
- ✗ Rounded corners on everything (use radius intentionally, not as a default)
- ✗ Gradient backgrounds that look like a crypto landing page
- ✗ Stock photos of diverse people high-fiving
- ✗ Cartoon illustrations of people at computers
-  The word "empower" anywhere
- ✗ "Revolutionizing," "disrupting," or "transforming"
- ✗ Pure white backgrounds (warm off-white only — white is hospital, warm is home)
- ✗ Roboto, Open Sans, or Poppins as primary typeface (find something with character)
- ✗ A nav bar that looks like every other SaaS product
- ✗ Cards that all look identical (vary by stage, importance, freshness)
- ✗ A mobile experience that's just the desktop shrunk
-  Safari animals, maasai patterns, or "African" stock imagery (local ≠ cliché)

---

## PART 5: FUNCTIONAL REQUIREMENTS

These are the features the rebuild MUST include. They come from the research above, not from opinion.

### 5.1 The Feed (Primary Surface)

- **Two-column layout** (desktop ≥1024px): Job list (left, ~70%), context/filters (right, ~30%). Collapses to single column on mobile with filters accessible via horizontal chip scroll.
- **Salary on every card:** The single most important number after the job title. Format: `KES 50,000 – 80,000/month`. If salary is unknown, show market range for that role/county or say "Salary not listed."
- **Match breakdown (Mokaru pattern):** For users with a CV, every card shows: `✓ 4 match | ✗ 2 missing` with the specific matching and missing keywords. Computed from real CV data only — never fabricate.
- **Application stage badge:** Every card shows current status: `WATCHING` → `SAVED` → `APPLIED` → `SCREENING` → `INTERVIEW` → `OFFER` → `REJECTED`. Color-coded pill. This turns the feed into a live status board.
- **1-click apply:** If user has a saved CV, the apply button is one tap. No forms. No "fill in your experience again" nonsense.
- **Prominent search bar:** At the top of the feed, above the filter chips. Instant suggestions pulled from CV skills, location, experience level.
- **Horizontal filter chips:** Not a sidebar. `All jobs`, `Remote`, `Hybrid`, `Past week`, `Salary shown`, `Easy apply`. Active state styling. Horizontal scroll on mobile.
- **Stats bar at top:** Four metrics in a row: Jobs matching, Live jobs, Closing soon, Applied. Like Indeed's top metrics row.
- **Freshness indicator:** Every card shows when it was last checked. Stale jobs get a visual warning.
- **Source attribution:** Show which source(s) the job came from. Trust signal.

### 5.2 The Application Tracker (Mokaru Pipeline)

- **Full pipeline view:** Visual board (Kanban columns OR sortable list) showing all applications across 8 stages.
- **Per-application data:** Notes, recruiter name, recruiter email, follow-up reminder date, salary as seen on listing, resume version sent, source URL of original posting.
- **Funnel statistics:** Dashboard showing user's own conversion: applied 40 → screening 8 → interview 3 → offer 1. Motivates continued effort.
- **Smart follow-up reminders:** Based on stage and time elapsed. "You applied 14 days ago — consider following up."
- **Status transitions:** User can move applications between stages manually. System auto-advances when it detects signals (e.g., user marks "applied" → system prompts for follow-up date in 7 days).

### 5.3 The CV System

- **Parse in under 3 seconds:** PDF, DOC, DOCX. Show live progress: uploading → extracting → analyzing → complete.
- **Confidence scores per field:** High (✓), Medium (~), Low (?). User can verify low-confidence fields.
- **Section detection:** Auto-detect education, experience, skills, contact info, certifications.
- **OCR for scanned PDFs:** Don't just fail — render the page and attempt OCR. If OCR fails, tell the user why and suggest pasting text directly.
- **Match breakdown against jobs:** When user views a job, show transparent comparison of their CV keywords vs job requirements.
- **Multi-version CVs:** User can have multiple tailored CV versions. System tracks which version was sent to which job.

### 5.4 Personalization (Use the Data You Collect)

- **Google sign-in data:** Use given_name, family_name, picture, locale. Don't just store it — use it.
- **Personalized greeting:** "Hey Flex" not "Account" or "Guest."
- **Profile picture in navigation and account page:** When signed in, show it. This builds recognition and trust.
- **Smart search suggestions:** Pull from CV skills, location, experience level. "Try: Django, Nairobi, Mid-level."
- **Explained recommendations:** "Recommended because you have Django experience" — show the reasoning.
- **Email pre-fill:** Use Google email for forms and CV parsing.

### 5.5 The Company Layer (Glassdoor Pattern)

- **Employer profiles:** Even basic ones. Company name, logo, location, industry, size.
- **Salary data:** Aggregated from job postings and (eventually) user submissions. Show market range for role + county.
- **Interview questions:** Curated from user submissions. "People who interviewed here reported questions about X, Y, Z."
- **Culture signals:** Work mode (remote/hybrid/onsite), benefits tags, employee count.

---

## PART 6: DESIGN DIRECTION

This is where the creative brief lives. The functional requirements above tell you WHAT to build. This section tells you HOW it should feel.

### 6.1 The Creative Spine

**Spatial Design (3D)**
- The feed is not a flat list. Cards exist in space — they have weight, elevation, shadow that responds to scroll position.
- Z-depth layers: background texture, mid-ground cards, foreground modals. Parallax on scroll.
- Hero sections that breathe — not static banners, but living surfaces. Subtle motion responding to cursor/touch.
- 3D is hierarchy, not decoration. Use it to tell the user what matters. The most relevant job should feel closest.

**Typography as Architecture**
- Big, confident display type for headlines. Serif or editorial sans. NOT Inter, NOT Roboto. Something with character.
- Test: does the typeface have personality at 48px? Does it stay legible at 14px? If it fails either, reject it.
- Body type: 16px+, line-height 1.6+. Let text breathe.
- Use type weight for hierarchy, not just size. A 600-weight headline at 24px can be more impactful than a 700-weight at 32px.
- Kenyan context: Test for readability with Sheng and mixed-language copy.

**Color: Warm, Earthy, Confident**
- Primary: Deep, rich tones that feel like soil or wood, not like a tech brand. Examples: #2C1810 (deep brown), #1A1A2E (night blue), #3D2B1F (espresso).
- Accent: Something alive. Coral, terracotta, saffron. NOT electric blue. NOT neon anything.
- Background: Warm off-white (#FAF7F2, #F5F0E8) — never pure white. White is hospital. Warm is home.
- Status colors: Green for success (sage, not lime). Amber for warning (honey, not caution tape). Red for danger (brick, not alarm).

**Texture & Material**
- Film grain: subtle, not noisy. Breaks up the flatness of digital.
- Paper-like surfaces: Cards feel like they're made of something. Subtle texture, subtle shadow, subtle response to hover.
- No glassmorphism unless it serves a function (backdrop blur for overlays, yes; decorative glass, no).

**Motion**
- 200-300ms for UI transitions. Fast enough to feel responsive, slow enough to feel intentional.
- Ease-out curves. Things arrive with momentum and settle naturally.
- Scroll-triggered reveals: cards fade up as they enter viewport. Stagger by 30ms for lists.
- Micro-interactions: Save button compresses on click. Match score fills like a progress bar. Stage badge pulses subtly when updated.
- Rule: Every animation must answer "What is this teaching the user?" If it can't answer, cut it.

**Layout: Editorial, Not Corporate**
- Asymmetric grids. Not everything needs to be centered and symmetrical.
- Generous whitespace. Let the design breathe.
- Mixed media: text alongside imagery alongside data visualizations. Break up "card, card, card" monotony.
- Magazine-style homepage: hero feature, secondary stories, data spotlight.

### 6.2 References — Study for Craft, Not to Copy

**Positive references:**
- **Aesop.com** — Editorial layout. Restraint. Typography as design.
- **Linear.app** — Motion craft. Micro-interactions that feel physical.
- **Arc Browser** — Spatial design. 3D depth used for hierarchy.
- **Stripe.com/docs** — Information design at scale. Complex data made beautiful.
- **The New York Times digital edition** — Editorial hierarchy. Mixed media.
- **Apple.com product pages** — Scroll storytelling. Product as hero.
- **Pitch.com** — Playful without being childish. Color with purpose.
- **Notion marketing pages** — Clean but not sterile.
- **Framer.com** — Interactive demos that teach through doing.

**Negative references (study what NOT to do):**
- Any crypto/Web3 landing page
- Any AI startup homepage from 2024
- Any government website
- Any job board from before 2020 (unless studying what to avoid)

### 6.3 Kenya-Specific Design Considerations

- **Mobile-first, always:** 80%+ of users are on phones. Design for 320px width first, then enhance.
- **Performance as design:** Page weight matters. Every KB is money for the user. Optimize aggressively.
- **Data sensitivity:** Show data usage indicators where relevant. Don't auto-play video. Lazy-load images.
- **County as identity:** Location is more than a filter — it's part of who the user is. Design for this.
- **WhatsApp integration points:** The digest is WhatsApp-delivered. Consider deep links back to the app.
- **M-Pesa salary display:** Consider showing salary in ways that map to real purchasing power. "KES 80,000/month = ~KES 2,600/day" might be more meaningful.

---

## PART 7: TECHNICAL CONSTRAINTS

You must design within these constraints. They are not negotiable.

1. **Server-rendered HTML.** No React, no Next.js, no client-side framework. The backend is Python with a custom HTTP server that returns HTML strings. Your designs must work as server-rendered pages.

2. **CSS-only animations where possible.** JS for interactivity is fine, but prefer CSS transitions and animations. They're faster and don't block the main thread.

3. **SVG for icons.** No icon fonts. No heavy raster icon assets. Custom icons designed for the product.

4. **3D must be GPU-efficient.** WebGL is allowed but use sparingly. Pre-baked assets where possible. Performance budget: 3D elements must not drop frame rate below 30fps on a mid-range Android.

5. **All assets must be cachable.** No uncachable JS blobs. Static assets have long cache headers.

6. **Performance budgets:**
   - First paint: under 1.5s on 4G
   - Time to interactive: under 3s on 4G
   - Total page weight: under 500KB for initial load (excluding images)
   - Mobile Lighthouse score: 90+ performance, 100 accessibility

7. **Accessibility:** WCAG AA minimum. Keyboard navigation for all interactive elements. Screen reader support. Color contrast 4.5:1 minimum for body text.

8. **Dark mode is optional for v1.** If attempted, it must be a first-class design, not an inverted light mode. Don't half-ass it.

---

## PART 8: DELIVERABLES & TIMELINE

### Phase 1: Research & Direction (Week 1)
- [ ] Competitive analysis deck (all 15 platforms, borrow/reject for each)
- [ ] User journey maps (3 personas: Amina the fresh grad, Brian the mid-career switcher, Wanjiru the senior)
- [ ] Mood board (visual direction, typography samples, color exploration)
- [ ] Design principles document (5-7 principles that guide every decision)
- [ ] Information architecture (site map, user flows for: feed → apply, CV upload → match, tracker management)

### Phase 2: Concept Design (Week 2-3)
- [ ] Wireframes: homepage/feed, job detail, application tracker, CV upload, account/profile, company page
- [ ] 3D/spatial concept exploration (how depth works in the product)
- [ ] Typography system (primary, secondary, monospace, hierarchy scale)
- [ ] Color system (primary palette, semantic colors, dark mode considerations if attempted)
- [ ] Component library foundation (cards, buttons, badges, chips, forms, filters)
- [ ] Motion design spec (durations, easings, scroll behaviors, micro-interactions)

### Phase 3: High-Fidelity Design (Week 4-5)
- [ ] Full design system in Figma (components, tokens, variants, dark mode if attempted)
- [ ] High-fidelity mockups: all key screens, desktop (1200px+) AND mobile (320-768px)
- [ ] Interactive prototype: key flows (feed → apply, CV upload → match, tracker update)
- [ ] 3D asset specs (what's rendered, what's pre-baked, performance budget)
- [ ] Animation specs (Lottie/JSON where appropriate, CSS where possible)
- [ ] Accessibility audit (WCAG AA, keyboard nav, screen reader, color contrast)

### Phase 4: Handoff & Support (Week 6)
- [ ] Developer handoff package (tokens, specs, interaction notes, asset exports)
- [ ] Design QA support during implementation (2 weeks post-handoff)
- [ ] Custom icon system (designed for the product, not from an icon library)
- [ ] Illustration guidelines (if used: how they should feel, what to avoid)

---

## PART 9: SUCCESS CRITERIA

How we know this worked. Both quantitative and qualitative.

### Quantitative (Post-Launch Targets)
- Session duration: 7+ minutes (Indeed benchmark)
- Pages per visit: 8+ (Indeed benchmark)
- Bounce rate: <35%
- CV upload rate: >20% of signed-in users
- Application completion rate: >60% of started applications
- 7-day retention: >40%
- Mobile Lighthouse: 90+ performance, 100 accessibility
- First paint: under 1.5s on 4G

### Qualitative
- A user can identify this as Kazi-Kasi within 3 seconds (distinct from any other job platform)
- No "generic SaaS" feeling anywhere in the product
- No AI-generated language in the UI
- Every design decision can be traced back to a principle or a research insight
- At least one element that makes a designer say "I haven't seen that before in a job platform"
- 3D/spatial elements serve hierarchy, not decoration
- Typography has character without sacrificing readability
- Color feels warm and human, not corporate and cold
- Motion teaches, not decorates

### The Ultimate Test
Would a designer at Apple or Pentagram be proud of this? If no, raise the bar.

---

## PART 10: DECISION FRAMEWORK

When you're stuck between two directions, run the candidate through these five questions in order:

1. **Does it serve the user's goal?** (Find a job. Apply quickly. Track progress.) If no, cut it.

2. **Does it build trust?** (Salary shown. Source attributed. Freshness dated. Data used respectfully.) If no, reconsider.

3. **Does it feel hand-built?** (Craft, texture, intentional type.) If no, push further.

4. **Does it work on a KES 15,000 Android phone on 3G?** If no, optimize. This is not a hypothetical — this is your median user.

5. **Would a designer at Apple or Pentagram be proud of this?** If no, raise the bar.

If a design decision passes all five, ship it. If it fails any one, iterate.

---

## PART 11: HOW TO GET STARTED (DAY 1 CHECKLIST)

You've read this document. Now what?

### Morning (Day 1)
1. **Open the current product:** https://kazi-kasi-app.vercel.app — use it for 15 minutes. Create an account. Upload a CV. Browse the feed. Note what works and what frustrates you.

2. **Open the research document:** `docs/redesign-research.md` in the repo — it has the raw research synthesis for all 15 platforms.

3. **Open the current code:** `src/kazikasi/serve.py` — look at the STYLE block (around line 86). See what design tokens exist. See what's being used and what's not.

4. **Read this document again** — the second read will land differently after you've seen the product.

### Afternoon (Day 1)
5. **Study the reference sites** (from Section 6.2): Aesop.com, Linear.app, Arc Browser. Not to copy — to calibrate your sense of craft.

6. **Study the benchmark platforms:** Indeed.com, LinkedIn.com/jobs, mokaru.ai. Note specific patterns you'd borrow and patterns you'd reject.

7. **Write down your first questions** — anything that's unclear, anything you disagree with, anything you want to challenge. Send them to the owner.

### Week 1 Deliverable Target
By end of Week 1, you should have:
- Competitive analysis deck (all 15 platforms)
- 3 user journey maps
- Mood board
- Draft design principles (5-7)
- Information architecture (site map + 3 key user flows)

---

## PART 12: COMMUNICATION & PROCESS

- **Creative decisions go through the owner** (Flex Brandon). No silent pivots. If you want to change direction, bring the evidence and make the case.

- **Weekly reviews** at the end of each phase. Show work, get feedback, iterate. Don't wait until the end of a phase to surface problems.

- **Push back** when a functional requirement conflicts with a design principle. That tension is where the best work happens. Don't just comply — argue your case.

- **Show your research.** If you're proposing a direction, bring the evidence. If you're rejecting a pattern, explain why. "I don't like it" is not a valid reason. "It fails decision framework question 4" is.

- **Prototype early.** A rough interactive prototype beats a polished static mockup. Show how it feels, not just how it looks.

- **Document decisions.** When you choose A over B, write down why. Six weeks from now, you'll forget. The next person joining the team will need the context.

---

## PART 13: FINAL NOTE

This is not a job board. Job boards are commodities. Indeed won that war twenty years ago.

This is a **career companion for the Kenyan market** — the first one designed with the same craft and ambition that Apple brings to its products, grounded in the reality of the Kenyan job seeker's daily experience.

The bar is not "better than the current version." The current version is functional but uninspired. The bar is: **the best-designed job platform in Africa.**

That's the assignment. The research is done. The functional requirements are clear. The creative direction is set. The constraints are known.

Go build it.

---

**Document version:** 1.0  
**Owner:** Flex Brandon  
**Next review:** End of Phase 1 (Week 1)  
**Questions?** Ask early. Ask often. The only bad question is the one you didn't ask because you assumed the answer.
