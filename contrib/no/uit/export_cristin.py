#! /usr/bin/env python
# -*- coding:utf-8 -*-
#
# Copyright 2003-2019 University of Oslo, Norway
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
from __future__ import unicode_literals

"""

This file is part of the Cerebrum framework.

It generates an xml dump, suitable for importing into the FRIDA framework
(for more information on FRIDA, start at <URL:
http://www.usit.uio.no/prosjekter/frida/pg/>). The output format is
specified by FRIDA.dtd, available in the "uiocerebrum" project, at
cvs.uio.no.

The general workflow is rather simple:

person.xml    --+
                |
sted.xml        +--> generate_frida_export.py ===> frida.xml
                |
<cerebrum db> --+

person.xml is needed for information about hiring / peoples statuses.

sted.xml contains information about organizational units (URLs,
specifically)

<cerebrum db> is needed for everything else.

person.xml format is specified by lt-person.dtd available in the
"uiocerebrum" project. Only some of the elements are of interest for FRIDA
export. We use Norwegian f�dselsnummer to tie <person>-elements to database
rows.

sted.xml format is noe specified anywhere (but it will be :)). For now, this
file is ignored and no <URL> elements are generated in frida.xml (in
violation of the FRIDA.dtd).

"""

import argparse
import logging
import os
import time
import string
import xml.sax

from xml.sax import make_parser

import cereconf
import Cerebrum.logutils

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.atomicfile import SimilarSizeWriter
from Cerebrum.extlib import xmlprinter
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.xmlutils.system2parser import system2parser
from Cerebrum.modules.entity_expire.entity_expire import EntityExpiredError

logger = logging.getLogger(__name__)

cerebrum_db = Factory.get("Database")()
constants = Factory.get("Constants")(cerebrum_db)
person_db = Factory.get("Person")(cerebrum_db)
account_db = Factory.get("Account")(cerebrum_db)
ou_db = Factory.get('OU')(cerebrum_db)
source_system = constants.system_paga
system_cached = constants.system_cached

# UIT:
# Added by kenneth
# date 27.10.2005
person_list = []  # baaaad boy. you should not use global lists :(


class PersonHandler(xml.sax.ContentHandler):

    def __init__(self, file_name, call_back_function):
        self.person_list = []
        self.call_back_function = call_back_function
        self.tils_attrs = {}
        self.person_attrs = {}

    def startElement(self, name, attrs):
        if name == 'tils':
            self.tils_attrs = {}
            for k in attrs.keys():
                self.tils_attrs[k] = attrs.get(k)
        if name == 'person':
            self.person_attrs = {}
            for k in attrs.keys():
                self.person_attrs[k] = attrs.get(k)
        return

    def characters(self, ch):
        self.var = None
        # tmp = ch.encode('iso8859-1').strip()
        tmp = ch.encode('utf-8').strip()
        if tmp:
            self.var = tmp
            self._elemdata.append(tmp)

    def endElement(self, name):
        if name == 'person':
            self.call_back_function(self, name)
        elif name == 'tils':
            self.person_attrs['tils'] = self.tils_attrs


def person_helper(obj, element):
    if element == 'person':
        person_list.append(obj.person_attrs)


class SystemXRepresentation(object):
    """This class gets information about persons from system_x that has
    a frida spread. All these persons will have a 'gjest' identification
    without any stillingskode or stillingstittel. The data about these persons
    are collected straight from the database.

    Each person will then populate the following fields according to the
    FRIDA dtd:
    <!ELEMENT person | gjest>
    <!ATTLIST person
              navn CDATA #REQUIRED
              fodtdag CDATA #REQUIRED
              fodtmnd CDATA #REQUIRED
              fodtar CDATA #REQUIRED
              personnr CDATA #REQUIRED>
    <!ATTLIST gjest
              sko CDATA #REQUIRED
              gjestetypekode CDATA #REQUIRED
              dato_fra CDATA #REQUIRED
              dato_til CDATA #REQUIRED>

    NB: All 'gjest' persons are entered into cerebrum via system_x. This
        means they do not exist in cerebrum already. q.e.d, they will wither
        appear here as a 'gjest' or in the LT/SLP4 import.
    """

    def execute(self, pobj, writer, system_source):
        db = Factory.get('Database')()
        person = Factory.get('Person')(db)
        account = Factory.get('Account')(db)
        const = Factory.get('Constants')(db)
        stedkode = Factory.get('OU')(db)

        current_source_system = const.system_x
        # Get all persons that come from SysX  ONLY, _and_ has a norwegian SSN!
        entities = person.search_external_ids(
            source_system=const.system_x,
            id_type=const.externalid_fodselsnr,
            entity_type=8)
        for entity in entities:
            # pprint(entity)
            account.clear()

            person.clear()
            stedkode.clear()

            # find account and person objects
            external_id = entity['external_id']
            logger.debug("Working on %s", external_id)
            logger.debug("entity id:%s", entity['entity_id'])
            # logger.debug("entity_id:%s", (entity))
            person.find(entity['entity_id'])

            # Get the affiliation status code string
            aff = person.list_affiliations(person_id=person.entity_id,
                                           source_system=current_source_system)
            if not aff:
                logger.debug(
                    "No systemX aff for person %s.. skip", external_id)
                continue

            aff_str = const.PersonAffStatus(aff[0]['status'])
            aff_id = aff[0]['ou_id']
            # print "person.entity_id says:%s" % person.entity_id
            fornavn = person.get_name(current_source_system, const.name_first)
            etternavn = person.get_name(current_source_system, const.name_last)
            # print "fornavn for this person is:%s" % fornavn
            # print "etternavn for this person is:%s" % etternavn

            acc_id = person.get_primary_account()
            if (acc_id):
                account.find(acc_id)
            else:
                logger.warn(
                    "SysX person ID=(%s) Fnr=(%s) has no active account",
                    entity['entity_id'], entity['external_id'])
                continue

            try:
                my_email = account.get_primary_mailaddress()
            except Errors.NotFoundError:
                logger.warn(
                    "unable to find primary email for person with "
                    "person_id: %s. Person not exported",
                    person.entity_id)
                continue

            person_attrs = {"fnr": external_id, "reservert": "N"}
            account_name = account.account_name

            # Got info, output!
            found = False
            for i in person_list:
                existing_person_ssn = i['fnr']
                # "%s%s%s%s"% (i['fodtdag'],i['fodtmnd'],
                # i['fodtar'],i['personnr'])
                if external_id == existing_person_ssn:
                    found = True
            if not found:
                logger.info("Output sysx person %s", external_id)
                logger.info(
                    "system-x person name: %s, %s", fornavn, etternavn)
                logger.info("account name:%s", account_name)
                writer.startElement("person", person_attrs)

                writer.startElement("etternavn")
                writer.data(etternavn)
                writer.endElement("etternavn")

                writer.startElement("fornavn")
                writer.data(fornavn)
                writer.endElement("fornavn")

                writer.startElement("brukernavn")
                writer.data(account_name)
                writer.endElement("brukernavn")

                writer.startElement("epost")
                writer.data(my_email)
                writer.endElement("epost")

                writer.startElement("gjester")
                writer.startElement("gjest")

                writer.startElement("institusjonsnr")
                stedkode.clear()
                stedkode.find(aff_id)
                writer.data(str(stedkode.institusjon))
                writer.endElement("institusjonsnr")

                writer.startElement("avdnr")
                writer.data(str(stedkode.fakultet))
                writer.endElement("avdnr")

                writer.startElement("undavdnr")
                writer.data(str(stedkode.institutt))
                writer.endElement("undavdnr")

                writer.startElement("gruppenr")
                writer.data(str(stedkode.avdeling))
                writer.endElement("gruppenr")

                writer.startElement("datoFra")
                create_date = aff[0]['create_date']

                dato_fra = "%s-%s-%s" % (
                    create_date.year, create_date.month, create_date.day)
                writer.data(dato_fra)
                writer.endElement("datoFra")

                writer.startElement("gjestebetegnelse")
                writer.data(aff_str.status_str)
                writer.endElement("gjestebetegnelse")

                writer.endElement("gjest")
                writer.endElement("gjester")
                writer.endElement("person")
        # generate XML data


