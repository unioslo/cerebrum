#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2003, 2004 University of Oslo, Norway
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

import hotshot, hotshot.stats
proffile  = 'hotshot.prof'

import getopt
import sys
import os
import pickle
import traceback
from time import localtime, strftime, time

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import PosixUser
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.modules.bofhd import errors
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uio import AutoStud
from Cerebrum.modules.no.uio import DiskQuota
from Cerebrum.modules.no.uio import PrinterQuotas
from Cerebrum.modules.templates.letters import TemplateHandler

db = Factory.get('Database')()
db.cl_init(change_program='process_students')
const = Factory.get('Constants')(db)
all_passwords = {}
derived_person_affiliations = {}
person_student_affiliations = {}
has_quota = {}
processed_students = {}
processed_accounts = {}
keep_account_home = {}
paid_paper_money = {}
account_id2fnr = {}

posix_user_obj = PosixUser.PosixUser(db)
account_obj = Factory.get('Account')(db)
person_obj = Factory.get('Person')(db)
group_obj = Factory.get('Group')(db)
disk_quota_obj = DiskQuota.DiskQuota(db)

debug = 0
max_errors = 50          # Max number of errors to accept in person-callback
posix_spreads = [int(const.Spread(s)) for s in cereconf.POSIX_SPREAD_CODES]

