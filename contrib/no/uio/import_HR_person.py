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

"""
This script loads the information from various HR DBs into Cerebrum.

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
from Cerebrum.modules.xmlutils.xml2object import DataEmployment, DataOU

db = Factory.get('Database')()
db.cl_init(change_program='import_HR')
const = Factory.get('Constants')(db)
group = Factory.get("Group")(db)
person = Factory.get("Person")(db)
logger = Factory.get_logger("cronjob")





ou_cache = {}
def get_sko((fakultet, institutt, gruppe), system):
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
        # yrt
    # fi

    return ou_cache[stedkode, system]
# end get_sko



def determine_affiliations(xmlperson, source_system):
    """Determine affiliations for person p_id/xmlperson in order of significance.
    
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
    gjest2affstat = { 'EMERITUS' :  const.affiliation_tilknyttet_emeritus,
                      'PCVAKT'   :  const.affiliation_tilknyttet_pcvakt,
                      'UNIRAND'  :  const.affiliation_tilknyttet_unirand,
                      'GRP-LÆRER':  const.affiliation_tilknyttet_grlaerer,
                      'EF-STIP'  :  const.affiliation_tilknyttet_ekst_stip,
                      'BILAGSLØN':  const.affiliation_tilknyttet_bilag,
                      'EF-FORSKER': const.affiliation_tilknyttet_ekst_forsker,
                      'SENIORFORS': const.affiliation_tilknyttet_ekst_forsker,
                      'GJ-FORSKER': const.affiliation_tilknyttet_gjesteforsker,
                      'SIVILARB':   const.affiliation_tilknyttet_sivilarbeider,
                      'EKST. PART': const.affiliation_tilknyttet_ekst_partner,
                      'EKST-PART': const.affiliation_tilknyttet_ekst_partner,
                      'EKST. KONS': const.affiliation_tilknyttet_ekst_partner,
                      'EKST-KONS': const.affiliation_tilknyttet_ekst_partner,
                      'ASSOSIERT':const.affiliation_tilknyttet_assosiert_person,
                      'REGANSV' : const.affiliation_tilknyttet_frida_reg,
                      'REG-ANSV': const.affiliation_tilknyttet_frida_reg,
                      'ST-POL FRI': const.affiliation_tilknyttet_studpol,
                      'ST-POL UTV': const.affiliation_tilknyttet_studpol,
                      'ST-POL-UTV': const.affiliation_tilknyttet_studpol,
                      'ST-ORG FRI': const.affiliation_tilknyttet_studorg,
                      'ST-ORG UTV': const.affiliation_tilknyttet_studorg, }

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
        # fi
        if t.percentage > max_so_far:
            max_so_far = t.percentage
            title = t.title
        # fi

        if t.category not in kind2affstat:
            logger.warn("Unknown category %s for %s", t.category, str_pid())
            continue
        # fi

        aff_stat = kind2affstat[t.category]
        k = "%s:%s" % (place["id"], int(const.affiliation_ansatt))
        if not ret.has_key(k):
            ret[k] = (place["id"], const.affiliation_ansatt, aff_stat)
        # fi
    # od
    
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
        # fi
            
        k = "%s:%s" % (place["id"], int(const.affiliation_ansatt))
        if not ret.has_key(k):
            ret[k] = (place["id"], const.affiliation_ansatt, 
                      const.affiliation_status_ansatt_bil)
        # fi
    # od

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
        # fi
        place = get_sko(g.place[1], source_system)
        if place is None:
            continue
        # fi

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
            logger.warn("Unknown gjestetypekode %s for person %s",
                        g.code, str_pid())
            continue
        # fi

        k = "%s:%s" % (place["id"], int(const.affiliation_tilknyttet))
        if not ret.has_key(k):
            ret[k] = place["id"], const.affiliation_tilknyttet, aff_stat
        # fi
    # od
    
    return ret, title
# end determine_affiliations


