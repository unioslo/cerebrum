# -*- coding: utf-8 -*-
""" Tests for :mod:`Cerebrum.modules.pwcheck.history`.  """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime

import pytest

from Cerebrum import Account
from Cerebrum.auth import all_auth_methods
from Cerebrum.modules.pwcheck import history
from Cerebrum.testutils import datasource


class PasswordHistoryAccount(history.PasswordHistoryMixin, Account.Account):
    """ Account with password history. """
    # TODO: PasswordHistoryMixin should probably just inherit Account.Account
    # to begin with.
    pass


@pytest.fixture(autouse=True)
def _patch_cereconf(cereconf):
    """
    Patch cereconf.AUTH_CRYPT_METHODS

    Make sure AUTH_CRYPT_METHODS only only contains auth methods supported by
    Cerebrum.Account.Account
    """
    cereconf.AUTH_CRYPT_METHODS = list(all_auth_methods)


@pytest.fixture
def account_ds():
    return datasource.BasicAccountSource()


@pytest.fixture
def account_creator(database, const, account_ds, initial_account):
    creator_id = initial_account.entity_id

    def _create_accounts(owner, limit=1):
        owner_id = owner.entity_id
        owner_type = owner.entity_type

        for account_dict in account_ds(limit=limit):

            account = PasswordHistoryAccount(database)
            if owner_type == const.entity_person:
                account_type = None
            else:
                account_type = const.account_program

            account.populate(account_dict['account_name'],
                             owner_type,
                             owner_id,
                             account_type,
                             creator_id,
                             account_dict.get('expire_date'))
            account.write_db()
            account_dict['entity_id'] = account.entity_id
            yield account, account_dict

    return _create_accounts


@pytest.fixture
def account(account_creator, initial_group):
    account, _ = next(account_creator(initial_group, limit=1))
    return account


@pytest.fixture
def pw_history(database):
    return history.PasswordHistory(database)


#
# Encode / match tests
#


class Signature(object):
    """ example password history entry. """
    name = "foo"  # not really relevant
    password = "bar"
    value = (
        "pbkdf2_sha512"
        "$100"
        "$Vapay9M60k/oUlLU7j2DrLaKYEHav5F0U6AwwwxWfr4="
        "$07ObgqcPnCNgQbuscZE+4nNsEL6300eSTpmXPLyYEGs="
    )

    @property
    def encode_args(self):
        return {
            "algo": "sha512",
            "rounds": 100,
            "salt": (
                b"U\xaaZ\xcb\xd3:\xd2O\xe8RR\xd4\xee=\x83\xac"
                b"\xb6\x8a`A\xda\xbf\x91tS\xa00\xc3\x0cV~\xbe"
            ),
            "password": self.password,
            "keylen": 32,
        }


class LegacySignature(object):
    """ example legacy password history entry. """
    name = "foo"  # not really relevant
    password = "bar"
    value = "OFj2IjCsPJFfMAxmQxLGPw"

    @property
    def encode_args(self):
        return {
            "name": self.name,
            "password": self.password,
        }


def test_old_encode_for_history():
    """ Test the legacy password signature function. """
    kwargs = LegacySignature().encode_args
    expect = LegacySignature.value
    assert history.old_encode_for_history(**kwargs) == expect


def test_encode_for_history():
    """ Test the password signature function. """
    kwargs = Signature().encode_args
    assert history.encode_for_history(**kwargs) == Signature.value


def test_check_password_history_hit():
    assert history.check_password_history(
        Signature.password,
        [Signature.value],
        Signature.name,
    )


def test_check_password_history_legacy_hit():
    assert history.check_password_history(
        LegacySignature.password,
        [LegacySignature.value],
        LegacySignature.name,
    )


def test_check_password_history_miss():
    assert not history.check_password_history(
        "this-is-not-a-matching-password",
        [Signature.value],
        Signature.name,
    )


def test_check_password_history_legacy_miss():
    assert not history.check_password_history(
        "this-is-not-a-matching-password",
        [LegacySignature.value],
        LegacySignature.name,
    )


