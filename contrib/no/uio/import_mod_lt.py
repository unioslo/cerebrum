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

import sys
import traceback
import string
import types
import xml
import xml.sax
import getopt

import cerebrum_path
import cereconf

import Cerebrum
from Cerebrum import Constants
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import Stedkode
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uio.mod_lt_codes import PermisjonsKode
from Cerebrum.modules.no.uio.mod_lt_codes import RolleKode
from Cerebrum.modules.no.uio.mod_lt_codes import StillingsKode
from Cerebrum.modules.no.uio.mod_lt_codes import GjestetypeKode
from Cerebrum.modules.no.uio.mod_lt_codes import Lonnsstatus

# FIXME: As of python 2.3, this module is part of the standard distribution
if sys.version >= (2, 3):
    import logging
else:
    from Cerebrum.extlib import logging
# fi





class PersonParser(xml.sax.ContentHandler):
    """
    This is a simple parser for the XML data file coming from LT.

    The xml source contains much more information than we need. Only certain
    elements are collected.
    """

    INTERESTING_ELEMENTS = [ "attrs", "bilag", "tils", "gjest", "res", "rolle" ]



    def __init__(self, filename, callback):
        self.callback = callback
        self.current_person = None
        self.current_tils = None
        xml.sax.parse(filename, self)
    # end __init__



    def startElement(self, element, attrs):
        decoded_attrs = {}
        for key, value in attrs.items():
            decoded_attrs[ key.encode( "latin1" ) ] = value.encode( "latin1" )
        # od
        
        if element == "person":
            # provide default values
            self.current_person = dict([(x, []) for x in self.INTERESTING_ELEMENTS])
            self.current_person["attrs"] = decoded_attrs
        elif element == "tils":
            self.current_tils = {"tilsetting" : decoded_attrs,
                                 "permisjon" : []}
            self.current_person[element].append(self.current_tils)
        elif element == "permisjon":
            self.current_tils["permisjon"].append(decoded_attrs)
        elif element in self.INTERESTING_ELEMENTS:
            self.current_person[element].append(decoded_attrs)
        # fi
    # end startElement



    def endElement(self, element):
        if element == "person":
            self.callback( self.current_person )
        # fi
    # end endElement
# end PersonParser





def find_stedkode(stedkode, fakultet, institutt, gruppe):
    """
    Locate the OU identified by FAKULTET, INSTITUTT, GRUPPE. Populate
    STEDKODE object with that information.

    Returns True if an OU is located, False otherwise.
    """

    stedkode.clear()
    try: 
        stedkode.find_stedkode(fakultet,
                               institutt,
                               gruppe,
                               185)
        return True
    except Cerebrum.Errors.NotFoundError, value:
        logger.error("Aiee! OU not found: %s, %s, %s %s",
                     fakultet, institutt, gruppe, value)
        return False
    # yrt

    # NOTREACHED
    return False
# end find_stedkode



def has_reservation(pxml, **attributes):
    """
    Check whether <person> represented by PXML contains at least one <res>
    element with specified ATTRIBUTES.
    """

    items = attributes.items()
    
    for res in pxml.get("res", []):
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
# end has_reservation
  


def get_reservation(pxml, person):
    '''
    Returns the reservation status ( True | False ) for a person represented
    by PERSON.

    PERSON is an instance of Cerebrum.Person core class

    PXML is a dictionary representing a <person> element in the XML source.

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

    '''
    reserved = True
    not_reserved = False
    unknown = None

    if person.get_tilsetting():
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

            if has_reservation(pxml, **tmp ):
                logger.info("%s has an employee reservation; criteria: %s %s",
                            person.entity_id, str(felttypekode),
                            str(resnivakode))
                return reserved
            # fi
        # od

        # None of the reservation were present. This means that the person
        # is up for grabs
        logger.info("%s has NO reservations. All tests failed",
                    person.entity_id)
        return not_reserved
    elif person.get_gjest():
        # guests are different
        if has_reservation(pxml,
                           katalogkode="ELKAT",
                           felttypekode="GJESTEOPPL",
                           resnivakode="SAMTYKKE"):
            logger.info("%s has a guest permit (NO res)", person.entity_id)
            return not_reserved
        else:
            logger.info("%s is a guest and is reserved", person.entity_id)
            return reserved
        # fi
    else:
        logger.info("%s has neither guest nor employment information. " +
                    "No reservation information can be calculated",
                    person.entity_id)
        return unknown
    # fi