class AccountUtil(object):
    """Collection of methods that operate on a single account to make
    it conform to a profile """

    def create_user(fnr, profile):
        # dryruning this method is unfortunately a bit tricky
        assert not dryrun
        logger.info2("CREATE")
        person = Factory.get('Person')(db)
        try:
            person.find_by_external_id(const.externalid_fodselsnr, fnr,
                                       const.system_fs)
        except Errors.NotFoundError:
            logger.warn("OUCH! person %s not found" % fnr)
            return None

        try:
            first_name = person.get_name(const.system_cached, const.name_first)
        except Errors.NotFoundError:
            # This can happen if the person has no first name and no
            # authoritative system has set an explicit name_first variant.
            first_name = ""
        if not persons[fnr]['affs']:
            logger.error("The person %s has no student affiliations" % fnr)
            return None
        try:
            last_name = person.get_name(const.system_cached, const.name_last)
        except Errors.NotFoundError:
            # See above.  In such a case, name_last won't be set either,
            # but name_full will exist.
            last_name = person.get_name(const.system_cached, const.name_full)
            assert last_name.count(' ') == 0

        account = Factory.get('Account')(db)
        uname = account.suggest_unames(const.account_namespace,
                                       first_name, last_name)[0]
        account.populate(uname,
                         const.entity_person,
                         person.entity_id,
                         None,
                         default_creator_id, default_expire_date)
        password = account.make_passwd(uname)
        account.set_password(password)
        tmp = account.write_db()
        logger.debug("new Account, write_db=%s" % tmp)
        all_passwords[int(account.entity_id)] = [password, profile.get_brev()]
        as_posix = False
	for spread in profile.get_spreads():
	    if int(spread) in posix_spreads:
		as_posix = True
        accounts[int(account.entity_id)] = {'owner': fnr,
                                            'expire_date': None,
                                            'groups': [],
					    'spreads':[],
                                            'affs': [],
                                            'home': {},
                                            'gid': None,
                                            'quarantines': [],
                                            'disk_kvote': {}}
        AccountUtil.update_account(account.entity_id, fnr, profile, as_posix)
        return account.entity_id
    create_user=staticmethod(create_user)

    def _populate_account_affiliations(account_id, fnr):
        """Assert that the account has the same student affiliations as
        the person.  Will not remove the last student account affiliation
        even if the person has no such affiliation"""

        changes = []
        remove_idx = 1     # Do not remove last account affiliation
        account_ous = [ou for aff, ou in accounts[account_id]['affs']
                       if aff == const.affiliation_student]
        for aff, ou, status in persons[fnr]['affs']:
            assert aff == const.affiliation_student
            if not ou in account_ous:
                changes.append(('set_ac_type', (ou, const.affiliation_student)))
            else:
                account_ous.remove(ou)
                remove_idx = 0

        for ou in account_ous[remove_idx:]:
            changes.append(('del_ac_type', (ou, const.affiliation_student)))
        return changes
    _populate_account_affiliations=staticmethod(_populate_account_affiliations)
    
    def _handle_user_changes(changes, account_id, as_posix):
        if as_posix:
            user = posix_user_obj
        else:
            user = account_obj
        user.clear()
        if changes[0][0] == 'dfg' and accounts[account_id]['gid'] is None:
            uid = user.get_free_uid()
            shell = default_shell
            account_obj.clear()
            account_obj.find(account_id)
            user.populate(uid, changes[0][1], None, shell, 
                          parent=account_obj, expire_date=default_expire_date)
            user.write_db()
            logger.debug("Used dfg2: "+str(changes[0][1]))
            accounts[account_id]['groups'].append(changes[0][1])
            del(changes[0])
        else:
            user.find(account_id)

        for c_id, dta in changes:
            if c_id == 'dfg':
                user.gid_id = dta
                logger.debug("Used dfg: "+str(dta))
                accounts[account_id]['groups'].append(dta)
            elif c_id == 'expire':
                user.expire_date = dta
            elif c_id == 'disk':
                current_disk_id, disk_spread, new_disk = dta
                if current_disk_id is None:
                    logger.debug("Set home: %s" % new_disk)
                    homedir_id = user.set_homedir(
                        disk_id=new_disk, status=const.home_status_not_created)
                    user.set_home(disk_spread, homedir_id)
                    accounts[account_id]['home'][disk_spread] = (new_disk, homedir_id)
                else:
                    br = BofhdRequests(db, const)
                    # TBD: Is it correct to set requestee_id=None?
                    try:
                        br.add_request(None, br.batch_time,
                                       const.bofh_move_user, account_id,
                                       new_disk, state_data=int(disk_spread))
                    except errors.CerebrumError, e:
                        # Conflicting request or similiar
                        logger.warn(e)
            elif c_id == 'remove_autostud_quarantine':
                user.delete_entity_quarantine(dta)
            elif c_id == 'add_spread':
                user.add_spread(dta)
            elif c_id == 'add_person_spread':
                if (not hasattr(person_obj, 'entity_id') or
                    person_obj.entity_id != user.owner_id):
                    person_obj.clear()
                    person_obj.find(user.owner_id)
                person_obj.add_spread(dta)
            elif c_id == 'set_ac_type':
                user.set_account_type(dta[0], dta[1])
            elif c_id == 'del_ac_type':
                user.del_account_type(dta[0], dta[1])
            elif c_id == 'add_quarantine':
                start_at = strftime('%Y-%m-%d', localtime(dta[1] + time()))
                user.add_entity_quarantine(
                    dta[0], default_creator_id, 'automatic', start_at)
            elif c_id == 'disk_kvote':
                disk_quota_obj.set_quota(dta[0], quota=int(dta[1]))
            else:
                raise ValueError, "Unknown change: %s" % c_id
        tmp = user.write_db()
        logger.debug("write_db=%s" % tmp)
    _handle_user_changes=staticmethod(_handle_user_changes)

    def _update_group_memberships(account_id, profile):
        changes = []       # Changes is only used for debug output
        already_member = {}
        for group_id in accounts[account_id]['groups']:
            already_member[group_id] = True

        logger.debug("%i already in %s" % (account_id, repr(already_member)))
        for g in profile.get_grupper():
            if not already_member.has_key(g):
                group_obj.clear()
                group_obj.find(g)
                group_obj.add_member(account_id, const.entity_account,
                                 const.group_memberop_union)
                changes.append(("g_add", group_obj.group_name))
            else:
                del already_member[g]
        if remove_groupmembers:
            for g in already_member.keys():
                if autostud.pc.group_defs.get(g, {}).get('auto', None) == 'auto':
                    group_obj.clear()
                    group_obj.find(g)
                    group_obj.remove_member(account_id, const.group_memberop_union)
                    changes.append(('g_rem', group_obj.group_name))
        return changes
    _update_group_memberships=staticmethod(_update_group_memberships)

    def update_account(account_id, fnr, profile, as_posix):
        # First fill 'changes' with all needed modifications.  We will
        # only lookup databaseobjects if changes is non-empty.
        logger.info2(" UPDATE:%s" % account_id)
        processed_accounts[account_id] = True
        changes = []
        ac = accounts[account_id]
        if as_posix:
            gid = profile.get_dfg()
            # we no longer want to change the default-group
            if (ac['gid'] is None): # or ac['gid'] != gid):
                changes.append(('dfg', gid))

        if ac['expire_date'] != default_expire_date:
            changes.append(('expire', default_expire_date))

        # Set/change homedir
        user_spreads = [int(s) for s in profile.get_spreads()]

        # quarantine scope='student_disk' should affect all users with
        # home on a student-disk, or that doesn't have a home at all
        may_be_quarantined = False
        if not ac['home']:
            may_be_quarantined = True
        for s in autostud.pc.disk_spreads.keys():
            tmp = ac['home'].get(s, None)
            if (tmp and
                autostud.student_disk.has_key(int(tmp[0]))):
                may_be_quarantined = True

        current_disk_id = None
        for disk_spread in profile.get_disk_spreads():
            if not disk_spread in user_spreads:
                # The disk-spread in disk-defs was not one of the users spread
                continue 
            current_disk_id = ac['home'].get(disk_spread, [None])[0]
            if keep_account_home[fnr] and (move_users or current_disk_id is None):
                try:
                    new_disk = profile.get_disk(disk_spread, current_disk_id)
                except AutoStud.ProfileHandler.NoAvailableDisk, msg:
                    raise
                if current_disk_id != new_disk:
                    profile.notify_used_disk(old=current_disk_id, new=new_disk)
                    changes.append(('disk', (current_disk_id, disk_spread, new_disk)))
                    current_disk_id = new_disk

        if autostud.pc.using_disk_kvote:
            for spread, (disk_id, homedir_id) in accounts[
                account_id]['home'].items():
                if not autostud.student_disk.has_key(disk_id):
                    # Setter kun kvote på student-disker
                    continue
                quota = profile.get_disk_kvote(disk_id)
                if ac['disk_kvote'].get(homedir_id, None) != quota:
                    changes.append(('disk_kvote', (homedir_id, quota)))
                    ac['disk_kvote'][homedir_id] = quota

        # TBD: Is it OK to ignore date on existing quarantines when
        # determining if it should be added?
        tmp = []
        for q in profile.get_quarantines():
            if q['scope'] == 'student_disk' and not may_be_quarantined:
                continue
            tmp.append(int(q['quarantine']))
            if with_quarantines and not int(q['quarantine']) in ac['quarantines']:
                changes.append(('add_quarantine', (q['quarantine'], q['start_at'])))

        # Remove auto quarantines
        for q in (const.quarantine_auto_inaktiv,
                  const.quarantine_auto_emailonly):
            if (int(q) in ac['quarantines'] and
                int(q) not in tmp):
                changes.append(("remove_autostud_quarantine", q))

        # Populate spreads
        has_acount_spreads = ac['spreads']
        has_person_spreads = persons[fnr]['spreads']
        for spread in profile.get_spreads():
            if spread.entity_type == const.entity_account:
                if not int(spread) in has_acount_spreads:
                    changes.append(('add_spread', spread))
            elif spread.entity_type == const.entity_person:
                if not int(spread) in has_person_spreads:
                    changes.append(('add_person_spread', spread))
                    has_person_spreads.append(int(spread))

        changes.extend(AccountUtil._populate_account_affiliations(account_id, fnr))
        # We have now collected all changes that would need fetching of
        # the user object.
        if changes:
            AccountUtil._handle_user_changes(changes, account_id, as_posix)

        changes.extend(AccountUtil._update_group_memberships(account_id, profile))

        if changes:
            logger.debug("Changes [%i/%s]: %s" % (
                account_id, fnr, repr(changes)))
    update_account = staticmethod(update_account)

