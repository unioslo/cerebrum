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
export. We use Norwegian fødselsnummer to tie <person>-elements to database
rows.

sted.xml format is noe specified anywhere (but it will be :)). For now, this
file is ignored and no <URL> elements are generated in frida.xml (in
violation of the FRIDA.dtd).

"""

import xml.sax
import sys
import time
import getopt
import string
import locale
import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum import Database
from Cerebrum.Utils import Factory
from Cerebrum.extlib import xmlprinter
from Cerebrum.modules import Email
from Cerebrum.modules.no import Stedkode
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uit.nsd import nsd
# UiT: added the next import line
from Cerebrum.modules.no.uit.Email import email_address

locale.setlocale(locale.LC_ALL,"en_US.ISO-8859-1")
# FIXME: As of python 2.3, this module is part of the standard distribution
if sys.version >= (2, 3):
    import logging
else:
    from Cerebrum.extlib import logging
# fi

#logger = logging.getLogger("console")
logger = None
#logger = Factory.get_logger("cronjob")



#UIT:
# Added by kenneth
# date 27.10.2005
class system_xRepresentation(object):
    """This class gets information about persons from system_x that has
    a frida spread. All these persons will have a 'gjest' identification withtouth
    any stillingskode or stillings tittel. The data about these persons are collected
    straight from the database.

    Each person will then populate the following fields according to the FRIDA dtd:
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

    NB: All 'gjest' persons are entered into cerebrum via system_x. This means they
        do not exist in cerebrum already. q.e.d, they will wither appear here as a 'gjest'
        or in the LT/SLP4 import.
    """

    
    def execute(self,writer,system_source):
        db = Factory.get('Database')()
        person = Factory.get('Person')(db)
        account = Factory.get('Account')(db)
        const = Factory.get('Constants')(db)
        stedkode = Stedkode.Stedkode(db)


        current_source_system= const.system_x

        # Get all persons that come from SysX _and_ has a norwegian SSN! 
        entities = person.list_external_ids(source_system=const.system_x,id_type=const.externalid_fodselsnr,entity_type=8)
        for entity in entities:
            account.clear()
            person.clear()
            stedkode.clear()

            # find account and person objects
            person.find(entity['entity_id'])
                        
            acc_id = person.get_primary_account()
            if (acc_id):
                account.find(acc_id)
            else:
                logger.warn("SysX person ID=(%s) Fnr=(%s) has no active account" % (entity['entity_id'],entity['external_id']))
                continue
                             

            external_id = entity['external_id']
            person_attrs = {"fnr":external_id,"reservert":"N"}
            account_name = account.account_name            
            
            # Get the affiliation status code string
            try:
                aff = person.list_affiliations(person_id=person.entity_id,source_system=current_source_system)
                fornavn = person.get_name(current_source_system,const.name_first)
                etternavn = person.get_name(current_source_system,const.name_last)
                aff_str = const.PersonAffStatus(aff[0]['status'])
                aff_id = aff[0]['ou_id']
            except Errors.NotFoundError:
                # Frida spread from another source system, we dont care about these here...
                continue
            except Exception,msg:
                logger.error("Error: %s,account_id =%s,person_id=%s" % (msg,account.entity_id,person.entity_id))
                continue


            # Got info, output!
            writer.startElement("person",person_attrs)

            writer.startElement("etternavn")
            writer.data(etternavn)
            writer.endElement("etternavn")

            writer.startElement("fornavn")
            writer.data(fornavn)
            #writer.endElement("givenName")
            writer.endElement("fornavn")

            writer.startElement("brukernavn")
            writer.data(account_name)
            writer.endElement("brukernavn")
            writer.startElement("gjester")
            writer.startElement("gjest")

            writer.startElement("institusjonsnr")
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

            dato_fra ="%s-%s-%s" % (create_date.year,create_date.month,create_date.day)
            writer.data(dato_fra)
            writer.endElement("datoFra")

            writer.startElement("gjestebetegnelse")
            writer.data(aff_str.status_str)
            writer.endElement("gjestebetegnelse")
            
            writer.endElement("gjest")
            writer.endElement("gjester")
            writer.endElement("person")
        #generate XML data


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
        if not (attributes.has_key("fodtdag") and
                attributes.has_key("fodtmnd") and
                attributes.has_key("fodtar") and
                attributes.has_key("personnr")):
            raise (ValueError,
                  "Missing critical data for person: " + str(attributes))

        self.fnr = "%02d%02d%02d%5s" % (int(attributes["fodtdag"]),
                                        int(attributes["fodtmnd"]),
                                        int(attributes["fodtar"]),
                                        attributes["personnr"])


        # NB! This code might raise fodselsnr.InvalidFnrError
        #     We need sanity checking, because LT dumps are suffer from bitrot
        #     (e.g. Swedish SSNs end up as Norwegian. Gah!)
        #logger.debug("self.fnr = %s" % self.fnr)
        fodselsnr.personnr_ok(self.fnr)
        
        self.fnr = self.fnr.encode("latin1")
        # we do not really need a name (it is in cerebrum), but it might
        # come in handy during debugging stages

        self.name = attributes["navn"].encode("latin1")
        logger.debug("extracted new person element from LT (%s, %s)",
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
            key = key.encode("latin1")
            value = value.encode("latin1")
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
                if not res.has_key(attribute) or res[attribute] != value:
                    hit = False
                    break 
            if hit: return True

        return False


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
      <gjest sko="130447" gjestetypekode="EMERITUS"/>
      <res katalogkode="ELKAT" felttypekode="PRIVADR"/>
    </person>

    FIXME: Note that the example above does not validate with lt-person.dtd
    (dato_fra and dato_til are missing from the <gjest>-element).
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
        elif (name in self.INTERESTING_ELEMENTS and
              self.current_person):
            self.current_person.register_element(name, attributes)


    def endElement(self, name):
        if name == self.PERSON_ELEMENT and self.current_person:
            self.callback(self.current_person)
# end class LTPersonParser



def output_organization(writer, db):
    """
    Output information about <Organization>

    FIMXE: NB! It might be wise to move all these hardwired values into
    cereconf. They are probably used by several parts of the cerebrum
    anyway.
    """

    writer.startElement("institusjon")

    writer.startElement("institusjonsnr")
    writer.data(cereconf.DEFAULT_INSTITUSJONSNR)
    writer.endElement("institusjonsnr")

    #for attributes in [("no", "Universitetet i Tromsø"),
    #                   ("en", "University of Tromsoe")]:
        #("la", "Universitas Osloensis")]:
    writer.startElement("navnBokmal")
    writer.data("Universitetet i Tromsø")
    writer.endElement("navnBokmal")
    writer.startElement("navnEngelsk")
    writer.data("Universitetet of Tromsoe")
    writer.endElement("navnEngelsk")
    #writer.startElement("norInstitutionName", {"language" : attributes[0]})
    #writer.data(attributes[1])

    # od
    writer.startElement("akronym")
    writer.data("UIT")
    writer.endElement("akronym")
    #for attributes in [("no", "UiT"), ("en", "UoT")]:
    #    writer.startElement("norInstitutionAcronym",
    #                        {"language" : attributes[0]})
    #    writer.data(attributes[1])
    #    writer.endElement("norInstitutionAcronym")
    # od

    writer.endElement("institusjon")
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
    
    writer.startElement("postnrOgPoststed")
    # We cannot have more than one answer for any given
    # (ou_id, source_system, address_type) triple
    
    address = db_ou.get_entity_address(constants.system_fs,
                                       constants.address_post)[0]

    #address = db_ou.get_entity_address(constants.system_fs,
    #                                   155)[0]
    
    #address = 155
    #city = address["city"]
    city = "Tromsø"
    #po_box = address["p_o_box"]
    po_box = "None"
    #postal_number = address["postal_number"]
    postal_number = "9037"
    #country = address["country"]
    country = "Norway"
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
        logger.error("There is no address information for %s",
                     db_ou.entity_id)
    # fi
    
    writer.data(output)
    writer.endElement("postnrOgPoststed")
# end output_OU_address



def output_OU(writer, id, db_ou, stedkode, constants,db):
    """
    Output all information pertinent to a specific OU

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
    if stedkode.katalog_merke != 'T':
        logger.debug("Skipping ou_id == %s", id)
        return
    # fi

    ou_names = db_ou.get_names()
    ou_acronyms = db_ou.get_acronyms()
    # Ufh! I want CL's count-if
    # Check that there is at least one name and at least one
    # acronym that are not empty.
    has_any = (lambda sequence, field:
                      [x for x in sequence
                         if x[field] is not None])
    if (not has_any(ou_names, "name") or 
        not has_any(ou_acronyms, "acronym")):
        logger.error("Missing name/acronym information for ou_id = %s",
                     id)
        return
    # fi

    writer.startElement("enhet")

    #institusjonsnr
    writer.startElement("institusjonsnr")
    writer.data("186")
    writer.endElement("institusjonsnr")

    # norOrgUnitFaculty/avdnr
    #writer.startElement("norOrgUnitFaculty")
    writer.startElement("avdnr")
    writer.data(str(stedkode.fakultet))
    #writer.endElement("norOrgUnitFaculty")
    writer.endElement("avdnr")

    # norOrgUnitDepartment/undavdnr
    #writer.startElement("norOrgUnitDepartment")
    writer.startElement("undavdnr")
    writer.data(str(stedkode.institutt))
    #writer.endElement("norOrgUnitDepartmen")
    writer.endElement("undavdnr")

    # norOrgUnitGroup/gruppenr
    #writer.startElement("norOrgUnitGroup")
    writer.startElement("gruppenr")
    writer.data(str(stedkode.avdeling))
    #writer.endElement("norOrgUnitGroup")
    writer.endElement("gruppenr")
    

    
    
    
    # NB! Extra lookups here cost us about 1/3 of the time it takes to
    #     generate all information on OUs
    parent_id = db_ou.get_parent(constants.perspective_fs)
    # This is a hack (blame baardj) for the root of the organisational
    # structure.
    if parent_id is None:
        parent_id = id
    # fi

    # find parent. NB! Remember to reset stedkode
    stedkode.clear(); stedkode.find(parent_id)

    writer.startElement("institusjonsnrUnder")
    writer.data(str(stedkode.institusjon))
    writer.endElement("institusjonsnrUnder")

    # norParentOrgUnitFaculty
    #writer.startElement("norParentOrgUnitFaculty")
    writer.startElement("avdnrUnder")
    writer.data(str(stedkode.fakultet))
    #writer.endElement("norParentOrgUnitFaculty")
    writer.endElement("avdnrUnder")
    
    # norParentOrgUnitDepartment
    #writer.startElement("norParentOrgUnitDepartment")
    writer.startElement("undavdnrUnder")
    writer.data(str(stedkode.institutt))
    #writer.endElement("norParentOrgUnitDepartment")
    writer.endElement("undavdnrUnder")
    
    # norParentOrgUnitGroup
    #writer.startElement("norParentOrgUnitGroup")
    writer.startElement("gruppenrUnder")
    writer.data(str(stedkode.avdeling))
    #writer.endElement("norParentOrgUnitGroup")
    writer.endElement("gruppenrUnder")
    
    # restore 'pointer' back to child
    stedkode.clear(); stedkode.find(id)
    
    # norOrgUnitNames+
    for name, language in ou_names:
        # Some tuples might have empty names (general case)
        if not name: continue
        attributes = {}
        if language: attributes = {"language": language}
        writer.startElement("navnBokmal", attributes)
        writer.data(name)
        writer.endElement("navnBokmal")
    # od


    # norOrgUnitAcronym+
    for acronym, language in ou_acronyms:
        # some tuples might have empty acronyms
        if not acronym: continue
        attributes = {}
        if language: attributes = {"language": language}
        #writer.startElement("norOrgUnitAcronym", attributes)
        writer.startElement("akronym", attributes)
        writer.data(str(acronym).lower())
        #writer.endElement("norOrgUnitAcronym")
        writer.endElement("akronym")
    # od

    # Addressline
    output_OU_address(writer, db_ou, constants)

    # Telephone
    for row in db_ou.get_contact_info(source=constants.system_lt,
                                      type=constants.contact_phone):
        writer.startElement("Telephone")
        writer.data(row.contact_value)
        writer.endElement("Telephone")
    # od

    # Fax
    for row in db_ou.get_contact_info(source=constants.system_lt,
                                      type=constants.contact_fax):
        writer.startElement("Fax")
        writer.data(row.contact_value)
        writer.endElement("Fax")
    # od
        
    # FIXME: URLs! For now we will simply ignore them
    #writer.startElement("URLBokmal")
    #writer.data("Not implemented")
    #writer.endElement("URLBokmal")
    

    # UIT ADDITION:
    # insert NSD kode
    my_nsd = nsd()
    nsd_kode = 0
    nsd_kode = my_nsd.get_nsd(stedkode.fakultet,stedkode.institutt,stedkode.avdeling,db)
    writer.startElement("NSDKode")
    #print "nsd kode = %s" % nsd_kode
    if nsd_kode != 0:
        for i in nsd_kode:
            writer.data(str(i['nsd']))
    else:
        write.data(str("MISSING %s%s%s" % stedkode.fakultet,stedkode.institutt,stedkode.avdeling))
    writer.endElement("NSDKode")

    writer.endElement("enhet")
