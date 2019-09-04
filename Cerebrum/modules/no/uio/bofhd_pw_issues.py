#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2019 University of Oslo, Norway
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
""" This module contains tools for the password_issues bofh command """

from mx import DateTime
from six import text_type
from Cerebrum import Utils, Errors
from Cerebrum.modules.bofhd.bofhd_core import (BofhdCommonMethods,
                                               BofhdCommandBase)
from Cerebrum.modules.bofhd.errors import (CerebrumError,
                                           PermissionDenied)
from Cerebrum.modules.bofhd.cmd_param import (AccountName,
                                              Command,
                                              FormatSuggestion)


def check_ac_basics(ac, correct_ac_type):
    """Checks if an account is deleted, expired or not belonging to a person"""
    if ac.is_deleted():
        raise CerebrumError('Account is deleted')
    elif ac.is_expired():
        raise CerebrumError('Account has expired')
    elif ac.owner_type != correct_ac_type:
        raise CerebrumError('Account is not owned by a person')
    return


def get_pe_from_ac(ac, db):
    """Creates pe from ac and db"""
    # Move elsewhere/check if relevante duplicate exists?
    try:
        pe = Utils.Factory.get('Person')(db)
        pe.find(ac.owner_id)
    except Errors.NotFoundError:
        raise CerebrumError('Account is not owned by a person')
    return pe


def _filter_trouble_traits(co, traits):
    """Check if a traits-dict contains traits that are problematic
    for the SMS-service.

    Pofh checks for such traits twice: 'sysadm_account' and
    'important_acc' in one test, 'reserve_passw' in another. These
    traits are hard coded into cerebrum_api_v1.py.
    """
    return set(traits.keys()) & {co.trait_sysadm_account,
                                 co.trait_reservation_sms_password,
                                 co.trait_important_account}


def _filter_informative_traits(co, traits):
    """Check if a traits-dict contains traits that are unproblematic,
    but still informative for determining the availability of the  SMS-service.
    """
    return set(traits.keys()) & {co.trait_sms_welcome,
                                 co.trait_student_new,
                                 co.trait_account_new,
                                 co.trait_primary_aff}


def investigate_traits(ac, co):
    """Investigate if ac contains problematic or informative traits"""
    traits = ac.get_traits()
    results = {}
    if traits:
        trouble_traits = _filter_trouble_traits(co, traits)
        if trouble_traits:
            results['issues'] = trouble_traits
        info_traits = _filter_informative_traits(co, traits)
        if info_traits:
            results['info'] = info_traits
    return results


def is_member_of_admingroups(ac, db):
    """Check account is member of group 'admin' or 'superusers'.
    pofh specifically checks these two"""
    Groupclass = Utils.Factory.get("Group")
    groups = {r['name'] for r in Groupclass(db).search(member_id=ac.entity_id)}
    return 'superusers' in groups or 'admin' in groups


def illegal_quarantines(ac, co):
    """Check if account has any illegal quarantines
    legal quarantine_type hard coded in example.pofh.cfg
    """
    qr = ac.get_entity_quarantine(only_active=True)
    qr = {text_type(co.human2constant(q['quarantine_type'])) for q in qr}
    return qr - {'svakt_passord', 'autopassord'}


def filter_valid_affiliations(affiliations):
    """Filter out valid affiliations"""
    now = DateTime.now()
    for aff in affiliations:
        del_date = aff['deleted_date']
        if not del_date or del_date > now:
            yield {'ssys': aff['source_system'],
                   'status': aff['status']}


def filter_mobilephones(co, contact_rows):
    """Extract mobile phone numbers with corresponding date and source
    system from contact rows.
    """
    phone_types = {int(co.contact_mobile_phone),
                   int(co.contact_private_mobile),
                   int(co.contact_private_mobile_visible)}
    for row in contact_rows:
        if (row['contact_type'] in phone_types):
            yield {'ssys': row['source_system'],
                   'number': row['contact_value'],
                   'date': row['last_modified']}


