import pickle

class ChangeLog(object):
    # Don't want to override the Database constructor
    def cl_init(self, change_by=None, change_program=None):
        self.change_by = change_by
        self.change_program = change_program
        self.messages = []
        
    def log_change(self, subject_entity, change_type_id,
                   destination_entity, change_params=None,
                   change_by=None, change_program=None):
        if change_by is None and self.change_by is not None:
            change_by = self.change_by
        elif change_program is None and self.change_program is not None:
            change_program = self.change_program
        if change_by is None and change_program is None:
            raise self.ProgrammingError, "must set change_by or change_program"
        change_type_id = int(change_type_id)
        if change_params is not None:
            change_params = pickle.dumps(change_params)
        self.messages.append( locals() )

    def rollback_log(self):
        """See commit_log"""
        self.messages = []

    def commit_log(self):
        """This method should be called by Database.commit to prevent
        ELInterface from returning data that are not commited (and are
        thus invisible to other processes, and may be rolled back),"""

        for m in self.messages:
            m['id'] = int(self.nextval('change_log_seq'))
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=change_log]
               (change_id, subject_entity, 
                change_type_id, dest_entity, change_params, change_by, change_program)
            VALUES (:id, :subject_entity, :change_type_id,
                :destination_entity, :change_params, :change_by, :change_program)""", m)
        self.messages = []

    def get_log_events(self, start_id, type=None):
        where = ["change_id >= :start_id"]
        bind = {'start_id': start_id}
        if type is not None:
            where += "type = :type"
            bind['type'] = type
        where = "WHERE "+" AND ".join(where)
        ret = []
        for r in self.query("""
        SELECT change_id, subject_entity, change_type_id, dest_entity,
               change_params, change_by, change_program
        FROM [:table schema=cerebrum name=change_log] %s
        ORDER BY change_id""" % where, bind):
            ret.append(r)
        return ret

##     def rollback(self):
##         self.rollback_log()
##         self.orig_rollback()

##     def commit(self):
##         self.commit_log()
##         self.orig_commit()
