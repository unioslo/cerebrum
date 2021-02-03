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

from Cerebrum import Errors
from Cerebrum.Constants import _OUPerspectiveCode
from Cerebrum.Utils import Factory

from . import job_assignments
from . import ou_utils


logger = logging.getLogger(__name__)


class OuRecursion(object):
    """ OU recursion rules for ORG-ERA groups. """

    searches = {
        'children': ou_utils.find_children,
        'parents': ou_utils.find_parents,
    }

    def __init__(self, perspective, include):
        """
        :param str perspective: ou perspective to use
        :param str include: 'parents' or 'children'
        """
        self.perspective = perspective
        if include not in self.searches:
            raise ValueError('invalid include %s' % repr(include))
        self.include = include

    def __repr__(self):
        return '<%s(%r, %r)>' % (type(self).__name__,
                                 self.perspective,
                                 self.include)

    def to_dict(self):
        return {
            'perspective': self.perspective,
            'include': self.include,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(d['perspective'], d['include'])


class GroupTemplate(object):

    def __init__(self, ou=None, sko=None, styrk=None, recursion=None):
        """
        :param str ou: ou filter for the group
        :param set sko: sko filter for the group
        :param set styrk: styrk filter for the group
        :param OuRecursion recursion: ou inheritance rules for ``ou``
        """
        if not any((ou, sko, styrk)):
            raise ValueError('must provide ou, sko or styrk')
        if recursion and not ou:
            raise ValueError('must provide an ou for recursion')
        if recursion and not isinstance(recursion, OuRecursion):
            raise ValueError('invalid recursion type %s' % repr(OuRecursion))
        self.ou = ou
        self.sko = set(sko or ())
        self.styrk = set(styrk or ())
        self.recursion = recursion

    def __repr__(self):
        return '<%s(%r, %r, %r, %r)>' % (
            type(self).__name__,
            self.ou, self.sko, self.styrk, self.recursion)

    def to_dict(self):
        items = (
            ('ou', self.ou),
            ('sko', self.sko),
            ('styrk', self.styrk),
            ('recursion', (None if self.recursion is None
                           else self.recursion.to_dict())),
        )
        return {k: v for k, v in items if v}

    @classmethod
    def from_dict(cls, d):
        recursion = d.get('recursion')
        return cls(
            d.get('ou'),
            d.get('sko'),
            d.get('styrk'),
            OuRecursion.from_dict(recursion) if recursion else None,
        )


def _get_ou(db, value):
    """ Get OU-object from a ``GroupTemplate.ou`` input value. """
    id_type, _, id_value = value.partition(':')
    if id_type == 'sko':
        return ou_utils.get_ou_by_sko(db, id_value)
    else:
        raise ValueError('invalid id-type %s' % repr(id_type))


def _get_perspective(co, value):
    """ Get OU perspective code a ``OuRecursion.perspective`` input value. """
    if isinstance(value, _OUPerspectiveCode):
        const = value
    else:
        const = co.human2constant(value, _OUPerspectiveCode)
    if const is None:
        raise LookupError("OUPerspective %r not defined" % (value, ))
    try:
        int(const)
    except Errors.NotFoundError:
        raise LookupError("OUPerspective %r (%r) not in db" %
                          (value, const))
    return const


def format_description(template):
    """ Format a human readable description of a GroupTemplate """
    sko = ('sko:%s' % ','.join(map(str, template.sko))
           if template.sko else '')
    styrk = ('styrk:%s' % ','.join(map(str, template.styrk))
             if template.styrk else '')
    ou = template.ou or ''
    rec = (template.recursion.include
           if template.recursion and template.ou else '')

    return 'Employees{w}{sko}{et}{styrk}{at}{ou}{ra}{rec}'.format(
        w=' with ' if (sko or styrk) else '',
        sko=sko,
        et=' and ' if (sko and styrk) else '',
        styrk=styrk,
        at=' at ' if ou else '',
        ou=ou,
        ra=' and ' if rec else '',
        rec=rec,
    )


def find_relevant_ous(db, template):
    """ Find all relevant ou_id values for a given template. """
    co = Factory.get('Constants')(db)
    ou_id = _get_ou(db, template.ou).entity_id
    ous = set((int(ou_id),))
    if template.recursion:
        r = template.recursion
        perspective = _get_perspective(co, r.perspective)
        search = r.searches[r.include]
        ous.update(int(row['ou_id']) for row in search(db, perspective, ou_id))
    return ous


def find_members(db, template):
    """ Find all members for a given template. """
    search_args = {}
    if template.ou:
        search_args.update({'ou_id': find_relevant_ous(db, template)})

    if template.sko:
        search_args.update({'sko': template.sko})

    if template.styrk:
        search_args.update({'styrk': template.styrk})

    return set(int(r['person_id'])
               for r in job_assignments.search_assignments(db, **search_args))