class RecalcQuota(object):
    """Collection of methods to calculate proper quota settings for a
    person"""

    def _recalc_quota_callback(person_info):
        fnr = fodselsnr.personnr_ok("%06d%05d" % (int(person_info['fodselsdato']),
                                                  int(person_info['personnr'])))
        logger.set_indent(0)
        logger.debug("Callback for %s" % fnr)
        logger.set_indent(3)
        logger.debug(logger.pformat(_filter_person_info(person_info)))
        pq = PrinterQuotas.PrinterQuotas(db)
        group = Factory.get('Group')(db)

        for account_id in students.get(fnr, {}).keys():
            groups = []
            try:
                profile = autostud.get_profile(
                    person_info, member_groups=persons[fnr]['groups'])
                quota = profile.get_pquota()
            except AutoStud.ProfileHandler.NoMatchingQuotaSettings, msg:
                logger.warn("Error for %s: %s" %  (fnr, msg))
                logger.set_indent(0)
                return
            except AutoStud.ProfileHandler.NoMatchingProfiles, msg:
                logger.warn("Error for %s: %s" %  (fnr, msg))
                logger.set_indent(0)
                return
            except Errors.NotFoundError, msg:
                logger.warn("Error for %s: %s" %  (fnr, msg))
                logger.set_indent(0)
                return
            logger.debug("Setting %s as pquotas for %s" % (quota, account_id))
            if dryrun:
                continue
            pq.clear()
            try:
                pq.find(account_id)
            except Errors.NotFoundError:
                # The quota update script should be ran just after this script
                if quota['weekly_quota'] == 'UL':
                    init_quota = 0
                else:
                    init_quota = int(quota['initial_quota']) - int(quota['weekly_quota'])
                pq.populate(account_id, init_quota, 0, 0, 0, 0, 0, 0)
            if quota['weekly_quota'] == 'UL' or profile.get_printer_kvote_fritak():
                pq.has_printerquota = 'F'
            else:
                pq.has_printerquota = 'T'
                pq.weekly_quota = quota['weekly_quota']
                pq.max_quota = quota['max_quota']
                pq.termin_quota = quota['termin_quota']
            if paper_money_file:
                if (not profile.get_printer_betaling_fritak() and
                    not paid_paper_money.get(fnr, False)):
                    logger.debug("didn't pay, max_quota=0 for %s " % fnr)
                    pq.max_quota = 0
                    pq.printer_quota = 0
            pq.write_db()
            has_quota[int(account_id)] = True
        logger.set_indent(0)
        # We commit once for each person to avoid locking too many db-rows
        if not dryrun:
            db.commit()
    _recalc_quota_callback=staticmethod(_recalc_quota_callback)

    def recalc_pq_main():
        raise SystemExit("--recalc-quota is obsolete and will be removed shortly")
        if paper_money_file:
            for p in AutoStud.StudentInfo.GeneralDataParser(paper_money_file, 'betalt'):
                fnr = fodselsnr.personnr_ok("%06d%05d" % (int(p['fodselsdato']),
                                                          int(p['personnr'])))
                paid_paper_money[fnr] = True
        autostud.start_student_callbacks(student_info_file,
                                         RecalcQuota._recalc_quota_callback)
        # Set default_quota for the rest that already has quota
        pq = PrinterQuotas.PrinterQuotas(db)
        dv = autostud.pc.default_values
        for row in pq.list_quotas():
            account_id = int(row['account_id'])
            if row['has_printerquota'] == 'F' or has_quota.get(account_id, False):
                continue
            logger.debug("Default quota for %i" % account_id)
            # TODO: sjekk om det er nødvendig med oppdatering før vi gjør find.
            pq.clear()
            try:
                pq.find(account_id)
            except Errors.NotFoundError:
                logger.error("not found: %i, recently deleted?" % account_id)
                continue
            pq.weekly_quota = dv['print_uke']
            pq.max_quota = dv['print_max_akk']
            pq.termin_quota = dv['print_max_sem']
            if paper_money_file:
                if not account_id2fnr.has_key(account_id):
                    # probably a deleted user
                    logger.debug("account_id %i not in account_id2fnr, deleted?" % account_id)
                elif not paid_paper_money.get(account_id2fnr[account_id], False):
                    logger.debug("didn't pay, max_quota=0 for %i " % account_id)
                    pq.max_quota = 0
                    pq.printer_quota = 0
            pq.write_db()
        if not dryrun:
            db.commit()
        else:
            db.rollback()
    recalc_pq_main=staticmethod(recalc_pq_main)

