#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2018 University of Oslo, Norway
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
from __future__ import unicode_literals
from Cerebrum.Errors import NotFoundError

import six


def get_person_address(person, address_lookups):
    for source, kind in address_lookups:
        address = person.get_entity_address(source=source, type=kind)
        if address:
            return address[0]
    return None


def get_address_mappings(address, co):
    mappings = dict()
    if address['address_text']:
        alines = address['address_text'].split("\n") + [""]
        mappings['address_line2'] = alines[0]
        mappings['address_line3'] = alines[1]
    else:
        mappings['address_line2'] = ''
        mappings['address_line3'] = ''
    mappings['zip'] = address['postal_number']
    mappings['city'] = address['city']
    country = address['country']
    try:
        if not isinstance(country, int):
            mappings['country'] = ''
        else:
            mappings['country'] = six.text_type(co.Country(country).country)
    except NotFoundError:
        mappings['country'] = ''
    return mappings


def get_person_info(person, co):
    person_info = dict()
    person_info['fullname'] = person.get_name(co.system_cached,
                                              co.name_full)
    person_info['birthdate'] = person.birth_date.strftime('%Y-%m-%d')
    return person_info


def get_account_primary_email(account):
    mappings = {}
    try:
        mappings['email_adr'] = account.get_primary_mailaddress()
    except NotFoundError:
        mappings['email_adr'] = ''
    return mappings


def get_account_mappings(account, password):
    u""" Get mappings for a given template.

    :param Cerebrum.Account account: The account to generate mappings for
    :param str password: The account's password

    :return dict: A dictionary of mappings to use in a template.

    """
    return {
        'username': account.account_name,
        'password': password,
        'account_id': account.entity_id,
        'serial_no': '',
        'barcode_file': 'barcode_{}.png'.format(account.entity_id)
    }


def get_group_mappings(group):
    return {
        'group': group.group_name,
        'fullname': group.group_name
    }