def merge_affs_and_phones(valid_affiliations, phones):
    """
    Merges affiliations and phones, ensuring that noe bogus
    duplicates are kept.

    Affs. contains: ssys, status
    Phone contains: ssys, number, date, has_been_added

    If ssys match, then the phone is from a valid affilition, and we want:
    (a) ssys, status, number, date
    If aff does not match any phones, then the affiliation is not associated
    with a phone. We want:
    (b) ssys, status, None, None
    If there is a phone that matches no valid affiliation, then the phone is
    associated with an *invalid* affiliation. We want:
    (c) ssys, None, number, date

    First, we loop through the phones, and add a flag to keep track of phones
    that has been added as entry type a.
    Then, we loop through the valid affiliations and create all entries of type
    a and b. If there are any unused phones left, these are added as entry
    type c.
    """
    entries = []
    Phones = list(phones)
    for phone in Phones:
        phone['unused'] = True

    def valid_phone(aff):
        for i, phone in enumerate(Phones):
            if aff['ssys'] == phone['ssys']:
                entry = {'ssys': aff['ssys'], 'status': aff['status'],
                         'number': phone['number'], 'date': phone['date']}
                phone['unused'] = False
                return entry
        return {'ssys': aff['ssys'], 'status': aff['status'],
                'number': None, 'date': None}

    for aff in valid_affiliations:
        entries.append(valid_phone(aff))
    for phone in phones:
        if phone['unused']:
            entries.append({'ssys': phone['ssys'], 'status': None,
                            'number': phone['number'], 'date': phone['date']})
    return entries


def any_valid_phones(phone_table):
    """Return True if a phone table contains any entry with a
    status (phone number comes from a valid affiliation) and
    a non-recent date (one week or more)
    """
    now = DateTime.now()
    last_week = now - DateTime.TimeDelta(24*7)
    for phone in phone_table:
        if phone['status'] and phone['number']:
            date = phone['date']
            if not date or date < last_week:
                return True
    return False


def format_phone_table(co, phone_table):
    now = DateTime.now()
    lastweek = now - DateTime.TimeDelta(24*7)
    table = []
    for i, entry in enumerate(sorted(phone_table)):
        ssys = entry['ssys']
        ssys_s = '{0: <8}'.format(text_type(
            co.AuthoritativeSystem(ssys)))
        status = entry['status']
        if status:
            status_s = '{0: <24}'.format(text_type(co.human2constant(status)))
        else:
            status_s = '{0: <24}'.format(text_type('invalid affiliation'))
        number = entry['number']
        if number:
            num_s = '{0: >18}'.format(text_type(number))
            mod_date = entry['date']
            if mod_date and mod_date > lastweek:
                date_s = '  (changed {} days ago)'.format(int(
                    (now - mod_date).days))
            else:
                date_s = '   date is OK'
        else:
            num_s = '{0: >18}'.format(None)
            date_s = '         None'
        if i == 0:
            k0, k1, k2, k3 = 'ssys0', 'status0', 'number0', 'date_str0'
        else:
            k0, k1, k2, k3 = 'ssysn', 'statusn', 'numbern', 'date_strn'
        table.append({k0: ssys_s, k1: status_s, k2: num_s, k3: date_s})
    return table


def format_simple(entries, keybase='issue'):
    data = []
    for i, ie in enumerate(entries):
        data.append({keybase + '0': ie} if i == 0 else {keybase + 'n': ie})
    return data


