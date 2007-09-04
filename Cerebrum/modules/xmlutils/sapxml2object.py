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
This module implements an abstraction layer for SAP-originated HR data.

Specifically, we build the datagetter API for XML SAP data sources. For now,
this means mapping XML-elements stemming from SAP data files to objects in
datagetter.
"""

from mx.DateTime import Date, now
import time
import sys

import cerebrum_path
import cereconf
from Cerebrum.modules.xmlutils.xml2object import \
     XMLDataGetter, XMLEntity2Object, HRDataPerson, DataAddress, \
     DataEmployment, DataOU, DataContact, DataName

from Cerebrum.modules.no.fodselsnr import personnr_ok
from Cerebrum.extlib.sets import Set as set





def deuglify_phone(phone):
    """Remove junk like ' ' and '-' from phone numbers."""

    for junk in (" ", "-"):
        phone = phone.replace(junk, "")

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
        else:
            return None

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

        tag2kind = {"Akronym": DataOU.NAME_ACRONYM,
                    "Kortnavn": DataOU.NAME_SHORT,
                    "Langnavn": DataOU.NAME_LONG, }

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
        """Return the next DataOU object."""

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
            elif sub.tag == "Overordnetsted":
                sko = make_sko(value)
                if sko is not None:
                    result.parent = (result.NO_SKO, make_sko(value))
            elif sub.tag == "stednavn":
                for name in self._make_names(sub):
                    result.add_name(name)
            elif sub.tag in ("stedadresse",):
                result.add_address(self._make_address(sub))
            elif sub.tag in ("Start_Date", "End_Date"):
                date = self._make_mxdate(sub.text)
                if sub.tag == "Start_Date":
                    result.start_date = date
                else:
                    result.end_date = date

        # Katalogmerke (whether the OU can be published in various online
        # directories)
        mark = False
        for tmp in element.findall(".//stedbruk/StedType"):
            if tmp.text == "Elektronisk katalog":
                mark = True
                break
        result.publishable = mark

        celems = element.findall("stedkomm")
        for sub in celems:
            ct = self._make_contact(sub)
            if ct:
                result.add_contact(ct)

        # Oh, this is not pretty -- expired OUs should not be in the file, but
        # for now we'd settle for quelling the errors
        if result.end_date >= now():
            assert result.get_name(DataOU.NAME_LONG) is not None, \
                   "No name available for OU %s" % str(result.get_id(DataOU.NO_SKO))

        return result
    # end next
# end XMLOU2Object



class XMLPerson2Object(XMLEntity2Object):
    """A converter class that maps ElementTree's Element to SAPPerson."""

    # Each employment has a 4-digit Norwegian state employment code. Ideally
    # SAP should tag the employments as either VITENSKAPELIG or
    # TEKADM/OEVRIG. Unfortunately, it does not always happen, and we are
    # forced to deduce the categories ourselves. This list of codes is derived
    # from LT-data. Unless there is an <adm_forsk> element with the right
    # values, this set will be used to determine vit/tekadm categories.
    #
    # Everything IN this set is tagged with KATEGORI_VITENSKAPLIG
    # Everything NOT IN this set is tagged with KATEGORI_OEVRIG
    kode_vitenskaplig = set([966, 1009, 1010, 1011, 1013, 1015, 1016, 1017,
                             1018, 1019, 1020, 1108, 1109, 1110, 1111, 1183,
                             1198, 1199, 1200, 1260, 1352, 1353, 1378, 1404,
                             1474, 1475, 8013, ])

    tag2type = {"Fornavn": HRDataPerson.NAME_FIRST,
                "Etternavn": HRDataPerson.NAME_LAST,
                "Fodselsnummer": HRDataPerson.NO_SSN,
                "Mann": HRDataPerson.GENDER_MALE,
                "Kvinne": HRDataPerson.GENDER_FEMALE,
                "Ukjent": HRDataPerson.GENDER_UNKNOWN,
                "HovedStilling": DataEmployment.HOVEDSTILLING,
                "Bistilling": DataEmployment.BISTILLING,
                "Ansattnr": SAPPerson.SAP_NR,
                "Title": HRDataPerson.NAME_TITLE,}

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
                # IVR 2007-01-04 FIXME: 8 is the length of the field in the
                # database. It's a bit ugly to do things this way, though.
                if len(zip) > 8:
                    return None
            elif sub.tag in ("Poststed",):
                city = value
            elif sub.tag in ("Landkode",):
                country = value
            # IVR 2007-07-06 spelling-lol
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


    def _code2category(self, data):
        """Categorize the employment, based on the 4-digit code in data"""

        if isinstance(data, basestring):
            data = data.strip()
            if not data.isdigit():
                return None
        code = int(data)

        if code in self.kode_vitenskaplig:
            return DataEmployment.KATEGORI_VITENSKAPLIG
        else:
            return DataEmployment.KATEGORI_OEVRIG
    # end _code2category


    def _make_employment(self, emp_element):
        """Make a DataEmployment instance of an <HovedStilling>, </Bistilling>.

        emp_element is the XML-subtree representing the employment.
        """

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
                # Some elements have the proper category set in adm_forsk
                if category is None:
                    category = self._code2category(code)
            elif sub.tag == "Stilling":
                tmp = value.split(" ")
                if len(tmp) == 1:
                    title = tmp[0]
                else:
                    title = " ".join(tmp[1:])
                    if category is None:
                        category = self._code2category(tmp[0])
            elif sub.tag == "Start_Date":
                start_date = self._make_mxdate(value)
            elif sub.tag == "End_Date":
                end_date = self._make_mxdate(value)
            elif sub.tag == "Orgenhet":
                sko = make_sko(value)
                if sko is not None:
                    ou_id = (DataOU.NO_SKO, sko)
            elif sub.tag == "adm_forsk":
                # if neither is specified, use, the logic in
                # stillingsgruppebetegnelse to decide on the category
                if value == "Vit":
                    category = DataEmployment.KATEGORI_VITENSKAPLIG
                elif value == "T/A":
                    category = DataEmployment.KATEGORI_OEVRIG
            elif sub.tag == "Status":
                # <Status> indicates whether the employment entry is
                # actually valid.
                if value != "Aktiv":
                    return None
            elif sub.tag == "Stillnum":
                # this code means that the employment has been terminated (why
                # would there be two elements for that?)
                if value == "99999999":
                    return None
                # these are temp employments (bilagslønnede) that we can
                # safely disregard (according to baardj).
                if value == "30010895":
                    return None

            # IVR 2007-07-11 FIXME: We should take a look at <Arsak>, since it
            # contains deceased status for a person.

        # We *must* have an OU to which this employment is attached.
        if not ou_id: return None

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
                sko = make_sko(value)
                if sko is not None:
                    ou_id = (DataOU.NO_SKO, sko)
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

        kommtype2const = {"Faks arbeid": DataContact.CONTACT_FAX,
                          "Telefaks midlertidig arbeidssted":
                            DataContact.CONTACT_FAX,
                          "Arbeidstelefon 1": DataContact.CONTACT_PHONE,
                          "Arbeidstelefon 2": DataContact.CONTACT_PHONE,
                          "Arbeidstelefon 3": DataContact.CONTACT_PHONE,
                          "Mobilnummer, jobb": DataContact.CONTACT_MOBILE,}

        ctype = elem.find("KOMMTYPE")
        if (ctype is None or
            ctype.text.strip() not in kommtype2const):
            return None

        ctype = ctype.text.strip().encode("latin1")
        cvalue = elem.find("KommVal").text.strip().encode("latin1")
        cvalue = deuglify_phone(cvalue)
        ctype = kommtype2const[ctype]

        return DataContact(ctype, cvalue, priority)
    # end _make_contact


    def next(self):
        """Return the next SAPPerson object.

        Consume the next XML-element describing a person, and return a
        suitable representation (SAPPerson).

        Should something fail (which prevents this method from constructing a
        proper SAPPerson object), an exception is raised.
        """

        # This call with propagate StopIteration when all the (XML) elements
        # are exhausted. element is the ElementTree element containing the
        # parsed chunk of XML data.
        element = super(XMLPerson2Object, self).next()
        result = SAPPerson()

        # Per baardj's request, we consider middle names as first names.
        middle = ""
        middle = element.find("person/Mellomnavn")
        if middle is not None and middle.text:
            middle = middle.text.encode("latin1").strip()

        main = None
        # Iterate over *all* subelements, 'fill up' the result object
        for sub in element.getiterator():
            value = None
            if sub.text:
                value = sub.text.strip().encode("latin1")

            if sub.tag == "Fornavn":
                if middle:
                    value += " " + middle

                # IVR 2007-05-30 FIXME: This is not pretty.
                #
                # In an e-mail from 2007-05-29, Johannes Paulsen suggests that
                # marking invalid entries with '*' in the some of the name
                # elements is the easiest approach. This is an ugly hack, but
                # since the invalid entries will not disappear anytime soon,
                # this is the easiest way of skipping them.
                #
                # JAZZ 2007-08-01
                #
                # '*' did not work all that well as it is used as common wildcard in
                # SAP. Johannes suggests that we use '@' in stead. As the data is not
                # updated yet (we don't know when that will happen) we need to test
                # for '*' as well in order to skipp all the invalid elements
                #
                if '*' in value or '@' in value:
                    raise ValueError("Name contains '@' or '*', ignored")
                result.add_name(DataName(self.tag2type[sub.tag], value))
            elif sub.tag == "Etternavn":
                if '*' in value or '@' in value:
                    raise ValueError("Name contains '@' or '*', ignored")
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
                    if sub.tag == "HovedStilling":
                        main = emp
            elif sub.tag == "Roller" and sub.findtext("IKKE-ANGIT") is None:
                emp = self._make_role(sub)
                if emp is not None:
                    result.add_employment(emp)
            elif sub.tag == "Title":
                result.add_name(DataName(self.tag2type[sub.tag], value))

        # We need to order 'Telefon 1' and 'Telefon 2' properly
        celems = list(element.findall("PersonKomm"))
        celems.sort(lambda x, y: cmp(x.find("KOMMTYPE").text,
                                     y.find("KOMMTYPE").text))
        # TBD: Priorities!
        priority = 0
        for ct in celems:
            contact = self._make_contact(ct, priority)
            if contact:
                result.add_contact(contact)
                priority += 1

        # Reservations for catalogue publishing
        # default: One active employment => can be published
        to_reserve = not result.has_active_employments()

        # Everyone with 'RESE' is reserved (regardless of everything else)
        for i in element.findall("Adresse/Reservert"):
            if i.text:
                tmp = i.text.strip()
                if tmp == "RESE":
                    to_reserve = True
                    break
        result.reserved = to_reserve

        # Address magic
        # If there is a sensible 'Sted for lønnsslipp', it will result i
        # proper "post/besøksaddresse" later. This code matches LT's behaviour
        # more closely (an employee 'inherits' the address of his/her
        # "primary" workplace.
        for sub in element.getiterator("PersonKomm"):
            txt = sub.findtext("KOMMTYPE")
            val = sub.findtext("KommVal")
            if (txt and txt.encode("latin1") == "Sted for lønnslipp" and val
                # *some* of the entries have a space here and there.
                # and some contain non-digit data
                and val.replace(" ", "").isdigit()):
                val = val.replace(" ", "")
                fak, inst, gruppe = [int(x) for x in
                                     (val[:2], val[2:4], val[4:])]
                result.primary_ou = (cereconf.DEFAULT_INSTITUSJONSNR,
                                     fak, inst, gruppe)

        # IVR 2007-05-30 FIXME: This is a workaround, beware!
        # 
        # If there is a valid "principal employment" (hovedstilling), AND we
        # have a 'sted for lønnslipp' defined, register a fake employment, so
        # that this person would receive the right affiliations later.
        #
        # It would be possible to put some extra logic in import_HR_person
        # that would take care of this affiliation assignment. However, this
        # workaround has no counterpart in LT, and as import_HR_person is
        # source agnostic, we do not want to pollute it with SAP-specific
        # logic.
        #
        # The ugly part is that this employment does not really exist. It's
        # just there, so that the right affiliations can be assigned
        # later. Until we get the proper data from SAP, this workaround would
        # have to stay in place.
        if main and hasattr(result, "primary_ou"):
            result.add_employment(
                DataEmployment(kind = DataEmployment.BISTILLING,
                               percentage = main.percentage,
                               code = main.code,
                               title = main.title,
                               start = main.start,
                               end = main.end,
                               place = (DataOU.NO_SKO, result.primary_ou[1:]),
                               category = main.category))

        assert (result.get_name(result.NAME_FIRST) and
                result.get_name(result.NAME_LAST))
        
        # NB! This is crucial to save memory on XML elements
        element.clear()
        return result
    # end next
# end XMLPerson2Object
