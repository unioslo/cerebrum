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


class PassWordIssues(object):
    def __init__(self, co, ac, pe, gr):
        self.co = co
        self.ac = ac
        self.pe = pe
        self.gr = gr
        self.data = []
        self.info = []
        self.issues = []
        self.phones = []
        self.all_traits = []
        self.info_traits = []
        self.affiliations = []
        self.trouble_traits = []
        self.illegal_groups = {'superusers', 'admin'}  # from example.pofh.cfg

    def get_relevant_traits(self):
        """checks account properties for misc_password_issues"""
        self.all_traits = self.ac.get_traits()
        traits = set(self.all_traits.keys())
        # Problematic traits:
        # Pofh checks traits twice: 'sysadm_account' and 'important_acc'
        # in one test, 'reserve_passw' in another. These traits are hard
        # coded into cerebrum_api_v1.py.
        self.trouble_traits = traits & {self.co.trait_sysadm_account,
                                        self.co.trait_reservation_sms_password,
                                        self.co.trait_important_account}
        # Informative traits:
        # These traits are not problematic in and of themselves, and are
        # not checked by pofh, but might still offer relevant information.
        # Primary affiliation requires special attention due to value.
        self.info_traits = traits & {self.co.trait_sms_welcome,
                                     self.co.trait_student_new,
                                     self.co.trait_account_new,
                                     self.co.trait_primary_aff}

    def format_traits(self):
        if self.co.trait_primary_aff in self.info_traits:
            primary_aff = self.all_traits[self.co.trait_primary_aff]['strval']
            self.info.append('Primary affiliation is {}'.format(primary_aff))
            self.info_traits.remove(self.co.trait_primary_aff)
        if self.info_traits:
            in_str = 'Other informative traits:' + ' {}'*len(self.info_traits)
            self.info.append(in_str.format(*self.info_traits))
        if self.trouble_traits:
            tr_str = 'Illegal traits:' + ' {}'*len(self.trouble_traits)
            self.issues.append(tr_str.format(*self.trouble_traits))

    def check_groups(self):
        gr = {r['name'] for r in self.gr.search(member_id=self.ac.entity_id)}
        if not gr:
            self.issues.append('No groups')
        else:
            # Todo: replace with a proper list?
            gr &= self.illegal_groups
            if gr:
                gr_str = text_type('Illegal groups:' + ' {}'*len(gr))
                self.issues.append(gr_str.format(*gr))

    def check_quarantines(self):
        qr = self.ac.get_entity_quarantine(only_active=True)
        qr = {text_type(self.co.human2constant(
            q['quarantine_type'])) for q in qr}
        # Todo: replace with a proper list from... where?
        qr -= {'svakt_passord', 'autopassord'}  # from example.pofh.cfg
        if qr:
            qr_str = text_type('Illegal quarantines:' + ' {}'*len(qr))
            self.issues.append(qr_str.format(*qr))

    def get_valid_affiliations(self):
        now = DateTime.now()
        affs = self.pe.get_affiliations()
        if not affs:
            self.issues.append('Person has no affiliations')
        for aff in affs:
            del_date = aff['deleted_date']
            if not del_date or del_date > now:
                self.affiliations.append({'ssys': aff['source_system'],
                                          'status': aff['status']})
        if affs and not self.affiliations:
            self.issues.append('Person has no valid affiliations')

    def get_phones(self):
        # The different mobile phone types may be hard coded here.
        phone_types = {int(self.co.contact_mobile_phone),
                       int(self.co.contact_private_mobile),
                       int(self.co.contact_private_mobile_visible)}
        contact_rows = self.pe.get_contact_info()
        if not contact_rows:
            self.issues.append('no_contact_info')
        for row in contact_rows:
            if (row['contact_type'] in phone_types):
                self.phones.append({'ssys': row['source_system'],
                                    'number': row['contact_value'],
                                    'date': row['last_modified']})
        if not self.phones and 'no_contact_info' not in self.issues:
            self.issues.append('No mobile phone numbers')

    def check_phones(self):
        validity_issues = True
        # Maybe add feature: Check validity and integrity of phone number?
        for phone in self.phones:
            number, date = phone['number'], phone['date']
            found = False
            for aff in self.affiliations:
                if phone['ssys'] == aff['ssys']:
                    validity_issues = False
                    found = True
                    aff['number'] = number
                    aff['date'] = date
            if not found:
                aff = {}
                aff['number'] = number
                aff['date'] = date
                aff['ssys'] = phone['ssys']
                aff['status'] = 'invalid affiliation'
                self.affiliations.append(aff)
        if self.phones and validity_issues:
            self.issues.append('No mobile number from a valid affiliation')

    def format_affiliations(self):
        now = DateTime.now()
        lastweek = now - DateTime.TimeDelta(24*7)
        date_issues = False
        for aff in self.affiliations:
            aff['ssys'] = '{0: <8}'.format(
                text_type(self.co.AuthoritativeSystem(aff['ssys'])))
            status = aff['status']
            if status == 'invalid affiliation':
                aff['status'] = '{0: <24}'.format(text_type(aff['status']))
            else:
                aff['status'] = '{0: <24}'.format(
                    text_type(self.co.human2constant(aff['status'])))
            if 'number' not in aff:
                aff['number'] = '{0: >18}'.format(None)
                aff['date'] = '   None'
            else:
                aff['number'] = '{0: >18}'.format(text_type(aff['number']))
                mod_date = aff['date']
                if mod_date and mod_date > lastweek:
                    date = '  (changed {} days ago)'.format(int(
                        (now - mod_date).days))
                    date_issues = True
                else:
                    date = '   date is OK'
                aff['date'] = date
        if date_issues:
            self.issues.append('Mobile numbers changed less than a week ago')
        for i, entry in enumerate(sorted(self.affiliations)):
            if i == 0:
                k0, k1, k2, k3 = 'ssys0', 'status0', 'number0', 'date_str0'
            else:
                k0, k1, k2, k3 = 'ssysn', 'statusn', 'numbern', 'date_strn'
            self.data.append({k0: entry['ssys'], k1: entry['status'],
                              k2: entry['number'], k3: entry['date']})

    def format_issues(self):
        if not self.issues:
            self.data.append({'sms_work_p': 'available',
                              'accountname': self.ac.account_name})
        else:
            self.data.append({'sms_work_p': 'UNAVAILABLE',
                              'accountname': self.ac.account_name})
            for i, ie in enumerate(self.issues):
                self.data.append({'issue0': ie} if i == 0 else {'issuen': ie})

    def format_info(self):
        for i, io in enumerate(self.info):
            self.data.append({'info0': io} if i == 0 else {'infon': io})

    def run_check(self):
        self.get_relevant_traits()
        self.check_groups()
        self.check_quarantines()
        self.get_valid_affiliations()
        self.get_phones()
        self.check_phones()

    def format_data(self):
        self.format_traits()
        self.format_affiliations()
        self.format_issues()
        self.format_info()
