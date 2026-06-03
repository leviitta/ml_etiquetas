# Draft: Bug and Security Improvements Planning

## Goal
Establish a comprehensive work plan for improving bug resilience and security posture of the ML Etiquetas project.

## Scope
- FastAPI routers and endpoint validation
- Google OAuth 2.0 implementation and Starlette SessionMiddleware security
- PDF extraction safety (PyMuPDF / fitz vulnerabilities, untrusted PDF files)
- Deployment script (`deploy_to_gcp.ps1`) and GCP credentials management
- Database security (Cloud SQL PostgreSQL, SQLAlchemy)

## Discovered Vulnerabilities & Bugs (Grounding Phase)
1. **Hardcoded Session Key Fallback** (`app/main.py`):
   Uses `"una_clave_secreta_de_respaldo"` as fallback, allowing session forgery if `SECRET_KEY` env var is missing.
2. **Client-Side Quota Trust** (`app/api/v1/router_extract.py` vs `router_quota.py`):
   `/extract` only verifies quota but does not record usage. Client registers usage via `/quota/register`. Attacker can call `/extract` directly and bypass quota limits.
3. **Payment Hijacking / Lack of Verification** (`app/api/v1/payments.py`):
   `/success` registers payment to current session email without checking if payment metadata email/reference matches. User A can claim User B's payment ID.
4. **Denial of Service (DoS) Risk** (`app/api/v1/router_extract.py`):
   No upload limits (file size, batch count, page count). Huge or malformed PDFs can crash or exhaust server memory.
5. **Insecure Session Cookie Options** (`app/main.py`):
   `SessionMiddleware` does not use `https_only=True` or `SameSite` options, risking session sniffing/CSRF.
6. **Insecure Temp Secret Handling** (`deploy_to_gcp.ps1`):
   Writes secrets to unencrypted `temp_secret.txt` on disk without `try/finally` cleanup guarantee.

## Proposed Strategy
- Register quota server-side in `/extract` endpoint after successful extraction.
- Cross-verify `external_reference` / `user_email` in payment `/success` callback.
- Add strict validation limits on uploads (files, size, pages).
- Configure secure session cookie flags (`https_only=True`, `samesite="lax"`) in main app.
- Harden deployment script secret writing with robust cleanup.
