#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2002, 2003 University of Oslo, Norway
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

import getopt
import sys
import pickle
import time
import pprint
import re

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum.Constants import _SpreadCode
from Cerebrum.modules import ChangeLog
from Cerebrum.modules.bofhd.auth import BofhdAuthOpTarget, BofhdAuthRole

Factory = Utils.Factory
db = Factory.get('Database')()
co = Factory.get('Constants')(db)

# TODO: Should have a cereconf variable for /cerebrum/var/log
status_file = "%s/db_clean_password.id" % cereconf.JOB_RUNNER_LOG_DIR  

logger = Factory.get_logger("big_shortlived")

"""
Hva skal ryddes bort?

ChangeLog ting
==============

* plaintext passord skal sensureres etter 1 døgn, men selve change
  entryen skal overleve

* Alle entries har en maks levetid på 6 måneder, med unntak av:
  - user create: tas vare på sålenge kontoen lever
  - add spread
  - gruppe innmeldinger uten påfølgende utmelding
  - siste passord endring

* Skal slettede entities ha kortere levetid?

* Når noe endrer tilstand, tar vi bare vare på den siste endringen
  F.eks:
  - passord satt (vi tar imidlertid vare på alle endringer siste 14
    dager for å fange flere bytter etterhverandre)
  - når en person meldes inn, og senere ut av en gruppe
  - når en person endrer navn for et gitt ss m/en gitt type
  - - - - - - - - - - -  adresse av en gitt tye
  - - - - - - - - - - -  contact info av en gitt type
  - person_affiliation for gitt ou+aff kombinasjon
  - person_affiliation_source for gitt ou+aff kombinasjon
  - account_type

* noe må fylle igjen gamle hull i change_handler_data, uvisst om det
  er dette scriptet.  Usikkert om behovet er tilstede.

Annet
=====

* ekspirerte grupper slettes etter 3 måneder

* person_affiliation m/deleted date > 3 måneder slettes (forutsatt at
  det ikke gir FK problemer).

* ekspirerte karantener slettes etter 3 måneder

* personer som ikke kommer fra FS/LT, og som ikke har noen kontoer
  slettes etter 6 måneder.  Hvordan finner vi de?  Hva hvis de har
  slettede kontoer?

Bofh ting
=========
Litt usikker på om bofh auth rydding skal gjøres av samme modul:

* Slå sammen duplikater av typen:
  - SELECT COUNT(*), entity_id
    FROM auth_op_target
    WHERE target_type='group'
    GROUP BY entity_id
    HAVING COUNT(*) > 1;

  - oppdage folk som har eierskap på u1, u2, u3 ... og vise jbofh
    komandoer som konverterer dette til u\d+.

  - oppdage auth_op_target som ikke lenger er i bruk  
"""

AGE_FOREVER = -1
default_age = 3600*24*185      # 6 months
minimum_age = 3600*24
password_age = 3600*24

# Sometimes we need to know where the users homedirectory was three
# years ago so that we can restore files the user owned then.
never_forget_homedir = True

# All entries will be expired after default_age, unless max_ages
# overrides it.  Data in max_ages may be removed by keep_togglers.
# This allows us to allways keep a group_add, unless there was a
# subsequent group_remove.

max_ages = {
    int(co.account_create): AGE_FOREVER,
    int(co.group_create): AGE_FOREVER,
    int(co.ou_create): AGE_FOREVER,
    int(co.person_create): AGE_FOREVER,
    int(co.group_add): AGE_FOREVER,
    int(co.spread_add): AGE_FOREVER,
    int(co.account_password): AGE_FOREVER,

    # TODO: Once account_type changes are better logged, we don't need
    # this special case
    int(co.account_type_add): 3600*24*31,
    int(co.account_type_mod): 3600*24*31,
    int(co.account_type_del): 3600*24*31,
    }

if never_forget_homedir:
    max_ages[int(co.account_move)] = AGE_FOREVER 
    max_ages[int(co.account_home_updated)] = AGE_FOREVER 
    max_ages[int(co.account_home_added)] = AGE_FOREVER 
    max_ages[int(co.account_home_removed)] = AGE_FOREVER 
# The keep_togglers datastructure is a list of entries that has the
# format:
#
#   ({'columns': []
#     'change_params': []
#     'triggers': []}
#
# The combination of the columns and change_params works like a
# database primary-key for events of the type listed in triggers.  We
# only want to keep the last event of this type.

