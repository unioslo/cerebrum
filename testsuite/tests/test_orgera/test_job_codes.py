# -*- encoding: utf-8 -*-
""" Tests for the ORG-ERA job codes (Cerebrum.modules.no.orgera.job_codes) """
import pytest

from Cerebrum.modules.no.orgera import job_codes


example_sko = (1, 'sko-1')


def test_insert_sko(database):
    res_t = job_codes.assert_sko(database, *example_sko)
    assert res_t == example_sko


@pytest.fixture
def sko_t(database):
    return tuple(job_codes.assert_sko(database, *example_sko))


def test_get_sko(database, sko_t):
    code, desc = sko_t
    res_t = job_codes.get_sko(database, code)
    assert res_t == (code, desc)


def test_update_sko(database, sko_t):
    code, _ = sko_t
    desc = 'a different description'
    res_t = job_codes.assert_sko(database, code, desc)
    assert res_t == (code, desc)


def test_list_sko(database, sko_t):
    all_sko = [tuple(r) for r in job_codes.list_sko(database)]
    assert sko_t in all_sko


example_styrk = (1, 'styrk-1')


def test_insert_styrk(database, sko_t):
    res_t = job_codes.assert_styrk(database, *example_styrk)
    assert len(res_t) == 2
    assert res_t == example_styrk


@pytest.fixture
def styrk_t(database, sko_t):
    return tuple(job_codes.assert_styrk(database, *example_styrk))


def test_get_styrk(database, styrk_t):
    styrk, styrk_desc = styrk_t
    res_t = job_codes.get_styrk(database, styrk)
    assert res_t == styrk_t


def test_update_styrk(database, styrk_t):
    styrk, _ = styrk_t
    desc = 'a different description'
    res_t = job_codes.assert_styrk(database, styrk, desc)
    assert res_t == (styrk, desc)


def test_list_styrk(database, styrk_t):
    all_styrk = [tuple(r) for r in job_codes.list_styrk(database)]
    assert styrk_t in all_styrk
