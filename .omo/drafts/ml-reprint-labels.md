# Draft: ML Reprint Labels DOM Extraction

## Goal
Modify the Chrome extension's `content.js` to correctly extract label download URLs even when the primary "Imprimir etiqueta" button has changed to "Donde lo despacho", and the label link is hidden under the "Reimprimir etiqueta" option in the 3-dots menu (`andes-floating-menu secondary-actions`).

## Known Context
- The user is on the MercadoLibre sales list (`/ventas/omni/listado` or `/v3/sales`).
- State 1: A visible `<a>` or `<button>` with "Imprimir Etiqueta" exists.
- State 2: A button "Donde lo despacho" exists. The actual print link is inside a secondary menu (3 dots) called `andes-floating-menu secondary-actions`. The menu item says "Reimprimir etiqueta".
- The user wants the "Optimizar Etiquetas" button to gather ALL labels (new ones AND reprinted ones) in batch.

## Open Questions & Risks
- **DOM Presence**: Do the "Reimprimir etiqueta" links exist in the DOM *before* the 3-dots menu is clicked? If ML uses React, the dropdown menu might only be rendered into the DOM upon click.
- **Portal Rendering**: If rendered, is the dropdown inside `.row-card-container` or appended to `document.body` (React Portal)? If attached to the body, our `querySelectorAll(".row-card-container a")` will miss it.
- **Link Format**: Is the "Reimprimir" option an actual `<a>` tag with an href? Or a `<button>` with an `onClick` handler?

## Technical Strategy
Since we cannot guarantee the "Reimprimir" links are in the DOM or have simple `href` attributes before clicking, the most robust approach for the Chrome extension is:

1. **Broaden the DOM Selector**:
   - Instead of just looking inside `.row-card-container a`, look across the whole document for any `<a>` tag containing keywords.
   - Include keywords like `"reprint"`, `"reimprimir"`, `"pdf"`, `"label"`, `"print"` in the `href` filter.

2. **Automated Menu Extraction (DOM Simulation)**:
   - If the links are NOT in the DOM until clicked, `content.js` should:
     a. Find all 3-dots menu buttons (`.andes-floating-menu`, `.secondary-actions`).
     b. Programmatically dispatch a `click` event on each to force MercadoLibre to render the dropdown menus into the DOM.
     c. Wait a brief moment (e.g., `setTimeout` 100ms or `MutationObserver`).
     d. Scrape the newly rendered DOM for the `<a>` tags corresponding to "Reimprimir etiqueta".
     e. Programmatically click again (or click outside) to close the menus.

3. **Fallback to API Interception**:
   - If it's a `<button>` triggering an API call (no `href`), we might need to intercept XHR/fetch requests or scrape the React component props (harder). Let's stick to DOM Simulation + Broad Selector first, as ML usually uses `<a>` tags for PDF downloads.
