# -*- coding: utf-8 -*-
#
# Copyright 2019-2023 University of Oslo, Norway
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
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime

import six

from Cerebrum import Utils
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.cmd_param import (
    AccountName,
    Command,
    FormatSuggestion,
)
from Cerebrum.modules.bofhd.errors import (
    CerebrumError,
    PermissionDenied,
)
from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.utils import date_compat


# This should be equal to CEREBRUM_FRESH_DAYS which is configured in the
# pofh-backend repo.
FRESH_DAYS = 7


def check_personal_account(ac):
    """Checks if an account is deleted, expired or not belonging to a person"""
    if ac.is_deleted():
        raise CerebrumError('Account is deleted')
    if ac.is_expired():
        raise CerebrumError('Account has expired')
    if ac.owner_type != ac.const.entity_person:
        raise CerebrumError('Account is not owned by a person')


def get_personal_account_owner(ac):
    """Creates pe from ac"""
    pe = Utils.Factory.get('Person')(ac._db)
    pe.find(ac.owner_id)
    return pe


def _filter_trouble_traits(co, traits):
    """Check if a traits-dict contains traits that are problematic
    for the SMS-service.
    """
    return set(traits) & {co.trait_sysadm_account,
                          co.trait_reservation_sms_password,
                          co.trait_important_account}


def _filter_informative_traits(co, traits):
    """Check if a traits-dict contains traits that are unproblematic,
    but still informative for determining the availability of the  SMS-service.
    """
    return set(traits) & {co.trait_sms_welcome,
                          co.trait_student_new,
                          co.trait_account_new,
                          co.trait_primary_aff}


def investigate_traits(ac):
    """Investigate if ac contains problematic or informative traits"""
    co = ac.const
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


def account_is_fresh(ac):
    """ Determine if an account is fresh (newly created *or* revived)"""
    co = ac.const
    traits = ac.get_traits()
    return (co.trait_student_new in traits
            or co.trait_account_new in traits)


def is_member_of_admingroups(ac):
    """Check account is member of group 'admin' or 'superusers'.
    pofh specifically checks these two"""
    db = ac._db
    gr = Utils.Factory.get("Group")(db)
    group_names = {r['name'] for r in gr.search(member_id=ac.entity_id)}
    return 'superusers' in group_names or 'admin' in group_names


def illegal_quarantines(ac):
    """Check if account has any illegal quarantines
    legal quarantine_type hard coded in example.pofh.cfg
    """
    co = ac.const
    qr = set(
        six.text_type(co.human2constant(q['quarantine_type']))
        for q in ac.get_entity_quarantine(only_active=True))
    return qr - {'svakt_passord', 'autopassord'}


def get_affiliations(pe):
    """Filter out valid affiliations"""
    for aff in pe.get_affiliations():
        yield {
            'ssys': aff['source_system'],
            'status': aff['status'],
        }


def get_mobile_numbers(pe):
    """Extract mobile phone numbers with corresponding date and source
    system from contact rows.
    """
    co = pe.const
    phone_types = {int(co.contact_mobile_phone),
                   int(co.contact_private_mobile),
                   int(co.contact_private_mobile_visible)}
    for row in pe.get_contact_info():
        if (row['contact_type'] in phone_types):
            yield {
                'ssys': row['source_system'],
                'number': row['contact_value'],
                'date': date_compat.get_datetime_tz(row['last_modified']),
            }


