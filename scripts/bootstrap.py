#!/usr/bin/env python3
import os
import sys
import json
import subprocess
import argparse

def parse_env(env_path):
    env_vars = {}
    if not os.path.exists(env_path):
        print(f"Error: {env_path} not found.")
        sys.exit(1)
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
    return env_vars

def run_command(cmd, dry_run=False, cwd=None):
    print(f"Running: {' '.join(cmd)}")
    if dry_run:
        print("  [Dry-run] Command skipped.")
        return True
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=cwd)
        if result.stdout:
            print(result.stdout.strip())
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(cmd)}")
        print(f"Exit code: {e.returncode}")
        if e.stdout:
            print(f"Stdout: {e.stdout}")
        if e.stderr:
            print(f"Stderr: {e.stderr}")
        return False

def main():
    parser = argparse.ArgumentParser(description="GCP Bootstrap and Secrets Automation")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    args = parser.parse_args()

    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env_path = os.path.join(root_dir, ".env")
    tf_dir = os.path.join(root_dir, "terraform")
    tfvars_path = os.path.join(tf_dir, "terraform.tfvars.json")

    print("=== GCP Bootstrap and Secrets Automation ===")
    print(f"Parsing .env from {env_path}...")
    env_vars = parse_env(env_path)

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

    if not project_id:
        print("Error: GCP_PROJECT_ID not found in .env")
        sys.exit(1)

    bucket_name = f"{project_id}-tf-state"
    bucket_uri = f"gs://{bucket_name}"

    print(f"Checking if GCS bucket {bucket_uri} exists...")
    check_cmd = ["gcloud", "storage", "buckets", "describe", bucket_uri, f"--project={project_id}"]
    
    bucket_exists = False
    if args.dry_run:
        print(f"  [Dry-run] Would check bucket existence with: {' '.join(check_cmd)}")
    else:
        try:
            subprocess.run(check_cmd, check=True, capture_output=True, text=True)
            bucket_exists = True
            print(f"  Bucket {bucket_uri} already exists.")
        except subprocess.CalledProcessError:
            print(f"  Bucket {bucket_uri} does not exist. Will create it.")

    if not bucket_exists and not args.dry_run:
        create_cmd = ["gcloud", "storage", "buckets", "create", bucket_uri, f"--project={project_id}", f"--location={region}"]
        if not run_command(create_cmd, dry_run=args.dry_run):
            sys.exit(1)

        versioning_cmd = ["gcloud", "storage", "buckets", "update", bucket_uri, "--versioning"]
        if not run_command(versioning_cmd, dry_run=args.dry_run):
            sys.exit(1)

        pap_cmd = ["gcloud", "storage", "buckets", "update", bucket_uri, "--public-access-prevention"]
        if not run_command(pap_cmd, dry_run=args.dry_run):
            sys.exit(1)

    elif not bucket_exists and args.dry_run:
        print(f"  [Dry-run] Would create bucket {bucket_uri}")
        print(f"  [Dry-run] Would enable versioning on {bucket_uri}")
        print(f"  [Dry-run] Would enable public access prevention on {bucket_uri}")

    init_cmd = ["terraform", "init", f"-backend-config=bucket={bucket_name}"]
    print(f"Initializing Terraform in {tf_dir}...")
    if not run_command(init_cmd, dry_run=args.dry_run, cwd=tf_dir):
        sys.exit(1)

    print("=== Bootstrap Completed Successfully ===")

if __name__ == "__main__":
    main()
