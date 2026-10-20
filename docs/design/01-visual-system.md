# Visual system

**What this is:** the tokens and components the product is built from, with the
reason for each. It is small on purpose — one surface (a list of cards), two
supporting pages, and a message. A design system bigger than the product is a
hobby.

**Where it lives:** `src/kazikasi/serve.py` (`STYLE`), asserted by
`tests/test_design.py` so the documentation and the shipped CSS cannot drift.

---

## 1. Tokens

```css
:root{
  /* surfaces */
  --paper:#FBF8F2;      /* page */
  --card:#FFFFFF;       /* card, header, inputs */
  --sunken:#F3EEE5;     /* the WhatsApp message preview, table stripes */
  --line:#E3DCCF;       /* 1px borders — warm, never grey */

  /* ink */
  --ink:#12161C;        /* 17.1:1 on paper */
  --ink-2:#3D4653;      /* 9.6:1 — secondary text */
  --muted:#5C6675;      /* 5.5:1 — timestamps, captions (still AA) */

  /* meaning */
  --forest:#14532D;     /* action + verified */
  --forest-soft:#E7F0E8;
  --amber:#9A4E00;      /* time pressure */
  --amber-soft:#FBEEDC;
  --risk:#A3241C;       /* danger only */
  --risk-soft:#FBEAE8;
  --live:#15803D;       /* dot / "live" indicator, never text-only meaning */

  /* geometry */
  --radius:14px; --radius-sm:10px; --radius-pill:999px;
  --pad:16px; --gap:12px;
  --shadow:0 1px 2px rgba(20,22,28,.05), 0 6px 20px rgba(20,22,28,.05);
  --focus:0 0 0 3px #B9D4C1, 0 0 0 1px #14532D;
}
```

**Spacing** is a 4 px scale: 4, 8, 12, 16, 20, 24, 32, 48. Nothing in the UI uses
a value off the scale.

**Radius:** cards 14 px, inputs and small controls 10 px, badges pill. One radius
per element class — no mixed corners inside a card.

## 2. Contrast contract

Measured, not eyeballed (WCAG 2.2 AA: 4.5:1 body, 3:1 large text and UI edges):

| Pair | Ratio | Verdict |
|---|---|---|
| ink on paper | 17.12 | AAA |
| ink-2 on card | 9.55 | AAA |
| muted on card | 5.81 | AA |
| forest on white | 9.11 | AAA |
| amber on white | 6.06 | AA |
| amber on amber-soft | 5.30 | AA |
| risk on white | 7.43 | AAA |
| risk on risk-soft | 6.38 | AA |
| live on white | 5.02 | AA |
| white on forest | 9.11 | AAA |

`tests/test_design.py` recomputes these from the CSS variables in `serve.py` and
fails the build if a future colour change breaks one.

## 3. Type scale

Two families, both system: **sans** for everything you read, **serif** (Georgia →
`Iowan Old Style` → `Times New Roman`) for the three places where the product is
allowed to be editorial — the page name, the four numbers, and the deadline in
the card corner. No webfont is downloaded; on Android the serif falls back to
Noto Serif, which is why the serif is used only at ≥16px.


| Token | px / line-height | Weight | Where |
|---|---|---|---|
| `--t-display` | 50 / 1.02 | 400 serif | masthead name (34 on phones) |
| `--t-title` | 18 / 1.3 | 650 | card job title |
| `--t-body` | 16 / 1.55 | 400 | body copy, inputs |
| `--t-small` | 13 / 1.45 | 400 | reasons, timestamps |
| `--t-label` | 12 / 1.2 | 600 | badges |

Headings use `letter-spacing:-.015em`. Body never goes below 16 px except in
badges and captions — on a 5-inch screen at arm's length in daylight, 14 px body
text is a readability bug, not a density choice.

## 4. Components

### 4.1 Badge

One line, one meaning, never wider than its content.

| Variant | Background | Text | Meaning |
|---|---|---|---|
| `good` | forest-soft | forest | "open to freshers", "remote", "on 2 sources" |
| `warn` | amber-soft | amber | "closes in 5 days", "not re-checked recently" |
| `danger` | risk-soft | risk | "flagged: asks for a fee" |
| `muted` | sunken | ink-2 | location, employment type, "eligibility unstated" |
| `live` | forest-soft + 6 px dot | forest | freshly checked |

