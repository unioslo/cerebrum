#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Basic tests for Cerebrum/Account.py."""
from __future__ import unicode_literals

import pytest

import datasource  # testsuite/testtools/

from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum import Person

person_cls = Person.Person
account_cls = Account.Account


def _set_of_ids(account_dicts):
    return set(int(a.get('entity_id', a.get('account_id')))
               for a in account_dicts)


@pytest.fixture
def account_object(database):
    """ Returns instantiated Cerebrum.Account object. """
    return account_cls(database)


@pytest.fixture
def account_ds():
    return datasource.BasicAccountSource()


@pytest.fixture
def person_creator(database, const):
    person_ds = datasource.BasicPersonSource()

    def _create_persons(limit=1):
        for person_dict in person_ds(limit=limit):
            person = person_cls(database)
            gender = person_dict.get('gender')
            if gender:
                gender = const.human2constant(gender, const.Gender)
            gender = gender or const.gender_unknown

            person.populate(person_dict['birth_date'],
                            gender,
                            person_dict.get('description'))
            person.write_db()
            person_dict['entity_id'] = person.entity_id
            yield person, person_dict

    return _create_persons


@pytest.fixture
def account_creator(database, const, account_ds, initial_account):
    creator_id = initial_account.entity_id

    def _create_accounts(owner, limit=1):
        owner_id = owner.entity_id
        owner_type = owner.entity_type

        for account_dict in account_ds(limit=limit):

            account = account_cls(database)
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
            if account_dict.get('password'):
                account.set_password(account_dict.get('password'))
            account.write_db()
            account_dict['entity_id'] = account.entity_id
            yield account, account_dict

    return _create_accounts


@pytest.fixture
def person(person_creator):
    person, _ = next(person_creator(limit=1))
    return person


@pytest.fixture
def account_dict(account_creator, initial_group):
    _, account_dict = next(account_creator(initial_group, limit=1))
    return account_dict


@pytest.fixture
def personal_accounts(account_creator, person):
    """ list of dicts with existing personal account data. """
    accounts = []
    for _, account_dict in account_creator(person, limit=5):
        accounts.append(account_dict)
    return accounts


@pytest.fixture
def np_accounts(account_creator, initial_group):
    """ list of dicts with existing non-personal account data. """
    accounts = []
    for _, account_dict in account_creator(initial_group, limit=5):
        accounts.append(account_dict)
    return accounts


def test_populate_personal(const, account_creator, person):
    account, account_dict = next(account_creator(person, limit=1))

    assert hasattr(account, 'entity_id')
    assert account.account_name == account_dict['account_name']
    assert account.np_type is None


def test_populate_np(const, account_creator, initial_group):
    account, account_dict = next(account_creator(initial_group, limit=1))

    assert hasattr(account, 'entity_id')
    assert isinstance(account.np_type, const.Account)
    assert account.account_name == account_dict['account_name']


def test_find(account_object, account_dict):
    account_id = account_dict['entity_id']
    account_object.find(account_id)
    assert account_object.entity_id == account_id


def test_find_not_found(account_object):
    # negative ids should be impossible in Cerebrum
    with pytest.raises(Errors.NotFoundError):
        account_object.find(-10)


def test_find_by_name(account_object, account_dict):
    account_id = account_dict['entity_id']
    account_name = account_dict['account_name']
    account_object.find_by_name(account_name)
    assert account_object.entity_id == account_id


def test_find_by_name_not_found(account_object):
    # entity_name is a varchar(256), no group with longer name should exist
    account_name = 'n' * (256 + 1)
    with pytest.raises(Errors.NotFoundError):
        assert account_object.find_by_name(account_name)


def test_is_expired(account_object, np_accounts):
    """ Account.is_expired() for expired and non-expired accounts. """
    account_ids = _set_of_ids(np_accounts)
    non_expired = _set_of_ids(
        filter(datasource.nonexpired_filter, np_accounts))

    # We must have at least one expired and one non-expired account
    # TODO: should we skip if test setup fails here? should we throw error?
    assert len(non_expired) > 0 and len(non_expired) < len(account_ids)

    for account_id in account_ids:
        account_object.clear()
        account_object.find(account_id)
        if int(account_id) in non_expired:
            assert account_object.is_expired() is False
        else:
            assert account_object.is_expired() is True


def test_search_owner(account_object, personal_accounts, person):
    """ Account.search() with owner_id argument. """
    account_ids = _set_of_ids(personal_accounts)
    owner_id = person.entity_id

    assert len(account_ids) >= 1

    results = [dict(r)
               for r in account_object.search(owner_id=owner_id,
                                              expire_start=None)]
    result_ids = _set_of_ids(results)

    # the person fixture should not own any other accounts:
    assert account_ids == result_ids

    # We should not get any results with another owner
    for result in results:
        assert int(result['owner_id']) == person.entity_id
        assert int(result['owner_type']) == person.entity_type


def test_search_owner_sequence(account_object, person_creator,
                               account_creator):
    # todo: heavier setup -- should maybe make fixtures
    p1, p2 = list(p for p, _ in person_creator(limit=2))
    p1_account_ids = [d['entity_id'] for a, d in account_creator(p1, limit=2)]
    p2_account_ids = [d['entity_id'] for a, d in account_creator(p2, limit=2)]
    account_ids = p1_account_ids + p2_account_ids

    assert len(account_ids) == 4

    for seq_type in (set, list, tuple):
        sequence = seq_type((p1.entity_id, p2.entity_id))
        results = [dict(r) for r in account_object.search(owner_id=sequence,
                                                          expire_start=None)]
        result_ids = _set_of_ids(results)

        assert len(results) == len(account_ids)
        assert set(result_ids) == set(account_ids)

        for result in results:
            assert int(result['owner_id']) in sequence


