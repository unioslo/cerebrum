#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""Check that the environment that the tests are run in is remotely sane."""


def test_import_critical_components():
    """Check that all the critical modules can be imported"""

    import cerebrum_path
    import cereconf
    
    import Cerebrum
    from Cerebrum.Utils import Factory
# end test_import_critical_components

def test_create_db_connection():
    """Make sure that we can actually establish a conn to the db."""

    import cerebrum_path, cereconf
    from Cerebrum.Utils import Factory

    print "\nDB: %s" % cereconf.CEREBRUM_DATABASE_NAME
    db = Factory.get("Database")()
    db.ping()
# end test_create_db_connection
