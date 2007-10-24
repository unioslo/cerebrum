#! python
# -*- coding: iso-8859-1 -*-

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
Landnavn            Country. Cerebrum has no country information, tries to extract from zip
Adrmatekode         empty
Registergruppe      This version, only POLS-TILS
Registerkode        empty
Adrtypekode         EKST || INT for addresses outside/inside campus.
"""

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum import Errors

db = Factory.get("Database")()
consts = Factory.get("Constants")(db)

def get_name(person):
    """Return a name.
    The returned name should be on the form:
    Last, First
    And be at most 40 characters wide.
    """
    try:
        last = person.get_name(consts.system_sap, consts.name_last)
        first = person.get_name(consts.system_sap, consts.name_first)
    except Errors.NotFoundError:
        try:
            last = person.get_name(consts.system_lt, consts.name_last)
            first = person.get_name(consts.system_lt, consts.name_first)
        except Errors.NotFoundError:
            # If everything is correct, this is the last option.
            # XXX: Should we consider the possibility of the person being a student as well?
            return person.get_name(consts.system_manual, consts.name_full)
    full = "%s, %s" % (last, first)
    return full[:40]

def get_num_copies(*args):
    """
    For now, returns the string ' 1'
    Field size: 2
    """
    return '1 '

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
    """
    try:
        # Priority one: post from SAP
        address = person.get_entity_address(consts.system_sap, consts.address_post)[0]
    except IndexError:
        try:
        # Priority two: priv from SAP
            address = person.get_entity_address(consts.system_sap, consts.address_post_private)[0]
        except IndexError:
            # SAP doesn't have the wanted info, try other means.
            rows = person.list_entity_addresses(address_type=consts.address_post)
            if not rows:
                rows = person.list_entity_addresses(address_type=consts.address_post_private)
            if rows:
                address=rows[0]
            else:
                return ('','','','','')
            
    if address['address_text']:
        lines = address['address_text'].split('\n')
    else:
        lines = ()
    if len(lines) > 2: # XXX: This doesn't seem to be a problem
        import sys
        print >>sys.stderr, "Address:\n\t" + "\n\t".join(lines)
        line1, line2 = lines[:2]
    elif len(lines) == 1:
        line1, line2 = lines[0], ''
    elif len(lines) < 1:
        line1 = line2 = ''
    else:
        line1, line2 = lines

    if address['p_o_box']:
        line1 = 'Postboks ' + address['p_o_box'] + line1

    # Non-norwegians seem to be registered with Zip = None, and foreign zip in city
    Zip = address['postal_number'] or ""
    if len(Zip) < 4 and Zip.isdigit(): # Fix erroneous zip codes.
        Zip = '0' + Zip
    city = address['city']

    # The country field seems unused in the database.
    country = address['country'] or 'NORGE'
    if not Zip and city.find('-') > -1:
        country = city[:city.find('-')]
    return (line1[:40], line2[:40], Zip[:4], city[:16], country[:20])

def get_feed_code(person):
    """
    I seriously don't know what this is
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
    return 'INT' for PO Boxes on Blindern, or 'EKST' for other.
    PO Boxes on Blindern should:
    * Have 'Blindern' somewhere in the address
    * Have a four digit number in the address
    Ex: 'EKST'
    field size: 4
    """
    if ad[0].find('Blindern')>-1:
        for i in ad[0].split(' '):
            if i.isdigit() and len(i) == 4:
                return "INT"
    return 'EKST'

def main():
    import sys
    person = Factory.get("Person")(db)

    # query copied from person.list_affiliations, but we only need
    # distinct person_id's.
    query = """SELECT DISTINCT person_id
               FROM [:table schema=cerebrum name=person_affiliation_source]
               WHERE affiliation = %d and (deleted_date IS NULL OR deleted_date > [:now]);""" % \
    consts.affiliation_ansatt
    
    #for p in person.list_affiliations(affiliation=consts.affiliation_ansatt):
    for p in db.query(query, fetchall = True):
        person.clear()
        person.find(p[0])
        ad = get_address(person)
        print "%-40s%-2s" % (get_name(person), get_num_copies(person)) + \
              "%-40s%-40s%-4s%-16s%-20s" % ad + \
              "%-4s%-10s%-2s%-4s" % (get_feed_code(person), get_register_group(person),
                                     get_register_code(person), get_address_type_code(person, ad))

if __name__ == '__main__':
    main()
