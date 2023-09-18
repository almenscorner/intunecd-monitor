import os
import re
import msal
import json
import base64
import secrets
import pytz

from app import app, db, docs, app_config
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
from .run_intunecd import run_intunecd_backup, run_intunecd_update
from datetime import datetime, timedelta, date
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from celery.result import AsyncResult
from flask_apispec import doc, marshal_with
from marshmallow import fields, Schema
from .scheduled_tasks import (
    add_scheduled_task,
    remove_scheduled_task,
    get_scheduled_tasks,
    get_scheduled_task_crontab,
)


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


# endregion


# region Helper Functions
@app.route("/sw.js")
def sw():
    response = make_response(send_from_directory("static", "sw.js"))
    response.headers["cache-control"] = "no-cache"
    return response


# endregion


# region Navigation Routes
@app.route("/")
@app.route("/home")
@login_required
@role_required
def home():
    segment = get_segment(request)

    baseline_tenant = intunecd_tenants.query.filter_by(baseline="true").first()

    if baseline_tenant:
        baseline_id = baseline_tenant.id
    else:
        baseline_id = None

    if session.get("tenant_id"):
        id = session["tenant_id"]
        session.pop("tenant_id")
    else:
        # get the id where baseline is true
        if baseline_tenant:
            id = baseline_tenant.id
        else:
            id = None

    # Diffs
    # Get number of diffs
    config_count_data = summary_config_count.query.filter_by(tenant=baseline_id).all()
    diff_count_data = summary_diff_count.query.filter_by(tenant=id).all()

    # Get the last config count from db
    if config_count_data:
        count_data = summary_config_count.query.filter_by(tenant=baseline_id).all()[-1]
        trackedCount = count_data.config_count
    # if count is empty, set count to 0
    else:
        count_data = None
        trackedCount = 0

    # Get the last diff count from db
    if diff_count_data:
        diff_data = summary_diff_count.query.filter_by(tenant=id).all()[-1]
        diffCount = diff_data.diff_count
    # if count is empty, set count to 0
    else:
        diff_data = None
        diffCount = 0

    # Get the last match count from db
    current_config_count = summary_config_count.query.filter_by(tenant=baseline_id).all()
    current_diff_count = summary_diff_count.query.filter_by(tenant=id).all()
    if current_config_count and current_diff_count:
        matchCount = current_config_count[-1].config_count - current_diff_count[-1].diff_count
    else:
        matchCount = 0

    # Feeds
    # Get backup feed from db
    if id:
        bfeed = intunecd_tenants.query.filter_by(id=id).first().backup_feed
    else:
        bfeed = None
    if bfeed:
        # Decode feed from base64 and split into list
        feed_backup = base64.b64decode(bfeed).decode("utf-8").splitlines()
    # if feed is empty, set feed to no data
    else:
        feed_backup = ["No data"]

    # Get update feed from db
    if id:
        ufeed = intunecd_tenants.query.filter_by(id=id).first().update_feed
    else:
        ufeed = None
    if ufeed:
        # Decode feed from base64 and split into list
        feed_update = base64.b64decode(ufeed).decode("utf-8").splitlines()
        for line in feed_update:
            # Renmove lines only containg '-' from feed_update
            if line == "-" * 90:
                feed_update.remove(line)
    # if feed is empty, set feed to no data
    else:
        feed_update = ["No data"]

    # Trends
    # Get the last 30 config and diff counts from db
    line_data_diff = summary_diff_count.query.filter_by(tenant=id).all()[-30:]
    line_data_config = summary_config_count.query.filter_by(tenant=baseline_id).all()[-30:]
    line_data_average = summary_average_diffs.query.filter_by(tenant=id).all()[-30:]

    # If we have diffs in the db, create a list with last upate date and diff count
    if line_data_diff:
        chart_data_diff = []
        for item in line_data_diff:
            chart_data_diff.append((item.last_update, item.diff_count))

        labelsDiff = [row[0] for row in chart_data_diff]
        diffs = [row[1] for row in chart_data_diff]

    else:
        labelsDiff = "null"
        diffs = 0

    # If we have diffs in the db, create a list with last upate date and diff count
    if line_data_config:
        chart_data_config = []
        for item in line_data_config:
            chart_data_config.append((item.last_update, item.config_count))

        labelsConfig = [row[0] for row in chart_data_config]
        config_counts = [row[1] for row in chart_data_config]

    else:
        labelsConfig = "null"
        config_counts = 0

    if line_data_average:
        chart_data_average = []
        for item in line_data_average:
            chart_data_average.append((item.last_update, item.average_diffs))

        labelsAverage = [row[0] for row in chart_data_average]
        average_diffs = [row[1] for row in chart_data_average]

    else:
        labelsAverage = "null"
        average_diffs = 0

    # Get all API keys from db
    api_keys = api_key.query.all()
    alert_api_keys = False
    # Check if there are any API keys expiring in the next 30 days
    for key in api_keys:
        # Get the expiration date of the key
        expiration = key.key_expiration
        # If the expiration date is within 30 days, set the key to expire
        if expiration < datetime.now() + timedelta(days=30) and app_config.ADMIN_ROLE in session["user"]["roles"]:
            alert_api_keys = True

    tenants = intunecd_tenants.query.all()
    if id:
        selected_tenant_name = intunecd_tenants.query.filter_by(id=id).first().display_name
    else:
        selected_tenant_name = "Tenants"

    return render_template(
        "pages/home.html",
        user=session["user"],
        version=msal.__version__,
        backup_feed=feed_backup,
        update_feed=feed_update,
        count_data=count_data,
        diff_data=diff_data,
        matchCount=matchCount,
        diffCount=diffCount,
        trackedCount=trackedCount,
        labelsDiff=labelsDiff,
        labelsConfig=labelsConfig,
        diffs=diffs,
        config_counts=config_counts,
        labelsAverage=labelsAverage,
        average_diffs=average_diffs,
        diff_data_len=len(line_data_diff),
        alert_api_keys=alert_api_keys,
        segment=segment,
        tenants=tenants,
        selected_tenant=id,
        selected_tenant_name=selected_tenant_name,
    )


