class ChangeLog(object):
    def __init__(self, change_by=None, change_program=None):
        self.change_by = change_by
        self.change_program = change_program
        self.messages = []
        
    def log_change(self, target_entity, target_type, change_category,
                   change_type, change_params=None, change_by=None,
                   change_program=None, comment=None):
        if change_by is None and self.change_by is not None:
            change_by = self.change_by
        elif change_program is None and self.change_program is not None:
            change_program = self.change_program
        if change_by is None and change_program is None:
            raise self.ProgrammingError, "must set change_by or change_program"
        self.messages.append( {'id': id,
                               't_type': target_type,
                               'c_category': change_category,
                               'c_type': change_type,
                               'c_params': change_params,
                               'c_by': change_by,
                               'c_program': change_program,
                               'comment': comment})

    def rollback_log(self):
        self.messages = []

    def commit_log(self):
        """This method should be called by Database.commit to prevent
        ELInterface from returning data that are not commited (and are
        thus invisible to other processes, and may be rolled back),"""

        for m in self.messages:
            id = int(self.nextval('change_log_seq'))
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=change_log]
               (change_id, target_entity, target_type, change_category,
                change_type, change_params, change_by, change_program,
                comment)
            VALUES (:id, :t_id, :t_type, :c_category, :c_type, :c_params, :c_by,
                    :c_program, :comment)""", m)
        self.messages = []
