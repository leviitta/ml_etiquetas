#!/usr/bin/env python3
import os
import sys
import json
import shutil
import subprocess
import argparse
import datetime
import time

def get_env_vars(env_path):
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, val = line.split('=', 1)
                    key = key.strip()
                    val = val.strip()
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    env_vars[key] = val
    # Fallback/override with os.environ
    for key, val in os.environ.items():
        env_vars[key] = val
    return env_vars

def run_command(cmd, dry_run=False, cwd=None, capture=False):
    print(f"Running: {' '.join(cmd)}")
    if dry_run:
        print("  [Dry-run] Command skipped.")
        return "" if capture else True
    use_shell = os.name == 'nt'
    try:
        if capture:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=cwd, shell=use_shell)
            return result.stdout.strip()
        else:
            subprocess.run(cmd, check=True, cwd=cwd, shell=use_shell)
            return True
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(cmd)}")
        print(f"Exit code: {e.returncode}")
        if capture:
            if e.stdout:
                print(f"Stdout: {e.stdout}")
            if e.stderr:
                print(f"Stderr: {e.stderr}")
        sys.exit(1)

def main():
    tf_cmd = "terraform"
    if not shutil.which("terraform") and shutil.which("terraform.exe"):
        tf_cmd = "terraform.exe"

    for tool in ["gcloud", "git"]:
        if not shutil.which(tool):
            print(f"Error: Required tool '{tool}' is not installed or not in PATH.")
            sys.exit(1)

    if not shutil.which(tf_cmd):
        print(f"Error: Required tool 'terraform' is not installed or not in PATH.")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="GCP Bootstrap, Secrets, and Deployment Automation")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--destroy", action="store_true", help="Destroy all resources created by Terraform")
    args = parser.parse_args()

    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env_path = os.path.join(root_dir, ".env")
    tf_dir = os.path.join(root_dir, "terraform")
    tfvars_path = os.path.join(tf_dir, "terraform.tfvars.json")

    print("=== GCP Bootstrap and Deployment Automation ===")
    
    # Detect active GCP account
    print("Detecting active GCP account...")
    gcloud_account_cmd = ["gcloud", "auth", "list", "--filter=status=ACTIVE", "--format=value(account)"]
    active_account = run_command(gcloud_account_cmd, dry_run=args.dry_run, capture=True)
    if active_account:
        print(f"Active GCP Account: {active_account}")
    else:
        print("Warning: No active GCP account detected. Please run 'gcloud auth login'.")

    print(f"Parsing environment variables...")
    env_vars = get_env_vars(env_path)

    mapping = {
        "GCP_PROJECT_ID": "project_id",
        "GCP_REGION": "region",
        "GCP_REPO": "repo_name",
        "GCP_SERVICE": "service_name",
        "DB_INSTANCE_NAME": "db_instance_name",
        "DB_NAME": "db_name",
        "DB_USER": "db_user",
        "DB_PASSWORD": "db_password",
        "GOOGLE_CLIENT_ID": "google_client_id",
        "GOOGLE_CLIENT_SECRET": "google_client_secret",
        "SECRET_KEY": "secret_key",
        "MP_ACCESS_TOKEN": "mp_access_token",
        "FREE_DAILY_QUOTA": "free_daily_quota",
        "FREE_MONTHLY_QUOTA": "free_monthly_quota",
        "PAID_MONTHLY_QUOTA": "paid_monthly_quota",
        "PAYMENT_DAYS": "payment_days",
        "PAYMENT_PRO_AMOUNT": "payment_pro_amount",
        "PAYMENT_INFINITY_AMOUNT": "payment_infinity_amount",
        "PAYMENT_UPGRADE_AMOUNT": "payment_upgrade_amount",
        "CUSTOM_DOMAIN": "custom_domain"
    }

    tfvars = {}
    for env_key, tf_key in mapping.items():
        if env_key in env_vars:
            tfvars[tf_key] = env_vars[env_key]

    # Get Git Commit SHA
    try:
        git_sha = run_command(["git", "rev-parse", "--short", "HEAD"], capture=True)
    except Exception:
        git_sha = "unknown"
    
    # Check if git is dirty
    is_dirty = False
    try:
        git_status = run_command(["git", "status", "--porcelain"], capture=True)
        if git_status:
            is_dirty = True
    except Exception:
        pass

    image_tag = git_sha
    if is_dirty:
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        image_tag = f"{git_sha}-dirty-{timestamp}"
    
    print(f"Determined image tag: {image_tag}")
    tfvars["image_tag"] = image_tag

    print(f"Generating {tfvars_path}...")
    if args.dry_run:
        print("  [Dry-run] Would write the following tfvars:")
        print(json.dumps(tfvars, indent=2))
    else:
        os.makedirs(tf_dir, exist_ok=True)
        with open(tfvars_path, 'w', encoding='utf-8') as f:
            json.dump(tfvars, f, indent=2)
        print(f"  Successfully wrote {tfvars_path}")

    project_id = env_vars.get("GCP_PROJECT_ID")
    region = env_vars.get("GCP_REGION", "us-central1")
    repo_name = env_vars.get("GCP_REPO", "ml-etiquetas-repo")

    if not project_id:
        print("Error: GCP_PROJECT_ID not found in .env or environment variables")
        sys.exit(1)

    bucket_name = f"{project_id}-tf-state"
    bucket_uri = f"gs://{bucket_name}"

    if args.destroy:
        print("=== Destroying Resources ===")
        init_cmd = [tf_cmd, "init", f"-backend-config=bucket={bucket_name}"]
        print(f"Initializing Terraform in {tf_dir}...")
        run_command(init_cmd, dry_run=args.dry_run, cwd=tf_dir)

        destroy_cmd = [tf_cmd, "destroy", "-auto-approve"]
        print(f"Running Terraform Destroy in {tf_dir}...")
        run_command(destroy_cmd, dry_run=args.dry_run, cwd=tf_dir)
        print("=== Destroy Completed Successfully ===")
        return

    print(f"Checking if GCS bucket {bucket_uri} exists...")
    check_cmd = ["gcloud", "storage", "buckets", "describe", bucket_uri, f"--project={project_id}"]
    
    bucket_exists = False
    if args.dry_run:
        print(f"  [Dry-run] Would check bucket existence with: {' '.join(check_cmd)}")
    else:
        try:
            subprocess.run(check_cmd, check=True, capture_output=True, text=True, shell=(os.name == 'nt'))
            bucket_exists = True
            print(f"  Bucket {bucket_uri} already exists.")
        except subprocess.CalledProcessError as e:
            stderr_lower = e.stderr.lower() if e.stderr else ""
            if "403" in stderr_lower or "permission" in stderr_lower or "denied" in stderr_lower:
                print(f"  Access to bucket {bucket_uri} denied or restricted (403). Assuming it already exists and proceeding...")
                bucket_exists = True
            else:
                print(f"  Bucket {bucket_uri} does not exist. Will create it.")

    if not bucket_exists and not args.dry_run:
        create_cmd = ["gcloud", "storage", "buckets", "create", bucket_uri, f"--project={project_id}", f"--location={region}"]
        run_command(create_cmd, dry_run=args.dry_run)

        versioning_cmd = ["gcloud", "storage", "buckets", "update", bucket_uri, "--versioning"]
        run_command(versioning_cmd, dry_run=args.dry_run)

        pap_cmd = ["gcloud", "storage", "buckets", "update", bucket_uri, "--public-access-prevention"]
        run_command(pap_cmd, dry_run=args.dry_run)

    elif not bucket_exists and args.dry_run:
        print(f"  [Dry-run] Would create bucket {bucket_uri}")
        print(f"  [Dry-run] Would enable versioning on {bucket_uri}")
        print(f"  [Dry-run] Would enable public access prevention on {bucket_uri}")

    init_cmd = [tf_cmd, "init", f"-backend-config=bucket={bucket_name}"]
    print(f"Initializing Terraform in {tf_dir}...")
    run_command(init_cmd, dry_run=args.dry_run, cwd=tf_dir)

    # Targeted apply of Artifact Registry
    target_apply_cmd = [tf_cmd, "apply", "-target=google_artifact_registry_repository.repo", "-auto-approve"]
    print("Running targeted apply for Artifact Registry...")
    run_command(target_apply_cmd, dry_run=args.dry_run, cwd=tf_dir)

    if not args.dry_run:
        print("Pausing for 10 seconds to allow Artifact Registry to propagate...")
        time.sleep(10)

    # Run Cloud Build with substitutions
    build_cmd = [
        "gcloud", "builds", "submit",
        "--config", "cloudbuild.yaml",
        f"--project={project_id}",
        f"--substitutions=_IMAGE_TAG={image_tag},_REGION={region},_REPO_NAME={repo_name}",
        "."
    ]
    print("Submitting build to Google Cloud Build...")
    run_command(build_cmd, dry_run=args.dry_run, cwd=root_dir)

    # Final full apply
    final_apply_cmd = [tf_cmd, "apply", "-auto-approve"]
    print("Running final full Terraform apply...")
    run_command(final_apply_cmd, dry_run=args.dry_run, cwd=tf_dir)

    print("=== Bootstrap and Deployment Completed Successfully ===")

if __name__ == "__main__":
    main()