# -*- coding: utf-8 -*-
# Copyright 2014 University of Oslo, Norway
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
"""Group models."""

from rpclib.model.complex import ComplexModel
# TODO: Fix'n move
from Cerebrum.modules.cis.Utils import Unicode, DateTime
from rpclib.model.primitive import String

NAMESPACE = 'GroupAPI'


class GroupInfo(ComplexModel):
    """Information about a group."""
    __namespace__ = NAMESPACE
    __tns__ = NAMESPACE

    name = String
    description = Unicode
    expire_date = DateTime
    visibility = String


class GroupMember(ComplexModel):
    """Information about a group member."""
    __namespace__ = NAMESPACE
    __tns__ = NAMESPACE

    type = String
    name = String
    # TBD: Not here: id, expire1, expire2, expire_date