keep_togglers = [
    # Spreads
    {'columns': ('subject_entity', ),
     'change_params': ('spread', ),
     'triggers': (co.spread_add, co.spread_del)},
    # Group members
    {'columns': ('subject_entity', 'dest_entity'),
     'triggers': (co.group_add, co.group_rem)},
    # Group creation/modification
    {'columns': ('subject_entity', ),
     'triggers': (co.group_create, co.group_mod, co.group_destroy)},
    # Account create
    {'columns': ('subject_entity', ),
     'triggers': (co.account_create, )},
    # Account updates
    {'columns': ('subject_entity', ),
     'triggers': (co.account_mod, )},
    # Account updates
    {'columns': ('subject_entity', ),
     'triggers': (co.posix_demote, )},
    # Account passwords
    {'columns': ('subject_entity', ),
     'triggers': (co.account_password, )},
    # AccountType
    # TBD:  Hvordan håndtere account_type_mod der vi bare logger old_pri og new_pri
    {'columns': ('subject_entity', ),
     # may remove a bit too much, but we log too little to filter better...
     # 'change_params': ('ou_id', 'affiliation', ),
     'triggers': (co.account_type_add, co.account_type_mod,
                  co.account_type_del)},
    # Disk
    {'columns': ('subject_entity', ),
     'triggers': (co.disk_add, co.disk_mod, co.disk_del)},
    # Host
    {'columns': ('subject_entity', ),
     'triggers': (co.host_add, co.host_mod)},
    # OU
    {'columns': ('subject_entity', ),
     'triggers': (co.ou_create, co.ou_mod)},
    # OU perspective
    {'columns': ('subject_entity', ),
     'change_params': ('perspective', ),
     'triggers': (co.ou_unset_parent, co.ou_set_parent)},
    # Person creation
    {'columns': ('subject_entity', ),
     'triggers': (co.person_create, co.person_update)},
    # Person names
    {'columns': ('subject_entity', ),
     'change_params': ('name_variant', 'src', ),
     'triggers': (co.person_name_del, co.person_name_add, co.person_name_mod)},
    # Person external id
    {'columns': ('subject_entity', ),
     'change_params': ('id_type', 'src'),
     'triggers': (co.person_ext_id_del, co.person_ext_id_mod,
                  co.person_ext_id_add)},
    # Person affiliation
    # TBD: The CL data could preferably contain more data
    {'columns': ('subject_entity', ),
     'triggers': (co.person_aff_add, co.person_aff_mod, co.person_aff_del)},
    # Person affiliation source
    {'columns': ('subject_entity', ),
     'triggers': (co.person_aff_src_add, co.person_aff_src_mod,
                  co.person_aff_src_del)},
    # Quarantines
    {'columns': ('subject_entity', ),
     'change_params': ('q_type', ),
     'triggers': (co.quarantine_add, co.quarantine_mod, co.quarantine_del)},
    # Entity creation/deletion
    {'columns': ('subject_entity', ),
     'triggers': (co.entity_add, co.entity_del)},
    # Entity names
    {'columns': ('subject_entity', ),
     'change_params': ('domain', ),
     'triggers': (co.entity_name_add, co.entity_name_mod, co.entity_name_del)},
    # Entity contact info
    # TBD: The CL data could preferably contain more data
    {'columns': ('subject_entity', ),
     'triggers': (co.entity_cinfo_add, co.entity_cinfo_del)},
    # Entity address info
    # TBD: The CL data could preferably contain more data
    {'columns': ('subject_entity', ),
     'triggers': (co.entity_addr_add, co.entity_addr_del)},
    ]

if never_forget_homedir:
    toggleable = 0
else:
    toggleable = 1

keep_togglers.extend([
    # Account homedir  (obsolete)
    {'columns': ('subject_entity', ),
     'toggleable': toggleable,
     'triggers': (co.account_move, )},
    # Account homedir
    {'columns': ('subject_entity', ),
     'toggleable': toggleable,
     'change_params': ('spread', ),
     'triggers': (co.account_home_updated, co.account_home_added,
                  co.account_home_removed)}
    ])

def setup():
    # Sanity check: assert that triggers are unique.  Also provides
    # quicker lookup
    global trigger_mapping
    trigger_mapping = {}
    i = 0
    for k in keep_togglers:
        k['toggler_id'] = i
        i += 1
        for t in k['triggers']:
            if trigger_mapping.has_key(int(t)):
                raise ValueError, "%s is not a unique trigger" % t
            if not k.get('toggleable', 1):
                trigger_mapping[int(t)] = None
            else:
                trigger_mapping[int(t)] = k

