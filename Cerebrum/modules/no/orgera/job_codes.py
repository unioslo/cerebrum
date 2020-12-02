# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
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
This module provides access to employee role identifiers used in ORG-ERA.

There are currently two identifier types in use:

py:class:`Sko`
    Job code (stillingskode)

py:class:`Styrk`
    Occupation code (yrkeskode).  These codes always belongs to a SKO.
"""
import logging

import six

from Cerebrum import Errors


logger = logging.getLogger(__name__)


def get_sko(db, sko):
    """
    Get a job code and description.

    Typically used to check if a given job code is defined.

    :param int sko: a job code

    :returns: a single row with a (sko, description) pair

    :raises NotFoundError: when the sko_code is invalid.
    """
    binds = {'sko': int(sko)}
    stmt = """
      SELECT sko, description
      FROM [:table schema=cerebrum name=orgera_stillingskode]
      WHERE sko = :sko
    """
    return db.query_1(stmt, binds)


def list_sko(db):
    """
    Get all known job codes.

    :returns: rows with (sko, description) pairs
    """
    stmt = """
      SELECT sko, description
      FROM [:table schema=cerebrum name=orgera_stillingskode]
    """
    return db.query(stmt)


def assert_sko(db, sko, description):
    """
    Insert a job code or update its description.

    :param int sko: a job code
    :param str description: a job code description

    :returns: a row with the updated (sko, description) pair
    """
    binds = {'sko': int(sko), 'description': six.text_type(description)}

    try:
        current = get_sko(db, sko)
        if current['description'] == description:
            # (sko, description) pair already exists
            logger.debug('assert_sko %r: no change', sko)
        else:
            # description update
            stmt = """
              UPDATE [:table schema=cerebrum name=orgera_stillingskode]
              SET description = :description
              WHERE sko = :sko
              RETURNING sko, description
            """
            current = db.query_1(stmt, binds)
            logger.info('assert_sko %r: updated', current)
    except Errors.NotFoundError:
        # sko missing
        stmt = """
          INSERT INTO [:table schema=cerebrum name=orgera_stillingskode]
            (sko, description)
          VALUES
            (:sko, :description)
          RETURNING sko, description
        """
        current = db.query_1(stmt, binds)
        logger.info('assert_sko %r: added', current)
    return current


@six.python_2_unicode_compatible
class Sko(object):
    """ Representation of a job code (sko/stillingskode). """

    def __init__(self, code, description):
        self.code = int(code)
        self.description = six.text_type(description)

    def __repr__(self):
        return '<{}({}, {})>'.format(type(self).__name__,
                                     repr(self.code),
                                     repr(self.description))

    def __str__(self):
        return six.text_type(format(self.code, '04d'))

    def __int__(self):
        return self.code

    def __eq__(self, other):
        if not isinstance(other, Sko):
            return False
        return self.code == other.code

    def __ne__(self, other):
        if not isinstance(other, Sko):
            return True
        return self.code != other.code

    @classmethod
    def from_dict(cls, d, code_field='sko', desc_field='description'):
        return cls(d[code_field], d[desc_field])

    @classmethod
    def fetch(cls, db, code):
        return cls.from_dict(get_sko(db, code))

    def flush(self, db):
        self.code, self.description = assert_sko(db, self.code,
                                                 self.description)

    @classmethod
    def list_all(cls, db):
        return (cls.from_dict(r) for r in list_sko(db))


def get_styrk(db, sko, styrk):
    """
    Get occopation code and description.

    :param int sko: a job code
    :param int sko: an occupation code

    :returns:
        a single row with fields: sko, sko_description, styrk,
        styrk_description

    :raises NotFoundError: when the (sko, styrk) pair is invalid.
    """
    binds = {'sko': int(sko), 'styrk': int(styrk)}
    stmt = """
      SELECT s.sko, s.description as sko_description,
             y.styrk, y.description as styrk_description
      FROM [:table schema=cerebrum name=orgera_stillingskode] s
      JOIN [:table schema=cerebrum name=orgera_yrkeskode] y
        ON s.sko = y.sko
      WHERE s.sko = :sko AND y.styrk = :styrk
    """
    return db.query_1(stmt, binds)


def list_styrk(db):
    """
    Get all known occopation codes.

    :returns:
        rows with fields: sko, sko_description, styrk, styrk_description
    """
    stmt = """
      SELECT s.sko, s.description as sko_description,
             y.styrk, y.description as styrk_description
      FROM [:table schema=cerebrum name=orgera_stillingskode] s
      JOIN [:table schema=cerebrum name=orgera_yrkeskode] y
        ON s.sko = y.sko
    """
    return db.query(stmt)


def assert_styrk(db, sko, styrk, description):
    """
    Insert an occupation code or update its description.

    :param int sko: a job code
    :param int styrk: an occupation code
    :param str description: a description for the (sko, styrk) pair

    :returns:
        a row with the updated occupation code, fields: sko, sko_description,
        styrk, styrk_description
    """
    binds = {
        'sko': int(sko),
        'styrk': int(styrk),
        'description': six.text_type(description),
    }

    get_sko(db, sko)  # assert sko exists

    try:
        current = get_styrk(db, sko, styrk)
        if current['styrk_description'] == description:
            # (sko, styrk, description) exists
            logger.debug('assert_styrk %r: no change', current)
        else:
            # styrk exists
            stmt = """
              UPDATE [:table schema=cerebrum name=orgera_yrkeskode]
              SET description = :description
              WHERE sko = :sko AND styrk = :styrk
            """
            db.execute(stmt, binds)
            current = get_styrk(db, sko, styrk)
            logger.info('set_styrk %r: updated', current)
    except Errors.NotFoundError:
        # styrk missing
        stmt = """
          INSERT INTO [:table schema=cerebrum name=orgera_yrkeskode]
            (sko, styrk, description)
          VALUES
            (:sko, :styrk, :description)
        """
        db.execute(stmt, binds)
        current = get_styrk(db, sko, styrk)
        logger.info('assert_styrk %r: added', current)
    return current


@six.python_2_unicode_compatible
class Styrk(object):
    """ Representation of an occupation code (styrk/yrkeskode). """

    def __init__(self, sko, code, description):
        if not isinstance(sko, Sko):
            raise ValueError('invalid sko: %s' % repr(sko))
        self.sko = sko
        self.code = int(code)
        self.description = six.text_type(description)

    def __repr__(self):
        return '<{}({}, {}, {})>'.format(type(self).__name__,
                                         repr(self.sko),
                                         repr(self.code),
                                         repr(self.description))

    def __str__(self):
        return six.text_type(format(self.code, '09d'))

    def __int__(self):
        return self.code

    def __eq__(self, other):
        if not isinstance(other, Styrk):
            return False
        return self.sko == other.sko and self.code == other.code

    def __ne__(self, other):
        if not isinstance(other, Styrk):
            return True
        return self.sko != other.sko or self.code != other.code

    @classmethod
    def from_dict(cls, d, sko_field='sko', sko_desc_field='sko_description',
                  styrk_field='styrk', styrk_desc_field='styrk_description'):
        sko = Sko.from_dict(d, code_field=sko_field, desc_field=sko_desc_field)
        return cls(sko, d[styrk_field], d[styrk_desc_field])

    @classmethod
    def fetch(cls, db, sko, styrk):
        return cls.from_dict(get_styrk(db, sko, styrk))

    def flush(self, db):
        self.sko.flush(db)
        _, _, self.code, self.description = assert_styrk(db, self.sko.code,
                                                         self.code,
                                                         self.description)

    @classmethod
    def list_all(cls, db):
        return (cls.from_dict(r) for r in list_styrk(db))
