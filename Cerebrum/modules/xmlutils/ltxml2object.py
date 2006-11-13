# -*- coding: iso-8859-1 -*-
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

from mx.DateTime import Date
import time, sys

from Cerebrum.modules.xmlutils.xml2object import \
     XMLDataGetter, XMLEntity2Object, DataOU, DataAddress, DataContact, \
     HRDataPerson, DataEmployment, DataEntity, DataName

import Cerebrum.modules.no.fodselsnr as fodselsnr





class LTXMLDataGetter(XMLDataGetter):
    """An abstraction layer for LT XML files."""

    def iter_ou(self):
        return self._make_iterator("sted", XMLOU2Object)
    # end iter_ou


    def iter_persons(self):
        return self._make_iterator("person", XMLPerson2Object)
    # end iter_persons
# end LTXMLDataGetter



class XMLPerson2Object(XMLEntity2Object):
    """A converter class that maps ElementTree's Element to LT"""

    def _register_names(self, result, element):
        attr2type = { "fornavn"   : result.NAME_FIRST,
                      "etternavn" : result.NAME_LAST,
                      "tittel_personlig" : result.NAME_TITLE }

        for kind, value in element.items():
            if kind in attr2type:
                result.add_name(DataName(attr2type[kind],
                                         value.encode("latin1")))
            # fi
        # od
    # end _register_names


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
                result.append((DataContact.CONTACT_PHONE, value))
            if comm_type in ("FAX", "FAXUTLAND") and value:
                result.append((DataContact.CONTACT_FAX, value))
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
    # end _make_contact


    def _make_employment(self, elem):
        """Convert element to proper employment record."""
        # There are 3 kinds -- tils, bilag && gjest. All in different
        # formats, of course:
        percentage = code = title = None
        start_date = end_date = None
        category = None
        ou_id = None
        leave = []     
        tag2kind = { "bilag" : DataEmployment.BILAG,
                     "tils"  : DataEmployment.HOVEDSTILLING,
                     "gjest" : DataEmployment.GJEST }
        xml2cat = { "ØVR" : DataEmployment.KATEGORI_OEVRIG,
                    "VIT" : DataEmployment.KATEGORI_VITENSKAPLIG, }
        make_sko = lambda f, i, g: tuple([int(elem.get(x)) for x in (f, i, g)])

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
            code = elem.get("gjestetypekode").encode("latin1")
        elif elem.tag == "tils":
            percentage = float(elem.get("prosent_tilsetting"))
            code = elem.get("stillingkodenr_beregnet_sist").encode("latin1")
            title = elem.get("tittel").encode("latin1")
            if title == "professor II":
                percentage = percentage / 5.0
            # fi
            start_date = self._make_mxdate(elem.get("dato_fra"))
            end_date = self._make_mxdate(elem.get("dato_til"))
            ou_id = (DataOU.NO_SKO,
                     make_sko("fakultetnr_utgift", "instituttnr_utgift",
                              "gruppenr_utgift"))
            if elem.get("hovedkat"):
                category = xml2cat[elem.get("hovedkat").encode("latin1")]
        # fi

        # Handle leave (permisjon).
        for child in elem:
            if child.tag == "permisjon":
                tmp = {}
                tmp['percentage'] = float(child.get("prosent_permisjon"))
                tmp['start_date'] = self._make_mxdate(elem.get("dato_fra"))
                tmp['end_date'] = self._make_mxdate(elem.get("dato_til"))
                leave.append(tmp)
            # fi
        # od

        return DataEmployment(kind = tag2kind[elem.tag],
                              percentage = percentage,
                              code = code, title = title,
                              start = start_date, end = end_date, place = ou_id,
                              category = category,
                              leave = leave)
    # end _make_employment
    

    def next(self):
        element = self._xmliter.next()
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
        extract = lambda y: element.get(y, "").encode("latin1")
        result.address = DataAddress(
            kind = DataAddress.ADDRESS_PRIVATE,
            street = extract("adresselinje1_privatadresse") + " " +
                     extract("adresselinje2_privatadresse"),
            zip = extract("poststednr_privatadresse"),
            city = extract("poststednavn_privatadresse"))
        
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

        #
        # FIXME:
        # 
        # baardj's reservation patch

        # En person har aktiv ansettelse dersom den har en
        # hoved/bistilling, eller er registrert som gjest med
        # gjestetypekode POLS-ANSAT
        has_active = filter(lambda x: (
            x.kind in (DataEmployment.HOVEDSTILLING,
                       DataEmployment.BISTILLING) or (
            x.kind == DataEmployment.GJEST and x.code == "POLS-ANSAT"))
                            and x.is_active(), result.iteremployment())
        if has_active:
            to_reserve = False
            for resv in element.findall("res"):
                if (resv.get("katalogkode") == "ELKAT" and 
                    resv.get("felttypekode") not in ("PRIVADR", "PRIVTLF") and
                    resv.get("resnivakode") != "SAMTYKKE"):
                    to_reserve = True
                # fi
            # od
        else:
            to_reserve = True
            for resv in element.findall("res"):
                if (resv.get("katalogkode") == "ELKAT" and
                    resv.get("felttypekode") not in ("PRIVADR", "PRIVTLF")):
                    to_reserve = resv.get("resnivakode") != "SAMTYKKE"
                # fi
            # od
        # fi
        result.reserved = to_reserve
        tmp = element.get("fakultetnr_for_lonnsslip")
        if tmp:
            result.primary_ou = ("185",
                                 extract("fakultetnr_for_lonnsslip"),
                                 extract("instituttnr_for_lonnsslip"),
                                 extract("gruppenr_for_lonnsslip"))

        if not (result.get_name(result.NAME_FIRST) and
                result.get_name(result.NAME_LAST)):
            raise AssertionError, ("Missing name for %s" %
                                   list(result.iterids()))
        # fi
                   
        # alternative reservation rules. Probably not applicable anymore.
        # 
        # TODO: Use something "a bit more defined and permanent". This is a
        # hack. For now we set a reservation on non-guests with any 'ELKAT'
        # reservation except 'PRIVADR' and 'PRIVTLF', and on guests without
        # 'ELKAT'+'GJESTEOPPL' anti-reservations.
        # step 1: We reserve, if a person has active <guest> but no active
        # <tils>
        # to_reserve = (filter(lambda x: x.kind == DataEmployment.GJEST and
        #                     x.is_active(), result.iteremployment()) and
        #              filter(lambda x: x.kind in (DataEmployment.HOVEDSTILLING,
        #                                          DataEmployment.BISTILLING,) and
        #                     x.is_active(), result.iteremployment()))
        # for sub in element.findall("res"):
        #    if (sub.get("katalogkode") == "ELKAT" and 
        #        sub.get("felttypekode") not in ("PRIVADR", "PRIVTLF")):
        #        to_reserve = sub.get("felttypekode") != "GJESTEOPPL"
        #    # fi
        # # od
        # result.reserved = to_reserve

        return result
    # end next
