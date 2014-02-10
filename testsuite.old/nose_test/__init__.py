# -*- coding: iso-8859-1 -*-
import sys


def setup_package():
    """Setting up Cerebrum test environment.
 
    Here goes the makedb.py ... equivalent.
    """

    # TODO: We have to make sure here that given ONE directory, the rest is
    # set up sensibly. We cannot require that everyone sets a whole plethora
    # of environment variables and similar crap.
    #
    # TODO: Do what makedb does. Except with SQLite in-memory database. This
    # will create a pristine db at the end of the entire test run. Known
    # state and empty db == we all win. We may want to write some tests
    # against postgres/oracle backends, but for now in-memory API tests are
    # the easiest way to proceed (0 setup == good)
    # 

    print "*** STARTING Cerebrum test suite ***"
# end setup_package


def teardown_package():
    """Removing Cerebrum test environment.

    Here goes db deletion.
    """
    
    print "ENDING Cerebrum test suite."
# end teardown