def merge_affs_and_phones(co, valid_affiliations, phones):
    """
    Merges affiliations and phones, ensuring that duplicates are kept.

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
    phone_list = list(phones)
    for phone in phone_list:
        phone['unused'] = True

    def valid_phone(aff):
        for i, phone in enumerate(phone_list):
            if aff['ssys'] == phone['ssys']:
                entry = {
                    'ssys': aff['ssys'],
                    'status': aff['status'],
                    'number': phone['number'],
                    'date': phone['date'],
                }
                phone['unused'] = False
                return entry
        return {
            'ssys': aff['ssys'],
            'status': aff['status'],
            'number': None,
            'date': None,
        }
    for aff in valid_affiliations:
        entries.append(valid_phone(aff))
    for phone in phones:
        if phone['unused']:
            entries.append({
                'ssys': phone['ssys'],
                'status': None,
                'number': phone['number'],
                'date': phone['date'],
            })
    return entries


def welcome_sms_received_date(ac, co):
    traits = ac.get_traits()
    raw_date = traits.get(co.trait_sms_welcome, {}).get('date')
    # The 'date' value of traits are naive datetime objects,
    # *not* an actual date, so we need:
    return date_compat.get_date(raw_date)


def any_valid_phones(ac, phone_table):
    """Return True if a phone table contains at least one phone
    which either:
    * has not been updated in the last week,
    * unless the account is fresh,
    * or a welcome SMS has been sent after the phone was updated.
    """
    co = ac.const
    fresh_account = account_is_fresh(ac)
    last_week = datetime.date.today() - datetime.timedelta(days=7)
    for phone in phone_table:
        if phone['status'] and phone['number']:
            if fresh_account:
                return True
            date = date_compat.get_date(phone['date'])
            if not date or date < last_week:
                return True
            welcome_sms = welcome_sms_received_date(ac, co)
            if welcome_sms:
                return welcome_sms >= date
    return False


def format_phone_table(co, phone_table):
    today = datetime.date.today()
    last_week = today - datetime.timedelta(days=7)
    table = []
    for i, entry in enumerate(sorted(phone_table,
                                     key=(lambda d: (d.get('ssys'),
                                                     d.get('status'))))):
        ssys = entry['ssys']
        ssys_s = '{0: <8}'.format(six.text_type(co.AuthoritativeSystem(ssys)))
        status = entry['status']
        if status:
            status_s = '{0: <24}'.format(
                six.text_type(co.human2constant(status)))
        else:
            status_s = '{0: <24}'.format('invalid affiliation')
        number = entry['number']
        if number:
            num_s = '{0: >18}'.format(six.text_type(number))
            mod_date = date_compat.get_date(entry['date'])
            if mod_date and mod_date > last_week:
                days_ago = (today - mod_date).days
                date_s = '  (changed {} days ago)'.format(int(days_ago))
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


def format_n_list(entries, keybase='issue'):
    """
    Return keyed items for list formatting:

    >>> list(format_n_list(["a", "b", "c"], "key_"))
    [{"key_0": "a"}, {"key_n": "b"}, {"key_n": "c"}]
    """
    for i, item in enumerate(entries):
        key = keybase + ('n' if i else '0')
        yield {key: item}


def check_password_issues(ac):
    """ Check if something blocks a user from using password services.

    1) Checks all necessary information from an account
       object to determine *whether* the SMS service can
       be used for password reset, and

    2) Formats this data into a shape required by the bofh
       command.
    """
    check_personal_account(ac)

    co = ac.const
    pe = get_personal_account_owner(ac)

    data = []

    # basics
    # Problematic or informative traits?
    trait_data = investigate_traits(ac)
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
    if is_member_of_admingroups(ac):
        issues.append('Member of admin group')
    # Illegal quarantines?
    quars = illegal_quarantines(ac)
    if quars:
        q_str = 'Illegal quarantines:' + ' {}'*len(quars)
        issues.append(q_str.format(*quars))
    # Affiliatins and phones
    affiliations = list(get_affiliations(pe))
    if not affiliations:
        issues.append('No affiliatons')
    phones = list(get_mobile_numbers(pe))
    valid_source_phone = False
    for phone in phones:
        if phone['ssys'] in (co.system_dfo_sap,
                             co.system_fs,
                             co.system_greg,):
            valid_source_phone = True
            break
    if not valid_source_phone:
        issues.append('No phone number from valid source system.')

    phone_table = merge_affs_and_phones(co, affiliations, phones)
    if phone_table:
        if not any_valid_phones(ac, phone_table):
            issues.append('No valid phones')
        for entry in format_phone_table(co, phone_table):
            data.append(entry)
    else:
        issues.append('No phones')
    # Finish formatting
    if issues:
        data.append({
            'sms_work_p': 'UNAVAILABLE',
            'accountname': ac.account_name,
        })
        data.extend(format_n_list(issues, keybase='issue'))
    else:
        data.append({
            'sms_work_p': 'available',
            'accountname': ac.account_name,
        })

    data.extend(format_n_list(info, keybase='info'))

    return data


class BofhdExtension(BofhdCommandBase):

    all_commands = {}

    @classmethod
    def get_help_strings(cls):
        command_help = {
            'misc': {
                'password_issues': 'Show if SMS pw service '
                'is available for ac',
            },
        }
        return merge_help_strings(
            get_help_strings(),
            ({}, command_help, {}),
        )

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
        perm_filter='can_set_password')

    def misc_password_issues(self, operator, accountname):
        """Determine why a user can't use the SMS service for resetting pw.

        The cause(s) of failure and/or possibly relevant additional
        information is returned.  There are two kinds of issues:
        Category I issues raises an error without further
        testing. Category II issues may require a bit more detective
        work from Houston. Consequently, all checks are performed in
        case more than one issue is present.  If no potential problems
        are found, this is clearly stated.

        The authoritative check is performed by pofh, and this function
        duplicates the same checks (and performs some additional ones).
        """

        # Primary intended users are Houston.
        # They are privileged, but not superusers.
        ac = self._get_account(accountname, idtype='name')
        if not self.ba.can_set_password(operator.get_entity_id(), ac):
            raise PermissionDenied("Access denied")
        return check_password_issues(ac)
