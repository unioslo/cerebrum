import sets

class Authorization:
    handlers = []

    def __init__(self, db, users):
        self.db = db
        self.users = users
        self.superuser = False

        self._permissions = {} # FIXME: weakref?
        self._handlers = [i(self) for i in self.handlers]
            
    def check_permission(self, obj, method):
        if self.superuser:
            return True
            
        methods = self._permissions.get(obj, sets.Set())
        if method in methods:
            return True

        for h in self._handlers:
            if hasattr(h, 'check_permission'):
                methods.update(h.check_permission(self.users, obj, method))

        self._permissions[obj] = methods

        return True # FIXME: for debugging...
        return method in methods
