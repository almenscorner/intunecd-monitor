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

AZURE_SQL_DSN = dsn = 'DRIVER='+AZ_DB_DRIVER+';SERVER='+AZ_DB_SERVER+';PORT=1433;DATABASE='+AZ_DB_NAME+';UID='+AZ_DB_USER+';PWD='+AZ_DB_PW
params = urllib.parse.quote_plus(AZURE_SQL_DSN)

ADMIN_ROLE = os.getenv("ADMIN_ROLE")
if not ADMIN_ROLE:
    raise ValueError("Need to define ADMIN_ROLE environment variable")

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("Need to define SECRET_KEY environment variable")

CLIENT_ID = os.getenv("CLIENT_ID")
if not CLIENT_ID:
    raise ValueError("Need to define CLIENT_ID environment variable")

CLIENT_SECRET = os.getenv("CLIENT_SECRET")
if not CLIENT_SECRET:
    raise ValueError("Need to define CLIENT_SECRET environment variable")

AZUREAD_ID = os.getenv("AZUREAD_ID")
if not AZUREAD_ID:
    raise ValueError("Need to define AZUREAD_ID environment variable")

DEVOPS_ORG_NAME = os.getenv("DEVOPS_ORG_NAME")
if not DEVOPS_ORG_NAME:
    raise ValueError("Need to define DEVOPS_ORG_NAME environment variable")

DEVOPS_PROJECT_NAME = os.getenv("DEVOPS_PROJECT_NAME")
if not DEVOPS_PROJECT_NAME:
    raise ValueError("Need to define DEVOPS_PROJECT_NAME environment variable")

REDIRECT_PATH = os.getenv("REDIRECT_PATH")
if not REDIRECT_PATH:
    raise ValueError("Need to define REDIRECT_PATH environment variable")

SCOPE = os.getenv("SCOPE")
if SCOPE:
    SCOPE = json.loads(os.environ['SCOPE'])
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

SESSION_LIFETIME_HOURS = os.getenv("SESSION_LIFETIME_HOURS")
if SESSION_LIFETIME_HOURS:
    PERMANENT_SESSION_LIFETIME = timedelta(hours=SESSION_LIFETIME_HOURS)
else:
    PERMANENT_SESSION_LIFETIME = timedelta(hours=3)

SQLALCHEMY_DATABASE_URI = "mssql+pyodbc:///?odbc_connect=%s" % params
AUTHORITY = f"https://login.microsoftonline.com/{AZUREAD_ID}"
SQLALCHEMY_TRACK_MODIFICATIONS = False
SESSION_TYPE = "filesystem"
SESSION_FILE_THRESHOLD = 100
SESSION_COOKIE_HTTPONLY = True
REMEMBER_COOKIE_HTTPONLY = True
COMPANY_NAME = os.getenv("COMPANY_NAME")