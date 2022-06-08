# -*- coding: utf-8 -*-
# Copyright 2021 University of Oslo, Norway
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
Database record wrapper.

This module implements the database row factory, and controls the row data
structure returned by database queries.

Database rows
-------------
A database row is an object that behaves similarly to a named tuple.  Common
traits (and required traits for Cerebrum code) are:

- Column values can be looked up with ``__getitem__`` (e.g. ``row['mycol']``).
- A row can be converted to a ``dict``: ``rowlike = dict(row)``
- Otherwise acts as a tuple: ``myval in row``, ``tuple(row)``.

For as long as Cerebrum has been around, py:class:`Cerebrum.extlib.db_row.row`
has been used as row object, and py:class:`._DbRowIterator` has been used as a
row iterator.

However, as the module has remained largely unchanged (unmaintained?) upstream,
it is not Python 3 compatible.  The third party module ``records``, and more
specifically its row and iterator implementations
(py:class:`Cerebrum.extlib.records.Record`,
py:class:`Cerebrum.extlib.records.RecordCollection`) has been chosen as
replacements.

Configuration
-------------
The behaviour of this module changes with the environment variable
``CEREBRUM_RECORDS``:

- If set to ``CEREBRUM_RECORDS=0`` or unset, this module will use
  legacy py:mod:`Cerebrum.extlib.db_row` objects.
- If set to ``CEREBRUM_RECORDS=1``, this module will use
  the new py:mod:`Cerebrum.extlib.records` objects.
"""
import os
from Cerebrum.extlib import records


# Cerebrum.extlib.records feature toggle.
# If CEREBRUM_RECORDS is set, we change from db_row to records
# TODO: Remove feature toggle when records is in use everywhere
ENABLE_RECORDS = bool(int(os.environ.get('CEREBRUM_RECORDS') or 0))


# ROW_TYPES for Database.pythonify_data
# TODO: Does this work with records?!
if ENABLE_RECORDS:
    ROW_TYPES = (records.Record,)

    def make_row_class(*args, **kwargs):
        raise NotImplementedError('db_row disabled')

else:
    # PY3: db_row is not importable
    from Cerebrum.extlib import db_row
    make_row_class = db_row.make_row_class
    ROW_TYPES = (db_row.abstract_row,)


class _DbRowIterator(object):
    """
    Legacy row iterator for db_row.

    This is the old ``Cerebrum.Database.RowIterator`` implemented for use with
    ``db_row``, with one change:  The ``row_class`` must be given on init,
    rather than letting the *cursor* build a row object (``Cursor.wrap_row()``
    has been removed).
    """

    def __init__(self, cursor, row_class):
        self._csr = cursor
        self._row_class = row_class
        self._queue = []

    def __iter__(self):
        return self

    def next(self):
        if not self._queue:
            self._queue.extend(self._csr.fetchmany())
        if not self._queue:
            raise StopIteration
        row = self._queue.pop(0)
        return self._row_class(row)


def _resultiter(cursor, size=None):
    """A simple iterator that fetches rows in groups of *size*."""
    if size is None:
        size = cursor.arraysize
    while True:
        results = cursor.fetchmany(size)
        if not results:
            break
        for result in results:
            yield result


def iter_rows(cursor, fields):
    """ Iterate over cursor results.

    Return value for ``Database.query(..., fetchall=False)``.  This function
    returns an iterator over the current cursor results.  Each result is a *row
    object*.

    :type cursor: Cerebrum.database.Cursor
    :type fields: tuple

    :returns:
        Returns an iterator over cursor results.

        The object type depends on module config, but is one of:

        - py:class:`._DbRowIterator`
        - py:class:`Cerebrum.extlib.records.RecordCollection`
    """
    if ENABLE_RECORDS:
        data = _resultiter(cursor)
        row_gen = (records.Record(fields, row) for row in data)
        return records.RecordCollection(row_gen)
    else:
        row_class = make_row_class(fields)
        return _DbRowIterator(cursor, row_class)


def list_rows(cursor, fields):
    """ Return all cursor results.

    Return value for ``Database.query(..., fetchall=True)``.  This function
    returns a list of rows for the current cursor results.  Each result is a
    *row object*.

    :type cursor: Cerebrum.database.Cursor
    :type fields: tuple

    :rtype: list
    :returns:
        Returns a list of cursor results.

        List item type depends on module config, and is one of:

        - py:class:`Cerebrum.extlib.db_row.row`
        - py:class:`Cerebrum.extlib.records.Record`
    """
    data = cursor.fetchall()
    if ENABLE_RECORDS:
        row_gen = (records.Record(fields, row) for row in data)
        return records.RecordCollection(row_gen).all()
    else:
        row_class = make_row_class(fields)
        return [row_class(r) for r in data]
