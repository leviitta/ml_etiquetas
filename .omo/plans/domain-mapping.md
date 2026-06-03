# Plan: Implement Cloud Run Domain Mapping

## 1. Context and Goals
- **Goal**: Map the Cloud Run service `google_cloud_run_v2_service.app` to a custom domain using the Terraform resource `google_cloud_run_domain_mapping`.
- **Inputs**: The custom domain URL is already available in the environment variables and passed into Terraform as `var.custom_domain` (default: `www.meliops.cl`).
- **Dependencies**: The `google_cloud_run_domain_mapping` resource requires the Cloud Run API (`run.googleapis.com`), which is already enabled. The domain mapping also implicitly depends on the `google_cloud_run_v2_service.app`.

## 2. Technical Approach
- We will add the `google_cloud_run_domain_mapping` resource to `terraform/main.tf` at the end of the file.
- The `google_cloud_run_domain_mapping` uses the `location` and `project` derived from the existing configuration.
- The `spec { route_name = ... }` points to `google_cloud_run_v2_service.app.name`.

## 3. Tasks

### Task 1: Append `google_cloud_run_domain_mapping` resource
**File**: `terraform/main.tf`
**Action**: Add the following code block to the end of the file.

- [x] Files created/modified: `terraform/main.tf`
- [x] Functionality: The `google_cloud_run_domain_mapping` resource is added to the end of the file.
- [x] Verification: `terraform fmt` passes.

```hcl
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
```

### Task 2: Validate the Terraform Configuration
**Action**: Run `terraform plan` in the `terraform/` directory to ensure there are no syntax errors or conflicts in the configuration, and that it successfully creates 1 resource (the domain mapping) without forcing replacement of other resources.
- [x] `cd terraform && terraform fmt`
- [x] `terraform plan`

## Final Verification Wave
1. Ensure the `terraform plan` output correctly shows the domain mapping being added.
2. Confirm the user will need to configure DNS records based on the domain mapping output (e.g., CNAME or A records) provided by Google Cloud, which can be done post-deployment.
