#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2003-2011 University of Oslo, Norway
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

"""To create new users:
        ./contrib/no/uio/process_students.py -C .../studconfig.xml
        -S .../studieprogrammer.xml -s .../merged_persons.xml -c
"""

from __future__ import unicode_literals
from __future__ import print_function

import hotshot
import hotshot.stats

import argparse
import sys
import os
import traceback
from time import localtime, strftime, time
import pprint

from mx.DateTime import now

import cereconf

import Cerebrum.logutils
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import ParserContext
from Cerebrum.modules.bofhd_requests.request import BofhdRequests
from Cerebrum.modules.bofhd import errors
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uio import AutoStud
from Cerebrum.modules.disk_quota import DiskQuota
from Cerebrum.modules.no.uio import PrinterQuotas

proffile = 'hotshot.prof'

db = Factory.get('Database')()
db.cl_init(change_program='process_students')
const = Factory.get('Constants')(db)
derived_person_affiliations = {}
person_student_affiliations = {}
has_quota = {}
processed_students = {}
processed_accounts = {}
keep_account_home = {}
paid_paper_money = {}
account_id2fnr = {}
posix_tables = False

posix_user_obj = Factory.get('PosixUser')(db)
account_obj = Factory.get('Account')(db)
person_obj = Factory.get('Person')(db)
group_obj = Factory.get('Group')(db)
disk_quota_obj = DiskQuota(db)

debug = 0
max_errors = 50  # Max number of errors to accept in person-callback
posix_spreads = [int(const.Spread(_s)) for _s in cereconf.POSIX_SPREAD_CODES]

# global Command-line alterable variables.  Defined here to make
# pychecker happy
skip_lpr = True  # Must explicitly tell that we want lpr
create_users = move_users = dryrun = update_accounts = False
with_quarantines = False
remove_groupmembers = False
ou_perspective = None
workdir = None
paper_money_file = None  # Default: don't check for paid paper money
student_info_file = None
studconfig_file = None
studieprogs_file = None
emne_info_file = None
fast_test = False
with_diskquota = False

# Other globals (to make pychecker happy)
autostud = accounts = persons = None
default_creator_id = default_expire_date = default_shell = None

merge_pdfs_cmd = ("/usr/bin/gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 "
                  "-dPDFSETTINGS=/default -dNOPAUSE -dQUIET -dBATCH "
                  "-dDetectDuplicateImages -dCompressFonts=true -r150 -"
                  "sOutputFile={merged_file} {pdf_files}")


def pformat(obj):
    return pformat.pp.pformat(obj)


pformat.pp = pprint.PrettyPrinter(indent=4)


