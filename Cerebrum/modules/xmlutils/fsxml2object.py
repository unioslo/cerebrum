# -*- coding: utf-8 -*-
#
# Copyright 2007-2025 University of Oslo, Norway
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
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import copy

from Cerebrum.modules.xmlutils.xml2object import (
    DataAddress,
    DataContact,
    DataName,
    DataOU,
    XMLDataGetter,
    XMLEntity2Object,
    XMLEntityIterator,
    ensure_unicode,
)


class FSOU(DataOU):
    """Class for representing FS-specific information about OUs."""

    # magic number + geographical code (forretningsområdekode), where
    # applicable. This magic key is registered in FS, rather than SAP.
    NO_SAP_ID = "sap-ou-id"

    def validate_id(self, kind, value):
        if kind in (self.NO_SAP_ID,):
            return
        super(FSOU, self).validate_id(kind, value)


class FSXMLDataGetter(XMLDataGetter):
    """An abstraction layer for FS XML files."""

    def iter_ou(self):
        return self._make_iterator("sted", XMLOU2Object)


class XMLOU2Object(XMLEntity2Object):
    """An iterator over OU elements in XML files generated from FS."""

    def _pull_name(self, element, attribute_name):
        if element.get(attribute_name):
            value = ensure_unicode(element.get(attribute_name), self.encoding)
            return value
        return None

    def _make_contact(self, element):
        """Return a DataContact entry corresponding to a given XML element."""

        comm_type = ensure_unicode(element.get("kommtypekode"), self.encoding)
        value = ensure_unicode(element.get("kommnrverdi"), self.encoding)

        if not value:
            return None, None

        if comm_type == "TLF":
            return DataContact.CONTACT_PHONE, value
        elif comm_type == "FAX":
            return DataContact.CONTACT_FAX, value
        elif comm_type == "EKSTRA TLF":
            return DataContact.CONTACT_PHONE, value

        return None, None

    def next_object(self, element):
        """Returns a DataEntity representation of the 'next' XML element."""
        result = FSOU()
        sko = tuple(int(element.get(x))
                    for x in ("fakultetnr", "instituttnr", "gruppenr"))
        result.add_id(result.NO_SKO, sko)
        # Parent ID - sko
        sko = tuple(int(element.get(x))
                    for x in ("fakultetnr_for_org_sted",
                              "instituttnr_for_org_sted",
                              "gruppenr_for_org_sted"))
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
        for name_kind, xmlname, lang in (
                (result.NAME_LONG, "stednavn", "nb"),
                (result.NAME_SHORT, "forkstednavn", "nb"),
                (result.NAME_ACRONYM, "akronym", "nb")):
            value = self._pull_name(element, xmlname)
            if value:
                result.add_name(DataName(name_kind, value, lang))

        # addresses
        def _extract_addr(field):
            return ensure_unicode(element.get(field, ""), self.encoding)

        for xmlkind, address_kind in (("besok", DataAddress.ADDRESS_BESOK),
                                      ("intern", DataAddress.ADDRESS_POST)):
            zipcode = _extract_addr("poststednr_%s_adr" % xmlkind)
            street = (_extract_addr("adresselinje1_%s_adr" % xmlkind),
                      _extract_addr("adresselinje2_%s_adr" % xmlkind))
            result.add_address(
                DataAddress(
                    kind=address_kind,
                    street=street,
                    zip=zipcode,
                    city="",
                    country="",
                )
            )

        # contact information
        priority = 0
        for subelement in element.findall("komm"):
            kind, value = self._make_contact(subelement)
            if kind and value:
                result.add_contact(DataContact(kind, value, priority))
                priority += 1

        # We require a sko from FS ...
        if not result.get_id(result.NO_SKO):
            self.logger.warning("OU %s is missing stedkode. Skipped", result)
            return None

        # ... and a name
        if not result.get_name(result.NAME_LONG):
            self.logger.warning("OU %s is missing name. Skipped", result)
            return None
        return result


class EduDataGetter(XMLDataGetter):
    "An abstraction layer for FS files pertaining to educational information."

    def __fix_iterator(self, element, fields):
        # We are cheating here somewhat: _make_iterator() expects a class, not
        # a callable that returns one. However, a callable would do as well,
        # given how class is used in XMLDataGetter.
        return self._make_iterator(
            element,
            lambda iterator, logger, encoding:
                EduKind2Object(iterator, logger, fields, encoding))

    def iter_stprog(self, tag="studprog"):
        return self.__fix_iterator(tag,
                                   ("studieprogramkode",
                                    "status_utdplan",
                                    "institusjonsnr_studieansv",
                                    "faknr_studieansv",
                                    "instituttnr_studieansv",
                                    "gruppenr_studieansv",
                                    "status_utgatt",
                                    "studieprognavn",
                                    "status_eksport_lms",))

    def iter_undenh(self, tag="enhet"):
        return self.__fix_iterator(tag, ("institusjonsnr",
                                         "terminnr",
                                         "terminkode",
                                         "emnekode",
                                         "arstall",
                                         "versjonskode",
                                         "status_eksport_lms",
                                         "institusjonsnr_kontroll",
                                         "faknr_kontroll",
                                         "instituttnr_kontroll",
                                         "gruppenr_kontroll",
                                         "emnenavn_bokmal",
                                         "emnenavnfork",
                                         "lmsrommalkode",))

    def iter_undakt(self, tag="aktivitet"):
        return self.__fix_iterator(tag, ("institusjonsnr",
                                         "terminnr",
                                         "terminkode",
                                         "emnekode",
                                         "arstall",
                                         "versjonskode",
                                         "aktivitetkode",
                                         "status_eksport_lms",
                                         "aktivitetsnavn",
                                         "institusjonsnr_kontroll",
                                         "faknr_kontroll",
                                         "instituttnr_kontroll",
                                         "gruppenr_kontroll",
                                         "lmsrommalkode",))

    def iter_evu(self, tag="evu"):
        return self.__fix_iterator(tag, ("kurstidsangivelsekode",
                                         "etterutdkurskode",
                                         "status_eksport_lms",
                                         "institusjonsnr_adm_ansvar",
                                         "faknr_adm_ansvar",
                                         "instituttnr_adm_ansvar",
                                         "gruppenr_adm_ansvar",
                                         "etterutdkursnavn",
                                         "lmsrommalkode",))

    def iter_kursakt(self, tag="kursakt"):
        return self.__fix_iterator(tag, ("kurstidsangivelsekode",
                                         "etterutdkurskode",
                                         "aktivitetskode",
                                         "status_eksport_lms",
                                         "aktivitetsnavn",
                                         "lmsrommalkode",))

    def iter_kull(self, tag="kull"):
        return self.__fix_iterator(tag, ("arstall",
                                         "studieprogramkode",
                                         "terminkode",
                                         "institusjonsnr_studieansv",
                                         "faknr_studieansv",
                                         "instituttnr_studieansv",
                                         "gruppenr_studieansv",
                                         "studiekullnavn",
                                         "lmsrommalkode",))


class EduGenericIterator(XMLEntityIterator):
    """
    A convenience class -- iterates over XML element attributes as dicts.
    """
    def __next__(self):
        element = super(EduGenericIterator, self).__next__()
        return dict(element.items())

    next = __next__


class EduKind2Object(XMLEntity2Object):

    def __init__(self, iterator, logger, required_attributes, encoding):
        super(EduKind2Object, self).__init__(iterator, logger, encoding)
        self._required_attributes = copy.deepcopy(required_attributes)

    def next_object(self, subtree):
        return dict((x, subtree.get(x)) for x in self._required_attributes)