class BuildAccounts(object):
    """Collection of methods for updating/creating student users for
    all persons"""

    def _process_students_callback(person_info):
        global max_errors
        try:
            BuildAccounts._process_student(person_info)
        except:
            max_errors -= 1
            if max_errors < 0:
                raise
            trace = "".join(traceback.format_exception(
                sys.exc_type, sys.exc_value, sys.exc_traceback))
            logger.error("Unexpected error: %s" % trace)
            db.rollback()
    _process_students_callback=staticmethod(_process_students_callback)

    def _process_student(person_info):
        fnr = fodselsnr.personnr_ok("%06d%05d" % (int(person_info['fodselsdato']),
                                                  int(person_info['personnr'])))
        logger.set_indent(0)
        logger.debug("Callback for %s" % fnr)

        logger.set_indent(3)
        logger.debug(logger.pformat(_filter_person_info(person_info)))
        if not persons.has_key(fnr):
            logger.warn("(person) not found error for %s" % fnr)
            logger.set_indent(0)
            return
        try:
            profile = autostud.get_profile(person_info, member_groups=persons[fnr]['groups'],
                                           person_affs=persons[fnr]['affs'])
            logger.debug(profile.matcher.debug_dump())
        except AutoStud.ProfileHandler.NoMatchingProfiles, msg:
            logger.warn("No matching profile error for %s: %s" %  (fnr, msg))
            logger.set_indent(0)
            return
        
        processed_students[fnr] = 1
        keep_account_home[fnr] = profile.get_build()['home']
        if fast_test:
            logger.debug(profile.debug_dump())
            # logger.debug("Disk: %s" % profile.get_disk())
            logger.set_indent(0)
            return
        try:
            _debug_dump_profile_match(profile, fnr)
            if dryrun:
                logger.set_indent(0)
                return
            pinfo = persons.get(fnr, None)
            if pinfo is None:
                logger.warn("Unknown person %s" % fnr)
                return
            if (create_users and not pinfo['stud_ac'] and
                profile.get_build()['action']):
                if pinfo['other_ac']:
                    logger.debug("Has active non-student account, skipping")
                    return
                elif pinfo['reserved_ac']:  # has a reserved account
                    logger.debug("using reserved: %s" % pinfo['reserved_ac'])
                    BuildAccounts._update_persons_accounts(
                        profile, fnr, [ pinfo['reserved_ac'][0] ])
                else:
                    account_id = AccountUtil.create_user(fnr, profile)
                    if account_id is None:
                        logger.set_indent(0)
                        return
                # students.setdefault(fnr, {})[account_id] = []
            elif update_accounts and pinfo['stud_ac']:
                BuildAccounts._update_persons_accounts(
                    profile, fnr, pinfo['stud_ac'])
        except AutoStud.ProfileHandler.NoAvailableDisk, msg:
            logger.error("  Error for %s: %s" % (fnr, msg))
        logger.set_indent(0)
        # We commit once for each person to avoid locking too many db-rows
        if not dryrun:
            db.commit()
    _process_student=staticmethod(_process_student)
    
    def _update_persons_accounts(profile, fnr, account_ids):
        """Update the account by checking that group, disk and
        affiliations are correct.  For existing accounts, account_info
        should be filled with affiliation info """

        # dryruning this method is unfortunately a bit tricky
        assert not dryrun
        
        as_posix = False
        for spread in profile.get_spreads():  # TBD: Is this check sufficient?
            if str(spread).startswith('NIS'):
                as_posix = True
        for account_id in account_ids:
            AccountUtil.update_account(account_id, fnr, profile, as_posix)
    _update_persons_accounts=staticmethod(_update_persons_accounts)

    def update_accounts_main():
        autostud.start_student_callbacks(student_info_file,
                                         BuildAccounts._process_students_callback)
        logger.set_indent(0)
        logger.info("student_info_file processed")
        if not dryrun:
            db.commit()
            logger.info("making letters")
            if only_dump_to is not None:
                f = open(only_dump_to, 'w')
                pickle.dump(all_passwords, f)
                f.close()
            else:
                make_letters()
        else:
            db.rollback()
        BuildAccounts._process_unprocessed_students()
    update_accounts_main=staticmethod(update_accounts_main)

    def _process_unprocessed_students():
        """Unprocessed students didn't match a profile, or didn't get a
        callback at all"""
        # TBD: trenger vi skille på de?
        logger.info("process_unprocessed_students")

        for fnr, pinfo in persons.items(): 
            if not pinfo['stud_ac']:
                continue
            if not processed_students.has_key(fnr):
                d, p = fodselsnr.del_fnr(fnr)
                BuildAccounts._process_students_callback({
                    'fodselsdato': d,
                    'personnr': p})
    _process_unprocessed_students=staticmethod(_process_unprocessed_students)

