# -*- coding: utf-8 -*-
#
# Copyright 2002-2019 University of Oslo, Norway
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
Bofhd commands at UiT.

History
-------
UiT used to have their own *copy* of bofhd_uio_cmds, which can be seen in:

    commit 5948d5fe8bd550acffde1073c3d17f8a04476df0
    Date:  Wed May 15 13:52:35 2019 +0200

This module was re-written to prevent duplicated code. It now *inherits* from
bofhd_uio_cmds. Certain commands were implemented differently, and still exists
in this module, for now.

TODO
----
Remove any commands from the BofhdExtension that is not actually in use at UiT.
"""

import imaplib
import re
import socket
import ssl

from mx import DateTime
from six import text_type

import cereconf
from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum import database
from Cerebrum.modules import Email
from Cerebrum.modules.bofhd.cmd_param import (
    AccountName,
    Command,
    EmailAddress,
    FormatSuggestion,
    GroupName,
    PersonId,
    SimpleString,
    YesNo,
)
from Cerebrum.modules.bofhd import bofhd_email
from Cerebrum.modules.bofhd.bofhd_contact_info import BofhdContactCommands
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd_requests import bofhd_requests_cmds
from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.modules.bofhd import bofhd_access
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uio.access_FS import FS
from Cerebrum.modules.no.uit import bofhd_auth, ad_email
from Cerebrum.modules.no.uio import bofhd_uio_cmds


format_day = bofhd_uio_cmds.format_day
date_to_string = bofhd_uio_cmds.date_to_string
exc_to_text = bofhd_uio_cmds.exc_to_text


class BofhdExtension(bofhd_uio_cmds.BofhdExtension):

    all_commands = {}
    hidden_commands = {}
    omit_parent_commands = {
        # UiT does not have the default host_info command - why have this?
        'host_info',

        # UiT does not allow a force option
        'group_delete',

        # UiT implements their own
        'misc_check_password',

        # UiT implements their own
        'person_info',

        # UiT implements their own
        'person_student_info',

        'user_create_sysadm',

        # We omit user_history, as UiT implements their own in
        # user_history_filtered
        'user_history',

        # We include user_restore (for the command definition and prompt_func),
        # but override the actual method in order to add some hooks.
        # 'user_restore',
    }
    parent_commands = True

    authz = bofhd_auth.UitAuth
    external_id_mappings = {}

    @classmethod
    def get_help_strings(cls):
        groups, cmds, args = super(BofhdExtension, cls).get_help_strings()

        # Move help for the 'user history' command to new key
        history = cmds['user'].pop('user_history')
        cmds['user']['user_history_filtered'] = history

        return groups, cmds, args

    #
    # group delete <groupname>
    #
    # TODO: UiO includes a force-flag to group_delete
    #
    all_commands['group_delete'] = Command(
        ("group", "delete"),
        GroupName(),
        perm_filter='can_delete_group')

    def group_delete(self, operator, groupname):

        grp = self._get_group(groupname)
        self.ba.can_delete_group(operator.get_entity_id(), grp)
        if grp.group_name == cereconf.BOFHD_SUPERUSER_GROUP:
            raise CerebrumError("Can't delete superuser group")
        # exchange-relatert-jazz
        # it should not be possible to remove distribution groups via
        # bofh, as that would "orphan" e-mail target. if need be such groups
        # should be nuked using a cerebrum-side script.
        if grp.has_extension('DistributionGroup'):
            raise CerebrumError(
                "Cannot delete distribution groups, use 'group"
                " exchange_remove' to deactivate %s" % groupname)
        elif grp.has_extension('PosixGroup'):
            raise CerebrumError(
                "Cannot delete posix groups, use 'group demote_posix %s'"
                " before deleting." % groupname)
        elif grp.get_extensions():
            raise CerebrumError(
                "Cannot delete group %s, is type %r" % (groupname,
                                                        grp.get_extensions()))

        self._remove_auth_target("group", grp.entity_id)
        self._remove_auth_role(grp.entity_id)
        try:
            grp.delete()
        except self.db.DatabaseError as msg:
            if re.search("group_member_exists", exc_to_text(msg)):
                raise CerebrumError(
                    ("Group is member of groups.  "
                     "Use 'group memberships group %s'") % grp.group_name)
            elif re.search("account_info_owner", exc_to_text(msg)):
                raise CerebrumError(
                    ("Group is owner of an account.  "
                     "Use 'entity accounts group %s'") % grp.group_name)
            raise
        return "OK, deleted group '%s'" % groupname

    #
    # group posix_demote <name>
    #
    # TODO: UiO aborts if the group is a default file group for any user.
    #
    all_commands['group_demote_posix'] = Command(
        ("group", "demote_posix"),
        GroupName(),
        perm_filter='can_force_delete_group')

    def group_demote_posix(self, operator, group):
        try:
            grp = self._get_group(group, grtype="PosixGroup")
        except self.db.DatabaseError as msg:
            if "posix_user_gid" in exc_to_text(msg):
                raise CerebrumError(
                    ("Assigned as primary group for posix user(s). "
                     "Use 'group list %s'") % grp.group_name)
            raise

        self.ba.can_force_delete_group(operator.get_entity_id(), grp)
        grp.demote_posix()
        return "OK, demoted '%s'" % group

    #
    # person info
    #
    # UiT includes the last_seen date in affiliation data
    # UiT includes deceased date
    # UiT does not censor contact info or extids
    #
    all_commands['person_info'] = Command(
        ("person", "info"),
        PersonId(help_ref="id:target:person"),
        fs=FormatSuggestion([
            ("Name:          %s\n"
             "Entity-id:     %i\n"
             "Birth:         %s\n"
             "Deceased:      %s\n"
             "Spreads:       %s", ("name", "entity_id", "birth",
                                   "deceased_date", "spreads")),
            ("Affiliations:  %s [from %s]", ("affiliation_1",
                                             "source_system_1")),
            ("               %s [from %s]", ("affiliation", "source_system")),
            ("Names:         %s [from %s]", ("names", "name_src")),
            ("Fnr:           %s [from %s]", ("fnr", "fnr_src")),
            ("Contact:       %s: %s [from %s]", ("contact_type", "contact",
                                                 "contact_src")),
            ("External id:   %s [from %s]", ("extid", "extid_src"))
        ]),
        perm_filter='can_view_person')

    def person_info(self, operator, person_id):
        try:
            person = self.util.get_target(person_id, restrict_to=['Person'])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        self.ba.can_view_person(operator.get_entity_id(), person)
        try:
            p_name = person.get_name(
                self.const.system_cached,
                getattr(self.const, cereconf.DEFAULT_GECOS_NAME))
            p_name = p_name + ' [from Cached]'
        except Errors.NotFoundError:
            raise CerebrumError("No name is registered for this person")
        data = [{
            'name': p_name,
            'entity_id': person.entity_id,
            'birth': date_to_string(person.birth_date),
            'deceased_date': date_to_string(person.deceased_date),
            'spreads': ", ".join([text_type(self.const.Spread(x['spread']))
                                  for x in person.get_spread()]),
        }]
        affiliations = []
        sources = []
        last_dates = []
        for row in person.get_affiliations():
            ou = self._get_ou(ou_id=row['ou_id'])
            date = row['last_date'].strftime("%Y-%m-%d")
            last_dates.append(date)
            affiliations.append("%s@%s" % (
                text_type(self.const.PersonAffStatus(row['status'])),
                self._format_ou_name(ou)))
            sources.append(
                text_type(
                    self.const.AuthoritativeSystem(row['source_system'])))
        for ss in cereconf.SYSTEM_LOOKUP_ORDER:
            ss = getattr(self.const, ss)
            person_name = ""
            for t in [self.const.name_first, self.const.name_last]:
                try:
                    person_name += person.get_name(ss, t) + ' '
                except Errors.NotFoundError:
                    continue
            if person_name:
                data.append({
                    'names': person_name,
                    'name_src': text_type(self.const.AuthoritativeSystem(ss)),
                })
        if affiliations:
            data[0]['affiliation_1'] = affiliations[0]
            data[0]['source_system_1'] = sources[0]
            data[0]['last_date_1'] = last_dates[0]

        else:
            data[0]['affiliation_1'] = "<none>"
            data[0]['source_system_1'] = "<nowhere>"
            data[0]['last_date_1'] = "<none>"
        for i in range(1, len(affiliations)):
            data.append({'affiliation': affiliations[i],
                         'source_system': sources[i],
                         'last_date': last_dates[i]})

        try:
            self.ba.can_get_person_external_id(operator, person, None, None)
            # Include fnr. Note that this is not displayed by the main
            # bofh-client, but some other clients (Brukerinfo, cweb) rely
            # on this data.
            for row in person.get_external_id(
                    id_type=self.const.externalid_fodselsnr):
                data.append({
                    'fnr': row['external_id'],
                    'fnr_src': text_type(
                        self.const.AuthoritativeSystem(row['source_system'])),
                })
            # Show external ids
            for extid in (
                    'externalid_fodselsnr',
                    'externalid_paga_ansattnr',
                    'externalid_studentnr',
                    'externalid_pass_number',
                    'externalid_social_security_number',
                    'externalid_tax_identification_number',
                    'externalid_value_added_tax_number'):
                extid_const = getattr(self.const, extid, None)
                if extid_const:
                    for row in person.get_external_id(id_type=extid_const):
                        data.append({
                            'extid': text_type(extid_const),
                            'extid_src': text_type(
                                self.const.AuthoritativeSystem(
                                    row['source_system'])),
                        })
        except PermissionDenied:
            pass

        # Show contact info, if permission checks are implemented
        if hasattr(self.ba, 'can_get_contact_info'):
            for row in person.get_contact_info():
                contact_type = self.const.ContactInfo(row['contact_type'])
                if contact_type not in (self.const.contact_phone,
                                        self.const.contact_mobile_phone,
                                        self.const.contact_phone_private,
                                        self.const.contact_private_mobile):
                    continue
                try:
                    if self.ba.can_get_contact_info(
                            operator.get_entity_id(),
                            entity=person,
                            contact_type=contact_type):
                        data.append({
                            'contact': row['contact_value'],
                            'contact_src': text_type(
                                self.const.AuthoritativeSystem(
                                    row['source_system'])),
                            'contact_type': text_type(contact_type),
                        })
                except PermissionDenied:
                    continue
        return data

    #
    # person student_info
    #
    all_commands['person_student_info'] = Command(
        ("person", "student_info"),
        PersonId(),
        fs=FormatSuggestion([
            ("Studieprogrammer: %s, %s, %s, %s, tildelt=%s->%s privatist: %s",
             ("studprogkode", "studieretningkode", "studierettstatkode",
              "studentstatkode", format_day("dato_tildelt"),
              format_day("dato_gyldig_til"), "privatist")),
            ("Eksamensmeldinger: %s (%s), %s",
             ("ekskode", "programmer", format_day("dato"))),
            ("Underv.meld: %s, %s",
             ("undvkode", format_day("dato"))),
            ("Utd. plan: %s, %s, %d, %s",
             ("studieprogramkode", "terminkode_bekreft", "arstall_bekreft",
              format_day("dato_bekreftet"))),
            ("Semesterregistrert: %s - %s, registrert: %s, endret: %s",
             ("regstatus", "regformkode",
              format_day("dato_endring"), format_day("dato_regform_endret"))),
            ("Semesterbetaling: %s - %s, betalt: %s",
             ("betstatus", "betformkode",
              format_day('dato_betaling'))),
            ("Registrert med status_dod: %s",
             ("status_dod",)),
        ]),
        perm_filter='can_get_student_info')

    def person_student_info(self, operator, person_id):
        person_exists = False
        person = None
        try:
            person = self._get_person(*self._map_person_id(person_id))
            person_exists = True
        except CerebrumError as e:
            # Check if person exists in FS, but is not imported yet, e.g.
            # emnestudents. These should only be listed with limited
            # information.
            if person_id and len(person_id) == 11 and person_id.isdigit():
                try:
                    person_id = fodselsnr.personnr_ok(person_id)
                except Exception:
                    raise e
                self.logger.debug('Unknown person %r, asking FS directly',
                                  person_id)
                self.ba.can_get_student_info(operator.get_entity_id(), None)
                fodselsdato, pnum = person_id[:6], person_id[6:]
            else:
                raise e
        else:
            self.ba.can_get_student_info(operator.get_entity_id(), person)
            fnr = person.get_external_id(
                id_type=self.const.externalid_fodselsnr,
                source_system=self.const.system_fs)
            if not fnr:
                raise CerebrumError("No matching fnr from FS")
            fodselsdato, pnum = fodselsnr.del_fnr(fnr[0]['external_id'])
        ret = []
        try:
            db = database.connect(user=cereconf.FS_USER,
                                  service=cereconf.FS_DATABASE_NAME,
                                  DB_driver=cereconf.DB_DRIVER_ORACLE)
        except database.DatabaseError as e:
            self.logger.warn("Can't connect to FS (%s)", text_type(e))
            raise CerebrumError("Can't connect to FS, try later")
        fs = FS(db)
        for row in fs.student.get_undervisningsmelding(fodselsdato, pnum):
            ret.append({
                'undvkode': row['emnekode'],
                'dato': row['dato_endring'],
            })

        har_opptak = set()
        if person_exists:
            for row in fs.student.get_studierett(fodselsdato, pnum):
                har_opptak.add(row['studieprogramkode'])
                ret.append({
                    'studprogkode': row['studieprogramkode'],
                    'studierettstatkode': row['studierettstatkode'],
                    'studentstatkode': row['studentstatkode'],
                    'studieretningkode': row['studieretningkode'],
                    'dato_tildelt': row['dato_studierett_tildelt'],
                    'dato_gyldig_til': row['dato_studierett_gyldig_til'],
                    'privatist': row['status_privatist'],
                })

            for row in fs.student.get_eksamensmeldinger(fodselsdato, pnum):
                programmer = []
                for row2 in fs.info.get_emne_i_studieprogram(row['emnekode']):
                    if row2['studieprogramkode'] in har_opptak:
                        programmer.append(row2['studieprogramkode'])
                ret.append({
                    'ekskode': row['emnekode'],
                    'programmer': ",".join(programmer),
                    'dato': row['dato_opprettet'],
                })

            for row in fs.student.get_utdanningsplan(fodselsdato, pnum):
                ret.append({
                    'studieprogramkode': row['studieprogramkode'],
                    'terminkode_bekreft': row['terminkode_bekreft'],
                    'arstall_bekreft': row['arstall_bekreft'],
                    'dato_bekreftet': row['dato_bekreftet'],
                })

            def _ok_or_not(input):
                """Helper function for proper feedback of status."""
                if not input or input == 'N':
                    return 'Nei'
                if input == 'J':
                    return 'Ja'
                return input

            semregs = tuple(fs.student.get_semreg(fodselsdato, pnum,
                                                  only_valid=False))
            for row in semregs:
                ret.append({
                    'regstatus': _ok_or_not(row['status_reg_ok']),
                    'regformkode': row['regformkode'],
                    'dato_endring': row['dato_endring'],
                    'dato_regform_endret': row['dato_regform_endret'],
                })
                ret.append({
                    'betstatus': _ok_or_not(row['status_bet_ok']),
                    'betformkode': row['betformkode'],
                    'dato_betaling': row['dato_betaling'],
                })
            # The semreg and sembet lines should always be sent, to make it
            # easier for the IT staff to see if a student have paid or not.
            if not semregs:
                ret.append({
                    'regstatus': 'Nei',
                    'regformkode': None,
                    'dato_endring': None,
                    'dato_regform_endret': None,
                })
                ret.append({
                    'betstatus': 'Nei',
                    'betformkode': None,
                    'dato_betaling': None,
                })

        db.close()
        return ret

    #
    # filtered user history
    #
    # TODO: Why is the method named user_history_filtered? Does anything call
    #       this remotely?
    #
    all_commands['user_history_filtered'] = Command(
        ("user", "history"),
        AccountName(help_ref='account_name_id'),
        perm_filter='can_show_history')

    def user_history_filtered(self, operator, accountname):
        self.logger.warn("in user history filtered")
        account = self._get_account(accountname)
        self.ba.can_show_history(operator.get_entity_id(), account)
        ret = []
        timedelta = "%s" % (DateTime.mxDateTime.now() -
                            DateTime.DateTimeDelta(7))
        timeperiod = timedelta.split(" ")

        for r in self.db.get_log_events(0,
                                        subject_entity=account.entity_id,
                                        sdate=timeperiod[0]):
            ret.append(self._format_changelog_entry(r))

        ret_val = ""
        for item in ret:
            ret_val += "\n"
            for key, value in item.items():
                ret_val += "%s\t" % str(value)
        return ret_val

    #
    # user restore
    #
    # all_commands['user_restore'] = Command(
    #     ('user', 'restore'),
    #     prompt_func=user_restore_prompt_func,
    #     perm_filter='can_create_user')
    #
    # TODO: Can we just use the UiO implementation here in stead? Difference is
    # that:
    # - UiO also removes membership from expired groups
    # - UiO restores the group and membership if the group is marked with a
    #   personal_group trait.

    def user_restore(self, operator, accountname, aff_ou, home):
        ac = self._get_account(accountname)
        # Check if the account is deleted or reserved
        if not ac.is_deleted() and not ac.is_reserved():
            raise CerebrumError('Please contact brukerreg to restore %r' %
                                accountname)

        # Checking to see if the home path is hardcoded.
        # Raises CerebrumError if the disk does not exist.
        if not home:
            raise CerebrumError('Home must be specified')
        elif home[0] != ':':  # Hardcoded path
            disk_id, home = self._get_disk(home)[1:3]
        else:
            if not self.ba.is_superuser(operator.get_entity_id()):
                raise PermissionDenied('Only superusers may use hardcoded'
                                       ' path')
            disk_id, home = None, home[1:]

        # Check if the operator can alter the user
        if not self.ba.can_create_user(operator.get_entity_id(), ac, disk_id):
            raise PermissionDenied('User restore is limited')

        # We demote posix
        try:
            pu = self._get_account(accountname, actype='PosixUser')
        except CerebrumError:
            pu = Utils.Factory.get('PosixUser')(self.db)
        else:
            pu.delete_posixuser()
            pu = Utils.Factory.get('PosixUser')(self.db)

        # We remove all old group memberships
        grp = self.Group_class(self.db)
        for row in grp.search(member_id=ac.entity_id):
            grp.clear()
            grp.find(row['group_id'])
            grp.remove_member(ac.entity_id)
            grp.write_db()

        # We remove all (the old) affiliations on the account
        for row in ac.get_account_types(filter_expired=False):
            ac.del_account_type(row['ou_id'], row['affiliation'])

        # Automatic selection of affiliation. This could be used if the user
        # should not choose affiliations.
        # # Sort affiliations according to creation date (newest first), and
        # # try to save it for later. If there exists no affiliations, we'll
        # # raise an error, since we'll need an affiliation to copy from the
        # # person to the account.
        # try:
        #     tmp = sorted(pe.get_affiliations(),
        #                  key=lambda i: i['create_date'], reverse=True)[0]
        #     ou, aff = tmp['ou_id'], tmp['affiliation']
        # except IndexError:
        #     raise CerebrumError('Person must have an affiliation')

        # We set the affiliation selected by the operator.
        self._user_create_set_account_type(ac,
                                           ac.owner_id,
                                           aff_ou['ou_id'],
                                           aff_ou['aff'])

        # And promote posix
        old_uid = self._lookup_old_uid(ac.entity_id)
        if old_uid is None:
            uid = pu.get_free_uid()
        else:
            uid = old_uid

        shell = self.const.posix_shell_bash

        # Populate the posix user, and write it to the database
        pu.populate(uid, None, None, shell, parent=ac,
                    creator_id=operator.get_entity_id())
        try:
            pu.write_db()
        except self.db.IntegrityError as e:
            self.logger.debug("IntegrityError (user_restore): %r", e)
            self.db.rollback()
            raise CerebrumError('Please contact brukerreg in order to restore')

        # Unset the expire date
        ac.expire_date = None

        # Add them spreads
        for s in cereconf.BOFHD_NEW_USER_SPREADS:
            if not pu.has_spread(self.const.Spread(s)):
                pu.add_spread(self.const.Spread(s))

        # And remove them quarantines (except those defined in cereconf)
        for q in ac.get_entity_quarantine():
            if (text_type(self.const.Quarantine(q['quarantine_type']))
                    not in cereconf.BOFHD_RESTORE_USER_SAVE_QUARANTINES):
                ac.delete_entity_quarantine(q['quarantine_type'])

        # We set the new homedir
        default_home_spread = self._get_constant(self.const.Spread,
                                                 cereconf.DEFAULT_HOME_SPREAD,
                                                 'spread')

        homedir_id = pu.set_homedir(
            disk_id=disk_id, home=home,
            status=self.const.home_status_not_created)
        pu.set_home(default_home_spread, homedir_id)

        # We'll set a new password and store it for printing
        passwd = ac.make_passwd(ac.account_name)
        ac.set_password(passwd)

        operator.store_state('new_account_passwd',
                             {'account_id': int(ac.entity_id),
                              'password': passwd})

        # We'll need to write to the db, in order to store stuff.
        try:
            ac.write_db()
        except self.db.IntegrityError as e:
            self.logger.debug("IntegrityError (user_restore): %r", e)
            self.db.rollback()
            raise CerebrumError('Please contact brukerreg in order to restore')

        # Return string with some info
        if ac.get_entity_quarantine():
            note = '\nNotice: Account is quarantined!'
        else:
            note = ''

        if old_uid is None:
            tmp = ', new uid=%i' % uid
        else:
            tmp = ', reused old uid=%i' % old_uid

        return ('OK, promoted %s to posix user%s.\n'
                'Password altered. Use misc list_password to print or view '
                'the new password.%s' % (accountname, tmp, note))

    def _format_ou_name(self, ou):
        """
        Override _format_ou_name to support OUs without SKO.
        """
        short_name = ou.get_name_with_language(
            name_variant=self.const.ou_name_short,
            name_language=self.const.language_nb,
            default="")

        # return None if ou does not have stedkode
        if ou.fakultet is not None:
            return "%02i%02i%02i (%s)" % (ou.fakultet, ou.institutt,
                                          ou.avdeling, short_name)
        else:
            return "None"


class ContactCommands(BofhdContactCommands):
    """ entity_contactinfo_* commands with custom uio auth. """
    authz = bofhd_auth.UitContactAuth


class EmailCommands(bofhd_email.BofhdEmailCommands):
    """ UiO specific email commands and overloads. """

    all_commands = {}
    hidden_commands = {}
    omit_parent_commands = {
        'email_tripnote',
        'email_tripnote_list',
        'email_tripnote_add',
        'email_tripnote_remove',
    }
    parent_commands = True
    authz = bofhd_auth.UitEmailAuth

    @classmethod
    def get_help_strings(cls):
        email_cmds = {
            'email': {
                'email_forward_info':
                    "Show information about an address that is forwarded to",
                'email_move':
                    "Move a user's e-mail to another server",
                'email_show_reservation_status':
                    "Show reservation status for an account",
                "email_move_domain_addresses":
                    "Move the first account's e-mail addresses at a domain to "
                    "the second account",
            }
        }
        arg_help = {
            'yes_no_move_primary':
                ['move_primary',
                 'Should primary email address be moved? (y/n)'],
        }
        return merge_help_strings(
            super(EmailCommands, cls).get_help_strings(),
            ({}, email_cmds, arg_help))

    def __email_forward_destination_allowed(self, account, address):
        """ Check if the forward is compilant with Norwegian law"""
        person = Utils.Factory.get('Person')(self.db)
        if (account.owner_type == self.const.entity_person and
                person.list_affiliations(
                    person_id=account.owner_id,
                    source_system=self.const.system_sap,
                    affiliation=self.const.affiliation_ansatt)):
            try:
                self._get_email_domain_from_str(address.split('@')[-1])
            except CerebrumError:
                return False
        return True

    def _get_email_target_and_address(self, address):
        # Support DistributionGroup email target lookup
        try:
            return super(EmailCommands,
                         self)._get_email_target_and_address(address)
        except CerebrumError as e:
            # Not found, maybe distribution group?
            try:
                dlgroup = Utils.Factory.get("DistributionGroup")(self.db)
                dlgroup.find_by_name(address)
                et = Email.EmailTarget(self.db)
                et.find_by_target_entity(dlgroup.entity_id)
                epa = Email.EmailPrimaryAddressTarget(self.db)
                epa.find(et.entity_id)
                ea = Email.EmailAddress(self.db)
                ea.find(epa.email_primaddr_id)
                return et, ea
            except Errors.NotFoundError:
                raise e

    def _get_email_target_and_dlgroup(self, address):
        """Returns a tuple consisting of the email target associated
        with address and the account if the target type is user.  If
        there is no at-sign in address, assume it is an account name.
        Raises CerebrumError if address is unknown."""
        et, ea = self._get_email_target_and_address(address)
        grp = None
        # what will happen if the target was a dl_group but is now
        # deleted? it's possible that we should have created a new
        # target_type = dlgroup_deleted, but it seemed redundant earlier
        # now, i'm not so sure (Jazz, 2013-12(
        if et.email_target_type in (self.const.email_target_dl_group,
                                    self.const.email_target_deleted):
            grp = self._get_group(et.email_target_entity_id,
                                  idtype='id',
                                  grtype="DistributionGroup")
        return et, grp

    def _is_email_delivery_stopped(self, ldap_target):
        """ Test if email delivery is turned off in LDAP for a user. """
        import ldap
        import ldap.filter
        import ldap.ldapobject
        ldapconns = [ldap.ldapobject.ReconnectLDAPObject("ldap://%s/" % server)
                     for server in cereconf.LDAP_SERVERS]
        target_filter = ("(&(target=%s)(mailPause=TRUE))" %
                         ldap.filter.escape_filter_chars(ldap_target))
        for conn in ldapconns:
            try:
                # FIXME: cereconf.LDAP_MAIL['dn'] has a bogus value, so we
                # must hardcode the DN.
                res = conn.search_s("cn=targets,cn=mail,dc=uio,dc=no",
                                    ldap.SCOPE_ONELEVEL, target_filter,
                                    ["1.1"])
                if len(res) != 1:
                    return False
            except ldap.LDAPError:
                self.logger.error("LDAP search failed", exc_info=True)
                return False
        return True

    def _email_info_detail(self, acc):
        info = []
        eq = Email.EmailQuota(self.db)
        try:
            eq.find_by_target_entity(acc.entity_id)
            et = Email.EmailTarget(self.db)
            et.find_by_target_entity(acc.entity_id)
            es = Email.EmailServer(self.db)
            es.find(et.email_server_id)

            # exchange-relatert-jazz
            # since Exchange-users will have a different kind of
            # server this code will not be affected at Exchange
            # roll-out It may, however, be removed as soon as
            # migration is completed (up to and including
            # "dis_quota_soft': eq.email_quota_soft})")
            if es.email_server_type == self.const.email_server_type_cyrus:
                pw = self.db._read_password(cereconf.CYRUS_HOST,
                                            cereconf.CYRUS_ADMIN)
                used = 'N/A'
                limit = None
                try:
                    cyrus = Utils.CerebrumIMAP4_SSL(
                        es.name,
                        ssl_version=ssl.PROTOCOL_TLSv1)
                    # IVR 2007-08-29 If the server is too busy, we do not want
                    # to lock the entire bofhd.
                    # 5 seconds should be enough
                    cyrus.socket().settimeout(5)
                    cyrus.login(cereconf.CYRUS_ADMIN, pw)
                    res, quotas = cyrus.getquota("user." + acc.account_name)
                    cyrus.socket().settimeout(None)
                    if res == "OK":
                        for line in quotas:
                            try:
                                folder, qtype, qused, qlimit = line.split()
                                if qtype == "(STORAGE":
                                    used = str(int(qused)/1024)
                                    limit = int(qlimit.rstrip(")"))/1024
                            except ValueError:
                                # line.split fails e.g. because quota isn't set
                                # on server
                                folder, junk = line.split()
                                self.logger.warning("No IMAP quota set for %r",
                                                    acc.account_name)
                                used = "N/A"
                                limit = None
                except (bofhd_uio_cmds.TimeoutException, socket.error):
                    used = 'DOWN'
                except bofhd_uio_cmds.ConnectException as e:
                    used = exc_to_text(e)
                except imaplib.IMAP4.error as e:
                    used = 'DOWN'
                info.append({'quota_hard': eq.email_quota_hard,
                             'quota_soft': eq.email_quota_soft,
                             'quota_used': used})
                if limit is not None and limit != eq.email_quota_hard:
                    info.append({'quota_server': limit})
            else:
                info.append({'dis_quota_hard': eq.email_quota_hard,
                             'dis_quota_soft': eq.email_quota_soft})
        except Errors.NotFoundError:
            pass
        # exchange-relatert-jazz
        # delivery for exchange-mailboxes is not regulated through
        # LDAP, and LDAP should not be checked there my be some need
        # to implement support for checking if delivery is paused in
        # Exchange, but at this point only very vague explanation has
        # been given and priority is therefore low
        if acc.has_spread(self.const.spread_uit_exchange):
            return info
        # Check if the ldapservers have set mailPaused
        if self._is_email_delivery_stopped(acc.account_name):
            info.append({'status': 'Paused (migrating to new server)'})

        return info

    def _email_info_dlgroup(self, groupname):
        et, dl_group = self._get_email_target_and_dlgroup(groupname)
        ret = []
        # we need to make the return value conform with the
        # client requeirements
        tmpret = dl_group.get_distgroup_attributes_and_targetdata()
        for x in tmpret:
            if tmpret[x] == 'T':
                ret.append({x: 'Yes'})
                continue
            elif tmpret[x] == 'F':
                ret.append({x: 'No'})
                continue
            ret.append({x: tmpret[x]})
        return ret

    #
    # email forward_add <account>+ <address>+
    #
    def email_forward_add(self, operator, uname, address):
        """Add an email-forward to a email-target asociated with an account."""
        # Override email_forward_add with check for employee email addr
        et, acc = self._get_email_target_and_account(uname)
        if acc and not self.__email_forward_destination_allowed(acc, address):
            raise CerebrumError("Employees cannot forward e-mail to"
                                " external addresses")
        return super(EmailCommands, self).email_forward_add(operator,
                                                            uname,
                                                            address)

    #
    # email forward_info
    #
    all_commands['email_forward_info'] = Command(
        ('email', 'forward_info'),
        EmailAddress(),
        fs=FormatSuggestion([('%s', ('id', ))]),
        perm_filter='can_email_forward_info',
    )

    def email_forward_info(self, operator, forward_to):
        """List owners of email forwards."""
        self.ba.can_email_forward_info(operator.get_entity_id())
        ef = Email.EmailForward(self.db)
        et = Email.EmailTarget(self.db)
        ac = Utils.Factory.get('Account')(self.db)
        ret = []

        # Different output format for different input.
        def rfun(r):
            return (r if '%' not in forward_to
                    else '%-12s %s' % (r, fwd['forward_to']))

        for fwd in ef.search(forward_to):
            try:
                et.clear()
                ac.clear()
                et.find(fwd['target_id'])
                ac.find(et.email_target_entity_id)
                ret.append({'id': rfun(ac.account_name)})
            except Errors.NotFoundError:
                ret.append({'id': rfun('id:%s' % et.entity_id)})
        return ret

    #
    # email show_reservation_status
    #
    all_commands['email_show_reservation_status'] = Command(
        ('email', 'show_reservation_status'),
        AccountName(),
        fs=FormatSuggestion([("%-9s %s", ("uname", "hide"))]),
        perm_filter='is_postmaster')

    def email_show_reservation_status(self, operator, uname):
        """Display reservation status for a person."""
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('Access to this command is restricted')
        hidden = True
        account = self._get_account(uname)
        if account.owner_type == self.const.entity_person:
            person = self._get_person('entity_id', account.owner_id)
            if person.has_e_reservation():
                hidden = True
            elif person.get_primary_account() != account.entity_id:
                hidden = True
            else:
                hidden = False
        return {
            'uname': uname,
            'hide': 'hidden' if hidden else 'visible',
        }

    #
    # email move
    #
    all_commands['email_move'] = Command(
        ("email", "move"),
        AccountName(help_ref="account_name", repeat=True),
        SimpleString(help_ref='string_email_host'),
        perm_filter='can_email_move')

    def email_move(self, operator, uname, server):
        acc = self._get_account(uname)
        self.ba.can_email_move(operator.get_entity_id(), acc)
        et = Email.EmailTarget(self.db)
        et.find_by_target_entity(acc.entity_id)
        old_server = et.email_server_id
        es = Email.EmailServer(self.db)
        try:
            es.find_by_name(server)
        except Errors.NotFoundError:
            raise CerebrumError("%r is not registered as an e-mail server" %
                                server)
        if old_server == es.entity_id:
            raise CerebrumError("User is already at %s" % server)

        et.email_server_id = es.entity_id
        et.write_db()
        return "OK, updated e-mail server for %s (to %s)" % (uname, server)

    #
    # email move_domain_addresses
    #
    all_commands['email_move_domain_addresses'] = Command(
        ("email", "move_domain_addresses"),
        AccountName(help_ref="account_name"),
        AccountName(help_ref="account_name"),
        SimpleString(help_ref='email_domain', optional=True,
                     default=cereconf.NO_MAILBOX_DOMAIN_EMPLOYEES),
        YesNo(help_ref='yes_no_move_primary', optional=True, default="No"),
        perm_filter="is_superuser")

    def _move_email_address(self, address, reassigned_addresses, dest_et):
        ea = Email.EmailAddress(self.db)
        ea.find(address['address_id'])
        ea.email_addr_target_id = dest_et.entity_id
        ea.write_db()
        reassigned_addresses.append(ea.get_address())

    def _move_primary_email_address(self, address, reassigned_addresses,
                                    dest_et, epat):
        epat.delete()
        self._move_email_address(address, reassigned_addresses, dest_et)
        epat.clear()
        try:
            epat.find(dest_et.entity_id)
        except Errors.NotFoundError:
            pass
        else:
            epat.delete()
        epat.clear()
        epat.populate(address['address_id'], parent=dest_et)
        epat.write_db()

    def _move_ad_email(self, email, dest_uname):
        ad = ad_email.AdEmail(self.db)
        ad.delete_ad_email(account_name=dest_uname)
        ad.set_ad_email(dest_uname, email['local_part'], email['domain_part'])

        ad_emails_added = "Updated ad email {} for {}. ".format(
            email['local_part']+"@"+email['domain_part'],
            dest_uname
        )
        return ad_emails_added

    def email_move_domain_addresses(self, operator, source_uname, dest_uname,
                                    domain_str, move_primary):
        """Move an account's e-mail addresses to another account

        :param domain_str: email domain to be affected
        :param move_primary: move primary email address
        """
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")

        move_primary = self._get_boolean(move_primary)
        source_account = self._get_account(source_uname)
        source_et = self._get_email_target_for_account(source_account)
        dest_account = self._get_account(dest_uname)
        dest_et = self._get_email_target_for_account(dest_account)
        epat = Email.EmailPrimaryAddressTarget(self.db)

        try:
            epat.find(source_et.entity_id)
        except Errors.NotFoundError:
            epat.clear()

        reassigned_addresses = []
        for address in source_et.get_addresses():
            if address['domain'] == domain_str:

                if address['address_id'] == epat.email_primaddr_id:
                    if move_primary:
                        self._move_primary_email_address(address,
                                                         reassigned_addresses,
                                                         dest_et,
                                                         epat)
                else:
                    self._move_email_address(address, reassigned_addresses,
                                             dest_et)
        # Managing ad_email
        ad_emails_added = ""
        if domain_str == cereconf.NO_MAILBOX_DOMAIN_EMPLOYEES:
            ad = ad_email.AdEmail(self.db)

            if move_primary:
                ad_emails = ad.search_ad_email(account_name=source_uname)
                if len(ad_emails) == 1:
                    ad_emails_added = self._move_ad_email(ad_emails[0],
                                                          dest_uname)
            # TODO:
            #  If this command is called with move_primary=False,
            #  the source account's primary email address will be left
            #  intact, but it's corresponding ad_email will be deleted.
            #  This mimics the functionality of the uit-script move_emails.py,
            #  but is it really what we want?
            ad.delete_ad_email(account_name=source_uname)

        return ("OK, reassigned {}. ".format(reassigned_addresses)
                + ad_emails_added)


class BofhdRequestCommands(bofhd_requests_cmds.BofhdExtension):
    authz = bofhd_auth.UitBofhdRequestsAuth


class AccessCommands(bofhd_access.BofhdAccessCommands):
    """UiT specific access * commands"""
    authz = bofhd_auth.UitAccessAuth
