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
try:
    set()
except NameError:
    from Cerebrum.extlib.sets import Set as set


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
    system2perspective = {int(const.system_lt): const.perspective_lt,
                          int(const.system_sap): const.perspective_sap,}
    
    if not ou_cache.has_key((stedkode, system)):
        ou = Factory.get('OU')(db)
        try:
            ou.find_stedkode(fakultet, institutt, gruppe,
                             institusjon=cereconf.DEFAULT_INSTITUSJONSNR)
            # Check that OU is present in the OU-hierarchy. Basically, it is
            # the only way to make sure that the OU referred to originated
            # from system.
            ou.get_parent(system2perspective[system])

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



def determine_traits(xmlperson, source_system):
    """Determine traits to assign to this person.

    cereconf.AFFILIATE_TRAITS decides which traits are assigned to each
    person, based on the information obtained from the authoritative system
    data.

    @type xmlperson: xml2object.DataHRPerson instance
    @param xmlperson:
      Next person to process

    @type source_system: ??
    @param source_system:
      Source system where the data originated from (useful for OU-lookup).

    @rtype: set of triples
    @return:
      A sequence of traits to adorn the corresponding cerebrum person object
      with. If no traits could be assigned, an empty sequence is returned. The
      only guarantee made about the sequence is that it is without duplicates
      and it is iterable.

      The items in the sequence are triples -- (trait, ou_id, description),
      where trait is the trait itself (int or constant), ou_id is the
      associated ou_id (traits collected here are always tied to an OU) and
      description is a string to make trait assignment more human-friendly.
    """

    if not hasattr(cereconf, "AFFILIATE_TRAITS"):
        return set()

    # emp_traits looks like <roleid> -> <trait (code_str)>
    # So, we'd have to remap them.
    emp_traits = cereconf.AFFILIATE_TRAITS

    answer = set()
    available_roles = [x for x in xmlperson.iteremployment()
                       if x.kind in (x.BILAG, x.GJEST) and
                          x.is_active()]
    for role in available_roles:
        roleid = role.code
        if roleid not in emp_traits:
            continue

        sko = role.place
        if not sko:
            logger.debug("role <%s> for <%s> is missing ou. skipped",
                         roleid, list(xmlperson.iterids()))
            continue

        assert role.place[0] == DataOU.NO_SKO
        # Map the sko from HR data to a dict with OU info (and ou_id)
        ou_info = get_sko(role.place[1], source_system)
        if not ou_info:
            logger.debug("role <%s> for <%s> has unknown ou. skipped",
                         roleid, list(xmlperson.iterids()))
            continue
        ou_id = ou_info["id"]
        try:
            trait = const.EntityTrait(emp_traits[roleid])
            answer.add((int(trait), int(ou_id), roleid))
        except Errors.NotFoundError:
            logger.warn("Trait '%s' is unknown in the db, but defined in "
                        "cereconf.AFFILIATE_TRAITS", emp_traits[roleid])
            continue

    logger.debug("Person %s gets %d traits: %s",
                 list(xmlperson.iterids()), len(answer), answer)
    return answer
# end determine_traits



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
        logger.info("Reservation registered for %s", p_id)
    elif not to_be_reserved and group.has_member(p_id, const.entity_person, op):
        group.remove_member(p_id, op)
        group.write_db()
        logger.info("Reservation removed for %s", p_id)
# end make_reservation



def parse_data(parser, source_system, group, gen_groups, old_affs, old_traits):
    """Process all people data available.

    For each person extracted from XML, register the changes in Cerebrum.  We
    try to treat all sources uniformly here.

    @type parser: instance of xmlutils.XMLDataGetter
    @param parser:
      Suitable parser for the given XML source file.

    @type source_system: instance of AuthoritativeSystem (or int)
    @param source_system:
      Source system where the data being parsed originated.

    @type group: instance of Factory.get('Group')
    @param group:
      Group for reservations for online directory publishing. For each person,
      his/her reservations for online directory publishing are expressed as
      the membership in this group.

    @type old_affs: dict
    @param old_affs:
      This mapping contains affiliations for every person currently present in
      Cerebrum. It is used to synchronise affiliation information (clean up
      'old' affiliations that are no longer present in the employee data).

    @type old_traits: dict (person_id -> set(trait_code1, ... trait_codeN))
    @param old_traits:
      This mapping containts traits for every person currently present in
      Cerebrum. It is used to synchronise trait information (clean up 'old'
      auto person traits that are no longer present in the employee data).

      For each person this function processes, the person's *current* traits
      are removed from old_traits. Whatever old_traits is left with, when we
      are done here, are the traits that have no longer basis in the
      authoritative system data. Thus, they can be deleted.
    """

    logger.info("processing file %s for system %s", parser, source_system)
    logger.debug("Group for reservations is: %s", group.group_name)

    xml2db = XML2Cerebrum(db, source_system, logger)
    for xmlperson in parser.iter_person():
        logger.debug("Loading next person: %s", list(xmlperson.iterids()))
        affiliations, work_title = determine_affiliations(xmlperson,
                                                          source_system)
        traits = determine_traits(xmlperson, source_system)

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
        status, p_id = xml2db.store_person(xmlperson, work_title,
                                           affiliations,
                                           traits)
        if p_id is None:
            logger.warn("Skipping person %s (invalid information on file)",
                        list(xmlperson.iterids()))
            continue

        if gen_groups == 1:
            make_reservation(xmlperson.reserved, p_id, group)

        # Now we mark current affiliations as valid (in case deletion is
        # requested later)
        if old_affs:
            for key in affiliations:
                tmp = "%s:%s" % (p_id, key)
                if tmp in old_affs:
                    old_affs[tmp] = False

        # Now we update the cache with traits (in case trait synchronisation
        # is requested later). This is similar to affiliation processing,
        # although the same goal is accomplished with a different data
        # structure.
        if old_traits:
            my_old_traits = old_traits.get(p_id, set())
            # select trait codes
            my_current_traits = set([x[0] for x in traits])
            logger.debug("Person id=%s has %d new traits, %d old traits. %d "
                         "old trait(s) will be removed",
                         p_id, len(my_current_traits), len(my_old_traits),
                         len(my_old_traits.difference(my_current_traits)))
            my_old_traits.difference_update(my_current_traits)

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
            logger.info("Person id=%s lost affiliation %s (ou id=%s)",
                        entity_id, const.PersonAffiliation(aff), ou_id)
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


