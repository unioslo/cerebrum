# -*- coding: utf-8 -*-
#
# Copyright 2022 University of Oslo, Norway
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
Utils for updating the ou tree structure in Cerebrum.

Modules
-------
py:mod:`.ou_model`
    Implements an abstract Org unit, py:class:`.ou_model.PreparedOrgUnit`, as
    well as an abstract py:class:`.ou_model.OrgUnitMapper` for creating new
    ``PreparedOrgUnit`` objects from some source.

    These objects can be passed to functions in the ``ou_sync`` module for
    import.

py:mod:`.ou_sync`
    Routines for updating OU objects in Cerebrum.  The sync takes a
    `py:class:`.ou_model.PreparedOrgUnit`, and ensures that an equivalent org
    unit exists in Cerebrum.

py:mod:`.legacy_xml2ou`
    Legacy mapper for OU objects from
    py:mod:`Cerebrum.modules.xmlutils.xml2object`.  This can be used to
    backport the py:mod:`.ou_sync` module into the ``contrib/no/import_OU.py``
    script.

py:mod:`.tree_model`
    Objects that can represent an org tree structure (or any tree structure).
    This can be used to model and validate the OU perspective given in sources.


Issues
------
The current org unit import (and a lot of org unit functionality in Cerebrum)
heavily depends on location code (stedkode, sko) identifiers when building tree
structures, or otherwise identifying org units.

We should re-factor org units in Cerebrum so that this value is just another
external id, and have each PreparedOrgUnit have one *primary* external id
(which can then be e.g. a location-code or orgreg-id).  In order to get there,
we should:

1. Start registering stedkode as an external_id string
   (e.g. location, location_code)

2. Start using stedkode from external_id rather than the stedkode tables

3. Replace stedkode lookups with generic primary external_id + other
   external_id lookups, or just location code external id lookups where this
   makes sense.

4. Remove all stedkode info when everything uses external_id
"""
