#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

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

"""This script loads the information from various HR DBs into Cerebrum.

Specifically, an XML input[1] with information about people, employments,
contact information, etc. is processed and stored in a suitable form in
Cerebrum. Additionally, based on the employment information, we assign
affiliations.

[1] Currently two input sources are supported -- LT and SAP. They use
different XML DTDs, but the interface to them is uniform (through
modules.xmlutils.*)
"""

import cerebrum_path
import cereconf

import sys
import getopt

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.xmlutils.system2parser import system2parser
from Cerebrum.modules.xmlutils.object2cerebrum import XML2Cerebrum
from Cerebrum.modules.xmlutils.xml2object import DataEmployment, DataOU, DataAddress
from Cerebrum.modules.xmlutils.xml2object import SkippingIterator
from Cerebrum.modules.no import fodselsnr

db = Factory.get('Database')()
db.cl_init(change_program='import_HR')
const = Factory.get('Constants')(db)
group = Factory.get("Group")(db)
person = Factory.get("Person")(db)
logger = Factory.get_logger("cronjob")





ou_cache = {}
def get_sko((fakultet, institutt, gruppe), system):
    """Lookup the information on a sko, and cache it for later.

    :Parameters:
      fakultet, institutt, gruppe : basestring or number
        sko designation.
      system : an AuthoritativeSystem instance (or an int)
        the source system for OU address information.

    :Returns:
      A dictionary with entity_id, fax, and addresses.
    """
    
    fakultet, institutt, gruppe = int(fakultet), int(institutt), int(gruppe)
    stedkode = (fakultet, institutt, gruppe)
    system = int(system)
    
    if not ou_cache.has_key((stedkode, system)):
        ou = Factory.get('OU')(db)
        try:
            ou.find_stedkode(fakultet, institutt, gruppe,
                             institusjon=cereconf.DEFAULT_INSTITUSJONSNR)
            addr_street = ou.get_entity_address(source=system,
                                                type=const.address_street)
            if len(addr_street) > 0:
                addr_street = addr_street[0]
                address_text = addr_street['address_text']
                if not addr_street['country']:
                    address_text = "\n".join(
                        filter(None, (ou.short_name, address_text)))
                addr_street = {'address_text': address_text,
                               'p_o_box': addr_street['p_o_box'],
                               'postal_number': addr_street['postal_number'],
                               'city': addr_street['city'],
                               'country': addr_street['country']}
            else:
                addr_street = None
            addr_post = ou.get_entity_address(source=system,
                                                type=const.address_post)
            if len(addr_post) > 0:
                addr_post = addr_post[0]
                addr_post = {'address_text': addr_post['address_text'],
                             'p_o_box': addr_post['p_o_box'],
                             'postal_number': addr_post['postal_number'],
                             'city': addr_post['city'],
                             'country': addr_post['country']}
            else:
                addr_post = None
            fax = ou.get_contact_info(source=system,
                                      type=const.contact_fax)
            if len(fax) > 0:
                fax = fax[0]['contact_value']
            else:
                fax = None

            ou_cache[stedkode, system] = {'id': int(ou.ou_id),
                                          'fax': fax,
                                          'addr_street': addr_street,
                                          'addr_post': addr_post}
            ou_cache[int(ou.ou_id)] = ou_cache[stedkode, system]
        except Errors.NotFoundError:
            logger.info("bad stedkode: %s" % str(stedkode))
            ou_cache[stedkode, system] = None

    return ou_cache[stedkode, system]
# end get_sko



