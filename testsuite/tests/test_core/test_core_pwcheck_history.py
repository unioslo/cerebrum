#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Tests for Cerebrum.modules.pwcheck.history.
"""
from __future__ import unicode_literals

from nose.tools import with_setup
from nose.plugins.skip import SkipTest

from Cerebrum.Utils import Factory
from Cerebrum.modules.pwcheck.history import PasswordHistoryMixin
from Cerebrum.modules.pwcheck.history import PasswordHistory
from Cerebrum.modules.pwcheck.checker import PasswordNotGoodEnough

# Cerebrum-specific test modules
from datasource import BasicAccountSource
from dbtools import DatabaseTools

# Global cererbum objects
db = None
ac = None
co = None

# Group datasource generator
account_ds = None

# Database tools to do common tasks
db_tools = None

# accounts
accounts = None


def setup_module():
    global db, ac, co, account_ds, db_tools
    db = Factory.get('Database')()
    db.cl_init(change_program='nosetests')
    db.commit = db.rollback

    account_class = Factory.get('Account')
    if PasswordHistoryMixin not in account_class.mro():
        raise SkipTest("No PasswordHistory configured, skipping module.")

    ac = account_class(db)
    co = Factory.get('Constants')(db)

    # Data sources
    account_ds = BasicAccountSource()

    # Tools for creating and destroying temporary db items
    db_tools = DatabaseTools(db)
    db_tools._ac = ac


def teardown_module():
    db_tools.clear_groups()
    db_tools.clear_accounts()
    db_tools.clear_persons()
    db_tools.clear_constants()
    db_tools.clear_ous()
    db.rollback()


def create_accounts(num=5):
    """ Create a set of groups to use in a test.

    See C{groups} in this file for format.

    """
    def wrapper():
        global accounts
        accounts = []
        for entry in account_ds(limit=num):
            entity_id = db_tools.create_account(entry)
            entry['entity_id'] = entity_id
            accounts.append(entry)
        for entry in accounts:
            assert entry['entity_id'] is not None
    return wrapper


def remove_accounts():
    """ Remove all groups.

    Complementary function/cleanup code for C{create_groups}.

    """
    def wrapper():
        global accounts
        for entry in accounts:
            db_tools.delete_account_id(entry['entity_id'])
        accounts = None
    return wrapper


def get_next_account():
    for entry in accounts:
        ac.clear()
        ac.find(entry['entity_id'])
        yield ac


password = '9aa56fa04cbfa6ddde4bcdb31ef72ab17ef3f3bd91385bddd55ebe6d3d68'


@with_setup(create_accounts(num=1), remove_accounts())
def test_assert_history_written():
    ph = PasswordHistory(db)
    for acc in get_next_account():
        for row in ph.get_history(acc.entity_id):
            return
    raise Exception("Did not find password history")


# TODO: Fix this test -- neither set_password() or write_db() actually performs
#       password checks, nor should they
# @with_setup(create_accounts(num=1), remove_accounts())
# def test_set_password_twice():
#     for acc in get_next_account():
#         try:
#             acc.set_password(password)
#             acc.write_db()
#         except PasswordNotGoodEnough:
#             return
#     assert False, "Could re-use password!"


@with_setup(create_accounts(num=1), remove_accounts())
def test_delete_account():
    ph = PasswordHistory(db)
    entity_id = None
    for acc in get_next_account():
        entity_id = acc.entity_id
        acc.delete()
        break
    for row in ph.get_history(entity_id):
        assert False, "Got password history for deleted e_id %s" % entity_id


@with_setup(create_accounts(num=1), remove_accounts())
def test_clear_password():
    for acc in get_next_account():
        acc.set_password(password)
        acc.clear()
    for k, v in acc.__dict__.iteritems():
        assert password != v, "Got plaintext in attr %r" % k


@with_setup(create_accounts(num=1), remove_accounts())
def test_write_clear_password():
    for acc in get_next_account():
        acc.set_password(password)
        acc.write_db()
    for k, v in acc.__dict__.iteritems():
        assert password != v, "Got plaintext in attr %r" % k


@with_setup(create_accounts(num=1), remove_accounts())
def test_delete_clear_password():
    for acc in get_next_account():
        acc.set_password(password)
        acc.delete()
    for k, v in acc.__dict__.iteritems():
        assert password != v, "Got plaintext in attr %r" % k
