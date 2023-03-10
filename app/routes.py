import os
import msal
import time
import json
import base64
import secrets
from app import app_config
from flask import (
    render_template,
    session,
    request,
    redirect,
    url_for,
    make_response,
    send_from_directory,
)
from app.auth import (
    _build_auth_code_flow,
    _load_cache,
    _save_cache,
    _build_msal_app,
    _get_token_from_cache,
)
from app import app, db, sock
from app.models import (
    summary_config_count,
    summary_match_count,
    summary_diff_count,
    summary_average_diffs,
    api_key,
    backup_feed,
    update_feed,
    summary_changes,
    summary_assignments,
)
from app.decorators import require_appkey, login_required, admin_required, role_required
from app.devops_api import get_pipeline_data, run_pipeline
from app.sock_pipelinestatus import pipelinestatus_html
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient

@app.context_processor
def inject_now():
    return {"now": datetime.utcnow()}


@app.context_processor
def inject_company_name():
    if app_config.COMPANY_NAME:
        return dict(company_name=app_config.COMPANY_NAME)
    else:
        return dict(company_name=None)
    

@app.route("/")
@app.route("/home")
@login_required
@role_required
def home():
    segment = get_segment(request)

    # Diffs
    # Get number of diffs
    config_count_data = summary_config_count.query.all()
    diff_count_data = summary_diff_count.query.all()
    match_count_data = summary_match_count.query.all()

    # Get the last config count from db
    if config_count_data:
        count_data = summary_config_count.query.all()[-1]
        trackedCount = count_data.config_count
    # if count is empty, set count to 0
    else:
        count_data = None
        trackedCount = 0

    # Get the last diff count from db
    if diff_count_data:
        diff_data = summary_diff_count.query.all()[-1]
        diffCount = diff_data.diff_count
    # if count is empty, set count to 0
    else:
        diff_data = None
        diffCount = 0

    # If we have match count data in db, get the last match count from db
    if match_count_data:
        match_data = summary_match_count.query.all()[-1]
        matchCount = match_data.match_count
    # if count is empty, set count to 0
    else:
        match_data = None
        matchCount = 0

    # Feeds
    # Get backup feed from db
    bfeed = backup_feed.query.all()
    if bfeed:
        # Decode feed from base64 and split into list
        for feed in bfeed:
            feed_backup = base64.b64decode(feed.feed).decode("utf-8").splitlines()
    # if feed is empty, set feed to no data
    else:
        feed_backup = ["No data"]

    # Get update feed from db
    ufeed = update_feed.query.all()
    if ufeed:
        # Decode feed from base64 and split into list
        for feed in ufeed:
            feed_update = base64.b64decode(feed.feed).decode("utf-8").splitlines()
            for line in feed_update:
                # Renmove lines only containg '-' from feed_update
                if line == "-" * 90:
                    feed_update.remove(line)
    # if feed is empty, set feed to no data
    else:
        feed_update = ["No data"]

    # Pipelines
    # Get authentication token from cache
    token = _get_token_from_cache(app_config.SCOPE)
    # Get pipeline data from devops api using token and env variables
    pipelines = get_pipeline_data(
        app_config.DEVOPS_ORG_NAME, app_config.DEVOPS_PROJECT_NAME, token
    )

    # If pipeline stats is not completed, set web socket to true
    if [item for item in pipelines if item["status"] != "completed"]:
        sock = True
    else:
        sock = False

    # Trends
    # Get the last 30 config and diff counts from db
    line_data_diff = summary_diff_count.query.all()[-30:]
    line_data_config = summary_config_count.query.all()[-30:]
    line_data_average = summary_average_diffs.query.all()[-30:]

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

    return render_template(
        "pages/home.html",
        user=session["user"],
        version=msal.__version__,
        backup_feed=feed_backup,
        update_feed=feed_update,
        count_data=count_data,
        diff_data=diff_data,
        match_data=match_data,
        matchCount=matchCount,
        diffCount=diffCount,
        trackedCount=trackedCount,
        pipelines=pipelines,
        labelsDiff=labelsDiff,
        labelsConfig=labelsConfig,
        diffs=diffs,
        config_counts=config_counts,
        labelsAverage=labelsAverage,
        average_diffs=average_diffs,
        diff_data_len=len(line_data_diff),
        alert_api_keys=alert_api_keys,
        segment=segment,
        sock=sock,
    )


@app.route("/sw.js")
def sw():
    response = make_response(send_from_directory("static", "sw.js"))
    response.headers["cache-control"] = "no-cache"
    return response


