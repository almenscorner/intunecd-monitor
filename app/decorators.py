import datetime
from functools import wraps
from flask import jsonify, request, abort, session, redirect, url_for, render_template
from app import app_config
from app.models import api_key
from app.auth import _get_token_from_cache


def require_appkey(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        key = api_key.query.all()
        headers = request.headers
        auth = headers.get("X-Api-Key")
        now = datetime.datetime.now()
        valid = False
        for k in key:
            if auth and k.check_key_correction(attempted_key=auth) is True and k.key_expiration > now:
                valid = True
                return f(*args, **kwargs)

        if valid == False:
            return jsonify({"error": "Authentication Failed", "error_description": "Invalid API Key."}), 401

    return wrap


def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login"))

        token = _get_token_from_cache(app_config.SCOPE)
        if not token:
            return redirect(url_for("login"))
        else:
            return f(*args, **kwargs)

    return wrap


def admin_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if session.get('user'):
            if 'roles' not in session['user']:
                result = {"error": "Authentication Failed", "error_description": "User does not have a role assigned."}
                return render_template("pages/auth_error.html", result=result, application_root_uri="")
            if app_config.ADMIN_ROLE not in session['user']['roles']:
                result = {"error": "No permission", "error_description": "Admin role are required to access this page."}
                return render_template("pages/auth_error.html", result=result, application_root_uri="")
            else:
                return f(*args, **kwargs)

    return wrap


def role_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if session.get('user'):
            if 'roles' not in session['user']:
                result = {"error": "Authentication Failed", "error_description": "User does not have a role assigned."}
                return render_template("pages/auth_error.html", result=result, application_root_uri="")
            else:
                return f(*args, **kwargs)

    return wrap