**Rule:** a badge is never the only place a fact appears in the page — the card
reason or the job page repeats it in a sentence. Colour is a fast path, not the
only path (WCAG 1.4.1).

### 4.2 Job card

```
┌────────────────────────────────────────────────────┐
│ Records Management Assistant              ← title 18/650
│ Public Service Commission of Kenya         ← employer 14 ink-2
│ [open to freshers] [Nairobi] [closes 12 Nov] ← badges
│ matches admin · pays above your floor      ← one reason, 13 muted
│ ────────────────────────────────────────────────
│ 0.61   checked 12 minutes ago        Apply on psc ↗ │ ← foot
└────────────────────────────────────────────────────┘
```

- **Title is the link**, and it is the only element with link colour.
- **The score is present but quiet** (13 px, muted). It is an audit trail, not a
  selling point: nobody should optimise for our number.
- **Apply is a link-out** to the employer, always labelled with the source
  (`Apply on psc`), never "Apply now".
- **"Not for me"** is a small, low-contrast text button — a deliberate signal
  should not be as loud as a job title.
- Whole card is **not** clickable: the title and Apply are separate targets ≥44 px
  apart so a thumb cannot hit the wrong one.

### 4.3 Stat strip

Four numbers with labels underneath (`31 live jobs`, `9 closing in 7 days`,
`18 match this profile`, `2 applied`). Tabular numerals; no icons.

### 4.4 Message preview

The digest preview on `/digest` is set in `--font-mono` at 14/1.55 on `--sunken`
inside a rounded rect, so it is unmistakably *a message* and not page copy.
WhatsApp's own `*bold*` markers are left visible: hiding them would be a lie about
what is being sent.

### 4.5 Forms

- Inputs: 44 px tall, 16 px text (below 16 px, iOS zooms the viewport on focus).
- Labels above, never placeholders as labels.
- One primary button per form (forest), one ghost button for the destructive or
  secondary path.
- Errors are text next to the field **and** announced in a `role="alert"` region.

### 4.6 Empty and blocked states

| State | Copy | Visual |
|---|---|---|
| Nothing matches | "Nothing matches these constraints yet. Loosen one, or check back after the next sweep." | plain card, no illustration |
| Nothing left to send | "Nothing to send today." | the digest page states it; the phone gets silence |
| Blocked job | "Can't take this one: needs 3 years, you have 0." | risk-soft panel, never red text on white |
| Source late | "Checked 24 minutes ago — target 15." | amber |

## 5. Accessibility contract

Written as requirements, because "accessible" is not a checklist item:

1. **Contrast:** AA minimum for all text, 3:1 for borders, focus rings and the
   live dot.
2. **Target size:** 44 × 44 px for primary actions, never under 24 × 24 (WCAG
   2.2 SC 2.5.8).
3. **Focus visible:** `--focus` ring on every interactive element, never
   `outline:none` without a replacement.
4. **Reflow:** usable at 320 px wide and 200% zoom with no horizontal scroll.
5. **Not colour alone:** every badge has words; every state has text.
6. **Reduced motion:** all transitions respect `prefers-reduced-motion`.
7. **Language:** `<html lang="en-KE">`; Swahili phrases marked `lang="sw"` when
   they appear in running text.
8. **Screen readers:** the digest preview is a `<pre>` with an accessible label;
   the score has a `title` ("match score") rather than being a mystery number.

## 6. Do / don't

| Do | Don't |
|---|---|
| One accent colour per card | Forest border, amber badge and red button on one card |
| Show the timestamp of the last check | Say "real-time" |
| Put the reason in a sentence | Put the reason only in a badge |
| Use `Apply on psc ↗` | Use `Apply now!` |
| Let an empty day be empty | Invent "trending jobs" to fill the space |
| Keep the score small and grey | Turn the score into a progress ring |
| Use the system font | Load Inter/Poppins "for brand consistency" |

## 7. Implementation notes

- Tokens are CSS custom properties in `serve.py::STYLE`; there is no build step
  and no stylesheet file to get out of sync.
- The mark is inline SVG (≈ 300 bytes) generated by `_scope_mark()`, inheriting
  `currentColor`, so it costs no request.
- The palette test parses `:root{…}` from `STYLE` and checks the contrast pairs
  listed in §2 — the doc and the build share one source of truth.