def determine_affiliations(xmlperson, source_system):
    """Determine affiliations for person p_id/xmlperson in order of significance.

    :Parameters:
      xmlperson : instance of xmlutils.HRDataPerson
        Representation of XML-data for a person
      source_system : instance of AuthoritativeSystem (or a number)
        Source system for OU lookup.

    :Returns:
      The affiliations are collected in ret, where keys are:
    
      'ou_id:affiliation'

      ... and values are

      (ou_id, affiliation, affiliation_status)
    """

    def str_pid():
        """For debugging purposes only."""
        return str(list(xmlperson.iterids()))
    # str_id

    ret = {}

    kind2affstat = { DataEmployment.KATEGORI_OEVRIG :
                         const.affiliation_status_ansatt_tekadm,
                     DataEmployment.KATEGORI_VITENSKAPLIG :
                         const.affiliation_status_ansatt_vit, }
    gjest2affstat = {'EMERITUS': const.affiliation_tilknyttet_emeritus,
                     'PCVAKT': const.affiliation_tilknyttet_pcvakt,
                     'UNIRAND': const.affiliation_tilknyttet_unirand,
                     'GRP-LÆRER': const.affiliation_tilknyttet_grlaerer,
                     'EF-STIP': const.affiliation_tilknyttet_ekst_stip,
                     'BILAGSLØN': const.affiliation_tilknyttet_bilag,
                     'EF-FORSKER': const.affiliation_tilknyttet_ekst_forsker,
                     'SENIORFORS': const.affiliation_tilknyttet_ekst_forsker,
                     'GJ-FORSKER': const.affiliation_tilknyttet_gjesteforsker,
                     'SIVILARB': const.affiliation_tilknyttet_sivilarbeider,
                     'EKST. PART': const.affiliation_tilknyttet_ekst_partner,
                     'EKST-PART': const.affiliation_tilknyttet_ekst_partner,
                     'ASSOSIERT':const.affiliation_tilknyttet_assosiert_person,
                     'ST-POL FRI': const.affiliation_tilknyttet_studpol,
                     'ST-POL UTV': const.affiliation_tilknyttet_studpol,
                     'ST-POL-UTV': const.affiliation_tilknyttet_studpol,
                     'ST-ORG FRI': const.affiliation_tilknyttet_studorg,
                     'ST-ORG UTV': const.affiliation_tilknyttet_studorg,

                     # IVR 2007-07-11 These should be ignored
                     # eventually, according to baardj
                     'REGANSV': const.affiliation_tilknyttet_frida_reg,
                     'REG-ANSV': const.affiliation_tilknyttet_frida_reg,
                     'EKST. KONS': const.affiliation_tilknyttet_ekst_partner,
                     'EKST-KONS': const.affiliation_tilknyttet_ekst_partner,
                     }

    #
    # #1 -- Tilsettinger
    tils_types = (DataEmployment.HOVEDSTILLING, DataEmployment.BISTILLING)
    # we look at active employments with OUs only
    tilsettinger = filter(lambda x: x.kind in tils_types and
                                    x.is_active() and
                                    x.place,
                          xmlperson.iteremployment())
    title = None
    max_so_far = -1
    for t in tilsettinger:
        assert t.place[0] == DataOU.NO_SKO
        place = get_sko(t.place[1], source_system)
        if place is None:
            continue

        if t.percentage > max_so_far:
            max_so_far = t.percentage
            title = t.title

        if t.category not in kind2affstat:
            logger.warn("Unknown category %s for %s", t.category, str_pid())
            continue

        aff_stat = kind2affstat[t.category]
        k = "%s:%s" % (place["id"], int(const.affiliation_ansatt))
        if not ret.has_key(k):
            ret[k] = (place["id"], const.affiliation_ansatt, aff_stat)
    
    #
    # #2 -- Bilagslønnede
    bilag = filter(lambda x: x.kind == DataEmployment.BILAG and
                             x.place,
                   xmlperson.iteremployment())
    for b in bilag:
        assert b.place[0] == DataOU.NO_SKO
        place = get_sko(b.place[1], source_system)
        if place is None:
            continue
            
        k = "%s:%s" % (place["id"], int(const.affiliation_ansatt))
        if not ret.has_key(k):
            ret[k] = (place["id"], const.affiliation_ansatt, 
                      const.affiliation_status_ansatt_bil)

    #
    # #3 -- Gjester
    gjest = filter(lambda x: x.kind == DataEmployment.GJEST and
                             x.is_active() and
                             x.place,
                   xmlperson.iteremployment())
    for g in gjest:
        assert g.place[0] == DataOU.NO_SKO
        if g.place[1] is None:
            logger.error("Defective guest entry for %s (missing sko)",
                         str_pid())
            continue
    
        place = get_sko(g.place[1], source_system)
        if place is None:
            continue
    
        aff_stat = None
        # Temporary fix until SAP-HR goes live@UiO (employees at UiO are
        # registered as guests, but have to be recognized as employees
        # in LDAP etc). We should be able to remove this in august 2006
        if g.code == 'POLS-ANSAT':
            aff_stat = const.affiliation_status_ansatt_ltreg
            k = "%s:%s" % (place["id"], int(const.affiliation_ansatt))
            if not ret.has_key(k):
                ret[k] = place["id"], const.affiliation_ansatt, aff_stat
            continue
        # endhack
        elif g.code in gjest2affstat:
            aff_stat = gjest2affstat[g.code]
        # Some known gjestetypekode can't be maped to any known affiliations
        # at the moment. Group defined above in head.  
        elif g.code == 'IKKE ANGIT':
            logger.info("No registrations of gjestetypekode: %s" % g.code)
            continue
        else:
            logger.info("Unknown gjestetypekode %s for person %s",
                        g.code, str_pid())
            continue
    
        k = "%s:%s" % (place["id"], int(const.affiliation_tilknyttet))
        if not ret.has_key(k):
            ret[k] = place["id"], const.affiliation_tilknyttet, aff_stat
    
    return ret, title
