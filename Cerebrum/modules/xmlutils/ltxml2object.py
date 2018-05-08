# -*- coding: utf-8 -*-
# Copyright 2005 University of Oslo, Norway
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
This module implements an abstraction layer for LT-originated data.
"""
from __future__ import unicode_literals

from mx.DateTime import Date

import cereconf
from Cerebrum.modules.xmlutils.xml2object import (
    DataAddress,
    DataContact,
    DataEmployment,
    # DataEntity,
    DataName,
    DataOU,
    HRDataPerson,
    XMLDataGetter,
    XMLEntity2Object,
    ensure_unicode,
)
import Cerebrum.modules.no.fodselsnr as fodselsnr


class LTXMLDataGetter(XMLDataGetter):
    """An abstraction layer for LT XML files."""

    def iter_ou(self):
        return self._make_iterator("sted", XMLOU2Object)

    def iter_person(self):
        return self._make_iterator("person", XMLPerson2Object)


class XMLPerson2Object(XMLEntity2Object):
    """A converter class that maps ElementTree's Element to LT"""

    def _register_names(self, result, element):
        attr2type = {
            "fornavn": result.NAME_FIRST,
            "etternavn": result.NAME_LAST,
            "tittel_personlig": result.NAME_TITLE,
        }

        for kind, value in element.items():
            if kind in attr2type:
                result.add_name(DataName(attr2type[kind],
                                         ensure_unicode(value, self.encoding)))

    def _make_contact(self, elem, contact_prefs):
        """Derive contact information from LT data.

        We do not have the exact meanings, so this is guesswork. One element
        can result in multiple contact entries.
        """

        result = list()
        if elem.tag == "arbtlf":
            if int(elem.get("telefonnr")):
                result.append((DataContact.CONTACT_PHONE,
                               elem.get("telefonnr")))
            if int(elem.get("linjenr")):
                result.append((DataContact.CONTACT_PHONE,
                               "%i%05i" % (int(elem.get("innvalgnr")),
                                           int(elem.get("linjenr")))))
            # fi
        elif elem.tag == "komm":
            comm_type = elem.get("kommtypekode")
            value = elem.get("kommnrverdi", elem.get("telefonnr", None))
            if (comm_type in ("ARBTLF", "EKSTRA TLF", "JOBBTLFUTL",) and
                    value):
                result.append((DataContact.CONTACT_PHONE,
                               ensure_unicode(value, self.encoding)))
            if comm_type in ("FAX", "FAXUTLAND") and value:
                result.append((DataContact.CONTACT_FAX,
                               ensure_unicode(value, self.encoding)))
            # fi
        # fi

        # Since we do not have priority data, we'll simple assign priorities
        # on per category basis.
        tmp = list()
        for c_kind, c_value in result:
            priority = contact_prefs.get(c_kind, 0)
            contact_prefs[c_kind] = priority + 1
            tmp.append(DataContact(c_kind, c_value, priority))
        # od

        return tmp

    def _make_employment(self, elem):
        """Convert element to proper employment record."""
        # There are 3 kinds -- tils, bilag && gjest. All in different
        # formats, of course:
        percentage = code = title = None
        start_date = end_date = None
        category = None
        ou_id = None
        leave = []
        tag2kind = {
            "bilag": DataEmployment.BILAG,
            "tils": DataEmployment.HOVEDSTILLING,
            "gjest": DataEmployment.GJEST,
        }
        xml2cat = {
            "ØVR": DataEmployment.KATEGORI_OEVRIG,
            "VIT": DataEmployment.KATEGORI_VITENSKAPLIG,
        }

        def make_sko(f, i, g):
            return tuple([int(elem.get(x)) for x in (f, i, g)])

        if elem.tag == "bilag":
            end_date = self._make_mxdate(elem.get("dato_oppgjor"))
            ou_id = (DataOU.NO_SKO,
                     make_sko("fakultetnr_kontering", "instituttnr_kontering",
                              "gruppenr_kontering"))
        elif elem.tag == "gjest":
            ou_id = (DataOU.NO_SKO,
                     make_sko("fakultetnr", "instituttnr", "gruppenr"))
            start_date = self._make_mxdate(elem.get("dato_fra"))
            end_date = self._make_mxdate(elem.get("dato_til"))
            code = ensure_unicode(elem.get("gjestetypekode"), self.encoding)
        elif elem.tag == "tils":
            percentage = float(elem.get("prosent_tilsetting"))
            code = ensure_unicode(elem.get("stillingkodenr_beregnet_sist"),
                                  self.encoding)
            title = ensure_unicode(elem.get("tittel"), self.encoding)
            if title == "professor II":
                percentage = percentage / 5.0
            # fi
            start_date = self._make_mxdate(elem.get("dato_fra"))
            end_date = self._make_mxdate(elem.get("dato_til"))
            ou_id = (DataOU.NO_SKO,
                     make_sko("fakultetnr_utgift", "instituttnr_utgift",
                              "gruppenr_utgift"))
            if elem.get("hovedkat"):
                category = xml2cat[ensure_unicode(elem.get("hovedkat"),
                                                  self.encoding)]

        # Handle leave (permisjon).
        for child in elem:
            if child.tag == "permisjon":
                tmp = {}
                tmp['percentage'] = float(child.get("prosent_permisjon"))
                tmp['start_date'] = self._make_mxdate(elem.get("dato_fra"))
                tmp['end_date'] = self._make_mxdate(elem.get("dato_til"))
                leave.append(tmp)

        return DataEmployment(kind=tag2kind[elem.tag],
                              percentage=percentage,
                              code=code, title=title,
                              start=start_date, end=end_date, place=ou_id,
                              category=category,
                              leave=leave)

    def next_object(self, element):

        def get_value(element_value):
            return ensure_unicode(element_value, self.encoding)

        def extract(element_attr):
            return get_value(element.get(element_attr, ""))

        result = HRDataPerson()

        # Pull out all names
        self._register_names(result, element)
        # Pull out fnr
        tmp = "%02d%02d%02d%05d" % tuple([int(element.get(x))
                                          for x in ("fodtdag",
                                                    "fodtmnd",
                                                    "fodtar",
                                                    "personnr")])
        fnr = fodselsnr.personnr_ok(tmp)
        result.add_id(result.NO_SSN, fnr)
        # Since LT does not provide birth date directly, we extract it from fnr
        result.birth_date = Date(*fodselsnr.fodt_dato(fnr))
        # ... and gender
        if fodselsnr.er_mann(fnr):
            result.gender = result.GENDER_MALE
        else:
            result.gender = result.GENDER_FEMALE
        # fi
        # Register address
        # extract = lambda y: ensure_unicode(element.get(y, ""), self.encoding)
        result.address = DataAddress(
            kind=DataAddress.ADDRESS_PRIVATE,
            street=(extract("adresselinje1_privatadresse"),
                    extract("adresselinje2_privatadresse")),
            zip=extract("poststednr_privatadresse"),
            city=extract("poststednavn_privatadresse"))

        # Contact information and jobs
        # FIXME: We do not have anything more intelligent for priorities
        priorities = dict()
        for sub in element.getiterator():
            if sub.tag in ("bilag", "gjest", "tils",):
                emp = self._make_employment(sub)
                result.add_employment(emp)
            elif sub.tag in ("komm", "arbtlf",):
                for contact in self._make_contact(sub, priorities):
                    result.add_contact(contact)
                # od
        # od

        # Reservation rules. Roughly, all employees are not reserved, unless
        # they say otherwise. Everyone else *is* reserved, unless they
        # explicitly allow publication in catalogues.
        has_active = result.has_active_employments()
        if has_active:
            to_reserve = False
            for resv in element.findall("res"):
                if (resv.get("katalogkode") == "ELKAT" and
                        resv.get("felttypekode") not in
                        ("PRIVADR", "PRIVTLF") and
                        resv.get("resnivakode") != "SAMTYKKE"):
                    to_reserve = True
        else:
            to_reserve = True
            for resv in element.findall("res"):
                if (resv.get("katalogkode") == "ELKAT" and
                        resv.get("felttypekode") not in
                        ("PRIVADR", "PRIVTLF")):
                    to_reserve = resv.get("resnivakode") != "SAMTYKKE"
        result.reserved = to_reserve
        if (element.get("fakultetnr_for_lonnsslip") and
                element.get("instituttnr_for_lonnsslip") and
                element.get("gruppenr_for_lonnsslip")):
            result.primary_ou = (cereconf.DEFAULT_INSTITUSJONSNR,
                                 extract("fakultetnr_for_lonnsslip"),
                                 extract("instituttnr_for_lonnsslip"),
                                 extract("gruppenr_for_lonnsslip"))

        if not (result.get_name(result.NAME_FIRST) and
                result.get_name(result.NAME_LAST)):
            raise AssertionError("Missing name for %s" %
                                 list(result.iterids()))

        return result


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
        result.start_date = self._make_mxdate(element.get("dato_opprettet"))
        result.end_date = self._make_mxdate(element.get("dato_nedlagt"))
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
                                               self.get_value(value),
                                               priority))
                priority += 1

        return result