class AccountUtil(object):
    """Collection of methods that operate on a single account to make
    it conform to a profile """

    @staticmethod
    def restore_uname(account_id, profile):
        logger.info("RESTORE")
        account = Factory.get('Account')(db)
        account.find(account_id)

        homes = account.get_homes()

        for h in homes:
            disk_quota_obj.clear(h['homedir_id'])
            account.clear_home(h['spread'])
        account.expire_date = None
        logger.debug("refreshing password write_db=%s", account.account_name)
        account.write_db()
        account.populate_trait(code=const.trait_student_new, date=now())
        account.write_db()

    @staticmethod
    def create_user(fnr, profile):
        # dryruning this method is unfortunately a bit tricky
        assert not dryrun
        uname = None
        logger.info("CREATE")
        person = Factory.get('Person')(db)
        try:
            person.find_by_external_id(const.externalid_fodselsnr, fnr,
                                       const.system_fs)
        except Errors.NotFoundError:
            logger.warn("OUCH! person %s not found", fnr)
            return None
        if cereconf.USE_STUDENTNR_AS_UNAME:
            logger.debug("using studentnr as uname")
            stdnr_lst = person.get_external_id(
                source_system=const.system_fs,
                id_type=const.externalid_studentnr)
            if stdnr_lst:
                uname = stdnr_lst[0]['external_id']
        # if cereconf.USE_STUDENTNR_AS_UNAME is not used or studentnr is not
        # found produce uname according to the usual algorithm
        account = Factory.get('Account')(db)
        if not uname:
            try:
                first_name = person.get_name(const.system_cached,
                                             const.name_first)
            except Errors.NotFoundError:
                # This can happen if the person has no first name and no
                # authoritative system has set an explicit name_first variant.
                first_name = ""
            if not persons[fnr].get_affiliations():
                logger.error("The person %s has no student affiliations", fnr)
                return None
            try:
                last_name = person.get_name(const.system_cached,
                                            const.name_last)
            except Errors.NotFoundError:
                # See above.  In such a case, name_last won't be set either,
                # but name_full will exist.
                last_name = person.get_name(const.system_cached,
                                            const.name_full)
                assert last_name.count(' ') == 0
            suggestions = account.suggest_unames(const.account_namespace,
                                                 first_name, last_name)
            for sugg in suggestions:
                try:
                    group_obj.clear()
                    group_obj.find_by_name(sugg)
                except Errors.NotFoundError:
                    uname = sugg
                    break
        if not uname:
            logger.error("Failed to find an available username for {}".format(
                fnr))
            return None
        logger.info("uname %s will be used", uname)
        account.populate(uname,
                         const.entity_person,
                         person.entity_id,
                         None,
                         default_creator_id, default_expire_date)
        tmp = account.write_db()
        logger.debug("new Account, write_db=%s", tmp)
        account.write_db()
        account.populate_trait(code=const.trait_student_new, date=now())
        account.write_db()
        as_posix = False
        for spread in profile.get_spreads():
            if int(spread) in posix_spreads:
                as_posix = True
        accounts[int(account.entity_id)] = ExistingAccount(fnr, None)
        AccountUtil.update_account(account.entity_id, fnr, profile, as_posix)
        return account.entity_id

    @staticmethod
    def _populate_account_affiliations(account_id, fnr):
        """Assert that the account has the same student affiliations as
        the person.  Will not remove the last student account affiliation
        even if the person has no such affiliation"""

        changes = []
        remove_idx = 1  # Do not remove last account affiliation
        account_ous = [ou for aff, ou in
                       accounts[account_id].get_affiliations()
                       if aff == const.affiliation_student]
        for aff, ou, status in persons[fnr].get_affiliations():
            assert aff == const.affiliation_student
            if ou not in account_ous:
                changes.append(('set_ac_type',
                                (ou, const.affiliation_student)))
            else:
                account_ous.remove(ou)
                # The account has at least one valid affiliation, so
                # we can delete everything left in account_ous.
                remove_idx = 0

        for ou in account_ous[remove_idx:]:
            changes.append(('del_ac_type', (ou, const.affiliation_student)))
        return changes

    @staticmethod
    def _handle_user_changes(changes, account_id, as_posix):
        if as_posix:
            user = posix_user_obj
        else:
            user = account_obj
        user.clear()
        if changes[0][0] == 'dfg' and accounts[account_id].get_gid() is None:
            uid = user.get_free_uid()
            shell = default_shell
            account_obj.clear()
            account_obj.find(account_id)
            user.populate(uid, changes[0][1], None, shell,
                          parent=account_obj, expire_date=default_expire_date)
            user.write_db()
            user.map_user_spreads_to_pg()
            logger.debug("Used dfg2: " + str(changes[0][1]))
            accounts[account_id].append_group(changes[0][1])
            del (changes[0])
        else:
            user.find(account_id)

        for c_id, dta in changes:
            if c_id == 'add_spread':
                try:
                    user.add_spread(dta)
                except db.IntegrityError:
                    logger.warn('Could not add %s to %s', dta, account_id)
        for c_id, dta in changes:
            if c_id == 'dfg':
                user.gid_id = dta
                logger.debug("Used dfg: %s", dta)
                accounts[account_id].append_group(dta)
            elif c_id == 'expire':
                user.expire_date = dta
            elif c_id == 'disk':
                current_disk_id, disk_spread, new_disk = dta
                if current_disk_id is None:
                    logger.debug("Set home: %s", new_disk)
                    homedir_id = user.set_homedir(
                        disk_id=new_disk, status=const.home_status_not_created)
                    user.set_home(disk_spread, homedir_id)
                    accounts[account_id].set_home(disk_spread, new_disk,
                                                  homedir_id)
                else:
                    br = BofhdRequests(db, const)
                    # TBD: Is it correct to set requestee_id=None?
                    try:
                        br.add_request(None, br.batch_time,
                                       const.bofh_move_user, account_id,
                                       new_disk, state_data=int(disk_spread))
                    except errors.CerebrumError as e:
                        # Conflicting request or similiar
                        logger.warn(e)
            elif c_id == 'remove_autostud_quarantine':
                user.delete_entity_quarantine(dta)
            elif c_id == 'remove_quarantine_at_restore':
                user.delete_entity_quarantine(dta)
            elif c_id == 'add_spread':
                pass  # already processed
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
                # Fix dette!
                # sett --quarantine-exempt krever
                # sjekk om opsjonen --quarantine-exempt er på
                # sjekk om personen har en annen aff og hvis så skip
                user.add_entity_quarantine(
                    dta[0], default_creator_id, 'automatic', start_at)
            elif c_id == 'disk_kvote':
                disk_id, homedir_id, quota, spread = dta
                if homedir_id is None:  # homedir was added in this run
                    homedir_id = accounts[account_id].get_home(spread)[1]
                disk_quota_obj.set_quota(homedir_id, quota=int(quota))
            else:
                raise ValueError("Unknown change: %s" % c_id)
        tmp = user.write_db()
        logger.debug("write_db=%s", tmp)

    @staticmethod
    def _update_group_memberships(account_id, profile):
        changes = []  # Changes is only used for debug output
        already_member = {}
        for group_id in accounts[account_id].get_groups():
            already_member[group_id] = True

        logger.debug("%i already in %s", account_id, repr(already_member))
        for g in profile.get_grupper():
            if g not in already_member:
                group_obj.clear()
                group_obj.find(g)
                # Double check the membership, as some members aren't cached
                # correctly, due to unknown reasons.
                if not group_obj.has_member(account_id):
                    try:
                        group_obj.add_member(account_id)
                        changes.append(("g_add", group_obj.group_name))
                    except db.IntegrityError as m:
                        logger.info("Did not give membership because: %s", m)
                        continue
            else:
                del already_member[g]
        if remove_groupmembers:
            for g in already_member.keys():
                if (autostud.pc.group_defs.get(
                        g, {}).get('auto', None) == 'auto'):
                    if accounts[account_id].get_gid() == g:
                        logger.warn("Can't remove %i from its dfg %i",
                                    account_id, g)
                        continue
                    group_obj.clear()
                    group_obj.find(g)
                    group_obj.remove_member(account_id)
                    changes.append(('g_rem', group_obj.group_name))
        return changes

    @staticmethod
    def update_account(account_id, fnr, profile, as_posix):

        def _dont_downgrade_account():
            """Return True if this is the time of year when accounts
            shouldn't be downgraded."""

            # We reuse the definition of the free period for printer
            # quotas.
            from Cerebrum.modules.no.uio.printer_quota.PPQUtil \
                import is_free_period

            year, month, mday = localtime()[0:3]
            return is_free_period(year, month, mday)

        # First fill 'changes' with all needed modifications.  We will
        # only lookup databaseobjects if changes is non-empty.
        logger.info(" UPDATE:%s", account_id)
        processed_accounts[account_id] = True
        changes = []
        ac = accounts[account_id]
        if as_posix:
            try:
                gid = profile.get_dfg()
            except AutoStud.ProfileHandler.NoDefaultGroup:
                logger.info("Found no dfg for account %s", account_id)
                # Setting it to a bad value, as UiO ignores the use of dfg.
                # Other instances will get an exception later on, when trying
                # to run write_db.
                gid = None
            # we no longer want to change the default-group if already set
            if ac.get_gid() is None:  # or ac['gid'] != gid):
                changes.append(('dfg', gid))

        if ac.get_expire_date() != default_expire_date:
            changes.append(('expire', default_expire_date))

        # Set/change homedir
        user_spreads = [int(s) for s in profile.get_spreads()]

        # quarantine scope='student_disk' should affect all users with
        # home on a student-disk, or that doesn't have a home at all
        may_be_quarantined = False
        if not ac.has_homes():
            may_be_quarantined = True
        for s in autostud.disk_tool.get_known_spreads():
            disk_id, homedir_id = ac.get_home(s)
            if (disk_id and
                    autostud.disk_tool.get_diskdef_by_diskid(disk_id)):
                may_be_quarantined = True

        current_disk_id = None
        for disk_spread in profile.get_disk_spreads():
            if disk_spread not in user_spreads:
                # The disk-spread in disk-defs was not one of the users spread
                continue
            current_disk_id, notused = ac.get_home(disk_spread)
            if keep_account_home[fnr] and (move_users or current_disk_id is
                                           None):
                try:
                    new_disk = profile.get_disk(disk_spread, current_disk_id)
                except AutoStud.ProfileHandler.NoAvailableDisk:
                    raise
                if current_disk_id != new_disk:
                    autostud.disk_tool.notify_used_disk(old=current_disk_id,
                                                        new=new_disk)
                    changes.append(('disk', (current_disk_id, disk_spread,
                                             new_disk)))
                    current_disk_id = new_disk
                    ac.set_home(disk_spread, new_disk,
                                ac.get_home(disk_spread)[1])

        if autostud.disk_tool.using_disk_kvote:
            for spread in accounts[account_id].get_home_spreads():
                disk_id, homedir_id = accounts[account_id].get_home(spread)
                if not autostud.disk_tool.get_diskdef_by_diskid(disk_id):
                    # Setter kun kvote på student-disker
                    continue
                quota = profile.get_disk_kvote(disk_id)
                if (ac.get_disk_kvote(homedir_id) > quota and
                        _dont_downgrade_account()):
                    continue
                if ac.get_disk_kvote(homedir_id) != quota:
                    changes.append(('disk_kvote',
                                    (disk_id, homedir_id, quota, spread)))
                    ac.set_disk_kvote(homedir_id, quota)

        # TBD: Is it OK to ignore date on existing quarantines when
        # determining if it should be added?
        tmp = []
        for q in profile.get_quarantines():
            if q['scope'] == 'student_disk' and not may_be_quarantined:
                continue
            tmp.append(int(q['quarantine']))
            if (with_quarantines and not int(q['quarantine']) in
                                         ac.get_quarantines()):
                changes.append(('add_quarantine', (q['quarantine'],
                                                   q['start_at'])))

        # Remove auto quarantines
        for q in (const.quarantine_auto_inaktiv,
                  const.quarantine_auto_emailonly):
            if (int(q) in ac.get_quarantines() and
                    int(q) not in tmp):
                changes.append(("remove_autostud_quarantine", q))

        # Populate spreads
        has_account_spreads = ac.get_spreads()
        has_person_spreads = persons[fnr].get_spreads()
        for spread in profile.get_spreads():
            if spread.entity_type == const.entity_account:
                if not int(spread) in has_account_spreads:
                    changes.append(('add_spread', spread))
            elif spread.entity_type == const.entity_person:
                if not int(spread) in has_person_spreads:
                    changes.append(('add_person_spread', spread))
                    has_person_spreads.append(int(spread))

        changes.extend(AccountUtil._populate_account_affiliations(account_id,
                                                                  fnr))
        # We have now collected all changes that would need fetching of
        # the user object.
        if changes:
            if ac.is_deleted():
                AccountUtil.restore_uname(account_id, profile)
                for q in ac.get_quarantines():
                    if q in [int(const.quarantine_generell),
                             int(const.quarantine_autopassord),
                             int(const.quarantine_slutta)]:
                        changes.append(('remove_quarantine_at_restore', q))

        if changes:
            AccountUtil._handle_user_changes(changes, account_id, as_posix)

        changes.extend(AccountUtil._update_group_memberships(account_id,
                                                             profile))

        if changes:
            logger.debug("Changes [%i/%s]: %s", account_id, fnr, repr(changes))


