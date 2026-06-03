# Plan: Fix File Size Limit and Fetch Authentication

## Goal
Resolve the "El archivo supera el límite de tamaño permitido de 200 KB" error when optimizing labels from the Chrome extension.

## Scope Boundaries
**IN SCOPE:**
- Modify backend file size limits to accommodate larger PDFs.
- Update the Chrome extension to authenticate PDF downloads from MercadoLibre.

## Technical Approach
1. **Increase Backend File Size Limit**: Some PDFs or fetched files might be larger than the hardcoded 200 KB limit. We will increase the limit in `app/api/v1/router_extract.py` from 200 KB to 2 MB (2000 KB).
2. **Authenticate Extension Fetch**: When `extension/background.js` downloads the PDF from MercadoLibre via `fetch(url)`, it currently does not include cookies. If MercadoLibre requires an active session, the fetch might be redirected to an HTML login page (which can easily exceed 200 KB). We need to add `credentials: "include"` to the `fetch` call and verify that the `content-type` of the response is indeed `application/pdf`.

## Tasks

### Task 1: Increase Backend Upload Limit
**Description:** Modify `router_extract.py` to allow file uploads up to 2 MB.
**File:** `app/api/v1/router_extract.py`
**Instructions:**
- Locate the file size validation logic (`size > 200 * 1024`).
- Change the limit to `2000 * 1024`.
- Update the error message to state "2 MB" instead of "200 KB".
**Acceptance Criteria:**
- The size validation checks for `2000 * 1024`.
**QA Scenario:**
- Use `grep` to verify the new size limit code is present in `app/api/v1/router_extract.py`.
- [x] Task 1 completed

### Task 2: Fix Extension Fetch Authentication and Validation
**Description:** Modify `background.js` to fetch PDFs with credentials and validate content type.
**File:** `extension/background.js`
**Instructions:**
- In `processMultiplePdfs` and `processPdfUrl`, update `fetch(url)` to `fetch(url, { credentials: "include" })`.
- After fetching the PDF, check the `content-type` header. If it doesn't include "pdf" or "octet-stream", throw a user-friendly error (e.g., "El archivo descargado no es un PDF válido. Verifica tu sesión de MercadoLibre.").
**Acceptance Criteria:**
- Both `fetch` calls to original ML URLs use `credentials: "include"`.
- Both `fetch` calls validate the `content-type` header.
**QA Scenario:**
- Use `grep` to verify `credentials: "include"` is present in the `pdfResponse` fetch calls inside `extension/background.js`.
- [x] Task 2 completed