# end determine_affiliations


def make_reservation(to_be_reserved, p_id, group):
    """Register reservation for a person.

    When a person is marked as reserved in the XML data, we register him/her
    as a member of a special group in Cerebrum. This function performs this
    registration (or removes it, if the person no longer has such a
    reservation).

    :Parameters:
      to_be_reserved : bool
        whether to make reservation (True) or remove it (False)
      p_id : int
        person_id
      group : Group instance
        Special group for reservations.
    """
    
    op = const.group_memberop_union

    if to_be_reserved and not group.has_member(p_id, const.entity_person, op):
        group.add_member(p_id, const.entity_person, op)
        group.write_db()
    elif not to_be_reserved and group.has_member(p_id, const.entity_person, op):
        group.remove_member(p_id, op)
        group.write_db()
# end make_reservation


def consistent_ids(xmlperson):
    """Check that person IDs on file point to the same entity in Cerebrum.

    No matter how many IDs there are on file, they should all point to the
    same entity in Cerebrum. Ideally a situation where, e.g. NO_SSN and SAP_NR
    lead to two different person entities in Cerebrum cannot
    exist. Nevertheless, this may happen, and we need to be prepared to trap
    such situations.

    This check does not superseed the checks in fnr_update.py.

    :Parameters:
      xmlperson : an instance of xml2object.HRDataPerson

    :Returns:
      True, if all IDs for xmlperson lead to the same entity_id in
      Cerebrum. Otherwise False.
    """

    file2db = {xmlperson.NO_SSN: const.externalid_fodselsnr,}
    if hasattr(xmlperson, "SAP_NR"):
        file2db[xmlperson.SAP_NR] = const.externalid_sap_ansattnr

    people = list()
    for kind, id_on_file in xmlperson.iterids():

        try:
            person.clear()
            person.find_by_external_id(file2db[kind], id_on_file)
            if int(person.entity_id) not in people:
                people.append(int(person.entity_id))
        except Errors.NotFoundError:
            # A new ID means that this person has not been registered with
            # this external id before. This is not an error.
            pass
        except Errors.TooManyRowsError:
            logger.error("Found more than one person with ID=%s", id_on_file)
            return False

    # Ok, how many IDs are there?
    if len(people) > 1:
        logger.error("%d people in Cerebrum (entity_ids: %s) share %s from file",
                     len(people), people, list(xmlperson.iterids()))
        return False

    return True
# end consistent_ids



def parse_data(parser, source_system, group, gen_groups, old_affs):
    """Process all people data available.

    For each person extracted from XML, register the changes in Cerebrum. 
    We try to treat all sources uniformly here.

    :Parameters:
      parser : instance of xmlutils.XMLDataGetter
        Parser suitable for the given source XML file.
      source_system : instance of AuthoritativeSystem (or int)
        Source system for which the data is to be registered.
      group : instance of Group associated with group for reservations
        For each person, his/her reservations for online directory publishing
        are expressed as membership in this group.
      old_affs : dictionary
        Contains affiliations for every person currently present in
        Cerebrum. Used to clean up old affiliations (affiliations which are no
        longer present in the employee data)
    """

    logger.info("processing file %s for system %s", parser, source_system)

    xml2db = XML2Cerebrum(db, source_system)
    it = parser.iter_persons()

    for xmlperson in SkippingIterator(it, logger):
        logger.debug("Loading next person: %s", list(xmlperson.iterids()))
        affiliations, work_title = determine_affiliations(xmlperson,
                                                          source_system)

        # If the person has primary_ou set, we set the besok/post
        # address in the xmlperson unless it is already set
        if hasattr(xmlperson, 'primary_ou'):
            sko_dta = get_sko(xmlperson.primary_ou[1:], source_system)
            for src_key, kind in (
                ('addr_street', DataAddress.ADDRESS_BESOK),
                ('addr_post', DataAddress.ADDRESS_POST)):
                if xmlperson.get_address(kind) is not None:
                    continue
                if not sko_dta:
                    continue
                addr = sko_dta[src_key]
                if addr is None:
                    continue
                xmlperson.add_address(
                    DataAddress(kind = kind,
                                street = addr['address_text'],
                                zip = addr['postal_number'] or '',
                                city = addr['city'] or '',
                                country = addr['country'] or ''))
        if not consistent_ids(xmlperson):
            logger.error("person with IDs %s points to several entities in Cerebrum",
                         list(xmlperson.iterids()))
            continue
                
        status, p_id = xml2db.store_person(xmlperson, affiliations, work_title)

        if gen_groups == 1:
            make_reservation(xmlperson.reserved, p_id, group)

        # Now we mark current affiliations as valid (in case deletion is
        # requested later)
        if old_affs:
            for key in affiliations:
                tmp = "%s:%s" % (p_id, key)
                if tmp in old_affs:
                    old_affs[tmp] = False

        logger.info("**** %s (%s) %s ****", p_id, dict(xmlperson.iterids()),
                    status)
