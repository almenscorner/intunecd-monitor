from flask import Flask
from app import app_config
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_paranoid import Paranoid
from flask_migrate import Migrate
from flask_apispec import FlaskApiSpec
from flask_socketio import SocketIO
from werkzeug.middleware.proxy_fix import ProxyFix
from celery import Celery, Task

app = Flask(__name__)
app.config.from_object(app_config)
app.config.from_mapping(
    CELERY=dict(
        broker_url="redis://redis:6379/0",
        result_backend="redis://redis:6379/0",
        task_ignore_result=True,
        task_track_started=True,
    ),
)
app.config["APP_VERSION"] = "2.0.3a2"
app.config["APISPEC_SWAGGER_UI_URL"] = "/apidocs"
app.config["APISPEC_TITLE"] = "IntuneCD Monitor API Docs"

with app.app_context():
    Session(app)
    db = SQLAlchemy(app)
    migrate = Migrate(app, db)
    bcrypt = Bcrypt(app)
    paranoid = Paranoid(app)
    paranoid.redirect_view = "/login"
    app.wsgi_app = ProxyFix(app.wsgi_app)
    docs = FlaskApiSpec(app)
    socketio = SocketIO(app, message_queue="redis://redis:6379/0", broadcast=True, namespace="/")

    def celery_init_app(app: Flask) -> Celery:
        class FlaskTask(Task):
            def __call__(self, *args: object, **kwargs: object) -> object:
                with app.app_context():
                    return self.run(*args, **kwargs)

        celery_app = Celery(app.name, task_cls=FlaskTask)
        celery_app.config_from_object(app.config["CELERY"])
        celery_app.set_default()
        app.extensions["celery-worker"] = celery_app

        return celery_app

    celery = celery_init_app(app)

    celery.conf.update({"beat_dburi": app_config.BEAT_DB_URI})
    celery.conf.update(result_extended=True)

    from app import routes
