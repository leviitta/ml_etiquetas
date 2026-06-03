# Decisions

- Created `scripts/bootstrap.py` to handle the chicken-and-egg problem of GCS state bucket creation and `.env` parsing.
- Removed hardcoded bucket name from `terraform/providers.tf` to allow dynamic backend configuration.
- Added `lifecycle { ignore_changes = [template[0].containers[0].image] }` to Cloud Run service in Terraform to allow CI/CD to update the image without Terraform reverting it.
- Simplified `deploy_to_gcp.ps1` and `.github/workflows/deploy.yml` to only update the image, leaving all configuration and secrets management to Terraform.