def start_process_students(recalc_pq=False, update_create=False):
    global autostud, accounts, persons

    logger.info("process_students started")
    autostud = AutoStud.AutoStud(db, logger, debug=debug, cfg_file=studconfig_file,
                                 studieprogs_file=studieprogs_file,
                                 emne_info_file=emne_info_file,
                                 ou_perspective=ou_perspective)
    logger.info("config processed")
    persons, accounts = get_existing_accounts()
    logger.info("got student accounts")
    if recalc_pq:
        RecalcQuota.recalc_pq_main()
    elif update_create:
        BuildAccounts.update_accounts_main()
    logger.info("process_students finished")

def bootstrap():
    global default_creator_id, default_expire_date, default_shell
    for t in ('PRINT_PRINTER', 'PRINT_BARCODE', 'AUTOADMIN_LOG_DIR',
              'TEMPLATE_DIR', 'PRINT_LATEX_CMD', 'PRINT_DVIPS_CMD',
              'PRINT_LPR_CMD'):
        if not getattr(cereconf, t):
            logger.warn("%s not set, check your cereconf file" % t)
    account = Factory.get('Account')(db)
    account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    default_creator_id = account.entity_id
    default_expire_date = None
    default_shell = const.posix_shell_bash

def get_existing_accounts():
    """Prefetch data about persons and their accounts to avoid
    multiple SQL queries for each callback.  Returns:

    persons = {'fnr': {'affs': [(aff, ou, status)],
                       'stud_ac': [account_id], 'other_ac': [account_id],
                       'reserved_ac': [account_id],
                       'spreads': [spread_id],
                       'groups': [group_id]}}
    accounts = {'account_id': {'owner: fnr, 'reserved': boolean,
                               'gid': group_id, 'quarantines': [quarantine_id],
                               'spreads': [spread_id], 'groups': [group_id],
                               'affs': [(aff, ou)],
                               'expire_date': expire_date,
                               'home': {spread: (disk_id, homedir_id)}}}
    """
    persons = {}

    logger.info("In get_existing_accounts")
    if fast_test:
        return {}, {}

    logger.info("Listing persons")
    pid2fnr = {}
    for row in person_obj.list_external_ids(id_type=const.externalid_fodselsnr):
        if (row['source_system'] == int(const.system_fs) or
            (not pid2fnr.has_key(int(row['person_id'])))):
            pid2fnr[int(row['person_id'])] = row['external_id']
            persons[row['external_id']] = {
                'affs': [], 'stud_ac': [], 'other_ac': [], 'reserved_ac': [], 'spreads': [],
                'groups': []}

    for row in person_obj.list_affiliations(
        source_system=const.system_fs,
        affiliation=const.affiliation_student,
        fetchall=False):
        tmp = pid2fnr.get(int(row['person_id']), None)
        if tmp is not None:
            persons[tmp]['affs'].append(
                (int(row['affiliation']), int(row['ou_id']), int(row['status'])))

    #
    # Hent ut info om eksisterende og reserverte konti
    #
    logger.info("Listing accounts...")
    accounts = {}
    for row in account_obj.list(filter_expired=True, fetchall=False):
        if not row['owner_id'] or not pid2fnr.has_key(int(row['owner_id'])):
            continue
        accounts[int(row['account_id'])] = {
            'owner': pid2fnr[int(row['owner_id'])],
            'expire_date': row['expire_date'],
            'spreads': [],
            'gid': None,
            'reserved': False,
            'home': {},
            'groups': [],
            'affs': [],
            'quarantines': [],
            'disk_kvote': {}}
    # PosixGid
    for row in posix_user_obj.list_posix_users():
        tmp = accounts.get(int(row['account_id']), None)
        if tmp is not None:
            tmp['gid'] = int(row['gid'])
    # Reserved users
    for row in account_obj.list_reserved_users(fetchall=False):
        tmp = accounts.get(int(row['account_id']), None)
        if tmp is not None:
            tmp['reserved'] = True
    # quarantines
    for row in account_obj.list_entity_quarantines(
        entity_types=const.entity_account):
        tmp = accounts.get(int(row['entity_id']), None)
        if tmp is not None:
            tmp['quarantines'].append(int(row['quarantine_type']))
    # Disk kvote
    for row in disk_quota_obj.list_quotas():
        tmp = accounts.get(int(row['account_id']), None)
        if tmp is not None:
            tmp['disk_kvote'][int(row['homedir_id'])] = row['quota']
    # Spreads
    for spread_id in autostud.pc.spread_defs:
        spread = const.Spread(spread_id)
        if spread.entity_type == const.entity_account:
            is_account_spread = True
        elif spread.entity_type == const.entity_person:
            is_account_spread = False
        else:
            logger.warn("Unknown spread type")
            continue
        for row in account_obj.list_all_with_spread(spread_id):
            if is_account_spread:
                tmp = accounts.get(int(row['entity_id']), None)
            else:
                tmp = persons.get(
                    pid2fnr.get(int(row['entity_id']), None), None)
            if tmp is not None:
                tmp['spreads'].append(spread_id)
    # Account homes
    for row in account_obj.list_account_home():
        tmp = accounts.get(int(row['account_id']), None)
        if tmp is not None and row['disk_id']:
            tmp['home'][int(row['home_spread'])] = (
                int(row['disk_id']), int(row['homedir_id']))
            
    # Group memberships (TODO: currently only handles union members)
    for group_id in autostud.pc.group_defs.keys():
        group_obj.clear()
        group_obj.find(group_id)
        for row in group_obj.list_members(member_type=const.entity_account)[0]:
            tmp = accounts.get(int(row[1]), None)    # Col 1 is member_id
            if tmp is not None:
                tmp['groups'].append(group_id)
        for row in group_obj.list_members(member_type=const.entity_person)[0]:
            tmp = persons.get(int(row[1]), None)    # Col 1 is member_id
            if tmp is not None:
                tmp['groups'].append(group_id)
    # Affiliations
    for row in account_obj.list_accounts_by_type(
        affiliation=const.affiliation_student, filter_expired=True,
        fetchall=False):
        tmp = accounts.get(int(row['account_id']), None)
        if tmp is not None:
            tmp['affs'].append([ int(row['affiliation']) , int(row['ou_id'])])

    for ac_id, tmp in accounts.items():
        if tmp['reserved']:
            persons[ accounts[ac_id]['owner'] ]['reserved_ac'].append(ac_id)
            
        elif int(const.affiliation_student) in [aff for aff, ou in tmp['affs']]:
            persons[ accounts[ac_id]['owner'] ]['stud_ac'].append(ac_id)
        else:
            persons[ accounts[ac_id]['owner'] ]['other_ac'].append(ac_id)

    logger.info(" found %i persons and %i accounts" % (len(persons), len(accounts)))
    #logger.debug("Persons: \n"+"\n".join([str(y) for y in persons.items()]))
    #logger.debug("Accounts: \n"+"\n".join([str(y) for y in accounts.items()]))
    return persons, accounts