def remove_plaintext_passwords():
    """Removes plaintext passwords."""

    # This job should be ran fairly often.  Therefore it should keep
    # track of where it last removed a password so that it can run
    # quickly.

    now = time.time()
    try:
        f = file(status_file)
        start_id = f.readline()
        start_id = int(start_id)
    except IOError:
        start_id = 0
    logger.debug("start_id=%i" % start_id)
    max_id = 0
    not_removed = 0
    num_removed = 0
    for e in db.get_log_events(start_id=start_id, types=[co.account_password]):
        age = now - e['tstamp'].ticks()
        # Remove plaintext passwords
        if (e['change_type_id'] == int(co.account_password) and
            age > password_age):
            if not e['change_params']:
                continue
            dta = pickle.loads(e['change_params'])
            if dta.has_key('password'):
                del(dta['password'])
                logger.debug(
                    "Removed password for id=%i" % e['subject_entity'])
                if not dryrun:
                    db.update_log_event(e['change_id'], dta)
            max_id = e['change_id']
            num_removed += 1
        else:
            not_removed += 1

    logger.debug("Removed %i, kept %i passwords" % (num_removed, not_removed))
    if not dryrun:
        db.commit()
        f = file(status_file, 'w')
        f.write("%s\n" % max_id)
        f.close()
    else:
        db.rollback()   # noia rollback just in case

def format_as_int(i):
    """Get rid of PgNumeric while preserving NULL values"""
    if i is not None:
        return int(i)
    return i

def process_log():
    if 0:
        for c in db.get_changetypes():
            print "%-5i %-8s %-8s" % (c['change_type_id'],
                                      c['category'], c['type'])

    now = time.time()
    last_seen = {}
    n = 0
    db2 = Factory.get('Database')()  # Work-around for fetchmany cursor re-usage
    warn_unknown_type = {}
    for e in db2.get_log_events():
        n += 1
        tmp = e['change_params']
        if e['change_type_id'] == int(co.account_password):
            tmp = 'password'      # Don't write password in log
        logger.debug((e['tstamp'].strftime('%Y-%m-%d'),
                      int(e['change_id']), int(e['change_type_id']),
                      format_as_int(e['subject_entity']),
                      format_as_int(e['dest_entity']),
                      repr(tmp)))

        if not trigger_mapping.has_key(int(e['change_type_id'])):
            if not warn_unknown_type.has_key(int(e['change_type_id'])):
                warn_unknown_type[ int(e['change_type_id']) ] = 1
            else:
                warn_unknown_type[ int(e['change_type_id']) ] += 1
            continue
        
        age = now - e['tstamp'].ticks()
        # Keep all data newer than minimum_age
        if age < minimum_age:
            continue

        tmp = max_ages.get(int(e['change_type_id']), default_age)
        if tmp != AGE_FOREVER and age > tmp:
            logger.debug("Remove due to age: %i" % e['change_id'])
            if not dryrun:
                db.remove_log_event(e['change_id'])
            
        # Determine a unique key for this event to check togglability
        m = trigger_mapping[int(e['change_type_id'])]
        if m is None:
            continue          # Entry is not toggle'able
        key = [ "%i" % m['toggler_id'] ]
        for c in m.get('columns'):
            key.append("%i" % e[c])
        if m.has_key('change_params'):
            if e['change_params']:
                dta = pickle.loads(e['change_params'])
            else:
                dta = {}
            for c in m['change_params']:
                key.append("%s" % dta.get(c, None))
        # Not needed if a list may be efficiently/safely used as key in a dict:
        key = "-".join(key)
        logger.debug("Key is: %s" % key)
        if last_seen.has_key(key):
            logger.debug("Remove (%s): %i" % (key, last_seen[key]))
            if not dryrun:
                db.remove_log_event(last_seen[key])
        last_seen[key] = int(e['change_id'])
        if (n % 500) == 0:
            if not dryrun:
                db.commit()
    for k, v in warn_unknown_type.items():
        logger.warn("Unknown change_type_id:%i for %i entries" % (k, v))

    if not dryrun:
        db.commit()
    else:
        db.rollback()   # noia rollback just in case

