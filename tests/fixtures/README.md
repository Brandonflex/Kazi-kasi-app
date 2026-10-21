# Test fixtures

Every page in this folder is **synthetic**: hand-written markup modelled on what the
live sites publish, not a copy of a real posting. That keeps the repository free of
third-party copyrighted content while still exercising the same structural paths
(JSON-LD, selector fallbacks, prose heuristics).

| File | What it exercises |
| --- | --- |
| `brightermonday-listing.html` | listing → detail link extraction, tracking params, pagination noise |
| `brightermonday-detail.html` | `schema.org/JobPosting` JSON-LD happy path, salary range, deadline |
| `myjobmag-listing.html` | listing with duplicate links and an off-pattern href |
| `myjobmag-detail.html` | no JSON-LD → CSS selector fallback, single-stipend internship |
| `suspicious-detail.html` | no employer identity, fee request, WhatsApp-only application |
| `reliefweb-jobs.json` | ReliefWeb API v2 record shape, closing date, city array |

If a real page ever contradicts a fixture, add a *new* fixture alongside it and mark
the old one; do not silently edit the old one, or the regression it encodes is lost.
