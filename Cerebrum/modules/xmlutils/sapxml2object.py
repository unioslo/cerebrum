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
This module implements an abstraction layer for SAP-originated HR data.

Specifically, we build the datagetter API for XML SAP data sources. For now,
this means mapping XML-elements stemming from SAP data files to objects in
datagetter.
"""

from __future__ import unicode_literals
from mx.DateTime import now

import cereconf

from Cerebrum.modules.xmlutils.xml2object import (
    XMLDataGetter, XMLEntity2Object, HRDataPerson, DataAddress,
    DataEmployment, DataOU, DataContact, DataName, DataExternalWork,
    ensure_unicode
)
from Cerebrum.modules.no.fodselsnr import personnr_ok


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
    except:
        # TBD: What do we do here?
        return None
    # yrt

    return tuple([int(x) for x in data[:2], data[2:4], data[4:]])


class SAPXMLDataGetter(XMLDataGetter):

    """An abstraction layer for SAP XML files."""

    def iter_person(self, **kwargs):
        return self._make_iterator("sap2bas_pers", XMLPerson2Object, **kwargs)

    def iter_ou(self, **kwargs):
        return self._make_iterator("sap2bas_sted", XMLOU2Object, **kwargs)


class XMLOU2Object(XMLEntity2Object):

    """A converter class that maps ElementTree's Element to DataOU."""

    # TBD: Bind it to Cerebrum constants?
    tag2type = {
        "Stedkode": DataOU.NO_SKO,
        "Akronym": DataOU.NAME_ACRONYM,
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
	# OU's intended usage code (bruksomr�de). Find out which attribute
        # this is.
        # Iterate over *all* subelements
        for sub in element.getiterator():
            value = None
            if sub.text:
		value = ensure_unicode(sub.text.strip(), self.encoding)
            if sub.tag == "Stedkode":
                sko = make_sko(value)
                if sko is not None:
                    result.add_id(self.tag2type[sub.tag], sko)
                else:
                    # invalid value for the <Stedkode> tag
                    if self.logger:
                        self.logger.warn(
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
                date = self._make_mxdate(sub.text, format="%Y-%m-%d")
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
            if result.end_date and result.end_date < now():
                if self.logger:
                    self.logger.debug("No name for expired OU %s",
                                      ou_no_sko_str)
            elif result.start_date and result.start_date > now():
                if self.logger:
                    self.logger.debug("No name for future OU %s",
                                      ou_no_sko_str)
            else:
                if self.logger:
                    self.logger.warn("No name available for OU %s",
                                     ou_no_sko_str)
                return None

        return result


class XMLPerson2Object(XMLEntity2Object):

    """A converter class that maps ElementTree's Element to SAPPerson."""

    # Each employment has a 4-digit Norwegian state employment code. Ideally
    # SAP should tag the employments as either VITENSKAPELIG or TEKADM/OEVRIG
    # themselves. Unfortunately, it does not always happen, and we are forced
    # to deduce the categories ourselves. This list of codes is derived from
    # LT-data. Unless there is an <AdmForsk> element with the right values,
    # this set will be used to determine vit/tekadm categories.
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
                "Hovedstilling": DataEmployment.HOVEDSTILLING,
                "Bistilling": DataEmployment.BISTILLING,
                "Ansattnummer": SAPPerson.SAP_NR, }

    # This map decides which ID-types to import
    sap2idtype = {"Passnummer": HRDataPerson.PASSNR, }

    def _make_address(self, addr_element):
        """Make a DataAddress instance out of an <Adresse>."""

	assert addr_element.tag == "Adresse"

	sap2intern = {
	    "Besøksadresse": DataAddress.ADDRESS_BESOK,
	    "Postadresse": DataAddress.ADDRESS_POST,
	    "Bostedsadresse": DataAddress.ADDRESS_PRIVATE,
	    "Avvikende postadresse": DataAddress.ADDRESS_OTHER_POST,
	    "Avvikende besøksadresse": DataAddress.ADDRESS_OTHER_BESOK,
	}

	zip = city = country = addr_kind = ""
        street = []

        for sub in addr_element.getiterator():
            if not sub.text:
                continue
	    value = ensure_unicode(sub.text.strip(), self.encoding)

            if sub.tag in ("Gateadresse",):
                street.insert(0, value)
            if sub.tag in ("Adressetillegg",):
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
            elif sub.tag in ("Type",):
                addr_kind = sap2intern.get(value, "")
            elif sub.tag in ("CO",):
                # CO-fields don't seem to be registered intentionally
                # or with any kind of plan an regularity. we will stop
                # importing them for now, and do an evaluation at a
                # latter time. Jazz, 2011-10-28
                #
                # street.insert(0, value)
                continue
        # If we do not know the address kind, we *cannot* register it.
        if not addr_kind:
            return None
        else:
            return DataAddress(kind=addr_kind,
                               street=street, zip=zip,
                               city=city, country=country)

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

    @XMLEntity2Object.exception_wrapper
    def _make_employment(self, emp_element):
        """Make a DataEmployment instance of an <Hovedstilling>, </Bistilling>.

        emp_element is the XML-subtree representing the employment. Returns a
        DataEmployment object, representing the XML-employment object.

        """
        percentage = code = None
        start_date = end_date = None
        ou_id = None
        category = None
        kind = self.tag2type[emp_element.tag]
        mg = mug = None

        for sub in emp_element.getiterator():
            if not sub.text:
                continue

	    value = ensure_unicode(sub.text.strip(), self.encoding)

            if sub.tag == "Stillingsprosent":
                percentage = float(value)
            elif sub.tag == "SKO":
                code = int(value[0:4])

                if getattr(self, 'filter_out_sko_0000', True):
                    # 0000 are to be discarded. This is by design.
                    if code == 0:
                        return None
                # Some elements have the proper category set in AdmForsk
                if category is None:
                    category = self._code2category(code)
            elif sub.tag == "Stilling":
                tmp = value.split(" ")
                if len(tmp) != 1 and category is None:
                    category = self._code2category(tmp[0])
            elif sub.tag == "Startdato":
                start_date = self._make_mxdate(value, format="%Y-%m-%d")
            elif sub.tag == "Sluttdato":
                end_date = self._make_mxdate(value, format="%Y-%m-%d")
            elif sub.tag == "Orgenhet":
                sko = make_sko(value)
                if sko is not None:
                    ou_id = (DataOU.NO_SKO, sko)
            elif sub.tag == "AdmForsk":
                # if neither is specified, use, the logic in
                # stillingsgruppebetegnelse to decide on the category
                if value == "Vit":
                    category = DataEmployment.KATEGORI_VITENSKAPLIG
                elif value == "T/A":
                    category = DataEmployment.KATEGORI_OEVRIG
            elif sub.tag == "Status":
                # <Status> indicates whether the employment entry is actually
                # valid.
                if value != "Aktiv":
                    return None
            elif sub.tag == "Stillingsnummer":
                # this code means that the employment has been terminated (why
                # would there be two elements for that?)
                if value == "99999999":
                    return None
		# these are temp employments (bilagsl�nnede) that we can
                # safely disregard (according to baardj).
                if value == "30010895":
                    return None
            elif sub.tag == "MEGType":
                mg = int(value)
            elif sub.tag == "MUGType":
                mug = int(value)
            # IVR 2007-07-11 FIXME: We should take a look at <Arsak>, since it
            # contains deceased status for a person.

        # We *must* have an OU to which this employment is attached.
        if getattr(self, 'require_ou_for_assignments', True) and not ou_id:
            return None

        kind = self.tag2type[emp_element.tag]
        tmp = DataEmployment(kind=kind, percentage=percentage,
                             code=code, start=start_date, end=end_date,
                             place=ou_id, category=category,
                             mg=mg, mug=mug)

        for element in emp_element.findall(".//Tittel"):
            work_title = self._make_title(DataEmployment.WORK_TITLE, element)
            if work_title:
                tmp.add_name(work_title)

        return tmp

    @XMLEntity2Object.exception_wrapper
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

	    value = ensure_unicode(sub.text.strip(), self.encoding)

	    if sub.tag == "Navn":
		code = value

		if value == "BILAGSLØNN":
		    kind = DataEmployment.BILAG
		else:
		    # For guests, we distinguish between different guest kinds
		    # For bilagsl�nnede, we don't care (they are all alike)
                    kind = DataEmployment.GJEST
            elif sub.tag == "Stedkode":
                sko = make_sko(value)
                if sko is not None:
                    ou_id = (DataOU.NO_SKO, sko)
            elif sub.tag == "Startdato":
                start_date = self._make_mxdate(value, format="%Y-%m-%d")
            elif sub.tag == "Sluttdato":
                end_date = self._make_mxdate(value, format="%Y-%m-%d")
            # fi
        # od

        if ou_id is None:
            return None

        return DataEmployment(kind=kind, percentage=None,
                              code=code,
                              start=start_date, end=end_date,
                              place=ou_id, category=None)

    @XMLEntity2Object.exception_wrapper
    def _make_contact(self, elem, priority):
        """Return a DataContact instance out of elem."""

        kommtype2const = {
            u"Faks arbeid": DataContact.CONTACT_FAX,
            u"Telefaks midlertidig arbeidssted": DataContact.CONTACT_FAX,
            u"Arbeidstelefon 1": DataContact.CONTACT_PHONE,
            u"Arbeidstelefon 2": DataContact.CONTACT_PHONE,
	    u"Arbeidstelefon 3": DataContact.CONTACT_PHONE,
	    u"Mobilnummer, jobb": DataContact.CONTACT_MOBILE_WORK,
	    u"Mobilnummer, privat": DataContact.CONTACT_MOBILE_PRIVATE,
	    u"Privat mobil synlig på web":
	    DataContact.CONTACT_MOBILE_PRIVATE_PUBLIC}

	ctype = elem.find("Type")
        if ctype is None:
            return None

	ctype = ensure_unicode(ctype.text.strip(), self.encoding)

        ctype = kommtype2const.get(ctype)
        if ctype is None:
            return None

	cvalue = ensure_unicode(elem.find("Verdi").text.strip(), self.encoding)
        cvalue = deuglify_phone(cvalue)

        return DataContact(ctype, cvalue, priority)

    def _make_title(self, title_kind, title_element):
        """Return a DataName representing title with language."""

        language = title_element.findtext(".//Sprak")
	value = ensure_unicode(title_element.findtext(".//Navn"),
			       self.encoding)

        if not (language and value):
            return None

        x = DataName(title_kind, value, language)
        return x

    def _make_sgm(self, element):
        """ Return a sgm object. """

        name = element.findtext(".//OrgNavn")
        type = element.findtext(".//OrgType")
        extent = element.findtext(".//Omfang")
        start = element.findtext(".//Startdato")
        if start:
	    start = self._make_mxdate(ensure_unicode(start, self.encoding),
                                      format="%Y-%m-%d")
        else:
            start = None
        end = element.findtext(".//Sluttdato")
        if end:
	    end = self._make_mxdate(ensure_unicode(end, self.encoding),
				    format="%Y-%m-%d")
        else:
            end = None
	description = ensure_unicode(element.findtext(".//Tekst"),
				     self.encoding)
        return DataExternalWork(name, type, extent, start, end, description)

    def next_object(self, element):
        """Return the next SAPPerson object.

        Consume the next XML-element describing a person, and return a
        suitable representation (SAPPerson).

        Should something fail (which prevents this method from constructing a
        proper SAPPerson object), an exception is raised.

        """
        result = SAPPerson()

        # Per baardj's request, we consider middle names as first names.
        middle = ""
        middle = element.find("Person/Mellomnavn")
        if middle is not None and middle.text:
	    middle = ensure_unicode(middle.text.strip(), self.encoding)

        # Iterate over *all* subelements, 'fill up' the result object
        for sub in element.getiterator():
            value = None
            if sub.text:
		value = ensure_unicode(sub.text.strip(), self.encoding)

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
                # '*' did not work all that well as it is used as common
                # wildcard in SAP. Johannes suggests that we use '@' in
                # stead. As the data is not updated yet (we don't know when
                # that will happen) we need to test for '*' as well in order
                # to skip all the invalid elements
                #
                if '*' in value or '@' in value:
                    if self.logger:
                        self.logger.debug("Name contains '@' or '*', ignored")
                    # Since the element is marked as void, there is no need to
                    # process further (we have no guarantee that any data
                    # would make sense and we won't have even more spurious
                    # warnings).
                    return None
                result.add_name(DataName(self.tag2type[sub.tag], value))
            elif sub.tag == "Etternavn":
                if '*' in value or '@' in value:
                    if self.logger:
                        self.logger.debug("Name contains '@' or '*', ignored")
                    # Se <Fornavn>.
                    return None
                result.add_name(DataName(self.tag2type[sub.tag], value))
            elif sub.tag == "Fodselsnummer" and value is not None:
                result.add_id(self.tag2type[sub.tag], personnr_ok(value))
            elif sub.tag == "Ansattnummer":
                result.add_id(self.tag2type[sub.tag], value)
                self.logger.debug(value)
            elif sub.tag == "Fodselsdato":
                result.birth_date = self._make_mxdate(value, format="%Y-%m-%d")
            elif sub.tag == "Kjonn":
                result.gender = self.tag2type[value]
            elif sub.tag == "Adresse":
                result.add_address(self._make_address(sub))
            elif sub.tag in ("Hovedstilling", "Bistilling"):
                emp = self._make_employment(sub)
                if emp is not None:
                    result.add_employment(emp)
            elif sub.tag == "Roller" and sub.findtext("IKKE-ANGIT") is None:
                emp = self._make_role(sub)
                if emp is not None:
                    result.add_employment(emp)
            elif sub.tag == "Person":
                # Lots of the other entries above also are part of the
                # "person"-firstlevel element, but we need to
                # specifically look here for Tittel => personal title,
                # to avoid confusion with worktitles
                for subsub in sub.findall("Tittel"):
                    personal_title = self._make_title(HRDataPerson.NAME_TITLE,
                                                      subsub)
                    if personal_title:
                        result.add_name(personal_title)
            elif sub.tag == "PersonligID":
                # Store additional person ids, like passport numbers.
                # Handle passport numbers
                if sub.find('Type').text in self.sap2idtype:
		    # Add the ID to the data-structure
		    pers_id = '{0}-{1}'.format(
			ensure_unicode(sub.find('Land').text, self.encoding),
			ensure_unicode(sub.find('Verdi').text, self.encoding)
		    )
                    result.add_id(self.sap2idtype[sub.find('Type').text],
				  pers_id)
                else:
                    self.logger.debug(
                        "Unknown %s type '%s': skipping id type",
                        sub.tag, sub.find('Type').text)
            elif sub.tag == "SGM":
                # New feature and unique (for now?) for UiO is SGM,
                # external attachments for person.
                self.logger.debug("SGM for %s", result)
                result.add_external_work(self._make_sgm(sub))
        # We need to order 'Telefon 1' and 'Telefon 2' properly
        celems = list(element.findall("Kommunikasjon"))
        celems.sort(lambda x, y: cmp(x.find("Type").text,
                                     y.find("Type").text))
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
        # If no 'RESE' exists, but there is a 'SAMT' => no reservation
        for i in element.findall("Adresse/Reservert"):
            if i.text:
                tmp = i.text.strip()
                if tmp == "RESE":
                    to_reserve = True
                    break
                elif tmp == "SAMT":
                    to_reserve = False
        result.reserved = to_reserve

        # Address magic
	# If there is a sensible 'Sted for l�nnsslipp', it will result i
	# proper "post/bes�ksaddresse" later. This code matches LT's behaviour
        # more closely (an employee 'inherits' the address of his/her
        # "primary" workplace.
	for sub in element.getiterator("Kommunikasjon"):
	    txt = ensure_unicode(sub.findtext("Type"), self.encoding)
	    val = ensure_unicode(sub.findtext("Verdi"), self.encoding)
	    if (txt and txt == "Sted for lønnslipp" and val
		    # *some* of the entries have a space here and there.
		    # and some contain non-digit data
		    and val.replace(" ", "").isdigit()):
                val = val.replace(" ", "")
                fak, inst, gruppe = [int(x) for x in
                                     (val[:2], val[2:4], val[4:])]
                result.primary_ou = (cereconf.DEFAULT_INSTITUSJONSNR,
                                     fak, inst, gruppe)

        # We require people to have first/last name.
        if not (result.get_name(result.NAME_FIRST) and
                result.get_name(result.NAME_LAST)):
            self.logger.warn(
                "People must have first and last names. %s skipped",
                list(result.iterids())
            )
            return None

        return result
