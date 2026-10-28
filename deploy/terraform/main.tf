terraform {
  required_version = ">= 1.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
  # Secrets (signal key) are generated here and therefore live in state.
  # Use an encrypted remote backend with restricted access, for example:
  # backend "gcs" { bucket = "<your-tf-state-bucket>" prefix = "vigil" }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  apis = [
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "secretmanager.googleapis.com",
    "aiplatform.googleapis.com",
    "bigquery.googleapis.com",
    "logging.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  service            = each.value
  disable_on_destroy = false
}

# ---------- image registry ----------
resource "google_artifact_registry_repository" "images" {
  repository_id = var.service_name
  location      = var.region
  format        = "DOCKER"
  description   = "Vigil container images"
  depends_on    = [google_project_service.apis]
}

# ---------- identity: least privilege ----------
resource "google_service_account" "run" {
  account_id   = "vigil-run"
  display_name = "Vigil Cloud Run runtime"
}

resource "google_project_iam_member" "run_vertex" {
  count   = var.llm_enabled ? 1 : 0
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.run.email}"
}

resource "google_project_iam_member" "run_logs" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.run.email}"
}

# ---------- secrets ----------
resource "random_password" "signal_key" {
  length  = 32
  special = false
}

resource "google_secret_manager_secret" "signal_key" {
  secret_id = "vigil-signal-key"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "signal_key" {
  secret = google_secret_manager_secret.signal_key.id
  # The app expects base64 (see Settings.signal_key).
  secret_data = base64encode(random_password.signal_key.result)
}

resource "google_secret_manager_secret" "api_keys" {
  secret_id = "vigil-api-key-digests"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "api_keys" {
  secret      = google_secret_manager_secret.api_keys.id
  secret_data = var.api_key_digests == "" ? "unset" : var.api_key_digests
}

resource "google_secret_manager_secret_iam_member" "run_secrets" {
  for_each = {
    signal = google_secret_manager_secret.signal_key.id
    keys   = google_secret_manager_secret.api_keys.id
  }
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.run.email}"
}

# ---------- Cloud Run ----------
resource "google_cloud_run_v2_service" "vigil" {
  name                = var.service_name
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = google_service_account.run.email
    timeout         = "30s"
    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }
    max_instance_request_concurrency = 40

    containers {
      image = var.image
      ports {
        container_port = 8080
      }
      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }
      env {
        name  = "VIGIL_ENV"
        value = var.env
      }
      env {
        name  = "VIGIL_LLM_ENABLED"
        value = tostring(var.llm_enabled)
      }
      env {
        name  = "VIGIL_TRUSTED_PROXY_HOPS"
        value = "1"
      }
      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "true"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = "global"
      }
      env {
        name = "VIGIL_SIGNAL_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.signal_key.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "VIGIL_API_KEYS"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.api_keys.secret_id
            version = "latest"
          }
        }
      }
      startup_probe {
        http_get {
          path = "/readyz"
        }
        initial_delay_seconds = 5
        period_seconds        = 5
        failure_threshold     = 12
      }
      liveness_probe {
        http_get {
          path = "/healthz"
        }
        period_seconds = 30
      }
    }
  }

  lifecycle {
    # Cloud Build ships new images; Terraform should not revert them.
    ignore_changes = [template[0].containers[0].image, client, client_version]
  }

  depends_on = [
    google_project_service.apis,
    google_secret_manager_secret_version.signal_key,
    google_secret_manager_secret_version.api_keys,
    google_secret_manager_secret_iam_member.run_secrets,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  count    = var.public_access ? 1 : 0
  name     = google_cloud_run_v2_service.vigil.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ---------- audit trail: Cloud Logging -> BigQuery ----------
# Decisions are logged without transcripts, payees or amounts (see vigil.obs / routes).
resource "google_bigquery_dataset" "audit" {
  dataset_id                  = "vigil_audit"
  location                    = var.region
  description                 = "Vigil decision audit log (no PII)."
  default_table_expiration_ms = var.audit_retention_days * 24 * 3600 * 1000
  depends_on                  = [google_project_service.apis]
}

resource "google_logging_project_sink" "audit" {
  name                   = "vigil-audit-to-bigquery"
  destination            = "bigquery.googleapis.com/projects/${var.project_id}/datasets/${google_bigquery_dataset.audit.dataset_id}"
  filter                 = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${var.service_name}\" AND jsonPayload.logger=\"vigil.audit\""
  unique_writer_identity = true

  bigquery_options {
    use_partitioned_tables = true
  }
}

resource "google_bigquery_dataset_iam_member" "sink_writer" {
  dataset_id = google_bigquery_dataset.audit.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = google_logging_project_sink.audit.writer_identity
}