class LTPersonRepresentation(object):
    """
    This class is a handy abstraction toward the information emcompassed by
    the <person> elements.

    There are not that many elements that are of interest to us:

    <person> -- a new person
    <tils>   -- hiring information
    <gjest>  -- guest information
    <res>    -- reservation information

    The relevant spec from the dtd is:

    <!ELEMENT person (arbtlf? | komm* | rolle* | tils* | res* | bilag* | gjest
    *)>
    <!ATTLIST person
              navn CDATA #REQUIRED
              fodtdag CDATA #REQUIRED
              fodtmnd CDATA #REQUIRED
              fodtar CDATA #REQUIRED
              personnr CDATA #REQUIRED>
    <!ELEMENT tils EMPTY>
    <!ATTLIST tils
        fakultetnr_utgift CDATA #REQUIRED
            instituttnr_utgift CDATA #REQUIRED
        gruppenr_utgift CDATA #REQUIRED
        stillingkodenr_beregnet_sist CDATA #REQUIRED
        prosent_tilsetting CDATA #REQUIRED
        dato_fra CDATA #REQUIRED
        dato_til CDATA #REQUIRED
        hovedkat (VIT | �VR) #REQUIRED
    tittel CDATA #REQUIRED>
    <!ELEMENT gjest EMPTY>
    <!ATTLIST gjest
              sko CDATA #REQUIRED
              gjestetypekode CDATA #REQUIRED
              dato_fra CDATA #REQUIRED
              dato_til CDATA #REQUIRED>
    <!ELEMENT res EMPTY>
    <!ATTLIST res
              katalogkode (ADRTLF | ELKAT) #REQUIRED
              felttypekode CDATA #REQUIRED>

    NB! Not all attributes/elements are shown, only those that are of
    interest to FRIDA.
    """

    # These are names of the XML-elements of interest to FRIDA export
    PERSON_ELEMENT = "person"
    INTERESTING_ELEMENTS = ["tils", "gjest", "res"]

    def __init__(self, attributes):
        """
        This constructor reports back whether initialization succeeded
        (True/False). Objects which lack critical attributes are useless in
        FRIDA export.

        If the initialization fails, no guarantees about the instance's
        state/attributes are made.
        """

        self.elements = {}

        # Interesting elements have repetitions. Thus a hash of lists
        for element in self.INTERESTING_ELEMENTS:
            self.elements[element] = []

        # We need an ID to tie a person to the database identification Let's
        # use fnr, although it's a bad identification in general, but we do
        # NOT have any other identifier in person.xml
        if "fnr" not in attributes:
            raise (ValueError,
                   "Missing critical data for person: " + str(attributes))

        self.fnr = attributes["fnr"]

        # NB! This code might raise fodselsnr.InvalidFnrError
        #     We need sanity checking, because LT dumps are suffer from bitrot
        #     (e.g. Swedish SSNs end up as Norwegian. Gah!)
        # logger.debug("self.fnr = %s", self.fnr)

        # the following test will fail for certain non-valid fnr (those
        # coming from PAGA with 5 0(zero) at the end
        # removed check
        # fodselsnr.personnr_ok(self.fnr)
        logger.debug("for debugging purposes: working on fnr:%s", self.fnr)
        # self.fnr = self.fnr.encode("latin1")
        # we do not really need a name (it is in cerebrum), but it might
        # come in handy during debugging stages

        # self.name = "%s %s" % (attributes["fornavn"].encode("latin1"),
        # attributes["etternavn"].encode("latin1"))
        self.name = "%s %s" % (attributes["fornavn"], attributes["etternavn"])
        logger.debug("extracted new person element from FS (%s, %s)",
                     self.fnr, self.name)

    def register_element(self, name, attributes):
        """
        Each <person> element has a number of interesting child
        elements. This method is used for 'attaching' them to person objects.
        """
        if name not in self.INTERESTING_ELEMENTS:
            return

        encoded_attributes = {}
        for key, value in attributes.items():
            # We have to do this charset conversion. No worries, parsing xml
            # takes too little time to be of consideration
            # key = key.encode("latin1")
            # value = value.encode("latin1")
            encoded_attributes[key] = value

        self.elements[name].append(encoded_attributes)

    def get_element(self, name):
        """
        Return a sequence of attributes of all NAME elements.

        #Each item in this sequence is a dictionary of the element's
        attributes (key = attribute name, value = attribute value).
        """
        return self.elements.get(name, [])

    def is_frida(self):
        """
        A person is interesting for FRIDA if he has an active <tils> or
        <gjest> element.

        An element is active if it has dato_fra in the past and dato_til in
        the future (or right *now*).

        FIXME: NB! Since <gjest>-elements do *NOT* have dates yet, any
        person having a <gjest> element is deemed active. Yes, it is wrong,
        but LT dumps violate the DTD.
        """

        return (self.has_active("gjest") or
                self.has_active("tils") or
                # FIXME: remove this as soon as LT dumps respect the DTD
                len(self.elements.get("gjest", [])) > 0)

    def is_employee(self):
        """
        A person is an employee if he has an active <tils> element
        """

        return self.has_active("tils")

    def has_active(self, element):
        """
        Determine whether SELF has an ELEMENT entry with suitable dates.
        """

        for attributes in self.elements.get(element, []):
            start = attributes.get("dato_fra", None)

            end = attributes.get("dato_til", None)

            now = time.strftime("%Y%m%d")

            # That's the beauty of ISO8601 -- date comparisons work right
            if (start and end and
                    start < now <= end):
                return True

        return False

    def has_reservation(self, **attributes):
        """
        Check whether <person> represented by SELF contains at least one
        <res> element with specified ATTRIBUTES.
        """

        items = attributes.items()

        for res in self.elements.get("res", []):
            hit = True
            for attribute, value in items:
                if attribute not in res or res[attribute] != value:
                    hit = False
                    break
            if hit:
                return True

        return False

    def __str__(self):
        """
        This function is mainly for debug purposes
        """
        output = ("<%s %s %s [" %
                  (type(self).__name__,
                   getattr(self, "fnr", "N/A"),
                   getattr(self, "name", "N/A")))

        if self.is_frida():
            output += " F"

        if self.is_employee():
            output += " E"

        output += " ]>"
        return output