def load_old_traits():
    """Collect all auto traits into a cache for later processing.

    This script assigns a number of traits automatically to people based on
    role information in the source data AND a mapping in cereconf. However,
    these traits have to be synchronised, and the obvious way of accomplishing
    this is to:

      # collect all existing auto traits into a data structure.
      # for each call of L{determine_traits}, update the data structure
        (i.e. remove the traits returned by L{determine_traits} from the data
        structure)
      # the remaining traits in the data structure have to be cleared out
        (there is no longer authoritative source system data to justify their
        existence)

    We can collect the list of currently valid auto traits from
    cereconf.AFFILIATE_TRAITS. Caveat: if someone removes an entry for a trait
    from that mapping, this script will no longer be able to sync that
    trait. That is fine, given that removing a trait from code (and from
    AFFILIATE_TRAITS) requires a cleanup stage anyway.

    @rtype: dict
    @return:
      A mapping person_id -> set, where each set contains the known auto
      traits for a given person (trait codes, specifically).
    """

    # Collect all known auto traits.
    if not hasattr(cereconf, "AFFILIATE_TRAITS"):
        return dict()

    auto_traits = set()
    for trait_code_str in cereconf.AFFILIATE_TRAITS.itervalues():
        try:
            trait = const.EntityTrait(trait_code_str)
            int(trait)
        except Errors.NotFoundError:
            logger.error("Trait <%s> is defined in cereconf.AFFILIATE_TRAITS, "
                         "but it is unknown i Cerebrum (code)", trait_code_str)
            continue

        # Check that the trait is actually associated with a person (and not
        # something else. AFFILIATE_TRAITS is supposed to "cover" person
        # objects ONLY!)
        if trait.entity_type != const.entity_person:
            logger.error("Trait <%s> from AFFILIATE_TRAITS is associated with "
                         "<%s>, but we allow person traits only",
                         trait, trait.entity_type)
            continue

        auto_traits.add(int(trait))

    # Now, let's build the mapping.
    answer = dict()
    # IVR 2008-01-16 FIXME: This assumes that list_traits can handle sequence
    # arguments.
    for row in person.list_traits(code=auto_traits):
        person_id = int(row["entity_id"])
        trait_id = int(row["code"])

        answer.setdefault(person_id, set()).add(trait_id)

    logger.debug("built person_id -> traits mapping. %d entries", len(answer))
    return answer
# end load_old_traits


def remove_traits(leftover_traits):
    """Remove traits from Cerebrum to synchronise the information.

    L{load_old_traits} builds a cache data structure that keeps track of all
    traits assigned to people in Cerebrum. Other functions update that cache
    and remove entries that should be considered up to date. When this
    function is called, whatever is left in cache is considered to be traits
    that have been assigned to people, but which should no longer exist, since
    the data from the authoritative source system says so.
    
    So, this function sweeps through leftover_traits and removes the traits
    from Cerebrum.

    @type leftover_traits: dict (see L{load_old_traits})
    @param leftover_traits:
      Cache of no longer relevant traits that should be removed.
    """

    logger.debug("Removing old traits (%d person objects concerned)",
                 len(leftover_traits))
    # Technically, EntityTrait and Person are different objects, but trait
    # auto administration in this context assumes person objects, so we can
    # safely ask for a 'Person' rather than an EntityTrait.
    person = Factory.get("Person")(db)
    for person_id, traits in leftover_traits.iteritems():
        try:
            person.clear()
            person.find(person_id)
        except Errors.NotFoundError:
            logger.warn("Person id=%s is in cache, but not in Cerebrum. "
                        "Another job removed it from the db?",
                        person_id)
            continue

        for trait in traits:
            try:
                person.delete_trait(trait)
                logger.info("Person id=%s lost trait %s",
                            person_id, const.EntityTrait(trait))
            except Errors.NotFoundError:
                logger.warn("Trait %s for person %s has already been deleted.",
                            const.EntityTrait(trait), person_id)

        person.write_db()
    logger.debug("Deleted all old traits")
# end remove_traits



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

    # Load current automatic traits (AFFILIATE_TRAITS)
    if include_del:
        cerebrum_traits = load_old_traits()
    
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
            parse_data(parser(filename, logger, False),
                       source_system,
                       group,
                       gen_groups,
                       include_del and cerebrum_affs or dict(),
                       include_del and cerebrum_traits or dict())

        if include_del:
            clean_old_affiliations(source_system, cerebrum_affs)

    if include_del:
        remove_traits(cerebrum_traits)

    if dryrun:
        db.rollback()
        logger.info("All changes rolled back")
    else:
        db.commit()
        logger.info("All changes committed")
# end main





if __name__ == "__main__":
    main()