class RecalcQuota(object):
    """Collection of methods to calculate proper quota settings for a
    person"""

    @staticmethod
    def _recalc_quota_callback(person_info):
        fnr = fodselsnr.personnr_ok("%06d%05d" %
                                    (int(person_info['fodselsdato']),
                                     int(person_info['personnr'])))
        logger.set_indent(0)
        logger.debug("Callback for %s", fnr)
        logger.set_indent(3)
        logger.debug(pformat(_filter_person_info(person_info)))
        pq = PrinterQuotas.PrinterQuotas(db)

        for account_id in persons.get(fnr, {}).keys():
            try:
                profile = autostud.get_profile(
                    person_info, member_groups=persons[fnr].get_groups())
                quota = profile.get_pquota()
            except AutoStud.ProfileHandler.NoMatchingQuotaSettings as msg:
                logger.warn("Error for %s: %s", fnr, msg)
                logger.set_indent(0)
                return
            except AutoStud.ProfileHandler.NoMatchingProfiles as msg:
                logger.warn("Error for %s: %s", fnr, msg)
                logger.set_indent(0)
                return
            except Errors.NotFoundError as msg:
                logger.warn("Error for %s: %s", fnr, msg)
                logger.set_indent(0)
                return
            logger.debug("Setting %s as pquotas for %s", quota, account_id)
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
                    init_quota = (int(quota['initial_quota']) -
                                  int(quota['weekly_quota']))
                pq.populate(account_id, init_quota, 0, 0, 0, 0, 0, 0)
            if (quota['weekly_quota'] == 'UL' or
                    profile.get_printer_kvote_fritak()):
                pq.has_printerquota = 'F'
            else:
                pq.has_printerquota = 'T'
                pq.weekly_quota = quota['weekly_quota']
                pq.max_quota = quota['max_quota']
                pq.termin_quota = quota['termin_quota']
            if paper_money_file:
                if (not profile.get_printer_betaling_fritak() and
                        not paid_paper_money.get(fnr, False)):
                    logger.debug("didn't pay, max_quota=0 for %s ", fnr)
                    pq.max_quota = 0
                    pq.printer_quota = 0
            pq.write_db()
            has_quota[int(account_id)] = True
        logger.set_indent(0)
        # We commit once for each person to avoid locking too many db-rows
        if not dryrun:
            db.commit()

    @staticmethod
    def recalc_pq_main():
        raise SystemExit("--recalc-quota is obsolete and will be removed"
                         " shortly")
        if paper_money_file:
            for p in AutoStud.StudentInfo.GeneralDataParser(paper_money_file,
                                                            'betalt'):
                fnr = fodselsnr.personnr_ok("%06d%05d" % (
                    int(p['fodselsdato']), int(p['personnr'])))
                paid_paper_money[fnr] = True
        autostud.start_student_callbacks(student_info_file,
                                         RecalcQuota._recalc_quota_callback)
        # Set default_quota for the rest that already has quota
        pq = PrinterQuotas.PrinterQuotas(db)
        dv = autostud.pc.default_values
        for row in pq.list_quotas():
            account_id = int(row['account_id'])
            if row['has_printerquota'] == 'F' or has_quota.get(account_id,
                                                               False):
                continue
            logger.debug("Default quota for %i", account_id)
            # TODO: sjekk om det er nødvendig med oppdatering før vi gjør find.
            pq.clear()
            try:
                pq.find(account_id)
            except Errors.NotFoundError:
                logger.error("not found: %i, recently deleted?", account_id)
                continue
            pq.weekly_quota = dv['print_uke']
            pq.max_quota = dv['print_max_akk']
            pq.termin_quota = dv['print_max_sem']
            if paper_money_file:
                if account_id not in account_id2fnr:
                    # probably a deleted user
                    logger.debug("account_id %i not in account_id2fnr, "
                                 "deleted?", account_id)
                elif not paid_paper_money.get(account_id2fnr[account_id],
                                              False):
                    logger.debug("didn't pay, max_quota=0 for %i ", account_id)
                    pq.max_quota = 0
                    pq.printer_quota = 0
            pq.write_db()
        if not dryrun:
            db.commit()
        else:
            db.rollback()