class LTPersonParser(xml.sax.ContentHandler, object):
    """
    This class is used to extract <person> elements (defined by
    lt-person.dtd) from the LT dumps.

    *Only* information of interest to the FRIDA project is extracted.

    The interesting elements look like this:

    <person fornavn="Kristi" etternavn="Agerup" navn="Agerup Kristi"
            adrtypekode_privatadresse="EKST"
            adresselinje1_privatadresse="Helene Sembs vei 19"
            poststednr_privatadresse="3610"
            poststednavn_privatadresse="KONGSBERG"
            telefonnr_privattelefon="32720909" fakultetnr_for_lonnsslip="18"
            instituttnr_for_lonnsslip="4" gruppenr_for_lonnsslip="0"
            fodtdag="27" personnr="48259" fodtmnd="6" fodtar="56">
      <tils fakultetnr_utgift="18" instituttnr_utgift="4" gruppenr_utgift="0"
            stillingkodenr_beregnet_sist="1017" prosent_tilsetting="80.0"
            dato_fra="20021201" dato_til="20031031"
            hovedkat="VIT"
            tittel="stipendiat"/>
      <gjest sko="130447" gjestetypekode="EMERITUS"/>
      <res katalogkode="ELKAT" felttypekode="PRIVADR"/>
    </person>

    FIXME: Note that the example above does not validate with lt-person.dtd
    (dato_fra and dato_til are missing from the <gjest>-element).
    """
    PERSON_ELEMENT = LTPersonRepresentation.PERSON_ELEMENT
    INTERESTING_ELEMENTS = LTPersonRepresentation.INTERESTING_ELEMENTS

    def __init__(self, filename, callback_function):
        super(LTPersonParser, self).__init__()

        # Keep the assosiated file name, just for debugging
        self.filename = filename
        # This handler would process person information
        self.callback = callback_function
        # We always keep track of the current person that we gather
        # information on (i.e. current <person> element being parsed)
        self.current_person = None

    def parse(self):
        if not hasattr(self, "filename"):
            logger.error("Missing filename. Operation aborted")
            raise SystemExit('Missing filename. Operation aborted')
        xml.sax.parse(self.filename, self)

    def startElement(self, name, attributes):
        """
        NB! we only handle elements interesting for the FRIDA output.

        Also, if a LTPersonRepresentation object cannot be constructed for
        some reason, that particular <person>-element from FS dump is
        discarded.
        """
        if name == self.PERSON_ELEMENT:
            try:
                self.current_person = None

                self.current_person = LTPersonRepresentation(attributes)

            except ValueError as value:
                logger.error("Failed to construct a person from XML: %s",
                             value)
            except fodselsnr.InvalidFnrError as value:
                logger.error("Failed to construct a person from XML: %s",
                             value)
        elif (name in self.INTERESTING_ELEMENTS and
              self.current_person):
            self.current_person.register_element(name, attributes)

    def endElement(self, name):
        if name == self.PERSON_ELEMENT and self.current_person:
            self.callback(self.current_person)


def output_element(writer, value, element, attributes=dict()):
    """A helper function to output XML elements.

    The output element would look like this:

    <ELEMENT KEY1="VALUE1" KEY2="VALUE2" ... >
      VALUE
    </ELEMENT>

    ... where KEY,VALUE pairs come from ATTRIBUTES

    This function is just a shorthand, to avoid mistyping the element names
    in open and close tags.
    """

    # If there are no attributes and no textual value for the element, we do
    # not need it.
    if not attributes and value is None:
        return

    writer.startElement(element, attributes)
    writer.data(unicode(value))
    writer.endElement(element)


def output_organization(writer, db):
    """
    Output information about <Organization>.

    FIMXE: NB! It might be wise to move all these hardwired values into
    cereconf. They are probably used by several parts of the cerebrum
    anyway.
    """
    writer.startElement("institusjon")

    writer.startElement("institusjonsnr")
    writer.data(cereconf.DEFAULT_INSTITUSJONSNR)
    writer.endElement("institusjonsnr")

    writer.startElement("navnBokmal")
    writer.data("UiT - Norges arktiske universitet")
    writer.endElement("navnBokmal")
    writer.startElement("navnEngelsk")
    writer.data("UiT The Arctic University of Norway")
    writer.endElement("navnEngelsk")

    writer.startElement("akronym")
    writer.data("UIT")
    writer.endElement("akronym")

    writer.endElement("institusjon")


