import os
import re
import msal
import json
import secrets
import shutil

from app import app, db, docs, app_config, celery, socketio
from flask import (
    render_template,
    session,
    request,
    redirect,
    url_for,
    make_response,
    send_from_directory,
    jsonify,
)
from app.auth import (
    _build_auth_code_flow,
    _load_cache,
    _save_cache,
    _build_msal_app,
)
from app.models import (
    summary_config_count,
    summary_diff_count,
    summary_average_diffs,
    api_key,
    summary_changes,
    summary_assignments,
    intunecd_tenants,
)
from app.decorators import (
    require_appkey,
    login_required,
    admin_required,
    role_required,
)
from .run_intunecd import run_intunecd_backup, run_intunecd_update, get_branches
from datetime import datetime, timedelta, date
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from celery.result import AsyncResult
from flask_apispec import doc, marshal_with
from flask_socketio import emit
from marshmallow import fields, Schema
from .scheduled_tasks import (
    add_scheduled_task,
    remove_scheduled_task,
    get_scheduled_tasks,
    get_scheduled_task_crontab,
)
from app.socket_tasks import emit_message, update_tenant_status_data, get_now
from .tenant_data import tenant_home_data


# region context_processors
@app.context_processor
def inject_now():
    return {"now": datetime.utcnow()}


@app.context_processor
def inject_company_name():
    if app_config.COMPANY_NAME:
        return {"company_name": app_config.COMPANY_NAME}
    else:
        return {"company_name": ""}


@app.context_processor
def tenant_data():
    tenant_data = intunecd_tenants.query.all()
    if tenant_data:
        return {"tenant_data": tenant_data}
    else:
        return {"tenant_data": ""}


@app.context_processor
def inject_version():
    return dict(app_version=app.config["APP_VERSION"])


@app.context_processor
def utility_processor():
    def get_icon_and_color(item, feed_type="update"):
        if "No changes" in item or "Checking if" in item:
            return "check_circle", "text-success"
        elif "***" in item:
            return "info", "text-info"
        elif "Removing" in item:
            return "delete", "text-danger"
        elif "[ERROR]" in item:
            return "cancel", "text-danger"
        elif "[WARNING]" in item:
            return "info", "text-warning"
        else:
            if feed_type == "update":
                return "published_with_changes", "opacity-5"
            else:
                return "cloud_download", "opacity-5"

    return dict(get_icon_and_color=get_icon_and_color)


# endregion


# region Helper Functions
@app.errorhandler(500)
def internal_server_error(e):
    return render_template("pages/error.html", error=e), 500


@app.route("/sw.js")
def sw():
    response = make_response(send_from_directory("static", "sw.js"))
    response.headers["cache-control"] = "no-cache"
    return response


@socketio.on("connect")
def connect():
    if not session.get("user"):
        return False


# endregion


# region Navigation Routes
@app.route("/")
@app.route("/home")
@login_required
@role_required
def home():
    segment = get_segment(request)

    data = tenant_home_data()

    # Check if any API keys are expiring in the next 30 days
    api_keys = api_key.query.all()
    alert_expiring_api_keys = any(
        key.key_expiration < datetime.now() + timedelta(days=30)
        and app_config.ADMIN_ROLE in session["user"]["roles"]
        for key in api_keys
    )
    alert_expired_api_keys = any(
        key.key_expiration < datetime.now()
        and app_config.ADMIN_ROLE in session["user"]["roles"]
        for key in api_keys
    )

    return render_template(
        "pages/home.html",
        user=session["user"],
        version=msal.__version__,
        alert_expiring_api_keys=alert_expiring_api_keys,
        alert_expired_api_keys=alert_expired_api_keys,
        segment=segment,
        data=data,
    )


@app.route("/home/tenant/<int:id>")
@login_required
@role_required
def home_tenant(id):
    """Returns the home page for a specific tenant."""
    data = tenant_home_data(id)
    # Create a new dictionary with the keys used in the JavaScript code
    response_data = {
        "matchCount": data["matchCount"],
        "trackedCount": data["trackedCount"],
        "diffCount": data["diffCount"],
        "labelsConfig": data["labelsConfig"],
        "configCounts": data["config_counts"],
        "labelsAverage": data["labelsAverage"],
        "averageDiffs": data["average_diffs"],
        "labelsDiff": data["labelsDiff"],
        "diffs": data["diffs"],
        "diff_len": data["diff_len"],
        "diff_data_last_update": data["diff_data_last_update"],
        "config_data_last_update": data["config_data_last_update"],
        "selectedTenantName": data["selected_tenant_name"],
        "feeds": {
            "backup_feed": data["backup_feed"],
            "update_feed": data["update_feed"],
        },
    }

    # Return the response as a JSON string
    return json.dumps(response_data), 200, {"Content-Type": "application/json"}