# end XMLPerson2Object



class XMLOU2Object(XMLEntity2Object):
    """A converter class that maps ElementTree's Element to DataOU."""

    def _pull_name(self, element, *possible_keys):
        """Return a first of possible_keys that is present in element."""
        for key in possible_keys:
            if element.get(key):
                value = element.get(key).encode("latin1")
                return value
            # fi
        # od

        # NB! A name that is not there *must* be represented as None. "" (empty
        # string) is NOT the same as no name.
        return None
    # end _pull_name


    def _make_contact(self, element):
        comm_type = element.get("kommtypekode")

        if comm_type == "TLF" and element.get("telefonnr"):
            return (DataContact.CONTACT_PHONE, element.get("telefonnr"))
        elif comm_type == "FAX" and element.get("telefonnr"):
            return (DataContact.CONTACT_FAX, element.get("telefonnr"))
        elif comm_type == "EPOST" and element.get("kommnrverdi"):
            return (DataContact.CONTACT_EMAIL, element.get("kommnrverdi"))
        elif comm_type == "URL" and element.get("kommnrverdi"):
            return (DataContact.CONTACT_URL, element.get("kommnrverdi"))
        # fi

        return None
    # end _make_contact

    
    def next(self):

        element = self._xmliter.next()
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
            result.add_id(result.NO_NSD, element.get("nsd_kode"))
        # fi

        # Activity period
        result.start_date = self._make_mxdate(element.get("dato_opprettet"))
        result.end_date = self._make_mxdate(element.get("dato_nedlagt"))
        # Accessibility for catalogues
        if element.get("opprettetmerke_for_oppf_i_kat"):
            result.publishable = True
        # fi

        for name_kind, candidates, lang in ((result.NAME_LONG,
                                             ("stedlangnavn_bokmal",
                                              "stedkortnavn_bokmal",
                                              "stednavnfullt", "stednavn"),
                                             "no"),
                                            (result.NAME_LONG,
                                             ("stedlangnavn_engelsk",
                                              "stedkortnavn_engelsk"),
                                             "en"),
                                            (result.NAME_ACRONYM,
                                             ("akronym",),
                                             "no"),
                                            (result.NAME_SHORT,
                                             ("forkstednavn",),
                                             "no")):
            result.add_name(DataName(name_kind,
                                     self._pull_name(element, *candidates),
                                     lang))
        # od

        extract = lambda y: element.get(y, "").encode("latin1")
        for (xmlkind, kind) in (("besok", DataAddress.ADDRESS_BESOK),
                                ("intern", DataAddress.ADDRESS_INTERN)):
            result.add_address(
                DataAddress(kind = kind,
                            street = extract("adresselinje1_%s_adr" % xmlkind) +
                                     extract("adresselinje2_%s_adr" % xmlkind),
                            zip = extract("poststednr_%s_adr" % xmlkind),
                            city = extract("poststednavn_%s_adr" % xmlkind),
                            country = extract("landnavn_%s_adr" % xmlkind)))
        # od

        # FIXME: priority assignment is a bit random at the moment.
        priority = 0
        for sub in element.findall("komm"):
            ct = self._make_contact(sub)
            if ct:
                kind, value = ct
                result.add_contact(DataContact(kind, value, priority))
                priority += 1
            # fi
        # od

        return result
    # end next
# end XMLOU2Object





# arch-tag: 38d18853-6d9a-4da6-aa78-70d62d2e1704

