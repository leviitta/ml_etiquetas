locals {
  database_url = "postgresql://${var.db_user}:${urlencode(var.db_password)}@/${var.db_name}?host=/cloudsql/${google_sql_database_instance.postgres.connection_name}"
}

# Enable APIs
resource "google_project_service" "services" {
  for_each = toset([
    "secretmanager.googleapis.com",
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "iam.googleapis.com",
    "sqladmin.googleapis.com",
    "artifactregistry.googleapis.com",
    "iamcredentials.googleapis.com"
  ])
  service            = each.key
  disable_on_destroy = false
}

# Artifact Registry Repository
resource "google_artifact_registry_repository" "repo" {
  depends_on    = [google_project_service.services]
  location      = var.region
  repository_id = var.repo_name
  description   = "Docker repository for ML Etiquetas"
  format        = "DOCKER"
}

# Cloud SQL Instance
resource "google_sql_database_instance" "postgres" {
  depends_on       = [google_project_service.services]
  name             = var.db_instance_name
  database_version = "POSTGRES_15"
  region           = var.region

  settings {
    tier            = "db-f1-micro"
    disk_autoresize = true
    backup_configuration {
      enabled    = true
      start_time = "03:00"
    }
  }
  deletion_protection = true
}

# Cloud SQL Database
resource "google_sql_database" "database" {
  name     = var.db_name
  instance = google_sql_database_instance.postgres.name
}

# Cloud SQL User
resource "google_sql_user" "user" {
  name     = var.db_user
  instance = google_sql_database_instance.postgres.name
  password = var.db_password
}

# Service Account for running Cloud Run
resource "google_service_account" "cloud_run_sa" {
  depends_on   = [google_project_service.services]
  account_id   = var.run_service_account_id
  display_name = "Service Account for running ML Etiquetas"
}

# Service Account for deploying Cloud Run
resource "google_service_account" "deploy_sa" {
  depends_on   = [google_project_service.services]
  account_id   = var.deploy_service_account_id
  display_name = "Service Account for deploying ML Etiquetas"
}

# IAM Roles for Cloud Run Service Account
resource "google_project_iam_member" "cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# Secret Manager Secrets
resource "google_secret_manager_secret" "secrets" {
  for_each = toset([
    "GOOGLE_CLIENT_SECRET",
    "SECRET_KEY",
    "MP_ACCESS_TOKEN",
    "DATABASE_URL"
  ])
  depends_on = [google_project_service.services]
  secret_id  = each.key
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "secret_versions" {
  for_each = {
    "GOOGLE_CLIENT_SECRET" = var.google_client_secret
    "SECRET_KEY"           = var.secret_key
    "MP_ACCESS_TOKEN"      = var.mp_access_token
    "DATABASE_URL"         = local.database_url
  }
  secret      = google_secret_manager_secret.secrets[each.key].id
  secret_data = each.value
}

# Secret Manager Access for Cloud Run Service Account
resource "google_secret_manager_secret_iam_member" "secret_accessor" {
  for_each = toset([
    "GOOGLE_CLIENT_SECRET",
    "SECRET_KEY",
    "MP_ACCESS_TOKEN",
    "DATABASE_URL"
  ])
  secret_id = google_secret_manager_secret.secrets[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# Cloud Run Service (Gen2)
resource "google_cloud_run_v2_service" "app" {
  depends_on = [
    google_project_service.services,
    google_sql_database_instance.postgres,
    google_secret_manager_secret_iam_member.secret_accessor,
    google_secret_manager_secret_version.secret_versions
  ]
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.cloud_run_sa.email

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.repo_name}/app:${var.image_tag}"

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          memory = "1Gi"
          cpu    = "1"
        }
      }

      # Environment Variables
      env {
        name  = "GOOGLE_CLIENT_ID"
        value = var.google_client_id
      }
      env {
        name  = "FREE_DAILY_QUOTA"
        value = var.free_daily_quota
      }
      env {
        name  = "FREE_MONTHLY_QUOTA"
        value = var.free_monthly_quota
      }
      env {
        name  = "PAID_MONTHLY_QUOTA"
        value = var.paid_monthly_quota
      }
      env {
        name  = "PAYMENT_DAYS"
        value = var.payment_days
      }
      env {
        name  = "PAYMENT_PRO_AMOUNT"
        value = var.payment_pro_amount
      }
      env {
        name  = "PAYMENT_INFINITY_AMOUNT"
        value = var.payment_infinity_amount
      }
      env {
        name  = "PAYMENT_UPGRADE_AMOUNT"
        value = var.payment_upgrade_amount
      }
      env {
        name  = "REDIRECT_URI"
        value = "https://${var.custom_domain}/api/v1/auth/callback"
      }
      env {
        name  = "BASE_URL"
        value = "https://${var.custom_domain}"
      }

      dynamic "env" {
        for_each = toset(["GOOGLE_CLIENT_SECRET", "SECRET_KEY", "MP_ACCESS_TOKEN", "DATABASE_URL"])
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.secrets[env.key].secret_id
              version = google_secret_manager_secret_version.secret_versions[env.key].version
            }
          }
        }
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.postgres.connection_name]
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
}

