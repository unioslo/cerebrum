import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory


class ImportBase(object):
    """
    I provide the base interface and structure for importing data to cerebrum
    """

    def __init__(self, db, dryrun):
        self.db                 = db
        self.dryrun             = dryrun

        self.constants          = Factory.get('Constants')(db)
        self.account            = Factory.get('Account')(db)
        self.logger             = Factory.get_logger("console")


        self.account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        self.default_creator_id = self.account.entity_id


    def attemptCommit(self):
        if self.dryrun:
            self.db.rollback()
            print("Rolled back all changes")
        else:
            self.db.commit()
            print("Committed all changes")
        # fi
    # end attempt_commit
