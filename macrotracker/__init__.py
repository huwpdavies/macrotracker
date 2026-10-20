from flask import Flask

from .config import Config
from .extensions import db, migrate


def create_app(config_object=Config):
    # Flask serves public/ at the site root locally; on Vercel the CDN does the same.
    app = Flask(
        __name__,
        static_folder="../public",
        static_url_path="",
    )
    app.config.from_object(config_object)

    db.init_app(app)
    migrate.init_app(app, db)

    from . import models  # noqa: F401  (so migrations can see the models)
    from .seed import seed_command

    app.cli.add_command(seed_command)

    from .blueprints.dashboard import bp as dashboard_bp

    app.register_blueprint(dashboard_bp)

    return app