def make_letters(data_file=None, type=None, range=None):
    if data_file is not None:  # Load info on letters to print from file
        f=open(data_file, 'r')
        tmp_passwords = pickle.load(f)
        f.close()
        for r in [int(x) for x in range.split(",")]:
            tmp = tmp_passwords["%s-%i" % (type, r)]
            tmp.append(r)
            all_passwords[tmp[0]] = tmp[1]
    person = Factory.get('Person')(db)
    account = Factory.get('Account')(db)
    dta = {}
    logger.debug("Making %i letters" % len(all_passwords))
    any_letter = None
    for account_id in all_passwords.keys():
        try:
            account.clear()
            account.find(account_id)
            person.clear()
            person.find(account.owner_id)  # should be account.owner_id
        except Errors.NotFoundError:
            logger.warn("NotFoundError for account_id=%s" % account_id)
            continue
        tpl = {}
        address = person.get_entity_address(source=const.system_fs,
                                            type=const.address_post)
        if not address:
            logger.warn("Bad address for %s" % account_id)
            continue
        address = address[0]
        alines = address['address_text'].split("\n")+[""]
        fullname = person.get_name(const.system_cached, const.name_full)
        tpl['address_line1'] = fullname
        tpl['address_line2'] = alines[0]
        tpl['address_line3'] = alines[1]
        tpl['zip'] = address['postal_number']
        tpl['city'] = address['city']
        tpl['country'] = address['country']

        tpl['uname'] = account.account_name
        tpl['password'] =  all_passwords[account_id][0]
        tpl['birthdate'] = person.birth_date.strftime('%Y-%m-%d')
        tpl['fullname'] =  fullname
        tmp = person.get_external_id(id_type=const.externalid_fodselsnr,
                                     source_system=const.system_fs)
        tpl['birthno'] =  tmp[0]['external_id']
        tpl['emailadr'] =  "TODO"  # We probably don't need to support this...
        tpl['account_id'] = account_id
        dta[account_id] = tpl
        if any_letter is None:
            any_letter = all_passwords[account_id][1]
    # Print letters sorted by zip by default. Override with 'order_by' in 
    # studconfig. order_by must have the same value in ALL letters.
    # Each template type has its own letter number sequence
    order_by = 'zip'
    if any_letter is not None and any_letter.has_key('order_by'):
        order_by = any_letter['order_by']
    keys = dta.keys()
    keys.sort(lambda x,y: cmp(dta[x][order_by], dta[y][order_by]))
    letter_info = {}
    files = {}
    tpls = {}
    counters = {}
    printers = {}
    for account_id in keys:
        if not dta[account_id]['zip'] or dta[account_id]['country']:
            # TODO: Improve this check, which is supposed to skip foreign addresses
            logger.warn("Not sending abroad: %s" % dta[account_id]['uname'])
            continue
        
        password, brev_profil = all_passwords[account_id][:2]
        letter_type = "%s.%s" % (brev_profil['mal'], brev_profil['type'])
        if not files.has_key(letter_type):
            files[letter_type] = file("letter-%i-%s" % (time(), letter_type), "w")
            tpls[letter_type] = TemplateHandler(
                'no_NO/letter', brev_profil['mal'], brev_profil['type'])
            if tpls[letter_type]._hdr is not None:
                files[letter_type].write(tpls[letter_type]._hdr)
            printers[letter_type] = cereconf.PRINT_PRINTER
            if brev_profil.has_key('printer'):
                printers[letter_type] = brev_profil['printer']
            counters[letter_type] = 1
        if data_file is not None:
            dta[account_id]['lopenr'] = all_passwords[account_id][2]
            if not os.path.exists("barcode_%s.eps" % account_id):
                make_barcode(account_id)
        else:
            dta[account_id]['lopenr'] = counters[letter_type]
            letter_info["%s-%i" % (brev_profil['mal'], counters[letter_type])] = \
                                [account_id, [password, brev_profil, counters[letter_type]]]
            # We allways create a barcode file, this is not strictly
            # neccesary
            make_barcode(account_id)
        dta[account_id]['barcode'] = os.path.realpath('barcode_%s.eps' %  account_id)
        files[letter_type].write(tpls[letter_type].apply_template(
            'body', dta[account_id], no_quote=('barcode',)))
        counters[letter_type] += 1
    # Save passwords for created users so that letters may be
    # re-printed at a later time in case of print-jam etc.
    if data_file is None:
        f=open("letters.info", 'w')
        pickle.dump(letter_info, f)
        f.close()
    # Close files and spool jobs
    for letter_type in files.keys():
        if tpls[letter_type]._footer is not None:
            files[letter_type].write(tpls[letter_type]._footer)
        files[letter_type].close()
        try:
            tpls[letter_type].spool_job(files[letter_type].name,
                                        tpls[letter_type]._type,
                                        printers[letter_type],
                                        skip_lpr=skip_lpr)
            os.unlink(tpls[letter_type].logfile)
        except IOError, msg:
            print msg

