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


def aff_lookup(constants, in_aff):
    """Find the aff code or status we want

    :type constants: Cerebrum.Utils._dynamic_Constants
    :param constants: Constants generated with Factory.get

    :type in_aff: int, str, PersonaffStatus, PersonAffiliation
    :param in_aff: Constant or str/int of the Constant
    """
    if isinstance(in_aff, constants.PersonAffStatus):
        return in_aff.affiliation, in_aff
    if isinstance(in_aff, constants.PersonAffiliation):
        return in_aff, None

    if isinstance(in_aff, int) or in_aff.isdigit():
        # Assume we got the id of the constant
        try:
            status = constants.PersonAffStatus(int(in_aff))
        except Errors.NotFoundError:
            status = None
            aff = constants.PersonAffiliation(int(in_aff))
            try:
                int(aff)
            except Errors.NotFoundError:
                raise Exception("Unknown affiliation: %s" % in_aff)
            else:
                return aff, status
        else:
            return status.affiliation, status

    aff = in_aff.split("/", 1)
    if len(aff) > 1:
        try:
            status = constants.PersonAffStatus(aff[0], aff[1])
            aff = status.affiliation
        except Errors.NotFoundError:
            raise Exception("Unknown affiliation: %s" % in_aff)
        else:
            return aff, status
    else:
        aff = constants.PersonAffiliation(in_aff)
        status = None
        try:
            int(aff)
        except Errors.NotFoundError:
            raise Exception("Unknown affiliation: %s" % in_aff)
        else:
            return aff, status