def output_ou_address(writer, db_ou, constants):
    """Output address information for a particular OU."""
    #
    # FIXME: This code is *horrible*. cerebrum has no idea about an OU's
    # address structure. That is, it is impossible to generate anything
    # sensible. This is just a guess (inspired by LDAP people's work) at
    # what might be potentially useful.
    #

    writer.startElement("postnrOgPoststed")
    # We cannot have more than one answer for any given
    # (ou_id, source_system, address_type) triple

    address = db_ou.get_entity_address(constants.system_fs,
                                       constants.address_post)[0]

    city = (address['city'] or 'Tromsø').strip()
    postal_number = (address['postal_number'] or "9037").strip()
    country = (address['country'] or "Norway").strip()
    address_text = (address["address_text"] or "").strip()

    post_nr_city = None
    if city or (postal_number and country):
        post_nr_city = string.join(filter(None,
                                          [postal_number,
                                           (city or "").strip()]))

    output = string.join(filter(None,
                                (address_text,
                                 post_nr_city,
                                 country))).replace("\n", ",")
    if not output:
        logger.error("There is no address information for %s",
                     db_ou.entity_id)

    writer.data(output)
    writer.endElement("postnrOgPoststed")


def output_ou(writer, id, db_ou, stedkode, constants, db):
    """
    Output all information pertinent to a specific OU.

    Each OU is described thus:
    <!ELEMENT enhet (navnBokmal,

    <!ELEMENT norOrgUnit (norOrgUnitName+, norOrgUnitFaculty,
                          norOrgUnitDepartment, norOrgUnitGroup,
                          norParentOrgUnitFaculty,
                          norParentOrgUnitDepartment,
                          norParentOrgUnitGroup, norOrgUnitAcronym+,
                          Addressline, Telephon*, Fax*, URL*)>
    """
    stedkode.clear()
    db_ou.clear()
    stedkode.find(id)
    db_ou.find(id)

    # This entry is not supposed to be published
    if not stedkode.has_spread(constants.spread_ou_publishable):
        logger.debug("Skipping ou_id == %s", id)
        return

    # get language
    language = int(constants.LanguageCode('nb'))
    ou_names = []
    ou_names.append({'language': language,
                     'name': db_ou.get_name_with_language(constants.ou_name,
                                                          language)})
    try:
        ou_acronyms = [{'language': language,
                        'acronym': db_ou.get_name_with_language(
                                constants.ou_name_acronym, language)}]
    except (Errors.NotFoundError, Errors.TooManyRowsError):
        ou_acronyms = [{'language': language, 'acronym': None}]

    # Ufh! I want CL's count-if
    # Check that there is at least one name and at least one
    # acronym that are not empty.
    has_any = (lambda sequence, field:
               [x for x in sequence
                if x[field] is not None])
    if (not (has_any(ou_names, "name") or
             has_any(ou_acronyms, "acronym"))):
        logger.error("Missing name/acronym information for ou_id = %s %s",
                     id, stedkode)
        return

    writer.startElement("enhet")

    # institusjonsnr
    for value, element in ((cereconf.DEFAULT_INSTITUSJONSNR, "institusjonsnr"),
                           (stedkode.fakultet, "avdnr"),
                           (stedkode.institutt, "undavdnr"),
                           (stedkode.avdeling, "gruppenr")):
        output_element(writer, value, element)

    # NB! Extra lookups here cost us about 1/3 of the time it takes to
    #     generate all information on OUs
    parent_id = db_ou.get_parent(constants.perspective_fs)
    # This is a hack (blame baardj) for the root of the organisational
    # structure.
    if parent_id is None:
        parent_id = id

    # find parent. NB! Remember to reset stedkode
    stedkode.clear()
    stedkode.find(parent_id)

    for value, element in (
            (cereconf.DEFAULT_INSTITUSJONSNR, "institusjonsnrUnder"),
            (stedkode.fakultet, "avdnrUnder"),
            (stedkode.institutt, "undavdnrUnder"),
            (stedkode.avdeling, "gruppenrUnder")):
        output_element(writer, value, element)

    stedkode.clear()
    stedkode.find(id)

    for entry in ou_names:
        if not entry['name']:
            continue
        attributes = {}
        writer.startElement("navnBokmal", attributes)
        writer.data(entry['name'])
        writer.endElement("navnBokmal")

    for entry in ou_acronyms:
        if not entry['acronym']:
            continue
        attributes = {}
        writer.startElement("akronym", attributes)
        writer.data(entry['acronym'].lower())
        writer.endElement("akronym")

    # Addressline
    output_ou_address(writer, db_ou, constants)

    for row in db_ou.get_contact_info(source=constants.system_paga,
                                      type=constants.contact_phone):
        output_element(writer, row.contact_value, "Fax")

    # Fax
    for row in db_ou.get_contact_info(source=constants.system_paga,
                                      type=constants.contact_fax):
        output_element(writer, row.contact_value, "Fax")

    # FIXME: URLs! For now we will simply ignore them
    # writer.startElement("URLBokmal")
    # writer.data("Not implemented")
    # writer.endElement("URLBokmal")

    # UIT ADDITION:
    # insert NSD kode
    nsd_kode = db_ou.get_external_id(id_type=constants.externalid_nsd)
    if nsd_kode:
        nsd_kode = nsd_kode[0]['external_id']
    else:
        nsd_kode = ""
    output_element(writer, str(nsd_kode), "NSDKode")

    writer.endElement("enhet")


def output_ous(writer, db):
    """
    Output information about all interesting OUs.

    An OU is interesting to FRIDA, if it is active in LT *now*
    (i.e. most recent LT dump) and is explicitly set up for
    publishing in a catalogue service (has the right spread)
    """
    db = Factory.get('Database')()
    db_ou = Factory.get("OU")(db)
    stedkode = Factory.get("OU")(db)
    constants = Factory.get("Constants")(db)

    writer.startElement("organisasjon")
    for id in db_ou.list_all():
        logger.debug("id is:%s", id['name'])
        output_ou(writer, id["ou_id"], db_ou, stedkode, constants, db)
    writer.endElement("organisasjon")


