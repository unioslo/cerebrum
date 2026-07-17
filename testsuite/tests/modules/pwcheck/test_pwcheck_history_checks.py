# -*- coding: utf-8 -*-
""" Tests for :mod:`Cerebrum.modules.pwcheck.history_checks`.  """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

from Cerebrum.modules.pwcheck import history_checks

# We mock away:
#   1. Account.verify_auth() - this should be tested by account tests
#   2. PasswordHistoryMixin._[bruteforce_]check_password_history - this is
#      tested in test_pwcheck_history


class MockAccount(object):
    """ A mock account with a name and a password history. """

    def __init__(self, name, history):
        self.name = name
        self.history = list(history) if history else []

    @property
    def password(self):
        return self.history[0] if self.history else None

    def verify_auth(self, password):
        return password == self.password

    def _check_password_history(self, password):
        return password in self.history

    def _bruteforce_check_password_history(self, password):
        # brute-force is an implementation detail - this is tested elsewhere
        return password in self.history


PASSWORD_CURRENT = "hunter2"
PASSWORD_HISTORY = ["password123", "123456"]
PASSWORD_UNKNOWN = "another-password"


@pytest.fixture
def account():
    return MockAccount("foo", [PASSWORD_CURRENT] + PASSWORD_HISTORY)


#
# CurrentPassword tests
#


@pytest.fixture
def check_current():
    return history_checks.CurrentPassword()


@pytest.mark.parametrize("password", PASSWORD_HISTORY + [PASSWORD_UNKNOWN])
def test_check_current_valid(check_current, account, password):
    assert not check_current.check_password(password, account=account)


def test_check_current_invalid(check_current, account):
    assert check_current.check_password(account.password, account=account)


#
# [Brute]CheckPasswordHistory tests
#


@pytest.fixture(params=[history_checks.CheckPasswordHistory,
                        history_checks.BruteCheckPasswordHistory],
                ids=["history", "brute"])
def check_history(request):
    return request.param()


def test_check_history_no_account(check_history):
    assert not check_history.check_password("")


def test_check_history_no_support(check_history):
    assert not check_history.check_password("", account=object())


def test_check_history_valid(check_history, account):
    assert not check_history.check_password(PASSWORD_UNKNOWN,
                                            account=account)


@pytest.mark.parametrize("password", [PASSWORD_CURRENT] + PASSWORD_HISTORY)
def test_check_history_invalid(check_history, password, account):
    assert check_history.check_password(password, account=account)
