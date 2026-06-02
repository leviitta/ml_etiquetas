variable "project_id" {
  type        = string
  description = "The GCP Project ID"
  default     = "ml-etiquetas"
}

variable "region" {
  type        = string
  description = "The GCP Region"
  default     = "us-central1"
}

variable "repo_name" {
  type        = string
  description = "The Artifact Registry repository name"
  default     = "ml-etiquetas-repo"
}

variable "service_name" {
  type        = string
  description = "The Cloud Run service name"
  default     = "ml-etiquetas-service"
}

variable "run_service_account_id" {
  type        = string
  description = "The Service Account ID for running the application"
  default     = "ml-etiquetas-run-sa"
}

variable "deploy_service_account_id" {
  type        = string
  description = "The Service Account ID for deploying the application"
  default     = "ml-etiquetas-deploy-sa"
}

variable "db_instance_name" {
  type        = string
  description = "The Cloud SQL instance name"
  default     = "ml-etiquetas-db"
}

variable "db_name" {
  type        = string
  description = "The database name"
  default     = "mldb"
}

variable "db_user" {
  type        = string
  description = "The database user"
  default     = "MeliOpsDB"
}

variable "db_password" {
  type        = string
  description = "The database password"
  sensitive   = true
}

variable "google_client_secret" {
  type        = string
  description = "The Google OAuth Client Secret"
  sensitive   = true
}

variable "secret_key" {
  type        = string
  description = "The application secret key"
  sensitive   = true
}

variable "mp_access_token" {
  type        = string
  description = "The Mercado Pago Access Token"
  sensitive   = true
}

variable "google_client_id" {
  type        = string
  description = "The Google OAuth Client ID"
}

variable "free_daily_quota" {
  type        = string
  description = "Free daily quota"
  default     = "5"
}

variable "free_monthly_quota" {
  type        = string
  description = "Free monthly quota"
  default     = "20"
}

variable "paid_monthly_quota" {
  type        = string
  description = "Paid monthly quota"
  default     = "100"
}

variable "payment_days" {
  type        = string
  description = "Payment validity days"
  default     = "30"
}

variable "payment_pro_amount" {
  type        = string
  description = "Payment Pro amount"
  default     = "9990"
}

variable "payment_infinity_amount" {
  type        = string
  description = "Payment Infinity amount"
  default     = "15990"
}

variable "payment_upgrade_amount" {
  type        = string
  description = "Payment Upgrade amount"
  default     = "5000"
}

variable "custom_domain" {
  type        = string
  description = "Custom domain for the application"
  default     = "www.meliops.cl"
}