# end output_OU
    


def output_OUs(writer, db):
    """
    Output information about all interesting OUs.

    An OU is interesting to FRIDA, if it is active in LT *now*
    (i.e. most recent LT dump) and is explicitely set up for
    publishing in a catalogue service (katalog_merke = 'T').
    """
    db = Factory.get('Database')()
    db_ou = Factory.get("OU")(db)
    stedkode = Stedkode.Stedkode(db)
    constants = Factory.get("Constants")(db)

    writer.startElement("organisasjon")
    for id in db_ou.list_all():
        output_OU(writer, id["ou_id"], db_ou, stedkode, constants,db)
    # od
    writer.endElement("organisasjon")
# end output_OUs



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
    attributes["fnr"] = str(row['external_id'])


    # The rule for selecting primary affiliation is pretty simple:
    # 1. If there is an ANSATT/vitenskapelig affiliation then
    #    Affiliation = Faculty
    # 2. If there is an ANSATT/tekadm affiliation then Affiliation = Staff
    # 3. Otherwise Affiliation = Member
    # 
    # We can do this in one database lookup, at the expense of much uglier
    # code
    #if db_person.list_affiliations(db_person.entity_id,
    #                               constants.system_lt,
    #                               constants.affiliation_ansatt,
    #                               constants.affiliation_status_ansatt_vit):
    #    attributes["Affiliation"] = "Faculty"
    #elif db_person.list_affiliations(db_person.entity_id,
    #                                 constants.system_lt,
    #                                 constants.affiliation_ansatt,
    #                                 constants.affiliation_status_ansatt_tekadm):
    #    attributes["Affiliation"] = "Staff"
    #else:
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
        # fi
    else:
        if pobj.has_reservation(katalogkode="ELKAT",
                                felttypekode="GJESTEOPPL"):
            attributes["reservert"] = "N"
        else:
            attributes["reservert"] = "J"
        # fi
    # fi
    attributes["reservert"] = "N"
    return attributes
