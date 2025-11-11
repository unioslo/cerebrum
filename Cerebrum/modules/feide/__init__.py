# -*- coding: utf-8 -*-
#
# Copyright 2016-2025 University of Oslo, Norway
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
Module for feide specific functionality

Feide services and user AuthnLevel
----------------------------------
Currently, most of the functinality here is connected to the
``norEduPersonServiceAuthnLevel`` attribute in OrgLDIF.

The database module ``feide_service``, along with :mod:`.service`,
allows us to store a required authentication level for a given (feide service,
person) combination - i.e. require MFA for given users in given systems.

:mod:`.bofhd_feide_cmds` implements bofhd commands for adding feide services
and setting required auth levels.

:mod:`.ldif_mixins` implements the export from this module to the
``norEduPersonServiceAuthnLevel`` attribute.

TODO
----
This module should probably be renamed to ``Cerebrum.modules.feide_service``
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

# Database module version (mod_feide_service.sql)
__version__ = "1.1"