@app.route("/home/tenant/<int:id>/feeds", methods=["POST"])
@login_required
@role_required
def home_tenant_feeds(id):
    """Returns the feeds for a specific tenant."""
    data = request.json["feeds"]

    return render_template("views/home_feeds.html", data=data)


@app.route("/changes")
@login_required
@role_required
def changes():
    """Displays changes for each tenant"""
    segment = get_segment(request)

    # Get last 180 changes from DB for each tenant
    tenants = intunecd_tenants.query.all()
    tenant_changes = []
    for tenant in tenants:
        change_data = summary_changes.query.filter_by(tenant=tenant.id).all()[-180:]
        tenant_data = {
            "name": tenant.display_name,
            "id": tenant.id,
            "data": {"changes": []},
        }
        for change in change_data:
            data = {
                "id": change.id,
                "name": change.name,
                "type": change.type,
                "diffs": change.diffs,
            }

            data["diffs"] = data["diffs"].replace("'", '"').replace("None", "null")
            data["diffs"] = json.loads(data["diffs"])
            tenant_data["data"]["changes"].append(data)
            tenant_data["data"]["changes"].reverse()

        tenant_changes.append(tenant_data)

    return render_template(
        "pages/changes.html",
        user=session["user"],
        tenant_changes=tenant_changes,
        segment=segment,
        version=msal.__version__,
    )


@app.route("/documentation")
@login_required
@admin_required
def documentation():
    """Returns the current documentation from the blob storage."""
    app.jinja_env.cache = {}
    segment = get_segment(request)
    blob_data = ""
    html = ""
    htmldoc = False
    active = False
    baseline_tenant = intunecd_tenants.query.filter_by(baseline="true").first()
    if baseline_tenant.create_documentation == "true":
        if os.path.exists("/documentation/documentation.html"):
            htmldoc = True
            with open("/documentation/documentation.html", "r") as f:
                html = f.read()
    else:

        def az_blob_client(connection_string, container_name, file_name):
            """Create a blob client to get the file from the container."""
            try:
                blob_service_client = BlobServiceClient.from_connection_string(
                    connection_string
                )

                blob_client = blob_service_client.get_blob_client(
                    container=container_name, blob=file_name
                )

                return blob_client

            except Exception as ex:
                print("Error: " + str(ex))

        def get_documentation_blob(connection_string, container_name, file_name):
            """Returns the current documentation from the blob storage."""
            try:
                local_path = "/intunecd/app/templates/include"
                data = ""
                download_file_path = os.path.join(local_path, "documentation.html")
                blob_client = az_blob_client(
                    connection_string, container_name, file_name
                )

                with open(download_file_path, "wb") as _f:
                    blob_data = blob_client.download_blob()
                    data = blob_data.readall()
                    _f.write(data)

                if data == "":
                    return False
                else:
                    return True

            except Exception as ex:
                print("Error: " + str(ex))

        if app_config.DOCUMENTATION:
            blob_data = get_documentation_blob(
                app_config.AZURE_CONNECTION_STRING,
                app_config.AZURE_CONTAINER_NAME,
                app_config.DOCUMENTATION_FILE_NAME,
            )

        if blob_data:
            active = True

    return render_template(
        "pages/documentation.html",
        user=session["user"],
        segment=segment,
        active=active,
        htmldoc=htmldoc,
        html=html,
        version=msal.__version__,
    )


@app.route("/assignments")
@login_required
@role_required
def assignments():
    """Displays the assignemnts for each tenant backed up"""
    segment = get_segment(request)

    # Get all assignments from DB
    tenants = intunecd_tenants.query.all()
    tenant_assignments = []

    for tenant in tenants:
        assignment_data = summary_assignments.query.filter_by(tenant=tenant.id).all()
        tenant_data = {
            "name": tenant.display_name,
            "id": tenant.id,
            "data": {"assignments": []},
        }
        for assignment in assignment_data:
            data = {
                "id": assignment.id,
                "name": assignment.name,
                "type": assignment.type,
                "membership_rule": assignment.membership_rule,
                "assigned_to": assignment.assigned_to,
            }

            data["assigned_to"] = (
                data["assigned_to"].replace("'", '"').replace("\\", "\\\\")
            )
            data["assigned_to"] = json.loads(data["assigned_to"])
            tenant_data["data"]["assignments"].append(data)

        # alphabetically sort the assignments by name
        tenant_data["data"]["assignments"] = sorted(
            tenant_data["data"]["assignments"], key=lambda x: x["name"].lower()
        )
        tenant_assignments.append(tenant_data)

    return render_template(
        "pages/assignments.html",
        user=session["user"],
        tenant_assignments=tenant_assignments,
        segment=segment,
        version=msal.__version__,
    )


