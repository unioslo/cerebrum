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
ORG-ERA access module.

This module supplements Cerebrum with employment (and potentially faculty) role
data, as well as rules for representing these roles as groups.

cereconf
--------
If the related ``mod_orgera.sql`` database schema is present, the following
Cerebrum modules must be included in ``cereconf`` in order to maintain
constraints:

``cereconf.CLASS_CONSTANTS``
    Must include ``Cerebrum.modules.no.orgera.constants/OrgEraConstants``

``cereconf.CLASS_PERSON``
    Must include ``Cerebrum.modules.no.orgera.person_mixins/OrgEraPersonMixin``

``cereconf.CLASS_OU``
    Must include ``Cerebrum.modules.no.orgera.ou_mixins/OrgEraOuMixin``


TODO
----
Include data models for faculty (FS-related) roles.  This could include:

- Course participation (undervisningsenhet, undervisningsaktivitetet)
- Study program affiliation
- Graduation year (kull - or is it entry year?)
- Academic level (bachelor, master, doctorate)
"""

__version__ = '0.1'
