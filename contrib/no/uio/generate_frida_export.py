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

It generates an xml dump, suitable for importing into the FRIDA framework
(for more information on FRIDA, start at <URL:
http://www.usit.uio.no/prosjekter/frida/pg/>). The output format is
specified by FRIDA.dtd, available in the "uiocerebrum" project, at
cvs.uio.no.

The general workflow is rather simple:

person.xml    --+
                |
                +--> generate_frida_export.py ===> frida.xml
                |
<cerebrum db> --+

person.xml is needed for information about hiring / peoples' statuses. 

<cerebrum db> is needed for everything else.

person.xml format is specified by lt-person.dtd available in the
"uiocerebrum" project. Only some of the elements are of interest for FRIDA
export. We use Norwegian fødselsnummer to tie <person>-elements to database
rows.

The output generation consists of the following steps:

1. grock options
2. generate hardcoded headers
3. output information on all interesting organizational units (output_OUs)
4. output information on all interesting people               (output_people)

"""

import xml.sax
import sys
import time
import getopt
import string

import cerebrum_path
import cereconf

import Cerebrum
from Cerebrum import Database
from Cerebrum.Utils import Factory
from Cerebrum.extlib import xmlprinter

from Cerebrum.modules.no import Stedkode
from Cerebrum.modules.no import fodselsnr

# FIXME: As of python 2.3, this module is part of the standard distribution
if sys.version >= (2, 3):
    import logging
else:
    from Cerebrum.extlib import logging
# fi





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

    <!ELEMENT person (arbtlf? | komm* | rolle* | tils* | res* | bilag* | gjest*)>
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
	      hovedkat (VIT | ØVR) #REQUIRED
	      tittel CDATA #REQUIRED>
    <!ELEMENT gjest EMPTY>
    <!ATTLIST gjest
              fakultetnr CDATA #REQUIRED
              instituttnr CDATA #REQUIRED
              gruppenr CDATA #REQUIRED
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
        # od

        # We need an ID to tie a person to the database identification Let's
        # use fnr, although it's a bad identification in general, but we do
        # NOT have any other identifier in person.xml
        if not (attributes.has_key("fodtdag") and
                attributes.has_key("fodtmnd") and
                attributes.has_key("fodtar") and
                attributes.has_key("personnr")):
            raise (ValueError,
                  "Missing critical data for person: " + str(attributes))
        # fi

        # NB! We 0-fill the 'personnr', as data from LT looks a bit funny
        # every now and then
        self.fnr = "%02d%02d%02d%05d" % (int(attributes["fodtdag"]),
                                         int(attributes["fodtmnd"]),
                                         int(attributes["fodtar"]),
                                         int(attributes["personnr"]))


        # NB! This code might raise fodselsnr.InvalidFnrError
        #     We need sanity checking, because LT dumps are suffer from bitrot
        #     (e.g. Swedish SSNs end up as Norwegian. Gah!)
        fodselsnr.personnr_ok(self.fnr)
        
        self.fnr = self.fnr.encode("latin1")
        # we do not really need a name (it is in cerebrum), but it might
        # come in handy during debugging stages
        self.name = attributes["navn"].encode("latin1")
        logger.debug("extracted new person element from LT (%s, %s)",
                     self.fnr, self.name)
    # end



    def register_element(self, name, attributes):
        """
        Each <person> element has a number of interesting child
        elements. This method is used for 'attaching' them to person objects.
        """
        if name not in self.INTERESTING_ELEMENTS:
            return
        # fi

        encoded_attributes = {}
        for key, value in attributes.items():
            # We have to do this charset conversion. No worries, parsing xml
            # takes too little time to be of consideration
            key = key.encode("latin1")
            value = value.encode("latin1")
            encoded_attributes[key] = value
        # od

        self.elements[name].append(encoded_attributes)
    # end registerElement



    def get_element(self, name):
        """
        Return a sequence of attributes of all NAME elements.

        Each item in this sequence is a dictionary of the element's
        attributes (key = attribute name, value = attribute value).
        """
        return self.elements.get(name, [])
    # end get_element
        


    def is_frida(self):
        """
        A person is interesting for FRIDA if he has an active <tils> or
        <gjest> element.

        An element is active if it has dato_fra in the past and dato_til in
        the future (or right *now*).
        """

        return (self.has_active("gjest") or
                self.has_active("tils"))
    # end is_frida



    def is_employee(self):
        """
        A person is an employee if he has an active <tils> element
        """

        return self.has_active("tils")
    # end is_employee



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
            # fi
        # od

        return False
    # end has_active



    def has_reservation(self, **attributes):
        """
        Check whether <person> represented by SELF contains at least one
        <res> element with specified ATTRIBUTES.
        """

        items = attributes.items()

        for res in self.elements.get("res", []):
            hit = True
            for attribute, value in items:
                if not res.has_key(attribute) or res[attribute] != value:
                    hit = False
                    break 
                # fi
            # od

            if hit: return True
        # od

        return False
    # end has_resevation



    def __str__(self):
        """
        This function is mainly for debug purposes
        """
        output = ("<%s %s %s [" %
                  (type(self).__name__,
                   getattr(self, "fnr", "N/A"),
                   getattr(self, "name", "N/A")))

        if self.is_frida(): output += " F"

        if self.is_employee(): output += " E"

        output += " ]>"
        return output
    # end debug_output
    
# end LTPersonRepresentation





class LTPersonParser(xml.sax.ContentHandler, object):
    '''
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
      <gjest fakultetnr="15" instituttnr="4" gruppenr="30"
             gjestetypekode="IKKE ANGIT"
             dato_fra="20030901" dato_til="20041231"/>
      <res katalogkode="ELKAT" felttypekode="PRIVADR"/>
    </person>
    '''

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
    # end ctor



    def parse(self):
        if not hasattr(self, "filename"):
            fatal("Missing filename. Operation aborted")
        # fi

        xml.sax.parse(self.filename, self)
    # end parse



    def startElement(self, name, attributes):
        """
        NB! we only handle elements interesting for the FRIDA output

        Also, if a LTPersonRepresentation object cannot be constructed for
        some reason, that particular <person>-element from LT dump is
        discarded.
        """
        if name == self.PERSON_ELEMENT:
            try:
                self.current_person = None
                self.current_person = LTPersonRepresentation(attributes)
            except ValueError, value:
                logger.error("Failed to construct a person from XML: %s",
                              value)
            except fodselsnr.InvalidFnrError, value:
                logger.error("Failed to construct a person from XML: %s",
                             value)
            # yrt
        elif (name in self.INTERESTING_ELEMENTS and
              self.current_person):
            self.current_person.register_element(name, attributes)
        # fi
    # end startElement



    def endElement(self, name):
        if name == self.PERSON_ELEMENT and self.current_person:
            self.callback(self.current_person)
        # fi
    # end endElement
# end class LTPersonParser





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



def output_OU_parent(writer, child_ou, parent_stedkode, constants):
    """
    Output all information about CHILD_OU's parent OU
    """

    parent_id = child_ou.get_parent(constants.perspective_lt)

    # This is a hack for the root of the organisational structure.
    # I.e. the root of the OU structure is its own parent
    if parent_id is None:
        parent_id = child_ou.entity_id
    # fi

    # find parent OU/stedkode
    parent_stedkode.clear()
    parent_stedkode.find(parent_id)

    for attr_name, element_name in [("fakultet", "norParentOrgUnitFaculty"),
                                    ("institutt", "norParentOrgUnitDepartment"),
                                    ("avdeling", "norParentOrgUnitGroup")]:
        output_element(writer,
                       getattr(parent_stedkode, attr_name),
                       element_name)
    # od
# end output_OU_parent
        


def output_OU(writer, id, db_ou, stedkode, parent_stedkode, constants):
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

    stedkode.clear()
    stedkode.find(id)
    # This entry is not supposed to be published
    if stedkode.katalog_merke != 'T':
        logger.debug("Skipping ou_id == %s", id)
        return
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
    output_element(writer, stedkode.fakultet, "norOrgUnitFaculty")

    # norOrgUnitDepartment
    output_element(writer, stedkode.institutt, "norOrgUnitDepartment")

    # norOrgUnitGroup
    output_element(writer, stedkode.avdeling, "norOrgUnitGroup")

    # Information on this OUs parent
    output_OU_parent(writer, db_ou, parent_stedkode, constants)
    
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
    stedkode = Stedkode.Stedkode(db)
    parent_stedkode = Stedkode.Stedkode(db)
    constants = Factory.get("Constants")(db)

    writer.startElement("OrganizationUnits")
    for id in db_ou.list_all():
        output_OU(writer, id["ou_id"], db_ou,
                  stedkode, parent_stedkode, constants)
    # od
    writer.endElement("OrganizationUnits")
# end output_OUs



def get_reservation(pobj):
    '''
    Returns the reservation status ( YES | NO ) for a person represented by
    POBJ.

    The rules are a bit involved. The decision is based on various <res
    katalogkode="..." felttypekode="..." resnivakode="..."> elements.

    The starting point is that all employees (tilsatte) have no reservations
    and all guests (gjester) do.  Further refinements of this simple rule
    are:

    There is only one katalogkode that is of interest -- ELKAT.

    The only guests not reserved are those having
    <res katalogkode="ELKAT" felttype="gjesteoppl" resnivakode="samtykke">

    For the employees, these are reserved:

    felttype    resniva
    BESØKSADR - ??      => reserved
    BRNAVN -    ??      => reserved
    EMAIL -     ??      => reserved
    JOBBADR -   ??      => reserved
    JOBBFAX -   TOTAL   => reserved
    JOBBTLF -   TOTAL   => reserved
    TOTAL   -   ??      => reserved

    ?? means "do not care"

    The old rules were:
    If P is an employee, then			      
      If P has <res katalogkode = "ELKAT"> too then	      
        Reservation = "yes"				      
      Else						      
        Reservation = "no"				      
    Else 						      
      If P has <res katalogkode="ELKAT" 		      
                    felttypekode="GJESTEOPPL"> then	      
        Reservation = "no"				      
      Else						      
        Reservation = "yes"				      
    Fi                                                  
    '''
    reserved = "yes"
    not_reserved = "no"

    if pobj.is_employee():
        # None means "don't care"
        for felttypekode, resnivakode in [ ("BESØKSADR", None),
                                           ("BRNAVN", None),
                                           ("EMAIL", None),
                                           ("JOBBADR", None),
                                           ("JOBBFAX", "TOTAL"),
                                           ("JOBBTLF", "TOTAL"),
                                           ("TOTAL", None) ]:
            tmp = { "felttypekode" : felttypekode,
                    "katalogkode" : "ELKAT" }
            if resnivakode: tmp[ "resnivakode" ] = resnivakode

            if pobj.has_reservation(**tmp):
                logger.info("%s has reservation; criteria: %s %s",
                            pobj.fnr, str(felttypekode), str(resnivakode))
                return reserved
            # fi
        # od

        # None of the reservation were present. This means that the person
        # is up for grabs
        return not_reserved
    else:
        # guests are different
        if pobj.has_reservation(katalogkode="ELKAT",
                                felttypekode="GJESTEOPPL",
                                resnivakode="SAMTYKKE"):
            return not_reserved
        else:
            return reserved
        # fi
    # fi
# end get_reservation



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

    # And now the reservations
    attributes["Reservation"] = get_reservation(pobj)

    return attributes
# end construct_person_attributes



def output_employment_information(writer, pobj):
    """
    Output all employment information pertinent to a particular person
    (POBJ). I.e. convert from <tils>-elements in LT dump to <Tilsetting>
    elements in FRIDA export. 

    Each employment record is written out thus:

    <!ELEMENT Tilsetting (Stillingskode, StillingsTitle, Stillingsandel,
                          StillingsFak, StillingsInstitutt, StillingsGruppe,
                          fraDato, tilDato)>
    <!ATTLIST Tilsetting Affiliation ( Staff | Faculty ) #REQUIRED>

    These elements/attributes are formed from the corresponding entries
    represented by POBJ.

    """

    # There can be several <tils> elements for each person
    # Each 'element' below is a dictionary of attributes for that particular
    # <tils>
    for element in pobj.get_element("tils"):

        if element["hovedkat"] == "VIT":
            attributes = {"Affiliation": "Faculty"}
        elif element["hovedkat"] == "ØVR":
            attributes = {"Affiliation": "Staff"}
        else:
            logger.error("Aiee! %s has no suitable employment affiliation %s",
                         pobj.fnr, str(element))
            continue
        # fi
        
        writer.startElement("Tilsetting", attributes)
        for output, index in [("Stillingskode", "stillingkodenr_beregnet_sist"),
                              ("StillingsTitle", "tittel"),
                              ("Stillingsandel", "prosent_tilsetting"),
                              ("StillingsFak", "fakultetnr_utgift"),
                              ("StillingsInstitutt", "instituttnr_utgift"),
                              ("StillingsGruppe", "gruppenr_utgift"),
                              ("fraDato", "dato_fra"),
                              ("tilDato", "dato_til"),
                              ]:
            if element.has_key(index):
                output_element(writer, element[index], output)
            # fi
        # od
        writer.endElement("Tilsetting")
    # od
# end output_employment_information



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

        for output, index in [("guestFak", "fakultetnr"),
                              ("guestInstitutt", "instituttnr"),
                              ("guestGroup", "gruppenr"),
                              ("fraDato", "dato_fra"),
                              ("tilDato", "dato_til"),
                              ]:
            if element.has_key(index):
                output_element(writer, element[index], output)
            # fi
        # od

        writer.endElement("Gjest")
    # od
# end output_guest_information



def output_person(writer, pobj, db_person, db_account, constants):
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

    # Ignore 'uninteresting' people
    if not pobj.is_frida(): return

    db_person.clear()
    try:
        # NB! There can be *only one* FNR per person in LT (PK in
        # the person_external_id table)
        db_person.find_by_external_id(constants.externalid_fodselsnr,
                                      pobj.fnr,
                                      constants.system_lt)
    except Cerebrum.Errors.NotFoundError:
        # This should *not* be possible -- everyone in the LT dump should
        # also be registered in the database (after a while, at least)
        logger.error("Aiee! No person with NO_SSN (fnr) = %s found " +
                     "although this NO_SSN exists in the LT dump",
                     pobj.fnr)
        return 
    # yrt
        
    writer.startElement("Person",
                        construct_person_attributes(writer,
                                                    pobj,
                                                    db_person,
                                                    constants))
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
        logger.info("Person %s has no accounts", pobj.fnr)
    else:
        db_account.clear()
        db_account.find(primary_account)

        output_element(writer, db_account.get_account_name(), "uname")

        try:
            primary_email = db_account.get_primary_mailaddress()
            output_element(writer, primary_email, "emailAddress")
        except Cerebrum.Errors.NotFoundError:
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

    output_employment_information(writer, pobj)

    output_guest_information(writer, pobj)
    
    writer.endElement("Person")
# end 



def output_people(writer, db, person_file):
    """
    Output information about all interesting people.

    LTPersonRepresentation.is_frida describes what kind of people are
    'interesting' in FRIDA context.
    """
    db_person = Factory.get("Person")(db)
    constants = Factory.get("Constants")(db)
    db_account = Factory.get("Account")(db)

    #
    # Sanity-checking
    # 
    for c in ["system_lt", "affiliation_ansatt",
              "affiliation_status_ansatt_tekadm",
              "affiliation_status_ansatt_vit", "externalid_fodselsnr",
              "name_last", "name_first", "contact_phone"]:
        logger.debug("%s -> %s (%d)",
                     c, getattr(constants,c), getattr(constants,c))
    # od

    # NB! The callable object (2nd argument) is invoked each time the parser
    # sees a </person> tag.
    # 
    parser = LTPersonParser(person_file,
                            lambda p: output_person(writer = writer,
                                                    pobj = p,
                                                    db_person = db_person,
                                                    db_account = db_account,
                                                    constants = constants))
    parser.parse()
# end output_people    



def output_xml(output_file,
               data_source,
               target,
               person_file):
    """
    Initialize all connections and start generating the xml output.

    OUTPUT_FILE names the xml output.

    DATA_SOURCE and TARGET are elements in the xml output.

    PERSON_FILE is the name of the person LT dump (used as input).
    """

    # Nuke the old copy
    output_stream = open(output_file, "w")
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
    writer.startElement("NorPersons")
    output_people(writer, db, person_file)
    writer.endElement("NorPersons")
    
    writer.endDocument()
    output_stream.close()
# end 



def usage():
    '''
    Display option summary
    '''

    options = '''
options: 
-o, --output-file: output file (default ./frida.xml)
-p, --person-file: person input file (default ./person.xml)
-s, --sted-file:   sted input file (default ./sted.xml)
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
                                      "o:p:vd:t:h", ["output-file=",
                                                     "person-file=",
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
    person_file = "person.xml"
    # FIXME: Maybe snatch these from cereconf?
    data_source = "Cerebrum@uio.no"
    target = "FRIDA"
    
    # Why does this look _so_ ugly?
    for option, value in options:
        if option in ("-o", "--output-file"):
            output_file = value
        elif option in ("-p", "--person-file"):
            person_file = value
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
               target = target,
               person_file = person_file)
# end main





if __name__ == "__main__":
    main(sys.argv[1:])
# fi
