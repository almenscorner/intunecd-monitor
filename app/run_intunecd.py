import os
import shutil
import subprocess
import json
import random
import shutil
import mistune

from app import app_config
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from flask_socketio import SocketIO
from celery import shared_task
from git import Repo, Remote
from app.models import (
    intunecd_tenants,
    summary_changes,
    summary_diff_count,
    summary_average_diffs,
    summary_config_count,
    summary_assignments,
)
from app import db
from app.socket_tasks import emit_message, update_tenant_status_data, get_now

socket = SocketIO(message_queue="redis://redis:6379/0", broadcast=True, namespace="/")


def get_prefix_name(OPTIONS) -> str:
    # Split the string into a list of words
    args = OPTIONS.split(" ")
    # Find the index of the "--prefix" word
    if "--prefix" in args:
        prefix_index = args.index("--prefix")
        # Extract the name of the prefix from the next word in the list
        prefix_name = args[prefix_index + 1].strip('"')

        return prefix_name


def get_branches(TENANT_ID) -> list:
    """Gets the branches from the repository.

    Args:
        repo_url (str): URL of the repository

    Returns:
        list: returns a list of branches
    """
    repo_url, _ = get_connection_info(TENANT_ID)

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
    branches = []
    for branch in remote.refs:
        branches.append(branch.name.split("/")[1])

    shutil.rmtree(local_path)

    return branches


def configure_git(path) -> None:
    """Configures git with the necessary settings."""
    cmd = ["git", "-C", path, "config", "user.email", "inteuncdmonitor@intunecd.local"]
    cmd = " ".join(cmd)
    subprocess.run(cmd, shell=True)
    cmd = ["git", "-C", path, "config", "user.name", "IntuneCD Monitor"]
    cmd = " ".join(cmd)
    subprocess.run(cmd, shell=True)


def get_connection_info(TENANT_ID) -> tuple:
    """Gets the connection info for the tenant from the database.

    Args:
        TENANT_ID (int): ID of the tenant to get info for.

    Returns:
        tuple: returns a tuple containing the repo url and the tenant name
    """
    credential = DefaultAzureCredential()
    client = SecretClient(app_config.AZURE_VAULT_URL, credential)
    tenant = intunecd_tenants.query.get(TENANT_ID)
    baseline = intunecd_tenants.query.filter_by(baseline="true").first()

    if not tenant.repo or tenant.baseline == "true":
        repo_url_base = baseline.repo
        pat = client.get_secret(baseline.vault_name).value
    elif tenant.repo and tenant.name == baseline.name and not tenant.baseline:
        repo_url_base = tenant.repo
        pat = client.get_secret(baseline.vault_name).value
    else:
        repo_url_base = tenant.repo
        pat = client.get_secret(tenant.vault_name).value

    repo_url = f"https://IntuneCDMonitor:{pat}@{repo_url_base}"

    return (repo_url, tenant.name)


def create_documentation(PATH, TENANT) -> None:
    """Creates documentation for the tenant.

    Args:
        PATH (str): path to the repository
        TENANT (object): tenant object
    """
    cmd = [
        "IntuneCD-startdocumentation",
        "-c",
        "-p",
        PATH,
        "-o",
        f"{PATH}/IntuneCD-documentation.md",
        "-t",
        TENANT.name,
    ]
    cmd = " ".join(cmd)

    emit_message("Creating documentation...", "running", "backup", TENANT.id, socket)
    update_tenant_status_data(TENANT, "running", "Creating documentation...")
    db.session.commit()
    document = subprocess.run(cmd, shell=True)

    if document.returncode != 0:
        message = "Could not run documentation"
        emit_message(message, "error", "backup", TENANT.id, socket)
        update_tenant_status_data(TENANT, "error", message)
        db.session.commit()

    else:
        try:
            with open(f"{PATH}/IntuneCD-documentation.md", "r") as f:
                content = f.read()
                html = mistune.html(content)

            with open("/documentation/documentation.html", "w") as f:
                f.write(html)

            message = "Back and documentation complete"
            emit_message(message, "success", "backup", TENANT.id, socket)
            update_tenant_status_data(TENANT, "success", message)
            db.session.commit()
        except:
            message = "Could not create documentation"
            emit_message(message, "error", "backup", TENANT.id, socket)
            update_tenant_status_data(TENANT, "error", message)
            db.session.commit()


