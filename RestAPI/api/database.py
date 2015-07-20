from flask import _app_ctx_stack as stack
from Cerebrum.Utils import Factory


class Database(object):
    """Interface to the Cerebrum database."""
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        app.teardown_appcontext(self.teardown)

    def connect(self):
        return Factory.get('Database')(client_encoding='UTF-8')

    def teardown(self, exception):
        """Closes the database connection at the end of the request."""
        ctx = stack.top
        if hasattr(ctx, 'db'):
            ctx.db.close()

    @property
    def connection(self):
        """Returns a database connection.
        Creates one if there is none for the current application context."""
        ctx = stack.top
        if ctx is not None:
            if not hasattr(ctx, 'db'):
                ctx.db = self.connect()
            return ctx.db
