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


def aff_lookup(constants, aff_string):
    """Find the aff code or status we want

    :param constants:
    :param int or str aff_string:
    """
    if isinstance(aff_string, int) or aff_string.isdigit():
        # Assume we got the id of the constant
        try:
            status = constants.PersonAffStatus(int(aff_string))
        except Errors.NotFoundError:
            status = None
            aff = constants.PersonAffiliation(int(aff_string))
            try:
                int(aff)
            except Errors.NotFoundError:
                raise Exception("Unknown affiliation: %s" % aff_string)
            else:
                return aff, status
        else:
            return status.affiliation, status

    aff = aff_string.split('/', 1)
    if len(aff) > 1:
        try:
            status = constants.PersonAffStatus(aff[0], aff[1])
            aff = status.affiliation
        except Errors.NotFoundError:
            raise Exception("Unknown affiliation: %s" % aff_string)
        else:
            return aff, status
    else:
        aff = constants.PersonAffiliation(aff_string)
        status = None
        try:
            int(aff)
        except Errors.NotFoundError:
            raise Exception("Unknown affiliation: %s" % aff_string)
        else:
            return aff, status