@app.route("/schedules")
@login_required
@admin_required
def schedules():
    """Displays added schedules that will be run by Celery"""
    segment = get_segment(request)

    # Get all schedules from DB
    db_schedules = get_scheduled_tasks()
    tenants = intunecd_tenants.query.all()
    schedules = []
    tenants_toggle = []
    for tenant in tenants:
        tenants_toggle.append({"id": tenant.id, "repo": tenant.repo})

    days = [
        "Sunday",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
    ]

    for schedule in db_schedules:
        tenant = ""
        target_tenant = json.loads(schedule.args)
        if target_tenant:
            tenant = intunecd_tenants.query.get(target_tenant[0])
        if tenant:
            tenant = tenant.display_name

        if schedule.task == "app.run_intunecd.run_intunecd_backup":
            task = "Backup"
        else:
            task = "Update"

        # get the crontab schedule
        crontab = get_scheduled_task_crontab(schedule.schedule_id)
        # convert to human readable format
        if crontab.hour == "*" and crontab.minute != "*":
            run_when = f"Run every hour at {crontab.minute} minutes past the hour"
        elif (
            crontab.hour != "*" and crontab.minute != "*" and crontab.day_of_week == "*"
        ):
            run_when = f"Run every day at {crontab.hour}:{crontab.minute}"
        elif (
            crontab.day_of_week != "*" and crontab.minute != "*" and crontab.hour != "*"
        ):
            run_when = f"Run every week on {days[int(crontab.day_of_week)]} at {crontab.hour}:{crontab.minute}"

        if (
            schedule.name != "celery.backend_cleanup"
            and schedule.name != "intunecd.status_check"
        ):
            schedules.append(
                {
                    "name": schedule.name,
                    "task": task,
                    "tenant": tenant,
                    "run_when": run_when,
                    "run_count": schedule.total_run_count,
                }
            )

    return render_template(
        "pages/schedules.html",
        user=session["user"],
        schedules=schedules,
        tenants=tenants,
        tenants_toggle=json.dumps(tenants_toggle),
        segment=segment,
        version=msal.__version__,
    )


@app.route("/settings")
@login_required
@admin_required
def settings():
    """Displays current configured env vars and the option to create an API key"""
    segment = get_segment(request)
    # If new_key is in the session then set new_key to the new key
    if "new_key" in session:
        new_key = session["new_key"]
        session.pop("new_key")
    else:
        new_key = ""

    # Get all keys from the db
    keys = api_key.query.all()
    keys_td = []
    key = False
    # If we have keys, create a dictionary with key id and expiration date from now
    if keys:
        key = True
        now = datetime.now()
        for key in keys:
            k = {"id": key.id, "expiration": (key.key_expiration - now).days}
            keys_td.append(k)

    return render_template(
        "pages/settings.html",
        user=session["user"],
        version=msal.__version__,
        settings=app_config,
        key=key,
        keys_td=keys_td,
        new_key=new_key,
        segment=segment,
    )


@app.route("/tenants")
@login_required
@admin_required
def tenants():
    """Displays all added tenants with ability to edit them"""
    segment = get_segment(request)

    tenant_list = ""
    # Get all tenants from the db
    tenant_list = intunecd_tenants.query.all()
    # check if list has a baseline tenant
    baseline = intunecd_tenants.query.filter_by(baseline="true").first()
    if baseline:
        baseline = True

    return render_template(
        "pages/tenants.html",
        user=session["user"],
        version=msal.__version__,
        tenants=tenant_list,
        baseline=baseline,
        segment=segment,
    )


@app.route("/profile")
@login_required
def profile():
    segment = get_segment(request)
    return render_template("pages/profile.html", user=session["user"], segment=segment)


# endregion


# region settings
@app.route("/settings/key/create", methods=["POST"])
@login_required
@admin_required
def create_key():
    """Creates a new API key in the database"""

    new_key = secrets.token_urlsafe()
    date = datetime.now()
    expiration = date + timedelta(days=90)
    create_key = api_key(key=new_key, key_expiration=expiration)

    db.session.add(create_key)
    db.session.commit()

    session["new_key"] = new_key

    return redirect(url_for("settings"))