def construct_person_attributes(writer, pobj, db_person, constants):
    """
    Construct a dictionary containing all attributes for the FRIDA <person>
    element represented by pobj.

    This function assumes that db_person is already associated to the
    appropriate database row(s) (via a suitable find*-call).
    """
    attributes = {}

    # This *cannot* fail or return more than one entry
    # NB! Although pobj.fnr is the same as row.extenal_id below, looking it
    #     up is an extra check for data validity
    row = db_person.get_external_id(constants.system_paga,
                                    constants.externalid_fodselsnr)[0]
    attributes["fnr"] = str(row['external_id'])

    # The rule for selecting primary affiliation is pretty simple:
    # 1. If there is an ANSATT/vitenskapelig affiliation then
    #    Affiliation = Faculty
    # 2. If there is an ANSATT/tekadm affiliation then Affiliation = Staff
    # 3. Otherwise Affiliation = Member
    #
    # We can do this in one database lookup, at the expense of much uglier
    # code
    # if db_person.list_affiliations(db_person.entity_id,
    #                               constants.system_lt,
    #                               constants.affiliation_ansatt,
    #                               constants.affiliation_status_ansatt_vit):
    #    attributes["Affiliation"] = "Faculty"
    # elif db_person.list_affiliations(db_person.entity_id,
    #                                 constants.system_lt,
    #                                 constants.affiliation_ansatt,
    #                                 constants.affiliation_status_ansatt_
    #                                 tekadm):
    #    attributes["Affiliation"] = "Staff"
    # else:
    #    attributes["Affiliation"] = "Member"
    # fi

    # The reservations rules are a bit funny:
    #
    # If P is an employee, then
    #   If P has <res katalogkode = "ELKAT"> too then
    #     Reservation = "yes"
    #   Else
    #     Reservation = "no"
    # Else
    #   If P has <res katalogkode="ELKAT"
    #                 felttypekode="GJESTEOPPL"> then
    #     Reservation = "no"
    #   Else
    #     Reservation = "yes"
    # Fi
    if pobj.is_employee():
        if pobj.has_reservation(katalogkode="ELKAT"):
            attributes["reservert"] = "J"
        else:
            attributes["reservert"] = "N"
    else:
        if pobj.has_reservation(katalogkode="ELKAT",
                                felttypekode="GJESTEOPPL"):
            attributes["reservert"] = "N"
        else:
            attributes["reservert"] = "J"
    attributes["reservert"] = "N"
    return attributes


def output_employment_information(writer, pobj):
    """
    Output all employment information pertinent to a particular person (POBJ).

    I.e. convert from <tils>-elements in LT dump to <Tilsetting>
    elements in FRIDA export.

    Each employment record is written out thus:

    <!ELEMENT Tilsetting (Stillingkode, StillingsTitle, Stillingsandel,
                          StillingFak, StillingInstitutt, StillingGruppe,
                          fraDato, tilDato)>
    <!ATTLIST Tilsetting Affiliation ( Staff | Faculty ) #REQUIRED>

    These elements/attributes are formed from the corresponding entries
    represented by POBJ.

    """
    # There can be several <tils> elements for each person
    # Each 'element' below is a dictionary of attributes for that particular
    # <tils>
    writer.startElement("ansettelser")
    for element in pobj.get_element("tils"):

        # if element["hovedkat"] == "VIT":
        #             attributes = {"Affiliation": "Faculty"}
        #         elif element["hovedkat"] == "�VR":
        #             attributes = {"Affiliation": "Staff"}
        #         else:
        #             logger.error("Aiee! %s has no suitable employment
        #             affiliation %s",
        #                          pobj.fnr, str(element))
        #             continue
        # fi

        # writer.startElement("Tilsetting", attributes)
        writer.startElement("ansettelse")

        # FRIDA wants date at the format YYYYMMDD
        element["dato_fra"] = element["dato_fra"]
        writer.startElement("institusjonsnr")
        writer.data(cereconf.DEFAULT_INSTITUSJONSNR)
        writer.endElement("institusjonsnr")

        for output, input in [("avdnr", "fakultetnr_utgift"),
                              ("undavdnr", "instituttnr_utgift"),
                              ("gruppenr", "gruppenr_utgift"),
                              ("stillingskode", "stillingskode"),
                              ("datoFra", "dato_fra"),
                              # ("datoTil", "dato_til"),
                              ("stillingsbetegnelse", "tittel"),
                              ("stillingsandel", "stillingsandel"),
                              ]:

            writer.startElement(output)
            # UIT: must minimize the element["tittel"] entry
            # element["tittel"] = element["tittel"].lower().decode(
            #   'iso-8859-1')

            # value = element[input].decode('iso8859-1')
            value = element[input]
            if input == 'tittel':
                value = value.lower()

            # writer.data(element[input])
            writer.data(value)
            writer.endElement(output)

        writer.endElement("ansettelse")
    writer.endElement("ansettelser")


def find_publishable_sko(sko, ou_cache):
    """
    Locate a publishable OU starting from sko and return its sko.

    We walk upwards the hierarchy tree until we run out of parents or a until
    a suitable publishable OU is located.
    """
    ou = ou_cache.get(sko)
    while ou:
        if ou.publishable:
            publishable_sko = ou.get_id(ou.NO_SKO, None)
            if not publishable_sko:
                logger.warn("OU %s has to sko and will not be published",
                            list(publishable_sko.iterids()))
            return publishable_sko

        parent_sko = None
        if ou.parent:
            assert ou.parent[0] == ou.NO_SKO
            parent_sko = ou.parent[1]
        ou = ou_cache.get(parent_sko)

    return None