@app.route("/home/tenant/<int:id>")
@login_required
@role_required
def home_tenant(id):
    """Returns the home page for a specific tenant."""

    session["tenant_id"] = id

    return redirect(url_for("home"))


@app.route("/changes")
@login_required
@role_required
def changes():
    segment = get_segment(request)

    # Get last 180 changes from DB for each tenant
    tenants = intunecd_tenants.query.all()
    tenant_changes = []
    for tenant in tenants:
        change_data = summary_changes.query.filter_by(tenant=tenant.id).all()[-180:]
        tenant_data = {"name": tenant.display_name, "data": {"changes": []}}
        for change in change_data:
            data = {
                "id": change.id,
                "name": change.name,
                "type": change.type,
                "diffs": change.diffs,
            }

            data["diffs"] = data["diffs"].replace("'", '"')
            data["diffs"] = json.loads(data["diffs"])

            tenant_data["data"]["changes"].append(data)

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

    def az_blob_client(connection_string, container_name, file_name):
        """Create a blob client to get the file from the container."""
        try:
            blob_service_client = BlobServiceClient.from_connection_string(connection_string)

            blob_client = blob_service_client.get_blob_client(container=container_name, blob=file_name)

            return blob_client

        except Exception as ex:
            print("Error: " + str(ex))

    def get_documentation_blob(connection_string, container_name, file_name):
        """Returns the current documentation from the blob storage."""
        try:
            local_path = "/intunecd/app/templates/include"
            data = ""
            download_file_path = os.path.join(local_path, "documentation.html")
            blob_client = az_blob_client(connection_string, container_name, file_name)

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

    active = False
    if blob_data:
        active = True

    return render_template(
        "pages/documentation.html",
        user=session["user"],
        segment=segment,
        active=active,
        version=msal.__version__,
    )


