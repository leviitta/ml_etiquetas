# Decisions - GCP Orchestration Improvements

- **Separation of Service Accounts**: Created two distinct service accounts:
  - `ml-etiquetas-run-sa`: Used by the Cloud Run service to run the application. It only has access to Secret Manager secrets and Cloud SQL.
  - `ml-etiquetas-deploy-sa`: Used by GitHub Actions to deploy the application. It has permissions to deploy to Cloud Run, write to Artifact Registry, and act as the run service account.
- **Deletion Protection**: Enabled `deletion_protection = true` on the Cloud SQL instance to prevent accidental database deletion in production.
- **Dummy Image**: Used `gcr.io/cloudrun/hello` as the initial image for the Cloud Run service to resolve the chicken-and-egg problem where the service must exist before the deployment pipeline can run.