def output_assignments(writer, sequence, ou_cache, blockname, elemname, attrs):
    """
    Output tilsetting/gjest information.

    The format is:
    <blockname>
      <elemname>
        <k1>x.v1</k1>
        <k2>x.v2</k2>
      </elemname>
    </blockname>

    ... where attrs is a mapping from k1 -> v1 and sequence contains the x's
    to be output.

    Parameters:
    writer  helper class to generate XML output
    sequence    a sequence of objects that we want to output. each object can
                be indexed as a dictionary.
    ou_cache    OU mappings registered for this import. Used to locate
                publishable OUs
    blockname   XML element name for a grouping represented by sequence.
    elemname    XML element name for each element of sequence.
    attrs       A dictionary-like object key->xmlname, where key can be used
                to extract values from each member of sequence.
    """
    # if there is nothing to output we are done
    if not sequence:
        return

    if blockname:
        writer.startElement(blockname)

    for item in sequence:

        sko = item["place"]
        publishable_sko = sko
        #        publishable_sko = find_publishable_sko(sko, ou_cache)
        #        if not publishable_sko:
        #            logger.debug("Cannot locate publishable sko starting
        #            from %s", sko)
        #            continue

        writer.startElement(elemname)
        for value, xmlelement in (
                (cereconf.DEFAULT_INSTITUSJONSNR, "institusjonsnr"),
                (publishable_sko[0], "avdnr"),
                (publishable_sko[1], "undavdnr"),
                (publishable_sko[2], "gruppenr")):
            output_element(writer, value, xmlelement)

        for key, xmlelement in attrs.iteritems():
            # The key is among the names passed to us, but since it is output
            # specially, no action should be taken here.
            if key == "place":
                continue
            value = item[key]
            # FIXME: DateTime hack. SIGTHTBABW
            if hasattr(value, "strftime"):
                value = value.strftime("%Y-%m-%d")
            output_element(writer, value, xmlelement)

        writer.endElement(elemname)

    if blockname:
        writer.endElement(blockname)


def output_guest_information(writer, pobj):
    """
    Output all guest information pertinent to a particular person (POBJ).

    I.e. convert from <gjest>-elements in LT dump to <Gjest> elements in
    FRIDA export.

    Each guest record is written out thus:

    <!ELEMENT Guest (guestFak, guestInstitutt, guestGroup, fraDato, tilDato)>
    <!ATTLIST Guest  Affiliation
                     ( Emeritus | Stipendiat | unknown ) #REQUIRED>
    """
    for element in pobj.get_element("gjest"):

        attributes = {"Affiliation": "unknown"}
        if element["gjestetypekode"] == "EMERITUS":
            attributes = {"Affiliation": "Emeritus"}
        elif element["gjestetypekode"] == "EF-STIP":
            attributes = {"Affiliation": "Stipendiat"}
        # fi

        writer.startElement("Gjest", attributes)

        # This is *unbelievably* braindead. Atomic keys with hidden parts
        # are The Wrong Thing[tm]. The LT dump should be changed to
        # represent this information in the same way as with <tils>
        key = element["sko"]
        for output, value in [("guestFak", key[0:2]),
                              ("guestInstitutt", key[2:4]),
                              ("guestGroup", key[4:6]),
                              ]:
            writer.startElement(output)
            writer.data(value)
            writer.endElement(output)
        # od

        # FIXME: The source has *no* information about dates. It is a DTD
        # violation but we cannot do anything in FRIDA until it is rectified
        # in import_LT

        writer.endElement("Gjest")


def output_guest_information_2(writer, db_person, const, stedkode):
    external_id_data = db_person.get_external_id(
        source_system=const.system_x,
        id_type=const.externalid_fodselsnr)
    if len(external_id_data) > 0:
        # This person comes from system_x. need to add a guest affiliation to
        # its profile
        try:
            aff = db_person.get_affiliations()
            writer.startElement("gjester")
            for single_aff in aff:
                logger.debug("aff=%s", single_aff)
                if single_aff['source_system'] == const.system_x:
                    logger.debug("WE HAVE GUEST: %s", db_person.entity_id)
                    stedkode.clear()
                    aff_id = single_aff['ou_id']
                    aff_str = const.PersonAffStatus(single_aff['status'])
                    stedkode.find(aff_id)
                    writer.startElement("gjest")

                    writer.startElement("institusjonsnr")
                    writer.data(str(stedkode.institusjon))
                    writer.endElement("institusjonsnr")

                    writer.startElement("avdnr")
                    writer.data(str(stedkode.fakultet))
                    writer.endElement("avdnr")

                    writer.startElement("undavdnr")
                    writer.data(str(stedkode.institutt))
                    writer.endElement("undavdnr")

                    writer.startElement("gruppenr")
                    writer.data(str(stedkode.avdeling))
                    writer.endElement("gruppenr")

                    writer.startElement("datoFra")
                    create_date = single_aff['create_date']
                    dato_fra = "{0}-{1}-{2}".format(
                        create_date.year, create_date.month, create_date.day)
                    writer.data(dato_fra)
                    writer.endElement("datoFra")

                    writer.startElement("gjestebetegnelse")
                    writer.data(aff_str.status_str)
                    writer.endElement("gjestebetegnelse")

                    writer.endElement("gjest")
            writer.endElement("gjester")

        except (Errors.NotFoundError, Errors.TooManyRowsError):
            logger.debug(
                "Warning: unable to insert guest data for person:%s",
                db_person.entity_id)


def output_account_info(writer, person_db):
    """Output primary account and e-mail information for person_db."""
    primary_account = person_db.get_primary_account()
    if primary_account is None:
        logger.info("Person %s has no accounts", person_db.entity_id)
        return

    account_db = Factory.get("Account")(cerebrum_db)
    account_db.find(primary_account)
    output_element(writer, account_db.get_account_name(), "brukernavn")

    try:
        primary_email = account_db.get_primary_mailaddress()
        output_element(writer, primary_email, "epost")
    except Errors.NotFoundError:
        logger.info("person %s has no primary e-mail address",
                    person_db.entity_id)


def filter_timelonnet(person_db):
    """
    Filter out persons with a single ansatt affiliation who's status is
    'timelonnet_midlertidig'
    """
    aff_status = person_db.get_affiliations()

    i_am_not_timelonnet = True
    for aff_stat in aff_status:
        if aff_stat['status'] != int(
                constants.affiliation_status_timelonnet_midlertidig):
            i_am_not_timelonnet = False

    if i_am_not_timelonnet:
        logger.info(
            "person_id:%s only has a single affiliation and it is timelonnet."
            " skipping...", person_db.entity_id)
        return False
    else:
        return True


