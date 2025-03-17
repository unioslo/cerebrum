# -*- coding: utf-8 -*-
#
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
This module implements an abstraction layer for LT-compatible data.

Data from LT is similar to SAPUIO-data (see :mod:`.sapxml2object`), and comes
in the form of an XML file with org-units:
::

    <data>
      <sted fakultetnr="70"
            instituttnr="55"
            gruppenr="0"
            forkstednavn="Foo"
            stednavn="Institutt for Foo"
            akronym="FOO" >
        <komm kommtypekode="EPOST"
              kommnrverdi="foo@example.org" />
        ...
      </sted>
      ...
    </data>
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from Cerebrum.modules.xmlutils.xml2object import (
    DataAddress,
    DataContact,
    DataName,
    DataOU,
    XMLDataGetter,
    XMLEntity2Object,
    ensure_unicode,
)


class LTXMLDataGetter(XMLDataGetter):
    """An abstraction layer for LT XML files."""

    def iter_ou(self):
        return self._make_iterator("sted", XMLOU2Object)


class XMLOU2Object(XMLEntity2Object):
    """A converter class that maps ElementTree's Element to DataOU."""

    def _pull_name(self, element, *possible_keys):
        """Return a first of possible_keys that is present in element."""
        for key in possible_keys:
            if element.get(key):
                value = ensure_unicode(element.get(key), self.encoding)
                return value
            # fi
        # od

        # NB! A name that is not there *must* be represented as None. "" (empty
        # string) is NOT the same as no name.
        return None

    def _make_contact(self, element):

        def get_value(element_value):
            return ensure_unicode(element_value, self.encoding)

        comm_type = element.get("kommtypekode")
        if comm_type == "TLF" and element.get("telefonnr"):
            return (DataContact.CONTACT_PHONE,
                    get_value(element.get("telefonnr")))
        elif comm_type == "FAX" and element.get("telefonnr"):
            return (DataContact.CONTACT_FAX,
                    get_value(element.get("telefonnr")))
        elif comm_type == "EPOST" and element.get("kommnrverdi"):
            return (DataContact.CONTACT_EMAIL,
                    get_value(element.get("kommnrverdi")))
        elif comm_type == "URL" and element.get("kommnrverdi"):
            return (DataContact.CONTACT_URL,
                    get_value(element.get("kommnrverdi")))

        return None

    def next_object(self, element):

        def get_value(element_value):
            return ensure_unicode(element_value, self.encoding)

        def extract(element_attr):
            return get_value(element.get(element_attr, ""))

        result = DataOU()

        # A lot of data is buried in attributes
        # Own ID -- sko
        sko = tuple([int(element.get(x)) for x in ("fakultetnr",
                                                   "instituttnr",
                                                   "gruppenr")])
        result.add_id(result.NO_SKO, sko)
        # Parent ID -- sko
        sko = tuple([int(element.get(x)) for x in ("fakultetnr_for_org_sted",
                                                   "instituttnr_for_org_sted",
                                                   "gruppenr_for_org_sted")])
        result.parent = (result.NO_SKO, sko)

        # Some weird ID
        if element.get("nsd_kode"):
            result.add_id(result.NO_NSD,
                          get_value(element.get("nsd_kode")))

        # Activity period
        result.start_date = self._make_date(element.get("dato_opprettet"))
        result.end_date = self._make_date(element.get("dato_nedlagt"))
        # Accessibility for catalogues
        if element.get("opprettetmerke_for_oppf_i_kat"):
            result.publishable = True

        for name_kind, candidates, lang in ((result.NAME_LONG,
                                             ("stedlangnavn_bokmal",
                                              "stedkortnavn_bokmal",
                                              "stednavnfullt", "stednavn"),
                                             "nb"),
                                            (result.NAME_LONG,
                                             ("stedlangnavn_engelsk",
                                              "stedkortnavn_engelsk"),
                                             "en"),
                                            (result.NAME_ACRONYM,
                                             ("akronym",),
                                             "nb"),
                                            (result.NAME_SHORT,
                                             ("forkstednavn",),
                                             "nb")):
            value = self._pull_name(element, *candidates)
            if value:
                result.add_name(DataName(name_kind, value, lang))

        for (xmlkind, kind) in (("besok", DataAddress.ADDRESS_BESOK),
                                ("intern", DataAddress.ADDRESS_POST)):
            zip = extract("poststednr_%s_adr" % xmlkind)
            street = None
            if xmlkind == "intern":
                try:
                    p_o_box = int(extract("stedpostboks"))
                    if p_o_box and int(zip) // 100 == 3:
                        street = "Postboks %d Blindern" % p_o_box
                except ValueError:
                    pass
            if street is None:
                street = (extract("adresselinje1_%s_adr" % xmlkind),
                          extract("adresselinje2_%s_adr" % xmlkind))
            result.add_address(
                DataAddress(kind=kind,
                            street=street,
                            zip=zip,
                            city=extract("poststednavn_%s_adr" % xmlkind),
                            country=extract("landnavn_%s_adr" % xmlkind)))

        # FIXME: priority assignment is a bit random at the moment.
        priority = 0
        for sub in element.findall("komm"):
            ct = self._make_contact(sub)
            if ct:
                kind, value = ct
                result.add_contact(DataContact(kind,
                                               get_value(value),
                                               priority))
                priority += 1

        return result
