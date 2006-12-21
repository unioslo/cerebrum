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
This module implements an abstraction layer for SAP-originated data.

Specifically, we build the datagetter API for XML SAP data sources. For now,
this means mapping XML-elements stemming from SAP data files to objects in
datagetter.

TBD: This comment does not belong here
The overall workflow looks like this:

* SAPXMLDataGetter creates an iterator over the XML elements (either from an
  in-memory document tree (faster for smaller files) or directly from file
  (faster for larger data sets). The break even point seems to be around
  3000-4000 elements).

* XMLPerson2Object provides an iterator that consumes ElementTree elements
  and provides SAPPerson objects as output.
"""

from mx.DateTime import Date
import time, sys

from Cerebrum.modules.xmlutils.xml2object import \
     XMLDataGetter, XMLEntity2Object, HRDataPerson, DataAddress, \
     DataEmployment, DataOU, DataContact, DataName

from Cerebrum.modules.no.fodselsnr import personnr_ok





def deuglify_phone(phone):
    """Remove junk like ' ' and '-' from phone numbers."""

    for junk in (" ", "-"):
        phone = phone.replace(junk, "")
    # od

    return phone
# end deuglify_phone



class SAPPerson(HRDataPerson):
    """Class for representing SAP_specific information about people."""

    SAP_NR = "Ansattnr"
    
    def validate_id(self, kind, value):
        if kind in (self.SAP_NR,):
            return

        super(SAPPerson, self).validate_id(kind, value)
    # end validate_id
# end SAPPerson



def make_sko(data):
    """Make a sko, (faculty, institute, group)-tuple, out of data."""
    
    # FIXME: re?
    try:
        int(data)
    except:
        # TBD: What do we do here?
        return None
    # yrt
        
    return tuple([int(x) for x in data[:2], data[2:4], data[4:]])
# end _make_sko



class SAPXMLDataGetter(XMLDataGetter):
    """An abstraction layer for SAP XML files."""

    def iter_persons(self):
        return self._make_iterator("sap_basPerson", XMLPerson2Object)
    # end iter_persons


    def iter_ou(self):
        return self._make_iterator("sap2bas_skode", XMLOU2Object)
    # end iter_ou

# end SAPXMLDataGetter        



class XMLOU2Object(XMLEntity2Object):
    """A converter class that maps ElementTree's Element to DataOU."""

    # TBD: Bind it to Cerebrum constants?
    tag2type = { "Stedkode" : DataOU.NO_SKO,
                 "Akronym"  : DataOU.NAME_ACRONYM,
                 "Kortnavn" : DataOU.NAME_SHORT,
                 "Langnavn" : DataOU.NAME_LONG,
                 }

    def __init__(self, xmliter):
        super(XMLOU2Object, self).__init__(xmliter)
    # end


    def _make_contact(self, element):
        comm_type = element.find("Stedknavn")
        value = element.find("Stedkomm")
        if comm_type is None or value is None:
            return None
        # fi

        priority = element.find("Stedprio")
        if priority is not None and priority.text is not None:
            priority = int(priority.text)
        # fi

        comm2const = { "E-post adresse" : DataContact.CONTACT_EMAIL,
                       "Telefax"        : DataContact.CONTACT_FAX,
                       "Telefon1"       : DataContact.CONTACT_PHONE,
                       "Telefon2"       : DataContact.CONTACT_PHONE,
                       "URL"            : DataContact.CONTACT_URL, }
        comm_type = comm_type.text.encode("latin1")
        if comm_type not in comm2const:
            return None
        # fi
        value = value.text.encode("latin1")

        if comm_type in ("Telefax", "Telefon1", "Telefon2"):
            value = deuglify_phone(value)
        # fi

        return DataContact(comm2const[comm_type], value, priority)
    # end _make_contact


    def _make_address(self, element):
        def ext(subelm):
            answer = element.find(subelm)
            if answer is not None and answer.text:
                return answer.text.encode("latin1")

            return ""
        # end

        kind = ext("AdressType")
        if not kind: return None

        xml2kind = { "Besøksadresse" : DataAddress.ADDRESS_BESOK,
                     "Postadresse"   : DataAddress.ADDRESS_POST, }
        if kind not in xml2kind:
            return None
        # fi

        result = DataAddress(kind = xml2kind[kind],
                             street = (ext("Cnavn"),
                                       ext("Gatenavn1"),
                                       ext("Gatenavn2")),
                             zip = ext("Postnummer"),
                             city = ext("Poststed"),
                             country = ext("Landkode"))
        return result
    # end _make_address


    def _make_names(self, sub):
        """Extract name information from XML element sub."""

        tag2kind = { "Akronym"  : DataOU.NAME_ACRONYM,
                     "Kortnavn" : DataOU.NAME_SHORT,
                     "Langnavn" : DataOU.NAME_LONG, }

        language = sub.findtext(".//Sap_navn_spraak")
        # Accumulate the results. One <stednavn> gives rise to several
        # DataName instances.
        result = list()
        for tmp in sub.getiterator():
            if tmp.tag not in tag2kind or not tmp.text:
                continue
            # fi
            
            result.append(DataName(tag2kind[tmp.tag],
                                   tmp.text.strip().encode("latin1"),
                                   language))
        # od

        return result
    # end _make_names


    def next(self):
        """Return the next SAPPerson object.

        Consume the next XML-element describing a person, and return a
        suitable representation (DataOU).
        """

        # This call with propagate StopIteration when all the (XML) elements
        # are exhausted.
        element = super(XMLOU2Object, self).next()
        result = DataOU()

        # Iterate over *all* subelements
        for sub in element.getiterator():
            value = None
            if sub.text:
                value = sub.text.strip().encode("latin1")

            if sub.tag == "Stedkode":
                sko = make_sko(value)
                if sko is not None:
                    result.add_id(self.tag2type[sub.tag], sko)
                # fi
            elif sub.tag == "Overordnetsted":
                if value:
                    result.parent = (result.NO_SKO, make_sko(value))
                # fi
            elif sub.tag == "stednavn":
                for name in self._make_names(sub):
                    result.add_name(name)
                # od
            elif sub.tag in ("stedadresse",):
                result.add_address(self._make_address(sub))
            elif sub.tag in ("Start_Date", "End_Date"):
                date = self._make_mxdate(sub.text)
                if sub.tag == "Start_Date":
                    result.start_date = date
                else:
                    result.end_date = date
                # fi
            # fi
        # od

        # Katalogmerke
        mark = False
        for tmp in element.findall(".//stedbruk/StedType"):
            if tmp.text == "Elektronisk katalog":
                mark = True
                break
            # fi
        # od
        result.publishable = mark

        celems = element.findall("stedkomm")
        for sub in celems:
            ct = self._make_contact(sub)
            if ct:
                result.add_contact(ct)
            # fi
        # od

        assert result.get_name(DataOU.NAME_LONG) is not None, \
               "No name available for OU %s" % str(result.get_id(DataOU.NO_SKO))

        return result
    # end next
