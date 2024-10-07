# -*- coding: utf-8 -*-
"""
Tests for :mod:`Cerebrum.database.ctx`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import pytest

from Cerebrum.database import ctx


class _MockDatabase(object):

    def __init__(self):
        self.did_rollback = 0
        self.did_commit = 0

    def driver_connection(self):
        return None

    def rollback(self):
        self.did_rollback += 1

    def commit(self):
        self.did_commit += 1


@pytest.fixture
def db():
    return _MockDatabase()


def test_ctx_dryrun(db):
    with ctx.db_context(db, dryrun=True):
        pass

    assert db.did_rollback == 1
    assert db.did_commit == 0


def test_ctx_no_dryrun(db):
    with ctx.db_context(db, dryrun=False):
        pass

    assert db.did_rollback == 0
    assert db.did_commit == 1


def test_ctx_error(db):
    with pytest.raises(ValueError):
        with ctx.db_context(db, dryrun=False):
            raise ValueError("test")

    assert db.did_rollback == 1
    assert db.did_commit == 0