class BuildAccounts(object):
    """Collection of methods for updating/creating student users for
    all persons"""

    @staticmethod
    def _process_students_callback(person_info):
        global max_errors
        try:
            BuildAccounts._process_student(person_info)
        except:
            max_errors -= 1
            if max_errors < 0:
                raise
            trace = "".join(traceback.format_exception(
                sys.exc_type, sys.exc_value, sys.exc_info()[2]))
            logger.error("Unexpected error: %s", trace)
            db.rollback()

    @staticmethod
    def _process_student(person_info):
        fnr = fodselsnr.personnr_ok("%06d%05d" %
                                    (int(person_info['fodselsdato']),
                                     int(person_info['personnr'])))
        logger.set_indent(0)
        logger.debug("Callback for %s", fnr)

        logger.set_indent(3)
        pinfo = persons.get(fnr, None)
        if pinfo is None:
            logger.warn("Unknown person %s", fnr)
            return
        logger.debug(pformat(_filter_person_info(person_info)))
        if fnr not in persons:
            logger.warn("(person) not found error for %s", fnr)
            logger.set_indent(0)
            return
        try:
            profile = autostud.get_profile(
                person_info, member_groups=persons[fnr].get_groups(),
                person_affs=persons[fnr].get_affiliations())
            logger.debug(profile.matcher.debug_dump())
        except AutoStud.ProfileHandler.NoMatchingProfiles as msg:
            logger.warn("No matching profile error for %s: %s", fnr, msg)
            logger.set_indent(0)
            return
        except AutoStud.ProfileHandler.NoAvailableDisk as msg:
            # pretend that the account was processed so that
            # list_noncallback_users doesn't include the user(s).
            # While this is only somewhat correct behaviour, the
            # NoAvailableDisk situation should be resolved switftly.
            for account_id in pinfo.get_student_ac():
                processed_accounts[account_id] = True
            raise
        processed_students[fnr] = 1
        keep_account_home[fnr] = profile.get_build()['home']
        if fast_test:
            logger.debug(profile.debug_dump())
            # logger.debug("Disk: %s", profile.get_disk())
            logger.set_indent(0)
            return
        try:
            _debug_dump_profile_match(profile, fnr)
            if dryrun:
                logger.set_indent(0)
                return
            if (create_users and not pinfo.has_student_ac() and
                    profile.get_build()['action']):
                if pinfo.has_other_ac():
                    logger.debug("Has active non-student account, skipping")
                    return
                elif pinfo.has_reserved_ac():  # has a reserved account
                    logger.debug("using reserved: %s",
                                 pinfo.get_best_reserved_ac())
                    BuildAccounts._update_persons_accounts(
                        profile, fnr, [pinfo.get_best_reserved_ac()])
                elif pinfo.has_deleted_ac():
                    logger.debug("using deleted: %s",
                                 pinfo.get_best_deleted_ac())
                    BuildAccounts._update_persons_accounts(
                        profile, fnr, [pinfo.get_best_deleted_ac()])
                else:
                    account_id = AccountUtil.create_user(fnr, profile)
                    logger.debug("would create account for %s", fnr)
                    if account_id is None:
                        logger.set_indent(0)
                        return
                # students.setdefault(fnr, {})[account_id] = []
            elif update_accounts and pinfo.has_student_ac():
                BuildAccounts._update_persons_accounts(
                    profile, fnr, pinfo.get_student_ac())
        except AutoStud.ProfileHandler.NoAvailableDisk as msg:
            logger.error("  Error for %s: %s", fnr, msg)
        logger.set_indent(0)
        # We commit once for each person to avoid locking too many db-rows
        if not dryrun:
            db.commit()

    @staticmethod
    def _update_persons_accounts(profile, fnr, account_ids):
        """Update the account by checking that group, disk and
        affiliations are correct.  For existing accounts, account_info
        should be filled with affiliation info """

        # dryruning this method is unfortunately a bit tricky
        assert not dryrun

        as_posix = False

        for spread in profile.get_spreads():  # TBD: Is this check sufficient?
            if int(spread) in posix_spreads:
                as_posix = True
        for account_id in account_ids:
            AccountUtil.update_account(account_id, fnr, profile, as_posix)

    @staticmethod
    def update_accounts_main():
        autostud.start_student_callbacks(
            student_info_file,
            BuildAccounts._process_students_callback)
        logger.set_indent(0)
        logger.info("student_info_file processed")
        if not dryrun:
            db.commit()
        else:
            logger.info("Dryrun: Rolled back changed")
            db.rollback()
        BuildAccounts._process_unprocessed_students()

    @staticmethod
    def _process_unprocessed_students():
        """Unprocessed students didn't match a profile, or didn't get a
        callback at all"""
        # TBD: trenger vi skille på de?
        logger.info("process_unprocessed_students")

        for fnr, pinfo in persons.items():
            if not pinfo.has_student_ac():
                continue
            if fnr not in processed_students:
                d, p = fodselsnr.del_fnr(fnr)
                BuildAccounts._process_students_callback({
                    'fodselsdato': d,
                    'personnr': p})