# end get_reservation



def import_reservasjon(pxml, person, stedkode, constanns):
    """
    Import reservation information about PERSON/PXML.

    NB! This operation *requires* up-to-date information on PERSON's
    tilsetting and gjest records.
    """

    reservation = None
    for element in pxml["res"]:
        value = get_reservation(pxml, person)

        # If there is at least one reservation, it is pointless to explore
        # other possibilities
        if value:
            reservation = value
            break
        # fi
        
        reservation = reservation or value
    # end 

    # FIXME: How sane is this approach?
    # No reservation information is known about person. Pretend nothing
    # happend.
    if reservation is None:
        return
    # fi

    person.populate_reservert(reservation)
    person.write_db()
# end import_reservasjon



def import_gjest(pxml, person, stedkode, constants):
    """
    Import guest information about PERSON/PXML.
    """
    
    for element in pxml["gjest"]:
        if not find_stedkode(stedkode,
                             element["fakultetnr"],
                             element["instituttnr"],
                             element["gruppenr"]):
            continue
        # fi

        try:
            code = GjestetypeKode(element["gjestetypekode"])
            code = int(code)
        except Cerebrum.Errors.NotFoundError:
            logger.error("Aiee! Unknown code string %s (GjestetypeKode)",
                         element["gjestetypekode"])
            continue
        # yrt

        
        person.populate_gjest(stedkode.entity_id,
                              element["dato_fra"],
                              code,
                              element["dato_til"])
    # od
    person.write_db()
    
    # No commit here just yet
    if len(pxml["gjest"]) > 0:
        logger.debug("%s -> %d", person.entity_id, len(pxml["gjest"]))
    # fi
# end import_gjest



def import_bilag(pxml, person, stedkode, constants):
    """
    Import bilag information about PERSON/PXML.
    """

    for element in pxml["bilag"]:
        if not find_stedkode(stedkode, 
                             element["fakultetnr_kontering"],
                             element["instituttnr_kontering"],
                             element["gruppenr_kontering"]):
            continue 
        # fi
        
        person.populate_bilag(stedkode.entity_id,
                              element["dato_oppgjor"])
    # od
    person.write_db()
    
    # No commit here just yet
    if len(pxml["bilag"]) > 0:
        logger.debug("%s -> %d", person.entity_id, len(pxml["bilag"]))
    # fi
# end import_bilag



def import_tilsetting(pxml, person, stedkode, constants):
    """
    Import tilsetting information about PERSON/PXML.
    """

    for element in pxml["tils"]:
        #
        # Each element is dictionary with information on tilsetting and
        # permisjon
        tilsetting = element["tilsetting"]
        permisjon = element["permisjon"]
        
        if not find_stedkode(stedkode, 
                             tilsetting["fakultetnr_utgift"],
                             tilsetting["instituttnr_utgift"],
                             tilsetting["gruppenr_utgift"]):
            continue 
        # fi

        try:
            code = StillingsKode(tilsetting["stillingkodenr_beregnet_sist"])
            code = int(code)
        except Cerebrum.Errors.NotFoundError:
            logger.error("Aiee! Unknown code string %s (StillingsKode)",
                         tilsetting["stillingkodenr_beregnet_sist"])
            continue
        # yrt

        person.populate_tilsetting(tilsetting["tilsnr"],
                                   stedkode.entity_id,
                                   code,
                                   tilsetting["dato_fra"],
                                   tilsetting["dato_til"],
                                   float(tilsetting["prosent_tilsetting"]))
        for p in permisjon:
            logger.info("Permisjon for %s", person.entity_id)
            import_permisjon(tilsetting, p, person)
        # od

    # od
    person.write_db()

    if len(pxml["tils"]) > 0:
        logger.debug("%s -> %d", person.entity_id, len(pxml["tils"]))
    # fi
# end import_tilsetting



def import_permisjon(tilsetting, permisjon, person):
    """
    Register a PERMISJON for TILSETTING for PERSON.
    """

    try:
        code = int(PermisjonsKode(permisjon["permarsakkode"]))
        lonstatuskode = int(Lonnsstatus(permisjon["lonstatuskode"])) 
        
        person.populate_permisjon(tilsetting["tilsnr"],
                                  code,
                                  permisjon["dato_fra"],
                                  permisjon["dato_til"],
                                  float(permisjon["prosent_permisjon"]),
                                  lonstatuskode)
    except Cerebrum.Errors.NotFoundError:
        logger.error("Aiee! Unknown code string ")
    # yrt
