from Cerebrum.Utils import Factory
db = Factory.get('DBDriver')
cl = Factory.get('ChangeLog')

class CLDatabase(db, cl):
    def rollback(self):
        self.rollback_log()
        super(db, self).rollback()

    def commit(self):
        self.commit_log()
        super(db, self).commit()