@shared_task(time_limit=3600, soft_time_limit=3000)
def run_intunecd_update(TENANT_ID) -> dict:
    """Runs the IntuneCD-startupdate command for the specified tenant.

    Args:
        TENANT_ID (int): ID of the tenant to run the update for.

    Returns:
        dict: returns a dict containing the status, message and date of the update.
    """
    REPO_URL, AAD_TENANT_NAME = get_connection_info(TENANT_ID)

    os.environ["TENANT_NAME"] = AAD_TENANT_NAME
    os.environ["CLIENT_ID"] = app_config.AZURE_CLIENT_ID
    os.environ["CLIENT_SECRET"] = app_config.AZURE_CLIENT_SECRET

    intunecd_tenant = intunecd_tenants.query.filter_by(id=TENANT_ID).first()

    intunecd_tenant.last_task_id = run_intunecd_update.request.id
    update_tenant_status_data(intunecd_tenant, "running", "Update in progress...")

    db.session.commit()

    date_now = get_now()
    emit_message("Update in progress...", "running", "update", TENANT_ID, socket)

    if not all(
        [
            os.getenv("TENANT_NAME"),
            os.getenv("CLIENT_ID"),
            os.getenv("CLIENT_SECRET"),
        ]
    ):
        date_now = get_now()
        message = "Could not get environment variables"
        emit_message(message, "error", "update", TENANT_ID, socket)
        update_tenant_status_data(intunecd_tenant, "error", message)

        db.session.commit()

        return {
            "status": "error",
            "message": message,
            "date": date_now,
        }

    # Clone the repository
    try:
        folder_name = f"tmp{random.randint(100000, 999999)}"
        local_path = f"/intunecd/git/{folder_name}"
        if os.path.exists(local_path):
            shutil.rmtree(local_path)

        Repo.clone_from(REPO_URL, local_path)
        repo = Repo(local_path)

        if intunecd_tenant.update_branch != "main":
            repo.git.checkout(intunecd_tenant.update_branch)

    except:
        date_now = get_now()
        message = "Could not clone repository"
        emit_message(message, "error", "update", TENANT_ID, socket)
        update_tenant_status_data(intunecd_tenant, "error", message)

        db.session.commit()

        return {
            "status": "error",
            "message": message,
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
        date_now = get_now()
        message = "Could not run IntuneCD-startupdate"
        emit_message(message, "error", "update", TENANT_ID, socket)
        # remove local_path
        shutil.rmtree(local_path)
        update_tenant_status_data(intunecd_tenant, "error", message)
        db.session.commit()
        return {
            "status": "error",
            "message": message,
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
            db.session.commit()

            # Update average diff count in database
            records = summary_diff_count.query.filter_by(tenant=TENANT_ID).all()[-30:]
            count = 0
            for record in records:
                count += record.diff_count
            average_count = count / len(records)
            average_diffs = summary_average_diffs(
                tenant=TENANT_ID,
                average_diffs=average_count,
                last_update=date_now,
            )

            db.session.add(average_diffs)

            # Update summary in database
            if intunecd_tenant:
                intunecd_tenant.update_feed = summary["feed"]

            message = "Update successful"
            emit_message(message, "success", "update", TENANT_ID, socket)
            update_tenant_status_data(intunecd_tenant, "success", message)

            db.session.commit()

            shutil.rmtree(local_path)

        date_now = get_now()
        return {
            "status": "success",
            "message": message,
            "date": date_now,
        }


@shared_task(time_limit=7200, soft_time_limit=6600)
def run_intunecd_backup(TENANT_ID, NEW_BRANCH=None) -> dict:
    """Runs the IntuneCD-startbackup command for the specified tenant.

    Args:
        TENANT_ID (int): ID of the tenant to run the backup for.
        NEW_BRANCH (str, optional): if configured, creates a new branch. Defaults to None.

    Returns:
        dict: returns a dict containing the status, message and date of the backup.
    """
    REPO_URL, AAD_TENANT_NAME = get_connection_info(TENANT_ID)

    os.environ["TENANT_NAME"] = AAD_TENANT_NAME
    os.environ["CLIENT_ID"] = app_config.AZURE_CLIENT_ID
    os.environ["CLIENT_SECRET"] = app_config.AZURE_CLIENT_SECRET

    intunecd_tenant = intunecd_tenants.query.filter_by(id=TENANT_ID).first()
    assignment_summary = {}
    prefix_name = ""

    intunecd_tenant.last_task_id = run_intunecd_backup.request.id
    update_tenant_status_data(intunecd_tenant, "running", "Backup in progress...")

    db.session.commit()

    emit_message("Backup in progress...", "running", "backup", TENANT_ID, socket)

    # Clone the repository
    try:
        folder_name = f"tmp{random.randint(100000, 999999)}"
        local_path = f"/intunecd/git/{folder_name}"
        if os.path.exists(local_path):
            shutil.rmtree(local_path)

        Repo.clone_from(REPO_URL, local_path)
        repo = Repo(local_path)
    except Exception:
        date_now = get_now()
        message = "Could not clone repository"
        emit_message(message, "error", "backup", TENANT_ID, socket)
        update_tenant_status_data(intunecd_tenant, "error", message)

        db.session.commit()

        return {
            "status": "error",
            "message": message,
            "date": date_now,
        }

    cmd = ["IntuneCD-startbackup", "-m", "1", "-p", local_path, "--intunecdmonitor"]
    audit = False

    # Get tenant args
    if intunecd_tenant.backup_args:
        OPTIONS = intunecd_tenant.backup_args.split(" ")
        prefix_name = get_prefix_name(intunecd_tenant.backup_args)
        if "--audit" in OPTIONS:
            audit = True
        cmd += OPTIONS

        if prefix_name and prefix_name in Remote(repo, "origin").refs:
            repo.git.checkout(prefix_name)

    cmd = " ".join(cmd)
    backup = subprocess.run(cmd, shell=True)

    if backup.returncode != 0:
        date_now = get_now()
        message = "Could not run IntuneCD-startbackup"
        emit_message(message, "error", "backup", TENANT_ID, socket)
        shutil.rmtree(local_path)
        update_tenant_status_data(intunecd_tenant, "error", message)
        db.session.commit()
        return {
            "status": "error",
            "message": message,
            "date": date_now,
        }

    else:
        if audit:
            configure_git(local_path)
        # check if tenant id is in the backup_feed table
        with open(f"{local_path}/backup_summary.json", "r") as f:
            summary = json.load(f)

        assignment_report_path = f"{local_path}/Assignment Report/report.json"
        if os.path.exists(assignment_report_path):
            with open(assignment_report_path, "r") as f:
                assignment_summary = json.load(f)

        with db.session.no_autoflush:
            date_now = get_now()
            count = summary_config_count(
                tenant=TENANT_ID,
                config_count=summary["config_count"],
                last_update=date_now,
            )
            db.session.add(count)

            if assignment_summary:
                for assignment in assignment_summary:
                    current_assignment = summary_assignments.query.filter_by(
                        tenant=TENANT_ID
                    )
                    if current_assignment:
                        current_assignment.delete()
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

            message = "Backup successful"
            emit_message(message, "success", "backup", TENANT_ID, socket)
            update_tenant_status_data(intunecd_tenant, "success", message)

            db.session.commit()

        # Commit and push changes
        ignore_files = ["backup_summary.json", "IntuneCD-documentation.md"]
        diff = repo.git.diff()
        untracked_files = repo.untracked_files
        for f in ignore_files:
            if f in untracked_files:
                untracked_files.remove(f)
        if diff or untracked_files:
            repo.git.add(
                "--all", ":^backup_summary.json", ":^IntuneCD-documentation.md"
            )
            if NEW_BRANCH:
                date = get_now()
                clean_date = date.replace(" ", "-").replace(":", "-")
                if prefix_name:
                    branch_name = prefix_name
                else:
                    branch_name = f"intunecd-backup-{clean_date}"
                # check if branch exists
                if branch_name in Remote(repo, "origin").refs:
                    repo.git.pull()
                    repo.index.commit("Changes pushed by IntuneCD")
                    repo.git.push()
                else:
                    branch = repo.create_head(branch_name)
                    branch.checkout()
                    repo.index.commit("Changes pushed by IntuneCD")
                    origin = repo.remote(name="origin")
                    origin.push(refspec=f"HEAD:{branch_name}")
            else:
                repo.index.commit("Changes pushed by IntuneCD")
                origin = repo.remote(name="origin")
                origin.push(refspec="HEAD")

            if intunecd_tenant.create_documentation == "true":
                create_documentation(local_path, intunecd_tenant)

        shutil.rmtree(local_path)

        return {
            "status": "success",
            "message": message,
            "date": date_now,
        }


@shared_task()
def status_check():
    tenants = intunecd_tenants.query.all()
    ignore_states = ["success", "error", "unknown"]

    for tenant in tenants:
        if tenant.last_task_id:
            task = run_intunecd_update.AsyncResult(tenant.last_task_id)
            task_type = ""
            if task.name == "app.run_intunecd.run_intunecd_update":
                task_type = "Update"
            elif task.name == "app.run_intunecd.run_intunecd_backup":
                task_type = "Backup"

            if tenant.last_update_status in ignore_states:
                continue
            else:
                if task.state == "STARTED":
                    emit_message(
                        f"{task_type} in progress...",
                        "running",
                        task_type,
                        tenant.id,
                        socket,
                    )
                    update_tenant_status_data(
                        tenant, "running", f"{task_type} is running"
                    )
                    db.session.commit()
                elif task.state == "SUCCESS":
                    emit_message(
                        f"{task_type} completed successfully",
                        "success",
                        task_type,
                        tenant.id,
                        socket,
                    )
                    update_tenant_status_data(
                        tenant, "success", f"{task_type} completed successfully"
                    )
                    db.session.commit()
                elif task.state == "FAILURE":
                    emit_message(
                        f"{task_type} failed", "error", task_type, tenant.id, socket
                    )
                    update_tenant_status_data(tenant, "error", f"{task_type} failed")
                    db.session.commit()
                else:
                    emit_message("None", "unknown", task_type, tenant.id, socket)
