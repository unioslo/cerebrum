#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""This files contains unit tests for VH's bofhd.

The idea is to test all of the VH-specific bofhd commands.

FIXME:
- Jot down the requirements:
    + A VH database instance
    + There must be a VH bofhd running somewhere
    + The testing account must have access to all commands (essentially
      superuser privileges in the test installation)
    + VH bofhd must be reachable from the testing site.

- Make sure not scratch accounts/groups are leaked. That means:
    + all tests creating scratch X, absolutely must delete them
    + should multiple scratch entities be created, they all must be deleted
      (and that must work in any order -- a scratch owner of a scratch group
       should be deletable before or after group delete just the same)

- Make sure create_scratch_vg() does not leave a scratch account owner behind,
when scratch vg is killed.
"""
import random
import re
import string
import sys
import uuid
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
        cls.url = 'bofhd url'
        cls.uname =    'superuser account'
        cls.password = "superuser's password"
        cls.vh_realm = "cereconf.VIRTHOME_REALM"
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
        if not re.search(what, current.faultString):
            raise
    # end assert_remote_fault


    def make_random_name(self, atype):
        """Create a username which satisfies WebID's requirements."""
        
        digits = list(string.digits)
        random.shuffle(digits)
        random_suffix = ''.join(digits)

        if atype == "va":
            return "testva " + random_suffix + self.vh_realm
        elif atype == "fa":
            return "testfa " + random_suffix + "@test.domain"
        elif atype == "group":
            return "testgrp " + random_suffix + self.vh_realm
        assert False
    # end make_random_name


    def make_random_email(self):
        """Create a fresh e-mail address."""

        return str(uuid.uuid4()) + "@some.domain"
    # end make_random_email
    

    def create_scratch_account(self, atype,
                               email = "bogus@mail",
                               password = "bogus password",
                               expire_date = None,
                               first_name = None,
                               last_name = None,
                               with_confirm = False):
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
            random_name = self.make_random_name(atype)
            args = [random_name, email, password,
                    marshal_expire(expire_date), first_name, last_name]
        elif atype == "fa":
            command = "user_fedaccount_create"
            random_name = self.make_random_name(atype)
            args = [random_name, email, marshal_expire(expire_date),
                    first_name, last_name]
        else:
            assert False, "Unknown atype=" + str(atype)

        result = conn.run_command(sid, command, *args)
        key = result["confirmation_key"]
        # We may want to confirm the account, so it's actually active
        if with_confirm:
            conn.run_command(sid, "user_confirm_request", key)
        return random_name
    # end create_scratch_va


    def create_scratch_va(self, email = "bogus@mail",
                          password = "bogus password",
                          expire_date = None,
                          first_name = None,
                          last_name = None,
                          with_confirm = False):
        """Interface to create_scratch_account for VA."""
        return self.create_scratch_account("va", email=email,
                                           password=password,
                                           expire_date=expire_date,
                                           first_name=first_name,
                                           last_name=last_name,
                                           with_confirm=with_confirm)
    # end create_scratch_va


    def create_scratch_fa(self):
        uname = self.create_scratch_account("fa")
        return uname
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

        # If the account has already been removed, this method must be a noop.
        try:
            conn.run_command(sid, command, uname)
        except xmlrpclib.Fault:
            self.assert_remote_fault("Did not find account")
    # end kill_scratch_account



    def create_scratch_vg(self, owner=None):
        """Create a scratch virtgroup.
        """

        # Since groups must be owned by somebody, we either get an account
        # supplied or grab a scratch account.
        conn = self.make_connection(self.url)
        sid = conn.login(self.uname, self.password)

        if not owner:
            owner = self.create_scratch_fa()

        gname = self.make_random_name("group")
        result = conn.run_command(sid, "group_create", gname,
                                  "scratch virtgroup",
                                  owner, "http://www.wetriffs.com")
        conn.run_command(sid, "group_info", gname)
        return gname
    # end create_scratch_vg



    def kill_scratch_group(self, gname, kill_owner=True):
        # Since groups must be owned by somebody, we either get an account
        # supplied or grab a scratch account.
        if not gname:
            return

        conn = self.make_connection(self.url)
        sid = conn.login(self.uname, self.password)

        # first kill the owner. But who is that?
        try:
            result = conn.run_command(sid, "group_info", gname)
            owners = [x["account_name"] for x in result["owner"]] 
            if kill_owner:
                for owner in owners:
                    self.kill_scratch_account(owner)
        except xmlrpclib.Fault:
            self.assert_remote_fault("Could not find a group")
            return

        # The group owner is dead now. Kill the group.
        try:
            return conn.run_command(sid, "group_delete", gname)
        except xmlrpclib.Fault:
            self.assert_remote_fault("Could not find a group")
            return
    # end kill_scratch_group
        


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
                 "user_recover_password", "user_recover_uname",
                 "group_create", "group_disable", "group_remove_members",
                 "group_list", "user_list_memberships", "group_change_owner",
                 "group_invite_moderator", "group_remove_moderator",
                 "group_invite_user", "group_info", "user_virtaccount_create",

                 'spread_add', 'spread_remove', 'spread_list',
                 "spread_entity_list",

                 'quarantine_add', 'quarantine_remove', 'quarantine_list',
                 'quarantine_show',
                 
                 "trait_list", "trait_set", "trait_remove", "trait_show",)
        commands = self.proxy.get_commands(self.sid)
        assert all(cmd in commands for cmd in cmds)
    # end test_get_commands


    #
    # group_info
    def test_group_info_nonexisting_group(self):
        try:
            self.remote_call("group_info", "bogus")
        except xmlrpclib.Fault:
            self.assert_remote_fault("CerebrumError:.*Could not find a group")
    # end test_group_info_nonexisting_group


    def test_group_info_regular(self):
        """Check that group_info spits back sensible crap"""

        vg = None
        try:
            vg = self.create_scratch_vg()
            result = self.remote_call("group_info", vg)
            assert all(x in result
                       for x in ("group_name", "expire", "spread",
                                 "description", "entity_id", "creator",
                                 "moderator", "owner", "member", "url",))
        finally:
            self.kill_scratch_group(vg)
    # end test_group_info_regular



    #
    # group_invite_user
    def test_just_invite_user(self):
        """Check that making an invite works.

        This does not test accepting the invite.
        """
        
        vg = None
        try:
            vg = self.create_scratch_vg()
            self.remote_call("group_invite_user", "address@is.invalid", vg)
        finally:
            self.kill_scratch_group(vg)
    # end test_invite_user


    def test_group_invite_and_accept(self):
        """Check that making and accepting group join invite works.
        """

        vg = va = None
        try:
            vg = self.create_scratch_vg()
            va = self.create_scratch_va()
            req = self.remote_call("group_invite_user", "address@is.invalid", vg)
            key = req["confirmation_key"]
            self.remote_call("user_su", va)
            self.remote_call("user_confirm_request", key)
            self.logout()
            self.login()
            result = self.remote_call("group_info", vg)
            assert "account: 1 member(s)" ==  result["member"]
        finally:
            self.kill_scratch_group(vg)
            self.kill_scratch_account(va)
    # end test_group_invite_and_accept
    

    #
    # group_remove_moderator
    def test_remove_actual_moderator(self):
        """Check that removing an active moderator from group works
        """

        vg = fa = None
        try:
            fa = self.create_scratch_fa()
            vg = self.create_scratch_vg(owner=fa)
            # Now, making a a moderator is suprisingly complex.
            self.remote_call("user_su", fa)
            req = self.remote_call("group_invite_moderator", "address.is@invalid", vg)
            key = req["confirmation_key"]
            self.remote_call("user_confirm_request", key)
            self.logout()
            self.login()
            result = self.remote_call("group_info", vg)
            moderators = result["moderator"]
            assert [fa,] == [x["account_name"] for x in moderators]
            # Finally, remove the moderator
            self.remote_call("group_remove_moderator", fa, vg)
        finally:
            self.kill_scratch_group(vg)
            self.kill_scratch_account(fa)
    # end test_remove_actual_moderator


    def test_remove_fa_which_is_not_moderator(self):
        """Removing an existing FA which is NOT a moderator for given group.

        This should still work, since an FA 
        """

        vg = fa = None
        try:
            vg = self.create_scratch_vg()
            fa = self.create_scratch_fa()
            self.remote_call("group_remove_moderator", fa, vg)
        finally:
            self.kill_scratch_group(vg)
            self.kill_scratch_account(fa)
    # end test_remove_fa_which_is_not_moderator
        
    

    def test_remove_mod_from_nonexist_group(self):
        """Cannot remove mods from non-existing group"""

        try:
            self.remote_call("group_remove_moderator", "bogus", "bogus")
        except xmlrpclib.Fault:
            self.assert_remote_fault("CerebrumError:.*Could not find a group")
    # end test_remove_mod_from_nonexist_group


    def test_remove_nonexist_mod_from_group(self):
        """Cannot remove non-existing mods."""
        
        vg = None
        try:
            vg = self.create_scratch_vg()
            self.remote_call("group_remove_moderator", "bogus", vg)
        except xmlrpclib.Fault:
            self.assert_remote_fault("CerebrumError:.*Could not find an account")
        finally:
            self.kill_scratch_group(vg)
    # end test_remove_nonexist_mod_from_group
            

    #
    # group_invite_moderator
    def test_invite_moderator_to_nonexist_group(self):
        try:
            result = self.remote_call("group_invite_moderator", "some@junk",
                                      "bogusgroup")
        except xmlrpclib.Fault:
            self.assert_remote_fault("CerebrumError:.*Could not find a group")
    # ebd test_invite_moderator_to_nonexist_group

    
    def test_invite_moderator(self):
        """Check that moderators can be invited

        FIXME? Some of the permission requirements may seem quaint.
        """

        vg = fa = None
        try:
            fa = self.create_scratch_fa()
            vg = self.create_scratch_vg(owner=fa)
            # group invite moderator can ONLY be done by FAs
            self.remote_call("user_su", fa)
            email = "foo@bar.invalid"
            result = self.remote_call("group_invite_moderator", email, vg)
            assert "confirmation_key" in result
            self.logout()
            self.login()
            request = self.remote_call("user_request_info",
                                       result["confirmation_key"])
            params = request["change_params"]
            assert all(x in params
                       for x in ("inviter_id", "group_id", "new"))
            assert params["new"] == email
            assert request["confirmation_key"] == result["confirmation_key"]
        finally:
            self.kill_scratch_account(fa)
            self.kill_scratch_group(vg)
    # end test_group_owner_change
     


    #
    # group_change_owner
    def test_change_to_nonexist_group(self):
        """Owner change for nonexisting group is impossible"""

        try:
            self.remote_call("group_change_owner", "foo@bar.invalid",
                             "somethingbogus")
        except xmlrpclib.Fault:
            self.assert_remote_fault("CerebrumError:.*Could not find a group")
    # end test_list_nonexist_group

    
    def test_group_change_owner(self):
        """Changing to nonexisting e-mail succeeds.

        group_change_owner does not really DO anything other than create a
        request. Even though the e-mail is fubar, the command still
        completes. It's like that by design.
        """

        vg = None
        try:
            vg = self.create_scratch_vg()
            email = "foo@bar.invalid"
            result = self.remote_call("group_change_owner", email, vg)
            assert "confirmation_key" in result
            request = self.remote_call("user_request_info",
                                       result["confirmation_key"])
            params = request["change_params"]
            assert all(x in params
                       for x in ("old", "group_id", "new"))
            assert params["new"] == email
            assert request["confirmation_key"] == result["confirmation_key"]
        finally:
            self.kill_scratch_group(vg)
    # end test_group_owner_change
        


    #
    # user_list_memberships
    def test_user_list_memberships_none(self):
        """Test that a fresh user is not member of anything"""
        va = None
        try:
            va = self.create_scratch_va()
            self.remote_call("user_su", va)
            assert self.remote_call("user_list_memberships") == list()
        finally:
            self.kill_scratch_account(va)
    # end user_list_memberships_none



    def test_user_list_memberships_normal(self):
        """Check that user is listed as part of a group where it's a member"""

        va = vg = None
        try:
            va = self.create_scratch_va()
            vg = self.create_scratch_vg()
            self.remote_call("group_add_members", va, vg)
            self.remote_call("user_su", va)
            assert [x["name"] for x in
                    self.remote_call("user_list_memberships")] == [vg,]
        finally:
            self.kill_scratch_account(va)
            self.kill_scratch_group(vg)
    # end user_list_memberships_normal



    #
    # group list
    def test_list_nonexist_group(self):
        """group list on non-existing group must fail"""
        try:
            self.remote_call("group_list", "somethingbogus")
        except xmlrpclib.Fault:
            self.assert_remote_fault("CerebrumError:.*Could not find a group")
    # end test_list_nonexist_group
    
    
    def test_list_empty_group(self):
        """Empty groups have no members"""

        vg = None
        try:
            vg = self.create_scratch_vg()
            assert self.remote_call("group_list", vg) == list()
        finally:
            self.kill_scratch_group(vg)
    # end test_list_empty_group
            

    def test_list_nonempty_group(self):

        va = vg = None
        try:
            va = self.create_scratch_va()
            vg = self.create_scratch_vg()
            self.remote_call("group_add_members", va, vg)
            assert [x["member_name"] for x in
                    self.remote_call("group_list", vg)] == [va,]
        finally:
            self.kill_scratch_group(vg)
            self.kill_scratch_account(va)
    # end test_list_nonempty_group



    #
    # group add_members
    def test_multiple_group_add_fails(self):
        """Check that adding the same members twice fails.

        Technically, this command is NOT part of the web-api, but we need it
        for testing just the same.
        """

        vg = va = None
        try:
            vg = self.create_scratch_vg()
            va = self.create_scratch_va()
            self.remote_call("group_add_members", va, vg)
            self.remote_call("group_add_members", va, vg)
        except xmlrpclib.Fault:
            self.assert_remote_fault("CerebrumError.*is already a member")
        finally:
            self.kill_scratch_account(va)
            self.kill_scratch_group(vg)
    # end test_remove_actually_works
        


    #
    # group remove_members
    def test_removing_members_from_nonexisting_group(self):
        """Removing members from nonexisting group should fail.
        """

        try:
            self.remote_call("group_remove_members", self.uname, "bogusgroup")
        except xmlrpclib.Fault:
            self.assert_remote_fault("CerebrumError:.*Could not find a group")
    # end test_removing_members_from_nonexisting_group


    def test_removing_nonexist_members_from_exist_group(self):
        """Removing nonexisting members from existing group should fail."""
        
        vg = None
        try:
            vg = self.create_scratch_vg()
            self.remote_call("group_remove_members", "bogususer", vg)
        except xmlrpclib.Fault:
            self.assert_remote_fault("CerebrumError:.*Could not find an account")
        finally:
            self.kill_scratch_group(vg)
    # end test_removing_nonexist_members_from_exist_gropu


    def test_remove_actually_works(self):
        """Test that removing members actually works.

        NB! This requires group_add_members to actually function.
        """

        vg = va = None
        try:
            vg = self.create_scratch_vg()
            va = self.create_scratch_va()
            self.remote_call("group_add_members", va, vg)
            self.remote_call("group_remove_members", va, vg)
        finally:
            self.kill_scratch_account(va)
            self.kill_scratch_group(vg)
    # end test_remove_actually_works
            


    #
    # group_disable
    def test_disabling_nonexist_group(self):
        """Disabling nonexinsting group must fail."""

        try:
            self.remote_call("group_disable", self.make_random_name("group"))
        except xmlrpclib.Fault:
            self.assert_remote_fault("CerebrumError:.*Could not find a group")
    # end test_disabling_nonexist_group


    def test_group_disable_works(self):
        """Check that disabling a group actually works."""

        gname = None
        owner = None
        try:
            owner = self.create_scratch_fa()
            gname = self.create_scratch_vg(owner=owner)
            assert "has been disabled" in self.remote_call("group_disable",
                                                           gname)
        finally:
            self.kill_scratch_account(owner)
            self.kill_scratch_group(gname)
    # end test_group_disable_works


    def test_double_disable_works(self):
        """Make sure the same group may be disabled multiple times."""

        gname = None
        owner = None
        try:
            owner = self.create_scratch_fa()
            gname = self.create_scratch_vg(owner=owner)
            assert "has been disabled" in self.remote_call("group_disable",
                                                           gname)
            assert "has been disabled" in self.remote_call("group_disable",
                                                           gname)
        finally:
            self.kill_scratch_account(owner)
            self.kill_scratch_group(gname)
    # end test_double_disable_works


    def test_nonowner_cannot_disable(self):
        """Make sure non-owners/root cannot disable groups"""

        owner = bogus = gname = None
        try:
            owner = self.create_scratch_fa()
            bogus = self.create_scratch_fa()
            gname = self.create_scratch_vg(owner=owner)
            self.remote_call("user_su", bogus)
            self.remote_call("group_disable", gname)
        except xmlrpclib.Error:
            self.assert_remote_fault("PermissionDenied")
        finally:
            self.kill_scratch_account(owner)
            self.kill_scratch_account(bogus)
            self.kill_scratch_group(gname)
    # end test_nonowner_cannot_disable


    #
    # group_create
    def test_va_cannot_create_group(self):
        """Only FA/superuser can create groups."""

        va = None
        try:
            va = self.create_scratch_va()
            self.remote_call("user_su", va)
            self.remote_call("group_create", "bogus", "bogus group",
                             va, "http://www.google.com")
        except xmlrpclib.Fault:
            self.assert_remote_fault("PermissionDenied.*not allowed")
        finally:
            self.kill_scratch_account(va)
    # test_va_cannot_create_group


    def test_group_create_must_have_proper_name(self):
        """Group names must have a domain."""

        va = None
        try:
            va = self.create_scratch_va()
            self.remote_call("group_create", "bogus", "bogus group",
                             va, "http://www.google.com")
        except xmlrpclib.Fault:
            self.assert_remote_fault("PermissionDenied.*not allowed")
        finally:
            self.kill_scratch_account(va)
    # test_va_cannot_create_group


    def test_group_owner_must_be_fa(self):
        """Groups can be owned by FA only."""

        va = None
        try:
            va = self.create_scratch_va()
            self.remote_call("group_create", self.make_random_name("group"),
                             "test group", va, "http://www.google.com")
        except xmlrpclib.Fault:
            self.assert_remote_fault("PermissionDenied.*Operation not allowed")
        finally:
            self.kill_scratch_account(va)
    # end test_group_owner_must_be_fa


    def test_group_create_normal(self):
        """Successfully create a virthome group."""

        try:
            gname = self.create_scratch_vg()
        finally:
            self.kill_scratch_group(gname)
    # end test_group_create_normal
            


    #
    # user_recover_uname
    def test_recover_uname_nonexisting_mail(self):
        """Bogus email -> empty username set."""

        assert self.remote_call("user_recover_uname",
                                self.make_random_email()) == list()
    # end test_recover_uname_nonexisting_mail


    def test_recover_1uname(self):
        """Check that recovering one account from 1 e-mail works."""

        va = None
        try:
            email = self.make_random_email()
            va = self.create_scratch_va(email=email, with_confirm=True)
            junk = self.remote_call("user_recover_uname", email)
            assert junk == [va,]
        finally:
            self.kill_scratch_account(va)
    # end test_recover_1uname


    def test_recover_multiple_unames(self):
        """Check that one e-mail can recover multiple unames."""

        email = self.make_random_email()
        scratch = list()
        try:
            for junk in range(3):
                scratch.append(self.create_scratch_va(email=email,
                                                      with_confirm=True))

            assert (sorted(self.remote_call("user_recover_uname", email)) ==
                    sorted(scratch))
        finally:
            for uname in scratch:
                self.kill_scratch_account(uname)
    # end test_recover_multiple_unames


    #
    # user_recover_password
    def test_recover_password_on_superuser_fails(self):
        """Password recovery works for VA only."""

        try:
            self.remote_call("user_recover_password",
                             self.uname, self.make_random_email())
        except xmlrpclib.Fault:
            self.assert_remote_fault("CerebrumError:.*is NOT a VA.*Cannot recover")
    # end test_recover_password_on_superuser_fails


    def test_recover_password_wrong_mail(self):
        """Check that recover from wrong e-mail is impossible"""

        email = self.make_random_email()
        va = None
        try:
            va = self.create_scratch_va(email=email)
            self.remote_call("user_recover_password", va,
                             self.make_random_email())
        except xmlrpclib.Fault:
            self.assert_remote_fault("CerebrumError:.*Unable to recover pass")
        finally:
            self.kill_scratch_account(va)
    # end test_recover_password_wrong_mail


    def test_proper_password_recover(self):
        """Check that password recover creates a proper request."""
        
        email = self.make_random_email()
        va = None
        try:
            va = self.create_scratch_va(email=email)
            result = self.remote_call("user_recover_password", va, email)
            assert "confirmation_key" in result
        finally:
            self.kill_scratch_account(va)
    # edn test_proper_password_recover


    #
    # user_change_human_name
    def test_change_bogus_name(self):
        try:
            va = self.create_scratch_va()
            self.remote_call("user_su", va)
            self.remote_call("user_change_human_name",
                             "bogustype", "something")
        except xmlrpclib.Fault:
            self.assert_remote_fault("CerebrumError:.*Unknown name type")
        finally:
            self.kill_scratch_account(va)
    # end test_change_bogus_name

    
    def test_change_first_name(self):
        new = "new name"
        old = "old name"
        try:
            va = self.create_scratch_va(first_name=old)
            self.remote_call("user_su", va)
            result = self.remote_call("user_change_human_name",
                                      "HUMANFIRST", new)
            assert "HUMANFIRST changed for account" in result
        finally:
            self.kill_scratch_account(va)
    # end test_change_first_name

    
    def test_change_name_superuser_fails(self):
        """Name change is possible for VAs only."""

        try:
            self.remote_call("user_change_human_name", "HUMANFIRST", "new name")
        except xmlrpclib.Fault:
            self.assert_remote_fault(
                "CerebrumError:.*Only non-federated accounts may change")
    # test_change_name_superuser_fails


    #
    # user_change_email
    def test_change_mail_superuser(self):
        """Superusers don't have e-mails"""

        try:
            self.remote_call("user_change_email", self.make_random_email())
        except xmlrpclib.Fault:
            self.assert_remote_fault(
                "CerebrumError:.*possible for VirtAccounts/FEDAccounts only")
    # end test_change_mail_superuser


    def test_change_mail_va(self):
        """Changing e-mail should create a request, not change e-mail"""

        old = self.make_random_email()
        new = self.make_random_email()
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
            mail = self.make_random_email()
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
        """Check that requesting info for existing OTP works"""
        
        # Let's make email change request -- they are the most benign.
        va = None
        try:
            old = "old@address.invalid"
            new = "new@address.invalid"
            va = self.create_scratch_va(email=old)
            self.remote_call("user_su", va)
            request = self.remote_call("user_change_email", new)
            key = request["confirmation_key"]
            self.logout()
            self.login()
            result = self.remote_call("user_request_info", key)
            params = result["change_params"]
            assert "old" in params and "new" in params
        finally:
            self.kill_scratch_account(va)
    # end test_confirm_valid_request



    #
    # user_fedaccount_login
    def test_fedaccount_login_1st_time(self):
        """Check that sensible values -> new FA """

        uname = self.make_random_name("fa")
        self.remote_call("user_fedaccount_login",
                         uname, self.make_random_email())
        self.kill_scratch_account(uname)
    # end test_fedaccount_login_1st_time
    

    def test_fedaccount_login_2nd_time(self):
        """2nd time -- no need to create a new account."""

        try:
            uname = self.create_scratch_fa()
            self.remote_call("user_fedaccount_login",
                             uname, self.make_random_email(), None,
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
                             self.make_random_email(),
                             "bogus password")
            assert False
        except xmlrpclib.Fault:
            self.assert_remote_fault("No event associated with key bogus key")
    # end test_join_group_invalid_key



    #
    # user_virtaccount_join_group
    def __create_group_invite(self):
        fa = self.create_scratch_fa()
        vg = self.create_scratch_vg(owner=fa)
        self.remote_call("user_su", fa)
        req = self.remote_call("group_invite_user", "address@is.invalid", vg)
        self.logout()
        self.login()
        return req["confirmation_key"], vg
    # end __create_group_invite
        


    def test_join_group_normal(self):
        """Normal event sequence for group join for VA"""

        va = key = vg = None
        try:
            va = self.make_random_name("va")
            key, vg = self.__create_group_invite()
            self.remote_call("user_virtaccount_join_group",
                             key, va, "something@is.invalid",
                             "pass word w33 m4k1k")
        finally:
            self.kill_scratch_account(va)
            self.kill_scratch_group(vg)
    # end test_join_group_invalid_uname

    
    def test_join_group_invalid_uname(self):
        """Invalid unames cannot join group by invitation"""

        va = key = vg = None
        try:
            va = self.create_scratch_va()
            key, vg = self.__create_group_invite()
            self.remote_call("user_virtaccount_join_group",
                             key, "bogus", "something@is.invalid",
                             "pass word w33 m4k1k")
        except xmlrpclib.Fault:
            self.assert_remote_fault("CerebrumError:.*Account name misses a realm")
        finally:
            self.kill_scratch_account(va)
            self.kill_scratch_group(vg)
    # end test_join_group_invalid_uname


    # FIXME: For some reason when talking to SSL-ed bofhd, a CerebrumError
    # resulting from invalid password fucks everything up. The test itself is
    # fine. There is something wrong with reading the XML-RPC message from
    # bofhd. This should really be looked into. This test works as expected
    # when bofhd is running unencrypted. I have no idea why this happens.
    def join_group_weak_password(self):
        """Users with weak passwords cannot join groups."""

        va = key = vg = None
        try:
            va = self.create_scratch_va()
            key, vg = self.__create_group_invite()
            self.remote_call("user_virtaccount_join_group",
                             key, va, "something@is.invalid",
                             "weak")
        finally:
            self.kill_scratch_account(va)
            self.kill_scratch_group(vg)
    # end test_join_group_weak_password
        


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
        """Check that a valid ID results in 'ok'.

        Use the most benign request -- email change.
        """

        va = None
        try:
            old = "old@address.invalid"
            new = "new@address.invalid"
            va = self.create_scratch_va(email=old)
            self.remote_call("user_su", va)
            request = self.remote_call("user_change_email", new)
            key = request["confirmation_key"]
            assert "e-mail changed" in self.remote_call("user_confirm_request",
                                                        key)
        finally:
            self.kill_scratch_account(va)
    # end test_confirm_valid_request
# end test_driver

