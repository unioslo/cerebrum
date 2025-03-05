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
This module implements an abstraction layer for SAPUiO-compatible data.

SAPUiO compatible data comes in the form of XML files with employees and/or
org-units.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import datetime

from Cerebrum.modules.xmlutils.xml2object import (
    DataAddress,
    DataContact,
    DataName,
    DataOU,
    HRDataPerson,
    XMLDataGetter,
    XMLEntity2Object,
    ensure_unicode,
)
from Cerebrum.utils import date_compat


def deuglify_phone(phone):
    """Remove junk like ' ' and '-' from phone numbers."""

    for junk in (" ", "-"):
        phone = phone.replace(junk, "")

    return phone


class SAPPerson(HRDataPerson):

    """Class for representing SAP_specific information about people."""

    SAP_NR = "Ansattnr"

    def validate_id(self, kind, value):
        if kind in (self.SAP_NR,):
            return

        super(SAPPerson, self).validate_id(kind, value)


def make_sko(data):
    """Make a sko, (faculty, institute, group)-tuple, out of data."""

    # FIXME: re?
    try:
        int(data)
    except Exception:
        # TBD: What do we do here?
        return None
    # yrt

    return tuple([int(x) for x in (data[:2], data[2:4], data[4:])])


class SAPXMLDataGetter(XMLDataGetter):
    """An abstraction layer for SAP XML files."""

    def iter_ou(self, **kwargs):
        return self._make_iterator("sap2bas_sted", XMLOU2Object, **kwargs)


