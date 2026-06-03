# Plan: LATAM Marketing, PDF Watermark, and Chrome Extension

## Goal
Attract MercadoLibre sellers in LATAM via a 90% organic / 10% paid marketing strategy, implement a diagonal watermark on generated PDFs, and build a Chrome Extension for seamless operation directly from MercadoLibre.

## Scope Boundaries
**IN SCOPE:**
- Backend: Modifying `app/utils/extract_label.py` to add a diagonal watermark.
- Backend: Adding `CORSMiddleware` to `app/main.py` for the extension.
- Chrome Extension: Scaffold in `extension/`, injecting a floating UI on MercadoLibre URLs.
- Marketing: Markdown files with Ad copy (Google Ads) and Blog content.

**OUT OF SCOPE:**
- Creating/executing actual Google Ads campaigns.
- Building a complex dashboard in the extension.
- Modifying the payment logic.

## Technical Approach & Guardrails (Metis)
1. **Watermark:** Must use low opacity/light gray to prevent barcode scanning failures. Diagonal text in PyMuPDF requires `fitz.Matrix` or `insert_text` with explicit angle/matrix if available.
2. **CORS & Auth:** `same_site="lax"` blocks cross-site cookies. Extension needs `host_permissions` and backend needs `CORSMiddleware` in `app/main.py` with `allow_credentials=True`.
3. **Extension UI:** Chrome does not allow programmatically opening the toolbar popup. The "pop-out" will be achieved by injecting a floating button/UI directly into the MercadoLibre DOM using a Content Script.
4. **Marketing:** Avoid "Mercado Libre" in Google Ads headlines to prevent trademark bans. Use "Etiquetas ML" or generic terms.

## Marketing Strategy (90% Organic / 10% Paid)
- **Organic:** Viral loop via watermark ("Generado gratis por meliops.cl"), SEO blog posts on label optimization.
- **Paid (Google Ads):** Targeting high-intent keywords ("unir pdf etiquetas ML") using generic copy.

## Tasks

### Task 1: Generate Marketing Assets
**Description:** Create the marketing strategy markdown files including Ad copy, Blog outlines, and the Google Ads setup guide.
**File:** `memory/marketing/strategy.md` (create new)
**Acceptance Criteria:**
- File `memory/marketing/strategy.md` exists.
- Contains section for SEO Blog Posts (Organic).
- Contains section for Google Ads copy avoiding trademark violations (e.g. "Etiquetas ML").
- Contains step-by-step Google Ads manual setup guide.
**QA Scenario:**
- `bash -c "cat memory/marketing/strategy.md | grep 'Etiquetas ML'"` (must succeed).

### Task 2: Backend CORS Configuration
**Description:** Add `CORSMiddleware` and update `SessionMiddleware` to allow the Chrome extension to make cross-origin authenticated requests.
**File:** `app/main.py`
**Instructions:** 
- Import `CORSMiddleware` from `fastapi.middleware.cors`.
- Add middleware allowing origins like `chrome-extension://*`, `https://*.mercadolibre.cl`, etc.
- Set `allow_credentials=True`.
- Update `SessionMiddleware` configuration to set `same_site="none"` and `https_only=True` (or `secure=True`) so Chrome allows cross-site cookies.
**Acceptance Criteria:**
- `app/main.py` has `CORSMiddleware` configured and `SessionMiddleware` updated.
**QA Scenario:**
- `pytest tests/` (all existing tests must pass).
- `curl -H "Origin: chrome-extension://test" -H "Access-Control-Request-Method: POST" -X OPTIONS -I http://localhost:8000/api/v1/extract` (must return 200 with CORS headers).

### Task 3: Implement Diagonal Watermark
**Description:** Inject a low-opacity diagonal watermark on every compiled PDF page.
**File:** `app/utils/extract_label.py`
**Instructions:**
- In `process_multiple_labels`, after each label is placed (or before saving), iterate through pages.
- Use PyMuPDF to add text: "Generado gratis por meliops.cl".
- Use font size ~40, light gray color `(0.9, 0.9, 0.9)`.
- Use a `fitz.Matrix` to rotate the text by 45 degrees, or `insert_text` if it supports `rotate=45` natively without breaking.
**Acceptance Criteria:**
- `extract_label.py` contains watermark logic.
**QA Scenario:**
- Write a quick python script `test_watermark.py` that calls `process_multiple_labels` with a mock PDF and checks that the output PDF contains the watermark text.

### Task 4: Build Chrome Extension
**Description:** Scaffold a Manifest V3 extension that injects a floating UI on MercadoLibre pages.
**Files:** `extension/manifest.json`, `extension/content.js`, `extension/background.js`, `extension/popup.html`, `extension/popup.js`.
**Instructions:**
- `manifest.json`: V3, permissions: `cookies`, `activeTab`, `host_permissions: ["*://*.mercadolibre.cl/*", "*://*.meliops.cl/*", "http://localhost:8000/*"]`.
- `content.js`: Matches `*://*.mercadolibre.cl/v3/sales*` (or equivalent ML domains). Injects a floating button "Optimizar Etiquetas" at the bottom right.
- `popup.html`: A fallback UI for manual triggering.
- `background.js`: Handles communication between content script and backend, ensuring cookies are sent (`credentials: 'include'`).
**Acceptance Criteria:**
- The `extension/` directory has all required files.
- `manifest.json` is valid JSON.
**QA Scenario:**
- `bash -c "jq .manifest_version extension/manifest.json"` (must output 3).

## Final Verification Wave
Wait for explicit approval from the user before executing these tasks.