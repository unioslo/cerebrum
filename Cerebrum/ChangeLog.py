import pickle

class ChangeLog(object):
    # Don't want to override the Database constructor
    def cl_init(self, change_by=None, change_program=None):
        pass
    
    def log_change(self, *foo, **bar):
        pass

    def rollback_log(self):
        pass

    def commit_log(self):
        pass
