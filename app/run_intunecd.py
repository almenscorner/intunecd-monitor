import os
import shutil
import subprocess
import pytz
import json
import random
import shutil

from app import app_config
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from celery import shared_task
from datetime import datetime
from git import Repo
from app.models import (
    intunecd_tenants,
    summary_changes,
    summary_diff_count,
    summary_average_diffs,
    summary_config_count,
    summary_assignments,
)
from app import db


def get_now():
    tz = pytz.timezone(os.environ.get("TIMEZONE", "UTC"))
    now = datetime.now(tz)
    date_now = now.strftime("%Y-%m-%d %H:%M:%S")

    return date_now


def get_connection_info(TENANT_ID):
    credential = DefaultAzureCredential()
    client = SecretClient(app_config.AZURE_VAULT_URL, credential)
    tenant = intunecd_tenants.query.get(TENANT_ID)
    baseline = intunecd_tenants.query.filter_by(baseline="true").first()

    if not tenant.repo or tenant.baseline == "true":
        baseline = intunecd_tenants.query.filter_by(baseline="true").first()
        repo_url_base = baseline.repo
        pat = client.get_secret(baseline.vault_name).value
    else:
        repo_url_base = tenant.repo
        pat = client.get_secret(tenant.vault_name).value

    repo_url = f"https://IntuneCDMonitor:{pat}@{repo_url_base}"

    return (repo_url, tenant.name)


@shared_task(ignore_result=False)
def run_intunecd_update(TENANT_ID):
    REPO_URL, AAD_TENANT_NAME = get_connection_info(TENANT_ID)

    os.environ["TENANT_NAME"] = AAD_TENANT_NAME
    os.environ["CLIENT_ID"] = app_config.AZURE_CLIENT_ID
    os.environ["CLIENT_SECRET"] = app_config.AZURE_CLIENT_SECRET

    intunecd_tenant = intunecd_tenants.query.filter_by(id=TENANT_ID).first()

    date_now = get_now()

    if not all(
        [
            os.getenv("TENANT_NAME"),
            os.getenv("CLIENT_ID"),
            os.getenv("CLIENT_SECRET"),
        ]
    ):
        intunecd_tenant.last_update = date_now
        intunecd_tenant.last_update_message = "Could not get environment variables"
        intunecd_tenant.last_update_status = "error"

        db.session.commit()

        return {
            "status": "error",
            "message": "Could not get environment variables",
            "date": date_now,
        }

    # Clone the repository
    try:
        folder_name = f"tmp{random.randint(100000, 999999)}"
        local_path = f"/intunecd/git/{folder_name}"
        if os.path.exists(local_path):
            shutil.rmtree(local_path)

        Repo.clone_from(REPO_URL, local_path)

    except:
        intunecd_tenant.last_update = date_now
        intunecd_tenant.last_update_message = "Could not clone repository"
        intunecd_tenant.last_update_status = "error"

        db.session.commit()

        return {
            "status": "error",
            "message": "Could not clone repository",
            "date": date_now,
        }

    cmd = ["IntuneCD-startupdate", "-m", "1", "-p", local_path, "--intunecdmonitor"]

    # Get tenant args
    if intunecd_tenant.update_args:
        OPTIONS = intunecd_tenant.update_args.split(" ")
        cmd += OPTIONS

    cmd = " ".join(cmd)
    update = subprocess.run(cmd, shell=True)

    if update.returncode != 0:
        # remove local_path
        shutil.rmtree(local_path)
        intunecd_tenant.last_update = date_now
        intunecd_tenant.last_update_status = "error"
        intunecd_tenant.last_update_message = "Could not run IntuneCD-startupdate"
        db.session.commit()
        return {
            "status": "error",
            "message": "Could not run IntuneCD-startupdate",
            "date": date_now,
        }

    else:
        # check if tenant id is in the update_feed table
        with open(f"{local_path}/update_summary.json", "r") as f:
            import json

            summary = json.load(f)

        with db.session.no_autoflush:
            for change in summary["changes"]:
                change = summary_changes(
                    tenant=TENANT_ID,
                    name=change["name"],
                    type=change["type"],
                    diffs=str(change["diffs"]),
                )
                db.session.add(change)

            # Add diff count to database
            diff_count = summary["diff_count"]
            count = summary_diff_count(
                tenant=TENANT_ID,
                diff_count=diff_count,
                last_update=date_now,
            )

            db.session.add(count)

            # Update average diff count in database
            records = summary_diff_count.query.filter_by(tenant=TENANT_ID).all()[-30:]
            count = 0
            for record in records:
                count += record.diff_count
            if count == 0:
                average_diffs = 0
            else:
                average_diffs = count / len(records)
            average_diffs = summary_average_diffs(
                tenant=TENANT_ID,
                average_diffs=average_diffs,
                last_update=date_now,
            )

            db.session.add(average_diffs)

            # Update summary in database
            if intunecd_tenant:
                intunecd_tenant.update_feed = summary["feed"]

            intunecd_tenant.last_update = date_now
            intunecd_tenant.last_update_message = "Update successful"
            intunecd_tenant.last_update_status = "success"

            db.session.commit()

            shutil.rmtree(local_path)

        return {
            "status": "success",
            "message": "Update successful",
            "date": date_now,
        }


