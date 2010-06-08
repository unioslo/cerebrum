#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""This files contains unit tests for VH's bofhd.

The idea is to test all of the VH-specific bofhd commands.

FIXME:

- Jot down the environment requirements for these automatic tests.
  Requirements:

    - A VH database instance
    - There must be a VH bofhd running somewhere
    - The testing account must have access to all commands (essentially
      superuser privileges in the test installation)
    - VH bofhd must be reachable from the testing site.
"""
import random
import re
import string
import sys
import xmlrpclib

from mx.DateTime import now
from mx.DateTime import DateTimeDelta





class test_driver(object):
    """Testing class for bofhd (autodiscovered).
    """

    @classmethod
    def setup_class(cls):
        """Test framework fixture. Loaded during file import.
        """

        # FIXME: This should be supplied from the command line.
        cls.url = ''
        cls.uname = ''
        cls.password = ''
        cls.vh_realm = ''
    # end setup_class


    def setup(self):
        """Test framework fixture. Loaded before each test is run."""

        self.login()
    # end setup(self):


    
    ########################################################################
    # Utility functions.
    ########################################################################
    def login(self):
        self.proxy = self.make_connection(self.url)
        self.sid = self.proxy.login(self.uname, self.password)
    # end setup


    def logout(self):
        if self.sid is not None:
            self.proxy.logout(self.sid)

        self.sid = None
        self.proxy = None
    # end logout


    @staticmethod
    def make_connection(url):
        """Open connections to a bofhd instance."""
        
        if url.startswith("https"):
            return xmlrpclib.ServerProxy(url, xmlrpclib.SafeTransport(),
                                         allow_none=True)
        return xmlrpclib.ServerProxy(url, allow_none=True)
    # end make_connection


    def remote_call(self, name, *rest):
        """Call the command 'name' in bofhd."""
        
        return self.proxy.run_command(self.sid, name, *rest)
    # end remote_call


    def assert_remote_fault(self, what):
        """Make it somewhat less cumbersome to test xmlrpclib.Faults"""
        
        current = sys.exc_info()[1]
        assert re.search(what, current.faultString)
    # end assert_remote_fault


    def make_random_uname(self, atype):
        """Create a username which satisfies WebID's requirements."""
        
        digits = list(string.digits)
        random.shuffle(digits)
        random_name = "test " + ''.join(digits)

        if atype == "va":
            return random_name + self.vh_realm
        elif atype == "fa":
            return random_name + "@test.domain"
        assert False
    # end make_random_uname
    

    def create_scratch_account(self, atype,
                               email = "bogus@mail",
                               password = "bogus password",
                               expire_date = None,
                               first_name = None,
                               last_name = None):
        """Make a scratch account that we can throw away later."""
        def marshal_expire(d):
            if d is None:
                return d
            return d.strftime("%Y-%m-%d")
        
        # Do it through a separate connection to have all the priviliges
        conn = self.make_connection(self.url)
        sid = conn.login(self.uname, self.password)
        if atype == "va":
            command = "user_virtaccount_create"
            random_name = self.make_random_uname(atype)
            args = [random_name, email, password,
                    marshal_expire(expire_date), first_name, last_name]
        elif atype == "fa":
            command = "user_fedaccount_create"
            random_name = self.make_random_uname(atype)
            args = [random_name, email, marshal_expire(expire_date),
                    first_name, last_name]
        else:
            assert False, "Unknown atype=" + str(atype)
            
        conn.run_command(sid, command, *args)
        return random_name
    # end create_scratch_va


    def create_scratch_va(self, email = "bogus@mail",
                          password = "bogus password",
                          expire_date = None,
                          first_name = None,
                          last_name = None):
        """Interface to create_scratch_account for VA."""
        return self.create_scratch_account("va", email=email,
                                           password=password,
                                           expire_date=expire_date,
                                           first_name=first_name,
                                           last_name=last_name)
    # end create_scratch_va


    def create_scratch_fa(self):
        return self.create_scratch_account("fa")
    # end create_scratch_fa


    def kill_scratch_account(self, uname, with_logout=True):
        """Inverse of create_scratch_va.

        with_logout decides whether the current session (self.sid) should be
        terminated. This is useful when deleting the account holding THIS
        session.
        """

        if not uname:
            return
        
        if with_logout:
            self.logout()
        
        conn = self.make_connection(self.url)
        sid = conn.login(self.uname, self.password)
        if uname.endswith(self.vh_realm):
            command = "user_virtaccount_nuke"
        else:
            command = "user_fedaccount_nuke"
        
        conn.run_command(sid, command, uname)
    # end kill_scratch_account
        




    ########################################################################
    # The tests themselves.
    ########################################################################
    def test_get_commands(self):
        """Check that bofhd returns a suitable command list.
        """

        cmds = ( "user_confirm_request", "user_virtaccount_join_group",
                 "user_fedaccount_nuke", "user_virtaccount_disable",
                 "user_fedaccount_login", "user_su", "user_request_info",
                 "user_info", "user_accept_eula", "user_change_password",

                 "user_change_email", "user_change_human_name",
                 "user_recover_password", "user_recover_uname", "group_create",
                 "group_disable", "group_remove_members", "group_list",
                 "user_list_memberships", "group_change_owner",
                 "group_invite_moderator", "group_remove_moderator",
                 "group_invite_user", "group_info", "user_virtaccount_create",
                 'spread_add', 'spread_remove', 'spread_list', "spread_entity_list",
                 'quarantine_add', 'quarantine_remove', 'quarantine_list',
                 'quarantine_show', "trait_list", "trait_set", "trait_remove",
                 "trait_show",)
        commands = self.proxy.get_commands(self.sid)
        assert all(cmd in commands for cmd in cmds)
    # end test_get_commands


    #
    #
    def test_change_mail_superuser(self):
        """Superusers don't have e-mails"""

        try:
            self.remote_call("user_change_email", "blapp@domain.invalid")
        except xmlrpclib.Fault:
            self.assert_remote_fault(
                "CerebrumError:.*possible for VirtAccounts/FEDAccounts only")
    # end test_change_mail_superuser


    def test_change_mail_va(self):
        """Changing e-mail should create a request, not change e-mail"""

        old = "old@address"
        new = "new@address"
        va = None
        try:
            # 1. create an account
            va = self.create_scratch_va(email=old)
            # 2. change session to it
            self.remote_call("user_su", va)
            # 3. ask for e-mail change
            req = self.remote_call("user_change_email", new)
            # 4. logout current session
            self.logout()
            # 5. login as superuser again
            self.login()
            # 6. check that the change request is actually there.
            stored_request = self.remote_call("user_request_info",
                                              req["confirmation_key"])
            d = stored_request["change_params"]
            assert d["new"] == new
            assert d["old"] == old
            assert stored_request["confirmation_key"] == req["confirmation_key"]
        finally:
            self.kill_scratch_account(va)
    # end test_change_mail_va
        

    #
    # user_change_password
    def test_change_password_old_is_wrong(self):
        """Check that old password must match before changing.
        """

        va = None
        try:
            pwd = "blipp blapp blopp"
            va = self.create_scratch_va(password=pwd)
            self.remote_call("user_su", va)
            # use reverse password as old; it's obviously wrong
            self.remote_call("user_change_password", pwd[::-1], pwd[::-1])
        except xmlrpclib.Fault:
            self.assert_remote_fault("CerebrumError: Old password does not match")
        finally:
            self.kill_scratch_account(va)
    # end test_change_password_old_is_wrong

    
    def test_change_password_on_fa(self):
        """FA are not allowed to change passwords."""

        fa = None
        try:
            fa = self.create_scratch_fa()
            self.remote_call("user_su", fa)
            self.remote_call("user_change_password",
                             "blapp blipp blopp", "blopp blipp blapp")
        except xmlrpclib.Fault:
            self.assert_remote_fault("CerebrumError: Changing passwords is "
                                     "possible for VirtAccounts only")
        finally:
            self.kill_scratch_account(fa)
    # end test_change_password_on_fa


    def test_change_password_proper(self):
        """Check that password changing actually works.
        """

        va = None
        try:
            pwd = "blipp blapp blopp"
            va = self.create_scratch_va(password=pwd)
            self.remote_call("user_su", va)
            self.remote_call("user_change_password", pwd, pwd[::-1])
        finally:
            self.kill_scratch_account(va)
    # end test_change_password_old_is_wrong

        

    #
    # user_accept_eula
    def test_user_eula(self):
        va = None
        try:
            va = self.create_scratch_va()
            self.remote_call("user_su", va)
            self.remote_call("user_accept_eula", "user_eula")
        finally:
            self.kill_scratch_account(va)
    # end test_user_eula

    
    def test_user_accept_bogus_eula(self):
        """Check that bogus eula designation fails"""

        va = None
        try:
            va = self.create_scratch_va()
            # operator accepts EULAs. We don't want to do that on superuser,
            # therefore a su
            self.remote_call("user_su", va)
            self.remote_call("user_accept_eula", "bogus")
        except xmlrpclib.Fault:
            self.assert_remote_fault("CerebrumError: Invalid EULA:")
        finally:
            self.kill_scratch_account(va)
    # end test_user_accept_bogus_eula
        

    #
    # user_info
    def test_user_info_on_user(self):
        """Check that user_info returns what we expect"""

        uname = None
        try:
            mail = "test@mail"
            password = "test password"
            expire_date = now() + DateTimeDelta(30)
            first_name = "Schnappi"
            last_name = "von Krokodil"
            uname = self.create_scratch_va(mail, password, expire_date,
                                       first_name, last_name)
            data = self.remote_call("user_info", uname)
            for name, value in (("username", uname),
                                ("email_address", mail),
                                ("expire", expire_date)):
                assert data[name] == value
        finally:
            self.kill_scratch_account(uname)
    # end test_user_info_on_user

    
    def test_user_info_on_bogus_user(self):
        """Take user info on non-existing user.
        """

        try:
            self.remote_call("user_info", "bogususer")
            assert False
        except xmlrpclib.Fault:
            self.assert_remote_fault("CerebrumError:.*Could not find an account with")
    # end test_user_info_on_bogus_user


    #
    # user_request_info
    def test_request_info_on_bogus_key(self):
        try:
            self.remote_call("user_request_info",
                             "boguskey")
            assert False
        except xmlrpclib.Fault:
            self.assert_remote_fault("CerebrumError: No event associated with key")
    # end test_request_info_on_bogus_key


    def test_request_info_on_existing_key(self):
        # FIXME: Need to create an event of some kind.
        pass
    

    #
    # user_fedaccount_login
    def test_fedaccount_login_1st_time(self):
        """Check that sensible values -> new FA """

        uname = self.make_random_uname("fa")
        self.remote_call("user_fedaccount_login",
                         uname, "bogus@email")
        self.kill_scratch_account(uname)
    # end test_fedaccount_login_1st_time
    

    def test_fedaccount_login_2nd_time(self):
        """2nd time -- no need to create a new account."""

        try:
            uname = self.create_scratch_fa()
            self.remote_call("user_fedaccount_login",
                             uname, "bogus@email", None,
                             "Human", "Test")
        finally:
            self.kill_scratch_account(uname)
    # end test_fedaccount_login_2nd_time
        

    #
    # user_virtaccount_disable
    def test_disable_nonexist_va(self):
        """Check that disabling a non-existing va fails"""

        try:
            uname = "bogus-name"
            self.remote_call("user_virtaccount_disable", uname)
            assert False
        except xmlrpclib.Fault:
            self.assert_remote_fault("Could not find an account with name=%s" % uname)
    # end test_nuke_nonexist_fa
        

    def test_disable_va(self):
        """Check that disabling existing va works."""

        va = None
        try:
            va = self.create_scratch_va()
            self.remote_call("user_virtaccount_disable", va)
        finally:
            self.kill_scratch_account(va)
    # end test_disable_va


    def test_disable_with_insufficient_privileges(self):
        """Check that disabling as a VA fails (superuser only)"""

        va1 = va2 = None
        try:
            va1 = self.create_scratch_va()
            va2 = self.create_scratch_va()
            self.remote_call("user_su", va1)
            self.remote_call("user_virtaccount_disable", va2)
            assert False
        except xmlrpclib.Fault:
            self.assert_remote_fault("PermissionDenied.*cannot delete")
        finally:
            self.kill_scratch_account(va1)
            self.kill_scratch_account(va2)
    # end test_disable_with_insufficient_privileges


    #
    # user_fedaccount_nuke
    def test_nuke_nonexist_fa(self):
        """Check that nuking a non-existing fedaccount fails"""

        try:
            uname = "bogus-name"
            self.remote_call("user_fedaccount_nuke", uname)
            assert False
        except xmlrpclib.Fault:
            self.assert_remote_fault("Did not find account %s" % uname)
    # end test_nuke_nonexist_fa


    def test_nuke_existing_fa(self):
        """Check that deleting existing FA is possible"""
        # We'll need to create such an FA

        fa = self.create_scratch_fa()
        self.remote_call("user_fedaccount_nuke", fa)
    # end test_nuke_existing_fa


    def test_nuke_existing_fa_by_nonsuperuser(self):
        """Check that only superuser can delete FAs."""

        fa1 = fa2 = None
        try:
            fa1 = self.create_scratch_fa()
            fa2 = self.create_scratch_fa()
            self.remote_call("user_su", fa1)
            self.remote_call("user_fedaccount_nuke", fa2)
            assert False
        except xmlrpclib.Fault:
            self.assert_remote_fault("PermissionDenied.*cannot delete")
        finally:
            self.kill_scratch_account(fa1)
            self.kill_scratch_account(fa2)
    # end test_nuke_existing_fa_by_nonsuperuser
    

    #
    # user_virtaccount_join_group
    def test_join_group_invalid_key(self):
        """Check that that joining a group is impossible with a bogus key.
        """

        try:
            self.remote_call("user_virtaccount_join_group",
                             "bogus key",
                             "bogus account",
                             "bogus@email",
                             "bogus password")
            assert False
        except xmlrpclib.Fault:
            self.assert_remote_fault("No event associated with key bogus key")
    # end test_join_group_invalid_key


    def test_join_group_valid_key(self):
        """Check that a user can join a group by invitation"""

        # Need to set up an invitation first
        pass
    # end test_join_group_valid_key

    def test_join_group_invalid_uname(self):
        pass

    def test_join_group_weak_password(self):
        pass

    def test_join_group_bogus_email(self):
        pass


    #
    # user confirm_request
    def test_confirm_bogus_request(self):
        """Check that an invalid ID results in an exception
        """
        try:
            key = "bogus"
            self.remote_call("user_confirm_request", key)
        except xmlrpclib.Fault:
            self.assert_remote_fault("No event associated with key %s" % key)
    # end test_confirm_bogus_request
    

    def test_confirm_valid_request(self):
        """Check that a valid ID results in 'ok'"""
        pass

# end test_driver