class PassWordIssues(BofhdCommonMethods):
    """This class exists to serve the bofh command
    `password issues`.

    This class does two things:
    1) Checks all necessary information from an account
       object to determine *whether* the SMS service can
       be used for password reset, and
    2) Formats this data into a shape required by the bofh
       command.
    """
    def __init__(self, ac, db):
        self.ac = ac
        self.database = db
        self.co = Utils.Factory.get('Constants')(db)
        self.pe = get_pe_from_ac(ac, db)
        self.data = []

    def __call__(self):
        # basics
        _ = check_ac_basics(self.ac, self.co.entity_person)
        # Problematic or informative traits?
        trait_data = investigate_traits(self.ac, self.co)
        issues = []
        info = []
        if 'info' in trait_data:
            trait_info = trait_data['info']
            in_str = 'Informative traits:' + ' {}'*len(trait_info)
            info.append(in_str.format(*trait_info))
        if 'issues' in trait_data:
            trait_issues = trait_data['issues']
            tr_str = 'Illegal traits:' + ' {}'*len(trait_issues)
            issues.append(tr_str.format(*trait_issues))
        # Member of an admin group?
        if is_member_of_admingroups(self.ac, self.database):
            issues.append('Member of admin group')
        # Illegal quarantines?
        quars = illegal_quarantines(self.ac, self.co)
        if quars:
            q_str = 'Illegal quarantines:' + ' {}'*len(quars)
            issues.append(q_str.format(*quars))
        # Affiliatins and phones
        contact_rows = self.pe.get_contact_info()
        if not contact_rows:
            issues.append('No contact info')
        valid_affiliations = [a for a in filter_valid_affiliations(
            self.pe.get_affiliations())]
        if not valid_affiliations:
            issues.append('No valid affiliatons')
        phones = [ent for ent in filter_mobilephones(self.co, contact_rows)]
        phone_table = merge_affs_and_phones(valid_affiliations, phones)
        if phone_table:
            if not any_valid_phones(phone_table):
                issues.append('No valid phones')
            for entry in format_phone_table(self.co, phone_table):
                self.data.append(entry)
        else:
            issues.append('No phones')
        # Finish formatting
        if issues:
            self.data.append({'sms_work_p': 'UNAVAILABLE',
                              'accountname': self.ac.account_name})
            for issue in format_simple(issues, keybase='issue'):
                self.data.append(issue)
        else:
            self.data.append({'sms_work_p': 'available',
                              'accountname': self.ac.account_name})

        for info in format_simple(info, keybase='info'):
            self.data.append(info)


class BofhdExtension(BofhdCommandBase):
    all_commands = {}

    @classmethod
    def get_help_strings(cls):
        group_help = {
            'password': "Miscellaneous commands",
        }

        command_help = {
            'misc': {
                'password_info': 'Show if SMS pw service is available for ac',
            },
        }
        arg_help = {
            'account_name':
            ['uname', 'Enter account name',
             'Enter the name of the account for this operation'],
        }
        return (group_help,
                command_help,
                arg_help)

    #
    # misc password_issues
    #
    all_commands['misc_password_issues'] = Command(
        ("misc", "password_issues"),
        AccountName(help_ref="id:target:account"),
        fs=FormatSuggestion([
            ('\nSMS service is %s for %s!\n', ('sms_work_p', 'accountname')),
            ('Issues found:\n'
             ' - %s', ('issue0',)),
            (' - %s', ('issuen',)),
            ('Mobile phone numbers and affiliations:\n'
             ' - %s %s %s %s',
             ('ssys0', 'status0', 'number0', 'date_str0')),
            (' - %s %s %s %s',
             ('ssysn', 'statusn', 'numbern', 'date_strn')),
            ('Additional info:\n'
             ' - %s', ('info0',)),
            (' - %s', ('infon',)), ]),
        perm_filter='can_create_user')

    def misc_password_issues(self, operator, accountname):
        """Determine why a user can't use the SMS service for resetting pw.

        The cause(s) of failure and/or possibly relevant additional
        information is returned.  There are two kinds of issues:
        Category I issues raises an error without further
        testing. Cathegory II issues may require a bit more detective
        work from Houston. COnsequently, all checks are performed in
        case more than one issue is present.  If no potential problems
        are found, this is clearly stated.

        The authoritative check is performed by pofh, and this function
        duplicates the same checks (and performs some additional ones).
        """

        # Primary intended users are Houston.
        # They are privileged, but not superusers.
        ac = self._get_account(accountname, idtype='name')
        if not self.ba.can_create_user(operator.get_entity_id(), ac):
            raise PermissionDenied("Access denied")
        pwi = PassWordIssues(ac, self.db)
        _ = pwi()
        return pwi.data


if __name__ == '__main__':
    db = Utils.Factory.get('Database')()
    logger = Utils.Factory.get_logger('console')
    pwi = BofhdExtension(db, logger)
