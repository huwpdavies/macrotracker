from flask import Flask

from .config import Config


def create_app(config_object=Config):
    # Flask serves public/ at the site root locally; on Vercel the CDN does the same.
    app = Flask(
        __name__,
        static_folder="../public",
        static_url_path="",
    )
    app.config.from_object(config_object)

    from .blueprints.dashboard import bp as dashboard_bp

    app.register_blueprint(dashboard_bp)

    return app
