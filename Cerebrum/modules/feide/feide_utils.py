# -*- coding: utf-8 -*-

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

import uuid
import six


def is_uuid(x):
    """Checks if x is a UUID"""
    if isinstance(x, uuid.UUID):
        return True
    try:
        _ = uuid.UUID(x)
        return True
    except (TypeError, ValueError, AttributeError):
        return False
    return False

def is_valid_feide_id_type(x):
    """Checks what kind of format a proposed feide-ID has.

    Valid values are: int, uuid (or a string representation of either)
    or the string 'all' (arbitrary capitalization)."""
    if not x:
        return False
    if isinstance(x, (uuid.UUID, int)) or is_uuid(x):
        return True
    try:
        _ = int(x)
        return True
    except ValueError:
        if six.text_type(x).lower() == six.text_type('all'):
            return True
    except Exception:
        return False
    return False