@app.route("/changes")
@login_required
@role_required
def changes():
    segment = get_segment(request)

    # Get last 180 changes from DB
    changes = summary_changes.query.all()[-180:]

    for change in changes:
        change.diffs = change.diffs.replace("'", '"')
        change.diffs = json.loads(change.diffs)

    return render_template(
        "pages/changes.html",
        user=session["user"],
        changes=changes,
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
            download_file_path = os.path.join(local_path, 'documentation.html')
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
        blob_data = get_documentation_blob(app_config.AZURE_CONNECTION_STRING, app_config.AZURE_CONTAINER_NAME, app_config.DOCUMENTATION_FILE_NAME)

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
    assignment_data = summary_assignments.query.all()

    assignments = []

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

        assignments.append(data)

    return render_template(
        "pages/assignments.html",
        user=session["user"],
        assignments=assignments,
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


@app.route("/profile")
@login_required
def profile():
    segment = get_segment(request)
    return render_template("pages/profile.html", user=session["user"], segment=segment)


@sock.route("/pipelinestatus")
def pipelinestatus(ws):
    token = _get_token_from_cache(app_config.SCOPE)
    pipelines = get_pipeline_data(
        app_config.DEVOPS_ORG_NAME, app_config.DEVOPS_PROJECT_NAME, token
    )

    with app.app_context():
        pipelines = get_pipeline_data(
            app_config.DEVOPS_ORG_NAME, app_config.DEVOPS_PROJECT_NAME, token
        )
        while [item for item in pipelines if item["status"] != "completed"]:
            time.sleep(30)
            pipelines = get_pipeline_data(
                app_config.DEVOPS_ORG_NAME, app_config.DEVOPS_PROJECT_NAME, token
            )
            html = pipelinestatus_html(pipelines)
            ws.send(html)


@app.route("/pipelines/run", methods=["POST"])
@login_required
def pipelines_run():
    if request.method == "POST":
        token = _get_token_from_cache(app_config.SCOPE)
        for id in request.form:
            run_pipeline(
                app_config.DEVOPS_ORG_NAME, app_config.DEVOPS_PROJECT_NAME, id, token
            )
        return redirect(url_for("home"))


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


@app.route("/api/overview/summary", methods=["POST"])
@require_appkey
def update_summary():
    data = request.get_json()

    # Config count
    if data["type"] == "config_count":
        numbers = summary_config_count(
            config_count=data["config_count"],
            last_update=str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        db.session.add(numbers)

    # Diff count
    if data["type"] == "diff_count":
        numbers = summary_diff_count(
            diff_count=data["diff_count"],
            last_update=str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        db.session.add(numbers)

    # Match count
    current_config_count = summary_config_count.query.all()
    current_diff_count = summary_diff_count.query.all()

    if (current_config_count) and (current_diff_count):
        # Add match count
        current_config_count = summary_config_count.query.all()[-1].config_count
        current_diff_count = summary_diff_count.query.all()[-1].diff_count

        numbers = summary_match_count(
            match_count=current_config_count - current_diff_count,
            last_update=str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        db.session.add(numbers)

        # Add average diffs
        records = summary_diff_count.query.all()[-30:]
        count = 0
        for record in records:
            count += record.diff_count
        average_count = int(count / len(records))
        average = summary_average_diffs(
            average_diffs=average_count,
            last_update=str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )

        db.session.add(average)

    db.session.commit()

    return data


@app.route("/api/feed/update", methods=["POST"])
@require_appkey
def update_feed_data():
    data = request.get_json()

    if data["type"] == "backup":
        output = backup_feed(feed=data["feed"])
        db.session.add(output)
        current_backup_feed = backup_feed.query.get(1)
        if current_backup_feed:
            current_backup_feed.feed = data["feed"]
            db.session.add(current_backup_feed)

    if data["type"] == "update":
        output = update_feed(feed=data["feed"])
        db.session.add(output)
        current_update_feed = update_feed.query.get(1)
        if current_update_feed:
            current_update_feed.feed = data["feed"]
            db.session.add(current_update_feed)

    db.session.commit()

    return data


@app.route("/api/changes/summary", methods=["POST"])
@require_appkey
def update_changes_summary():
    data = request.get_json()

    for change in data:
        output = summary_changes(
            name=change["name"], type=change["type"], diffs=str(change["diffs"])
        )
        db.session.add(output)

    db.session.commit()

    return json.dumps(data)

@app.route("/api/assignments/summary", methods=["POST"])
@require_appkey
def update_assignments_summary():
    data = request.get_json()
    # Clear table
    summary_assignments.query.delete()

    for assignment in data:
        output = summary_assignments(
            name=assignment["groupName"], 
            type=assignment["groupType"], 
            assigned_to=str(assignment["assignedTo"]),
            membership_rule=assignment["membershipRule"]
        )
        db.session.add(output)

    db.session.commit()

    return json.dumps(data)

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
