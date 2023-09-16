import os
from datetime import timedelta
import urllib.parse
import json

AZ_DB_DRIVER = os.getenv("AZDBDRIVER")
if not AZ_DB_DRIVER:
    raise ValueError("Need to define AZDBDRIVER environment variable")
AZ_DB_SERVER = os.getenv("AZDBSERVER")
if not AZ_DB_SERVER:
    raise ValueError("Need to define AZDBSERVER environment variable")
AZ_DB_NAME = os.getenv("AZDBNAME")
if not AZ_DB_NAME:
    raise ValueError("Need to define AZDBNAME environment variable")
AZ_DB_USER = os.getenv("AZDBUSER")
if not AZ_DB_USER:
    raise ValueError("Need to define AZDBUSER environment variable")
AZ_DB_PW = os.getenv("AZDBPW")
if not AZ_DB_PW:
    raise ValueError("Need to define AZDBPW environment variable")

AZURE_SQL_DSN = dsn = (
    "DRIVER="
    + AZ_DB_DRIVER
    + ";SERVER="
    + AZ_DB_SERVER
    + ";PORT=1433;DATABASE="
    + AZ_DB_NAME
    + ";UID="
    + AZ_DB_USER
    + ";PWD="
    + AZ_DB_PW
    + ";connect_timeout=5"
)
params = urllib.parse.quote_plus(AZURE_SQL_DSN)

ADMIN_ROLE = os.getenv("ADMIN_ROLE")
if not ADMIN_ROLE:
    raise ValueError("Need to define ADMIN_ROLE environment variable")

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("Need to define SECRET_KEY environment variable")

AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
if not AZURE_CLIENT_ID:
    raise ValueError("Need to define CLIENT_ID environment variable")

AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
if not AZURE_CLIENT_SECRET:
    raise ValueError("Need to define CLIENT_SECRET environment variable")

AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")
if not AZURE_TENANT_ID:
    raise ValueError("Need to define AZUREAD_ID environment variable")

REDIRECT_PATH = os.getenv("REDIRECT_PATH")
if not REDIRECT_PATH:
    raise ValueError("Need to define REDIRECT_PATH environment variable")

SCOPE = os.getenv("SCOPE")
if SCOPE:
    SCOPE = json.loads(os.environ["SCOPE"])
else:
    raise ValueError("Need to define SCOPE environment variable")

DOCUMENTATION = os.getenv("DOCUMENTATION_ACTIVE")
if DOCUMENTATION:
    AZURE_CONNECTION_STRING = os.getenv("AZURE_CONNECTION_STRING")
    if not AZURE_CONNECTION_STRING:
        raise ValueError("Need to define AZURE_CONNECTION_STRING environment variable")
    AZURE_CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME")
    if not AZURE_CONTAINER_NAME:
        raise ValueError("Need to define AZURE_CONTAINER_NAME environment variable")
    DOCUMENTATION_FILE_NAME = os.getenv("DOCUMENTATION_FILE_NAME")
    if not DOCUMENTATION_FILE_NAME:
        raise ValueError("Need to define DOCUMENTATION_FILE_NAME environment variable")


AZURE_VAULT_URL = os.getenv("AZURE_VAULT_URL")
if not AZURE_VAULT_URL:
    raise ValueError("Need to define AZURE_VAULT_URL environment variable")


SESSION_LIFETIME_HOURS = os.getenv("SESSION_LIFETIME_HOURS")
if SESSION_LIFETIME_HOURS:
    PERMANENT_SESSION_LIFETIME = timedelta(hours=SESSION_LIFETIME_HOURS)
else:
    PERMANENT_SESSION_LIFETIME = timedelta(hours=3)

SQLALCHEMY_DATABASE_URI = "mssql+pyodbc:///?odbc_connect=%s" % params
SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
AUTHORITY = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}"
SQLALCHEMY_TRACK_MODIFICATIONS = False
SESSION_TYPE = "filesystem"
SESSION_FILE_THRESHOLD = 100
SESSION_COOKIE_HTTPONLY = True
REMEMBER_COOKIE_HTTPONLY = True
COMPANY_NAME = os.getenv("COMPANY_NAME")
CELERY_BROKER_URL = "redis://redis:6379/0"
RESULT_BACKEND = "redis://redis:6379/0"
TIMEZONE = "Europe/Stockholm"
BEAT_DB_URI = os.getenv("BEAT_DB_URI")