@app.route("/settings/key/delete", methods=["POST"])
@login_required
@admin_required
def delete_key():
    """Deletes an API key from the database"""
    for id in request.form:
        delete = api_key.query.get(id)
        db.session.delete(delete)
        db.session.commit()

    return redirect(url_for("settings"))


# endregion


# region intunecd
@app.route("/intunecd/run", methods=["POST"])
@login_required
@admin_required
def run_intunecd():
    tenant_id = request.json["tenant_id"]
    task_type = request.json["task_type"]

    tenant = intunecd_tenants.query.get(tenant_id)

    if task_type == "backup":
        result = run_intunecd_backup.delay(
            tenant_id,
            tenant.new_branch,
        )
    elif task_type == "update":
        result = run_intunecd_update.delay(tenant_id)

    data = {"task_id": result.id}

    # check if task is received but not started
    task_status = celery.AsyncResult(result.id)
    if task_status != "STARTED":
        # task is received, return response
        emit_message(
            f"Waiting for {task_type} to start",
            "pending",
            result.id,
            tenant_id,
            socketio,
        )
        update_tenant_status_data(
            tenant, "pending", f"Waiting for {task_type} to start"
        )

        db.session.commit()

    # return response
    return jsonify(data), 202


@app.route("/intunecd/cancel", methods=["POST"])
@login_required
@admin_required
def cancel_intunecd():
    tenant_id = request.json["tenant_id"]
    tenant = intunecd_tenants.query.get(tenant_id)
    try:
        celery.control.revoke(tenant.last_task_id, terminate=True)
        emit_message(
            "Task cancelled", "cancelled", tenant.last_task_id, tenant_id, socketio
        )
        update_tenant_status_data(tenant, "cancelled", "Task cancelled")

        db.session.commit()

        return jsonify({"status": "success"}), 202
    except Exception as e:
        emit_message(
            "Error cancelling task", "error", tenant.last_task_id, tenant_id, socketio
        )
        update_tenant_status_data(tenant, "error", "Error cancelling task")
        db.session.commit()

        return jsonify({"error": str(e)}), 500


@app.route("/intunecd/purge", methods=["POST"])
@login_required
@admin_required
def purge_intunecd():
    try:
        # purge tasks
        celery.control.purge()

        # revoke all tenant tasks
        tenants = intunecd_tenants.query.all()
        # get all tenant task ids
        task_ids = [tenant.last_task_id for tenant in tenants if tenant.last_task_id]
        celery.control.revoke(task_ids, terminate=True)

        # clear all tenant task ids and statuses
        for tenant in tenants:
            tenant.last_task_id = None
            tenant.last_update_status = "unknown"
            tenant.last_update_status_message = None

        db.session.commit()

        # clean up tmp folders
        if os.path.exists("/intunecd/tmp"):
            shutil.rmtree("/intunecd/tmp")

        return jsonify({"status": "success"}), 202
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# endregion


# region tenants
@app.route("/tenants/add", methods=["POST"])
@login_required
@admin_required
def add_tenant():
    credential = DefaultAzureCredential()
    client = SecretClient(app_config.AZURE_VAULT_URL, credential)

    tenant_display_name = request.form.get("tenant_display_name")
    tenant_name = request.form.get("tenant_name")
    tenant_repo = request.form.get("tenant_repo")
    tenant_pat = request.form.get("tenant_pat")
    tenant_update_args = request.form.get("tenant_update_args")
    tenant_backup_args = request.form.get("tenant_backup_args")
    tenant_baseline = request.form.get("tenant_baseline")
    tenant_new_branch = request.form.get("tenant_new_branch")

    if tenant_repo and tenant_pat:
        # check if url contains https:// or http:// and remove it
        if re.match(r"^https?://", tenant_repo) or re.match(r"^http://", tenant_repo):
            tenant_repo = re.sub(r"^https?://", "", tenant_repo)
            tenant_repo = re.sub(r"^http://", "", tenant_repo)

        tenant_name_input = request.form.get("tenant_name")
        vault_name_output = re.sub(r"[^a-zA-Z0-9]+", "-", tenant_name_input)
        try:
            tenant_value = client.get_secret(vault_name_output)
        except Exception as e:
            if "Code: SecretNotFound" in str(e):
                # Secret not found, create it
                client.set_secret(vault_name_output, tenant_pat)
            else:
                # Other error occurred, re-raise the exception
                raise e
    else:
        vault_name_output = ""

    add_tenant = intunecd_tenants(
        display_name=tenant_display_name,
        name=tenant_name,
        repo=tenant_repo,
        vault_name=vault_name_output,
        update_args=tenant_update_args,
        backup_args=tenant_backup_args,
        baseline=tenant_baseline,
        last_update_status="unknown",
        new_branch=tenant_new_branch,
        update_branch="main",
    )

    db.session.add(add_tenant)
    db.session.commit()

    base_url = "https://login.microsoftonline.com/organizations/v2.0/adminconsent"
    client_ID = app_config.AZURE_CLIENT_ID
    scope = "https://graph.microsoft.com/.default"
    redirect_uri = f"{os.getenv('SERVER_NAME')}/tenants"
    consent_url = (
        f"{base_url}?client_id={client_ID}&scope={scope}&redirect_uri={redirect_uri}"
    )

    return redirect(consent_url)