# end construct_person_attributes



def output_employment_information(writer, pobj):
    """
    Output all employment information pertinent to a particular person
    (POBJ). I.e. convert from <tils>-elements in LT dump to <Tilsetting>
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
#         elif element["hovedkat"] == "ØVR":
#             attributes = {"Affiliation": "Staff"}
#         else:
#             logger.error("Aiee! %s has no suitable employment affiliation %s",
#                          pobj.fnr, str(element))
#             continue
        # fi
        
        #writer.startElement("Tilsetting", attributes)
        writer.startElement("ansettelse")

        # FRIDA wants date at the format YYYYMMDD while the format already
        # stored is DD.MM.YYY. thus the next tree lines are needed to convert to the right format
        start = element["dato_fra"]
        my_month,my_day,my_year = start.split("/")
        element["dato_fra"] = '%s-%s-%s' % (my_year,my_month,my_day)
        writer.startElement("institusjonsnr")
        writer.data(cereconf.DEFAULT_INSTITUSJONSNR)
        writer.endElement("institusjonsnr")

        for output, input in [("avdnr", "fakultetnr_utgift"),
                              ("undavdnr", "instituttnr_utgift"),
                              ("gruppenr", "gruppenr_utgift"),
                              ("stillingskode", "stillingkodenr_beregnet_sist"),
                              ("datoFra", "dato_fra"),
                              #("datoTil", "dato_til"),
                              ("stillingsbetegnelse", "tittel"),
                              ("stillingsandel", "prosent_tilsetting"),
                              ]:
         

            writer.startElement(output)
            # UIT: must minimize the element["tittel"] entry
            element["tittel"] = element["tittel"].lower()
            writer.data(element[input])
           
            writer.endElement(output)
        # od

        writer.endElement("ansettelse")
    writer.endElement("ansettelser")
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
# end output_guest_information



#def output_person(execute,email_list,writer, pobj, db_person, db_account, constants,system_source):
def output_person(writer, pobj, db_person, db_account, constants,system_source):
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
    #for i in pobj:
    #    print "i = %s" %i
    #sys.exit(1)
    db = Factory.get('Database')()
    #et = Email.EmailTarget(db)
    #ea = Email.EmailAddress(db)
    #edom = Email.EmailDomain(db)
    #epat = Email.EmailPrimaryAddressTarget(db)
    account = Factory.get('Account')(db)
    # Ignore 'uninteresting' people
    #if not pobj.is_frida(): return

    db_person.clear()
    db_account.clear()

    # NB! There can be *only one* FNR per person in LT (PK in
    # the person_external_id table)
    #print "externalid_fodselsnr = %s" % constants.externalid_fodselsnr
    #print "fnr = %s" % pobj.fnr
    #print "constant.system_lt = %s" % constants.system_lt
    db_person.find_by_external_id(constants.externalid_fodselsnr,
                                  pobj.fnr,
                                  system_source)

    writer.startElement("person",
                        construct_person_attributes(writer,
                                                    pobj,
                                                    db_person,
                                                    constants))
    # surname
    #writer.startElement("sn")
    writer.startElement("etternavn")
    #print "etternavn--->%s<---" %(str(db_person.get_name(system_source,
    #                                   constants.name_last)))
    writer.data(str(db_person.get_name(system_source,
                                       constants.name_last)))
    #writer.endElement("sn")
    writer.endElement("etternavn")

    # first name
    first_name = db_person.get_name(system_source,
                                    constants.name_first)
    #print "fornavn--->%s<---" % first_name
    if first_name:
        #writer.startElement("givenName")
        writer.startElement("fornavn")
        writer.data(str(first_name))
        #writer.endElement("givenName")
        writer.endElement("fornavn")
    # fi

    # uname && email for the *primary* account.
    primary_account = db_person.get_primary_account()
    
    #print "Primary account_id=%s" % primary_account    
    #account.find(primary_account)
    #print "MYEMAIL = %s" % my_email    
    #accounts = db_person.get_accounts()

    #####################################################
    # UIT: need to find the primary account of the user
    # and the get the right email address
    #####################################################
    
    #traverse all accounts for this person
    #for i in accounts:
    #    account.find(i['account_id'])
    #    types = account.get_account_types()
    #    # traverse all account types for this account
    #    main_check = 0
    #    for type in types:
    #        if ((type['affiliation'] == constants.affiliation_student)and(main_check ==0)):
    #my_email = execute.account_id2email_address (primary_account)
    #        elif (type['affiliation'] == constants.affiliation_ansatt):
    #            main_check = 1
    #            primary_account = i['account_id']
    #            my_email = execute.account_id2email_address (primary_account)
    #account.clear()
    # UIT: end
    ########################################################
    
    #print "account stuff = %s" % primary_account.items()

    if primary_account is None:
        logger.warn("Person %s has no accounts", pobj.fnr)
    else:
        db_account.find(primary_account)
        try:
            my_email = db_account.get_primary_mailaddress()
        except Errors.NotFoundError:
            # UIT: No primary email addr. What do we do??
            logger.warn("Account '%s' has no email address!" % db_account.get_account_name())
            my_email = ""
            
        writer.startElement("brukernavn")
        writer.data(db_account.get_account_name())
        writer.endElement("brukernavn")
        writer.startElement("epost")
        writer.data(my_email)
        writer.endElement("epost")
    # fi

    # <Telephone>?
    # We need the one with lowest contact_pref, if there are many
    contact = db_person.get_contact_info(source=system_source,
                                         type=constants.contact_phone)
    contact.sort(lambda x, y: cmp(x.contact_pref, y.contact_pref))
    if contact:
        writer.startElement("telefonnr")
        writer.data(contact[0].contact_value)
        writer.endElement("telefonnr")
    # od

    output_employment_information(writer, pobj)

    output_guest_information(writer, pobj)
    
    writer.endElement("person")
    db.close()
# end 

# def get_ansatt_email(stedkode):
#     #front = fronter_lib.uitfronter(db)
 

#     my_fakultet = "%02i" % int(stedkode[0:2])
#     my_institutt = "%02i" % int(stedkode[2:4])
#     my_gruppe = "%02i" % int(stedkode[4:6])
 
#     #print "my stedkode = %s,%s,%s," % (my_fakultet,my_institutt,my_gruppe)
#     # TODO: This should be given as a parameter to the program itself and not hardcoded like it is now
#     file = "/home/cerebrum/CVS/cerebrum/contrib/no/uit/create_import_data/source_data/email_conversion_list.txt"
#     file_handle = open(file,"r")
#     check = 0
#     my_email_domain = "asp.no"
#     for element in file_handle:
#         if((element[0] != '#') and (element[0] != '\n')):
#             sko,email_domain = element.split(' ')
#             ou_fakultet = sko[0:2]
#             ou_institutt = sko[2:4]
#             ou_gruppe = sko[4:6]
#             if ((my_fakultet == ou_fakultet) and (my_institutt == ou_institutt) and(my_institutt != '00')):
#                 my_email_domain = email_domain
#                 check = 1
#                 #print "email at institute level= %s" % my_email_domain
#             if((my_fakultet == ou_fakultet) and (ou_institutt == '00')and(check == 0)):
#                 my_email_domain = email_domain
#                 #print "email at faculty level =%s" % my_email_domain
#     return my_email_domain



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

    #writer.startElement("NorPersons")
    writer.startElement("personer")

    # NB! The callable object (2nd argument) is invoked each time the parser
    # sees a </person> tag.
    # 
#    execute = email_address()
#    email_list = execute.build_email_list()
    
#    parser = LTPersonParser(person_file,
#                            lambda p: output_person(execute,email_list,writer = writer,
#                                                    pobj = p,
#                                                    db_person = db_person,
#                                                    db_account = db_account,
#                                                    constants = constants,
#                                                    system_source = constants.system_lt))

    parser = LTPersonParser(person_file,
                            lambda p: output_person(writer = writer,
                                                    pobj = p,
                                                    db_person = db_person,
                                                    db_account = db_account,
                                                    constants = constants,
                                                    system_source = constants.system_lt))


    parser.parse()
    system_x_parser = system_xRepresentation()
    system_x_parser.execute(writer = writer,system_source = constants.system_x)
    #writer.endElement("NorPersons")
    writer.endElement("personer")
# end output_people    



def output_xml(output_file,
               data_source,
               target,
               person_file):
    """
    Initialize all connections and start generating the xml output.

    OUTPUT_FILE names the xml output.

    DATA_SOURCE and TARGET are elements in the xml output.

    PERSON_FILE is the name of the LT dump (used as input).
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
    writer.startDocument(encoding = "iso-8859-1")

    #writer.startElement("XML-export")
    xml_options = {'xmlns:xsi' : "http://www.w3.org/2001/XMLSchema-instance","xsi:noNamespaceSchemaLocation":"http://www.usit.uio.no/prosjekter/frida/dok/import/institusjonsdata/schema/Frida-import-1_0.xsd"}
    writer.startElement("fridaImport",xml_options)

    writer.startElement("beskrivelse")
    writer.startElement("kilde")
    writer.data(data_source)
    writer.endElement("kilde")
    writer.startElement("dato")
    # ISO8601 style -- the *only* right way :)
    #writer.data(time.strftime("%Y-%m-%dT%H:%M:%S"))
    writer.data(time.strftime("%Y-%m-%d"))
    writer.endElement("dato")
    writer.startElement("mottager")
    writer.data(target)
    writer.endElement("mottager")

    writer.endElement("beskrivelse")

    #writer.startElement("NorOrgUnits")
    # Organization "header"
    # FIXME: It's all hardwired
    output_organization(writer, db)

    # Dump all OUs
    output_OUs(writer, db)

    #writer.endElement("NorOrgUnits")
    # Dump all people
    output_people(writer, db, person_file)
    
    writer.endElement()
    #writer.endElement("fridaImport")
    writer.endDocument()
    output_stream.close()
