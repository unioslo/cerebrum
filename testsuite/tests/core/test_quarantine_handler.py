# encoding: utf-8
"""
Unit tests for :mod:`Cerebrum.QuarantineHandler`.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime

import pytest

from Cerebrum import Account
from Cerebrum import QuarantineHandler
from Cerebrum.testutils import datasource

QUARANTINE_NOLOGIN = "q_d50ecaee"
QUARANTINE_SYSTEM = "q_9ada9ec4"
SPREAD_AD = "s_f3038466"


@pytest.fixture
def q_nologin(constant_module, constant_creator):
    return constant_creator(constant_module._QuarantineCode,
                            QUARANTINE_NOLOGIN)


@pytest.fixture
def q_system(constant_module, constant_creator):
    return constant_creator(constant_module._QuarantineCode, QUARANTINE_SYSTEM)


@pytest.fixture
def spread_ad(constant_module, constant_creator):
    return constant_creator(constant_module._SpreadCode, SPREAD_AD,
                            constant_module.CoreConstants.entity_account)


@pytest.fixture(autouse=True)
def _patch_cereconf(cereconf, q_nologin, q_system, spread_ad):
    # Quarantine rules for tests
    cereconf.QUARANTINE_RULES = {
        QUARANTINE_NOLOGIN: {
            'lock': 1,
            'shell': 'nologin-shell',
            'sort_num': 10,
        },
        QUARANTINE_SYSTEM: [
            {
                'lock': 1,
                'shell': 'nologin-shell2',
                'sort_num': 2,
            },
            {
                'spread': SPREAD_AD,
                'shell': 'ad-shell',
                'sort_num': 3,
            },
        ],
    }


@pytest.fixture(autouse=True)
def _patch_quarantinehandler(const):
    # We need to explicitly reset the QuarantineHandler class attributes.
    # These *really* shouldn't be class attribtues, as the values may change
    # across two transactions (allthough they never actaully do)
    QuarantineHandler.QuarantineHandler.qc2rules = {}
    QuarantineHandler.QuarantineHandler._explicit_sort = False


def test_simple_policy(database, const, q_nologin):
    quarantines = (int(q_nologin),)
    qh = QuarantineHandler.QuarantineHandler(database, quarantines)
    assert qh.is_locked()
    assert qh.get_shell() == "nologin-shell"


def test_policy_list(database, const, q_system):
    quarantines = (int(q_system),)
    qh = QuarantineHandler.QuarantineHandler(database, quarantines)
    assert qh.is_locked()
    assert qh.get_shell() == "nologin-shell2"


def test_policy_spread_select(database, q_system, spread_ad):
    quarantines = (int(q_system),)
    spreads = (int(spread_ad),)
    qh = QuarantineHandler.QuarantineHandler(database, quarantines,
                                             spreads=spreads)
    assert not qh.is_locked()
    assert qh.get_shell() == "ad-shell"


def test_policy_spread_select_combined(database, q_system, q_nologin,
                                       spread_ad):
    # User has *both* nologin and system quarantines
    quarantines = (q_system, q_nologin)
    spreads = (spread_ad,)
    qh = QuarantineHandler.QuarantineHandler(database, quarantines,
                                             spreads=spreads)
    assert qh.is_locked()
    assert qh.get_shell() == "ad-shell"


@pytest.fixture
def account(database, const, initial_account, initial_group, q_nologin):
    """ A simple account for tests. """
    account_ds = datasource.BasicAccountSource()
    account_dict = next(account_ds(limit=1))
    account = Account.Account(database)
    account.populate(
        account_dict['account_name'],
        initial_group.entity_type,
        initial_group.entity_id,
        const.account_program,
        initial_account.entity_id,
        account_dict.get('expire_date'),
    )
    account.write_db()
    return account


def test_check_quarantine_miss(database, account):
    # initialize QuarantineHandler from entity
    qh = QuarantineHandler.QuarantineHandler.check_entity_quarantines(
        database, account.entity_id,
    )
    assert not qh.is_locked()


def test_check_quarantine_hit(database, initial_account, account, q_nologin):
    account.add_entity_quarantine(
        qtype=q_nologin,
        creator=initial_account.entity_id,
        description="test quarantine",
        start=(datetime.date.today() - datetime.timedelta(days=30)),
    )

    # initialize QuarantineHandler from entity
    qh = QuarantineHandler.QuarantineHandler.check_entity_quarantines(
        database, account.entity_id,
    )
    assert qh.is_locked()
    assert qh.get_shell() == "nologin-shell"