# end XMLOU2Object



class XMLPerson2Object(XMLEntity2Object):
    """A converter class that maps ElementTree's Element to SAPPerson."""

    # This is beyond horrible. This crap *MUST* go, as soon as SAP gets its
    # act together and starts tagging the employment info properly.
    stilling2kode = { 1304 : DataEmployment.KATEGORI_OEVRIG, 1260 : DataEmployment.KATEGORI_VITENSKAPLIG, 8013 : DataEmployment.KATEGORI_VITENSKAPLIG, 1077 : DataEmployment.KATEGORI_OEVRIG, 1070 : DataEmployment.KATEGORI_OEVRIG, 1379 : DataEmployment.KATEGORI_OEVRIG, 1378 : DataEmployment.KATEGORI_VITENSKAPLIG, 1094 : DataEmployment.KATEGORI_OEVRIG, 1095 : DataEmployment.KATEGORI_OEVRIG, 1097 : DataEmployment.KATEGORI_OEVRIG, 1028 : DataEmployment.KATEGORI_OEVRIG, 1027 : DataEmployment.KATEGORI_OEVRIG, 1069 : DataEmployment.KATEGORI_OEVRIG, 1068 : DataEmployment.KATEGORI_OEVRIG, 1061 : DataEmployment.KATEGORI_OEVRIG, 1010 : DataEmployment.KATEGORI_VITENSKAPLIG, 1063 : DataEmployment.KATEGORI_OEVRIG, 1062 : DataEmployment.KATEGORI_OEVRIG, 1065 : DataEmployment.KATEGORI_OEVRIG, 1064 : DataEmployment.KATEGORI_OEVRIG, 829 : DataEmployment.KATEGORI_OEVRIG, 1060 : DataEmployment.KATEGORI_OEVRIG, 1410 : DataEmployment.KATEGORI_OEVRIG, 1411 : DataEmployment.KATEGORI_OEVRIG, 826 : DataEmployment.KATEGORI_OEVRIG, 1087 : DataEmployment.KATEGORI_OEVRIG, 1085 : DataEmployment.KATEGORI_OEVRIG, 1084 : DataEmployment.KATEGORI_OEVRIG, 8031 : DataEmployment.KATEGORI_OEVRIG, 1082 : DataEmployment.KATEGORI_OEVRIG, 8032 : DataEmployment.KATEGORI_OEVRIG, 1088 : DataEmployment.KATEGORI_OEVRIG, 830 : DataEmployment.KATEGORI_OEVRIG, 835 : DataEmployment.KATEGORI_OEVRIG, 1408 : DataEmployment.KATEGORI_OEVRIG, 1018 : DataEmployment.KATEGORI_VITENSKAPLIG, 1019 : DataEmployment.KATEGORI_VITENSKAPLIG, 1015 : DataEmployment.KATEGORI_VITENSKAPLIG, 1016 : DataEmployment.KATEGORI_VITENSKAPLIG, 1017 : DataEmployment.KATEGORI_VITENSKAPLIG, 1407 : DataEmployment.KATEGORI_OEVRIG, 1011 : DataEmployment.KATEGORI_VITENSKAPLIG, 1405 : DataEmployment.KATEGORI_OEVRIG, 1404 : DataEmployment.KATEGORI_VITENSKAPLIG, 1132 : DataEmployment.KATEGORI_OEVRIG, 1130 : DataEmployment.KATEGORI_OEVRIG, 1137 : DataEmployment.KATEGORI_OEVRIG, 1136 : DataEmployment.KATEGORI_OEVRIG, 1434 : DataEmployment.KATEGORI_OEVRIG, 1433 : DataEmployment.KATEGORI_OEVRIG, 1009 : DataEmployment.KATEGORI_VITENSKAPLIG, 1083 : DataEmployment.KATEGORI_OEVRIG, 1032 : DataEmployment.KATEGORI_OEVRIG, 1033 : DataEmployment.KATEGORI_OEVRIG, 1213 : DataEmployment.KATEGORI_OEVRIG, 9131 : DataEmployment.KATEGORI_OEVRIG, 1211 : DataEmployment.KATEGORI_OEVRIG, 1216 : DataEmployment.KATEGORI_OEVRIG, 1353 : DataEmployment.KATEGORI_VITENSKAPLIG, 1352 : DataEmployment.KATEGORI_VITENSKAPLIG, 810 : DataEmployment.KATEGORI_OEVRIG, 966 : DataEmployment.KATEGORI_VITENSKAPLIG, 1026 : DataEmployment.KATEGORI_OEVRIG, 1020 : DataEmployment.KATEGORI_VITENSKAPLIG, 1182 : DataEmployment.KATEGORI_OEVRIG, 1183 : DataEmployment.KATEGORI_VITENSKAPLIG, 1181 : DataEmployment.KATEGORI_OEVRIG, 1108 : DataEmployment.KATEGORI_VITENSKAPLIG, 1109 : DataEmployment.KATEGORI_VITENSKAPLIG, 1200 : DataEmployment.KATEGORI_VITENSKAPLIG, 1203 : DataEmployment.KATEGORI_OEVRIG, 1199 : DataEmployment.KATEGORI_VITENSKAPLIG, 1198 : DataEmployment.KATEGORI_VITENSKAPLIG, 1054 : DataEmployment.KATEGORI_OEVRIG, 1056 : DataEmployment.KATEGORI_OEVRIG, 1059 : DataEmployment.KATEGORI_OEVRIG, 1013 : DataEmployment.KATEGORI_VITENSKAPLIG, 1111 : DataEmployment.KATEGORI_VITENSKAPLIG, 1110 : DataEmployment.KATEGORI_VITENSKAPLIG, 1113 : DataEmployment.KATEGORI_OEVRIG, 1116 : DataEmployment.KATEGORI_OEVRIG, 1275 : DataEmployment.KATEGORI_OEVRIG, 1178 : DataEmployment.KATEGORI_OEVRIG, 948 : DataEmployment.KATEGORI_OEVRIG, 947 : DataEmployment.KATEGORI_OEVRIG, 1364 : DataEmployment.KATEGORI_OEVRIG, 1362 : DataEmployment.KATEGORI_OEVRIG, 1363 : DataEmployment.KATEGORI_OEVRIG, 1474 : DataEmployment.KATEGORI_VITENSKAPLIG, 1475 : DataEmployment.KATEGORI_VITENSKAPLIG, 1078 : DataEmployment.KATEGORI_OEVRIG, 1090 : DataEmployment.KATEGORI_OEVRIG, 1409 : DataEmployment.KATEGORI_OEVRIG, 1447 : DataEmployment.KATEGORI_OEVRIG }

    # TBD: Bind it to Cerebrum constants?
    tag2type = { "Fornavn"       : HRDataPerson.NAME_FIRST,
                 "Etternavn"     : HRDataPerson.NAME_LAST,
                 "Fodselsnummer" : HRDataPerson.NO_SSN,
                 "Mann"          : HRDataPerson.GENDER_MALE,
                 "Kvinne"        : HRDataPerson.GENDER_FEMALE,
                 "HovedStilling" : DataEmployment.HOVEDSTILLING,
                 "Bistilling"    : DataEmployment.BISTILLING,
                 "Ansattnr"      : SAPPerson.SAP_NR, }


    def __init__(self, xmliter):
        """Constructs an iterator supplying SAPPerson objects."""

        super(XMLPerson2Object, self).__init__(xmliter)
    # end


    def _make_address(self, addr_element):
        """Make a DataAddress instance out of an <Adresse>."""
        assert addr_element.tag == "Adresse"

        sap2intern = { "Fysisk arbeidssted" : DataAddress.ADDRESS_POST,
                       "Bostedsadresse" : DataAddress.ADDRESS_PRIVATE, }
        zip = city = country = addr_kind = ""
        street = []

        for sub in addr_element.getiterator():
            if not sub.text:
                continue
            value = sub.text.strip().encode("latin1")

            if sub.tag in ("Gateadresse", "Adressetillegg"):
                street.append(value)
            elif sub.tag in ("Postnummer",):
                zip = value
            elif sub.tag in ("Poststed",):
                city = value
            elif sub.tag in ("Landkode",):
                country = value
            # NB! Note the spelling.
            elif sub.tag in ("AdressType",):
                addr_kind = sap2intern.get(value, "")
            # fi
        # od

        # If we do not know the address kind, we *cannot* register it.
        if not addr_kind:
            return None
        else:
            return DataAddress(kind = addr_kind,
                               street = street, zip = zip,
                               city = city, country = country)
    # end _make_address


    def _make_employment(self, emp_element):
        """Make a DataEmployment instance of an <HovedStilling>, </Bistilling>."""

        percentage = code = title = None
        start_date = end_date = None
        ou_id = None
        category = None
        kind = self.tag2type[emp_element.tag]

        for sub in emp_element.getiterator():
            if not sub.text:
                continue
            
            value = sub.text.strip().encode("latin1")
            
            if sub.tag == "stillingsprosent":
                percentage = float(value)
            elif sub.tag == "stillingsgruppebetegnelse":
                code = int(value[0:4])

                # 0000 are to be discarded. This is by design.
                if code == 0:
                    return None
                # fi
                if code in self.stilling2kode:
                    category = self.stilling2kode[code]
                # FIXME: assuyming this silently is a probably a bad thing
                else:
                    category = DataEmployment.KATEGORI_OEVRIG
                # fi
            elif sub.tag == "Stilling":
                title = value.strip()
            elif sub.tag == "Start_Date":
                start_date = self._make_mxdate(value)
            elif sub.tag == "End_Date":
                end_date = self._make_mxdate(value)
            elif sub.tag == "Orgenhet":
                ou_id = (DataOU.NO_SKO, make_sko(value))
            # fi
        # od

        # We *must* have an OU to which this employment is attached.
        if not ou_id:
            return None
        # fi

        kind = self.tag2type[emp_element.tag]
        tmp = DataEmployment(kind = kind, percentage = percentage,
                             code = code, title = title,
                             start = start_date, end = end_date,
                             place = ou_id, category = category)
        return tmp
    # end _make_employment


    def _make_role(self, elem):
        """Make an employment out of a <Roller>...</Roller>.

        SAP uses <Roller>-elements to designate bilagslønnede and gjester.
        """

        ou_id = None
        start_date = end_date = None
        kind = None
        code = None

        for sub in elem.getiterator():
            if not sub.text:
                continue

            value = sub.text.strip().encode("latin1")

            if sub.tag == "Rolleid":
                if value == "BILAGSLØNN":
                    kind = DataEmployment.BILAG
                else:
                    # For guests, we distinguish between different guest kinds
                    # For bilagslønnede, we don't care (they are all alike)
                    kind = DataEmployment.GJEST
                    code = value
                # fi
            elif sub.tag == "Stedkode":
                ou_id = (DataOU.NO_SKO, make_sko(value))
            elif sub.tag == "Start_Date":
                start_date = self._make_mxdate(value)
            elif sub.tag == "End_Date":
                end_date = self._make_mxdate(value)
            # fi
        # od

        if ou_id is None:
            return None
        # fi
        
        return DataEmployment(kind = kind, percentage = None,
                              code = code, title = None,
                              start = start_date, end = end_date,
                              place = ou_id, category = None)
    # end _make_role


    def _make_contact(self, elem, priority):
        """Return a DataContact instance out of elem."""

        ctype = elem.find("KOMMTYPE")
        if (ctype is None or
            ctype.text.strip() not in ("Faks arbeid",
                                       "Arbeidstelefon 1",
                                       "Arbeidstelefon 2",
                                       "Arbeidstelefon 3",)):
            return None
        # fi

        ctype = ctype.text.strip().encode("latin1")
        cvalue = elem.find("KommVal").text.strip().encode("latin1")
        cvalue = deuglify_phone(cvalue)
        if ctype == "Faks arbeid":
            ctype = DataContact.CONTACT_FAX
        else:
            ctype = DataContact.CONTACT_PHONE
        # fi

        return DataContact(ctype, cvalue, priority)
    # end _make_contact


    def next(self):
        """Return the next SAPPerson object.

        Consume the next XML-element describing a person, and return a
        suitable representation (SAPPerson).
        """

        # This call with propagate StopIteration when all the (XML) elements
        # are exhausted.
        element = super(XMLPerson2Object, self).next()
        result = SAPPerson()

        middle = element.find("person/Mellomnavn")
        if middle is not None and middle.text:
            middle = middle.text.encode("latin1").strip()
        else:
            middle = ""
        # fi

        # Iterate over *all* subelements
        for sub in element.getiterator():
            value = None
            if sub.text:
                value = sub.text.strip().encode("latin1")

            if sub.tag == "Fornavn":
                # Per baardj's request, we consider middle names as first names
                if middle:
                    value += " " + middle
                # fi
                result.add_name(DataName(self.tag2type[sub.tag], value))
            elif sub.tag == "Etternavn":
                result.add_name(DataName(self.tag2type[sub.tag], value))
            elif sub.tag == "Fodselsnummer":
                result.add_id(self.tag2type[sub.tag], personnr_ok(value))
            elif sub.tag == "Ansattnr":
                result.add_id(self.tag2type[sub.tag], value)
            elif sub.tag == "Fodselsdato":
                result.birth_date = self._make_mxdate(value)
            elif sub.tag == "Kjonn":
                result.gender = self.tag2type[value]
            elif sub.tag == "Adresse":
                result.add_address(self._make_address(sub))
            elif sub.tag in ("HovedStilling", "Bistilling"):
                emp = self._make_employment(sub)
                if emp is not None:
                    result.add_employment(emp)
                # fi
            elif sub.tag == "Roller" and sub.findtext("IKKE-ANGIT") is None:
                emp = self._make_role(sub)
                if emp is not None:
                    result.add_employment(emp)
                # fi
            # fi
        # od

        # We need to order 'Telefon 1' and 'Telefon 2' properly
        celems = list(element.findall("PersonKomm"))
        celems.sort(lambda x, y: cmp(x.find("KOMMTYPE").text,
                                     y.find("KOMMTYPE").text))
        # TBD: Prioritiies!
        priority = 0
        for ct in celems:
            contact = self._make_contact(ct, priority)
            if contact:
                result.add_contact(contact)
                priority += 1
            # fi
        # od

        # default: Personer med minst en ekte aktiv tilsetting => samtykket
        if filter(lambda x: x.kind in (DataEmployment.HOVEDSTILLING,
                                       DataEmployment.BISTILLING) and
                            x.is_active(), result.iteremployment()):
            to_reserve = False
        # alle andre => reservert
        else:
            to_reserve = True
        # fi

        # 3. Alle som ligger inne med minst en 'RESE' er reservert (uavhengig
        #    av om der også ligger registrert samtykke på vedkommende).
        for i in element.findall("person/Adresse/Reservert"):
            if i.text.strip() == "RESE":
                to_reserve = True
                break
            # fi
        # od
        result.reserved = to_reserve

        assert (result.get_name(result.NAME_FIRST) and
                result.get_name(result.NAME_LAST))
        
        # NB! This is crucial to save memory on XML elements
        element.clear()
        return result
    # end next
# end XMLPerson2Object





# arch-tag: 18e47e1a-ccf4-4417-adcc-958d5e99f895

