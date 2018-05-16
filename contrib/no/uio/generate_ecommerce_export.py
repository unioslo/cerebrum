#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2007 University of Oslo, Norway
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
This file is part of the Cerebrum framework. It produces a set of text
files used to provision IP Basware, UiOs e-commerce application.
The standard format of all the files is:

 <value>;<value>;...<value>

Following files are produced:

 YYYYMMDD-User.cvs:
  - information about the users of e-commerce application

 YYYYMMDD-Org.cvs:
  - information about UiOs organizational structure

 YYYYMMDD-Roles.cvs:
  - information about affiliations

 YYYYMMDD-Adr.cvs:
  - information about addresses of organizational units at UiO

 YYYYMMDD-AdrPart.cvs:
  - information about actual address parts (street address etc)

"""

from __future__ import unicode_literals


import sys
import getopt
import io

from six import text_type

from mx import DateTime
import cerebrum_path

from Cerebrum.Utils import Factory
from Cerebrum.utils.context import entity
from Cerebrum import Errors
from Cerebrum.QuarantineHandler import QuarantineHandler

del cerebrum_path

outencoding = 'ISO-8859-1'

ordered_people_keys = ['use_uid', 'use_home_oun_id', 'use_supervisor_uid',
                       'use_name', 'use_domain', 'use_full_name',
                       'use_email_address', 'use_language_code',
                       'use_approval_limit', 'use_approve_own',
                       'use_send_email', 'use_move_to_substitute',
                       'use_substitute_uid', 'use_substitute_start_date',
                       'use_substitute_end_date', 'use_client_type',
                       'use_inherit_delivery_address', 'use_delivery_add_id',
                       'use_change_delivery_addr', 'use_edit_delivery_addr',
                       'use_inherit_invoicing_address', 'use_invoicing_add_id',
                       'use_change_invoicing_addr',  'use_edit_invoicing_addr',
                       'use_inherit_cost_center', 'use_cce_id',
                       'use_change_cost_center', 'use_ugr_id', 'use_enabled',
                       'use_superadmin', 'use_personnel_number',
                       'use_view_abstract_suplier', 'use_plan_approval_limit',
                       'use_t1', 'use_t2']

ordered_org_keys = ['oun_id', 'oun_name', 'oun_parent_id', 'oun_type',
                    'oun_party_id', 'oun_default_delivery_party',
                    'oun_default_invoicing_party',
                    'oun_default_delivery_address',
                    'oun_default_invoice_address',
                    'oun_default_cost_center_id',
                    'oun_default_acc_currency', 'oun_acc_cur_rate',
                    'oun_acc_cur_rate_method']

ordered_role_keys = ['uro_user_uid', 'uro_id', 'uro_oun_id', 'uro_is_self']

ordered_addr_keys_1 = ['add_id_1', 'add_oun_id_1', 'add_title_1',
                       'add_is_invoicing_1', 'add_is_delivery_1']
ordered_addr_keys_2 = ['add_id_2', 'add_oun_id_2', 'add_title_2',
                       'add_is_invoicing_2', 'add_is_delivery_2']

ordered_addr_part_keys = ['apa_add_id', 'apa_id', 'apa_type', 'apa_text']

default_org_data = {'oun_id': '83',
                    'oun_name': 'Universitetet i Oslo',
                    'oun_parent_id': '',
                    'oun_type': '1',
                    'oun_party_id': '',
                    'oun_default_delivery_party': '',
                    'oun_default_invoicing_party': '83',
                    'oun_default_delivery_address': '',
                    'oun_default_invoice_address': '',
                    'oun_default_cost_center_id': '83',
                    'oun_default_acc_currency': 'NOK',
                    'oun_acc_cur_rate': '1',
                    'oun_acc_cur_rate_method': '0',
                    'add_id_1': '831',
                    'add_oun_id_1': '83',
                    'add_title_1': '83 (Toppnivå-post)',
                    'add_is_invoicing_1': '0',
                    'add_is_delivery_1': '1',
                    'add_id_2': '832',
                    'add_oun_id_2': '83',
                    'add_title_2': '83 (Toppnivå-besøk)',
                    'add_is_invoicing_2': '0',
                    'add_is_delivery_2': '1'}


def generate_people_file(exported_orgs):
    file_name = person_file_name
    people_data = generate_people_info(exported_orgs)
    with io.open(file_name, 'w', encoding=outencoding) as people_file, \
            io.open(role_file_name, 'w', encoding=outencoding) as role_file:
        free_vals = ';' * 37
        for p in people_data.keys():
            people_line = ''
            for k in ordered_people_keys:
                people_line = people_line + '%s;' % people_data[p][k]
            people_file.write(people_line + free_vals + '\n')
            role_line = ''
            for r in ordered_role_keys:
                role_line = role_line + '%s;' % people_data[p][r]

            role_file.write(role_line + '\n')


def generate_people_info(exported_orgs):
    exported_employee_id = []
    employee_data = {}
    all_employee_ids = fetch_employee_data()
    quarantined_accounts = QuarantineHandler.get_locked_entities(
        db,
        entity_types=const.entity_account,
        entity_ids=[x['person_id'] for x in all_employee_ids])
    for p in all_employee_ids:
        if not p['person_id'] in exported_employee_id:
            exported_employee_id.append(p['person_id'])
        else:
            continue
        person.clear()
        person.find(p['person_id'])
        with entity.ou.find(p['ou_id']) as ou:
            use_home_oun_id = text_type(ou)
            if ou.entity_id not in exported_orgs:
                logger.warn("Person %s connected to non-exported org. unit %s,"
                            " skipping", person.entity_id, use_home_oun_id)
                # if a person is connected to a non-exported org unit,
                # do not export
            continue
        primary_account_id = person.get_primary_account()
        if not primary_account_id:
            continue
        account.clear()
        try:
            account.find(primary_account_id)
        except Errors.NotFoundError:
            logger.warn("Skipping %s, no valid account found", p['person_id'])
            continue
        no_sap_nr = person.get_external_id(
            source_system=const.system_sap,
            id_type=const.externalid_sap_ansattnr)[0]['external_id']
        try:
            email_address = account.get_primary_mailaddress()
        except Errors.NotFoundError:
            logger.info("No primary e-mail address found for %s, sending ''",
                        account.account_name)
            email_address = ''
        quarantined = 0 if primary_account_id in quarantined_accounts else 1
        person_name_full = person.get_name(const.system_cached,
                                           const.name_full)
        phones = person.get_contact_info(source=const.system_sap,
                                         type=const.contact_phone)
        if not phones:
            use_t1 = ''
        else:
            use_t1 = phones[0]['contact_value']
        fax = person.get_contact_info(source=const.system_sap,
                                      type=const.contact_fax)
        if not fax:
            use_t2 = ''
        else:
            use_t2 = fax[0]['contact_value']
        employee_data[p['person_id']] = {'use_uid': no_sap_nr,
                                         'use_home_oun_id': use_home_oun_id,
                                         'use_supervisor_uid': '',
                                         'use_name': account.account_name,
                                         'use_domain': '',
                                         'use_full_name': person_name_full,
                                         'use_email_address': email_address,
                                         'use_language_code': 'NO',
                                         'use_approval_limit': '',
                                         'use_approve_own': '',
                                         'use_send_email': '1',
                                         'use_move_to_substitute': '',
                                         'use_substitute_uid': '',
                                         'use_substitute_start_date': '',
                                         'use_substitute_end_date': '',
                                         'use_client_type': '2',
                                         'use_inherit_delivery_address': '1',
                                         'use_delivery_add_id': '',
                                         # setting this value to none allows
                                         # inheritance of delivery address
                                         # in stead of use_home_oun_id,
                                         'use_change_delivery_addr': '1',
                                         'use_edit_delivery_addr': '1',
                                         'use_inherit_invoicing_address': '1',
                                         'use_invoicing_add_id': '',
                                         'use_change_invoicing_addr': '0',
                                         'use_edit_invoicing_addr': '',
                                         'use_inherit_cost_center': '0',
                                         'use_cce_id': '',
                                         'use_change_cost_center': '1',
                                         'use_ugr_id': '',
                                         'use_enabled': quarantined,
                                         'use_superadmin': '',
                                         'use_personnel_number': '',
                                         'use_view_abstract_suplier': '0',
                                         'use_plan_approval_limit': '',
                                         'use_t1': use_t1,
                                         'use_t2': use_t2,
                                         'uro_user_uid': no_sap_nr,
                                         'uro_id': 'DUMMY1',
                                         'uro_oun_id': use_home_oun_id,
                                         'uro_is_self': ''}
    logger.debug("Fetched all relevant employee data.")
    return employee_data


def fetch_employee_data():
    all_employee_ids = person.list_affiliations(
        source_system=const.system_sap,
        affiliation=const.affiliation_ansatt,
        status=const.affiliation_status_ansatt_tekadm)
    all_vit_ids = person.list_affiliations(
        source_system=const.system_sap,
        affiliation=const.affiliation_ansatt,
        status=const.affiliation_status_ansatt_vit)
    all_guest_ids = person.list_affiliations(
        source_system=const.system_sap,
        affiliation=const.affiliation_tilknyttet,
        status=const.affiliation_tilknyttet_innkjoper)
    for v in all_vit_ids:
        all_employee_ids.append(v)

    for i in all_guest_ids:
        all_employee_ids.append(i)
    return all_employee_ids


def generate_organization_file(org_units, exported_orgs):
    org_structure = get_org_unit_data(org_units, exported_orgs)
    with io.open(org_file_name, 'w', encoding=outencoding) as org_file, \
            io.open(address_file_name, 'w',
                    encoding=outencoding) as address_file, \
            io.open(address_part_file_name, 'w',
                    encoding=outencoding) as addr_part_file:
        org_structure['999999'] = default_org_data
        addr_part_file_data = generate_address_parts_file(org_structure)
        for apfd in addr_part_file_data:
            addr_part_file.write(apfd + '\n')
        for o in org_structure.keys():
            org_line = ''
            for k in ordered_org_keys:
                org_line = org_line + '%s;' % org_structure[o][k]
            org_file.write(org_line + '\n')
            addr_line_1 = ''
            addr_line_2 = ''
            for a in ordered_addr_keys_1:
                addr_line_1 = addr_line_1 + '%s;' % org_structure[o][a]
            for a in ordered_addr_keys_2:
                addr_line_2 = addr_line_2 + '%s;' % org_structure[o][a]
            address_file.write(addr_line_1 + '\n')
            address_file.write(addr_line_2 + '\n')


def get_org_unit_data(org_units, exported_orgs):
    org_structure = {}
    for o in org_units:
        oun_parent_id = None
        oun_type = None
        count_level = 1
        try:
            with entity.ou.find(o[0]) as ou:
                oun_id = text_type(ou)
                tmp = ou.search_name_with_language(
                    entity_id=ou.entity_id,
                    name_language=const.language_nb,
                    name_variant=const.ou_name_display)
                oun_name = tmp[0]["name"]
                parent_id = ou.get_parent(const.perspective_sap)
                # No direct parent is registered for ou
                if not parent_id or parent_id not in exported_orgs:
                    logger.info("No parent for ou %s, exporting default values"
                                " for oun_type and oun_parent_id", oun_id)
                    oun_parent_id = '999999'
                else:
                    oun_parent_id = get_parent_id(int(parent_id),
                                                  exported_orgs)
                    count_level = get_org_level(int(parent_id), count_level)
                if count_level < 3:
                    oun_type = '2'
                else:
                    oun_type = '0'
                if oun_type == '2':
                    oun_parent_id = '83'
                org_structure[ou.entity_id] = {
                    'oun_id': oun_id,
                    'oun_name': oun_id + ' - ' + oun_name,
                    'oun_parent_id': oun_parent_id,
                    'oun_type': oun_type,
                    'oun_party_id': '',
                    'oun_default_delivery_party': '',
                    'oun_default_invoicing_party': '83',
                    'oun_default_delivery_address': oun_id + '1',
                    # default delivery address er besøksadresse
                    'oun_default_invoice_address': '',
                    'oun_default_cost_center_id': '83',
                    'oun_default_acc_currency': 'NOK',
                    'oun_acc_cur_rate': '1',
                    'oun_acc_cur_rate_method': '0',
                    'add_id_1': oun_id + '1',
                    'add_oun_id_1': oun_id,
                    'add_title_1': oun_id + '-Besøk',
                    'add_is_invoicing_1': '0',
                    'add_is_delivery_1': '1',
                    'add_id_2': oun_id + '2',
                    'add_oun_id_2': oun_id,
                    'add_title_2': oun_id + '-Post',
                    'add_is_invoicing_2': '0',
                    'add_is_delivery_2': '1'}
        except Errors.NotFoundError:
            logger.warn("Could not find OU with id: %s "
                        "(this should never happen!).",
                        o[0])
    return org_structure


def get_parent_id(parent_id, exported_orgs):
    try:
        with entity.ou.find(parent_id) as parent_ou:
            if parent_id and parent_id in exported_orgs:
                return text_type(parent_ou)
            else:
                return get_parent_id(parent_ou.get_parent(
                    const.perspective_sap),
                    exported_orgs)
    except Errors.NotFoundError:
        return None


def generate_address_parts_file(orgs):
    addr_parts = []
    for o in orgs.keys():
        try:
            with entity.ou.find(o) as ou:
                sko = text_type(ou)
                logger.debug("SKO: %s", sko)
                addrs_1 = ou.get_entity_address(source=const.system_sap,
                                                type=const.address_post)
                apa_add_id = sko + '2'
                pobox = []

                ou_name = ou.get_name_with_language(
                    name_variant=const.ou_name,
                    name_language=const.language_nb,
                    default="")
                if len(addrs_1) == 0:
                    # This will happen when the OU has no valid postal address
                    # Use bogus/empty address to enable further processing
                    logger.warning("OU '%s' (SKO: '%s', ENT-ID: '%s') is "
                                   "registered without a post address",
                                   ou_name, sko, o)
                    addrs_1.append((0, 0, 0, '', None, '', None, ''))

                for k in addrs_1[0][3].split('\n'):
                    pobox.append(k)

                for e in ['Name1:0', 'Name2:1', 'POBox:3', 'Street1:4',
                          'Department:12', 'Postalcode:13', 'City:14']:
                    apa_id, apa_type = e.split(':')
                    if apa_id == 'Name1':
                        apa_text = 'Universitetet i Oslo'
                    elif apa_id == 'Name2':
                        apa_text = ou_name
                    elif apa_id == 'POBox':
                        apa_text = pobox[0]
                    elif apa_id == 'Street1':
                        if len(pobox) == 2:
                            apa_text = pobox[1]
                        else:
                            apa_text = ''
                    elif apa_id == 'Department':
                        apa_text = apa_add_id
                    elif apa_id == 'Postalcode':
                        apa_text = 'NO-' + addrs_1[0][7]
                    elif apa_id == 'City':
                        apa_text = addrs_1[0][5]
                    line1 = ';'.join((apa_add_id, apa_id, apa_type, apa_text))
                    addr_parts.append(line1)
                apa_add_id = ""

                addrs_2 = ou.get_entity_address(source=const.system_sap,
                                                type=const.address_street)
                apa_add_id = sko + '1'
                street = []

                if len(addrs_2) == 0:
                    # This will happen when the OU has no valid street address
                    # Use bogus/empty address to enable further processing
                    logger.warning("OU '%s' (SKO: '%s', ENT-ID: '%s') is "
                                   "registered without a street address",
                                   ou_name, sko, o)
                    addrs_2.append((0, 0, 0, '', None, '', None, ''))

                for k in addrs_2[0][3].split('\n'):
                    street.append(k)
                for e in ['Name1:0', 'Name2:1', 'Street1:4', 'Street2:6',
                          'Department:12', 'Postalcode:13', 'City:14']:
                    apa_id, apa_type = e.split(':')
                    if apa_id == 'Name1':
                        apa_text = 'Universitetet i Oslo'
                    elif apa_id == 'Name2':
                        apa_text = ou_name
                    elif apa_id == 'Street1':
                        apa_text = street[0]
                    elif apa_id == 'Street2':
                        if len(street) == 2:
                            apa_text = street[1]
                        else:
                            apa_text = ''
                    elif apa_id == 'Department':
                        apa_text = apa_add_id
                    elif apa_id == 'Postalcode':
                        apa_text = 'NO-' + addrs_2[0][7]
                    elif apa_id == 'City':
                        apa_text = addrs_2[0][5]
                    line2 = ';'.join((apa_add_id, apa_id, apa_type, apa_text))
                    addr_parts.append(line2)
            return addr_parts
        except Errors.NotFoundError:
            logger.warn("could not find OU %s", o)


def get_org_level(parent_ou_id, level):
    with entity.ou.find(parent_ou_id) as parent_ou:
        po = parent_ou.get_parent(const.perspective_sap)
        return level if po is None else get_org_level(int(po), level + 1)


def generate_address_file():
    print("not yet implemented")


def usage():
    print("""Usage: generate_ehandel_export.py [options]
             Options:
               --gen-organization-files, -o: generate organization file
               --org-file-name: override name of the organization file
               --gen-person-files, -p: generate person file
               --person-file-name: override name of the person file
               --help, -h: print this text
          """)


def main():
    global db, person, account, const
    global person_file_name, logger, role_file_name
    global org_file_name, address_file_name, address_part_file_name

    logger = Factory.get_logger("cronjob")
    db = Factory.get("Database")()
    person = Factory.get("Person")(db)  # TODO entity.person
    account = Factory.get("Account")(db)  # TODO: entity.account
    const = Factory.get("Constants")(db)
    ou = Factory.get("OU")(db)

    dump_directory = '/cerebrum/var/cache/BASWAREPM/'

    now = DateTime.now()
    datetime = now.Format("%Y%m%d")
    person_file_name = dump_directory + datetime + '-' + 'User.csv'
    role_file_name = dump_directory + datetime + '-' + 'Roles.csv'
    org_file_name = dump_directory + datetime + '-' + 'Org.csv'
    address_file_name = dump_directory + datetime + '-' + 'Adr.csv'
    address_part_file_name = dump_directory + datetime + '-' + 'AdrPart.csv'

    org_units = ou.search(spread=const.spread_uio_org_ou,
                          filter_quarantined=True)
    exported_orgs = []

    for e in org_units:
        exported_orgs.append(int(e[0]))
    exported_orgs.append(999999)

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'proash',
                                   ['help',
                                    'gen-person-file',
                                    'person-file-name=',
                                    'gen-role-file',
                                    'role-file-name=',
                                    'gen-organization-file',
                                    'org-file-name=',
                                    # 'gen-address-file',
                                    'address-file-name=',
                                    # 'gen-address-part-file',
                                    'address-part-file-name='])
    except getopt.GetoptError:
        usage()

    for opt, val in opts:
        if opt in ('--help', '-h'):
            usage()
        elif opt in ('--person-file-name', ):
            person_file_name = val
        elif opt in ('--role-file-name', ):
            role_file_name = val
        elif opt in ('--org-file-name', ):
            org_file_name = val
        elif opt in ('--address-file-name', ):
            address_file_name = val
        elif opt in ('--address-part-file-name', ):
            address_part_file_name = val

    for opt, val in opts:
        if opt in ('--gen-person-file', '-p'):
            generate_people_file(exported_orgs)
        elif opt in ('--gen-organization-file', '-o'):
            generate_organization_file(org_units, exported_orgs)
#        elif opt in ('--gen-address-file', '-a'):
#            # Implied by -o
#            generate_address_file()
#        elif opt in ('--gen-address-parts-file', '-s'):
#            # Implied by -o
#            generate_address_parts_file()

    if not opts:
        usage()


if __name__ == "__main__":
    main()