@app.route("/assignments")
@login_required
@role_required
def assignments():
    segment = get_segment(request)

    # Get all assignments from DB
    tenants = intunecd_tenants.query.all()
    tenant_assignments = []

    for tenant in tenants:
        assignment_data = summary_assignments.query.filter_by(tenant=tenant.id).all()
        tenant_data = {"name": tenant.display_name, "data": {"assignments": []}}
        for assignment in assignment_data:
            data = {
                "id": assignment.id,
                "name": assignment.name,
                "type": assignment.type,
                "membership_rule": assignment.membership_rule,
                "assigned_to": assignment.assigned_to,
            }

            data["assigned_to"] = data["assigned_to"].replace("'", '"').replace("\\", "\\\\")
            data["assigned_to"] = json.loads(data["assigned_to"])
            tenant_data["data"]["assignments"].append(data)

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
    segment = get_segment(request)

    # Get all schedules from DB
    db_schedules = get_scheduled_tasks()
    tenants = intunecd_tenants.query.all()
    schedules = []
    tenants_toggle = []
    for tenant in tenants:
        tenants_toggle.append({"id": tenant.id, "repo": tenant.repo})

    days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

    for schedule in db_schedules:
        tenant = ""
        target_tenant = json.loads(schedule.args)
        if target_tenant:
            tenant = intunecd_tenants.query.get(target_tenant[0]).display_name

        if schedule.task == "app.run_intunecd.run_intunecd_backup":
            task = "Backup"
        else:
            task = "Update"

        # get the crontab schedule
        crontab = get_scheduled_task_crontab(schedule.schedule_id)
        # convert to human readable format
        if crontab.hour == "*" and crontab.minute != "*":
            run_when = f"Run every hour at {crontab.minute} minutes past the hour"
        elif crontab.hour != "*" and crontab.minute != "*" and crontab.day_of_week == "*":
            run_when = f"Run every day at {crontab.hour}:{crontab.minute}"
        elif crontab.day_of_week != "*" and crontab.minute != "*" and crontab.hour != "*":
            run_when = f"Run every week on {days[int(crontab.day_of_week)]} at {crontab.hour}:{crontab.minute}"

        if schedule.name != "celery.backend_cleanup":
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
    for id in request.form:
        delete = api_key.query.get(id)
        db.session.delete(delete)
        db.session.commit()

    return redirect(url_for("settings"))


# endregion


# region intunecd
@app.route("/intunecd/backup", methods=["POST"])
@login_required
@admin_required
def backup_intunecd():
    tenant_id = request.json["tenant_id"]
    tenant = intunecd_tenants.query.get(tenant_id)

    result = run_intunecd_backup.delay(
        tenant_id,
        tenant.new_branch,
    )

    tenant.last_task_id = result.id
    tenant.last_update = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    db.session.commit()

    data = {"task_id": result.id}

    # return response
    return jsonify(data), 202


@app.route("/intunecd/update", methods=["POST"])
@login_required
@admin_required
def update_intunecd():
    tenant_id = request.json["tenant_id"]
    tenant = intunecd_tenants.query.get(tenant_id)

    result = run_intunecd_update.delay(tenant_id)

    tenant.last_task_id = result.id
    tenant.last_update = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    db.session.commit()

    data = {"task_id": result.id}

    # return response
    return jsonify(data), 202


@app.get("/intunecd/backup/status/<task_id>")
@login_required
@admin_required
def backup_intunecd_status(task_id):
    task_result = AsyncResult(task_id)
    if task_result.status == "PENDING":
        message = "Backup is pending..."
        status = "pending"

    if task_result.status == "STARTED":
        message = "Backup is in progress..."
        status = "started"

    if task_result.status == "SUCCESS":
        if task_result.result.get("status") == "error":
            message = task_result.result.get("message")
            status = "error"
        else:
            message = "Backup is complete."
            status = "success"

    if task_result.status == "FAILURE":
        message = "Backup failed."
        status = "error"

    if task_result.result.get("status") == "error":
        message = task_result.result.get("message")
        status = "error"

    tenant = intunecd_tenants.query.filter_by(last_task_id=task_id).first()
    tenant_id = tenant.id
    tenant.last_update_status = task_result.result.get("status", "unknown")
    db.session.commit()

    result = {
        "task_id": task_id,
        "task_status": status,
        "task_message": message,
        "tenant_id": tenant_id,
    }

    return jsonify(result), 200


