#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2008-2016 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""
Test module for PasswordNotifier.

This module is found by Nose (http://code.google.com/p/python-nose/),
and its tests are invoked by Nose's nosetests script.
"""

import time, mx.DateTime as dt

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.password_notifier.notifier import PasswordNotifier
from Cerebrum.modules.EntityTrait import _EntityTraitCode
import pickle

now = dt.today()
age = 365
w2 = 2 * dt.oneWeek
w3 = 3* dt.oneWeek
w5 = 5 * dt.oneWeek

# This dict has user names as key, these will
# be used as test users.
# The values are lists, whose first element
# is a date or None, which represents when
# the user's password was last set.
# The following elements, if any are the 
# dates when notifications/reminders were sent
users = {
        # Alice should be splatted
        'alice': [now - (age + w5 + dt.oneDay), now - (w5 + dt.oneDay), now - (w3 + dt.oneDay)],
        # bob should be warned
        'bob': [None],
        # charlie should be reminded
        'charlie': [now - (age + w3 + dt.oneDay), now - (w3 + dt.oneDay)],
        # david ought not to be touched
        'david': [now - dt.oneDay],
        # emma should get her trait removed
        'emma': [now - dt.oneDay, now - w5, now - w2],
        # frank should be splatted
        'frank': [now - (age + w5 + dt.oneDay), (now - (w5 + dt.oneDay),)],
        }


from Cerebrum.modules.Email import AccountEmailMixin

class AccountFixEmail(AccountEmailMixin):
    """
    Mixin to override behaviour in some mixins related to
    email information. We don't store any, and we are not
    testing mod_email here.
    """
    def __init__(self, *rest, **kw):
        super(AccountFixEmail, self).__init__(*rest, **kw)
        # nobody@usit.uio.no is sent to /dev/null
        self.__override_primary_address = 'nobody@usit.uio.no'

    def get_primary_mailaddress(self):
        """Use this address instead of AccountEmailMixin.get_primary_mailaddress"""
        return self.__override_primary_address

    def set_primary_mailaddress(self, adr):
        self.__override_primary_address = adr

    def update_email_addresses(self):
        pass


def get_person(db):
    """
    Return a person who will own the test users
    """
    p = Factory.get("Person")(db)
    r = p.list_persons()
    if len(r) < 1:
        p.populate(birth_date=now, gender=c.gender_unknown)
        p.write_db()
        db.commit()
        return p
    p.find(r[0]['person_id'])
    return p

class sendmail(object):
    """
    Collect mails instead of sending them away.

    An object of this class should replace the _send_mail function
    in Cerebrum.modules.password_notifier.notifier, to make the PasswordNotifier
    module not to send mails.

    In stead the mails are collected in a list called `mails` in
    this object.
    """
    def __init__(self):
        self.mails = []
        self.returnvalue = True

    def __call__(self, mail_to, mail_from, subject, body, logger, mail_cc=None, debug_enabled=False):
        self.mails.append(locals())
        logger.info("From: %s\n%s", mail_from, body)
        return self.returnvalue

    def find(self, body):
        for i in self.mails:
            if i['body'] == body:
                return i

    def find_word(self, word):
        for i in self.mails:
            if word in i['body']:
                return i

def get_bootstrap(db):
    """
    Get the bootstrap_account
    """
    a = Factory.get("Account")(db)
    a.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    return a

def set_history(db, account, time):
    """
    Make an entry in password history for a password
    """
    sql = """DELETE FROM password_history WHERE entity_id = :id"""
    db.execute(sql, {'id': account.entity_id})
    if time is None:
        return
    sql = """INSERT INTO password_history (entity_id, md5base64, set_at)
             VALUES (:id, 'passord', :tm)"""
    db.execute(sql, {'id': account.entity_id, 'tm': time})

def make_mail(user, deadline, first=""):
    deadline = deadline.strftime('%Y-%m-%d')
    if first:
        first = first.strftime('%Y-%m-%d')
    return """User name: %(user)s
Deadline:  %(deadline)s
First:     %(first)s
""" % locals()

def setup():
    import tempfile, os
    fil, name = tempfile.mkstemp()
    os.write(fil,
"""From: nobody@usit.uio.no
Subject: Test PasswordNotifier

User name: ${USERNAME}
Deadline:  ${DEADLINE}
First:     ${FIRST_TIME}
""")
    os.close(fil)
    config.template = [name]
    import Cerebrum.modules.password_notifier.notifier as pn
    pn._send_mail = sendmail()
    import sys
    from Cerebrum import Utils
    if hasattr(Utils.this_module(), '__path__'):
        sys.path.append(__path__)
    else:
        sys.path.append(os.getcwd())
    cereconf.CLASS_ACCOUNT = list(cereconf.CLASS_ACCOUNT)
    cereconf.CLASS_ACCOUNT.insert(0, 'test_PasswordNotifier/AccountFixEmail')

def teardown():
    db = Factory.get("Database")()
    db.cl_init(change_program="nose-tests")
    account = Factory.get("Account")(db)
    from Cerebrum.modules.PasswordHistory import PasswordHistory
    pwhist = PasswordHistory(db)
    for u in users.keys():
        try:
            account.clear()
            account.find_by_name(u)
            try:
                pwhist.del_history(account.entity_id)
            except:
                pass
            # TODO: This overcomes a flaw in AccountHome.delete(), but to 
            # fix it, we must do politics
            account.delete()
            import Cerebrum.Account
            super(Cerebrum.Account.AccountHome, account).delete()
        except:
            import traceback
            print traceback.format_exc()
    if config.template:
        import os
        os.unlink(config.template[0])
    db.commit()

class config(object):
    template = []
    # nobody@usit.uio.no is sent to /dev/null
    summary_to = 'nobody@usit.uio.no'
    summary_from = 'nobody@usit.uio.no'

def create_users(db):
    """
    Create the accounts, and set password history and notification history.
    """
    b = get_bootstrap(db)
    p = get_person(db)
    c = Factory.get("Constants")(db)
    a = Factory.get("Account")(db)
    for key, val in users.iteritems():
        a.clear()
        try:
            a.find_by_name(key)
            try:
                a.delete_trait(c.trait_passwordnotifier_notifications)
            except:
                pass
            try:
                a.delete_trait(c.trait_passwordnotifier_excepted)
            except:
                pass
            a.write_db()
        except Errors.NotFoundError:
            a.populate(key, c.entity_person, p.entity_id, None, b.entity_id, None)
            a.write_db()
        set_history(db, a, val[0])
        # TODO: Unfortunately, I can't find any global Account spreads,
        # and accounts without spreads are not returned
        # by password history.
        # The AD@uio spread is selected because it doesn't trigger any
        # activities in our Account mixins.
        if not a.has_spread(c.spread_test_password_notifier):
            a.add_spread(c.spread_test_password_notifier)
        for r in a.get_entity_quarantine():
            a.delete_entity_quarantine(r['quarantine_type'])
        if len(val) > 1:
            if isinstance(val[1], tuple):
                numval = 0
                date = val[1][0]
                strval = val[1][0].strftime("Failed: %Y-%m-%d")
            else:
                numval = len(val) - 1
                date = val[1]
                strval = val[1].strftime("%Y-%m-%d")
            trait = {
                'code': c.trait_passwordnotifier_notifications,
                'target_id': None,
                'date': date,
                'numval': numval,
                'strval': strval
                }
            if len(val) == 3:
                trait['strval'] = trait['strval'] + ", " + val[2].strftime("%Y-%m-%d")
            a.populate_trait(**trait)
            a.write_db()

class test_PasswordNotifier(object):
    def setup(self):
        """
        Setup fresh every time
        """
        self.db = Factory.get("Database")()
        self.db.cl_init(change_program="nose-tests")
        global c
        C = Factory.get("Constants")
        c = C(self.db)
        if not hasattr(C, 'spread_test_password_notifier'):
            print "legger inn spread"
            C.spread_test_password_notifier = c.Spread('test@pwnotify', c.entity_account, 'Testspread')
            try:
                int(c.spread_test_password_notifier)
            except:
                c.spread_test_password_notifier.insert()
                c.spread_test_password_notifier.sql.commit()
        create_users(self.db)
        self.db.commit()
        self.account = Factory.get("Account")(self.db)
        logger = Factory.get_logger("console")
        self.notifier = PasswordNotifier.get_notifier(config=config)(db=self.db, logger=logger)
        from Cerebrum.modules.password_notifier.notifier import _send_mail
        _send_mail.mails = []
        _send_mail.returnvalue = True

    def teardown(self):
        self.db.commit()
                
    def test_get_old_account_ids(self):
        """
        Fetch the old account ids
        The users alice, bob, charlie, and frank does
        have old passwords or no history.
        """
        ids = set(self.notifier.get_old_account_ids())
        for u in ['alice', 'bob', 'charlie', 'frank']:
            self.account.find_by_name(u)
            assert self.account.entity_id in ids, "%s (%s) is not in old_account_ids" % (
                        u, self.notifier.get_notification_time(self.account))
            ids.remove(self.account.entity_id)
            self.account.clear()
        assert not ids, "%r is overflowing in ids" % ids

    def test_get_notified_ids(self):
        """
        Get previously notified users
        alice, charlie, emma, and frank are previously notified.
        Assert that they, and nobody else are returned.
        """
        ids = set(self.notifier.get_notified_ids())
        for u in ['alice', 'charlie', 'emma', 'frank']:
            self.account.find_by_name(u)
            assert self.account.entity_id in ids, "%s is not in old_account_ids" % u
            ids.remove(self.account.entity_id)
            self.account.clear()
        assert not ids, "%r is overflowing in ids" % ids

    def test_remove_trait(self):
        """
        Remove all password traits
        Remove the password trait from the users, and assert
        that it is gone.
        """
        for u in users.keys():
            self.account.clear()
            self.account.find_by_name(u)
            self.notifier.remove_trait(self.account)
            trait = self.account.get_trait(c.trait_passwordnotifier_notifications)
            assert trait is None, "Trait not removed for %s" % self.account.account_name

    def test_get_num_notifications(self):
        """
        Assert that the users have the correct number of notifications.
        """
        for u, v in users.items():
            self.account.clear()
            self.account.find_by_name(u)
            n = self.notifier.get_num_notifications(self.account)
            expect = len(v) - 1
            # Handle failed account
            if len(v) == 2 and isinstance(v[1], tuple):
                expect = 0
            assert n == expect, "Wrong number of notifications for %s" % self.account.account_name

    def test_inc_num_notifications(self):
        """
        Add a new notification record to database
        Increase the number of notifications by one, and assert that everything
        happens as expected.
        """
        for u, v in users.items():
            self.account.clear()
            self.account.find_by_name(u)
            self.notifier.inc_num_notifications(self.account)
            tr = self.account.get_trait(c.trait_passwordnotifier_notifications)
            expect = len(v)
            if len(v) == 2 and isinstance(v[1], tuple):
                expect = 1
            assert tr['numval'] == expect, "Wrong number of notifications for %s" % u
            dat = now
            if len(v) > 1:
                dat = v[1]
            assert tr['date'] == dat, "Wrong date for %s: expected %s, got %s" % (u, dat, tr['date'])
            all = str(tr['strval'])
            test = ", ".join([ x.strftime("%Y-%m-%d") for x in v[1:]])
            if test:
                test = test + ", " + now.strftime("%Y-%m-%d")
            else:
                test = now.strftime("%Y-%m-%d")
            assert all == test, "Wrong date for %s: expected %s, got %s" % (u, test, all)

    def test_get_notification_time(self):
        """
        For every user with a notification, check that it matches.
        """
        for u, v in users.iteritems():
            if len(v) == 1:
                continue
            self.account.clear()
            self.account.find_by_name(u)
            tm = self.notifier.get_notification_time(self.account)
            expect = v[1]
            if isinstance(expect, tuple):
                expect = expect[0]
            assert expect ==  tm, "Wrong date for %s: expected %s, got %s" % (u, v[1], tm)

    def test_rec_fail_notification(self):
        """
        Test that fail_notification works
        """
        for u, v in users.iteritems():
            if len(v) == 1:
                self.account.clear()
                self.account.find_by_name(u)
                self.notifier.rec_fail_notification(self.account)
                self.account.clear()
                self.account.find_by_name(u)
                tr = self.account.get_trait(c.trait_passwordnotifier_notifications)
                assert tr['numval'] == 0, "Wrong number of notifications after fail for %s" % u
                assert tr['date'] == now, "wrong date for %s: expected %s, got %s" %(
                        u, now, type(tr['date']))

    def test_get_deadline(self):
        """
        The calculated deadline should match the deadline found by this function.
        """
        for u, v in users.iteritems():
            self.account.clear()
            self.account.find_by_name(u)
            tm = self.notifier.get_deadline(self.account)
            ex = now + w5
            if len(v) > 1:
                if isinstance(v[1], tuple):
                    ex = v[1][0] + w5
                else:
                    ex = v[1] + w5
            assert tm == ex, "Wrong deadline for %s: expected %s, got %s" % (u, ex, tm)

    def test_remind_ok(self):
        """
        Assert that the correct users are reminded
        """
        for u, v in users.iteritems():
            self.account.clear()
            self.account.find_by_name(u)
            ex = False
            if len(v) == 2:
                if isinstance(v[1], tuple):
                    ex = False
                else:
                    ex = now >= v[1] + w2
            assert ex == self.notifier.remind_ok(self.account)

    def test_splat_user(self):
        """
        Splat the user and check for the quarantine
        """
        for u, v in users.iteritems():
            self.account.clear()
            self.account.find_by_name(u)
            self.notifier.splat_user(self.account)
            q = self.account.get_entity_quarantine(c.quarantine_autopassord)
            assert q, "%s has no quarantine" % u

    def test_process_accounts(self):
        """
        Process the accounts and check the results.
        This doesn't have any cool side effects other than a mail sent.
        """
        from Cerebrum.modules.password_notifier.notifier import _send_mail
        self.notifier.process_accounts()
        self.account.clear()
        self.account.find_by_name('alice')
        q = self.account.get_entity_quarantine(c.quarantine_autopassord)
        assert q, "alice should be splatted"
        assert not _send_mail.find_word('alice'), \
            "alice should not have been mailed"
        self.account.clear()
        self.account.find_by_name('bob')
        assert self.notifier.get_num_notifications(self.account) == 1, \
                "bob should have been first notified"
        assert _send_mail.find(make_mail('bob', now + w5)), \
                "did not find mail for bob"
        self.account.clear()
        self.account.find_by_name('charlie')
        assert self.notifier.get_num_notifications(self.account) == 2, \
                "charlie should have been reminded"
        assert _send_mail.find(make_mail('charlie', users['charlie'][1] + w5, users['charlie'][1])), \
                "did not find mail for charlie"
        self.account.clear()
        self.account.find_by_name('emma')
        assert self.notifier.get_num_notifications(self.account) == 0, \
                "emma should not have been touched"
        assert not _send_mail.find_word('emma'), \
            "emma should not have been mailed"
        self.account.clear()
        self.account.find_by_name('emma')
        assert self.notifier.get_num_notifications(self.account) == 0, \
                "david should have his trait removed"
        assert not _send_mail.find_word('david'), \
            "david should not have been mailed"
        self.account.clear()
        self.account.find_by_name('frank')
        q = self.account.get_entity_quarantine(c.quarantine_autopassord)
        assert q, "frank should be splatted"
        assert not _send_mail.find_word('frank'), \
            "frank should not have been mailed"

    def test_process_accounts_fail(self):
        """
        Process the accounts, but now make sendmail fail
        """
        import Cerebrum.modules.password_notifier.notifier as pn
        pn._send_mail.returnvalue = False
        self.notifier.process_accounts()
        self.account.clear()
        self.account.find_by_name('alice')
        q = self.account.get_entity_quarantine(c.quarantine_autopassord)
        assert q, "alice should be splatted"
        self.account.clear()
        self.account.find_by_name('bob')
        assert self.notifier.get_num_notifications(self.account) == 0, \
                "bob should not have been touched"
        self.account.clear()
        self.account.find_by_name('charlie')
        assert self.notifier.get_num_notifications(self.account) == 1, \
                "charlie should not have been touched"
        self.account.clear()
        self.account.find_by_name('emma')
        assert self.notifier.get_num_notifications(self.account) == 0, \
                "emma should not have been touched"
        self.account.clear()
        self.account.find_by_name('david')
        assert self.notifier.get_num_notifications(self.account) == 0, \
                "david should have his trait removed"
        self.account.clear()
        self.account.find_by_name('frank')
        q = self.account.get_entity_quarantine(c.quarantine_autopassord)
        assert q, "frank should be splatted"

    def test_except_user(self):
        """
        Users with the excepted trait should be excepted
        We set the trait on a couple of users, and then
        assert that except_user returns true for exactly
        these accounts.
        """
        for i in ('emma', 'david'):
            self.account.clear()
            self.account.find_by_name(i)
            self.account.populate_trait(c.trait_passwordnotifier_excepted)
            self.account.write_db()
        for u, v in users.items():
            ex = u in ('emma', 'david')
            self.account.clear()
            self.account.find_by_name(u)
            ans = self.notifier.except_user(self.account)
            if ex:
                assert ans, "Wrongly not excepted: %s" % u
            else:
                assert not ans, "Wrongly excepted: %s -- %s" % (u, ans)

    def test_notify(self):
        """
        Notify the user
        """
        for u in users.keys():
            self.account.clear()
            self.account.find_by_name(u)
            assert self.notifier.notify(self.account), \
                    "Could not mail " + u
            # TODO: check the mail sent