def output_person(writer, pobj, phd_cache, system_source):
    """
    Output all information pertinent to a particular person (POBJ).

    Each <Person> is described thus:

    <!ELEMENT Person (sn, givenName?, uname?,
                      emailAddress?, Telephone?,
                      Tilsetting*, Guest*)>

    <!ATTLIST Person NO_SSN CDATA #REQUIRED
              Affiliation ( Staff | Faculty | Member ) #REQUIRED
              Reservation ( yes | no ) #REQUIRED>
    """
    person_db.clear()
    account_db.clear()

    # NB! There can be *only one* FNR per person in LT (PK in
    # the person_external_id table)
    try:
        person_db.find_by_external_id(constants.externalid_fodselsnr,
                                      pobj.fnr,
                                      system_source)
    except Errors.NotFoundError:
        logger.error(
            "Person with FNR %s not found in BAS - skipping. Check for "
            "inconsistent FNR", pobj.fnr)
        return

    # Filter out persons with a single employee affiliation whos status is
    # timelonnet
    retval = filter_timelonnet(person_db)
    if not retval:
        return

    writer.startElement("person",
                        construct_person_attributes(writer,
                                                    pobj,
                                                    person_db,
                                                    constants))
    # surname
    navn = person_db.get_name(system_cached, constants.name_last)
    output_element(writer, navn, "etternavn")

    # first name
    navn = person_db.get_name(system_cached, constants.name_first)
    output_element(writer, navn, "fornavn")

    # if person in phd_cache, delete!
    phds = phd_cache.get(int(person_db.entity_id), [])
    if phds:
        del phd_cache[int(person_db.entity_id)]

    output_account_info(writer, person_db)

    # <Telephone>?
    # We need the one with lowest contact_pref, if there are many
    contact = person_db.get_contact_info(source=constants.system_tlf,
                                         type=constants.contact_phone)
    contact.sort(lambda x, y: cmp(x.contact_pref, y.contact_pref))

    if len(contact) > 0:
        contact = contact[0]['contact_value']
        if len(contact) == 5:
            if ((contact[0] == '5') and (contact[1] == '0')):
                contact = cereconf.INTERNAL_PHONE_PREFIX_FINMARK + contact
            else:
                contact = cereconf.INTERNAL_PHONE_PREFIX + contact
    else:
        contact = ''

    output_element(writer, contact, "telefonnr")
    output_employment_information(writer, pobj)
    output_guest_information(writer, pobj)
    writer.endElement("person")


def extract_names(person_db, kinds):
    """Return a mapping kind->name of names of the required kinds."""
    result = {}
    all_names = person_db.get_names()
    for name in all_names:
        kind = int(name["name_variant"])
        source = int(name["source_system"])
        value = name["name"]
        if kind not in kinds:
            continue

        # if we have not seen the proper name variant, grab it now
        if kind not in result:
            result[kind] = value
        # ... and if current source matches source_system, then this is the
        # best match possible, so take it.
        elif int(source) == int(source_system):
            result[kind] = value
    return result


def output_phd_students(writer, sysname, phd_students, ou_cache):
    """
    Output information about PhD students based on Cerebrum only.

    There may be phd students who have no employment records.
    However, they still need access to FRIDA and we need to gather as
    much information as possible about them.
    """
    # A few helper mappings first
    # source system name => group with individuals hidden in catalogues
    sys2group = {"system_paga": "PAGA-elektroniske-reservasjoner",
                 "system_sap": "SAP-lektroniske-reservasjoner", }
    # name constant -> xml element for that name constant
    name_kinds = dict(((int(constants.name_last), "etternavn"),
                       (int(constants.name_first), "fornavn"),
                       (int(constants.name_work_title), "tittel")))
    # contact constant -> xml element for that contact constant
    contact_kinds = dict(((int(constants.contact_phone), "telefonnr"),
                          (int(constants.contact_fax), "telefaxnr"),
                          (int(constants.contact_url), "URL")))

    group = Factory.get("Group")(cerebrum_db)
    try:
        group.find_by_name(sys2group[sysname])
        reserved = group.get_members()
    except Errors.NotFoundError:
        reserved = []  # was set()

    for person_id, phd_records in phd_students.iteritems():
        try:
            person_db.clear()
            person_db.find(person_id)
            # We can be a bit lenient here.
            fnr = person_db.get_external_id(
                id_type=constants.externalid_fodselsnr)
            if fnr:
                fnr = fnr[0]["external_id"]
            else:
                logger.warn("No fnr for person_id %s", person_id)
                continue
        except Errors.NotFoundError:
            logger.warn(
                "Cached id %s not found in the database. This cannot happen",
                person_id)
            continue

        res_status = {True: "J", False: "N"}[person_id in reserved]
        writer.startElement("person", {"fnr": fnr, "reservert": res_status})

        names = extract_names(person_db, name_kinds)
        for variant, xmlname in name_kinds.iteritems():
            value = names.get(variant)
            if value:
                # RMI000 - Geir Magne Vangen iflg epost ba om denne
                # endringen selv om den er mot DTDen
                if xmlname == 'tittel':
                    xmlname = 'personligTittel'
                output_element(writer, value, xmlname)

        output_account_info(writer, person_db)

        for contact_kind in contact_kinds:
            value = person_db.get_contact_info(source_system, contact_kind)
            if value:
                value = value[0]["contact_value"]
                output_element(writer, value, contact_kinds[contact_kind])

        names = dict((("start", "datoFra"),
                      ("end", "datoTil"),
                      ("code", "gjestebetegnelse"),
                      ("place", None)))
        output_assignments(writer, phd_records, ou_cache, "gjester", "gjest",
                           names)
        writer.endElement("person")


def cache_phd_students():
    """Load all PhD students from cerebrum and return a set of their IDs."""
    result = {}
    for row in person_db.list_affiliations(
            status=constants.affiliation_status_student_drgrad):
        key = int(row["person_id"])

        try:
            ou_db.clear()
            ou_db.find(row["ou_id"])
        except Errors.NotFoundError:
            logger.warn("OU with ou_id %s does not exist. This cannot happen",
                        row["ou_id"])
            continue

        value = {"start": row["create_date"],
                 "end": row["deleted_date"],
                 "code": "DOKTORGRADSSTUDENT",
                 "place": (ou_db.fakultet, ou_db.institutt, ou_db.avdeling)}
        result.setdefault(key, []).append(value)

    return result


