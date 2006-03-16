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
        return True
        if self.superuser:
            return True

        operations = [(i.__name__, method) for i in obj.builder_parents + (obj.__class__, )]
        print 'checking', operations

        if obj in self._permissions:
            return bool(self._permissions[obj].intersection(operations))
            
        methods = sets.Set()

        for h in self._handlers:
            if hasattr(h, 'get_permissions'):
                methods.update(h.get_permissions(obj))

        self._permissions[obj] = methods

        return bool(self._permissions[obj].intersection(operations))

# arch-tag: d6e64578-943c-11da-98e6-fad2a0dc4525