# end parse_data



def clean_old_affiliations(source_system, aff_set):
    """Remove affiliations which have no basis in the data set imported in
    this run.

    While importing people information, we mark valid affiliations. All affs
    that have not been marked are no longer valid.

    :Parameters:
      source_system : an instance of AuthoritativeSystem (or an int)
        Source system for the data set we are importing
      aff_set : a dictionary
        see parse_data
    """

    for key, status in aff_set.items():
        if status:
            entity_id, ou_id, aff = key.split(":")
            person.clear()
            person.entity_id = int(entity_id)
            person.delete_affiliation(ou_id, aff, source_system)
# end clean_old_affiliations



def load_old_affiliations(source_system):
    """Load all affiliations from Cerebrum registered to source_system.

    :Parameters:
      source_system : an instance of AuthoritativeSystem (or an int)
        Source system for the data set we are importing
    :Returns:
      A dictionary, mapping keys to bool, where keys look like s1:s2:s3, and
      s1 is person_id, s2 is ou_id and s3 is the affiliation (int).
    """

    affi_set = dict()
    for row in person.list_affiliations(source_system=source_system):
        key = "%s:%s:%s" % (row["person_id"], row["ou_id"], row["affiliation"])
        affi_set[key] = True

    return affi_set
# end load_old_affiliations



def locate_and_build((group_name, group_desc)):
    """Locate a group named groupname in Cerebrum and build it if necessary.

    :Parameters:
      group_name : string
      group_desc : string
        Group description, in case the group needs to be built, the name for
        the group.
    :Returns:
      Group instance that is associated with group_name.
    """

    try:
        group.find_by_name(group_name)
    except:
        group.clear()
        account = Factory.get("Account")(db)
        account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        group.populate(account.entity_id, const.group_visibility_internal,
                       group_name, group_desc)
        group.write_db()

    return group
# end locate_and_build



def usage(exitcode=0):
    print """Usage: %s -s system:filename [-g] [-d] [-r]""" % sys.argv[0]
    sys.exit(exitcode)
# end usage


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "s:gdr",
                                   ["source-spec=",
                                    "group",
                                    "include_delete",
                                    "dryrun"])
    except getopt.GetoptError, val:
        print val
        usage(1)

    gen_groups = 0
    verbose = 0
    sources = list()
    include_del = False
    dryrun = False

    for option, value in opts:
        if option in ("-s", "--source-spec"):
            sysname, personfile = value.split(":")
            sources.append((sysname, personfile))
        elif option in ("-g", "--group"):
            gen_groups = 1
        elif option in ("-d", "--include_delete"):
            include_del = True
        elif option in ("-r", "--dryrun"):
            dryrun = True

    system2group = {"system_lt":
                    ("LT-elektroniske-reservasjoner",
                     "Internal group for people from LT which will not be shown online"),
                    "system_sap":
                    ("SAP-elektroniske-reservasjoner",
                     "Internal group for people from SAP which will not be shown online"), }

    logger.debug("sources is %s", sources)
    for system_name, filename in sources:
        # Locate the appropriate Cerebrum constant
        source_system = getattr(const, system_name)
        parser = system2parser(system_name)
        
        # Locate the proper reservation group
        group = locate_and_build(system2group[system_name])

        # Load old affiliations
        cerebrum_affs = dict()
        if include_del:
            cerebrum_affs = load_old_affiliations(source_system)

        # Read in the file, and register the information in cerebrum
        if filename is not None:
            parse_data(parser(filename, False),
                       source_system,
                       group,
                       gen_groups,
                       include_del and cerebrum_affs or dict())

        if include_del:
            clean_old_affiliations(source_system, cerebrum_affs)
        
        if dryrun:
            db.rollback()
            logger.info("All changes rolled back")
        else:
            db.commit()
            logger.info("All changes committed")
# end main





if __name__ == "__main__":
    main()