def make_barcode(account_id):
    ret = os.system("%s -e EAN -E -n -b %012i > barcode_%s.eps" % (
        cereconf.PRINT_BARCODE, account_id, account_id))
    if ret:
        logger.warn("Bardode returned %s" % ret)

def _filter_person_info(person_info):
    """Makes debugging easier by removing some of the irrelevant
    person-information."""
    ret = {}
    filter = {
        'opptak': ['studieprogramkode', 'studierettstatkode'],
        'privatist_emne': ['emnekode'],
        'privatist_studieprogram': ['studieprogramkode'],
        'fagperson': [],
        'alumni': ['studieprogramkode', 'studierettstatkode'],
        'evu': ['etterutdkurskode'],
        'tilbud': ['studieprogramkode']
        }
    for info_type in person_info.keys():
        if info_type in ('fodselsdato', 'personnr'):
            continue
        for f in filter:
            if info_type == f:
                for dta in person_info[info_type]:
                    ret.setdefault(info_type, []).append(
                        dict([(k, dta[k]) for k in filter[info_type]]))
        if not ret.has_key(info_type):
            ret[info_type] = person_info[info_type]
    return ret

def _debug_dump_profile_match(profile, fnr):
    # TODO:  Hører ikke dette hjemme i ProfileHandler?
    # Note that we don't pass current_disk to get_disks() here.
    # Thus this value may differ from the one used during an
    # update
    try:
        dfg = profile.get_dfg()       # dfg is only mandatory for PosixGroups
    except AutoStud.ProfileHandler.NoDefaultGroup:
        dfg = "<no_dfg>"
    if keep_account_home[fnr]:
        # This will throw an exception if <build home="true">, and
        # we can't get a disk.  This is what we want
        disk = []
        spreads = [int(s) for s in profile.get_spreads()]
        for s in profile.get_disk_spreads():
            if s in spreads:
                disk.append((profile.get_disk(s), s))
        if not disk:
            raise AutoStud.ProfileHandler.NoAvailableDisk(
                "No disk matches profiles")
    else:
        disk = "<no_home>"
    logger.debug("disk=%s, dfg=%s, fg=%s sko=%s" % \
                 (str(disk), dfg,
                  profile.get_grupper(),
                  profile.get_stedkoder()))

def validate_config():
    AutoStud.AutoStud(db, logger, debug=debug, cfg_file=studconfig_file,
                      studieprogs_file=studieprogs_file,
                      emne_info_file=emne_info_file)

