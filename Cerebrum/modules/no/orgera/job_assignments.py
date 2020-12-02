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
This module provides access to ORG-ERA employee assignment roles.
"""
import logging

import six

from Cerebrum import Errors
from Cerebrum.Utils import argument_to_sql, NotSet


logger = logging.getLogger(__name__)


def _cast_or_none(cast):
    return lambda v: None if v is None else cast(v)


assignment_fields = ('assignment_id', 'person_id', 'ou_id', 'sko', 'styrk',
                     'updated_at')


def get_assignment(db, assignment_id):
    """
    Ensure assignment exists and is up to date.

    :param str assignment_id: external reference for the assignment

    :returns:
        an assignment row with fields: assignment_id, person_id, ou_id, sko,
        styrk
    """
    binds = {'assignment_id': six.text_type(assignment_id)}

    stmt = """
      SELECT {fields}
      FROM [:table schema=cerebrum name=orgera_assignments]
      WHERE assignment_id = :assignment_id
    """.format(fields=', '.join(assignment_fields))
    return db.query_1(stmt, binds)


def set_assignment(db, assignment_id, person_id, ou_id, sko, styrk=None):
    """
    Ensure assignment exists and is up to date.

    :param str assignment_id: external reference for the assignment
    :param int person_id: person_id that assignment belongs to
    :param int ou_id: ou_id that the assingment targets
    :param int sko: job code for this assignment
    :param int styrk: optional styrk for this assignment

    :returns: an up to date assignment row
    """
    binds = {
        'assignment_id': six.text_type(assignment_id),
        'person_id': int(person_id),
        'ou_id': int(ou_id),
        'sko': int(sko),
        'styrk': _cast_or_none(int)(styrk),
    }

    try:
        current = get_assignment(db, assignment_id)
    except Errors.NotFoundError:
        current = None

    if all(current[k] == binds[k] for k in binds):
        logger.debug('set_assignment (%r, %r, %r): no change',
                     assignment_id, person_id, ou_id)
        # No change
        return current

    if not current:
        stmt = """
          INSERT INTO [:table schema=cerebrum name=orgera_assignments]
            (assignment_id, person_id, ou_id, sko, styrk)
          VALUES
            (:assignment_id, :person_id, :ou_id, :sko, :styrk)
          RETURNING
            {fields}
        """.format(fields=', '.join(assignment_fields))
        logger.info('set_assignment (%r, %r, %r): adding',
                    assignment_id, person_id, ou_id)
    else:
        stmt = """
          UPDATE [:table schema=cerebrum name=orgera_assignments]
          SET
            person_id = :person_id
            ou_id = :ou_id,
            sko = :sko,
            styrk = :styrk
          WHERE
            assignment_id = :assignment_id
          RETURNING
            {fields}
        """.format(fields=', '.join(assignment_fields))
        logger.info('set_assignment (%r, %r, %r): updating',
                    assignment_id, person_id, ou_id)

    return db.query_1(stmt, binds)


def search_assignments(db, assignment_id=NotSet, person_id=NotSet,
                       ou_id=NotSet, sko=NotSet, styrk=NotSet):
    """
    Ensure assignment exists and is up to date.

    :type assignment_id: int, sequence
    :type person_id: int, sequence
    :type ou_id: int, sequence
    :type sko: int
    :type styrk: int, NoneType

    :returns: an up to date assignment row
    """
    binds = {}
    conds = []

    if assignment_id is not NotSet:
        conds.append(argument_to_sql(assignment_id, 'assignment_id', binds,
                                     six.text_type))

    if person_id is not NotSet:
        conds.append(argument_to_sql(person_id, 'person_id', binds, int))

    if ou_id is not NotSet:
        conds.append(argument_to_sql(ou_id, 'ou_id', binds, int))

    if sko is not NotSet:
        binds['sko'] = int(sko)
        conds.append('sko = :sko')

    if styrk is not NotSet:
        if styrk is None:
            conds.append('styrk IS NULL')
        else:
            binds['styrk'] = int(styrk)
            conds.append('styrk = :styrk')

    stmt = """
      SELECT {fields}
      FROM [:table schema=cerebrum name=orgera_assignments]
      {where}
    """.format(
        fields=', '.join(assignment_fields),
        where=('WHERE ' + ' AND '.join(conds)) if conds else '',
    )
    return db.query(stmt, binds)


def delete_assignments(db, assignment_id=NotSet, person_id=NotSet,
                       ou_id=NotSet, sko=NotSet, styrk=NotSet):
    """
    Delete assignments.

    :type assignment_id: int, sequence
    :type person_id: int, sequence
    :type ou_id: int, sequence
    :type sko: int
    :type styrk: int, NoneType

    :returns: an up to date assignment row
    """
    binds = {}
    conds = []

    if assignment_id is not NotSet:
        conds.append(argument_to_sql(assignment_id, 'assignment_id', binds,
                                     six.text_type))

    if person_id is not NotSet:
        conds.append(argument_to_sql(person_id, 'person_id', binds, int))

    if ou_id is not NotSet:
        conds.append(argument_to_sql(ou_id, 'ou_id', binds, int))

    if sko is not NotSet:
        binds['sko'] = int(sko)
        conds.append('sko = :sko')

    if styrk is not NotSet:
        if styrk is None:
            conds.append('styrk IS NULL')
        else:
            binds['styrk'] = int(styrk)
            conds.append('styrk = :styrk')

    stmt = """
      DELETE
      FROM [:table schema=cerebrum name=orgera_assignments]
      {where}
      RETURNING {fields}
    """.format(
        fields=', '.join(assignment_fields),
        where=('WHERE ' + ' AND '.join(conds)) if conds else '',
    )
    return db.query(stmt, binds)
