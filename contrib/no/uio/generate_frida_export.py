#! /usr/bin/env python
# -*- coding: iso8859-1 -*-
#
# Copyright 2003 University of Oslo, Norway
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

This file is part of the Cerebrum framework.

It generates an XML dump, suitable for importing into the FRIDA project (for
more information on FRIDA, start at <URL:
http://www.usit.uio.no/prosjekter/frida/pg/>). The output format is
specified in:

<URL: http://www.usit.uio.no/prosjekter/frida/dok/import/institusjonsdata/schema/Frida-import-1_0.xsd>
<URL: http://www.usit.uio.no/prosjekter/frida/dok/import/institusjonsdata/>

The uiocerebrum project has some additional notes
(cvs.uio.no:/uiocerebrum/docs/frida/frida-export.txt).

Although the original specification places a limit on the length of certain
(string) values, we do not enforce those. Furthermore, the address
'calculations' are a bit involved.

All information for the XML dump is fetched from the cerebrum database.

FIXME: Right now (2005-01-03), Cerebrum has no information about OU
lifetimes. Therefore this information is gathered from the XML file produced
by import_from_LT.py. This is a temporary solution while we wait for mod_HR.
"""

import sys
import time
import getopt
import string

import cerebrum_path
import cereconf

import Cerebrum
from Cerebrum import Database
from Cerebrum.Utils import Factory
from Cerebrum.Utils import AtomicFileWriter
from Cerebrum.extlib import xmlprinter
from Cerebrum.extlib.sets import Set

from Cerebrum.modules.no import fodselsnr
from Cerebrum.Cache import memoize_function





def output_element(writer, value, element, attributes = {}):
    '''
    A helper function to write out xml elements.

    The output element would look like this:

    <ELEMENT KEY1="VALUE1" KEY2="VALUE2" ... >
      VALUE
    </ELEMENT>

    ... where KEY,VALUE pairs come from ATTRIBUTES

    This function is just a shorthand, to avoid mistyping the element names
    in open and close tags
    '''

    # skip "empty" elements
    if not attributes and (value is None or not str(value)):
        return
    # fi

    writer.startElement(element, attributes)
    writer.data(str(value))
    writer.endElement(element)
# end output_element


def output_contact_element(writer, contact_entity, type, element, constants):
    """
    A help function for outputting contact information
    """

    sequence = contact_entity.get_contact_info(source = constants.system_lt,
                                               type = type)
    sequence.sort(lambda x, y: cmp(x.contact_pref, y.contact_pref))
    value = ""
    if sequence: value = sequence[0].contact_value

    output_element(writer, value, element)
# end output_contact_element


def output_OU_address(writer, db_ou, constants):
    """
    Output address information for a particular OU.

    """
    #
    # FIXME: This code is *horrible*. cerebrum has no idea about an OU's
    # address structure. That is, it is impossible to generate anything
    # sensible. This is just a guess (inspired by LDAP people's work) at
    # what might be potentially useful.
    # 
    
    address = db_ou.get_entity_address(constants.system_lt,
                                       constants.address_post)

    addr_text, post_nr_city, country = ("", "", "")

    # Unfortunately, there are OUs without any addresses registered
    if not address:
        logger.error("No address information for %s is registered",
                     db_ou.entity_id)
    else:
        # We cannot have more than one answer for any given
        # (ou_id, source_system, address_type) triple
        address = address[0]

        city = address["city"]
        po_box = address["p_o_box"]
        postal_number = address["postal_number"]
        country = address["country"] or ""
        
        if (po_box and int(postal_number or 0) / 100 == 3):
            addr_text = "Pb. %s - Blindern" % po_box
        else:
            addr_text = (address["address_text"] or "").strip()
        # fi
        
        post_nr_city = ""
        if city or (postal_number and country):
            post_nr_city = string.join(filter(None,
                                              [postal_number,
                                               (city or "").strip()]))
        # fi
    # fi

    output_element(writer, addr_text, "postadresse")
    output_element(writer, post_nr_city, "postnrOgPoststed")
    output_element(writer, country, "land")
# end output_OU_address


#
# Mapping ou_id -> publishable_id.
#
# publishable_id is any id in the OU hierarchy (starting from ou_id and
# walking upwards toward the root) for which katalog_merke = 'T'
def find_suitable_OU(ou, id, constants):
    """
    This is a caching wrapper around __find_suitable_OU
    """
    child = int(id)

    parent = __find_suitable_OU(ou, child, constants)
    if parent is not None:
        parent = int(parent)
    # fi
    
    return parent
# end find_suitable_OU
find_suitable_OU = memoize_function(find_suitable_OU)



def find_sko(ou, id):
    """
    """

    try:
        ou.clear()
        ou.find(id)
    except Cerebrum.Errors.NotFoundError:
        return ""
    else:
        return int(ou.fakultet), int(ou.institutt), int(ou.avdeling)
    # yrt
# end find_sko
find_sko = memoize_function(find_sko)



def __find_suitable_OU(ou, id, constants):
    """
    Return ou_id for an OU x that:

    * x.entity_id = id or x is a parent of the OU with id 'id'.
    * x.katalog_merke = 'T'

    ... or None if no such id is found.

    While walking upward the organization tree, we consider LT perspective
    only.
    """

    try:
        ou.clear()
        ou.find(id)

        if ou.katalog_merke == 'T':
            return id
        # fi

        parent_id = ou.get_parent(constants.perspective_lt)
        logger.debug("parent search: %s -> %s",
                     ou.entity_id, parent_id)
                 
        if (parent_id is not None and 
            parent_id != ou.entity_id):
            return __find_suitable_OU(ou, parent_id, constants)
        # fi
    except Cerebrum.Errors.NotFoundError, value:
        logger.error("AIEE! Looking up an OU failed: %s", value)
        return None
    # yrt

    return None
# end __find_suitable_OU



_ou_cache = Set()
def output_OU(writer, start_id, db_ou, parent_ou, lifetimes, constants):
    '''
    Output all information pertinent to a specific OU

    Each OU is described thus:

    <enhet>
      <institusjonsnr>...</...>      <!-- stedkode.institusjon -->
      <avdnr>...</avdnr>             <!-- stedkode.fakultet -->
      <undavdnr>...</undavdnr>       <!-- stedkode.institutt -->
      <gruppenr>...</gruppenr>       <!-- stedkode.avdeling -->
      <institusjonsnrUnder>...</...> <!-- parent.stedkode.institusjon -->
      <avdnrUnder>...</...>          <!-- parent.stedkode.fakultet -->
      <undavdnrUnder>...</...>       <!-- parent.stedkode.institutt -->
      <gruppenrUnder>...</...>       <!-- parent.stedkode.avdeling -->

      <datoAktivFra>...</...>        <!-- LT.STED.DATO_OPPRETTET -->
      <datoAktivTil>...</...>        <!-- LT.STED.DATO_NEDLAGT -->
      <navnBokmal>...</...>          <!-- LT.STED.STEDLANGNAVN_BOKMAL
                                                  STEDKORTNAVN_BOKMAL
                                                  STEDNAVNFULLT
                                                  STEDNAVN -->
      <navnEngelsk>...</...>         <!-- LT.STED.STEDLANGNAVN_ENGELSK
                                                  STEDKORTNAVN_ENGELSK -->
      <akronym>...</...>             <!-- LT.STED.AKRONYM -->
      <postadresse>...</...>    <!-- LT.STED.ADDRESSELINJE{1+2}_INTERN_ADR -->
      <postnrOgPoststed>...</...>    <!-- LT.STED.POSTSTEDNR_INTERN_ADR +
                                          LT.STED.POSTSTEDNAVN_INTERN_ADR  -->
      <land>...</...>                <!-- LT.STED.LANDNAVN_INTERN_ADR -->
      <telefonnr>                    <!-- LT.STEDKOMM.TELEFONNR &&
                                          LT.STEDKOMM.KOMMTYPEKODE = "TLF" &&
                                          MIN(LT.STEDKOMM.TLFPREFTEGN) -->
      <telefaxnr>                    <!-- LT.STEDKOMM.TELEFONNR &&
                                          LT.STEDKOMM.KOMMTYPEKODE = "FAX"
                                          MIN(LT.STEDKOMM.TLFPREFTEGN -->
      <epost>                        <!-- LT.STEDKOMM.KOMMNRVERDI &&
                                          LT.STEDKOMM.KOMMTYPEKODE = "EPOST"
                                          MIN(LT.STEDKOMM.TLFPREFTEGN) --> 
      <URLBokmal>                    <!-- LT.STEDKOMM.KOMMNRVERDI &&
                                          LT.STEDKOMM.KOMMTYPEKODE = "URL"
                                          MIN(LT.STEDKOMM.TLFPREFTEGN) -->
    </enhet>
    '''

    # 
    # Find the OU in Cerebrum
    #
    id = find_suitable_OU(db_ou, start_id, constants)
    if id is None:
        sko = find_sko(db_ou, start_id)
        logger.warn("Cannot find an OU with katalog_merke = 'T' " +
                    "from id = %s (sko: %s)", start_id, sko)
        return
    # fi

    # Skip duplicates
    if int(id) in _ou_cache:
        return
    # fi

    # Cache for future reference
    _ou_cache.add(int(id))
    if int(id) != int(start_id):
        logger.debug("ID %s converted to %s", id, start_id)
    # fi

    db_ou.clear()
    db_ou.find(id)

    #
    # Locate the parent
    # 
    parent_id = db_ou.get_parent(constants.perspective_lt)
    # This is a hack for the root of the organisational structure.
    # I.e. the root of the OU structure is its own parent
    if parent_id is None:
        parent_id = db_ou.entity_id
    # fi

    parent_ou.clear()
    parent_ou.find(parent_id)

    #
    # Output the element 
    #
    writer.startElement("enhet")

    for attribute, element in (("institusjon", "institusjonsnr"),
                               ("fakultet", "avdnr"),
                               ("institutt", "undavdnr"),
                               ("avdeling", "gruppenr")):
        output_element(writer, getattr(db_ou, attribute), element)
    # od

    for attribute, element in (("institusjon", "institusjonsnrUnder"),
                               ("fakultet", "avdnrUnder"),
                               ("institutt", "undavdnrUnder"),
                               ("avdeling", "gruppenrUnder")):
        output_element(writer, getattr(parent_ou, attribute), element)
    # od

    sko = int(db_ou.fakultet), int(db_ou.institutt), int(db_ou.avdeling)

    # TBD: If the test fails, we have a strage situation -- we have an OU in
    # the database, *BUT* there is no information about its lifetime in the
    # current LT dump. It probably means that something is very wrong
    # (e.g. cerebrum has not been updated in a while, whereas the OU dumps
    # have.
    if sko in lifetimes:
        output_element(writer, lifetimes[sko][0], "datoAktivFra")
        output_element(writer, lifetimes[sko][1], "datoAktivTil")
        output_element(writer, lifetimes[sko][2], "navnBokmal")
        output_element(writer, lifetimes[sko][3], "navnEngelsk")
        output_element(writer, lifetimes[sko][4], "NSDKode")
    # fi

    output_element(writer, db_ou.acronym or "", "akronym")

    output_OU_address(writer, db_ou, constants)

    # Contact information
    for item, attr in ((constants.contact_phone, "telefonnr"),
                       (constants.contact_fax, "telefaxnr"),
                       (constants.contact_email, "epost"),
                       (constants.contact_url, "URLBokmal")):
        output_contact_element(writer, db_ou, item, attr, constants)
    # od

    writer.endElement("enhet")
# end output_OU
    


#
# FIXME: This is a temporary hack, until the information is available through
# Cerebrum. 

import xml.sax

class OUParser(xml.sax.ContentHandler):

    def __init__(self, filename):
        self.mapping = dict()
        xml.sax.parse(filename, self)
    # end __init__

    def startElement(self, element, attrs):
        if element != "sted":
            return
        # fi

        decoded_attrs = dict()
        for (key, value) in attrs.items():
            decoded_attrs[key.encode("latin1")] = value.encode("latin1")
        # od

        key = self.make_sko(decoded_attrs)
        if key not in self.mapping:
            self.mapping[key] = self.extract_attributes(decoded_attrs)
        # fi
    # end endElement

    def make_sko(self, attrs):
        return tuple(map(lambda x: int(x),
                         (attrs["fakultetnr"],
                          attrs["instituttnr"],
                          attrs["gruppenr"])))
    # end make_sko

    def extract_attributes(self, attrs):
        def reformat_date(date):
            if not date:
                return ""
            # fi

            return date[:4] + "-" + date[4:6] + "-" + date[6:]
        # end
        
        name_bokmal = ""
        for i in ("stedlangnavn_bokmal", "stedkortnavn_bokmal",
                  "stednavn"):
            if attrs.get(i):
                name_bokmal = attrs[i]
            # fi
        # od

        name_english = ""
        for i in ("stedlangnavn_engelsk", "stedkortnavn_engelsk"):
            if attrs.get(i):
                name_english = attrs[i]
            # fi
        # od

        return (reformat_date(attrs.get("dato_opprettet")),
                reformat_date(attrs.get("dato_nedlagt")),
                name_bokmal, name_english, attrs.get("nsd_kode"))
    # end extract_attributes
# end OUParser


def output_OUs(writer, db, ou_file):
    """
    Output information about all interesting OUs.

    An OU is interesting to FRIDA, if:

    - 'katalog_merke' = 'T' (the OU is supposed to be published)
    - NVL(LT.DATO_NEDLAGT, SYSDATE) > SYSDATE - 365 (it has been less than a
      year since the OU has been terminated).
    """

    db_ou = Factory.get("OU")(db)
    parent_ou = Factory.get("OU")(db)
    constants = Factory.get("Constants")(db)

    # FIXME: This is a temporary hack until we have the proper information
    # in Cerebrum. We need OU lifetimes ([from, to]) in the output file, but
    # this information is NOT available through Cerebrum (yet); for now
    # we'll just extract it from the XML file:

    parser = OUParser(ou_file)
    ou_lifetimes = parser.mapping

    writer.startElement("organisasjon")

    for id in db_ou.list_all():
        output_OU(writer, id["ou_id"], db_ou, parent_ou, ou_lifetimes,
                  constants)
    # od

    writer.endElement("organisasjon")
# end output_OUs



def construct_person_attributes(writer, db_person, constants):
    """
    Construct a dictionary containing all attributes for the FRIDA <person>
    element represented by DB_PERSON.

    This function assumes that DB_PERSON is already associated to the
    appropriate database row(s) (via a suitable find*-call).

    This function returns a dictionary with all attributes to be output in
    the xml file.
    """

    attributes = {}

    # This *cannot* fail or return more than one entry
    row = db_person.get_external_id(constants.system_lt,
                                    constants.externalid_fodselsnr)[0]
    attributes["fnr"] = str(row.external_id)

    result = db_person.get_reservert()
    if result:
        # And now the reservations -- there is at most one result
        attributes["reservert"] = {"T" : "J",
                                   "F" : "N" }[result[0]["reservert"]]
    else:
        logger.error("Aiee! Missing reservation information for person_id %s",
                     db_person.entity_id)
    # fi

    return attributes
# end construct_person_attributes



def process_person_frida_information(db_person, db_ou, constants):
    """
    This function locate all tils/gjest records for DB_PERSON and possibly
    re-writes them in a suitable fashion.

    'Suitable fashion' means that each record output has information on an
    OU that is 'publishable' (i.e. has katalog_merke = 'T'). A person is
    output only if (s)he has at least one tils or gjest record with a
    publisheable OU.

    If there is an OU that is not 'publishable', its closest publishable
    parent is used instead.

    This function returns a tuple with two sequences -- one containing all
    updated employment (tils) records, the other containing all updated
    guest (gjest) records.
    """

    # We are interested only in "active" records 
    now = time.strftime("%Y%m%d")
    employments = map(lambda db_row: db_row._dict(),
                      db_person.get_tilsetting(now))
    guests = map(lambda db_row: db_row._dict(),
                 db_person.get_gjest(now))

    logger.debug("Fetched %d employments and %d guests from db",
                 len(employments), len(guests))

    # Force ou_ids to refer to publishable OUs
    employments = filter(lambda dictionary:
                         _update_person_ou_information(dictionary,
                                                       db_ou,
                                                       constants),
                         employments)

    # Force ou_ids to refer to publishable OUs
    guests = filter(lambda dictionary:
                    _update_person_ou_information(dictionary,
                                                  db_ou,
                                                  constants),
                    guests)

    for sequence in (employments, guests):
        for item in sequence:
            item["dato_fra"] = item["dato_fra"].strftime("%Y-%m-%d")
            item["dato_til"] = item["dato_til"].strftime("%Y-%m-%d")
        # od
    # od

    return (employments, guests)
# end process_person_frida_information



def _update_person_ou_information(dictionary, db_ou, constants):
    """
    This function forces the OU_ID in DICTIONARY to be the ou_id for a
    publishable OU, if at all possible.

    It returns True if such an OU can be found, and False otherwise.

    Consult find_suitable_OU.__doc__ for more information.

    NB! DICTIONARY is modified.
    """

    ou_id = find_suitable_OU(db_ou, dictionary["ou_id"], constants)
    if ou_id is None:
        return False
    # fi

    db_ou.clear()
    db_ou.find(ou_id)

    # Otherwise, register the publishable parent under the key ou_id
    dictionary["ou_id"] = ou_id
    dictionary["institusjon"] = db_ou.institusjon
    dictionary["fakultet"] = db_ou.fakultet
    dictionary["institutt"] = db_ou.institutt
    dictionary["avdeling"] = db_ou.avdeling
    return True
# end _process_employment



def output_employment_information(writer, employment):
    """
    Output all employment information contained in sequence EMPLOYMENT. Each
    entry is a dictionary, representing employment information from mod_lt.

    Each employment record is written out thus:

    <ansettelse>
      <institusjonsnr>...</...>
      <avdnr>...</...>
      <undavdnr>...</...>
      <gruppenr>...</...>
      <stillingskode>...</...>
      <datoFra>...</...>
      <datoTil>...</...>
      <stillingsbetegnelse>...</...>
      <stillingsandel>...</...>
    </ansettelse>        
    """

    if not employment:
        return
    # fi

    writer.startElement("ansettelser")

    # There can be several <ansettelse> elements for each person
    # Each 'element' below is a dictionary of attributes for that particular
    # <ansettelse>
    for element in employment:

        writer.startElement("ansettelse")

        for item, attr in (("institusjon", "institusjonsnr"),
                           ("fakultet", "avdnr"),
                           ("institutt", "undavdnr"),
                           ("avdeling", "gruppenr"),
                           ("code_str", "stillingskode"),
                           ("dato_fra", "datoFra"),
                           ("dato_til", "datoTil"),
                           ("tittel", "stillingsbetegnelse"),
                           ("andel", "stillingsandel")):
            output_element(writer, element[item], attr)
        # od

        writer.endElement("ansettelse")
    # od

    writer.endElement("ansettelser")
# end output_employment_information



def output_guest_information(writer, guest, constants):
    """
    Output all guest information contained in sequence GUEST. Each entry in
    GUEST is a dictionary representing guest information from mod_lt.

    Each guest record is written out thus:

    <gjest>
      <institusjonsnr>...</...>
      <avdnr>...</...>
      <undavdnr>...</...>
      <gruppenr>...</...>
      <gjestebetegnelse>...</...> <!-- LT: gjestetypekode -->
    </gjest>
    """

    if not guest:
        return
    # fi

    writer.startElement("gjester")

    for element in guest:

        writer.startElement("gjest")

        for item, attr in (("institusjon", "institusjonsnr"),
                           ("fakultet", "avdnr"),
                           ("institutt", "undavdnr"),
                           ("avdeling", "gruppenr"),
                           ("dato_fra", "datoFra"),
                           ("dato_til", "datoTil"),
                           ("code_str", "gjestebetegnelse")):
            output_element(writer, element[item], attr)
        # od

        writer.endElement("gjest")
    # od

    writer.endElement("gjester")
# end output_guest_information



def output_person(writer, person_id, db_person, db_account,
                  constants, db_ou):
    '''
    Output all information pertinent to a particular person (PERSON_ID)

    Each <person> is described thus:

    <person fnr="..." reservert="X">
      <etternavn>...</etternavn>
      <fornavn>...</fornavn>
      <brukernavn>...</brukernavn>  <!-- primary user account -->
      <telefonnr>...</telefonnr>
      <telefaxnr>...</telefaxnr>
      <epost>...</epost>            <!-- primary user account? -->
      <URL>...</URL>                <!-- ?? -->
      <personligTittel>...</...>    <!-- ?? -->
      <ansettelser>
        ...
      </ansettelser>
      <gjester>
        ...
      </gjester>
    <person>
    '''

    # load all interesting information about this person
    try:
        db_person.clear()
        db_person.find(person_id)
    except Cerebrum.Errors.NotFoundError:
        logger.error("Aiee! person_id %s spontaneously disappeared", person_id)
        return
    # yrt

    employment, guest = process_person_frida_information(db_person,
                                                         db_ou,
                                                         constants)
    logger.debug("There are %d employments and %d guest rows for %s",
                 len(employment), len(guest), db_person.entity_id)
    
    if (not employment and not guest):
        logger.info("person_id %s has no suitable tils/gjest records",
                    person_id)
        return
    # fi

    attributes = construct_person_attributes(writer, db_person, constants)

    writer.startElement("person", attributes)

    #
    # Process all names
    for item, attr in ((constants.name_last, "etternavn"),
                       (constants.name_first, "fornavn"),
                       (constants.name_personal_title, "personligTittel")):
        try:
            value = db_person.get_name(constants.system_lt, item)
        except Cerebrum.Errors.NotFoundError:
            value = ""
        # yrt

        output_element(writer, value, attr)
    # od

    # uname && email for the *primary* account.
    primary_account = db_person.get_primary_account()
    if primary_account is None:
        logger.info("person_id %s has no accounts", db_person.entity_id)
    else:
        db_account.clear()
        db_account.find(primary_account)

        output_element(writer, db_account.get_account_name(), "brukernavn")

        try:
            primary_email = db_account.get_primary_mailaddress()
            output_element(writer, primary_email, "epost")
        except Cerebrum.Errors.NotFoundError:
            logger.info("person_id %s has no primary e-mail address",
                        db_person.entity_id)
            pass
        # yrt
    # fi

    for item, attr in ((constants.contact_phone, "telefonnr"),
                       (constants.contact_fax, "telefaxnr"),
                       (constants.contact_url, "URL")):
        output_contact_element(writer, db_person, item, attr, constants)
    # od
    
    output_employment_information(writer, employment)

    output_guest_information(writer, guest, constants)
    
    writer.endElement("person")
# end output_person



def output_people(writer, db):
    """
    Output information about all interesting people.

    A person is interesting for FRIDA, if it has active employments
    (tilsetting) or active guest records (gjest). A record is considered
    active, if it has a start date in the past (compared to the moment when
    the script is run) and the end date is either unknown or in the future.
    """

    db_person = Factory.get("Person")(db)
    constants = Factory.get("Constants")(db)
    db_account = Factory.get("Account")(db)
    ou = Factory.get("OU")(db)    

    writer.startElement("personer")
    for id in db_person.list_frida_persons():
        output_person(writer, id["person_id"],
                      db_person,
                      db_account,
                      constants,
                      ou)
    # od
    writer.endElement("personer")
# end output_people    



def output_xml(output_file, data_source, target, ou_file):
    """
    Initialize all connections and start generating the xml output.

    OUTPUT_FILE names the xml output.

    DATA_SOURCE and TARGET are elements in the xml output.
    """

    # Nuke the old copy
    output_stream = AtomicFileWriter(output_file, "w")
    writer = xmlprinter.xmlprinter(output_stream,
                                   indent_level = 2,
                                   # Output is for humans too
                                   data_mode = True,
                                   input_encoding = 'latin1')
    db = Factory.get('Database')()

    # 
    # Here goes the hardcoded stuff
    #
    writer.startDocument(encoding = "iso8859-1")

    writer.startElement("fridaImport")

    writer.startElement("beskrivelse")
    output_element(writer, data_source, "kilde")
    # ISO8601 style -- the *only* right way :)
    output_element(writer, time.strftime("%Y-%m-%d %H:%M:%S"), "dato")
    output_element(writer, target, "mottager")
    writer.endElement("beskrivelse")

    writer.startElement("institusjon")
    output_element(writer, 185, "institusjonsnr")
    output_element(writer, "Universitetet i Oslo", "navnBokmal")
    output_element(writer, "University of Oslo", "navnEngelsk")
    output_element(writer, "UiO", "akronym")
    output_element(writer, "1110", "NSDKode")
    writer.endElement("institusjon")

    # Dump all OUs
    output_OUs(writer, db, ou_file)

    # Dump all people
    output_people(writer, db)

    writer.endElement("fridaImport")

    writer.endDocument()

    output_stream.close()
# end output_xml



def usage():
    '''
    Display option summary
    '''

    options = '''
options: 
-o, --output-file: output file (default ./frida.xml)
-v, --verbose:     output more debugging information
-d, --data-source: source that generates frida.xml (default "UiO-Cerebrum")
-t, --target:      what (whom :)) the dump is meant for (default "UiO-FRIDA")
-s, --sted:        sted.xml generated by import_from_LT.py (this is hack!)
-h, --help:        display usage
    '''

    # FIMXE: hmeland, is the log facility the right thing here?
    logger.info(options)
# end usage



def main():
    """
    Start method for this script. 
    """
    global logger

    logger = Factory.get_logger()
    logger.info("Generating FRIDA export")

    try:
        options, rest = getopt.getopt(sys.argv[1:],
                                      "o:vd:t:hs:", ["output-file=",
                                                    "verbose",
                                                    "data-source=",
                                                    "target",
                                                    "help",
                                                    "sted=",])
    except getopt.GetoptError:
        usage()
        sys.exit(1)
    # yrt

    # Default values
    output_file = "frida.xml"
    data_source = "UIO"
    target = "UiO-FRIDA"
    ou_file = None

    # Why does this look _so_ ugly?
    for option, value in options:
        if option in ("-o", "--output-file"):
            output_file = value
        elif option in ("-d", "--data-source"):
            data_source = value
        elif option in ("-t", "--target"):
            target = value
        elif option in ("-h", "--help"):
            usage()
            sys.exit(2)
        elif option in ("-s", "--sted"):
            ou_file = value
        # fi
    # od

    output_xml(output_file = output_file,
               data_source = data_source,
               target = target,
               ou_file = ou_file)
# end main





if __name__ == "__main__":
    main()
# fi

# arch-tag: 82474d1a-532f-4619-97c4-bf412c7564db
