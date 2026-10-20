# Phase 3 — the document lane (PSC and county sources)

**Status:** built and tested (192 tests, all offline) · **Network required:** no
**Depends on:** [Phase 1](./phase-1-build.md) ingestion, [Phase 2](./phase-2-build.md) job graph

The boards publish job objects. The public service does not. PSC and the county
governments publish a PDF: one advert, several posts, one closing date, one
inbox — and expect a human to read it.

This phase is the part that reads it.

---

## 1. What runs today

```bash
python -m pytest                                   # 192 tests, no network

# one advert, from disk, no source required
kazikasi document --file advert.pdf --source psc \
  --employer "Public Service Commission of Kenya" --county Nairobi

# or straight into the graph
kazikasi document --file advert.pdf --source psc --employer "…" --county Nairobi --db ./data/kazi.db

# the whole lane, end to end
kazikasi ingest --source psc --store ./data/raw --db ./data/kazi.db
kazikasi replay --source psc --store ./data/raw
kazikasi canary --source psc
```

Two new sources in the registry:

| id | what | cadence |
|---|---|---|
| `psc` | Public Service Commission of Kenya — PDF adverts on psckjobs.go.ke | every 4 h |
| `nairobi_county` | Nairobi City County Government careers page | every 12 h |

## 2. One advert, N posts

`documents.py` splits a bulletin at its headings and emits **one candidate per
post**:

```
VACANCY NO. 1/2026: ASSISTANT OFFICE ADMINISTRATOR - CSG 11
  → Assistant Office Administrator   · 1/2026 · KSh 38,270–49,950 · some_experience
VACANCY NO. 2/2026: RECORDS MANAGEMENT ASSISTANT - CSG 12
  → Records Management Assistant     · 2/2026 · KSh 30,550–39,720 · open_to_freshers
VACANCY NO. 3/2026: SENIOR ICT OFFICER - CSG 8
  → Senior ICT Officer               · 3/2026 · KSh 95,470–141,300 · experienced
```

Headings are found two ways, because Kenya writes them two ways:

- `VACANCY NO. 1/2026: TITLE` / `POST NO. …` / `POSITION …` (PSC style);
- `1. TITLE` numbered all-caps headings (county style).

Shared fields are read once from the whole document and applied to every post —
closing date, application inbox, employer — because that is how the document is
written. Per-post fields come from each section: salary, requirements,
eligibility, posts count.

Details that turned out to matter:

- **Salary lives on its own line.** Flattening the document to one paragraph
  before parsing silently lost every salary, so line structure is preserved from
  the PDF or HTML and only prose fields are flattened.
- **"one (1) year"** is how Kenyan adverts write 1 year. It is normalised before
  eligibility is read, or every mid-level post reads as unstated.
- **Requirements, not duties.** Eligibility is read from the requirements slice;
  duties describe the role and inflate the match.
- **Reference numbers are namespaced** (`public-service-commission-of-kenya/1/2026`)
  because PSC vacancy numbers restart every year and `1/2026` alone is not unique.
- **Titles are un-shouted** for display ("Senior ICT Officer", not "SENIOR ICT
  OFFICER"), while matching still uses the normalised text.

## 3. Why the identity layer mattered here

The same county advert appears as an HTML page and as its PDF. They carry
**different** reference numbers and the same everything else. Phase 2's cultural
key (employer + title + county + deadline) merges them:

```
payloads 2 · candidates 4 · jobs 2 · review queue 0
```

And three posts in one PSC PDF stay three jobs, because each carries its own
exclusive reference key. That is the "one advert, N posts" rule working in
practice, not just in a document.

A test asserts both directions (`tests/test_bulletins.py`).

## 4. Bytes, not text

Reading a PDF required one structural change: the pipeline now carries the raw
**bytes** of every payload through to the content-addressed store, and only
decodes to text where text is what is wanted.

Before this phase, `store.put(fetched.body.encode("utf-8"))` re-encoded a decoded
string. For HTML that was invisible. For a PDF it would have stored mojibake and
made replay impossible — which is exactly the failure the raw store exists to
prevent. `Payload` (url + bytes + content type) is now the unit of transfer, and
a test asserts the stored blob still starts with `%PDF-`.

The adapter interface gained one method, `parse_payload(payload) → list[JobCandidate]`;
the HTML adapters inherit a default that wraps `parse_detail`, so nothing else
changed.

## 5. Honesty about documents we cannot read

- A PDF with no text layer (a scan) raises `DocumentError("no extractable text;
  OCR not implemented")`. The CLI exits `2` and says so. **We do not invent a
  job from a scan.**
- `looks_scanned()` exists so the canary can report scan-only uploads as a
  coverage problem rather than a parser bug.
- `canary --source psc` reports `posts` as well as `ok`, so a source that starts
  returning adverts with one post instead of six shows up as a shape change.

**OCR is deliberately not implemented.** It needs its own confidence model and a
human review path; smuggling it in here would make every extracted field
untrustworthy in a way this codebase is built to avoid.

## 6. Fixtures

`psc-advert.pdf` and `nairobi-advert.pdf` are **synthetic** adverts, generated as
minimal PDFs for the tests — not real postings. They exercise the same structure
as the real thing (headings, salary lines, requirement lists, one shared closing
date). The PDFs are committed because the bytes are the test.

## 7. Deliberately not built

- **OCR / scanned adverts.** See above.
- **County coverage beyond Nairobi.** Each county is its own adapter and its own
  canary; pretending one selector set generalises would be wrong.
- **MyGov / e-procurement portals** and other login-gated boards.
- **Fetching from the live sites in tests.** The lane is proven offline; the
  canary is what proves it live.

## 8. Next

1. **Run the canary on `psc` and `nairobi_county` daily for a week** and fix the
   selectors from what it reports. This is the step that turns "adapter written"
   into "source covered".
2. **Add a second county** once Nairobi's shape is stable — Mombasa and Kiambu
   are the obvious next two by posting volume.
3. **Load a real PSC bulletin into the graph** and check the duplication rate
   against the boards; public-sector adverts are widely republished by MyJobMag,
   so this is where the identity rules earn their keep.