def test_search_filter_expired(account_object, personal_accounts, person):
    """ Account.is_expired() for expired and non-expired accounts. """
    account_ids = _set_of_ids(personal_accounts)
    non_expired = _set_of_ids(
        filter(datasource.nonexpired_filter, personal_accounts))
    expired = account_ids - non_expired

    # Test criterias
    assert len(non_expired) >= 1
    assert len(expired) >= 1

    owner_id = person.entity_id

    want_all = [dict(r)
                for r in account_object.search(owner_id=owner_id,
                                               expire_start=None,
                                               expire_stop=None)]

    assert _set_of_ids(want_all) == account_ids

    want_non_expired = [dict(r)
                        for r in account_object.search(owner_id=owner_id,
                                                       expire_start='[:now]',
                                                       expire_stop=None)]

    assert _set_of_ids(want_non_expired) == non_expired

    want_expired = [dict(r)
                    for r in account_object.search(owner_id=owner_id,
                                                   expire_start=None,
                                                   expire_stop='[:now]')]

    assert _set_of_ids(want_expired) == expired


def test_search_name_wildcard(account_object, np_accounts, account_ds):
    """ Account.search() for name. """
    search_expr = account_ds.name_prefix + '%'
    result = [dict(r) for r in account_object.search(name=search_expr,
                                                     expire_start=None)]
    assert len(result) == len(np_accounts)
    assert _set_of_ids(result) == _set_of_ids(np_accounts)


def test_equality(database, np_accounts):
    """ Account __eq__ comparison. """
    assert len(np_accounts) >= 2
    # we don't care which is a1 and which is a2, we just need to make sure we
    # have to different valid account_ids
    a1, a2 = _set_of_ids(np_accounts[0:2])

    ac1, ac2, ac3 = [account_cls(database) for _ in range(3)]
    ac1.find(a1)
    ac2.find(a2)
    ac3.find(a1)
    assert ac1 == ac3
    assert ac1 != ac2
    assert ac2 != ac3


def test_verify_auth(account_object, np_accounts):
    has_passwd = [a for a in np_accounts if a.get('password')]
    assert len(has_passwd) > 1

    # Password should have been set when created
    for account in has_passwd:
        account_object.clear()
        account_object.find(account['entity_id'])
        assert account_object.verify_auth(account['password']) is True
        assert account_object.verify_auth(account['password'] + 'x') == []


def test_set_password(account_object, account_dict):
    """ Account.set_password(). """
    account_id = account_dict['entity_id']
    password = 'my new supersecret password'

    # set password
    account_object.find(account_id)
    account_object.set_password(password)
    account_object.write_db()
    account_object.clear()

    # verify password
    account_object.find(account_id)
    assert account_object.verify_auth(password) is True


# built in auth types with implementations
auth_types = [
    'MD4-NT',
    'MD5-crypt',
    'SHA-256-crypt',
    'SHA-512-crypt',
    'SSHA',
    'md5-unsalted',
    'plaintext',
]


@pytest.mark.parametrize('auth_type', auth_types)
def test_encrypt_verify_methods(const, account_object, auth_type):
    correct_passwd = 'ex-mpLe-p4~~'
    wrong_passwd = 'ex-mpLe-p5~~'
    method = const.human2constant(auth_type, const.Authentication)

    # We add the salt to the password, just to get a different
    # password from the unsalted test
    cryptstring = account_object.encrypt_password(method, correct_passwd)

    assert account_object.verify_password(method, correct_passwd,
                                          cryptstring)
    assert not account_object.verify_password(method, wrong_passwd,
                                              cryptstring)


def test_populate_affect_auth(const, account_object, account_dict):
    """ Account.populate_auth_type() and Account.affect_auth_types. """
    # populate_auth_type and affect_auth_types will always be used in
    # conjunction, and is not possible to test independently without
    # digging into the Account class implementation.
    account_id = account_dict['entity_id']

    # Tuples of (auth_method, cryptstring, try_to_affect)
    tests = [(const.auth_type_sha256_crypt, 'crypt-resgcsgq', False),
             (const.auth_type_sha512_crypt, 'crypt-juoxpixs', True)]
    # This should change the sha-512 crypt, but not the sha-256 crypt:

    account_object.find(account_id)

    # Populate both of the auth methods given in tests
    for method, crypt, _ in tests:
        account_object.populate_authentication_type(method, crypt)

    # Only affect selected auth methods
    affect = [method for method, _, do_affect in tests if do_affect]
    account_object.affect_auth_types(*affect)
    account_object.write_db()

    # Check that only affected auth method crypts were altered
    for method, new_crypt, do_affect in tests:
        try:
            crypt = account_object.get_account_authentication(method)
        except Errors.NotFoundError:
            # The non-affected methods may not exist in the db, but the
            # affected method MUST exist
            assert do_affect is False
        else:
            # The method exists in the database...
            if do_affect:
                # ...and is an affected method - the crypt must match
                # the one we set
                assert crypt == new_crypt
            else:
                # ...and is not an affected method - the crypt SHOULD
                # NOT match the one we set.
                assert crypt != new_crypt
