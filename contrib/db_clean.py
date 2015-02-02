#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2002-2011 University of Oslo, Norway
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
from mx import DateTime

import cerebrum_path
import cereconf
import dbcl_conf
from Cerebrum import Entity
from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum.modules.bofhd.auth import BofhdAuthOpTarget, BofhdAuthRole
from Cerebrum.modules import default_dbcl_conf

Factory = Utils.Factory
db = Factory.get('Database')()
db.cl_init(change_program="db_clean")
co = Factory.get('Constants')(db)
account = Factory.get('Account')(db)
group = Factory.get('Group')(db)
person = Factory.get('Person')(db)

# Initialising the global ChangeLog constants for cleaning
CLCleanDefConfInstance = default_dbcl_conf.CLCleanDefConf()

# TODO: Should have a cereconf variable for /cerebrum/var/log
logger = Factory.get_logger("big_shortlived")

"""
Hva skal ryddes bort?

ChangeLog ting
==============

* check the class Cerebrum.modules.default_dbcl_conf.CLCleanDefConf for the
  default constants used during the ChangeLog cleaning.

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

def format_as_int(i):
    """Get rid of PgNumeric while preserving NULL values"""
    if i is not None:
        return int(i)
    return i


class CleanChangeLog(object):

    # Importing the instance specific ChangeLog constants for cleaning
    AGE_FOREVER = dbcl_conf.AGE_FOREVER
    try:
     if dbcl_conf.default_age_update:
        default_age = dbcl_conf.default_age_update
    except:
        default_age = CLCleanDefConfInstance.default_age

    try:
     if dbcl_conf.minimum_age_update:
        minimum_age = dbcl_conf.minimum_age_update
    except:
        minimum_age = CLCleanDefConfInstance.minimum_age
    # max_ages and keep_togglers are respectively a dict and a list that can
    # only be updated from the original configuraiton.
    # For a full list over the data structures for those constants or
    # variabels please check the imported file: Cerebrum.modules.default_dbcl_conf .
    try:
     if dbcl_conf.max_ages_update:
       CLCleanDefConfInstance.max_ages.update(dbcl_conf.max_ages_update)
       max_ages   = CLCleanDefConfInstance.max_ages
    except:
       max_ages      = CLCleanDefConfInstance.max_ages

    keep_togglers = CLCleanDefConfInstance.keep_togglers
    try:
     if dbcl_conf.keep_togglers_to_update and dbcl_conf.keep_togglers_updated:
      for i in dbcl_conf.keep_togglers_to_update:
       if i in keep_togglers:
        keep_togglers[keep_togglers.index(i)] =  dbcl_conf.keep_togglers_updated[
         dbcl_conf.keep_togglers_to_update.index(i)]
    except:
        pass

    def process_log(self):
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
            change_type = int(e['change_type_id'])
            if change_type == int(co.account_password):
                tmp = 'password'      # Don't write password in log
            debuginfo = (e['tstamp'].strftime('%Y-%m-%d'),
                          int(e['change_id']), change_type,
                          format_as_int(e['subject_entity']),
                          format_as_int(e['dest_entity']), tmp)
            logger.debug('Changelog entry: %r', debuginfo)

            if change_type not in self.trigger_mapping:
                if change_type not in warn_unknown_type:
                    warn_unknown_type[change_type] = 1
                else:
                    warn_unknown_type[change_type] += 1
                continue

            age = now - e['tstamp'].ticks()
            # Keep all data newer than minimum_age
            if age < self.minimum_age:
                continue

            tmp = self.max_ages.get(change_type, self.default_age)
            if tmp != self.AGE_FOREVER and age > tmp:
                logger.info("Removed due to age: %r", debuginfo)
                if not dryrun:
                    db.remove_log_event(e['change_id'])

            # Determine a unique key for this event to check togglability
            m = self.trigger_mapping[change_type]
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
            if last_seen.has_key(key):
                logger.info("Remove toggle %r %r %r",
                            key, last_seen[key], debuginfo)
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

    def _setup(self):
        # Sanity check: assert that triggers are unique.  Also provides
        # quicker lookup
        self.trigger_mapping = {}
        i = 0
        for k in self.keep_togglers:
            k['toggler_id'] = i
            i += 1
            for t in k['triggers']:
                if self.trigger_mapping.has_key(int(t)):
                    raise ValueError, "%s is not a unique trigger" % t
                if not k.get('toggleable', 1):
                    self.trigger_mapping[int(t)] = None
                else:
                    self.trigger_mapping[int(t)] = k

    def run(self):
        self._setup()
        self.process_log()

class CleanPasswords(object):
    status_file = "%s/db_clean_password.id" % cereconf.JOB_RUNNER_LOG_DIR  

    def __init__(self, password_age):
        self.password_age = password_age

    def remove_plaintext_passwords(self):
        """Removes plaintext passwords."""

        # This job should be ran fairly often.  Therefore it should keep
        # track of where it last removed a password so that it can run
        # quickly.

        now = time.time()
        try:
            f = file(self.status_file)
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
                age > self.password_age):
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
            f = file(self.status_file, 'w')
            f.write("%s\n" % max_id)
            f.close()
        else:
            db.rollback()   # noia rollback just in case

    def run(self):
        self.remove_plaintext_passwords()

class CleanBofh(object):
    def _change_op_target(self, src_target_ids, dest_target_id=None):
        """If dest_target_id is None, only delete the
        op-target. src_target_ids must be a tuple"""
        ba = BofhdAuthOpTarget(db)
        ar = BofhdAuthRole(db)
        for row in ar.list_owners(src_target_ids):
            logger.debug((int(row['entity_id']), int(row['op_set_id']),
                          int(row['op_target_id'])))
            if not dryrun:
                ar.revoke_auth(row['entity_id'], row['op_set_id'],
                               row['op_target_id'])
                if dest_target_id is not None:
                    ar.grant_auth(row['entity_id'], row['op_set_id'],
                                  dest_target_id)
        # Remove the now empty auth_op_targets
        for op_target_id in src_target_ids:
            ba.find(op_target_id)
            if not dryrun:
                ba.delete()
        
    def merge_bofh_auth(self):
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
                self._change_op_target(attr_map[k][1:], attr_map[k][0])
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
                try:
                    disk.find(k[0])
                except Errors.NotFoundError:
                    logger.debug("No such disk: %i" % k[0])
                    self._change_op_target(attr_map[k])
                    continue
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

    def run(self):
        self.merge_bofh_auth()

class PersonAff(object):
    def __init__(self, ou, aff, source_system, status, delete_age, last_age):
        self.ou = int(ou)
        self.aff = int(aff)
        self.source_system = int(source_system)
        self.status = int(status)
        self.delete_age = delete_age
        self.last_age = last_age

    def __repr__(self):
        return "%i/%i@%i, src=%i, del_age=%s, last_age=%s" % (
            self.aff, self.status, self.ou, self.source_system,
            self.delete_age, self.last_age)

class UserAff(object):
    def __init__(self, ou, aff, pri, person_id):
        self.ou = int(ou)
        self.aff = int(aff)
        self.pri = int(pri)
        self.person_id = int(person_id)

    def __repr__(self):
        return "%i@%i#%i, pid=%i" % (self.aff, self.ou, self.pri, self.person_id)
    
class CleanPersons(object):
    def post_create(self, clean_users):
        self._cu = clean_users
        self.pid2affs = self.__get_pid2affs()
        self.pid2aid = self.__get_pid2aid()
        self.pid2age, self.pid2src_sys_age = self.__get_persons_age()
        self.log_r = LogRemoved()
    
    def __get_pid2affs(self):
        logger.debug("__get_pid2affs")
        now = DateTime.now()
        ret = {}
        for row in person.list_affiliations(include_deleted=True):
            if row['deleted_date']:
                delete_age = (now - row['deleted_date']).days
            else:
                delete_age = -1
            if row['last_date']:
                last_age = (now - row['last_date']).days
            else:
                last_age = -1
            ret.setdefault(int(row['person_id']), []).append(
                PersonAff(row['ou_id'], row['affiliation'],
                          row['source_system'], row['status'], delete_age,
                          last_age))
        return ret
    
    def __get_pid2aid(self):
        logger.debug("__get_pid2aid")
        ret = {}
        for row in account.list(filter_expired=False):
            if row['owner_type'] == int(co.entity_person):
                ret.setdefault(int(row['owner_id']), []).append(
                    int(row['account_id']))
        return ret
        
    def __get_persons_age(self):
        """Try to determine when person was last updated in days by
        looking at person_affiliation_source.last_age and change_log.
        Also try to figure out when we last got an update from a
        spesific source_system"""
        
        logger.debug("__get_persons_age")
        pid2age = {}
        pid2src_sys_age = {}
        now = DateTime.now()

        src_systems = (int(co.system_sap), int(co.system_lt), int(co.system_fs))
        # Find age from person_affiliation_source
        for row in person.list_persons():
            pid = int(row['person_id'])
            all_affs = [a for a in self.pid2affs.get(pid, [])]
            if all_affs:
                pid2age[pid] = min([a.last_age for a in all_affs])
            else:
                pid2age[pid] = None
            pid2src_sys_age[pid] = {}
            for s in src_systems:
                tmp = [a for a in all_affs if a.source_system==s]
                if tmp:
                    pid2src_sys_age[pid][s] = min([a.last_age for a in tmp])

        # For those not in person_affiliation_source, find age from
        # change_log
        for row in db.get_log_events(
            types=[int(x) for x in (co.person_update, co.person_create)]):
            eid = int(row['subject_entity'])
            if not pid2age.has_key(eid):
                continue
            age = (now - row['tstamp']).days            
            if pid2age[eid] is None or age < pid2age[eid]:
                 pid2age[eid] = age
        return pid2age, pid2src_sys_age

    def __nuke_person(self, pid):
        for row in group.search(member_id=pid, indirect_members=False):
            group.clear()
            group.find(row['group_id'])
            self.log_r.remove_member(pid, row['group_id'])
            group.remove_member(pid)
        person.clear()
        person.find(pid)
        # TBD: Hvor mye skal vi logge om personen som slettes?
        self.log_r.nuke_person(person)
        person.delete()
        db.commit()

    def remove_old_persons(self):
        logger.debug("remove_old_persons")
        age_threshold = 365
        for pid, age in self.pid2age.items():
            if ((age is not None and age < age_threshold) or  # Ny nok
                self.pid2aid.has_key(pid)):           # eller har en konto
                #logger.debug("Keep %i: age=%s, %s" % (
                #    pid, age, self.pid2aid.has_key(pid)))
                continue
            logger.debug("Nuking person_id=%i with age=%s" % (pid, age))
            if not dryrun:
                self.__nuke_person(pid)
            if self.pid2affs.has_key(pid):
                del(self.pid2affs[pid])

    def remove_old_person_affiliations(self):

        # TODO/TBD: If we end up removing all affiliations for a
        # person that doesn't have an account, there is a fair chance
        # that the person will be nuked on the next consequtive run.
        # Is this intented?

        logger.debug("remove_old_person_affiliations")
        some_systems = [int(x) for x in (co.system_fs, co.system_sap,
                                         co.system_lt, co.system_manual)]
        def has_other(p_aff, affs, match_type, src_systems):
            for p in affs:
                if p == p_aff or p.source_system not in src_systems:
                    continue
                if match_type == 'aff' and p.aff == p_aff.aff:
                    return True
                if (match_type == 'aff_ou' and p.aff == p_aff.aff and
                    p.ou == p_aff.ou):
                    return True
            return False

        fs_lt_sap = (int(co.system_sap), int(co.system_lt), int(co.system_fs))
        # Vi venter med å sjekke account_type FK problemer til etter
        # at vi har funnet det vi ønsker å slette.
        for pid, affs in self.pid2affs.items():
            affs = self.pid2affs[pid]
            remove = []
            # Remove UREG aff is person has affilation from another system
            if [p for p in affs if p.source_system in some_systems]:
                tmp = []
                for p in affs:
                    if p.source_system == int(co.system_ureg):
                        remove.append(p)
                    else:
                        tmp.append(p)
                affs = tmp
                    
            for p_aff in affs:
                if p_aff.delete_age > 30:
                    # en har deleted_date > 30 dage
                    remove.append(p_aff)
                    continue
                if p_aff.aff == int(co.affiliation_manuell) and not [
                    p2 for p2 in affs if p_aff != p2 and p_aff.ou == p2.ou]:
                    # kaster ikke MANUELL@ou hvis vi ikke har noe annet mot samme ou
                    continue
                if int(p_aff.source_system) in fs_lt_sap:
                    # vi kaster FS/LT kun hvis deleted_date != None
                    continue
                if (p_aff.source_system == int(co.system_manual) and
                    p_aff.last_age < 365 and
                    not has_other(p_aff, affs, 'aff_ou', fs_lt_sap)):
                    # sletter manual først når samme aff+ou er kommet fra FS/LT
                    continue
                if p_aff.last_age > 180:
                    remove.append(p_aff)
                elif p_aff > 90:
                    if has_other(p_aff, affs, 'aff', fs_lt_sap):
                        remove.append(p_aff)

            all_ac_affs = {}
            for aid in self.pid2aid.get(pid, []):
                for ac_aff in self._cu.aid2affs.get(aid,[]):
                    all_ac_affs[(ac_aff.ou, ac_aff.aff)] = True
            all_ac_affs = all_ac_affs.keys()
            if not remove:
                continue
            if not hasattr(person, 'entity_id') or person.entity_id != pid:
                person.clear()
                person.find(pid)
            for aff in remove:
                # Check if this would trigger a FK-violation
                if (len([p for p in affs
                         if aff.aff == p.aff and aff.ou == p.ou]) <= 1 and
                    (aff.ou, aff.aff) in all_ac_affs):
                    pass  # Would trigger FK-violation
                else:
                    log_rem.person_aff(pid, aff)
                    if not dryrun:
                        person.nuke_affiliation(aff.ou, aff.aff,
                                                aff.source_system, aff.status)
                    if aff in affs:  # Not in affs if it was from UREG
                        affs.remove(aff)
            if not dryrun:
                db.commit()

    def remove_old_fnr(self):
        logger.debug("remove_old_fnr")
        def do_fnr_filter(fnrs, src_systems):
            return [
                f for f in fnrs
                if int(f['source_system']) in [int(s) for s in src_systems]]

        ex = Entity.EntityExternalId(db)
        pid2ext_ids = {}
        for row in ex.list_external_ids(id_type=co.externalid_fodselsnr):
            pid2ext_ids.setdefault(int(row['entity_id']), []).append(row)

        remove = []
        fs_lt_sap = (int(co.system_sap), int(co.system_lt), int(co.system_fs))
        for pid, fnrs in pid2ext_ids.items():
            fnrs_from_fs_lt_sap = do_fnr_filter(fnrs, fs_lt_sap)
            systems = [int(row['source_system']) for row in fnrs]
            if fnrs_from_fs_lt_sap:
                # kast alle fnr ikke fra FS/LT/SAP
                for s in systems:
                    if s not in (fs_lt_sap):
                        remove.append(fnrs[systems.index(s)])
                fnrs = fnrs_from_fs_lt_sap

                # RH: Et forsøk på å tilpasse koden under ifm med lt-> sap...
                nr_fnrs = len(fnrs)
                if nr_fnrs > 1:
                    # kast > 30 dager gamle fnr hvis et kildesystem er
                    # gammelt, men pass på at det er minst et fnr igjen.
                    for tmp_fnr in fnrs:
                        ss = int(tmp_fnr['source_system'])
                        if nr_fnrs > 1 and ss in fs_lt_sap and \
                               self.pid2src_sys_age[pid].get(ss, 1) > 30:
                            nr_fnrs -= 1
                            remove.append(tmp_fnr)
                # if len(fnrs) == 2:
                #     # kast > 30 dager gamle fnr hvis et kildesystem er gammelt
                #     if self.pid2src_sys_age[pid].get(fs_lt_sap[0], 1) > 30:
                #         remove.append(fnrs[0])
                #     elif self.pid2src_sys_age[pid].get(fs_lt_sap[1], 1) > 30:
                #         remove.append(fnrs[1])

            # Kast ureg hvis vi har manual
            if len(do_fnr_filter(fnrs, (co.system_manual, co.system_ureg))) == 2:
                remove.append(fnrs[systems.index(int(co.system_ureg))])
        for row in remove:
            log_rem.person_fnr(row['entity_id'], row['id_type'], row['source_system'])
            person.clear()
            person.find(row['entity_id'])
            # TODO: why is _delete_external_id hidden?
            person._delete_external_id(row['source_system'], row['id_type'])
            db.commit()

    def remove_old_navn(self):
        logger.debug("remove_old_navn")
        relevant_src_sys = [int(s) for s in (co.system_fs, co.system_sap,
                                             co.system_lt, co.system_ureg,
                                             co.system_manual)]
        pid2names = {}
        name_variants = [x["code"] for x in person.list_person_name_codes()]
        for row in person.search_person_names(source_system=relevant_src_sys,
                                              name_variant=name_variants):
            pid2names.setdefault(int(row['person_id']), []).append(row)
                
        logger.debug("got %i names" % len(pid2names))
        remove = []
        fs_lt_sap = (int(co.system_lt), int(co.system_lt), int(co.system_fs))
        for pid, names in pid2names.items():
            systems = dict([(int(row['source_system']), 0)
                            for row in names]).keys()
            logger.debug("check_name pid=%s, sys=%s" % (pid, systems))
            remove_sys = []
            if int(co.system_ureg) in systems and [
                s for s in systems if s in fs_lt_sap]:
                # Har FS/LT/SAP, kaster ureg
                remove_sys.append(int(co.system_ureg))

            # RH: Et forsøk på å tilpasse koden under ifm med lt-> sap...
            nr_systems = len([s for s in systems if s in fs_lt_sap])
            if nr_systems > 1:
                # kast > 30 dager gamle navn hvis et kildesystem er
                # gammelt, men pass på at det er minst et fnr igjen.
                for ss in fs_lt_sap:
                    if nr_systems > 1 and self.pid2src_sys_age[pid].get(ss, 1) > 30:
                        remove_sys.append(ss)
                        nr_systems -= 1

            for s in remove_sys:
                for row in names:
                    if int(row['source_system']) == s:
                        remove.append(row)
                        
        for row in remove:
            log_rem.person_name(row['person_id'], row['name_variant'],
                                row['source_system'])
            person.clear()
            person.find(row['person_id'])
            # TODO: why is _delete_name hidden?
            person._delete_name(row['source_system'], row['name_variant'])
            db.commit()

    def __remove_old_entity_data(self, list_func, type_col, relevant_src_sys):
        # entity_address and entity_contact are very similar

        logger.debug("__remove_old_entity_data")
        relevant_src_sys = [int(s) for s in relevant_src_sys]

        pid2entity_data = {}
        for row in list_func():
            if int(row['source_system']) not in relevant_src_sys:
                continue
            pid2entity_data.setdefault(int(row['entity_id']), []).append(row)
        remove = []
        fs_lt_sap = (int(co.system_sap), int(co.system_lt), int(co.system_fs))
        for pid, data in pid2entity_data.items():
            data_types = dict([(int(row[type_col]), 0) for row in data]).keys()
            for dta_type in data_types:
                # map src_sys+dta_type combo to index in data
                system2dta = dict([(int(data[n]['source_system']), n)
                                   for n in range(len(data))
                                   if int(data[n][type_col]) == dta_type])
                # RH: Et forsøk på å tilpasse koden under ifm med lt-> sap...
                src_systems = [x for x in fs_lt_sap if system2dta.has_key(x)]
                nr_ss = len(src_systems)
                if nr_ss > 1:
                    for ss in src_systems:
                        if nr_ss > 1 and self.pid2src_sys_age[pid].get(ss, 1) > 30:
                            remove.append(data[system2dta[ss]])
                            nr_ss -= 1
                # if system2dta.has_key(fs_lt_sap[0]) and system2dta.has_key(fs_lt_sap[1]):
                #     # kast > 30 dager gamle entries hvis et kildesystem er gammelt
                #     if self.pid2src_sys_age[pid].get(fs_lt_sap[0], 1) > 30:
                #         remove.append(data[system2dta[fs_lt_sap[0]]])
                #     elif self.pid2src_sys_age[pid].get(fs_lt_sap[1], 1) > 30:
                #         remove.append(data[system2dta[fs_lt_sap[1]]])

            if [row for row in data if int(row['source_system']) in fs_lt_sap]:
                # Har FS/LT/SAP, kaster ureg
                for row in data:
                    if row['source_system'] == int(co.system_ureg):
                        remove.append(row)
        return remove

    def remove_old_address(self):
        logger.debug("remove_old_address")
        ea = Entity.EntityAddress(db)
        rel_ss = (co.system_fs, co.system_sap, co.system_lt,
                  co.system_ureg, co.system_manual)
        remove = self.__remove_old_entity_data(ea.list_entity_addresses,
                                               'address_type', rel_ss)
        for row in remove:
            log_rem.entity_address(
                row['entity_id'], row['source_system'],
                row['address_type'], row['address_text'],
                row['p_o_box'], row['postal_number'], row['city'],
                row['country'])
            ea.clear()
            ea.find(row['entity_id'])
            ea.delete_entity_address(row['source_system'], row['address_type'])
            db.commit()

    def remove_old_contact(self):
        logger.debug("remove_old_contact")
        # TBD: Throw away co.system_folk_uio_no if user har no account?
        ec = Entity.EntityContactInfo(db)
        rel_ss = (co.system_fs, co.system_sap, co.system_lt,
                  co.system_ureg, co.system_manual)
        remove = self.__remove_old_entity_data(ec.list_contact_info,
                                               'contact_type', rel_ss)
        for row in remove:
            log_rem.entity_contact(
                row['entity_id'], row['source_system'],
                row['contact_type'], row['contact_pref'],
                row['contact_value'], None) # row['description'])
            ec.clear()
            ec.find(row['entity_id'])
            ec.delete_contact_info(row['source_system'], row['contact_type'],
                                   row['contact_pref'])
            db.commit()

    def run(self):
        logger.debug("Starting CleanPersons.run")
        self.remove_old_persons()
        self.remove_old_person_affiliations()
        self.remove_old_fnr()
        self.remove_old_navn()
        self.remove_old_address()
        self.remove_old_contact()

class CleanUsers(object):
    def __init__(self, cp):
        self._cp = cp
        self.aid2affs = self.__get_aid2affs()
        
    def __get_aid2affs(self):
        ret = {}
        for row in account.list_accounts_by_type(filter_expired=False):
            ret.setdefault(int(row['account_id']), []).append(
                UserAff(row['ou_id'], row['affiliation'],
                        row['priority'], row['person_id']))
        return ret

    def remove_expired_affs(self):
        age_threshold = 60   # Days
        for aid, affs in self.aid2affs.items():
            # Sjekk om affs er gyldige
            paffs = self._cp.pid2affs[affs[0].person_id]
            valid_paffs = [p for p in paffs
                           if p.delete_age is None or p.delete_age < age_threshold]
            valid_ac_affs = []
            invalid_ac_affs = []
            for ac_aff in affs:
                if [p for p in valid_paffs
                    if p.ou == ac_aff.ou and p.aff == ac_aff.aff]:
                    valid_ac_affs.append(ac_aff)
                else:
                    invalid_ac_affs.append(ac_aff)

            add_affs = []
            remove_affs = []
            # Iterate over all invalid affs and determine action
            for ac_aff in invalid_ac_affs:
                if [a for a in valid_ac_affs if a.aff == ac_aff.aff]:
                    # has another account type of same affiliation, so
                    # it's safe to remove this one
                    pass
                else:
                    r = [p for p in valid_paffs if ac_aff.aff == p.aff]
                    if r:
                        # person had same affiliation for different
                        # ou, give this account_type to user
                        # TODO: should sort r
                        add_affs.append(r[0])
                    elif ac_aff.aff == co.affiliation_student and not [
                        a for a in valid_ac_affs if a.aff == co.affiliation_student]:
                        continue # Don't remove last student aff
                remove_affs.append(ac_aff)
            if not (add_affs or remove_affs):
                continue
            logger.debug("ac=%i, add=%s, remove=%s" % (aid, add_affs, remove_affs))

            if not dryrun:
                account.clear()
                account.find(aid)
                for a in add_affs:
                    log_rem.set_ac_type(aid, a.ou, a.aff)
                    account.set_account_type(a.ou, a.aff)
                for r in remove_affs:
                    log_rem.del_ac_type(aid, r.ou, r.aff)
                    account.del_account_type(r.ou, r.aff)
                db.commit()

    def run(self):
        logger.debug("Starting CleanUsers.run")
        self.remove_expired_affs()
        # We're lazy, so we re-fetch the mapping rather than keeping
        # track of it in remove_expired_affs
        self.aid2affs = self.__get_aid2affs()


class CleanQuarantines(object):
    def run(self):
        logger.debug("Starting CleanQuarantines.run")
        date_threshold = DateTime.now() - DateTime.DateTimeDelta(30)
        def filter_rows(rows):
            ret = []
            for row in rows:
                if (row['end_date'] is not None and
                    row['end_date'] < date_threshold):
                    ret.append(row)
            return ret
        eq = Entity.EntityQuarantine(db)
        # We use a two-step aproach as list_entity_quarantines don't
        # return enough data
        entity_ids = dict([(int(row['entity_id']), None) for row in
                           filter_rows(eq.list_entity_quarantines())])
        for entity_id in entity_ids.keys():
            eq.clear()
            eq.find(entity_id)
            for row in filter_rows(eq.get_entity_quarantine()):
                log_rem.del_entity_quarantine(
                    row['entity_id'], row['quarantine_type'],
                    row['creator_id'], row['description'],
                    row['create_date'], row['start_date'],
                    row['disable_until'], row['end_date'])
                eq.delete_entity_quarantine(row['quarantine_type'])
        db.commit()

class LogRemoved(object):
    """We want to log all info that we throw away"""
    # TODO: should use a separate logger
    
    def format_as_date(self, date):
        if date is not None:
            return date.strftime('%Y-%m-%d')
        return None
    
    def remove_member(self, pid, group_id):
        logger.debug("remove member %i from %i", pid, group_id)

    def nuke_person(self, person):
        logger.debug("person_remove pid=%i" % person.entity_id)

    def person_aff(self, pid, aff):
        logger.debug("aff_remove pid=%i, aff=%s" % (pid, aff))

    def person_fnr(self, pid, id_type, source_system):
        logger.debug("fnr_remove pid=%i, type=%i, src_sys=%i" % (
            pid, id_type, source_system))

    def person_name(self, pid, name_variant, source_system):
        logger.debug("name_remove pid=%i, name_var=%i, src_sys=%i" % (
            pid, name_variant, source_system))

    def entity_address(self, entity_id, source_system, address_type,
                       address_text, p_o_box, postal_number, city,
                       country):
        logger.debug("e_addr_remove eid=%i, src_sys=%i, adr_type=%i, at=%s, pb=%s, "
                     "pn=%s, ci=%s, co=%s" % (
            entity_id, source_system, address_type, address_text,
            p_o_box, postal_number, city, format_as_int(country)))

    def entity_contact(self, entity_id, source_system, contact_type,
                       contact_pref, contact_value, description):
        logger.debug("e_c_remove  eid=%i, src_sys=%i, c_type=%i, c_pref=%i, "
                     "c_v=%s, desc=%s" % (
            entity_id, source_system, contact_type, contact_pref,
            contact_value, description))

    def set_ac_type(self, account_id, ou, aff):
        logger.debug("set_ac_type aid=%i, ou=%i, aff=%i" % (account_id, ou, aff))

    def del_ac_type(self, account_id, ou, aff):
        logger.debug("del_ac_type aid=%i, ou=%i, aff=%i" % (account_id, ou, aff))

    def del_entity_quarantine(self, entity_id, quarantine_type,
                              creator_id, description, create_date,
                              start_date, disable_until, end_date):
        logger.debug("del_eq eid=%i, qtype=%i, creator=%i,  desc=%s, create=%s, "
                     "start=%s,disable=%s, end=%s" % (
            entity_id, quarantine_type, creator_id, description,
            self.format_as_date(create_date), self.format_as_date(start_date),
            self.format_as_date(disable_until), self.format_as_date(end_date)))

def run_expired_tasks():
    clean_quarantines = CleanQuarantines()
    clean_persons = CleanPersons()
    clean_users = CleanUsers(clean_persons)
    clean_persons.post_create(clean_users)

    for clean in (clean_quarantines, clean_users, clean_persons):
        clean.run()

def main():
    global dryrun, log_rem
    try:
        opts, args = getopt.getopt(
            sys.argv[1:], '', ['help', 'dryrun', 'plain', 'expired',
                               'changelog', 'bofh', 'password-age='])

    except getopt.GetoptError:
        usage(1)
    log_rem = LogRemoved()
    do_remove_bofh = do_remove_plain = do_process_log = dryrun = False
    clean_passwords = CleanPasswords(3600*24)
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
            clean_passwords.password_age = int(val)
        elif opt in ('--expired',):
            run_expired_tasks()
        else:
            usage()

    if do_remove_plain:
        clean_passwords.run()
    if do_process_log:
        CleanChangeLog().run()
    if do_remove_bofh:
        CleanBofh().run()

def usage(exitcode=0):
    print """Usage: [options]
    --help : this text
    --dryrun : don't do any changes to the db
    --plain : delete plaintext passwords
    --bofh : merge equal targets in auth_op_target
    --changelog : delete 'irrelevant' changelog entries
    --password-age seconds: delete passwords older than this (see --plain)
    --expired: remove expired affiliations, person names, account_types,
          quarantines etc.
    """
    sys.exit(exitcode)

if __name__ == '__main__':
    main()

