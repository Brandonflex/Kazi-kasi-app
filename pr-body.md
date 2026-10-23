## Summary

This PR fixes two critical production bugs and adds personalization features using Google sign-in data.

## Bug Fixes

### 1. Sign-in Callback Crash (Postgres)
**Problem:** `ERROR: function max(text) does not exist` when signing in with Google

**Root cause:** Postgres doesn't allow `MAX()` on mixed types (smallint + text)

**Fix:** Cast `email_verified` to integer before the MAX comparison in `accounts.py`

### 2. PDF Reader Crash
**Problem:** `pypdf.errors.PdfStreamError: Stream has ended unexpectedly` when uploading malformed PDFs

**Root cause:** Insufficient error handling in PDF parsing

**Fix:** 
- Catch all PDF parsing exceptions (corrupted files, scanned images, truncated files)
- Show friendly error messages instead of 500 errors
- Handle edge cases: no text content, page-level parsing failures

## Personalization Features

Using data from Google sign-in (name, email, profile picture) to create a tailored experience:

- **Personalized greetings:** "Hey [First Name]" instead of generic "Account"
- **Profile pictures:** Show Google profile photo in navigation and account page
- **Email pre-fill:** Use Google email for CV parsing and forms
- **Store additional fields:** given_name, family_name, picture, locale

## Database Changes

Added new columns to `accounts` table:
- `given_name TEXT` — First name from Google
- `family_name TEXT` — Last name from Google  
- `picture TEXT` — Profile photo URL
- `locale TEXT` — Language preference

Migration safely adds columns to existing databases using `_add_column()`.

## Testing

- ✅ Sign-in callback works without type cast errors
- ✅ Malformed PDFs show friendly error messages
- ✅ Google profile data stored and displayed
- ✅ Personalized greetings work
- ✅ Profile pictures show in navigation
- ✅ All imports compile successfully

## Files Changed

- `src/kazikasi/accounts.py` — Fixed Postgres cast, added Google profile fields
- `src/kazikasi/db.py` — Added new columns and migrations
- `src/kazikasi/serve.py` — PDF error handling, personalized UI