@app.route("/tenants/delete/<int:id>")
@login_required
@admin_required
def delete_tenant(id):
    credential = DefaultAzureCredential()
    client = SecretClient(app_config.AZURE_VAULT_URL, credential)

    delete_tenant = intunecd_tenants.query.get(id)
    summary_changes.query.filter_by(tenant=id).delete()
    summary_assignments.query.filter_by(tenant=id).delete()
    summary_config_count.query.filter_by(tenant=id).delete()
    summary_diff_count.query.filter_by(tenant=id).delete()
    summary_average_diffs.query.filter_by(tenant=id).delete()

    if delete_tenant.vault_name:
        delte_secret = client.begin_delete_secret(delete_tenant.vault_name)
        delte_secret.wait()
        client.purge_deleted_secret(delete_tenant.vault_name)

    db.session.delete(delete_tenant)
    db.session.commit()

    return redirect(url_for("tenants"))


@app.route("/tenants/edit/<int:id>")
@login_required
@admin_required
def edit_tenant(id):
    edit_tenant = intunecd_tenants.query.get(id)
    edit_id = edit_tenant.id
    tenants_list = []

    tenants = intunecd_tenants.query.all()

    for tenant in tenants:
        tenants_list.append(
            {
                "id": tenant.id,
                "display_name": tenant.display_name,
                "name": tenant.name,
                "repo": tenant.repo,
                "update_args": tenant.update_args,
                "backup_args": tenant.backup_args,
                "baseline": tenant.baseline,
                "last_update_status": tenant.last_update_status,
                "update_branch": tenant.update_branch,
                "new_branch": tenant.new_branch,
                "create_documentation": tenant.create_documentation,
            }
        )

    branches = get_branches(id)
    if "HEAD" in branches:
        branches.remove("HEAD")

    # Create a dictionary with the data to be returned
    data = {"edit_id": edit_id, "tenants": tenants_list, "branches": branches}

    return render_template(
        "views/edit_tenant.html",
        user=session["user"],
        data=data,
        version=msal.__version__,
    )


@app.route("/tenants/edit/<int:id>/save", methods=["POST"])
@login_required
@admin_required
def save_tenant(id):
    tenant = intunecd_tenants.query.get(id)
    tenant.display_name = request.form.get("tenant_display_name")
    tenant.repo = request.form.get("tenant_repo")
    tenant.update_args = request.form.get("tenant_update_args")
    tenant.backup_args = request.form.get("tenant_backup_args")
    tenant_baseline = request.form.get("tenant_baseline")
    tenant.new_branch = request.form.get("tenant_new_branch")
    tenant_pat = request.form.get("tenant_pat")
    tenant.update_branch = request.form.get("tenant_update_branch")
    tenant.create_documentation = request.form.get("tenant_create_documentation")

    credential = DefaultAzureCredential()
    client = SecretClient(app_config.AZURE_VAULT_URL, credential)

    if tenant_baseline == "true":
        # Get the current baseline tenant
        baseline_tenant = intunecd_tenants.query.filter_by(baseline="true").first()
        # If there is a baseline tenant, set it to false
        if baseline_tenant:
            baseline_tenant.baseline = ""

        # Set the current tenant to baseline if it's not already
        if tenant.baseline != "true":
            tenant.baseline = "true"
    else:
        tenant.baseline = ""

    if tenant.repo and tenant_pat and tenant.vault_name:
        # add update PAT to vault
        client.set_secret(tenant.vault_name, tenant_pat)

    db.session.commit()

    return redirect(url_for("tenants"))


# endregion


