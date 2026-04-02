import json
import logging
import os
import random
import shutil
import subprocess

import mistune
from celery import Celery, shared_task
from cryptography.fernet import InvalidToken
from git import Remote, Repo

from app.config import settings
from app.database import SessionLocal
from app.encryption import decrypt_pat
from app.models import (
    SummaryAssignment,
    SummaryAverageDiffs,
    SummaryChange,
    SummaryConfigCount,
    SummaryDiffCount,
    Tenant,
)
from app.socket_tasks import emit_message, get_now, get_now_dt, update_tenant_status_data

# Celery app used for task result inspection inside tasks
_celery = Celery(
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

logger = logging.getLogger(__name__)


def get_prefix_name(options: str) -> str:
    args = options.split(" ")
    if "--prefix" in args:
        idx = args.index("--prefix")
        return args[idx + 1].strip('"')
    return ""


def get_branches(tenant_id: int) -> list:
    repo_url, _ = get_connection_info(tenant_id)
    folder_name = f"tmp{random.randint(100000, 999999)}"
    local_path = f"/intunecd/git/{folder_name}"
    if os.path.exists(local_path):
        shutil.rmtree(local_path)

    try:
        Repo.clone_from(repo_url, local_path)
    except Exception as e:
        print(f"Failed to clone repository: {e}")
        return []

    repo = Repo(local_path)
    remote = Remote(repo, "origin")
    branches = [ref.name.split("/")[1] for ref in remote.refs]
    shutil.rmtree(local_path)
    return branches


def configure_git(path: str) -> None:
    subprocess.run(
        f'git -C {path} config user.email "intunecd-monitor@intunecd.local"',
        shell=True,
    )
    subprocess.run(
        f'git -C {path} config user.name "IntuneCD Monitor"',
        shell=True,
    )


def get_connection_info(tenant_id: int) -> tuple:
    db = SessionLocal()
    try:
        tenant = db.get(Tenant, tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        baseline = db.query(Tenant).filter_by(baseline="true").first()

        try:
            if not tenant.repo or tenant.baseline == "true":
                if not baseline or not baseline.encrypted_pat:
                    raise ValueError("Baseline tenant has no encrypted PAT configured")
                repo_url_base = baseline.repo
                pat = decrypt_pat(baseline.encrypted_pat)
            elif tenant.repo and baseline and tenant.name == baseline.name and not tenant.baseline:
                if not baseline.encrypted_pat:
                    raise ValueError("Baseline tenant has no encrypted PAT configured")
                repo_url_base = tenant.repo
                pat = decrypt_pat(baseline.encrypted_pat)
            else:
                if not tenant.encrypted_pat:
                    raise ValueError(f"Tenant '{tenant.display_name}' has no encrypted PAT configured")
                repo_url_base = tenant.repo
                pat = decrypt_pat(tenant.encrypted_pat)
        except InvalidToken:
            raise ValueError(
                f"Could not decrypt PAT for tenant '{tenant.display_name}'. "
                "The token may be corrupted or the SECRET_KEY may have changed."
            )

        return f"https://IntuneCDMonitor:{pat}@{repo_url_base}", tenant.name
    finally:
        db.close()


def create_documentation(path: str, tenant_id: int) -> None:
    db = SessionLocal()
    try:
        tenant = db.get(Tenant, tenant_id)
        cmd_parts = [
            "IntuneCD-startdocumentation", "-c", "-p", path,
            "-o", f"{path}/IntuneCD-documentation.md",
            "-t", tenant.name,
        ]
        if settings.DOCUMENTATION_MAX_LENGTH:
            cmd_parts += ["-m", str(settings.DOCUMENTATION_MAX_LENGTH)]

        emit_message("Creating documentation...", "running", "backup", tenant_id)
        update_tenant_status_data(tenant, "running", "Creating documentation...")
        db.commit()

        result = subprocess.run(" ".join(cmd_parts), shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error("IntuneCD-startdocumentation failed (exit %s):\nSTDOUT: %s\nSTDERR: %s",
                         result.returncode, result.stdout, result.stderr)
            update_tenant_status_data(tenant, "error", "Could not run documentation")
            emit_message("Could not run documentation", "error", "backup", tenant_id)
        else:
            try:
                with open(f"{path}/IntuneCD-documentation.md", "r") as f:
                    html = mistune.html(f.read())
                tenant.documentation_html = html
                message = "Backup and documentation complete"
                emit_message(message, "success", "backup", tenant_id)
                update_tenant_status_data(tenant, "success", message)
            except Exception:
                logger.exception("Failed to write documentation.html")
                emit_message("Could not create documentation", "error", "backup", tenant_id)
                update_tenant_status_data(tenant, "error", "Could not create documentation")

        db.commit()
    finally:
        db.close()


@shared_task(time_limit=3600, soft_time_limit=3000)
def run_intunecd_update(tenant_id: int) -> dict:
    db = SessionLocal()
    try:
        try:
            repo_url, aad_tenant_name = get_connection_info(tenant_id)
        except ValueError as e:
            logger.error("get_connection_info failed for tenant %s: %s", tenant_id, e)
            tenant = db.query(Tenant).filter_by(id=tenant_id).first()
            message = str(e)
            if tenant:
                update_tenant_status_data(tenant, "error", message)
                db.commit()
            emit_message(message, "error", "update", tenant_id)
            return {"status": "error", "message": message}
        os.environ["TENANT_NAME"] = aad_tenant_name
        os.environ["CLIENT_ID"] = settings.AZURE_CLIENT_ID
        os.environ["CLIENT_SECRET"] = settings.AZURE_CLIENT_SECRET

        tenant = db.query(Tenant).filter_by(id=tenant_id).first()
        tenant.last_task_id = run_intunecd_update.request.id
        update_tenant_status_data(tenant, "running", "Update in progress...")
        db.commit()

        emit_message("Update in progress...", "running", "update", tenant_id)
        date_now = get_now()
        date_now_dt = get_now_dt()

        # Clone repository
        try:
            folder_name = f"tmp{random.randint(100000, 999999)}"
            local_path = f"/intunecd/git/{folder_name}"
            if os.path.exists(local_path):
                shutil.rmtree(local_path)
            Repo.clone_from(repo_url, local_path)
            repo = Repo(local_path)
            if tenant.update_branch and tenant.update_branch != "main":
                repo.git.checkout(tenant.update_branch)
        except Exception:
            message = "Could not clone repository"
            emit_message(message, "error", "update", tenant_id)
            update_tenant_status_data(tenant, "error", message)
            db.commit()
            return {"status": "error", "message": message, "date": date_now}

        cmd = ["IntuneCD-startupdate", "-m", "1", "-p", local_path, "--intunecdmonitor"]
        if tenant.update_args:
            cmd += tenant.update_args.split(" ")
        update = subprocess.run(" ".join(cmd), shell=True)

        if update.returncode != 0:
            message = "Could not run IntuneCD-startupdate"
            emit_message(message, "error", "update", tenant_id)
            shutil.rmtree(local_path)
            update_tenant_status_data(tenant, "error", message)
            db.commit()
            return {"status": "error", "message": message, "date": date_now}

        with open(f"{local_path}/update_summary.json", "r") as f:
            summary = json.load(f)

        for change in summary.get("changes", []):
            db.add(SummaryChange(
                tenant=tenant_id,
                name=change["name"],
                type=change["type"],
                diffs=str(change["diffs"]),
            ))

        diff_count_entry = SummaryDiffCount(
            tenant=tenant_id,
            diff_count=summary["diff_count"],
            last_update=date_now_dt,
        )
        db.add(diff_count_entry)
        db.flush()

        records = db.query(SummaryDiffCount).filter_by(tenant=tenant_id).all()[-30:]
        average_count = sum(r.diff_count for r in records) / len(records) if records else 0
        db.add(SummaryAverageDiffs(tenant=tenant_id, average_diffs=average_count, last_update=date_now_dt))

        tenant.update_feed = summary.get("feed")
        message = "Update successful"
        emit_message(message, "success", "update", tenant_id)
        update_tenant_status_data(tenant, "success", message)
        db.commit()

        shutil.rmtree(local_path)
        return {"status": "success", "message": message, "date": date_now}
    finally:
        db.close()


@shared_task(time_limit=7200, soft_time_limit=6600)
def run_intunecd_backup(tenant_id: int, new_branch=None) -> dict:
    db = SessionLocal()
    try:
        try:
            repo_url, aad_tenant_name = get_connection_info(tenant_id)
        except ValueError as e:
            logger.error("get_connection_info failed for tenant %s: %s", tenant_id, e)
            tenant = db.query(Tenant).filter_by(id=tenant_id).first()
            message = str(e)
            if tenant:
                update_tenant_status_data(tenant, "error", message)
                db.commit()
            emit_message(message, "error", "backup", tenant_id)
            return {"status": "error", "message": message}
        os.environ["TENANT_NAME"] = aad_tenant_name
        os.environ["CLIENT_ID"] = settings.AZURE_CLIENT_ID
        os.environ["CLIENT_SECRET"] = settings.AZURE_CLIENT_SECRET

        tenant = db.query(Tenant).filter_by(id=tenant_id).first()
        prefix_name = ""

        tenant.last_task_id = run_intunecd_backup.request.id
        update_tenant_status_data(tenant, "running", "Backup in progress...")
        db.commit()

        emit_message("Backup in progress...", "running", "backup", tenant_id)

        try:
            folder_name = f"tmp{random.randint(100000, 999999)}"
            local_path = f"/intunecd/git/{folder_name}"
            if os.path.exists(local_path):
                shutil.rmtree(local_path)
            Repo.clone_from(repo_url, local_path)
            repo = Repo(local_path)
        except Exception:
            date_now = get_now()
            message = "Could not clone repository"
            emit_message(message, "error", "backup", tenant_id)
            update_tenant_status_data(tenant, "error", message)
            db.commit()
            return {"status": "error", "message": message, "date": date_now}

        cmd = ["IntuneCD-startbackup", "-m", "1", "-p", local_path, "--intunecdmonitor"]
        audit = False

        if tenant.backup_args:
            options = tenant.backup_args.split(" ")
            prefix_name = get_prefix_name(tenant.backup_args)
            audit = "--audit" in options
            cmd += options
            if prefix_name and prefix_name in Remote(repo, "origin").refs:
                repo.git.checkout(prefix_name)

        backup = subprocess.run(" ".join(cmd), shell=True)

        if backup.returncode != 0:
            date_now = get_now()
            message = "Could not run IntuneCD-startbackup"
            emit_message(message, "error", "backup", tenant_id)
            shutil.rmtree(local_path)
            update_tenant_status_data(tenant, "error", message)
            db.commit()
            return {"status": "error", "message": message, "date": date_now}

        if audit:
            configure_git(local_path)

        with open(f"{local_path}/backup_summary.json", "r") as f:
            summary = json.load(f)

        assignment_report_path = f"{local_path}/Assignment Report/report.json"
        assignment_summary = []
        if os.path.exists(assignment_report_path):
            with open(assignment_report_path, "r") as f:
                assignment_summary = json.load(f)

        date_now = get_now()
        date_now_dt = get_now_dt()
        db.add(SummaryConfigCount(
            tenant=tenant_id,
            config_count=summary["config_count"],
            last_update=date_now_dt,
        ))

        if assignment_summary:
            db.query(SummaryAssignment).filter_by(tenant=tenant_id).delete()
            for assignment in assignment_summary:
                db.add(SummaryAssignment(
                    tenant=tenant_id,
                    name=assignment["groupName"],
                    type=assignment["groupType"],
                    membership_rule=assignment["membershipRule"],
                    assigned_to=str(assignment["assignedTo"]),
                ))

        tenant.backup_feed = summary.get("feed")
        message = "Backup successful"
        emit_message(message, "success", "backup", tenant_id)
        update_tenant_status_data(tenant, "success", message)
        db.commit()

        # Git commit and push
        ignore_files = ["backup_summary.json", "IntuneCD-documentation.md"]
        diff = repo.git.diff()
        untracked = [f for f in repo.untracked_files if f not in ignore_files]
        if diff or untracked:
            repo.git.add("--all", ":^backup_summary.json", ":^IntuneCD-documentation.md")
            if new_branch:
                clean_date = date_now.replace(" ", "-").replace(":", "-")
                branch_name = prefix_name or f"intunecd-backup-{clean_date}"
                if branch_name in Remote(repo, "origin").refs:
                    repo.git.pull()
                    repo.index.commit("Changes pushed by IntuneCD")
                    repo.git.push()
                else:
                    branch = repo.create_head(branch_name)
                    branch.checkout()
                    repo.index.commit("Changes pushed by IntuneCD")
                    repo.remote("origin").push(refspec=f"HEAD:{branch_name}")
            else:
                repo.index.commit("Changes pushed by IntuneCD")
                repo.remote("origin").push(refspec="HEAD")

        if tenant.create_documentation == "true":
            create_documentation(local_path, tenant_id)

        shutil.rmtree(local_path)
        return {"status": "success", "message": message, "date": date_now}
    finally:
        db.close()


@shared_task()
def status_check():
    db = SessionLocal()
    try:
        tenants = db.query(Tenant).all()
        ignore_states = ["success", "error", "unknown"]

        for tenant in tenants:
            if not tenant.last_task_id:
                continue
            if tenant.last_update_status in ignore_states:
                continue

            task = run_intunecd_update.AsyncResult(tenant.last_task_id)
            task_type = ""
            if task.name == "app.run_intunecd.run_intunecd_update":
                task_type = "Update"
            elif task.name == "app.run_intunecd.run_intunecd_backup":
                task_type = "Backup"

            if task.state == "STARTED":
                emit_message(f"{task_type} in progress...", "running", task_type, tenant.id)
                update_tenant_status_data(tenant, "running", f"{task_type} is running")
            elif task.state == "SUCCESS":
                emit_message(f"{task_type} completed successfully", "success", task_type, tenant.id)
                update_tenant_status_data(tenant, "success", f"{task_type} completed successfully")
            elif task.state == "FAILURE":
                emit_message(f"{task_type} failed", "error", task_type, tenant.id)
                update_tenant_status_data(tenant, "error", f"{task_type} failed")
            else:
                emit_message("Unknown state", "unknown", task_type, tenant.id)

            db.commit()
    finally:
        db.close()