def test_check_passwords_history_hit():
    assert history.check_passwords_history(
        [Signature.password],
        [Signature.value],
        Signature.name,
    )


def test_check_passwords_history_legacy_hit():
    assert history.check_passwords_history(
        [LegacySignature.password],
        [LegacySignature.value],
        LegacySignature.name,
    )


def test_check_passwords_history_miss():
    assert not history.check_passwords_history(
        ["this-is-not-a-matching-password"],
        [Signature.value],
        Signature.name,
    )


def test_check_passwords_history_legacy_miss():
    assert not history.check_passwords_history(
        ["this-is-not-a-matching-password"],
        [LegacySignature.value],
        LegacySignature.name,
    )


#
# PasswordHistory tests
#
# TODO: Some of this gets used by the PasswordHistoryMixin tests, but we should
# write explicit tests for each method here as well.
#

def test_add_history(pw_history, account):
    pw_history.add_history(account, example_passwd)
    rows = list(pw_history.get_history(int(account.entity_id)))
    assert len(rows) == 1


def test_del_history(pw_history, account):
    pw_history.add_history(account, example_passwd)
    pw_history.del_history(int(account.entity_id))
    rows = list(pw_history.get_history(int(account.entity_id)))
    assert not rows


def test_get_history(pw_history, account):
    pw_history.add_history(account, example_passwd)
    rows = list(pw_history.get_history(int(account.entity_id)))
    assert len(rows) == 1
    row = rows[0]
    assert row['set_at']
    assert row['hash']


def test_get_most_recent_set_at(pw_history, account):
    """ check that we get the most recently set entry set_at value. """
    # Add two history entries with explicit set_at times
    new_when = datetime.datetime(2024, 7, 19, 15, 30)
    pw_history.add_history(account, "not-relevant", _when=new_when)
    old_when = datetime.datetime(2024, 7, 19, 15, 00)
    pw_history.add_history(account, "not-relevant", _when=old_when)

    result = pw_history.get_most_recent_set_at(int(account.entity_id))
    assert result == new_when


#
# PasswordHistoryMixin tests
#


example_passwd = "Password1"
similar_passwd = "Password2"
another_passwd = "This-is-not-the-same-password-at-all"


def test_assert_history_written(pw_history, account):
    """ Setting an initial password should add password history. """
    account.set_password(example_passwd)
    account.write_db()
    assert list(pw_history.get_history(int(account.entity_id)))


def test_delete_account(pw_history, account):
    """ Deleting an account should delete password history. """
    account.set_password(example_passwd)
    account.write_db()
    entity_id = int(account.entity_id)
    account.delete()
    assert not list(pw_history.get_history(entity_id))


def test_check_password_history(account):
    account.set_password(example_passwd)
    account.write_db()
    assert account._check_password_history(example_passwd)
    assert not account._check_password_history(similar_passwd)
    assert not account._check_password_history(another_passwd)


def test_check_similar_password_history(account):
    account.set_password(example_passwd)
    account.write_db()
    assert account._bruteforce_check_password_history(example_passwd)
    assert account._bruteforce_check_password_history(similar_passwd)
    assert not account._bruteforce_check_password_history(another_passwd)


def test_clear_password(account):
    """ Assert no attributes contains plaintext password after clear(). """
    account.set_password(example_passwd)
    account.clear()
    attrs = list(k for k, v in sorted(account.__dict__.items())
                 if v == example_passwd)
    assert not attrs


def test_write_clear_password(account):
    """ Assert no attributes contains plaintext password after write_db(). """
    account.set_password(example_passwd)
    account.write_db()
    attrs = list(k for k, v in sorted(account.__dict__.items())
                 if v == example_passwd)
    assert not attrs


def test_delete_clear_password(account):
    """ Assert no attributes contains plaintext password after delete(). """
    account.set_password(example_passwd)
    account.delete()
    attrs = list(k for k, v in sorted(account.__dict__.items())
                 if v == example_passwd)
    assert not attrs