@shared_task(ignore_result=False)
def run_intunecd_backup(TENANT_ID):
    REPO_URL, AAD_TENANT_NAME = get_connection_info(TENANT_ID)

    os.environ["TENANT_NAME"] = AAD_TENANT_NAME
    os.environ["CLIENT_ID"] = app_config.AZURE_CLIENT_ID
    os.environ["CLIENT_SECRET"] = app_config.AZURE_CLIENT_SECRET

    intunecd_tenant = intunecd_tenants.query.filter_by(name=AAD_TENANT_NAME).first()
    assignment_summary = {}

    date_now = get_now()

    # Clone the repository
    try:
        folder_name = f"tmp{random.randint(100000, 999999)}"
        local_path = f"/intunecd/git/{folder_name}"
        if os.path.exists(local_path):
            shutil.rmtree(local_path)

        Repo.clone_from(REPO_URL, local_path)
    except:
        intunecd_tenant.last_update = date_now
        intunecd_tenant.last_update_message = "Could not clone repository"
        intunecd_tenant.last_update_status = "error"

        db.session.commit()

        return {
            "status": "error",
            "message": "Could not clone repository",
            "date": date_now,
        }

    cmd = ["IntuneCD-startbackup", "-m", "1", "-p", local_path, "--intunecdmonitor"]

    # Get tenant args
    if intunecd_tenant.backup_args:
        OPTIONS = intunecd_tenant.backup_args.split(" ")
        cmd += OPTIONS

    cmd = " ".join(cmd)
    backup = subprocess.run(cmd, shell=True)

    if backup.returncode != 0:
        shutil.rmtree(local_path)
        intunecd_tenant.last_update = date_now
        intunecd_tenant.last_update_message = "Could not run IntuneCD-startbackup"
        intunecd_tenant.last_update_status = "error"
        db.session.commit()
        return {
            "status": "error",
            "message": "Could not run IntuneCD-startbackup",
            "date": date_now,
        }

    else:
        # check if tenant id is in the backup_feed table
        with open(f"{local_path}/backup_summary.json", "r") as f:
            summary = json.load(f)

        assignment_report_path = f"{local_path}/Assignment Report/report.json"
        if os.path.exists(assignment_report_path):
            with open(assignment_report_path, "r") as f:
                assignment_summary = json.load(f)

        with db.session.no_autoflush:
            count = summary_config_count(
                tenant=TENANT_ID,
                config_count=summary["config_count"],
                last_update=date_now,
            )
            db.session.add(count)

            if assignment_summary:
                for assignment in assignment_summary:
                    assignment = summary_assignments(
                        tenant=TENANT_ID,
                        name=assignment["groupName"],
                        type=assignment["groupType"],
                        membership_rule=assignment["membershipRule"],
                        assigned_to=str(assignment["assignedTo"]),
                    )
                    db.session.add(assignment)

            if intunecd_tenant:
                intunecd_tenant.backup_feed = summary["feed"]

            intunecd_tenant.last_update = date_now
            intunecd_tenant.last_update_message = "Backup successful"
            intunecd_tenant.last_update_status = "success"

            db.session.commit()

        # Commit and push changes
        repo = Repo(local_path)
        diff = repo.git.diff()
        if diff:
            repo.git.add("--all")
            repo.index.commit("Changes pushed by IntuneCD")
            origin = repo.remote(name="origin")
            origin.push(refspec="HEAD")

        shutil.rmtree(local_path)

        return {
            "status": "success",
            "message": "Backup successful",
            "date": date_now,
        }
