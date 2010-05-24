#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""This file constains unit tests (nose) for the VirtAccount modules.

For now (2009-03-18), just jot down something. The tests assume an existing
environment and a database. This cannot be a prerequisite, but for now we
don't bother fixing this.

Notes:
------
* Rule #1 - No matter how silly, if it actually tests some aspect of the
  functionality, a part of a business logic, anything of value, it's a
  test. Write it.
* FIXME: This testsuite presumes an existing database and an environment. It
  should not be like this.
* 

"""

from mx.DateTime import now
from nose.tools import raises, assert_raises


class testbase(object):

    def __init__(self):
        self.db = None
        self.const = None
        self.factory = None
    # end __init__


    def setup(self):
        import cerebrum_path, cereconf
        from Cerebrum.Utils import Factory

        self.factory = Factory
        self.db = Factory.get("Database")()
        self.const = Factory.get("Constants")()
    # end setup

    def teardown(self):
        self.db.rollback()
        self.db.close()
    # end teardown
# end testbase



class test_VAccount(testbase):
    def test_vaccount_exists(self):
        """Check that VAccount instances exist."""

        va = self.factory.get("VAccount")(self.db)
    # end test_vaccount_exists

    def test_vaccount_has_methods(self):
        """Check that VAccounts have the necessary methods."""

        va = self.factory.get("VAccount")(self.db)
        for name in ("write_db", "clear", "find", "populate",):
            obj = getattr(va, name)
            assert hasattr(obj, "__call__")
    # end test_vaccount_has_methods


    def test_populate_vaccont1(self):
        """Simplest VAccount.populate() test."""

        va = self.factory.get("VAccount")(self.db)
        va.populate(now(), None, "nosetest@virthome")
        va.write_db()
    # end test_populate_vaccont1


    @raises(Exception)
    def test_populate_vaccount2(self):
        """Test that VAccount's expire date exceeds create date."""

        va = self.factory.get("VAccount")(self.db)
        va.populate(now(), now() - 20, "nosetest@virthome")
        va.write_db()
    # end test_populate_vaccount2


    @raises(Exception)
    def test_populate_vaccount3(self):
        """Check that VAccount ID's realm is hardwired to a specific value."""

        va = self.factory.get("VAccount")(self.db)
        va.populate(now(), now() - 20, "nosetest1@schnappi")
        va.write_db()
    # end test_populate_vaccount3
        

    def test_vaccount_has_attributes(self):
        """Check that VAccounts have the necessary attributes.

        We'll have to populate an account in order to check for attributes. It
        is like that by design.
        """

        va = self.factory.get("VAccount")(self.db)
        va = self.factory.get("VAccount")(self.db)
        va.populate(now(), None, "nosetest1@virthome")
        for name in ("create_date", "expire_date"):
            assert hasattr(va, name)
    # end test_vaccount_has_attributes


    @raises(Exception)
    def test_double_populate_impossible(self):
        """Test that 2 consecutive populate() calls are impossible."""

        va = self.factory.get("VAccount")(self.db)
        va.populate(now(), None, "nosetest1@virthome")
        va.populate(now(), None, "nosetest1@virthome")
    # end test_double_populate_impossible


    def test_find_nonexisting_vaccount_fails(self):
        """Check that find() on non-existing vaccounts fails."""

        va = self.factory.get("VAccount")(self.db)
        va.find(-1)
    # end test_find_nonexisting_vaccount_fails


# end test_VAccount
        


class test_FEDAccount(testbase):

    @raises(NotImplementedError)
    def test_no_password_for_fedaccount(self):
        """Check that FEDAccounts cannot be set password on."""

        fa = self.factory.get("FEDAccount")(self.db)
        fa.set_password("schnappi")
    # end test_no_password_for_fedaccount

# end test_FEDAccount
    