def output_people(writer, db, person_file):
    """
    Output information about all interesting people.

    LTPersonRepresentation.is_frida describes what kind of people are
    'interesting' in FRIDA context.
    """
    logger.info("extracting people from %s", person_file)
    phd_students = cache_phd_students()
    logger.info("cached PhD students (%d people)", len(phd_students))

    #
    # Sanity-checking
    #
    for c in ["system_paga", "affiliation_ansatt",
              "affiliation_status_ansatt_tekadm",
              "affiliation_status_ansatt_vitenskapelig",
              "externalid_fodselsnr",
              "name_last", "name_first", "contact_phone"]:
        logger.debug("%s -> %s (%d)",
                     c, getattr(constants, c), getattr(constants, c))
    writer.startElement("personer")
    parser = LTPersonParser(person_file,
                            lambda p: output_person(
                                writer=writer,
                                pobj=p,
                                phd_cache=phd_students,
                                system_source=constants.system_paga))
    parser.parse()

    logger.info("still has cached PhD students (%d people)", len(phd_students))
    output_phd_students(writer, 'system_paga', phd_students, {})

    system_x_parser = SystemXRepresentation()
    system_x_parser.execute(person_file, writer=writer,
                            system_source=constants.system_x)
    writer.endElement("personer")


def output_ous_new(writer, sysname, oufile):
    """Run through all OUs and publish the interesting ones.

    An OU is interesting to FRIDA, if:
    - the OU is supposed to be published (marked as such in the data source)
    - it has been less than a year since the OU has been terminated.
    """
    # First we build an ID cache.
    ou_cache = {}
    parser = system2parser('system_lt')(oufile, logger, False)
    for ou in parser.iter_ou():
        sko = ou.get_id(ou.NO_SKO, None)
        if sko:
            ou_cache[sko] = ou

    logger.info("Cached info on %d OUs from %s", len(ou_cache), oufile)

    db = Factory.get('Database')()
    # db_ou = Factory.get("OU")(db)
    sko_class = Factory.get("OU")(db)
    stedkode = Factory.get("OU")(db)
    constants = Factory.get("Constants")(db)

    writer.startElement("organisasjon")
    for ou in ou_cache:
        sko_class.clear()
        try:
            # pprint(ou)
            sko_class.find_stedkode(ou[0], ou[1], ou[2], 186)
        except EntityExpiredError:
            logger.error("OU %s%s%s expired - not exported to Frida",
                         ou[0], ou[1], ou[2])
            continue
        id = sko_class.entity_id
        sko_class.clear()
        tmp_sko = "%s%s%s" % (ou[0], ou[1], ou[2])
        if tmp_sko not in cereconf.CRISTIN_OU_EXCLUDE_LIST:
            output_ou(writer, id, sko_class, stedkode, constants, db)
        else:
            logger.debug("%s not exported to Cristin", tmp_sko)
    writer.endElement("organisasjon")


def output_xml(output_file,
               data_source,
               target,
               person_file,
               sted_file):
    """
    Initialize all connections and start generating the xml output.

    OUTPUT_FILE names the xml output.
    DATA_SOURCE and TARGET are elements in the xml output.
    PERSON_FILE is the name of the LT dump (used as input).
    """
    # Nuke the old copy
    output_stream = SimilarSizeWriter(output_file, "wb")
    output_stream.set_size_change_limit(15)
    writer = xmlprinter.xmlprinter(output_stream,
                                   indent_level=2,
                                   # Output is for humans too
                                   data_mode=True,
                                   input_encoding='utf-8')
    db = Factory.get('Database')()

    # Here goes the hardcoded stuff
    writer.startDocument(encoding='iso-8859-1')
    # writer.startElement("XML-export")
    xml_options = {'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
                   'xsi:noNamespaceSchemaLocation':
                       'http://www.usit.uio.no/prosjekter/frida/dok/' +
                       'import/institusjonsdata/schema/Frida-import-1_0'
                       '.xsd'}
    writer.startElement("fridaImport", xml_options)

    writer.startElement("beskrivelse")
    writer.startElement("kilde")
    writer.data(data_source)
    writer.endElement("kilde")
    writer.startElement("dato")
    # ISO8601 style -- the *only* right way :)
    writer.data(time.strftime("%Y-%m-%d"))
    writer.endElement("dato")
    writer.startElement("mottager")
    writer.data(target)
    writer.endElement("mottager")

    writer.endElement("beskrivelse")

    # Organization "header"
    # FIXME: It's all hardwired
    output_organization(writer, db)
    # Dump all OUs
    output_ous_new(writer, 'system_paga', sted_file)

    # Dump all people
    output_people(writer, db, person_file)

    writer.endElement()
    writer.endDocument()
    output_stream.close()


def main():
    """Start method for this script."""
    date = time.localtime()
    date_today_paga = "%02d-%02d-%02d" % (date[0], date[1], date[2])
    date_today = "%02d%02d%02d" % (date[0], date[1], date[2])

    default_output_file = os.path.join(cereconf.DUMPDIR, 'cristin',
                                       'cristin.xml')
    default_person_file = os.path.join(cereconf.DUMPDIR, 'employees',
                                       'paga_persons_{0}.xml'.format(
                                           date_today_paga))
    default_sted_file = os.path.join(cereconf.DUMPDIR, 'ou',
                                     'uit_ou_{0}.xml'.format(date_today))
    # FIXME: Maybe snatch these from cereconf?
    target = "FRIDA"

    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument('-o',
                        '--output-file',
                        dest='output_file',
                        default=default_output_file,
                        help='Output file')
    parser.add_argument('-p',
                        '--person-file',
                        dest='person_file',
                        default=default_person_file,
                        help='Output file')
    parser.add_argument('-s',
                        '--sted-file',
                        dest='sted_file',
                        default=default_sted_file,
                        help='Sted input file')
    parser.add_argument('-d',
                        '--data-source',
                        dest='data_source',
                        default='UITO',
                        help='Source that generates frida.xml '
                             '(Default: UITO)')
    parser.add_argument('-t',
                        '--target',
                        dest='target',
                        default='FRIDA',
                        help='Result target. (Default: FRIDA)')

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Starting Cristin exports')
    person_parser = make_parser()
    current_person_handler = PersonHandler(args.person_file, person_helper)
    person_parser.setContentHandler(current_person_handler)
    person_parser.parse(args.person_file)

    logger.info("Generating Cristin export")
    output_xml(output_file=args.output_file,
               data_source=args.data_source,
               target=target,
               person_file=args.person_file,
               sted_file=args.sted_file)
    logger.info("Generating Cristin export finished")


if __name__ == "__main__":
    main()
