from decimal import ROUND_HALF_UP, Decimal

from flask import Flask

from .config import Config
from .extensions import csrf, db, migrate


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
    csrf.init_app(app)

    from . import models  # noqa: F401  (so migrations can see the models)
    from .seed import seed_command

    app.cli.add_command(seed_command)

    from . import errors

    errors.register(app)

    from .blueprints.dashboard import bp as dashboard_bp
    from .blueprints.foods import bp as foods_bp
    from .blueprints.goals import bp as goals_bp
    from .blueprints.log import bp as log_bp
    from .blueprints.tags import bp as tags_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(foods_bp)
    app.register_blueprint(tags_bp)
    app.register_blueprint(goals_bp)
    app.register_blueprint(log_bp)

    @app.template_filter("num")
    def num(value, places=1):
        """Round only for display: 26.250 -> 26.3, 5.00 -> 5."""
        exp = Decimal(1).scaleb(-places)
        text = f"{Decimal(str(value)).quantize(exp, rounding=ROUND_HALF_UP):f}"
        return text.rstrip("0").rstrip(".") if "." in text else text

    @app.template_filter("pct")
    def pct(value):
        """57.84 -> "58%"; None (no target) -> "–"."""
        if value is None:
            return "–"
        return f"{Decimal(str(value)).quantize(Decimal(1), rounding=ROUND_HALF_UP)}%"

    return app
