#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Tests for the rest.database.DatabaseContext. """


def test_query(app_ctx, db_ctx):
    rows = db_ctx.connection.query("SELECT 'foo' as value")
    assert len(rows) == 1
    assert 'value' in rows[0].keys()
    assert rows[0]['value'] == 'foo'
