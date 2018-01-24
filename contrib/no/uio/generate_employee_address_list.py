#! python
# -*- coding: utf-8 -*-
#
# Copyright 2007 University of Oslo, Norway
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
Create address list with data from Cerebrum.

Dump a file with one person per line. Each line has following data:
Feltnavn         Feltlengde  Eksempel
Navn                A40      Oftedal, Lars Inge
Antalleksemplarer   N2       1
Adresselinje1       A40      USIT
Adresselinje2       A40      Pb. 1059, Blindern
Poststednr          A4       0316
Poststednavn        A16      OSLO
Landnavn            A20      NORGE
Adrmatekode         A4
Registergruppe      A10      POLS-TILS
Registerkode        A2
Adrtypekode         A4       EKST

Description:
Navn:               Person's name
Antalleksemplarer   The number 1, to be extended
Adresselinje1
Adresselinje2
Poststednr          norwegian zip code. Empty for foreign addresses.
Landnavn            Country. Cerebrum has no country information.
Adrmatekode         empty
Registergruppe      This version, only POLS-TILS
Registerkode        empty
Adrtypekode         empty
"""

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum import Errors

db = Factory.get("Database")()
constants = Factory.get("Constants")(db)
logger = Factory.get_logger("console")

def get_name(person):
    """Return person's name.
    The returned name should be on the form:
    Last, First
    And be at most 40 characters wide.
    """
    try:
        logger.debug("Fetching last name from cache")
        last = person.get_name(constants.system_cached, constants.name_last)
    except Errors.NotFoundError:
        try:
            logger.debug("... last not found. Trying SAP")
            last = person.get_name(constants.system_sap, constants.name_last)
        except Errors.NotFoundError:
            logger.warning("Person entity_id=%d has no last name in SAP" % person.entity_id)
            last = ''
    try:
        logger.debug("Fetching first name from cache")
        first = person.get_name(constants.system_cached, constants.name_first)
    except Errors.NotFoundError:
        try:
            logger.debug("... first not found. Trying SAP")
            first = person.get_name(constants.system_sap, constants.name_first)
        except Errors.NotFoundError:
            if last:
                logger.warning("Person entity_id=%d has no first name in SAP" % person.entity_id)
                return last
            logger.warning("Person entity_id=%d has no name in SAP, ignoring" % person.entity_id)
            return None
    if last:
        full = "%s, %s" % (last, first)
    else:
        full = first
    return full[:40]

def get_num_copies(*args):
    """
    For now, returns the string ' 1'
    Field size: 2
    """
    return ' 1'

def get_address(person):
    """
    Return the physical address of a person.
    Will try
    * physical workplace
    * home address
    in this order.
    The address is a sequence with each component on each line.
    Field size:
    * Line1: 40
    * Line2: 40
    * Zip : 4
    * City: 16
    * Country: 20
    If the address doesn't exist, return None
    """
    try:
        # Priority one: post from SAP
        logger.debug("Fetching address from SAP")
        address = person.get_entity_address(constants.system_sap, constants.address_post)[0]
    except IndexError:
        try:
        # Priority two: priv from SAP
            logger.debug("Fetching private address from SAP")
            address = person.get_entity_address(constants.system_sap, constants.address_post_private)[0]
        except IndexError:
            # SAP doesn't have the wanted info.
            logger.warning("Person %d has no address in SAP" % person.entity_id)
            return None
            
    if address['address_text']:
        lines = address['address_text'].split('\n')
    else:
        lines = ()
    if len(lines) > 2: # TBD: This doesn't seem to be a problem
        logger.warning("Person %d has more than two address lines" % person.entity_id)
        line1, line2 = lines[:2]
    elif len(lines) == 1:
        line1, line2 = lines[0], ''
    elif len(lines) < 1:
        line1 = line2 = ''
    else:
        line1, line2 = lines

    if address['p_o_box']:
        # People tend to be registered with the PO box number encoded in the address in SAP
        line1 = 'Pb ' + address['p_o_box'] + ' ' + line1

    # Non-norwegians seem to be registered with Zip = None, and foreign zip encoded in city
    Zip = address['postal_number'] or ""
    if len(Zip) < 4 and Zip.isdigit(): # Fix erroneous zip codes.
        logger.warning("Person %d has zip code %s" % (person.entity_id, Zip))
        Zip = '0' + Zip

    # TBD: Should we check the validity of zip codes?

    city = address['city'] or ""

    # The country field seems unused in the database.
    # TBD: Fix this when SAP import imports country
    #country = address['country'] or ''
    country = ''

    return {'address1': line1[:40], 
            'address2': line2[:40],
            'address': lines,
            'zip':     Zip[:4], 
            'city':    city[:16], 
            'country': country[:20]
            }

def get_feed_code(person):
    """
    Return ''
    Field size: 4
    """
    return ''

def get_register_group(person):
    """
    Return the register group of this person.
    ex: 'POLS-TILS'
    Field size: 10
    """
    return 'POLS-TILS'

def get_register_code(person):
    """
    Field size: 2
    """
    return ''

def get_address_type_code(person, ad):
    """
    Return ''
    field size: 4
    """
    return ''

def compare_addresses(a, b):
    """
    Return -1, 0, 1 for comparison between person_information dicts as seen below.
    Both arguments should be dicts following that scheme.
    Priority:
    * country
    * zip/city
    * address1
    """
    value = cmp(a['country'], b['country'])
    if value: return value
    value = cmp(a['zip'], b['zip'])
    if value: return value
    value = cmp(a['city'], b['city'])
    if value: return value
    value = cmp(a['address1'], b['address1'])
    if value: return value
    return cmp(a['name'], b['name'])

def main(outfile):
    person = Factory.get("Person")(db)

    logger.debug("Getting all persons with affiliation ansatt")
    result = person.list_affiliations(affiliation=constants.affiliation_ansatt, 
            source_system=constants.system_sap)

    persons = set()
    for i in result:
        if i['status'] == constants.affiliation_status_ansatt_bil:
            continue
        if i['status'] == constants.affiliation_status_ansatt_ltreg:
            logger.warn("Person %s has %s", i[0], constants.affiliation_status_ansatt_ltreg)
            continue
        persons.add(i[0])

    addresses=[]
    for p in persons:
        person.clear()
        logger.debug("Finding person id %d" % p)
        person.find(p)
        name = get_name(person)
        # Persons without name or address should be skipped
        if not name:
            continue
        person_information = get_address(person)
        if not person_information:
            continue
        person_information.update({
            'name': name,
            'copies': get_num_copies(person),
            'feed_code': get_feed_code(person),
            'register_group': get_register_group(person),
            'register_code': get_register_code(person),
            'type_code': get_address_type_code(person, person_information)
            })
        addresses.append(person_information)
    addresses.sort(compare_addresses)
    for i in addresses:
        for j, k in i.items():
            if isinstance(k, str):
                i[j] = k.replace('\t', ' ')
            else:
                i[j] = '\t'.join([x.replace('\t', ' ') for x in k])
        line = "%(name)s\t%(zip)s\t%(city)s\t%(address)s" % i
        #print >>outfile, "%(name)-40s%(copies)-2s%(address1)-40s" \
        #        "%(address2)-40s%(zip)-4s%(city)-16s%(country)-20s" \
        #        "%(feed_code)-4s%(register_group)-10s%(register_code)-2s%(type_code)-4s" \
        #        % i
        outfile.write(line)
        outfile.write('\n')
    outfile.flush()

    #print >>outfile, "%-40s%-2s" % (name, get_num_copies(person)) + \
    #                 "%-40s%-40s%-4s%-16s%-20s" % address + \
    #                 "%-4s%-10s%-2s%-4s" % (get_feed_code(person), get_register_group(person),
    #                                        get_register_code(person), get_address_type_code(person, ad))

def usage(prog):
    print """%s [-f filename]
    Writes to filename if given, else standard output
""" % prog

if __name__ == '__main__':
    import sys, getopt
    opts = getopt.getopt(sys.argv[1:], "hf:")
    file = sys.stdout
    for i in opts[0]:
        if i[0] == '-f':
            logger.debug("Using %s for output" % i[1])
            file = open(i[1], 'w')
        if i[0] == '-h':
            usage(sys.argv[0])
            sys.exit(0)
    main(file)

