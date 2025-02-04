# -*- coding: utf-8 -*-

# Copyright 2005-2025 University of Oslo, Norway
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
XML import utils for Cerebrum.

This module is responsible for importing xml objects from external sources.  It
follows a *legacy* import pattern, and newer imports should omit this module.

A typical legacy xml import consists of:

Legacy parsing
    A parser (xml2object or a system-specific alternative) to parse XML data
    into intermediate objects (:class:`.xml2object.DataEntity`).  This step
    should select and map specific fields from the source XML object and into
    generic attributes in the DataEntity object.

    Example: In fsxml2object, we map <sted> -> <komm> objects to
    :class:`.xml2object.DataContact` entries.  In the DataEntity, a ``<komm
    kommtypekode="TLF" kommnrverdi="12345678"/>`` would end up as a
    ``(DataContact.CONTACT_PHONE, "12345678")`` tuple in the DataEntity org
    unit subclass.

Legacy import
    An importer (object2cerebrum) which takes intermediate objects from the
    previous step and stores that object.

    Example: To continue the legacy parsing example - the tuple stored as
    contact info in the org unit DataEntity would be mapped to, and stored as
    contact type PHONE in Cerebrum.


New import pattern
------------------
Newer imports should split this into three distinct steps:

Datasource
    A datasource module that validates and normalizes source data.  The
    datasource module is system specific for the source system, and deals only
    with source data and data formats.  This includes for example:

    - checking that mandatory fields have valid values, and ensuring that
      optional fields are either empty or have valid values.

    - converting date/time strings into ``datetime`` objects.

    - decoding bytestring texts and normalizing unicode text to NFC

Mapper
    A mapper module that chooses which source fields to keep, and which
    Cerebrum attributes to map source fields to.  The mapper module is the only
    part that deals with both the source system and destination system
    (Cerebrum).  E.g. a field called ``mobile_phone`` from the source system is
    stored as contact info of type ``PRIVATE_MOBILE`` in Cerebrum.

Importer
    An importer module that takes Cerberum-esque data from a mapper and stores
    as-is.

See e.g. :mod:`Cerebrum.modules.greg` for examples of an import that follows
this pattern.
"""
