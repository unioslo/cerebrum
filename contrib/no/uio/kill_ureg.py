#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2002-2015 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""Remove or copy to source Manual most data registered with source UREG.

Note: Name changes schedule a few test-mailboxes to be moved.  Report
these to postmaster, so the moves can be canceled before they are executed.

Usage: kill_ureg.py [--commit] [removal options; default = all removals]

Removals:

--affiliation
  Remove from person_affiliation_source.

--refresh
  Remove nothing, but regenerate cached names which --name will regenerate

--name
  Table person_name.
  Save other names not overridden in SAP, FS or Manual.
  E-mail addresses are also affected by name changes.

--fnr
  entity_external_id[externalid_fodselsnr].
  Remove all old fnr from ureg.
"""

Debug = False
commit = False

import sys
import getopt

from collections import defaultdict

from Cerebrum.Utils import Factory
logger = Factory.get_logger("console")
db = Factory.get('Database')()
db.cl_init(change_program="kill_ureg")
const, person = [Factory.get(x)(db) for x in 'Constants', 'Person']

Log, Info, Warn = None, logger.info, logger.warning

system_sap    = int(const.system_sap)
system_fs     = int(const.system_fs)
system_manual = int(const.system_manual)
system_ureg   = int(const.system_ureg)
# Systems whose data override person_name and entity_external_id[fodselsnr]
better_systems= (system_sap, system_fs, system_manual) # for names and ext.ids

type_person = int(const.entity_person)
idtype_fnr  = const.externalid_fodselsnr

# Remove these name variants without saving to Manual.
drop_names  = ()


def nint(x):
    if x is not None:
        x = int(x)
    return x

def affiliation():
    """Clean up person_affiliation_source"""
    logger.debug('affiliation...')
    person.nuke_affiliation_for_source_system(system_ureg)
    logger.debug('... done')

def refresh():
    """Refresh person_name[source Cached] where UREG names exist"""
    name(True)

def name(refresh_only=False):
    """
    Clean up person_name, also affecting email addresses.
    If refresh_only, only update Cached names.
    """
    logger.debug("name%s...", ["", " refresh"][refresh_only])
    count_del = count_ins = persons = 0

    name_types = [int(row['code']) for row in person.list_person_name_codes()]
    uregnames = person.getdict_persons_names(
        source_system=system_ureg, name_types=name_types)

    total_persons = len(uregnames.keys())
    for person_id, ureg_variant2name in uregnames.iteritems():
        if Debug and count_ins >= Debug:
            logger.debug("Debug done.")
            break
        person.clear()
        person.find(person_id)
        persons += 1
        Info('prosessing person %d of %d' % (persons, total_persons))

        if not refresh_only:
            # Find which name variants we need to copy to Manual
            need_variants = set(ureg_variant2name).difference(drop_names)
            for row in person.get_names():
                if int(row['source_system']) in better_systems:
                    need_variants.discard(int(row['name_variant']))
            # Copy them
            if need_variants:
                person.affect_names(system_manual, *need_variants)
                for variant in need_variants:
                    count_ins += 1
                    Info("insert Manual name person_id=%d variant=%d '%s'"
                         % (person_id, variant, ureg_variant2name[variant]))
                    person.populate_name(variant, ureg_variant2name[variant])
                person.write_db()
                person.clear()
                person.find(person_id)
            # Delete UREG names
            for variant, name in ureg_variant2name.iteritems():
                count_del += 1
                Info("delete UREG name person_id=%d variant=%d '%s'"
                     % (person_id, variant, name))
                person.get_name(system_ureg, variant)
                person._delete_name(system_ureg, variant)

        person._update_cached_names()

    person.clear()
    if refresh_only:
        Info("*Person_name: Updated %d*" % len(uregnames.keys()))
    else:
        Info("*Person_name: Inserted %d and removed %d* from %d persons" %
             (count_ins, count_del, total_persons))


def address():
    """Clean up entity_address"""
    logger.debug("address...")
    del_count = del_eid_count = 0

    addresses = defaultdict(list)
    for row in person.list_entity_addresses(source_system=system_ureg):
        addresses[row['entity_id']].append(row['address_type'])

    for entity_id, address_types in addresses.iteritems():
        person.clear()
        person.find(entity_id)
        del_eid_count += 1
        for address_type in address_types:
            person.delete_entity_address(system_ureg, address_type)
            del_count += 1

    Info("entity_address: removed %d from %d persons*"
         % (del_count, del_eid_count))


def fnr():
    """Clean up entity_external_id[externalid_fodselsnr]"""
    logger.debug("fnr...")
    count_del = 0

    # All entity_ids with fnr from ureg
    ids = [int(row['entity_id'])
           for row in person.search_external_ids(source_system=system_ureg,
                                                 id_type=idtype_fnr,
                                                 entity_type=type_person,
                                                 fetchall=False)]

    for entity_id in ids:
        count_del += 1
        person.clear()
        person.find(entity_id)
        person._delete_external_id(source_system=system_ureg, id_type=idtype_fnr)
    Info("*External_id: removed %d*" % count_del)


def main():
    global Dryrun
    prog_opts = ["affiliation","refresh","name","address","fnr"]
    try:
        opts, args = getopt.getopt(sys.argv[1:], "", prog_opts + ["commit"])
    except getopt.GetoptError, e:
        sys.exit(str(e))
    if args:
        sys.exit("Invalid arguments: " + " ".join(args))

    commit = False
    opts = [opt[2:] for opt, val in opts]
    if "commit" in opts:
        logger.debug("commit")
        commit = True
        opts.remove("commit")
    if not opts:
        prog_opts.remove("refresh")
        opts = prog_opts
    elif "refresh" in opts and "name" in opts:
        sys.exit("Options --refresh and --name incompatible")

    for opt in prog_opts:
        if opt in opts:
            globals()[opt]()

    if commit:
        Info('commiting changes...')
        db.commit()
    else:
        Info('rolling back changes...')
        db.rollback()
    Info('...done')

    if Log: Log.close()



if __name__ == '__main__':
    main()
