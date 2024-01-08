# -*- coding: utf-8 -*-
#
# Copyright 2019-2023 University of Oslo, Norway
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
Utilities for looking up default disks and disk rules.

This modules implements two important features in the default disk mapping
module:

Wildcard rules (:func:`.get_disk_rule`)
    Rules can apply to all affiliations or affiliation statuses at a given org
    unit.  If an org unit has multiple rules (e.g. `<*>/<*>@<ou>`,
    `<AFFILIATION>/<*>@<ou>`, `<AFFILIATION>/<status>@<ou>`), the most specific
    rule will be used.

Hierarchical lookup (:func:`.resolve_disk`)
    If no rule (including wildcard rules) applies to a given org unit,  we
    continue searching upwards in the org unit tree for a matching rule.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from Cerebrum import Errors
from Cerebrum.Utils import Factory


def get_disk_rule(disk_mapping, ou_id, affiliation, status):
    """
    Get disk for a given affiliation/selection rule.

    :param int ou_id: org unit id
    :param int affiliation: affiliation code
    :param int status: affiliation status code

    :returns: matching rule row
    :raises Error.NotFoundError: if no matching rule exists
    """
    # Is there a rule for this affiliation and status?
    if status:
        try:
            return disk_mapping.get(ou_id, affiliation, status)
        except Errors.NotFoundError:
            pass

    # Is there a rule for this affiliation?
    if affiliation:
        try:
            return disk_mapping.get(ou_id, affiliation, None)
        except Errors.NotFoundError:
            pass

    # Is there a rule for all affiliations?
    return disk_mapping.get(ou_id, None, None)


def get_parent_id(db, ou_id, perspective):
    """
    Get parent org unit id.

    :returns int: parent id
    :raises Error.NotFoundError: if no parent exists
    """
    ou = Factory.get("OU")(db)
    ou.find(ou_id)
    return ou.get_parent(perspective)


def resolve_disk(disk_mapping,
                 ou_id,
                 affiliation,
                 status,
                 perspective):
    """
    Search the org tree for the best matching ou mapping disk rule.

    :param disk_mapping: disk mapping implementation
    :param int ou_id: org unit id
    :param int affiliation: affiliation code
    :param int status: affiliation status code
    :param int perspective: org unit perspective
    """
    db = disk_mapping._db
    seen_ids = set()

    while True:
        try:
            return get_disk_rule(disk_mapping, ou_id, affiliation, status)
        except Errors.NotFoundError:
            # No match at this ou_id
            pass

        seen_ids.add(ou_id)

        # No matching rule found yet, continue with parent.
        # This will raise NotFoundError if there aren't any more parents
        ou_id = get_parent_id(db, ou_id, perspective)

        # org tree cycle protection
        if ou_id in seen_ids:
            raise RuntimeError("Org tree cycle! (ou_id=%s, perspective=%s)"
                               % (repr(ou_id), repr(perspective)))


def get_disk(database,
             disk_mapping,
             ou_id,
             aff_code,
             status_code,
             perspective,
             ou_class=None,
             constants=None):
    """
    This function is deprecated, and is only here to support legacy lookups.

    Find the appropriate disk_id for a given affiliation.  This is a
    hierarchical selection process, and the selection process is as follows:

    OU+Aff+Status > OU+Aff > OU > parent OU+Aff+Status > parent OU+Aff > ...

    :param disk_mapping: disk mapping implementation
    :param database: not used
    :param int ou_id: org unit for default disk selection
    :param aff_code: affiliation for default disk selection
    :param status_code: affiliation status for default disk selection
    :param perspective: org unit perspective
    :param ou_class: not used
    :param constants: not used

    :returns int: entity id of the matching default disk
    :raises Error.NotFoundError:
        if no matching default disk setting exists anywhere in the org tree
    """
    row = resolve_disk(disk_mapping, ou_id, aff_code, status_code, perspective)
    return row['disk_id']
