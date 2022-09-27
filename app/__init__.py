from flask import Flask
from app import app_config
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_paranoid import Paranoid
from flask_sock import Sock

app = Flask(__name__)
app.config.from_object(app_config)
Session(app)
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
sock = Sock(app)
paranoid = Paranoid(app)
paranoid.redirect_view = '/login'

from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app)

from app import routes