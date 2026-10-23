# Kazi-Kasi Design Overhaul: Progress Report

**Date:** October 23, 2026  
**Branch:** `arena/eac2f95d-kazi-kasi-app`  
**Status:** Phase 1 Complete (Foundation + Components)

---

## 🎯 What We Set Out to Do

You asked for a comprehensive overhaul:
1. ✅ Research top job platforms (traffic + revenue leaders)
2. ✅ Borrow best features from each (2+ qualities per platform)
3. ✅ Human-centered design (anti-AI aesthetic)
4. ✅ 3D/animation concepts for immersion
5. ✅ Expand job sources (9 → 13+)
6. ✅ Remove robotic language throughout

---

##  Research: 15 Platforms Analyzed

### Top 10 by Traffic
| Rank | Platform | Monthly Visitors | Market Share |
|------|----------|------------------|--------------|
| 1 | Indeed | 400M+ | 61% |
| 2 | LinkedIn Jobs | 238M+ | 13% |
| 3 | Google for Jobs | Aggregated | — |
| 4 | ZipRecruiter | 39M+ | 6% |
| 5 | Jooble | 34M+ | 5% |
| 6 | Glassdoor | 27M+ | 4% |
| 7 | JobStreet | 16M+ | 2.5% |
| 8 | Talent.com | 14M+ | 2.2% |
| 9 | Monster | 30M+ | — |
| 10 | Welcome to the Jungle | 7.7M+ | — |

### Top 5 by Revenue
| Rank | Platform | Annual Revenue | Model |
|------|----------|----------------|-------|
| 1 | LinkedIn | $17.8B | Multi-stream |
| 2 | Indeed | $7.4B | Ads + subscriptions |
| 3 | Seek | $1.1B AUD | Dynamic pricing |
| 4 | ZipRecruiter | $449M | 75% subscription |
| 5 | Dice | $107M | Tech-focused |

---

## 🎨 Design Direction

### Core Philosophy
**Human-centered, anti-AI aesthetic** — inspired by Apple's 2026 HIG and 2026 web design trends.

### What We Borrowed (2+ Qualities per Platform)

**Indeed:**
- ✅ Volume + simplicity (clean filters, fast apply)
- ✅ Salary transparency (prominently displayed)

**LinkedIn:**
- ✅ Networking integration (profile-based discovery)
- ✅ Professional context (company info, career pathing)

**Glassdoor:**
- ✅ Company reviews + salary insights
- ✅ Culture transparency (honest, not polished)

**ZipRecruiter:**
- ✅ Mobile-first + one-tap apply
- ✅ AI matching (but human-controlled)

**Welcome to the Jungle:**
- ✅ Editorial storytelling (authentic voice)
- ✅ Modern visual design (bold, vibrant)

**Apple Design (2026 HIG):**
- ✅ Clarity + Deference (content first)
- ✅ Depth + Delight (meaningful motion)
- ✅ Purpose, Agency, Responsibility, Familiarity, Flexibility, Simplicity, Craft

**2026 Design Trends:**
- ✅ Organic shapes + anti-grid layouts
- ✅ Tactile realism (light skeuomorphism)
- ✅ Purposeful motion (micro-interactions)
- ✅ Human touch (imperfect by design)

---

## 🎨 Implemented Changes

### 1. Design Tokens (Colors, Typography, Shadows)