# end 



def usage():
    '''
    Display option summary
    '''

    options = '''
options: 
-o, --output-file: output file 
-p, --person-file: person input file 
-s, --sted-file:   sted input file 
-v, --verbose:     output some debugging
-d, --data-source: source that generates frida.xml (default"UITO")
-t, --target:      what (whom :)) the dump is meant for (default "FRIDA")
-h, --help:        display usage
    '''

    # FIMXE: hmeland, is the log facility the right thing here?
    print options
# end usage



def main():
    """
    Start method for this script. 
    """

    global logger

    try:
        options, rest = getopt.getopt(sys.argv[1:],
                                      "o:p:s:vd:t:hl:", ["output-file=",
                                                         "person-file=",
                                                         "sted-file=",
                                                         "verbose",
                                                         "data-source=",
                                                         "target",
                                                         "help",
                                                         "logger_name=",])
    except getopt.GetoptError:
        usage()
        sys.exit(1)


    # Default values
    output_file = 0
    person_file = 0
    sted_file = 0
    verbose = False
    # FIXME: Maybe snatch these from cereconf?
    data_source = "UITO"
    target = "FRIDA"
    logger_name = cereconf.DEFAULT_LOGGER_TARGET
    
    # Why does this look _so_ ugly?
    for option, value in options:
        if option in ("-o", "--output-file"):
            output_file = value
        elif option in ("-p", "--person-file"):
            person_file = value
        elif option in ("-s", "--sted-file"):
            sted_file = value
        elif option in ("-v", "--verbose"):
            # FIXME: make the logger log more? :)
            pass
        elif option in ("-d", "--data-source"):
            data_source = value
        elif option in ("-t", "--target"):            
            target = value
        elif option in ('-l', '--logger_name'):
            logger_name = value
        elif option in ("-h", "--help"):
            usage()
            sys.exit(2)

    logger = Factory.get_logger(logger_name)
    if (sted_file != 0 and output_file != 0 and person_file != 0):
        logger.info( "Generating FRIDA export")
        output_xml(output_file = output_file,
                   data_source = data_source,
                   target = target,
                   person_file = person_file)
    else:
        usage()





if __name__ == "__main__":
    main()

# arch-tag: adade92c-b426-11da-9da7-f4082863a3d1
