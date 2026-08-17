# -*- coding: utf-8 -*-
#
# Copyright 2021-2026 University of Oslo, Norway
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
Orgreg related modules.

Orgreg is an authoritative system for org structures and org units.

At institutions with Orgreg, the organizational tree is manually maintained in
this system, and then imported into Cerebrum and other systems.


Configuration
==============
``cereconf.CLASS_CONSTANTS``
    Must include ``Cerebrum.modules.orgreg.constants/OrgregConstants`` to
    provide Orgreg-related constants.


How to use
===========
To import data from Orgreg, Cerebrum first needs to fetch it, and extract the
relevant objects and attributes.  As with most integrations, this is separated
into three distinct operations:

1. Fetching data from Orgreg (see :mod:`.client`)
2. Normalizing the org unit data (see :mod:`.datasource`)
3. Mapping fields from Orgreg to Cerebrum (see :mod:`.mapper`)


Org unit import
----------------
This module only provides a compatibility layer for Orgreg - and the org unit
import is implemented in the generic :mod:`Cerebrum.modules.ou_import` module.

For now, the Orgreg import use a slightly convoluted compatibility layer for a
legacy SAP import, and a regular Orgreg import consists of:

1. Using ``contrib/orgreg/orgreg-fetch-legacy-xml.py`` to fetch and write the
   org tree and org units to a legacy XML file.

2. Importing the file with
   ``contrib/no/import_OU.py --file "ORGREG:<filename>"``.
"""
