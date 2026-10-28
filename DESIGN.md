# Kazi-Kasi 2.0 Design Philosophy

## What We Built

A complete redesign blending **Mokaru's tracker**, **LinkedIn's professional polish**, and **Indeed's clean functionality** while maintaining the dark editorial aesthetic.

## Design Influences

### Mokaru (Application Tracker)
- ✅ Kanban board with 6 stages: Wishlist → Applied → Interview → Offer → Rejected → Hired
- ✅ Board view AND list view (user can switch)
- ✅ Per-card details: salary, notes, application date, company links
- ✅ Status overview with color-coded counts
- ✅ Drag-ready architecture (future enhancement)

### LinkedIn (Professional Feel)
- ✅ Profile completeness indicator (78% complete)
- ✅ Activity stats (jobs applied, interviews, matching jobs)
- ✅ Tabbed profile sections (Overview, Experience, Skills, Preferences)
- ✅ Clean typography hierarchy
- ✅ Professional header with navigation
- ✅ Public/private profile concept

### Indeed (Clean Functionality)
- ✅ Job cards with company logos (letter-based for now)
- ✅ Clear salary display
- ✅ Match score prominently shown
- ✅ Search + sort + filter controls
- ✅ "Why it matches" explanation on every card
- ✅ Urgent/Remote badges
- ✅ One-click apply (opens company site)
- ✅ Clean, scannable layout

### Original Kazi-Kasi Contributions (Preserved)
- ✅ Smart matching algorithm (ranking.py) - constraints, relevance, utility
- ✅ Application tracking lifecycle
- ✅ WhatsApp digest/alerts feature
- ✅ CV auto-extraction from PDF
- ✅ Cover letter generation
- ✅ Location-aware matching (county-level)
- ✅ Distance scoring

## Dark Editorial Design System

### Colors
- **Background**: `#0a0a0a` (cinematic dark)
- **Surface**: `#111111` (elevated cards)
- **Surface Light**: `#1a1a1a` (hover states)
- **Border**: `#2a2a2a` (subtle dividers)
- **Text Primary**: `#f5f5f5` (headings, important text)
- **Text Secondary**: `#a0a0a0` (body text, labels)
- **Ember Gold**: `#E9A23B` (CTAs, highlights, match scores)
- **Safari Mint**: `#2dd4a8` (success, salary, positive states)
- **Nairobi Blue**: `#1e90ff` (info, applied status)

### Typography
- **Display**: Fraunces (serif) - headings, hero text
- **Body**: Inter (sans-serif) - body text, UI elements
- **Scale**: 7xl → 5xl → 4xl → 2xl → xl → base → sm → xs

### Spacing
- **Sections**: py-24 (96px vertical rhythm)
- **Cards**: p-6 to p-8 (24-32px padding)
- **Gaps**: gap-3 to gap-8 (12-32px spacing)
- **Max widths**: 7xl (1280px) for content, 1800px for tracker board

### Components
- **Buttons**: 
  - Primary: bg-[#E9A23B] text-[#0a0a0a] rounded-lg
  - Secondary: border border-[#2a2a2a] rounded-lg
  - Hover states with scale transitions
- **Cards**: 
  - border border-[#2a2a2a] bg-[#111111] rounded-xl
  - Hover: border-[#E9A23B]/50 bg-[#1a1a1a]
- **Badges**: 
  - px-3 py-1 rounded-full text-xs font-semibold
  - Color-coded by status
- **Inputs**: 
  - bg-[#0a0a0a] border border-[#2a2a2a] rounded-lg
  - Focus: border-[#E9A23B]/50

## Pages Built

### Landing Page (/)
- Hero with "Find your next / career move"
- Stats bar (284 jobs, 47 closing, 15 sources, 92% accuracy)
- "How it works" section (3 steps)
- Features grid (6 features)
- CTA section
- Footer with links

### Job Feed (/feed)
- Search bar with real-time filtering
- Sort controls (Best Match, Recent, Closing Soon)
- Remote filter toggle
- Job cards with:
  - Company logo (letter-based)
  - Title, company, location, type
  - Match score (prominent)
  - Salary
  - "Why it matches" explanation
  - Urgent/Remote badges
  - Skill tags
  - Posted date

### Job Detail (/feed/[id])
- Match score badge
- Full job info (title, company, location, salary)
- Match breakdown with progress bars
- Job description
- Requirements checklist
- Benefits checklist
- Apply button (opens company site)
- Save button

### Application Tracker (/tracker)
- Stats overview (6 status columns with counts)
- Toggle: Board view / List view
- Kanban board with 6 columns:
  - Wishlist (gray)
  - Applied (blue)
  - Interview (gold)
  - Offer (mint)
  - Rejected (dark gray)
  - Hired (mint)
- Each card shows: title, company, location, salary, notes, date
- List view with expanded details

### Profile (/profile)
- Profile header with avatar, name, location
- Profile completeness indicator
- Tabbed interface:
  - Overview: CV upload, activity stats
  - Experience: Work history
  - Skills: Skill tags
  - Preferences: Location, salary, job type

## What's Next

### Phase 2: Backend Integration
- Connect to existing Python FastAPI backend
- Wire up ranking.py for real match scoring
- Connect applications.py for tracker data
- Integrate extract.py for CV parsing
- Connect digest.py for WhatsApp alerts
- Integrate cover_letter.py for generation

### Phase 3: Authentication
- Sign in / Sign up flows
- User profiles
- Session management
- OAuth (Google, LinkedIn)

### Phase 4: Advanced Features
- Real drag-and-drop kanban
- Email notifications
- Company pages
- Salary benchmarking
- Interview prep
- Network features (LinkedIn-style)

## Architecture

### Frontend
- Next.js 14 with App Router
- TypeScript
- Tailwind CSS
- Dark editorial design system
- Responsive (mobile-first)

### Backend (Existing)
- Python FastAPI
- SQLite database
- Smart matching algorithm (ranking.py)
- Application tracking (applications.py)
- CV extraction (extract.py)
- WhatsApp digest (digest.py, outbox.py)
- Cover letter generation (cover_letter.py)
- Location matching (geo.py)

## Key Design Decisions

1. **Dark editorial over light/corporate**
   - User explicitly loved the dark aesthetic
   - More modern, less generic
   - Better for long reading sessions

2. **Kanban tracker (Mokaru influence)**
   - Most requested feature
   - Visual, intuitive
   - Professional job search standard

3. **Profile completeness (LinkedIn influence)**
   - Gamification without being cheesy
   - Encourages data quality
   - Better matching results

4. **Clean job cards (Indeed influence)**
   - Scannable
   - Information hierarchy clear
   - Mobile-friendly

5. **Preserve original contributions**
   - Smart matching is the core value prop
   - WhatsApp integration is unique to Kenya
   - Location-aware matching is critical
   - CV extraction saves time

6. **No 3D/galaxy (user rejected)**
   - Keep it clean and professional
   - Focus on data and typography
   - Performance matters

## Design Philosophy

**"Smart job matching that looks like a premium product"**

We're not another generic job board. We're:
- **Intelligent**: AI-powered matching with clear explanations
- **Professional**: LinkedIn-level polish
- **Functional**: Indeed-level usability
- **Organized**: Mokaru-level tracking
- **Local**: Built for Kenya (WhatsApp, M-Pesa, county-level)

The dark editorial design makes it feel premium and modern while staying functional and accessible.
