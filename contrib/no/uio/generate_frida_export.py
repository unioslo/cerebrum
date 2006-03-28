#! /usr/bin/env python
# -*- coding: iso8859-1 -*-
#
# Copyright 2006 University of Oslo, Norway
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
http://www.usit.uio.no/prosjekter/frida/pg/>). The output format is specified
in:

<URL: http://www.usit.uio.no/prosjekter/frida/dok/import/institusjonsdata/schema/Frida-import-1_0.xsd>
<URL: http://www.usit.uio.no/prosjekter/frida/dok/import/institusjonsdata/>

The uiocerebrum project has some additional notes
(cvs.uio.no:/uiocerebrum/docs/frida/frida-export.txt).

Although the original specification places a limit on the length of certain
(string) values, we do not enforce those. Furthermore, the address
'calculations' are a bit involved.

All information for the XML dump is fetched from the cerebrum database.

As of 2006-03, the data basis for this script is the XML files from
LDPROD/SAP, not Cerebrum.
"""

import getopt, sys, time, types

import cerebrum_path, cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.Utils import AtomicFileWriter
from Cerebrum.extlib import xmlprinter
from Cerebrum.modules.xmlutils.system2parser import system2parser
from Cerebrum.modules.xmlutils.xml2object import DataOU, DataAddress
from Cerebrum.modules.xmlutils.object2cerebrum import XML2Cerebrum
from Cerebrum.modules.xmlutils.xml2object import DataEmployment, DataOU
from Cerebrum.modules.xmlutils.xml2object import DataContact, DataPerson

INSTITUSJON = 185





def output_element(writer, value, element, attributes = dict()):
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
    if not attributes and (value is None or not str(value)):
        return
    # fi 

    writer.startElement(element, attributes)
    writer.data(str(value))
    writer.endElement(element)
# end output_element


def output_contact(writer, xmlobject, *seq):
    """Output contact information (seq) for xmlobject.

    seq is a sequence of tuples (kind, xml-attribute-name).
    """
    
    for attribute, element in seq:
        # We have to respect the relative priority order
        # TBD: Should we hide this ugliness inside DataContact?
        contacts = filter(lambda x: x.kind == attribute, xmlobject.itercontacts())
        contacts.sort(lambda x, y: cmp(x.priority, y.priority))
        if contacts:
            output_element(writer, contacts[0].value, element)
        # fi
    # od
# end output_contact


def find_ou(sko, ou_cache):
    """Locate a publishable OU starting from SKO.

    We walk upwards in the hierarchy tree until we run out of parents or
    until a publishable OU is located.
    """

    ou = ou_cache.get(sko)
    while ou:
        if ou.publishable:
            return ou
        # fi

        parent = None
        if ou.parent:
            assert ou.parent[0] == DataOU.NO_SKO
            parent = ou.parent[1]
        # fi
        ou = ou_cache.get(parent)
    # od

    return None
# end find_ou



def output_OU(writer, sko, ou_cache):
    """Publish a particular OU.

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
    """

    # step1: locate a publishable OU
    # find_ou returns either an instance of DataOU or None
    ou = find_ou(sko, ou_cache)
    if ou is None:
        return
    # fi
    sko = ou.get_id(DataOU.NO_SKO)

    # step2: output OU info
    writer.startElement("enhet")
    for value, element in ((INSTITUSJON, "institusjonsnr"),
                           (sko[0], "avdnr"),
                           (sko[1], "undavdnr"),
                           (sko[2], "gruppenr")):
        output_element(writer, value, element)
    # od

    # Is a missing parent at all possible here?
    if ou.parent:
        assert ou.parent[0] == DataOU.NO_SKO 
        psko = ou.parent[1]
    else:
        psko = (None, None, None)
    # fi
    for value, element in ((INSTITUSJON, "institusjonsnrUnder"),
                           (psko[0], "avdnrUnder"),
                           (psko[1], "undavdnrUnder"),
                           (psko[2], "gruppenrUnder")):
        output_element(writer, value, element)
    # od

    for attribute, element in (("start_date", "datoAktivFra"),
                               ("end_date", "datoAktivTil")):
        value = getattr(ou, attribute)
        if value:
            value = value.strftime("%Y-%m-%d")
        output_element(writer, value, element)
    # od

    for kind, lang, element in ((DataOU.NAME_LONG, "no", "navnBokmal"),
                                (DataOU.NAME_LONG, "en", "navnEngelsk")):
        tmp = ou.get_name_with_lang(kind, lang)
        output_element(writer, tmp, element)
    # od

    nsd = ou.get_id(DataOU.NO_NSD)
    if nsd:
        output_element(writer, str(nsd), "NSDKode")
    # fi
    
    output_element(writer, ou.get_name_with_lang(DataOU.NAME_ACRONYM, "no", "en"),
                   "akronym")

    # Grab the first available address
    for kind in (DataAddress.ADDRESS_BESOK, DataAddress.ADDRESS_POST):
        addr = ou.get_address(kind)
        if addr:
            output_element(writer, addr.street, "postadresse")
            output_element(writer, (addr.zip + " " + addr.city).strip(),
                           "postnrOgPoststed")
            output_element(writer, addr.country, "land")
            break
        # fi 
    # od

    output_contact(writer, ou,
                   (DataContact.CONTACT_PHONE, "telefonnr"),
                   (DataContact.CONTACT_FAX, "telefaxnr"),
                   (DataContact.CONTACT_EMAIL, "epost"),
                   (DataContact.CONTACT_URL, "URLBokmal"))
    
    writer.endElement("enhet")
# end output_OU
    


def output_OUs(writer, db, sysname, oufile):
    """Run through all OUs and publish the interesting ones.

    An OU is interesting to FRIDA, if:

    - the OU is supposed to be published (marked as such in the data source)
    - it has been less than a year since the OU has been terminated.
    """

    # First we build an ID cache.
    ou_cache = dict()
    parser = system2parser(sysname)(oufile, False)
    it = parser.iter_ou()
    while 1:
        try:
            ou = it.next()
        except StopIteration:
            break
        except:
            logger.exception("Failed to process next OU")
            continue
        # yrt

        sko = ou.get_id(DataOU.NO_SKO, None)
        if sko:
            ou_cache[sko] = ou
        # fi
    # od

    logger.info("Cached info on %d OUs from %s", len(ou_cache), oufile)
    for sko in ou_cache:
        output_OU(writer, sko, ou_cache)
    # od
# end output_OUs


def output_assignments(writer, seq, blockname, elemname, *rest):
    """Output tilsetting/gjest information.

    The format is:
    
    <blockname>
      <elemname>
        <k1>x.v1</k1>
        <k2>x.v2</k2>
      </elemname>
    </blockname>

    ... where rest is a sequence of (v1, k1) and seq contains the x's to be
    output.
    """
    
    if not seq:
        return
    # fi

    writer.startElement(blockname)
    for item in seq:
        writer.startElement(elemname)
        assert item.place[0] == DataOU.NO_SKO
        ou = item.place[1]
        for value, xmlelement in ((INSTITUSJON, "institusjonsnr"),
                                  (ou[0], "avdnr"),
                                  (ou[1], "undavdnr"),
                                  (ou[2], "gruppenr")):
            output_element(writer, value, xmlelement)
        # od

        for key, xmlelement in rest:
            value = getattr(item, key)
            # FIXME: DateTime hack. SIGTHTBABW
            if hasattr(value, "strftime"):
                value = value.strftime("%Y-%m-%d")
            output_element(writer, value, xmlelement)
        # od
        
        writer.endElement(elemname)
    # od
        
    writer.endElement(blockname)
# end output_assignments


def output_person(writer, person, db, source_system):
    """Output all information pertinent to a particular person.

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
    """

    employments = filter(lambda x: x.kind in (DataEmployment.HOVEDSTILLING,
                                              DataEmployment.BISTILLING) and
                                   x.is_active(),
                         person.iteremployment())
    guests = filter(lambda x: x.kind == DataEmployment.GJEST and
                              x.is_active(),
                    person.iteremployment())

    if not (employments or guests):
        logger.info("person_id %s has no suitable tils/gjest records",
                    list(person.iterids()))
        return
    # fi

    reserved = { True  : "J",
                 False : "N",
                 None  : "N", }[person.reserved]
    fnr = person.get_id(DataPerson.NO_SSN)
    writer.startElement("person", { "fnr" : fnr,
                                    "reservert" : reserved })
    for attribute, element in ((DataPerson.NAME_LAST, "etternavn"),
                               (DataPerson.NAME_FIRST, "fornavn"),
                               (DataPerson.NAME_TITLE, "personligTittel")):
        # NB! I assume here that there is only *one* name. Is this always true
        # for personligTittel?
        output_element(writer, person.get_name(attribute), element)
    # od

    db_person = Factory.get("Person")(db)
    db_const = Factory.get("Constants")(db)
    try:
        db_person.find_by_external_id(db_const.externalid_fodselsnr, fnr)
    except Errors.NotFoundError:
        logger.error("Person %s is in the datafile, but not in Cerebrum",
                     list(person.iterids()))
    else:
        primary_account = db_person.get_primary_account()
        if primary_account is None:
            logger.info("Person %s has no accounts", list(person.iterids()))
        else:
            db_account = Factory.get("Account")(db)
            db_account.find(primary_account)

            output_element(writer, db_account.get_account_name(), "brukernavn")

            try:
                primary_email = db_account.get_primary_mailaddress()
                output_element(writer, primary_email, "epost")
            except Errors.NotFoundError:
                logger.info("person %s has no primary e-mail address",
                            list(person.iterids()))
                pass
            # yrt
        # fi
    # yrt

    output_contact(writer, person,
                   (DataContact.CONTACT_PHONE, "telefonnr"),
                   (DataContact.CONTACT_FAX, "telefaxnr"),
                   (DataContact.CONTACT_URL, "URL"))

    output_assignments(writer, employments,
                      "ansettelser", "ansettelse",
                      ("code", "stillingskode"),
                      ("start", "datoFra"),
                      ("end", "datoTil"),
                      ("title", "stillingsbetegnelse"),
                      ("percentage", "stillingsandel"))

    output_assignments(writer, guests,
                      "gjester", "gjest",
                      ("start", "datoFra"),
                      ("end", "datoTil"),
                      ("code", "gjestebetegnelse")) 

    writer.endElement("person")
# end output_person


def output_people(writer, db, sysname, personfile):
    """Output information about all interesting people.

    A person is interesting for FRIDA, if it has active employments
    (tilsetting) or active guest records (gjest). A record is considered
    active, if it has a start date in the past (compared to the moment when
    the script is run) and the end date is either unknown or in the future.
    """

    logger.info("extracting people from %s", personfile)

    source_system = getattr(Factory.get("Constants")(db), sysname)

    writer.startElement("personer")
    parser = system2parser(sysname)(personfile, False)
    it = parser.iter_persons()
    while 1:
        try:
            person = it.next()
        except StopIteration:
            break
        except:
            logger.exception("Failed to process next person")
            continue
        # yrt

        output_person(writer, person, db, source_system)
    # od

    writer.endElement("personer")
# output_people


def output_xml(output_file, sysname, personfile, oufile):
    """Output the data from sysname source."""

    output_stream = AtomicFileWriter(output_file, "w")
    writer = xmlprinter.xmlprinter(output_stream,
                                   indent_level = 2,
                                   data_mode = True,
                                   input_encoding = "latin1")
    db = Factory.get("Database")()

    # Hardcoded headers
    writer.startDocument(encoding = "iso8859-1")

    writer.startElement("fridaImport")

    writer.startElement("beskrivelse")
    output_element(writer, "UIO", "kilde")
    # ISO8601 style -- the *only* right way :)
    output_element(writer, time.strftime("%Y-%m-%d %H:%M:%S"), "dato")
    output_element(writer, "UiO-FRIDA", "mottager")
    writer.endElement("beskrivelse")

    writer.startElement("institusjon")
    output_element(writer, INSTITUSJON, "institusjonsnr")
    output_element(writer, "Universitetet i Oslo", "navnBokmal")
    output_element(writer, "University of Oslo", "navnEngelsk")
    output_element(writer, "UiO", "akronym")
    output_element(writer, "1110", "NSDKode")
    writer.endElement("institusjon")

    # Dump all OUs
    output_OUs(writer, db, sysname, oufile)

    # Dump all people
    output_people(writer, db, sysname, personfile)
    
    writer.endElement("fridaImport")

    writer.endDocument()

    output_stream.close()
# end output_xml



def main():
    global logger
    logger = Factory.get_logger("cronjob")
    logger.info("Generating FRIDA export")

    try:
        options, rest = getopt.getopt(sys.argv[1:],
                                      "o:s:", ["output-file=",
                                               "source-spec=",])
    except getopt.GetoptError, val:
        usage(1)
        sys.exit(str(val))
    # yrt

    output_file = "frida.xml"
    sources = list()

    for option, value in options:
        if option in ("-o", "--output-file"):
            output_file = value
        elif option in ("-s", "--source-spec"):
            sysname, personfile, oufile = value.split(":")
        # fi
    # od

    output_xml(output_file, sysname, personfile, oufile)
# end main
    
    



if __name__ == "__main__":
    main()
# fi