def list_noncallback_users(fname):
    """Dump accounts on student-disk that did not get a callback
    resulting in update_account."""
    
    f = file(fname, 'w')
    on_student_disk = {}
    for row in account_obj.list_account_home():
        if autostud.student_disk.has_key(int(row['disk_id'] or 0)):
            on_student_disk[int(row['account_id'])] = True

    for ac_id in on_student_disk.keys():
        if processed_accounts.has_key(ac_id):
            continue
        f.write("%i\n" % ac_id)
    f.close()

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'dcus:C:S:e:p:G:',
                                   ['debug', 'create-users', 'update-accounts',
                                    'student-info-file=', 'only-dump-results=',
                                    'studconfig-file=', 'fast-test', 'with-lpr',
                                    'workdir=', 'type=', 'reprint=',
                                    'ou-perspective=',
                                    'emne-info-file=', 'move-users',
                                    'recalc-pq', 'studie-progs-file=',
                                    'paper-file=',
                                    'remove-groupmembers'
                                    'dryrun', 'validate',
                                    'with-quarantines'])
    except getopt.GetoptError, e:
        usage(str(e))
    global debug, fast_test, create_users, update_accounts, logger, skip_lpr
    global student_info_file, studconfig_file, only_dump_to, studieprogs_file, \
           dryrun, emne_info_file, move_users, remove_groupmembers, \
           workdir, paper_money_file, ou_perspective, with_quarantines

    skip_lpr = True       # Must explicitly tell that we want lpr
    update_accounts = create_users = recalc_pq = dryrun = move_users = False
    remove_groupmembers = validate = with_quarantines = False
    ou_perspective = None
    fast_test = False
    workdir = None
    range = None
    only_dump_to = None
    paper_money_file = None         # Default: don't check for paid paper money
    to_stdout = False
    log_level = AutoStud.Util.ProgressReporter.DEBUG
    non_callback_fname = None
    for opt, val in opts:
        if opt in ('-d', '--debug'):
            debug += 1
            log_level += 1
            to_stdout = True
        elif opt in ('-c', '--create-users'):
            create_users = True
        elif opt in ('-u', '--update-accounts'):
            update_accounts = True
        elif opt in ('-s', '--student-info-file'):
            student_info_file = val
        elif opt in ('-e', '--emne-info-file'):
            emne_info_file = val
        elif opt in ('-p', '--paper-file'):
            paper_money_file = val
        elif opt in ('-S', '--studie-progs-file'):
            studieprogs_file = val
        elif opt in ('--recalc-pq',):
            recalc_pq = True
        elif opt in ('--remove-groupmembers',):
            remove_groupmembers = True
        elif opt in ('--with-quarantines',):
            with_quarantines = True
        elif opt in ('--move-users',):
            move_users = True
        elif opt in ('-C', '--studconfig-file'):
            studconfig_file = val
        elif opt in ('-G',):
            non_callback_fname = val
        elif opt in ('--fast-test',):  # Internal debug use ONLY!
            fast_test = True
        elif opt in ('--ou-perspective',):
            ou_perspective = const.OUPerspective(val)
            int(ou_perspective)   # Assert that it is defined
        elif opt in ('--only-dump-results',):
            only_dump_to = val
        elif opt in ('--dryrun',):
            dryrun = True
        elif opt in ('--validate',):
            validate = True
            to_stdout = True
            workdir = '.'
            log_level = AutoStud.Util.ProgressReporter.INFO
        elif opt in ('--with-lpr',):
            skip_lpr = False
        elif opt in ('--workdir',):
            workdir = val
        elif opt in ('--type',):
            type = val
        elif opt in ('--reprint',):
            range = val
            to_stdout = True
        else:
            usage("Unimplemented option: " + opt)

    if recalc_pq and (update_accounts or create_users):
        raise ValueError, "recalc-pq cannot be combined with other operations"

    if workdir is None:
        workdir = "%s/ps-%s.%i" % (cereconf.AUTOADMIN_LOG_DIR,
                                   strftime("%Y-%m-%d", localtime()),
                                   os.getpid())
        os.mkdir(workdir)
    os.chdir(workdir)
    logger = AutoStud.Util.ProgressReporter("%s/run.log.%i"
                                            % (workdir, os.getpid()),
                                            stdout=to_stdout,
                                            loglevel=log_level)
    bootstrap()
    if validate:
        validate_config()
        sys.exit(0)
    if range is not None:
        make_letters("letters.info", type=type, range=val)
        return

    if not (recalc_pq or update_accounts or create_users or
            non_callback_fname):
        usage("No action selected")

    start_process_students(recalc_pq=recalc_pq,
                           update_create=(create_users or non_callback_fname))
    if non_callback_fname:
        list_noncallback_users(non_callback_fname)
    
def usage(error=None):
    if error:
        print "Error:", error
    print """Usage: process_students.py
    Actions:
      -c | --create-user : create new users
      -u | --update-accounts : update existing accounts
      --reprint range:  Re-print letters in case of paper-jam etc. (comma
        separated)
      --recalc-pq : recalculate printerquota settings (does not update
        quota).  Cannot be combined with -c/-u
      -G file : Dump account_id for users on student disks that did not
       get a callback.

    Input files:
      -s | --student-info-file file:
      -e | --emne-info-file file:
      -C | --studconfig-file file:
      -S | --studie-progs-file file:
      -p | --paper-file file: check for paid-quota only done if set

    Other settings:
      --only-dump-results file: just dump results with pickle without
        entering make_letters
      --workdir dir:  set workdir for --reprint
      --with-lpr: Spool the file with new user letters to printer

    Action limiters/enablers:
      --remove-groupmembers: remove groupmembers if profile says so
      --move-users: move users if profile says so
      --with-quarantines: Enables quarantine settings

    Misc:
      -d | --debug: increases debug verbosity
      --ou-perspective code_str: set ou_perspective (default: perspective_fs)
      --dryrun: don't do any changes to the database.  This can be used
        to get an idea of what changes a normal run would do.  TODO:
        also dryrun some parts of update/create user.
      --validate: parse the configuration file and report any errors,
        then exit.
      --type type: set type (=the mal attribute to <brev> in studconfig.xml)
        for --reprint

To create new users:
  ./contrib/no/uio/process_students.py -C .../studconfig.xml -S .../studieprogrammer.xml -s .../merged_persons.xml -c

To reprint letters of a given type:
  ./contrib/no/uio/process_students.py --workdir tmp/ps-2003-09-25.1265 --type new_stud_account --reprint 1,2
    """
    sys.exit(0)

if __name__ == '__main__':
    #logger = AutoStud.Util.ProgressReporter(
    #    None, stdout=1, loglevel=AutoStud.Util.ProgressReporter.DEBUG)
    #AutoStud.AutoStud(db, logger, debug=3,
    #                  cfg_file="/home/runefro/usit/cerebrum/uiocerebrum/etc/config/studconfig.xml")

    if False:
        print "Profilerer..."
        prof = hotshot.Profile(proffile)
        prof.runcall(main)                # profiler hovedprogrammet
        prof.close()
    else:
        main()

# arch-tag: 99817548-9213-4dc3-8d03-002fc6a2f138