# Allow unauthenticated access to Cloud Run
resource "google_cloud_run_v2_service_iam_member" "noauth" {
  location = google_cloud_run_v2_service.app.location
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Workload Identity Pool
resource "google_iam_workload_identity_pool" "github_pool" {
  depends_on                = [google_project_service.services]
  workload_identity_pool_id = "github-actions-pool"
  display_name              = "GitHub Actions Pool"
  description               = "Workload Identity Pool for GitHub Actions"
}

# Workload Identity Provider
resource "google_iam_workload_identity_pool_provider" "github_provider" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_pool.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-actions-provider"
  display_name                       = "GitHub Actions Provider"
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }
  attribute_condition = "attribute.repository == 'leviitta/ml_etiquetas'"
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# Allow GitHub Actions to impersonate the Service Account
resource "google_service_account_iam_member" "wif_sa_user" {
  service_account_id = google_service_account.deploy_sa.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_pool.name}/attribute.repository/leviitta/ml_etiquetas"
}

# Grant Service Account permissions to deploy to Cloud Run and write to Artifact Registry
resource "google_project_iam_member" "sa_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.deploy_sa.email}"
}

resource "google_project_iam_member" "sa_sa_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.deploy_sa.email}"
}

resource "google_project_iam_member" "sa_ar_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.admin"
  member  = "serviceAccount:${google_service_account.deploy_sa.email}"
}

resource "google_project_iam_member" "sa_cloudsql_admin" {
  project = var.project_id
  role    = "roles/cloudsql.admin"
  member  = "serviceAccount:${google_service_account.deploy_sa.email}"
}

resource "google_project_iam_member" "sa_secretmanager_admin" {
  project = var.project_id
  role    = "roles/secretmanager.admin"
  member  = "serviceAccount:${google_service_account.deploy_sa.email}"
}

resource "google_project_iam_member" "sa_project_iam_admin" {
  project = var.project_id
  role    = "roles/resourcemanager.projectIamAdmin"
  member  = "serviceAccount:${google_service_account.deploy_sa.email}"
}

resource "google_project_iam_member" "sa_service_usage_admin" {
  project = var.project_id
  role    = "roles/serviceusage.serviceUsageAdmin"
  member  = "serviceAccount:${google_service_account.deploy_sa.email}"
}

resource "google_project_iam_member" "sa_service_account_admin" {
  project = var.project_id
  role    = "roles/iam.serviceAccountAdmin"
  member  = "serviceAccount:${google_service_account.deploy_sa.email}"
}

resource "google_project_iam_member" "sa_workload_identity_pool_admin" {
  project = var.project_id
  role    = "roles/iam.workloadIdentityPoolAdmin"
  member  = "serviceAccount:${google_service_account.deploy_sa.email}"
}

resource "google_project_iam_member" "sa_storage_object_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.deploy_sa.email}"
}

# Cloud Run Domain Mapping
resource "google_cloud_run_domain_mapping" "domain_mapping" {
  depends_on = [google_cloud_run_v2_service.app]
  location   = var.region
  name       = var.custom_domain

  metadata {
    namespace = var.project_id
  }

  spec {
    route_name = google_cloud_run_v2_service.app.name
  }
}
