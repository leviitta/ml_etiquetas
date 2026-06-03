# Learnings - GCP Orchestration Improvements

- **Terraform Cloud SQL settings**: The argument for enabling automatic storage increase in `google_sql_database_instance` settings block is `disk_autoresize = true`, not `storage_auto_increase` or `storage_auto_resize`.
- **Workload Identity Federation (WIF)**: Separating the service account used to run the application (`ml-etiquetas-run-sa`) from the service account used to deploy the application (`ml-etiquetas-deploy-sa`) follows the principle of least privilege. The deploy service account is impersonated by GitHub Actions via WIF and has permissions to deploy to Cloud Run and write to Artifact Registry.