def merge_bofh_auth():
    pp = pprint.PrettyPrinter(indent=4)
    ba = BofhdAuthOpTarget(db)
    ar = BofhdAuthRole(db)
    disk = Utils.Factory.get('Disk')(db)
    attr_map = {}
    logger.debug("Reading auth_op_target table...")
    for row in ba.list():
        key = (format_as_int(row['entity_id']),row['target_type'], row['attr'])
        attr_map.setdefault(key, []).append(int(row['op_target_id']))

    #logger.debug("Map of auth_op_targets: ")
    #logger.debug(pp.pformat(attr_map))
    disk_regexp = re.compile(r"(.*/\D+)(\d+)$")
    paths = {}
    for k in attr_map.keys():
        if len(attr_map[k]) > 1:
            # Multiple rows point to a syntactically identical auth_op_target
            logger.debug("Owners of %s [move to %i]" % (
                str(attr_map[k][1:]), attr_map[k][0]))
            # Move grants to the first auth_op_target
            for row in ar.list_owners(attr_map[k][1:]):
                logger.debug((int(row['entity_id']), int(row['op_set_id']),
                              int(row['op_target_id'])))
                if not dryrun:
                    ar.revoke_auth(row['entity_id'], row['op_set_id'],
                                   row['op_target_id'])
                    ar.grant_auth(row['entity_id'], row['op_set_id'],
                                  attr_map[k][0])
            # Remove the now empty auth_op_targets
            for op_target_id in attr_map[k][1:]:
                ba.find(op_target_id)
                if not dryrun:
                    ba.delete()
        else: 
            # This check is a bit slow when we have many entries,
            # consider disabling when debugging.
            
            # Check for empty auth_op_targets
            if not ar.list_owners(attr_map[k][0]):
                ba.find(attr_map[k][0])
                if not dryrun:
                    ba.delete()
        if k[1] == 'disk':     # determine path for disk
            disk.clear()
            disk.find(k[0])
            m = disk_regexp.match(disk.path)
            if m is None:
                logger.warn("Unexpected disk: %s" % disk.path)
            else:
                paths.setdefault(m.group(1), []).append((m.group(2), attr_map[k][0]))

    # TBD: Could we process any of these data automagically, or
    # present them in a more readable way?
    logger.debug(
        "The following disks could be merged into a host target with "
        "regexp for disk matching.  The first line is the path, "
        "followed by the numeric part of the part and the corresponding "
        "target_id.  The owners are listed below in the format "
        " (owner_entity_id, ): [op_target_id]"
        )
    order = paths.keys()
    order.sort()
    for base in order:
        if len(paths[base]) == 1:
            continue
        logger.debug((base, paths[base]))
        owners = {}
        # Make mapping target_id:[entity_ids]
        for row in ar.list_owners([k[1] for k in paths[base]]):
            owners.setdefault(int(row['op_target_id']), []).append(
                int(row['entity_id']))
        # Make mapping [entity_ids]:[target_ids]
        tmp = {}
        for op_target_id in owners.keys():
            tmp.setdefault(tuple(owners[op_target_id]), []).append(op_target_id)
        logger.debug(pp.pformat(tmp))
    if not dryrun:
        db.commit()
    else:
        db.rollback()   # noia rollback just in case

def main():
    global dryrun
    try:
        opts, args = getopt.getopt(
            sys.argv[1:], '', ['help', 'dryrun', 'plain',
                               'changelog', 'bofh', 'password-age='])

    except getopt.GetoptError:
        usage(1)
    do_remove_bofh = do_remove_plain = do_process_log = dryrun = False
    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('--dryrun',):
            dryrun = True
        elif opt in ('--plain',):
            do_remove_plain = True
        elif opt in ('--bofh',):
            do_remove_bofh = True
        elif opt in ('--changelog',):
            do_process_log = True
        elif opt in ('--password-age',):
            global password_age
            password_age = int(val)
        else:
            usage()

    setup()
    if do_remove_plain:
        remove_plaintext_passwords()
    if do_process_log:
        process_log()
    if do_remove_bofh:
        merge_bofh_auth()

def usage(exitcode=0):
    print """Usage: [options]
    --help : this text
    --dryrun : don't do any changes to the db
    --plain : delete plaintext passwords
    --bofh : merge equal targets in auth_op_target
    --changelog : delete 'irrelevant' changelog entries
    --password-age seconds: delete passwords older than this (see --plain)
    """
    sys.exit(exitcode)

if __name__ == '__main__':
    main()

# arch-tag: 4e7cd28d-ed69-4a8a-98c8-de24115385d5