# region schedules
@app.route("/schedules/add", methods=["POST"])
@login_required
@admin_required
def add_schedule():
    schedule_name = request.form.get("display_name")
    schedule_tenant = request.form.get("schedule_tenant")
    schedule_type = request.form.get("schedule_type")
    schedule_hourly = request.form.get("schedule_hourly")
    schedule_daily = request.form.get("schedule_daily")
    schedule_weekly = request.form.get("schedule_weekly")
    schedule_time = request.form.get("timeOfDay")
    schedule_day = request.form.get("dayOfWeek")
    schedule_time_hourly = request.form.get("timeOfDayHourly")

    time = schedule_time.split(":")

    if schedule_type == "update":
        schedule_task = "app.run_intunecd.run_intunecd_update"
    else:
        schedule_task = "app.run_intunecd.run_intunecd_backup"

    if schedule_hourly == "true":
        # Set crontab to selecetd time in schedule_time and every hour
        schedule_cron = {"minute": f"{schedule_time_hourly}", "hour": "*"}
    elif schedule_daily == "true":
        # Set crontab to selected time and once a day
        schedule_cron = {"minute": f"{time[1]}", "hour": f"{time[0]}"}
    elif schedule_weekly == "true":
        # Set crontab to selected time and once a week
        schedule_cron = {
            "minute": f"{time[1]}",
            "hour": f"{time[0]}",
            "day_of_week": f"{schedule_day}",
        }

    # get tenant by id
    tenant = intunecd_tenants.query.get(schedule_tenant)
    if tenant.new_branch == "true":
        schedule_tenant_args = [schedule_tenant, tenant.new_branch]
    else:
        if schedule_type == "update":
            schedule_tenant_args = [schedule_tenant]
        else:
            schedule_tenant_args = [schedule_tenant, ""]

    add_scheduled_task(
        schedule_cron, schedule_name, schedule_task, schedule_tenant_args
    )

    return redirect(url_for("schedules"))


@app.route("/schedules/delete/<string:name>")
@login_required
@admin_required
def delete_schedule(name):
    remove_scheduled_task(name)

    return redirect(url_for("schedules"))


# endregion


# region API
class TenantSchema(Schema):
    """Tenant schema."""

    id = fields.Integer()
    display_name = fields.String()
    name = fields.String()
    repo = fields.String()
    update_args = fields.String()
    backup_args = fields.String()
    baseline = fields.String()
    last_update_status = fields.String()
    pat = fields.String()
    update_branch = fields.String()


class ChangeSchema(Schema):
    """Change schema."""

    id = fields.Integer()
    name = fields.String()
    type = fields.String()
    diffs = fields.String()
    tenant = fields.Integer()


class AssignmentSchema(Schema):
    """Assignment schema."""

    id = fields.Integer()
    name = fields.String()
    type = fields.String()
    membership_rule = fields.String()
    assigned_to = fields.String()
    tenant = fields.Integer()


class ScheduleSchema(Schema):
    """Schedule schema."""

    id = fields.Integer()
    name = fields.String()
    task = fields.String()
    args = fields.String()
    schedule_id = fields.String()
    last_run_at = fields.DateTime()
    total_run_count = fields.Integer()
    discriminator = fields.String()
    date_changed = fields.DateTime()


def headerDoc():
    params = {
        "X-API-Key": {
            "description": "API Key for the API",
            "in": "header",
            "type": "string",
            "required": "true",
        }
    }

    return params


@app.route("/api/v1/assignments", methods=["GET"])
@require_appkey
@doc(description="Get all assignments", tags=["assignments"], params=headerDoc())
@marshal_with(AssignmentSchema(many=True))
def get_assignments():
    assignments = summary_assignments.query.all()

    data = []
    for assignment in assignments:
        data.append(
            {
                "id": assignment.id,
                "name": assignment.name,
                "type": assignment.type,
                "membership_rule": assignment.membership_rule,
                "assigned_to": assignment.assigned_to,
                "tenant": assignment.tenant,
            }
        )

    response = jsonify(data)
    response.status_code = 200
    return response


@app.route("/api/v1/assignments/<int:id>", methods=["GET"])
@require_appkey
@doc(
    description="Get all assignments for a specific tenant",
    tags=["assignments"],
    params=headerDoc(),
)
@marshal_with(AssignmentSchema(many=True))
def get_assignments_tenant(id):
    assignments = summary_assignments.query.filter_by(tenant=id).all()

    data = []
    for assignment in assignments:
        data.append(
            {
                "id": assignment.id,
                "name": assignment.name,
                "type": assignment.type,
                "membership_rule": assignment.membership_rule,
                "assigned_to": assignment.assigned_to,
                "tenant": assignment.tenant,
            }
        )

    if not data:
        response = jsonify({"error": "not found"})
        response.status_code = 404
        return response
    else:
        response = jsonify(data)
        response.status_code = 200
        return response


