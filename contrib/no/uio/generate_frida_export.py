#! /usr/bin/env python2.2
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

It generates an xml dump, suitable for importing into the FRIDA project (for
more information on FRIDA, start at <URL:
http://www.usit.uio.no/prosjekter/frida/pg/>). The output format is
specified by FRIDA.dtd, available in the 'uiocerebrum' project, at
cvs.uio.no.

The general workflow is rather simple:

<cerebrum db> ---> generate_frida_export.py ===> frida.xml

The output generation consists of the following steps:

1. grock options
2. generate hardcoded headers
3. output information on all interesting organizational units (output_OUs)
4. output information on all interesting people               (output_people)

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

# FIXME: As of python 2.3, this module is part of the standard distribution
if sys.version >= (2, 3):
    import logging
else:
    from Cerebrum.extlib import logging
# fi





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

    writer.startElement(element, attributes)
    writer.data(str(value))
    writer.endElement(element)
# end output_element



def output_organization(writer, db):
    """
    Output information about <Organization>

    FIMXE: NB! It might be wise to move all these hardwired values into
    cereconf. They are probably used by several parts of the cerebrum
    anyway.
    """

    writer.startElement("Organization")

    output_element(writer, "0185", "norInstitutionNumber")

    for attributes in [("no", "Universitetet i Oslo"),
                       ("en", "University of Oslo"),
                       ("la", "Universitas Osloensis")]:
        output_element(writer, attributes[1],
                       "norInstitutionName", {"language" : attributes[0]})
    # od

    for attributes in [("no", "UiO"), ("en", "UoO")]:
        output_element(writer, attributes[1],
                       "norInstitutionAcronym", {"language" : attributes[0]})
    # od

    writer.endElement("Organization")
# end output_organization



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

    # Unfortunately, there are OUs without any addresses registered
    if not address:
        logger.error("No address information for %s is registered",
                     db_ou.entity_id)
        output = "No address information available"
    else:
        # We cannot have more than one answer for any given
        # (ou_id, source_system, address_type) triple
        address = address[0]

        city = address["city"]
        po_box = address["p_o_box"]
        postal_number = address["postal_number"]
        country = address["country"]
        
        if (po_box and int(postal_number or 0) / 100 == 3):
            address_text = "Pb. %s - Blindern" % po_box
        else:
            address_text = (address["address_text"] or "").strip()
        # fi
        
        post_nr_city = None
        if city or (postal_number and country):
            post_nr_city = string.join(filter(None,
                                              [postal_number,
                                               (city or "").strip()]))
        # fi

        output = string.join(filter(None,
                                    (address_text,
                                     post_nr_city,
                                     country))).replace("\n", ",")
        if not output:
            logger.error("No address information for %s could be generated",
                         db_ou.entity_id)
        # fi
    # fi

    output_element(writer, output, "Addressline")
# end output_OU_address



def output_OU_parent(writer, child_ou, parent_ou, constants):
    """
    Output all information about CHILD_OU's parent OU
    """

    parent_id = child_ou.get_parent(constants.perspective_lt)

    # This is a hack for the root of the organisational structure.
    # I.e. the root of the OU structure is its own parent
    if parent_id is None:
        parent_id = child_ou.entity_id
    # fi

    # find parent OU
    parent_ou.clear()
    parent_ou.find(parent_id)

    for attr_name, element_name in [("fakultet", "norParentOrgUnitFaculty"),
                                    ("institutt", "norParentOrgUnitDepartment"),
                                    ("avdeling", "norParentOrgUnitGroup")]:
        output_element(writer,
                       getattr(parent_ou, attr_name),
                       element_name)
    # od
# end output_OU_parent



_ou_parent = dict()
def find_suitable_OU(ou, id, constants):
    """
    This is a caching wrapper around __find_suitable_OU
    """
    child = int(id)

    if _ou_parent.has_key(child):
        return _ou_parent[child]
    # fi

    parent = __find_suitable_OU(ou, child, constants)
    if parent is not None:
        parent = int(parent)
    # fi
    
    _ou_parent[child] = parent
    return parent
# end find_suitable_OU



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
def output_OU(writer, start_id, db_ou, parent_ou, constants):
    """
    Output all information pertinent to a specific OU

    Each OU is described thus:

    <!ELEMENT NorOrgUnit (norOrgUnitName+, norOrgUnitFaculty,
                          norOrgUnitDepartment, norOrgUnitGroup,
                          norParentOrgUnitFaculty,
                          norParentOrgUnitDepartment,
                          norParentOrgUnitGroup, norOrgUnitAcronym*, 
                          Addressline, Telephon*, Fax*, URL*)>
    """

    id = find_suitable_OU(db_ou, start_id, constants)
    if id is None:
        logger.warn("No suitable ids for (start) id = %s", start_id)
        return
    # fi
    # Skip duplicates
    if int(id) in _ou_cache:
        return
    # fi
    _ou_cache.add(int(id))
    if int(id) != int(start_id):
        logger.info("ID %s converted to %s", id, start_id)
    # fi

    db_ou.clear()
    db_ou.find(id)
    
    ou_names = db_ou.get_names()
    # Ufh! I want CL's count-if
    # Check that there is at least one non-empty name
    has_any = (lambda sequence, field:
                      [x for x in sequence
                         if x[field] is not None])
    if not has_any(ou_names, "name"):
        logger.error("Missing name information for ou_id = %s", id)
        return
    # fi

    writer.startElement("norOrgUnit")
    # norOrgUnitNames+
    for name, language in ou_names:
        # Some tuples might have empty names (general case)
        if not name: continue
        attributes = {}
        if language: attributes = {"language": language}

        output_element(writer, name, "norOrgUnitName", attributes)
    # od

    # norOrgUnitFaculty
    output_element(writer, db_ou.fakultet, "norOrgUnitFaculty")

    # norOrgUnitDepartment
    output_element(writer, db_ou.institutt, "norOrgUnitDepartment")

    # norOrgUnitGroup
    output_element(writer, db_ou.avdeling, "norOrgUnitGroup")

    # Information on this OUs parent
    output_OU_parent(writer, db_ou, parent_ou, constants)
    
    # norOrgUnitAcronym*
    ou_acronyms = db_ou.get_acronyms()
    for acronym, language in ou_acronyms:
        # some tuples might have empty acronyms
        if not acronym: continue
        attributes = {}
        if language: attributes = {"language": language}

        output_element(writer, acronym, "norOrgUnitAcronym", attributes)
    # od

    # Addressline
    output_OU_address(writer, db_ou, constants)

    # Telephone
    for row in db_ou.get_contact_info(source=constants.system_lt,
                                      type=constants.contact_phone):
        output_element(writer, row.contact_value, "Telephone")
    # od

    # Fax
    for row in db_ou.get_contact_info(source=constants.system_lt,
                                      type=constants.contact_fax):
        output_element(writer, row.contact_value, "Fax")
    # od

    # URL*
    for row in db_ou.get_contact_info(source=constants.system_lt,
                                      type=constants.contact_url):
        output_element(writer, row.contact_value, "URL")
    # od

    writer.endElement("norOrgUnit")
# end output_OU
    


def output_OUs(writer, db):
    """
    Output information about all interesting OUs.

    An OU is interesting to FRIDA, if it is active in LT *now*
    (i.e. most recent LT dump) and is explicitely set up for
    publishing in a catalogue service (katalog_merke = 'T').
    """

    db_ou = Factory.get("OU")(db)
    parent_ou = Factory.get("OU")(db)
    constants = Factory.get("Constants")(db)

    writer.startElement("OrganizationUnits")
    for id in db_ou.list_all():
        output_OU(writer, id["ou_id"], db_ou,
                  parent_ou, constants)
    # od
    writer.endElement("OrganizationUnits")
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
    attributes["NO_SSN"] = str(row.external_id)

    # The rule for selecting primary affiliation is pretty simple:
    # 1. If there is an ANSATT/vitenskapelig affiliation then
    #    Affiliation = Faculty
    # 2. If there is an ANSATT/tekadm affiliation then Affiliation = Staff
    # 3. Otherwise Affiliation = Member
    # 
    # We can do this in one database lookup, at the expense of much uglier
    # code
    if db_person.list_affiliations(db_person.entity_id,
                                   constants.system_lt,
                                   constants.affiliation_ansatt,
                                   constants.affiliation_status_ansatt_vit):
        attributes["Affiliation"] = "Faculty"
    elif db_person.list_affiliations(db_person.entity_id,
                                     constants.system_lt,
                                     constants.affiliation_ansatt,
                                     constants.affiliation_status_ansatt_tekadm):
        attributes["Affiliation"] = "Staff"
    else:
        attributes["Affiliation"] = "Member"
    # fi


    result = db_person.get_reservert()
    if result:
        # And now the reservations -- there is at most one result
        attributes["Reservation"] = {"T" : "yes",
                                     "F" : "no" }[result[0]["reservert"]]
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

    return (employments, guests)
# end process_person_frida_information



def _update_person_ou_information(dictionary, db_ou, constants):
    """
    This function forces the OU_ID in DICTIONARY to be the ou_id for a
    publishable OU, if at all possible.

    It returns True if such an OU can be found, and False otherwise.

    Consult find_suitable_OU.__doc__ for more information.
    """

    ou_id = find_suitable_OU(db_ou, dictionary["ou_id"], constants)
    if ou_id is None:
        return False
    # fi

    db_ou.clear()
    db_ou.find(ou_id)

    # Otherwise, register the publishable parent under the key ou_id
    dictionary["ou_id"] = ou_id
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

    <!ELEMENT Tilsetting (Stillingskode, StillingsTitle, Stillingsandel,
                          StillingsFak, StillingsInstitutt, StillingsGruppe,
                          fraDato, tilDato)>
    <!ATTLIST Tilsetting Affiliation ( Staff | Faculty ) #REQUIRED>

    """

    # There can be several <tils> elements for each person
    # Each 'element' below is a dictionary of attributes for that particular
    # <tils>
    for element in employment:
        if element["hovedkategori"] is None:
            logger.error("Aiee! %s has no suitable employment affiliation (%s)",
                         employment["person_id"])
            continue
        else:
            affiliation = { "VIT" : "Faculty",
                            "ØVR" : "Staff" }[element["hovedkategori"]]
            attributes = {"Affiliation" : affiliation}
        # fi

        writer.startElement("Tilsetting", attributes)
        for output, index in [("Stillingskode", "code_str"),
                              ("StillingsTitle", "tittel"),
                              ("Stillingsandel", "andel"),
                              ("StillingsFak", "fakultet"),
                              ("StillingsInstitutt", "institutt"),
                              ("StillingsGruppe", "avdeling"),
                              ]:
            if element.has_key(index):
                output_element(writer, element[index], output)
            # fi
        # od
        
        for output, index in [("fraDato", "dato_fra"),
                              ("tilDato", "dato_til")]:
            if element.has_key(index):
                output_element(writer, element[index].strftime("%Y%m%d"),
                               output)
            # fi
        # od
        
        writer.endElement("Tilsetting")
    # od
# end output_employment_information



def output_guest_information(writer, guest, constants):
    """
    Output all guest information contained in sequence GUEST. Each entry in
    GUEST is a dictionary representing guest information from mod_lt.

    Each guest record is written out thus:
    
    <!ELEMENT Guest (guestFak, guestInstitutt, guestGroup, fraDato, tilDato)>
    <!ATTLIST Guest  Affiliation
                     ( Emeritus | Stipendiat | unknown ) #REQUIRED>
    """

    for element in guest:
        attributes = {"Affiliation": "unknown"}

        if int(element["gjestetypekode"]) == int(constants.lt_gjestetypekode_emeritus):
            attributes = {"Affiliation": "Emeritus"}
        elif int(element["gjestetypekode"]) == int(constants.lt_gjestetypekode_ef_stip):
            attributes = {"Affiliation": "Stipendiat"}
        # fi

        writer.startElement("Gjest", attributes)
        for output, index in [("guestFak", "fakultet"),
                              ("guestInstitutt", "institutt"),
                              ("guestGroup", "avdeling"),
                              ]:
            if element.has_key(index):
                output_element(writer, element[index], output)
            # fi
        # od

        for output, index in [("fraDato", "dato_fra"),
                              ("tilDato", "dato_til")]:
            if element.has_key(index):
                output_element(writer, element[index].strftime("%Y%m%d"),
                               output)
            # fi
        # od
        writer.endElement("Gjest")
    # od
# end output_guest_information



def output_person(writer, person_id, db_person, db_account,
                  constants, db_ou):
    """
    Output all information pertinent to a particular person (PERSON_ID)

    Each <Person> is described thus:

    <!ELEMENT Person (sn, givenName?, uname?,
                      emailAddress?, Telephone?,
                      Tilsetting*, Guest*)>

    <!ATTLIST Person NO_SSN CDATA #REQUIRED
              Affiliation ( Staff | Faculty | Member ) #REQUIRED
              Reservation ( yes | no ) #REQUIRED>

    """

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

    writer.startElement("Person", attributes)

    # surname
    output_element(writer,
                   db_person.get_name(constants.system_lt,
                                      constants.name_last),
                   "sn")

    # first name
    first_name = db_person.get_name(constants.system_lt,
                                    constants.name_first)
    if first_name:
        output_element(writer, first_name, "givenName")
    # fi

    # uname && email for the *primary* account.
    primary_account = db_person.get_primary_account()
    if primary_account is None:
        logger.info("person_id %s has no accounts", db_person.entity_id)
    else:
        db_account.clear()
        db_account.find(primary_account)

        output_element(writer, db_account.get_account_name(), "uname")

        try:
            primary_email = db_account.get_primary_mailaddress()
            output_element(writer, primary_email, "emailAddress")
        except Cerebrum.Errors.NotFoundError:
            logger.info("person_id %s has no primary e-mail address",
                        db_person.entity_id)
            pass
        # yrt
    # fi

    # <Telephone>?
    # We need the one with lowest contact_pref, if there are many
    contact = db_person.get_contact_info(source=constants.system_lt,
                                         type=constants.contact_phone)
    contact.sort(lambda x, y: cmp(x.contact_pref, y.contact_pref))
    if contact:
        output_element(writer, contact[0].contact_value, "Telephone")
    # od

    output_employment_information(writer, employment)

    output_guest_information(writer, guest, constants)
    
    writer.endElement("Person")
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

    writer.startElement("NorPersons")
    for id in db_person.list_frida_persons():
        output_person(writer, id["person_id"],
                      db_person,
                      db_account,
                      constants,
                      ou)
    # od
    writer.endElement("NorPersons")
# end output_people    



def output_xml(output_file, data_source, target):
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

    # Here goes the hardcoded stuff
    writer.startDocument(encoding = "iso8859-1")

    writer.startElement("XML-export")

    writer.startElement("Properties")

    output_element(writer, data_source, "datasource")

    output_element(writer, target, "target")

    # ISO8601 style -- the *only* right way :)
    output_element(writer, time.strftime("%Y-%m-%dT%H:%M:%S"), "datetime")

    writer.endElement("Properties")

    writer.startElement("NorOrgUnits")
    # Organization "header"
    # FIXME: It's all hardwired
    output_organization(writer, db)
    # Dump all OUs
    output_OUs(writer, db)
    writer.endElement("NorOrgUnits")

    # Dump all people
    output_people(writer, db)
    
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
-d, --data-source: source that generates frida.xml (default"Cerebrum@uio.no")
-t, --target:      what (whom :)) the dump is meant for (default "FRIDA")
-h, --help:        display usage
    '''

    # FIMXE: hmeland, is the log facility the right thing here?
    logger.info(options)
# end usage



def main(argv):
    """
    Start method for this script. 
    """
    global logger

    logging.fileConfig(cereconf.LOGGING_CONFIGFILE)
    logger = logging.getLogger("console")
    logger.setLevel(logging.INFO)
    logger.info("Generating FRIDA export")
    
    try:
        options, rest = getopt.getopt(argv,
                                      "o:vd:t:h", ["output-file=",
                                                   "verbose",
                                                   "data-source=",
                                                   "target",
                                                   "help",])
    except getopt.GetoptError:
        usage()
        sys.exit(1)
    # yrt

    # Default values
    output_file = "frida.xml"
    # FIXME: Maybe snatch these from cereconf?
    data_source = "Cerebrum@uio.no"
    target = "FRIDA"
    
    # Why does this look _so_ ugly?
    for option, value in options:
        if option in ("-o", "--output-file"):
            output_file = value
        elif option in ("-v", "--verbose"):
            logger.setLevel(logging.DEBUG)
        elif option in ("-d", "--data-source"):
            data_source = value
        elif option in ("-t", "--target"):
            target = value
        elif option in ("-h", "--help"):
            usage()
            sys.exit(2)
        # fi
    # od

    output_xml(output_file = output_file,
               data_source = data_source,
               target = target)
# end main





if __name__ == "__main__":
    main(sys.argv[1:])
# fi
