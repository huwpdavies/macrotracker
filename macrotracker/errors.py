"""Friendly pages for things that go wrong, in the app's own style."""
from flask import render_template
from sqlalchemy.exc import InterfaceError, OperationalError

from .extensions import db


def register(app):
    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/error.html", code=404, title="Page not found",
                               message="That page doesn't exist, or the item was deleted."), 404

    @app.errorhandler(OperationalError)
    @app.errorhandler(InterfaceError)
    def database_down(error):
        # The connection failed part-way, so throw away the half-finished transaction.
        db.session.rollback()
        app.logger.warning("Database unreachable: %s", error)
        return render_template("errors/error.html", code=503, title="Can't reach your data",
                               message="The database isn't answering right now. Your data is safe; "
                                       "try again in a moment.", retry=True), 503

    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        return render_template("errors/error.html", code=500, title="Something went wrong",
                               message="That didn't work, and it's not your fault. Try again, "
                                       "or go back to the dashboard.", retry=True), 500
