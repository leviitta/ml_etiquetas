# Plan: ML Reprint Labels DOM Extraction

## Goal
Modify the Chrome extension's `content.js` to correctly extract ALL label download URLs, including those hidden under the "Reimprimir etiqueta" option in the 3-dots menus (`andes-floating-menu secondary-actions`), combining them into a single batch for extraction.

## Scope Boundaries
**IN SCOPE:**
- Modifying `extension/content.js` to add sequential DOM scraping for hidden portal menus.
- Adding a loading overlay during the scraping process to prevent user interaction and hide visual flicker.
- Updating URL filtering to include "reprint" and "reimprimir" keywords.

**OUT OF SCOPE:**
- Navigating to other pages (pagination). We only scrape the currently visible page.
- Modifying backend PDF extraction logic.
- Handling `<button>` based JS downloads if they bypass `href` entirely (assuming they use `<a>` tags with `href` for now, which is ML standard).

## Technical Approach & Guardrails (Metis)
1. **Sequential Clicking**: ML's UI (Andes) only allows one dropdown open at a time. We MUST click the 3-dots menus sequentially, wait for the portal to render, extract the link, and close it before moving to the next.
2. **Global Selector**: Since dropdowns render in React Portals at the end of the `<body>`, the link selector must search globally (`document.querySelectorAll('a')`) while the menu is open, not just inside `.row-card-container`.
3. **UX Protection**: Show a full-screen or prominent loading overlay ("⏳ Procesando etiquetas y buscando reimpresiones...") to block user clicks during the automated menu toggling.
4. **Failsafe**: Implement a short timeout (e.g., 300ms) for menu rendering to prevent infinite loops if a menu fails to open.

## Tasks

### Task 1: Update Link Filtering and DOM Simulation in `content.js`
**Description:** Modify `content.js` to sequentially click 3-dots menus, wait for portals, and extract links alongside visible ones.
**File:** `extension/content.js`
**Instructions:** 
- Add a loading overlay to the UI while searching.
- Create an async function `extractHiddenLinks()`.
- Find all visible standard links first (current logic but expanded keywords: `pdf`, `label`, `print`, `reprint`, `reimprimir`).
- Find all 3-dots menus: `document.querySelectorAll('.andes-floating-menu.secondary-actions, .andes-floating-menu')`.
- Loop through menus sequentially:
  - Scroll element into view (optional but good practice).
  - Click the menu button.
  - `await new Promise(r => setTimeout(r, 200))` to let React render the portal.
  - Search `document.querySelectorAll('.andes-list__item a, .andes-dropdown__menu a, body > div[data-focus-lock-disabled] a')` or just broadly `document.querySelectorAll('a')` that contain our target keywords.
  - Add found URLs to a `Set`.
  - Click the menu button again (or click `document.body`) to close it.
  - `await new Promise(r => setTimeout(r, 100))` to let it close.
- Combine all found URLs, remove duplicates, and send via `chrome.runtime.sendMessage({ action: "process_multiple_pdfs", urls })`.
**Acceptance Criteria:**
- `content.js` uses an async loop to handle menus.
- Loading indicator is shown during the process.
**QA Scenario:**
- Create a mock HTML file `tests/mock_ml_sales.html` containing:
  - A visible `<a>` with `href="https://.../print"`.
  - A `<button class="andes-floating-menu">` that, via a small inline JS, appends a `<div class="andes-dropdown"><a href="https://.../reprint">Reimprimir</a></div>` to `document.body` after 50ms when clicked.
- Create a simple script `tests/test_content_script.js` (using Playwright or JSDOM) that loads the mock HTML, runs `content.js`, clicks the floating button, and asserts that BOTH the `/print` and `/reprint` URLs are captured and sent to the background script.
- [x] Task 1 completed

## Final Verification Wave
Wait for explicit approval from the user before executing these tasks.