class ExistingAccount(object):
    def __init__(self, fnr, expire_date):
        self._affs = []
        self._disk_kvote = {}
        self._expire_date = expire_date
        self._fnr = fnr
        self._gid = None
        self._groups = []
        self._home = {}
        self._quarantines = []
        self._reserved = False
        self._deleted = False
        self._spreads = []

    def append_affiliation(self, affiliation, ou_id):
        self._affs.append((affiliation, ou_id))

    def get_affiliations(self):
        return self._affs

    def has_affiliation(self, aff_cand):
        return aff_cand in [aff for aff, ou in self._affs]

    def get_disk_kvote(self, homedir_id):
        return self._disk_kvote.get(homedir_id, None)

    def set_disk_kvote(self, homedir_id, quota):
        self._disk_kvote[homedir_id] = quota

    def get_expire_date(self):
        return self._expire_date

    def get_fnr(self):
        return self._fnr

    def get_gid(self):
        return self._gid

    def set_gid(self, gid):
        self._gid = gid

    def append_group(self, group_id):
        self._groups.append(group_id)

    def get_groups(self):
        return self._groups

    def get_home(self, spread):
        return self._home.get(spread, (None, None))

    def get_home_spreads(self):
        return self._home.keys()

    def has_homes(self):
        return len(self._home) > 0

    def set_home(self, spread, disk_id, homedir_id):
        self._home[spread] = (disk_id, homedir_id)

    def append_quarantine(self, q):
        self._quarantines.append(q)

    def get_quarantines(self):
        return self._quarantines

    def is_reserved(self):
        return self._reserved

    def set_reserved(self, cond):
        self._reserved = cond

    def is_deleted(self):
        return self._deleted

    def set_deleted(self, cond):
        self._deleted = cond

    def append_spread(self, spread):
        self._spreads.append(spread)

    def get_spreads(self):
        return self._spreads


