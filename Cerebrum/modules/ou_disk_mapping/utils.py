# -*- coding: utf-8 -*-
# Copyright 2019 University of Oslo, Norway
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
Utilities related to ou_disk_mapping module
"""
from Cerebrum import Errors
from Cerebrum.Utils import Factory


def get_disk(database,
             disk_mapping,
             ou_id,
             aff_code,
             status_code,
             perspective,
             ou_class=None,
             constants=None):
    """
    Find the appropriate disk depending on OU, Aff, Status

    This is a hierarchical selection process.
    The selection process is as follows:
      OU+Aff+Status > OU+Aff > OU > parent OU+Aff+Status > parent OU+Aff
      and so on until there is a hit.

    :param disk_mapping: Instance of OUDiskMapping

    :type constants: Cerebrum.Utils._dynamic_Constants
    :param constants: Constants generated with Factory.get

    :type ou_class: Cerebrum.OU.OU or None
    :param ou_class: Unpopulated Ou object

    :type perspective: int or Cerebrum.Constants._OUPerspectiveCode
    :param perspective: Ou perspective

    :type database: Cerebrum.CLDatabase.CLDatabase
    :param database: Database connection

    :param int ou_id: entity id of the OU

    :param aff_code: None or Cerebrum.Constants._PersonAffiliationCode

    :param status_code: None or Cerebrum.Constants._PersonAffStatusCode

    :rtype: int
    :return: The entity id of the disk
    """
    if ou_class is None:
        ou_class = Factory.get("OU")(database)
    if constants is None:
        constants = Factory.get("Constants")(database)

    # Is there a hit for the specific one?
    if status_code:
        try:
            row = disk_mapping.get(ou_id, aff_code, status_code)
        except Errors.NotFoundError:
            pass
        else:
            return row["disk_id"]

    # With just Ou and aff?
    if aff_code:
        try:
            row = disk_mapping.get(ou_id, aff_code, None)
        except Errors.NotFoundError:
            pass
        else:
            return row["disk_id"]

    # With just OU?
    try:
        row = disk_mapping.get(ou_id, None, None)
    except Errors.NotFoundError:
        pass
    else:
        return row["disk_id"]

    # Jump to parent and start over
    ou_class.find(ou_id)
    parent_id = ou_class.get_parent(perspective)
    ou_class.clear()
    disk_id = get_disk(database, disk_mapping, parent_id, aff_code,
                       status_code,
                       perspective,
                       ou_class=ou_class)
    return disk_id
