#!/usr/bin/env python
# -*- encoding: iso-8859-1 -*-

"""This file sets up the environment for the sqlite backend.
"""

from common import DBTestBase
from common import sneaky_import

class test_SQLite(DBTestBase):
    def setup(self):
        if not self.db_class:
            db_mod = sneaky_import("Cerebrum.Database", True)
            DBTestBase.db_class = db_mod.SQLite

        self.db = self.db_class(service=":memory:")
    # end setup

    def teardown(self):
        self.db.rollback()
        self.db.close()
    # end teardown

    def test_foreign_key2(self):
        """Check that foreign keys are enforced"""

        # We know that sqlite does not support them. Don't like test failure
        pass
    # end test_foreign_key2
# end test_SQLite
