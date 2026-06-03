# Learnings

- Python is highly robust for parsing `.env` files and generating `terraform.tfvars.json` dynamically.
- Separating configuration management (Terraform) from image deployment (CI/CD and PowerShell scripts) prevents configuration drift and accidental overrides.
- Pinning secret versions in Cloud Run using Terraform's `google_secret_manager_secret_version` resource ensures that changes to secrets trigger a new revision deployment automatically.