@app.route("/api/v1/tenants", methods=["GET"])
@require_appkey
@doc(tags=["tenants"], params=headerDoc(), description="Get all tenants")
@marshal_with(TenantSchema(many=True))
def get_tenants():
    tenants = intunecd_tenants.query.all()

    data = []
    for tenant in tenants:
        data.append(
            {
                "id": tenant.id,
                "display_name": tenant.display_name,
                "name": tenant.name,
                "repo": tenant.repo,
                "update_args": tenant.update_args,
                "backup_args": tenant.backup_args,
                "baseline": tenant.baseline,
                "last_update_status": tenant.last_update_status,
                "update_branch": tenant.update_branch,
            }
        )

    response = jsonify(data)
    response.status_code = 200

    return response


@app.route("/api/v1/tenants/<int:id>", methods=["GET", "PATCH", "DELETE"])
@require_appkey
@doc(
    description="Get and update a specific tenant", tags=["tenants"], params=headerDoc()
)
@marshal_with(TenantSchema)
def get_tenant(id):
    tenant = intunecd_tenants.query.get(id)

    if request.method == "GET":
        data = {
            "id": tenant.id,
            "display_name": tenant.display_name,
            "name": tenant.name,
            "repo": tenant.repo,
            "update_args": tenant.update_args,
            "backup_args": tenant.backup_args,
            "baseline": tenant.baseline,
            "last_update_status": tenant.last_update_status,
            "update_branch": tenant.update_branch,
        }

        if not data:
            response = jsonify({"error": "not found"})
            response.status_code = 404
            return response
        else:
            response = jsonify(data)
            response.status_code = 200
            return response

    if request.method == "PATCH":
        data = request.get_json()
        tenant.display_name = data[0]["display_name"]
        tenant.repo = data[0]["repo"]
        tenant.update_args = data[0]["update_args"]
        tenant.backup_args = data[0]["backup_args"]
        tenant_baseline = data[0]["baseline"]
        tenant_pat = data[0]["pat"]

        if tenant_baseline == "true":
            # Get the current baseline tenant
            baseline_tenant = intunecd_tenants.query.filter_by(baseline="true").first()
            # If there is a baseline tenant, set it to false
            if baseline_tenant:
                baseline_tenant.baseline = ""

            # Set the current tenant to baseline if it's not already
            if tenant.baseline != "true":
                tenant.baseline = "true"
        else:
            tenant.baseline = ""

        if tenant_pat and tenant.vault_name:
            credential = DefaultAzureCredential()
            client = SecretClient(app_config.AZURE_VAULT_URL, credential)
            # add update PAT to vault
            client.set_secret(tenant.vault_name, tenant_pat)

        db.session.commit()

        response = jsonify(data)
        response.status_code = 200
        return response

    if request.method == "DELETE":
        tenant = intunecd_tenants.query.get(id)

        if not tenant:
            response = jsonify({"error": "not found"})
            response.status_code = 404
            return response

        credential = DefaultAzureCredential()
        client = SecretClient(app_config.AZURE_VAULT_URL, credential)

        delete_tenant = intunecd_tenants.query.get(id)
        summary_changes.query.filter_by(tenant=id).delete()
        summary_assignments.query.filter_by(tenant=id).delete()
        summary_config_count.query.filter_by(tenant=id).delete()
        summary_diff_count.query.filter_by(tenant=id).delete()
        summary_average_diffs.query.filter_by(tenant=id).delete()

        if delete_tenant.vault_name:
            delte_secret = client.begin_delete_secret(delete_tenant.vault_name)
            delte_secret.wait()
            client.purge_deleted_secret(delete_tenant.vault_name)

        db.session.delete(delete_tenant)
        db.session.commit()

        response = jsonify({"message": "deleted"})
        response.status_code = 200
        return response


@app.route("/api/v1/changes", methods=["GET"])
@require_appkey
@doc(description="Get all changes", tags=["changes"], params=headerDoc())
@marshal_with(ChangeSchema(many=True))
def get_changes():
    data = []
    changes = summary_changes.query.all()

    for change in changes:
        data.append(
            {
                "id": change.id,
                "name": change.name,
                "type": change.type,
                "diffs": change.diffs,
                "tenant": change.tenant,
            }
        )

    response = jsonify(data)
    response.status_code = 200
    return response


