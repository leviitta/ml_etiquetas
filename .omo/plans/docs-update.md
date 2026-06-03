# Plan: Update Project Documentation

## 1. Context and Goals
- **Goal**: Synchronize all project documentation (`README.md`) with the actual state of the codebase and infrastructure.
- **Background**: The project has evolved significantly. Deployment moved from PowerShell scripts to Python/Terraform/GitHub Actions. A quota system and Mercado Pago integration were added. The database uses `asyncpg` directly, not SQLAlchemy. The API behavior (hardcoded 6-label grid) differs from the documented configurable grid.
- **Success Criteria**: All environment variables are documented, API endpoints match reality, deployment instructions reflect the current CI/CD and bootstrap script, and redundant/obsolete files are removed.

## 2. Technical Approach
- **Update README.md**: Rewrite sections on Features, Environment Variables, Local Development, Deployment, and API Reference to match the current codebase.

## 3. Tasks

### Task 1: Update `README.md` - Deployment and Architecture
- [ ] Update the **Arquitectura del proyecto** and **Stack tecnológico** sections to include the Quota System and Mercado Pago integration.
- [ ] Rewrite the **Despliegue en Google Cloud Run** section to remove `.ps1` scripts and properly document `python scripts/bootstrap.py` and the GitHub Actions CI/CD pipeline.
**QA Scenario**: Use `read` on `README.md` and visually verify that the Arquitectura and Despliegue sections match the requirements, and `grep` for `.ps1` in `README.md` to ensure no matches.

### Task 2: Update `README.md` - Environment Variables
- [ ] Expand the **Variables de entorno** section to include all active variables:
  - Database: `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DATABASE_URL`
  - Mercado Pago: `MP_ACCESS_TOKEN`, `MP_WEBHOOK_SECRET`, `BASE_URL`
  - Pricing/Quotas: `PAYMENT_PRO_AMOUNT`, `PAYMENT_INFINITY_AMOUNT`, `PAYMENT_UPGRADE_AMOUNT`, `PAYMENT_DAYS`, `FREE_DAILY_QUOTA`, `FREE_MONTHLY_QUOTA`, `PAID_MONTHLY_QUOTA`
  - Testing: `TESTING`, `TESTING_WITH_REAL_DB`
**QA Scenario**: Use `grep` on `README.md` for each of the new environment variables (e.g., `PAYMENT_PRO_AMOUNT`, `MP_WEBHOOK_SECRET`) and verify they are documented in the file.

### Task 3: Update `README.md` - API Reference and Features
- [ ] Update the `/api/v1/extract` endpoint documentation: remove `labels_per_page` (clarify it uses a fixed 2x3 grid) and mention the extraction of product details.
- [ ] Add documentation for new endpoints: `/faq`, `/api/v1/quota/register`, Mercado Pago webhooks and callbacks, `/robots.txt`, and `/sitemap.xml`.
**QA Scenario**: Use `read` on `README.md` to verify the API Reference section correctly reflects the actual API endpoints, especially `/api/v1/extract` and `/api/v1/quota/register`.

## Final Verification Wave
- [x] Read `README.md` to ensure no `.ps1` references exist.
- [x] Confirm all environment variables required by Terraform/Cloud Run are listed in the markdown.