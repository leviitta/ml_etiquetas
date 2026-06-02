output "workload_identity_provider" {
  value       = google_iam_workload_identity_pool_provider.github_provider.name
  description = "The Workload Identity Provider resource name"
}

output "deploy_service_account_email" {
  value       = google_service_account.deploy_sa.email
  description = "The Deploy Service Account email"
}

output "cloud_run_url" {
  value       = google_cloud_run_v2_service.app.uri
  description = "The URL of the Cloud Run service"
}