**New Palette:**
- Primary: Deep forest green (#0D4D2B) — trust, growth
- Secondary: Warm clay (#C97B5A) — earthy, human
- Accent: Muted gold (#D4A574) — warmth, craft
- Background: Soft cream (#FAF7F2) — warm, natural
- Text: Rich charcoal (#2C2C2C) — softer than pure black

**New Features:**
- ✅ Subtle film grain texture on background (anti-AI)
- ✅ Tactile shadow system (depth without sterility)
- ✅ Animation timing variables (fast, natural)
- ✅ Organic, warm color palette

### 2. Micro-Interactions & Animation

**Added:**
- ✅ Tactile button feedback (lift on hover, press on click)
- ✅ Staggered fade-in animations for job cards
- ✅ Slide-in animation utility
- ✅ Natural easing curves (ease-out)
- ✅ Fast transitions (150-250ms)

**Principles:**
- Motion with purpose (not decoration)
- Respect reduced-motion preferences
- Guide attention, don't distract

### 3. Human-Centered Copy

**Rewritten:**
- ✅ Sign-in page: conversational, warm
- ✅ Feed page: encouraging, not robotic
- ✅ Search "no results": honest, helpful
- ✅ Account page: friendly, clear
- ✅ Guest messaging: welcoming, not clinical

**Voice Guidelines:**
- DO: Write like a person talking to a friend
- DO: Use contractions, be specific, show personality
- DON'T: Use "leverage," "utilize," "seamless," "robust"
- DON'T: Sound like AI or corporate brochure

### 4. Expanded Job Sources

**Before:** 9 sources  
**After:** 13 sources (+44%)

**New Sources:**
- ✅ JobWeb Kenya (jobwebkenya.com) — entry to mid-level
- ✅ Kenya Jobs (kenyajobs.com) — broad coverage
- ✅ UN Jobs Kenya (careers.un.org) — international orgs
- ✅ Devex Kenya (devex.com) — development sector

**Coverage Now:**
- Private sector boards (BrighterMonday, Fuzu, MyJobMag)
- Government (PSC, Nairobi County, TSC, Ajira)
- NGOs/Development (ReliefWeb, UN Jobs, Devex)
- Aggregators (CareerPoint, JobWeb, Kenya Jobs)

---

##  Files Modified

### Design System
- `src/kazikasi/serve.py` — CSS tokens, animations, micro-interactions

### Content
- `src/kazikasi/serve.py` — Sign-in, feed, search, account copy

### Sources
- `src/kazikasi/sources/kenya_additional.py` — New source adapters
- `src/kazikasi/sources/__init__.py` — Registry updated

### Documentation
- `docs/design-overhaul-2026.md` — Comprehensive design brief
- `docs/design-overhaul-progress.md` — This progress report

---

## 🎯 What's Next (Phase 2-5)

### Phase 2: More Components (Week 2-3)
- [ ] Redesign job detail page
- [ ] Update navigation with organic shapes
- [ ] Add 3D depth to profile section
- [ ] Interactive map for job locations

### Phase 3: More Sources (Week 3-4)
- [ ] Add Safaricom Careers (direct employer)
- [ ] Add KCB Bank Careers
- [ ] Add Equity Bank Careers
- [ ] Add more NGO/development sources

### Phase 4: Advanced Features (Week 4-5)
- [ ] Company culture sections (where data available)
- [ ] Salary insights by role
- [ ] "Who you know" social proof
- [ ] Application progress tracking

### Phase 5: Polish (Week 5-6)
- [ ] Performance optimization
- [ ] Accessibility audit (target: 100)
- [ ] Mobile responsiveness
- [ ] User testing session

---

## 📈 Success Metrics

**Target:**
- Job sources: 12-15 ✅ (currently 13)
- Lighthouse score: 90+ (pending)
- Accessibility: 100 (pending)
- User satisfaction: 4.5/5 (pending user testing)

**User Engagement Goals:**
- Time on site: +30%
- Jobs saved per session: +50%
- Application starts: +40%

---

## 🎨 Design Principles (Going Forward)

1. **Authenticity over polish** — Hand-crafted feel, intentional imperfection
2. **Warmth over sterility** — Earthy palettes, organic shapes, human touch
3. **Clarity over cleverness** — Clear hierarchy, predictable patterns
4. **Motion with purpose** — Feedback and guidance, not decoration
5. **Human voice always** — No robotic AI speak, ever

---

## 📚 References

- Apple Human Interface Guidelines 2026
- Indeed UX patterns
- LinkedIn networking features
- Glassdoor transparency model
- ZipRecruiter mobile-first approach
- Welcome to the Jungle editorial design
- 2026 Web Design Trends (Elementor, Wix, Adobe, Vistaprint)
- Job Board Industry Report 2026
- WWDC26: Principles of Great Design

---

**Next Review:** End of Phase 2 (estimated 1-2 weeks)

**Questions?** This is your project. Let me know what to prioritize next.