class XMLOU2Object(XMLEntity2Object):

    """A converter class that maps ElementTree's Element to DataOU."""

    # TBD: Bind it to Cerebrum constants?
    tag2type = {
        "Stedkode": DataOU.NO_SKO,
        "Akronym": DataOU.NAME_ACRONYM,
        "DfoOrgId": DataOU.NO_DFO,
        "OrgRegOuId": DataOU.NO_ORGREG,
        "Navn20": DataOU.NAME_SHORT,
        "Navn120": DataOU.NAME_LONG,
    }

    def _make_contact(self, element):
        comm_type = element.find("Type")
        value = element.find("Verdi")
        if comm_type is None or value is None or value.text is None:
            return None

        priority = element.find("Prioritet")
        if (
                priority is not None and
                priority.text is not None and
                priority.text.isdigit()
        ):
            priority = int(priority.text)
        else:
            return None

        comm2const = {
            "E-post adresse": DataContact.CONTACT_EMAIL,
            "Telefax": DataContact.CONTACT_FAX,
            "Telefon1": DataContact.CONTACT_PHONE,
            "Telefon2": DataContact.CONTACT_PHONE,
            "URL": DataContact.CONTACT_URL,
        }
        comm_type = ensure_unicode(comm_type.text, self.encoding)
        if comm_type not in comm2const:
            return None

        value = ensure_unicode(value.text, self.encoding)
        if comm_type in ("Telefax", "Telefon1", "Telefon2"):
            value = deuglify_phone(value)

        return DataContact(comm2const[comm_type], value, priority)

    def _make_address(self, element):
        def ext(subelm):
            answer = element.find(subelm)
            if answer is not None and answer.text:
                return ensure_unicode(answer.text, self.encoding)
            return ""
        # end

        kind = ext("Type")
        if not kind:
            return None

        xml2kind = {
            "Besøksadresse": DataAddress.ADDRESS_BESOK,
            "Postadresse": DataAddress.ADDRESS_POST,
        }
        if kind not in xml2kind:
            return None
        result = DataAddress(
            kind=xml2kind[kind],
            street=(ext("CO"),
                    ext("Gateadresse"),
                    ext("Adressetillegg")),
            zip=ext("Postnummer"),
            city=ext("Poststed"),
            country=ext("Landkode")
        )
        return result

    def _make_names(self, sub):
        """Extract name information from XML element sub."""

        tag2kind = {"Akronym": DataOU.NAME_ACRONYM,
                    "Navn20": DataOU.NAME_SHORT,
                    "Navn120": DataOU.NAME_LONG, }

        language = sub.findtext(".//Sprak")
        # Accumulate the results. One <stednavn> gives rise to several
        # DataName instances.
        result = list()
        for tmp in sub.getiterator():
            if tmp.tag not in tag2kind or not tmp.text:
                continue

            # Common mistake. The keys are, like, right next to each other.
            if language.lower() == "no":
                language = "nb"

            # It has been decided that we need to consider nn/nb/en only
            if language.lower() not in ("nn", "nb", "ny", "en"):
                continue
            result.append(DataName(tag2kind[tmp.tag],
                                   ensure_unicode(tmp.text.strip(),
                                                  self.encoding),
                                   language))

        return result

    def next_object(self, element):
        """Return the next DataOU object."""

        result = DataOU()

        # IVR 2007-12-24 FIXME: One of the attributes is special, and tags the
        # OU's intended usage code (bruksområde). Find out which attribute
        # this is.
        # Iterate over *all* subelements
        for sub in element.getiterator():
            value = None
            if sub.text:
                value = ensure_unicode(sub.text.strip(), self.encoding)
            if sub.tag in ("DfoOrgId", "OrgRegOuId"):
                result.add_id(self.tag2type[sub.tag], value)
            if sub.tag == "Stedkode":
                sko = make_sko(value)
                if sko is not None:
                    result.add_id(self.tag2type[sub.tag], sko)
                else:
                    # invalid value for the <Stedkode> tag
                    if self.logger:
                        self.logger.warning(
                            'Detected XML <Stedkode> '
                            'tag with invalid value: %s',
                            value
                        )
            elif sub.tag == "Overordnetstedkode":
                sko = make_sko(value)
                if sko is not None:
                    result.parent = (result.NO_SKO, sko)
            elif sub.tag == "Navn":
                for name in self._make_names(sub):
                    result.add_name(name)
            elif sub.tag in ("Adresse",):
                result.add_address(self._make_address(sub))
            elif sub.tag in ("Startdato", "Sluttdato"):
                date = self._make_date(sub.text, format="%Y-%m-%d")
                if sub.tag == "Startdato":
                    result.start_date = date
                else:
                    result.end_date = date

        # Whether the OU can be published in various online directories
        result.publishable = False
        for tmp in element.findall(".//Bruksomrade/Type"):
            if tmp.text == "Tillatt Organisasjon":
                result.publishable = True
            # <StedType> tell us how an OU can be used. This information is
            # represented in Cerebrum with the help of spreads and can be
            # accessed via the EntitySpread interface.
            result.add_usage_code(tmp.text)

        celems = element.findall("Kommunikasjon")
        for sub in celems:
            ct = self._make_contact(sub)
            if ct:
                result.add_contact(ct)

        # We require an OU to have a name.
        # Ideally, the information about expired OUs should be complete as
        # well, but we won't be this lucky in our lifetimes. So, for expired
        # OUs we won't care about the names.
        # Neither do we care about the missing names of not yet active
        # OUs; we choose to hope that the names will be in place when
        # the OU becomes active.
        if result.get_name(DataOU.NAME_LONG) is None:
            ou_no_sko_str = result.get_id(DataOU.NO_SKO)
            if not ou_no_sko_str:
                ou_no_sko_str = 'Missing a valid NO_SKO value'

            start_date = date_compat.get_date(result.start_date)
            end_date = date_compat.get_date(result.end_date)
            today = datetime.date.today()

            if end_date and end_date < today:
                if self.logger:
                    self.logger.debug("No name for expired OU %s",
                                      ou_no_sko_str)
            elif start_date and start_date > today:
                if self.logger:
                    self.logger.debug("No name for future OU %s",
                                      ou_no_sko_str)
            else:
                if self.logger:
                    self.logger.warning("No name available for OU %s",
                                        ou_no_sko_str)
                return None

        return result