# end import_permisjon



def import_rolle(pxml, person, stedkode, constants):
    """
    Register roles for PXML/PERSON
    """

    for element in pxml["rolle"]:

        if not find_stedkode(stedkode,
                             element["fakultetnr"],
                             element["instituttnr"],
                             element["gruppenr"]):
            continue
        # fi

        try:
            code = int(RolleKode(element["ansvarsrollekode"]))
        except Cerebrum.Errors.NotFoundError:
            logger.error("Aiee! Unknown code string %s (RolleKode)",
                         element["ansvarsrollekode"])
            continue
        # yrt
        
        person.populate_rolle(stedkode.entity_id,
                              code,
                              element["dato_fra"],
                              element["dato_til"])
    # od
    person.write_db()

    if len(pxml["rolle"]) > 0:
        logger.debug("%s -> %d", person.entity_id, len(pxml["rolle"]))
    # fi
# end import_rolle

    

def import_person(pxml, person, stedkode, constants, import_list):
    """
    Synchronize Cerebrum with information on person represented by
    PXML. This object is a dictionary containing all intereseting
    information from a <person> element in the xml data source.
    """

    attrs = pxml["attrs"]
    no_ssn = "%02d%02d%02d" % (int(attrs["fodtdag"]),
                               int(attrs["fodtmnd"]),
                               int(attrs["fodtar"]))
    no_ssn = no_ssn + attrs["personnr"].zfill(5)

    try:
        person.clear()
        person.find_by_external_id(constants.externalid_fodselsnr,
                                   no_ssn,
                                   constants.system_lt)
    except Cerebrum.Errors.NotFoundError:
        logger.error("No such person: %s", no_ssn)
        return
    # yrt


    for import_name in import_list:
        function = globals()[import_name]
        function(pxml, person, stedkode, constants)
    # od
# end import_person



def usage():
    logger.info("""

This script loads information from LT into the LT-specific extension to
UiO's Cerebrum installation.

The following options are supported:
-t, --tilsetting	-- import information on employments (tilsetting)
-b, --bilag		-- import information on temps (bilag)
-g, --gjest 		-- import information on guests (gjest)
-r, --reservasjon	-- import information on reservations (reservasjon)
-l, --rolle		-- import information on roles (rolle)
-h, --help		-- display this message
-p, --person-file [file] -- use [file] as data source
-v, --verbose           -- increase logger verbosity level
""")
# end usage



def main(argv):
    global logger
    logging.fileConfig(cereconf.LOGGING_CONFIGFILE)
    logger = logging.getLogger("console")
    logger.setLevel(logging.INFO)
    logger.info("test run")

    try:
        options, rest = getopt.getopt(argv,
                                      "tbgrlhp:v",
                                      ["tilsetting",
                                       "bilag",
                                       "gjest",
                                       "reservasjon",
                                       "rolle",
                                       "help",
                                       "person-file=",
                                       "verbose"])
    except getopt.GetoptError:
        usage()
        sys.exit(1)
    # yrt

    imports = []
    person_file = None
    # Why does this look _so_ ugly?
    for option, value in options:
        if option in ("-t", "--tilsetting"):
            imports.append("import_tilsetting")
        elif option in ("-b", "--bilag"):
            imports.append("import_bilag")
        elif option in ("-g", "--gjest"):
            imports.append("import_gjest")
        elif option in ("-r", "--reservasjon"):
            imports.append("import_reservasjon")
        elif option in ("-l", "--rolle"):
            imports.append("import_rolle")
        elif option in ("-h", "--help"):
            usage()
            sys.exit(2)
        elif option in ("-p", "--person-file"):
            person_file = value
        elif option in ("-v", "--verbose"):
            logger.setLevel(logging.DEBUG)
        # fi
    # od

    # We want reservasjon to be after tilsetting and bilag
    # This is the simplest way of doing it :)
    if "import_reservasjon" in imports:
        index = imports.index("import_reservasjon")
        imports[-1], imports[index] = imports[index], imports[-1]
    # fi

    logger.info("Imports (in order): %s", imports)

    db = Factory.get("Database")()
    person = Factory.get("Person")(db) 
    const = Factory.get("Constants")(db)
    stedkode = Stedkode.Stedkode(db)

    func = lambda x: import_person(x, person, stedkode, const, imports)
    p = PersonParser(person_file, func)
    db.commit()
# end 


main(sys.argv[1:])