@app.get("/intunecd/update/status/<task_id>")
@login_required
@admin_required
def update_intunecd_status(task_id):
    task_result = AsyncResult(task_id)
    if task_result.status == "PENDING":
        message = "Update is pending..."
        status = "pending"

    if task_result.status == "STARTED":
        message = "Update is in progress..."
        status = "started"

    if task_result.status == "SUCCESS":
        if task_result.result.get("status") == "error":
            message = task_result.result.get("message")
            status = "error"
        else:
            message = "Update is complete."
            status = "success"

    if task_result.status == "FAILURE":
        message = "Update failed."
        status = "error"

    if task_result.result.get("status") == "error":
        message = task_result.result.get("message")
        status = "error"

    tenant = intunecd_tenants.query.filter_by(last_task_id=task_id).first()
    tenant_id = tenant.id
    tenant.last_update_status = task_result.result.get("status", "unknown")
    tenant.last_update_message = task_result.result.get("message", "unknown")
    db.session.commit()

    result = {
        "task_id": task_id,
        "task_status": status,
        "task_message": message,
        "tenant_id": tenant_id,
    }

    return jsonify(result), 200


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
    )

    db.session.add(add_tenant)
    db.session.commit()

    base_url = "https://login.microsoftonline.com/organizations/v2.0/adminconsent"
    client_ID = app_config.AZURE_CLIENT_ID
    scope = "https://graph.microsoft.com/.default"
    redirect_uri = f"{os.getenv('SERVER_NAME')}/tenants"
    consent_url = f"{base_url}?client_id={client_ID}&scope={scope}&redirect_uri={redirect_uri}"

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
    tenant = intunecd_tenants.query.get(id)
    edit_id = tenant.id

    tenants = intunecd_tenants.query.all()

    return render_template("pages/tenants.html", edit_id=edit_id, tenants=tenants)


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
        schedule_cron = {"minute": f"{time[1]}", "hour": f"{time[0]}", "day_of_week": f"{schedule_day}"}

    # get tenant by id
    tenant = intunecd_tenants.query.get(schedule_tenant)
    if tenant.new_branch == "true":
        schedule_tenant_args = [schedule_tenant, tenant.new_branch]
    else:
        schedule_tenant_args = [schedule_tenant, ""]

    add_scheduled_task(schedule_cron, schedule_name, schedule_task, schedule_tenant_args)

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
    params = {"X-API-Key": {"description": "API Key for the API", "in": "header", "type": "string", "required": "true"}}

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
@doc(description="Get all assignments for a specific tenant", tags=["assignments"], params=headerDoc())
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
            }
        )

    response = jsonify(data)
    response.status_code = 200

    return response


@app.route("/api/v1/tenants/<int:id>", methods=["GET", "POST", "DELETE"])
@require_appkey
@doc(description="Get and update a specific tenant", tags=["tenants"], params=headerDoc())
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
        }

        if not data:
            response = jsonify({"error": "not found"})
            response.status_code = 404
            return response
        else:
            response = jsonify(data)
            response.status_code = 200
            return response

    if request.method == "POST":
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
@doc(description="Get all changes for a specific tenant", tags=["changes"], params=headerDoc())
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


@app.route(app_config.REDIRECT_PATH)  # Its absolute URL must match your app's redirect_uri set in AAD
def authorized():
    try:
        cache = _load_cache()
        result = _build_msal_app(cache=cache).acquire_token_by_auth_code_flow(session.get("flow", {}), request.args)
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
        app_config.AUTHORITY + "/oauth2/v2.0/logout" + "?post_logout_redirect_uri=" + url_for("login", _external=True)
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


app.jinja_env.globals.update(_build_auth_code_flow=_build_auth_code_flow)  # Used in template