class ExistingPerson(object):
    def __init__(self):
        self._affs = []
        self._groups = []
        self._other_ac = []
        self._reserved_ac = []
        self._deleted_ac = []
        self._spreads = []
        self._stud_ac = []

    def append_affiliation(self, affiliation, ou_id, status):
        self._affs.append((affiliation, ou_id, status))

    def get_affiliations(self):
        return self._affs

    def append_group(self, group_id):
        self._groups.append(group_id)

    def get_groups(self):
        return self._groups

    def append_other_ac(self, account_id):
        self._other_ac.append(account_id)

    def has_other_ac(self):
        return len(self._other_ac) > 0

    def append_deleted_ac(self, account_id):
        self._deleted_ac.append(account_id)

    def get_best_deleted_ac(self):
        return self._deleted_ac[0]

    def has_deleted_ac(self):
        return len(self._deleted_ac) > 0

    def append_reserved_ac(self, account_id):
        self._reserved_ac.append(account_id)

    def get_best_reserved_ac(self):
        return self._reserved_ac[0]

    def has_reserved_ac(self):
        return len(self._reserved_ac) > 0

    def append_spread(self, spread):
        self._spreads.append(spread)

    def get_spreads(self):
        return self._spreads

    def append_stud_ac(self, account_id):
        self._stud_ac.append(account_id)

    def get_student_ac(self):
        return self._stud_ac

    def has_student_ac(self):
        return len(self._stud_ac) > 0


