# -*- coding: iso-8859-1 -*-
# Copyright 2007 University of Oslo, Norway
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
This module implements an abstraction layer for FS-originated data.
"""

from mx.DateTime import Date
import time
import sys

from Cerebrum.modules.xmlutils.xml2object import \
     XMLDataGetter, XMLEntity2Object, DataOU, DataName, \
     DataAddress, DataContact





class FSXMLDataGetter(XMLDataGetter):
    """An abstraction layer for FS XML files."""


    def iter_ou(self):
        return self._make_iterator("sted", XMLOU2Object)
    # end iter_ou
# end FSXMLDataGetter





class XMLOU2Object(XMLEntity2Object):
    """An iterator over OU elements in XML files generated from FS."""


    def _pull_name(self, element, attribute_name):

        if element.get(attribute_name):
            value = element.get(attribute_name).encode("latin1")
            return value

        return None
    # end _pull_name


    def _make_contact(self, element):
        """Return a DataContact entry corresponding to a given XML element."""

        comm_type = element.get("kommtypekode")
        value = element.get("kommnrverdi")

        if not value:
            return None, None

        if comm_type == "TLF":
            return DataContact.CONTACT_PHONE, value
        elif comm_type == "FAX":
            return DataContact.CONTACT_FAX, value
        elif comm_type == "EKSTRA TLF":
            return DataContact.CONTACT_PHONE, value

        return None, None
    # end _make_contact
    
    
    def next(self):
        """Returns a DataEntity representation of the 'next' XML element."""

        element = self._xmliter.next()
        result = DataOU()

        sko = tuple([int(element.get(x)) for x in ("fakultetnr",
                                                   "instituttnr",
                                                   "gruppenr")])
        result.add_id(result.NO_SKO, sko)

        # Parent ID - sko
        sko = tuple([int(element.get(x)) for x in ("fakultetnr_for_org_sted",
                                                   "instituttnr_for_org_sted",
                                                   "gruppenr_for_org_sted")])
        result.parent = (result.NO_SKO, sko)

        # stedkode_konv occationally contains SAP-OU-id for some
        # SAP-implementations. NB! This does not apply to UiO (as UiO's
        # implementation uses sko).
        if element.get("stedkode_konv"):
            result.add_id(result.NO_SAP_ID, element.get("stedkode_konv"))

        # IVR 2007-01-02: Everything coming from FS is publishable. However,
        # we may want to revise that at some point.
        result.publishable = True

        # names
        for name_kind, xmlname, lang in ((result.NAME_LONG, "stednavn", "no"),
                                         (result.NAME_SHORT, "forkstednavn", "no"),
                                         (result.NAME_ACRONYM, "akronym", "no")):
            value = self._pull_name(element, xmlname)
            if value:
                result.add_name(DataName(name_kind, value, lang))

        # addresses
        extract = lambda x: element.get(x, "").encode("latin1")
        for xmlkind, address_kind in (("besok", DataAddress.ADDRESS_BESOK),
                                      ("intern", DataAddress.ADDRESS_POST)):
            zipcode = extract("poststednr_%s_adr" % xmlkind)
            street = (extract("adresselinje1_%s_adr" % xmlkind),
                      extract("adresselinje2_%s_adr" % xmlkind))
            result.add_address(DataAddress(kind=address_kind,
                                           street=street,
                                           zip=zipcode,
                                           city="",
                                           country=""))

        # contact information
        priority = 0
        for subelement in element.findall("komm"):
            kind, value = self._make_contact(subelement)
            if kind and value:
                result.add_contact(DataContact(kind, value, priority))
                priority += 1

        return result
    # end next
# end XMLOU2Object
        
            
