output "service_url" {
  value = google_cloud_run_v2_service.vigil.uri
}

output "image_repository" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}

output "runtime_service_account" {
  value = google_service_account.run.email
}

output "audit_dataset" {
  value = "${var.project_id}.${google_bigquery_dataset.audit.dataset_id}"
}