def start_process_students(recalc_pq=False, update_create=False):
    global autostud, accounts, persons

    logger.info("process_students started")
    autostud = AutoStud.AutoStud(db, logger, debug=debug,
                                 cfg_file=studconfig_file,
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
            logger.warn("%s not set, check your cereconf file", t)
    account = Factory.get('Account')(db)
    account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    default_creator_id = account.entity_id
    default_expire_date = None
    if posix_tables:
        default_shell = const.posix_shell_bash


def get_existing_accounts():
    """Prefetch data about persons and their accounts to avoid
    multiple SQL queries for each callback.  Returns:

    persons = {'fnr': {'affs': [(aff, ou, status)],
                       'stud_ac': [account_id], 'other_ac': [account_id],
                       'reserved_ac': [account_id], 'deleted_ac': [account_id],
                       'spreads': [spread_id],
                       'groups': [group_id]}}
    accounts = {'account_id': {'owner: fnr, 'reserved': boolean,
                               'gid': group_id, 'quarantines': [quarantine_id],
                               'spreads': [spread_id], 'groups': [group_id],
                               'affs': [(aff, ou)],
                               'expire_date': expire_date,
                               'home': {spread: (disk_id, homedir_id)}}}
    """
    tmp_persons = {}

    logger.info("In get_existing_accounts")
    if fast_test:
        return {}, {}

    logger.info("Listing persons")
    pid2fnr = {}
    for row in person_obj.search_external_ids(
            id_type=const.externalid_fodselsnr,
            fetchall=False):
        if (row['source_system'] == int(const.system_fs) or
                int(row['entity_id']) not in pid2fnr):
            pid2fnr[int(row['entity_id'])] = row['external_id']
            tmp_persons[row['external_id']] = ExistingPerson()

    for row in person_obj.list_affiliations(
            source_system=const.system_fs,
            affiliation=const.affiliation_student,
            fetchall=False):
        tmp = pid2fnr.get(int(row['person_id']), None)
        if tmp is not None:
            tmp_persons[tmp].append_affiliation(
                int(row['affiliation']), int(row['ou_id']), int(row['status']))

    #
    # Hent ut info om eksisterende og reserverte konti
    #
    logger.info("Listing accounts...")
    tmp_ac = {}
    for row in account_obj.list(filter_expired=False, fetchall=False):
        if not row['owner_id'] or int(row['owner_id']) not in pid2fnr:
            continue
        tmp_ac[int(row['account_id'])] = ExistingAccount(
            pid2fnr[int(row['owner_id'])],
            row['expire_date'])
    # PosixGid
    for row in posix_user_obj.list_posix_users():
        tmp = tmp_ac.get(int(row['account_id']), None)
        if tmp is not None:
            tmp.set_gid(int(row['gid']))
    # Reserved users
    for row in account_obj.list_reserved_users(fetchall=False):
        tmp = tmp_ac.get(int(row['account_id']), None)
        if tmp is not None:
            tmp.set_reserved(True)
    # Deleted users
    for row in account_obj.list_deleted_users():
        tmp = tmp_ac.get(int(row['account_id']), None)
        if tmp is not None:
            tmp.set_deleted(True)
    # quarantines
    for row in account_obj.list_entity_quarantines(
            entity_types=const.entity_account):
        tmp = tmp_ac.get(int(row['entity_id']), None)
        if tmp is not None:
            tmp.append_quarantine(int(row['quarantine_type']))
    # Disk kvote
    if with_diskquota:
        for row in disk_quota_obj.list_quotas():
            tmp = tmp_ac.get(int(row['account_id']), None)
            if tmp is not None:
                tmp.set_disk_kvote(int(row['homedir_id']), row['quota'])
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
                tmp = tmp_ac.get(int(row['entity_id']), None)
            else:
                tmp = tmp_persons.get(
                    pid2fnr.get(int(row['entity_id']), None), None)
            if tmp is not None:
                tmp.append_spread(spread_id)
    # Account homes
    for row in account_obj.list_account_home():
        tmp = tmp_ac.get(int(row['account_id']), None)
        if tmp is not None and row['disk_id']:
            tmp.set_home(int(row['home_spread']), int(row['disk_id']),
                         int(row['homedir_id']))

    # Group memberships
    for group_id in autostud.pc.group_defs.keys():
        group_obj.clear()
        group_obj.find(group_id)
        for row in group_obj.search_members(group_id=group_obj.entity_id,
                                            member_type=const.entity_account,
                                            member_filter_expired=False):
            tmp = tmp_ac.get(int(row["member_id"]), None)
            if tmp is not None:
                tmp.append_group(group_id)
        for row in group_obj.search_members(group_id=group_obj.entity_id,
                                            member_type=const.entity_person):
            tmp = tmp_persons.get(int(row["member_id"]), None)
            if tmp is not None:
                tmp.append_group(group_id)
    # Affiliations
    for row in account_obj.list_accounts_by_type(
            affiliation=const.affiliation_student, fetchall=False):
        tmp = tmp_ac.get(int(row['account_id']), None)
        if tmp is not None:
            tmp.append_affiliation(int(row['affiliation']), int(row['ou_id']))

    for ac_id, tmp in tmp_ac.items():
        fnr = tmp_ac[ac_id].get_fnr()
        if tmp.is_reserved():
            tmp_persons[fnr].append_reserved_ac(ac_id)
        elif tmp.is_deleted():
            tmp_persons[fnr].append_deleted_ac(ac_id)
        elif tmp.has_affiliation(int(const.affiliation_student)):
            tmp_persons[fnr].append_stud_ac(ac_id)
        elif tmp_persons[fnr].get_affiliations():
            # get_affiliations() only returns STUDENT affiliations.
            # Accounts on student disks are handled as if they were
            # students if the person has at least one STUDENT
            # affiliation.  The STUDENT affiliation(s) will be added
            # later during this run.
            for s in tmp.get_home_spreads():
                disk_id = tmp.get_home(s)[0]
                if autostud.disk_tool.get_diskdef_by_diskid(disk_id):
                    tmp_persons[fnr].append_stud_ac(ac_id)
                    break
            else:
                tmp_persons[fnr].append_other_ac(ac_id)
        else:
            tmp_persons[fnr].append_other_ac(ac_id)

    logger.info(" found %i persons and %i accounts", len(tmp_persons),
                len(tmp_ac))
    return tmp_persons, tmp_ac


def _filter_person_info(person_info):
    """Makes debugging easier by removing some of the irrelevant
    person-information."""
    ret = {}
    _filter = {
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
        for f in _filter:
            if info_type == f:
                for dta in person_info[info_type]:
                    ret.setdefault(info_type, []).append(
                        dict([(k, dta[k]) for k in _filter[info_type]]))
        if info_type not in ret:
            ret[info_type] = person_info[info_type]
    return ret


def _debug_dump_profile_match(profile, fnr):
    # TODO:  Hører ikke dette hjemme i ProfileHandler?
    # Note that we don't pass current_disk to get_disks() here.
    # Thus this value may differ from the one used during an
    # update
    try:
        dfg = profile.get_dfg()  # dfg is only mandatory for PosixGroups
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
    logger.debug("disk=%s, dfg=%s, fg=%s sko=%s", disk, dfg,
                 profile.get_grupper(), profile.get_stedkoder())


def validate_config():
    if studconfig_file is None or \
            studieprogs_file is None or \
            emne_info_file is None:

        print("Missing required parameter(s). 'studconfig_file' (-C), "
              "studieprogs_file' (-S)\nand 'emne_info_file' (-e) needs "
              "to be specified when running --validate.")
        sys.exit(1)

    else:
        AutoStud.AutoStud(db, logger, debug=debug, cfg_file=studconfig_file,
                          studieprogs_file=studieprogs_file,
                          emne_info_file=emne_info_file)


def process_noncallback_users(reset_diskquota=False):
    """Process accounts on student-disk that did not get a callback
    resulting in update_account."""

    # TODO: --dryrun currently makes this useless, since it implies
    # doing no updates, and therefore _every_ student is processed.

    logger.info("Processing noncallback users")
    on_student_disk = {}
    for row in account_obj.list_account_home():
        if (row['disk_id'] is not None and
                autostud.disk_tool.get_diskdef_by_diskid(int(row['disk_id']))):
            on_student_disk[int(row['account_id'])] = True

    for ac_id in on_student_disk.keys():
        if ac_id in processed_accounts:
            continue
        if ac_id not in accounts:
            # This will happen if the accounts owner has no registered
            # fødselsnummer.
            logger.info("Not in list of existing accounts: %d", ac_id)
            continue
        if not reset_diskquota:
            continue
        for spread in accounts[ac_id].get_home_spreads():
            disk_id, homedir_id = accounts[ac_id].get_home(spread)
            if accounts[ac_id].get_disk_kvote(homedir_id):
                logger.info("Clearing quota for %d", ac_id)
                disk_quota_obj.clear(homedir_id)
    if not dryrun:
        logger.debug("Commiting changes")
        db.commit()


def main():
    global debug, fast_test, create_users, update_accounts, logger, skip_lpr
    global student_info_file, studconfig_file, studieprogs_file, dryrun, \
        emne_info_file, move_users, remove_groupmembers, workdir, \
        paper_money_file, ou_perspective, with_quarantines, with_diskquota, \
        posix_tables

    # Parse arguments
    parser = argparse.ArgumentParser(description=__doc__)
    input_grp = parser.add_argument_group('Input files')
    input_grp.add_argument(
        '-s',
        '--student-info-file')
    input_grp.add_argument(
        '-e',
        '--emne-info-file')
    input_grp.add_argument(
        '-p', '--paper-file',
        help='check for paid-quota only done if set')
    input_grp.add_argument(
        '-S',
        '--studie-progs-file')
    input_grp.add_argument(
        '-C',
        '--studconfig-file')

    act_group = parser.add_argument_group('Actions')
    act_group.add_argument(
        '-c', '--create-users',
        action='store_true',
        help='create new users',
        default=False)
    act_group.add_argument(
        '-u', '--update-accounts',
        action='store_true',
        help='update existing accounts',
        default=False)
    act_group.add_argument(
        '--recalc-pq',
        action='store_true',
        help='recalculate printerquota settings (does not update quota). '
             'Cannot be combined with -c/-u',
        default=False)
    act_group.add_argument(
        '--reset-diskquota',
        action='store_true',
        help='remove disk quota from users on student disks that did not get '
             'a callback',
        default=False)

    parser.add_argument(
        '-d', '--debug',
        action='store_true',
        help='increases debug verbosity',
        default=False)
    parser.add_argument(
        '--remove-groupmembers',
        action='store_true',
        help='remove groupmembers if profile says so',
        default=False)
    parser.add_argument(
        '--with-quarantines',
        action='store_true',
        help='Enables quarantine settings',
        default=False)
    parser.add_argument(
        '--with-diskquota',
        action='store_true',
        default=False)
    parser.add_argument(
        '--posix-tables',
        action='store_true',
        default=False)
    parser.add_argument(
        '--move-users',
        action='store_true',
        help='move users if profile says so',
        default=False)
    parser.add_argument(
        '--fast-test',
        action='store_true',
        default=False)
    parser.add_argument(
        '--dryrun',
        action='store_true',
        help='don\'t do any changes to the database. '
             'This can be used to get an idea of what changes a normal run '
             'would do. TODO: also dryrun some parts of update/create user.',
        default=False)
    parser.add_argument(
        '--workdir',
        help='set workdir for --reprint')
    parser.add_argument(
        '--ou-perspective',
        help='set ou_perspective (default: perspective_fs)')
    parser.add_argument(
        '--validate',
        action='store_true',
        help='parse the configuration file and report any errors, then exit.',
        default=False)

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()
    Cerebrum.logutils.autoconf('studauto', args)

    # Set values according to arguments
    debug = args.debug
    create_users = args.create_users
    update_accounts = args.update_accounts
    remove_groupmembers = args.remove_groupmembers
    with_quarantines = args.with_quarantines
    with_diskquota = args.with_diskquota
    posix_tables = args.posix_tables
    move_users = args.move_users
    fast_test = args.fast_test  # Internal debug use ONLY!

    if args.student_info_file:
        student_info_file = args.student_info_file
    if args.emne_info_file:
        emne_info_file = args.emne_info_file
    if args.paper_file:
        paper_money_file = args.paper_file
    if args.studie_progs_file:
        studieprogs_file = args.studie_progs_file
    if args.studconfig_file:
        studconfig_file = args.studconfig_file

    if args.ou_perspective:
        ou_perspective = const.OUPerspective(args.ou_perspective)
        int(ou_perspective)  # Assert that it is defined
    if args.validate:
        workdir = '.'
    if args.workdir:
        workdir = args.workdir
    if workdir is None:
        workdir = "%s/ps-%s.%i" % (cereconf.AUTOADMIN_LOG_DIR,
                                   strftime("%Y-%m-%d", localtime()),
                                   os.getpid())
        os.mkdir(workdir)
    os.chdir(workdir)

    logger = Factory.get_logger("studauto")
    bootstrap()

    if args.validate:
        validate_config()
        print("The configuration was successfully validated.")
        sys.exit(0)

    with ParserContext(parser):
        if args.recalc_pq and (args.update_accounts or args.create_users):
            raise ValueError("recalc-pq cannot be combined with other "
                             "operations")
        if not (args.recalc_pq or args.update_accounts or args.create_users):
            raise ValueError('No action selected')

    start_process_students(recalc_pq=args.recalc_pq,
                           update_create=(args.create_users or
                                          args.reset_diskquota))
    if args.reset_diskquota:
        process_noncallback_users(reset_diskquota=args.reset_diskquota)
    logger.debug("all done")


if __name__ == '__main__':
    if False:
        print("Profilerer...")
        prof = hotshot.Profile(proffile)
        prof.runcall(main)  # profiler hovedprogrammet
        prof.close()
    else:
        main()