@app.route("/api/v1/changes/<int:id>", methods=["GET"])
@require_appkey
@doc(
    description="Get all changes for a specific tenant",
    tags=["changes"],
    params=headerDoc(),
)
@marshal_with(ChangeSchema(many=True))
def get_changes_tenant(id):
    data = []
    changes = summary_changes.query.filter_by(tenant=id).all()

    for change in changes:
        data.append(
            {
                "id": change.id,
                "name": change.name,
                "type": change.type,
                "diffs": change.diffs,
                "tenant": change.tenant,
            }
        )

    if not data:
        response = jsonify({"error": "not found"})
        response.status_code = 404
        return response
    else:
        response = jsonify(data)
        response.status_code = 200
        return response


@app.route("/api/v1/schedules", methods=["GET"])
@require_appkey
@doc(description="Get all schedules", tags=["schedules"], params=headerDoc())
@marshal_with(ScheduleSchema(many=True))
def get_schedules():
    schedules = get_scheduled_tasks()

    data = []
    for schedule in schedules:
        data.append(
            {
                "id": schedule.id,
                "name": schedule.name,
                "task": schedule.task,
                "args": schedule.args,
                "last_run_at": schedule.last_run_at,
                "total_run_count": schedule.total_run_count,
                "date_changed": schedule.date_changed,
                "discriminator": schedule.discriminator,
                "schedule_id": schedule.schedule_id,
            }
        )

    response = jsonify(data)
    response.status_code = 200
    return response


@app.route("/api/v1/schedules/<string:name>", methods=["GET", "DELETE"])
@require_appkey
@doc(description="Get a specific schedule", tags=["schedules"], params=headerDoc())
@marshal_with(ScheduleSchema)
def get_schedule(name):
    schedules = get_scheduled_tasks()
    schedule = ""

    for s in schedules:
        if s.name.lower() == name.lower():
            schedule = s

    if not schedule:
        response = jsonify({"error": "not found"})
        response.status_code = 404
        return response

    if request.method == "GET":
        data = {
            "id": schedule.id,
            "name": schedule.name,
            "task": schedule.task,
            "args": schedule.args,
            "last_run_at": schedule.last_run_at,
            "total_run_count": schedule.total_run_count,
            "date_changed": schedule.date_changed,
            "discriminator": schedule.discriminator,
            "schedule_id": schedule.schedule_id,
        }

        response = jsonify(data)
        response.status_code = 200
        return response

    if request.method == "DELETE":
        remove_scheduled_task(schedule.name)

        response = jsonify({"message": "deleted"})
        response.status_code = 200
        return response


docs.register(get_assignments)
docs.register(get_assignments_tenant)
docs.register(get_tenants)
docs.register(get_tenant)
docs.register(get_changes)
docs.register(get_changes_tenant)
docs.register(get_schedules)
docs.register(get_schedule)

# endregion


# region Azure AD
@app.route("/login")
def login():
    # Technically we could use empty list [] as scopes to do just sign in,
    # here we choose to also collect end user consent upfront
    session["flow"] = _build_auth_code_flow(scopes=app_config.SCOPE)
    return render_template(
        "pages/login.html",
        auth_url=session["flow"]["auth_uri"],
        version=msal.__version__,
    )


@app.route(
    app_config.REDIRECT_PATH
)  # Its absolute URL must match your app's redirect_uri set in AAD
def authorized():
    try:
        cache = _load_cache()
        result = _build_msal_app(cache=cache).acquire_token_by_auth_code_flow(
            session.get("flow", {}), request.args
        )
        if "error" in result:
            return render_template("pages/auth_error.html", result=result)
        session["user"] = result.get("id_token_claims")
        _save_cache(cache)
    except ValueError:  # Usually caused by CSRF
        pass  # Simply ignore them
    return redirect(url_for("home"))


@app.route("/logout")
def logout():
    session.clear()  # Wipe out user and its token cache from session
    return redirect(  # Also logout from your tenant's web session
        app_config.AUTHORITY
        + "/oauth2/v2.0/logout"
        + "?post_logout_redirect_uri="
        + url_for("login", _external=True)
    )


# endregion


def get_segment(r):
    try:
        segment = r.path.split("/")[-1]
        if segment == "":
            segment = "home"

        return segment

    except:
        return None


app.jinja_env.globals.update(
    _build_auth_code_flow=_build_auth_code_flow
)  # Used in template