def make_reservation(to_be_reserved, p_id, group):
    op = const.group_memberop_union

    if to_be_reserved and not group.has_member(p_id, const.entity_person, op):
        group.add_member(p_id, const.entity_person, op)
        group.write_db()
    elif not to_be_reserved and group.has_member(p_id, const.entity_person, op):
        group.remove_member(p_id, op)
        group.write_db()
    # fi
# end


def parse_data(parser, source_system, person, group, gen_groups, old_affs):
    """Process all people available through parser.

    We try to treat all sources uniformly here.
    """

    logger.info("processing file %s for system %s", parser, source_system)

    xml2db = XML2Cerebrum(db, source_system)
    it = parser.iter_persons()

    # 
    # TBD: This while-contraption is atrocious. However, until SAP learns to
    # deliver data that is at least remotely sane, we'll assume the worst.
    while 1:
        try:
            xmlperson = it.next()
        except StopIteration:
            break
        except:
            logger.exception("Failed to process next person")
            continue
        # yrt

        logger.debug("Loading next person: %s", list(xmlperson.iterids()))
        affiliations, work_title = determine_affiliations(xmlperson,
                                                          source_system)
        status, p_id = xml2db.store_person(xmlperson, affiliations, work_title)

        if gen_groups == 1:
            make_reservation(xmlperson.reserved, p_id, group)
        # fi

        # Now we mark current affiliations as valid (in case deletion is
        # requested later)
        if old_affs:
            for key in affiliations:
                tmp = "%s:%s" % (p_id, key)
                if tmp in old_affs:
                    old_affs[tmp] = False
                # fi
            # od
        # fi

        logger.info("**** %s (%s) %s ****", p_id, dict(xmlperson.iterids()),
                    status)
    # od
# end parse_data



def clean_old_affiliations(source_system, aff_set):
    """Walk through (updated) aff_set and remove invalid entries."""

    for key, status in aff_set.items():
        if status:
            entity_id, ou_id, aff = key.split(":")
            person.clear()
            person.entity_id = int(entity_id)
            person.delete_affiliation(ou_id, aff, source_system)
        # fi
    # od
# end clean_old_affiliations



def load_old_affiliations(source_system):
    """Load all affiliations pertaining to source_system."""
    affi_set = dict()
    for row in person.list_affiliations(source_system=source_system):
        key = "%s:%s:%s" % (row["person_id"], row["ou_id"], row["affiliation"])
        affi_set[key] = True
    # od

    return affi_set
# end load_old_affiliations



def locate_and_build((group_name, group_desc)):
    """Locate a group named groupname in Cerebrum and build it if necessary."""

    try:
        group.find_by_name(group_name)
    except:
        group.clear()
        account = Factory.get("Account")(db)
        account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        group.populate(account.entity_id, const.group_visibility_internal,
                       group_name, group_desc)
        group.write_db()
    # yrt

    return group
# end locate_and_build



def usage(exitcode=0):
    print """Usage: %s -s system:filename [-v] [-g] [-d]""" % sys.argv[0]
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
    # yrt

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
        # fi
    # od

    system2group = { "system_lt" :
                     ("LT-elektroniske-reservasjoner",
                      "Internal group for people from LT which will not be shown online"),
                     "system_sap" :
                     ("SAP-lektroniske-reservasjoner",
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
        # fi

        # Read in the file, and register the information in cerebrum
        if filename is not None:
            parse_data(parser(filename, False),
                       source_system,
                       person, group,
                       gen_groups,
                       include_del and cerebrum_affs or dict())
        # fi

        if include_del:
            clean_old_affiliations(source_system, cerebrum_affs)
        # fi
        
        if dryrun:
            db.rollback()
            logger.info("All changes rolled back")
        else:
            db.commit()
            logger.info("All changes committed")
        # fi
    # od
# end main





if __name__ == "__main__":
    main()
# fi

# arch-tag: 6b130cce-27e2-4643-8306-d857698cafe8
