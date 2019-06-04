#!/usr/bin/env python
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
This script creates an xml file that the UiT portal reads.

kbj005 2015.02.12: Copied from Leetah.
"""
from __future__ import unicode_literals

import argparse
import csv
import datetime
import io
import logging
import os
import sys
from collections import OrderedDict

import six

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Constants import _CerebrumCode
from Cerebrum.Utils import Factory
from Cerebrum.extlib.xmlprinter import xmlprinter
from Cerebrum.modules.no.stillingskoder import Stillingskoder
from Cerebrum.modules.no.uit.PagaDataParser import PagaDataParserClass
from Cerebrum.utils import csvutils
from Cerebrum.utils.argutils import ParserContext

logger = logging.getLogger(__name__)


def parse_date(date_str):
    """
    Parse a date on the strfdate format "%Y-%m-%d".
    """
    if not date_str:
        return None
    args = (int(date_str[0:4]),
            int(date_str[5:7]),
            int(date_str[8:10]))
    return datetime.date(*args)


class AffCache(object):
    """
    Affiliation cache.

    Filter and map employments from a paga xml employee file.
    """

    def __init__(self, db, employee_file):
        self._db = db
        self._co = Factory.get('Constants')(db)
        self._skode = Stillingskoder(db)
        logger.info("Loading employee data from %r", employee_file)
        self._aff_to_stilling_map = {}
        PagaDataParserClass(employee_file, self._parse_person_affs)

    def __getitem__(self, key):
        return self._aff_to_stilling_map[key]

    def _parse_person_affs(self, person):
        today = datetime.date.today()
        co = self._co

        fnr = person['fnr']

        for t in person.get('tils', ()):
            # TODO: the 'today' default value is leftover logic from
            # mx.DateTime.DateFrom()
            dato_fra = parse_date(t.get("dato_fra")) or today
            earliest = (dato_fra -
                        datetime.timedelta(days=cereconf.PAGA_EARLYDAYS))
            dato_til = parse_date(t.get("dato_til")) or today

            if today < earliest or today > dato_til:
                logger.debug(
                    "Inactive role, earliest=%s, dato_fra=%s, dato_til=%s",
                    earliest, dato_fra, dato_til)
                continue

            stedkode = "%s%s%s" % (t['fakultetnr_utgift'].zfill(2),
                                   t['instituttnr_utgift'].zfill(2),
                                   t['gruppenr_utgift'].zfill(2))

            if t['hovedkategori'] == 'TEKN':
                tilknytning = co.affiliation_status_ansatt_tekadm
            elif t['hovedkategori'] == 'ADM':
                tilknytning = co.affiliation_status_ansatt_tekadm
            elif t['hovedkategori'] == 'VIT':
                tilknytning = co.affiliation_status_ansatt_vitenskapelig
            else:
                logger.warning("Unknown hovedkategori=%r, skipping",
                               t['hovedkategori'])
                continue

            pros = "%2.2f" % float(t['stillingsandel'])

            # Looking up stillingstittel and dbh_kat from DB
            stillingskode = t['stillingskode']

            try:
                skode = self._skode.get(stillingskode)
                stillingstittel = skode['title']
                dbh_kat = skode['category']
            except Errors.TooManyRowsError:
                logger.error('Multiple results for stillingskode=%r',
                             stillingskode)
                # TODO: No stillingstittel, dbh_kat - will fail
            except Errors.NotFoundError:
                # Default to file info
                stillingstittel = t['tittel']
                dbh_kat = t['dbh_kat']
                logger.error('No results for stillingskode=%r, using %r/%r',
                             stillingskode, stillingstittel, dbh_kat)

            hovedarbeidsforhold = ''
            if 'hovedarbeidsforhold' in t:
                hovedarbeidsforhold = t['hovedarbeidsforhold']
            aux_key = (fnr, stedkode, six.text_type(tilknytning))
            aux_val = {
                'stillingskode': stillingskode,
                'stillingstittel_paga': t['tittel'],
                'stillingstittel': stillingstittel,
                'prosent': pros,
                'dbh_kat': dbh_kat,
                'hovedarbeidsforhold': hovedarbeidsforhold,
            }

            self._aff_to_stilling_map[aux_key] = aux_val


class OuCache(object):
    """A cache of relevant ou data"""
    def __init__(self, db):
        ou = Factory.get('OU')(db)
        co = Factory.get('Constants')(db)

        logger.info("Caching OUs")
        self._id_to_sko = {}
        self._sko_to_id = {}
        for row in ou.get_stedkoder():
            sko = '{:02d}{:02d}{:02d}'.format(row['fakultet'],
                                              row['institutt'],
                                              row['avdeling'])
            self._id_to_sko[int(row['ou_id'])] = sko
            self._sko_to_id[sko] = int(row['ou_id'])

        logger.info("Caching OU names")
        self._id_to_name = {}
        for row in ou.search_name_with_language(
                entity_type=co.entity_ou,
                name_variant=co.ou_name,
                name_language=co.language_nb):
            self._id_to_name[int(row['entity_id'])] = row['name']

    def get_ou_sko(self, ou_id):
        return self._id_to_sko[ou_id]

    def get_ou_name(self, ou_id):
        return self._id_to_name.get(ou_id) or ''

    def get_sko_id(self, sko):
        return self._sko_to_id[sko]

    def get_sko_name(self, sko):
        return self._id_to_name.get(self._sko_to_id.get(sko)) or ''


FIELD_STEDKODE_FROM = 0
FIELD_STEDKODE_TO = 1


def read_ou_mappings(filename):
    """Read CSV file with SKO mappings."""
    logger.info("Reading OU mappings from %r", filename)
    with open(filename, 'r') as f:
        for row in csv.reader(f, delimiter=b';'):
            yield (
                six.text_type(row[FIELD_STEDKODE_FROM]).strip(),
                six.text_type(row[FIELD_STEDKODE_TO]).strip(),
            )


def build_ou_mappings(ou_cache, csv_data):
    """Build a dict of ou mappings from csv."""
    mapping = {}
    for from_sko, to_sko in csv_data:
        try:
            from_id = ou_cache.get_sko_id(from_sko)
        except KeyError:
            logger.error("Invalid sko mapping from %r (to %r)",
                         from_sko, to_sko)
            continue
        if from_id in mapping:
            logger.warning("Duplicate mappings from %r", from_sko)
        try:
            ou_cache.get_sko_id(to_sko)
        except KeyError:
            logger.warning("Mapping to invalid sko %r (from %r)",
                           to_sko, from_sko)
        mapping[from_id] = to_sko
    logger.info("Built OU mappings from %d OUs", len(mapping))
    return mapping


def load_cache(db):
    # TODO: Get rid of global caches too
    global account2name
    global owner2account
    global persons
    global uname2mail
    global num2const
    global name_cache_cached
    global auth_list
    global person2contact
    global person2campus
    global person2home_address
    global person2employeeNumber
    global bas_portal_mapping
    global ou_stedkode_mapping
    global pid_fnr_dict

    p = Factory.get('Person')(db)
    ac = Factory.get('Account')(db)
    co = Factory.get('Constants')(db)

    # Creating ou map
    logger.info('Getting pid -> fnr dict')
    pid_fnr_dict = p.getdict_fodselsnr()

    logger.info("Retrieving persons and their birth_dates")
    persons = {}
    for pers in p.list_persons():
        persons[pers['person_id']] = pers['birth_date']

    logger.info("Retrieving person names")
    # name_cache_cached = p.getdict_persons_names(
    #     source_system=co.system_cached,
    #     name_types=(co.name_first, co.name_last))
    name_cache_cached = {}
    for row in p.search_person_names(
            source_system=co.system_cached,
            name_variant=(co.name_first, co.name_last)):
        pn = name_cache_cached.setdefault(int(row['person_id']), {})
        if row['name_variant'] == co.name_first:
            pn['first_name'] = row['name']
        else:
            pn['last_name'] = row['name']

    logger.info("Retrieving account names")
    account2name = {}
    for a in ac.list_names(co.account_namespace):
        account2name[a['entity_id']] = a['entity_name']

    logger.info("Retrieving account emailaddrs")
    uname2mail = ac.getdict_uname2mailaddr()

    logger.info("Retrieving account owners")
    owner2account = {}
    # filter out unwanted affiliations
    # (only list those we want to export to oid)
    valid_affs = (co.affiliation_manuell,
                  co.affiliation_ansatt,
                  co.affiliation_tilknyttet,
                  co.affiliation_student)
    for a in ac.list_accounts_by_type(affiliation=valid_affs,
                                      filter_expired=False,
                                      primary_only=True):
        owner2account[a['person_id']] = a['account_id']
    logger.info("Retrieving auth strings")
    auth_list = {}
    auth_type = co.auth_type_md5_b64
    for auth in ac.list_account_authentication(auth_type=auth_type):
        auth_list[auth['account_id']] = auth['auth_data']

    logger.info("Retrieving contact info (phonenrs and such)")
    person2contact = {}
    for row in p.list_contact_info(entity_type=co.entity_person,
                                   source_system=(co.system_tlf,
                                                  co.system_fs)):
        person2contact.setdefault(row['entity_id'], list()).append({
            'source': six.text_type(co.AuthoritativeSystem(
                row['source_system'])),
            'type': six.text_type(co.ContactInfo(row['contact_type'])),
            'pref': row['contact_pref'],
            'value': row['contact_value'],
        })

    # get person campus location
    logger.info("Retreiving person campus location")
    person2campus = {}

    for c in p.list_entity_addresses(entity_type=co.entity_person,
                                     source_system=co.system_paga,
                                     address_type=co.address_location):
        person2campus.setdefault(c['entity_id'], list()).append(c)

    # get person home address
    person2home_address = dict()
    for c in p.list_entity_addresses(entity_type=co.entity_person,
                                     source_system=co.system_paga,
                                     address_type=co.address_post_private):
        person2home_address.setdefault(c['entity_id'], list()).append(c)

    # get person employee number
    person2employeeNumber = dict()
    for c in p.search_external_ids(source_system=co.system_paga,
                                   id_type=co.externalid_paga_ansattnr,
                                   entity_type=co.entity_person):
        if not c['external_id']:
            continue
        person2employeeNumber.setdefault(c['entity_id'],
                                         set()).add(c['external_id'])

    logger.info("Start get constants")
    num2const = {}
    for c in dir(co):
        tmp = getattr(co, c)
        if isinstance(tmp, _CerebrumCode):
            num2const[int(tmp)] = tmp
    logger.info("Cache finished")


def get_affiliations(db, ou_cache, ou_mapping, aff_cache):
    logger.info("Listing affiliations")
    pe = Factory.get('Person')(db)
    co = Factory.get('Constants')(db)

    # export_attrs = {}
    person_affs = {}

    skip_source = (
        co.system_lt,
        co.system_flyt,
        # co.system_hitos,
    )

    for aff in pe.list_affiliations():
        # simple filtering
        aff_status_filter = (co.affiliation_status_student_tilbud,
                             co.affiliation_manuell_gjest,
                             co.affiliation_manuell_gjest_u_konto,
                             co.affiliation_status_ansatt_sito)
        if aff['status'] in aff_status_filter:
            continue

        if aff['source_system'] in skip_source:
            logger.warn('Skipped affiliation because it originated from '
                        'unwanted source system {}'.format(aff))
            continue

        # Needs to keep original ou id in order to be able to look up persons
        # BAS specific affiliation/stillingskode
        # original_ou_id = ou_id = aff['ou_id']
        #
        # Do mapping to "PORTAL specific" ou
        # try:
        #     ou_id_ = bas_portal_mapping[ou_id]
        #
        #     if ou_id_ == 'SKIP':
        #         logger.info('Skipped affiliation to ou=%s due to bas to '
        #                     'portal mapping rule saying to do so' % (ou_id))
        #         continue
        #
        #     logger.info('Mapped %s to %s' % (ou_id, ou_id_))
        #     ou_id = ou_id_
        # except KeyError:
        #     pass

        ou_id = aff['ou_id']

        last_date = aff['last_date'].strftime("%Y-%m-%d")

        try:
            ou_sko = ou_cache.get_ou_sko(ou_id)
            ou_name = ou_cache.get_sko_name(ou_sko)
        except KeyError as e:
            logger.warning("No stedkode for aff with ou_id=%r, skipping (%s)",
                           ou_id, e)
            continue

        if ou_mapping.get(ou_id) == 'SKIP':
            logger.info('No mapping (SKIP) for aff with ou_id=%r, sko=%r, '
                        'skipping', ou_id, ou_sko)
            continue
        elif ou_id in ou_mapping:
            logger.info('Mapping ou_id=%r (%r to %r)',
                        ou_id, ou_sko, ou_mapping[ou_id])
            ou_sko = ou_mapping[ou_id]
            ou_name = '%s - MAPPED' % (ou_name, )

        p_id = aff['person_id']
        aff_stat = num2const[aff['status']]
        # account
        acc_id = owner2account.get(p_id, None)
        if acc_id not in account2name:
            logger.warning("No account for person_id=%r, skipping", p_id)
            continue

        aff = {
            'affiliation': six.text_type(aff_stat.affiliation),
            'status': six.text_type(aff_stat.status_str),
            'stedkode': ou_sko,
            'stednavn': ou_name,
            'last_date': last_date,
        }

        try:
            aux_key = (pid_fnr_dict[p_id],
                       ou_cache.get_ou_sko(ou_id),
                       six.text_type(aff_stat))
            tils_info = aff_cache[aux_key]
        except KeyError:
            pass
        else:
            aff.update({
                'stillingskode': tils_info['stillingskode'],
                'stillingstittel': tils_info['stillingstittel_paga'],
                'prosent': tils_info['prosent'],
                'dbh_kategori': tils_info['dbh_kat'],
                'hovedarbeidsforhold': tils_info['hovedarbeidsforhold'],
            })
        person_affs.setdefault(p_id, list()).append(aff)
    return person_affs


def generate_export_data(affiliation_map):
    export_objects = {}

    for p_id in affiliation_map:
        # Full name
        first_name = name_cache_cached.get(p_id, {}).get('first_name') or ''
        last_name = name_cache_cached.get(p_id, {}).get('last_name') or ''

        # Account info
        acc_id = owner2account[p_id]
        acc_name = account2name[acc_id]

        employee_number = tuple(sorted(person2employeeNumber.get(p_id, ())))
        if len(employee_number) > 1:
            logger.warning("Multiple employee numbers for person_id=%r", p_id)

        if len(employee_number) < 1:
            logger.debug("No employee_number for person_id=%r", p_id)
            employee_number = None
        else:
            employee_number = employee_number[0]

        attrs = {
            'uname': acc_name,
            'given': first_name,
            'sn': last_name,
            'birth': persons[p_id].strftime('%d-%m-%Y'),
            # 'worktitle': worktitle,
            'contacts': person2contact.get(p_id, None),
            'campus': person2campus.get(p_id, None),
            'home_address': person2home_address.get(p_id, None),
            'auth_str': auth_list.get(acc_id, ""),
            'employee_number': employee_number,
            'email': uname2mail.get(acc_name, ""),
        }
        export_objects[p_id] = {
            'attrs': attrs,
            'affs': affiliation_map[p_id],
        }
    return export_objects


def build_csv(fh, persons):
    """
    Write person data to csv file.

    :param fh:
        An open filelike bytestream
    :param persons:
        A dict with data to write, from :py:func:`generate_export_data`
    """
    writer = csvutils.UnicodeWriter(fh, dialect=csvutils.CerebrumDialect)
    for person_id, person_data in persons.items():
        attrs = person_data['attrs']
        affs = person_data['affs']
        for aff in affs:
            # TODO: Do we really want to pick the last one?
            affkode, sko, sko_name = (aff['affiliation'], aff['stedkode'],
                                      aff['stednavn'])
        writer.writerow((
            attrs['sn'],
            attrs['given'],
            attrs['birth'],
            attrs['uname'],
            # TODO: home_address is a list of db_rows?
            attrs['home_address'],
            attrs['email'],
            affkode,
            sko,
            sko_name,
        ))


def build_xml(fh, persons):
    """
    Write person data to xml file.

    :param fh:
        An open filelike bytestream
    :param persons:
        A dict with data to write, from :py:func:`generate_export_data`
    """
    xml = xmlprinter(fh,
                     indent_level=2,
                     data_mode=True)
    xml.startDocument(encoding='utf-8')
    xml.startElement('data')
    xml.startElement('properties')
    xml.dataElement('exportdate', datetime.datetime.now().isoformat(b' '))
    xml.endElement('properties')

    for person_id in sorted(persons):
        attrs = persons[person_id]['attrs']
        xml_attr = {'given': attrs['given'],
                    'sn': attrs['sn'],
                    'birth': attrs['birth']}
        # get person employee number
        employee_number = attrs['employee_number']
        if employee_number:
            logger.debug("collected employee_number=%r", employee_number)
            xml_attr['employee_number'] = employee_number
        # get home address
        home_addressinfo = attrs['home_address']
        if home_addressinfo:
            for c in home_addressinfo:
                home_address = c['address_text']
                home_postalnumber = six.text_type(c['postal_number'])
                home_city = c['city']
                if home_address is not None:
                    home_address = home_address
                    xml_attr['home_address'] = home_address
                if home_postalnumber is not None:
                    xml_attr['home_postal_code'] = home_postalnumber
                if home_city is not None:
                    home_city = home_city
                    xml_attr['home_city'] = home_city
        # get campus
        campusinfo = attrs['campus']
        if campusinfo:
            for c in campusinfo:
                campus_name = c['address_text']
                xml_attr['campus'] = campus_name
        # if attrs['worktitle']: xml_attr['worktitle'] = attrs['worktitle']
        xml.startElement('person', xml_attr)
        xml.emptyElement('account', {'username': attrs['uname'],
                                     'userpassword': 'x',
                                     'email': attrs['email']})
        affs = persons[person_id]['affs']
        if affs:
            xml.startElement('affiliations')
            for aff in affs:
                aff_attrs = OrderedDict(
                    (k, (aff.get(k) or '')) for k in
                    (
                        'affiliation',
                        'status',
                        'stedkode',
                        'prosent',
                        'hovedarbeidsforhold',
                        'stillingskode',
                        'dbh_kategori',
                        'stillingstittel',
                        'last_date',
                    ))
                xml.emptyElement('aff', aff_attrs)
            xml.endElement('affiliations')
        contactinfo = attrs['contacts']
        if contactinfo:
            xml.startElement('contactinfo')
            for c in contactinfo:
                c_attrs = OrderedDict(
                    (k, six.text_type(c[k] or '')) for k in
                    ('source', 'pref', 'type', 'value'))
                xml.emptyElement('contact', c_attrs)
            xml.endElement('contactinfo')
        xml.endElement('person')
    xml.endElement('data')
    xml.endDocument()


default_mapping_file = os.path.join(
    sys.prefix, "var/source/bas_portal_mapping.csv")

default_employees_file = os.path.join(
    sys.prefix, "var/cache/employees",
    "paga_persons_%s.xml" % datetime.date.today().strftime("%Y-%m-%d"))

default_outfile = os.path.join(
    sys.prefix, "var/cache/oid",
    "oid_export_%s" % datetime.date.today().strftime("%Y-%m-%d"))


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Generate an OID export file",
    )
    parser.add_argument(
        '--employee-file',
        dest='employee_file',
        default=default_employees_file,
        help=('Read and parse employee data from xml-file %(metavar)s '
              '(%(default)s)'),
        metavar='<file>',
    )
    parser.add_argument(
        '--ou-mapping',
        dest='mapping_file',
        default=default_mapping_file,
        help=('Read and parse OU mappings from csv-file %(metavar)s '
              '(%(default)s)'),
        metavar='<file>',
    )
    outfile_arg = parser.add_argument(
        '-o', '--outfile',
        dest='outfile',
        default=default_outfile,
        help='Write output to %(metavar)s (%(default)s)',
        metavar='<file>',
    )
    parser.add_argument(
        '--csv',
        dest='use_csv',
        action='store_true',
        default=False,
        help='Format output as CSV (default: XML)',
    )
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('console', args)

    with ParserContext(parser, outfile_arg):
        if args.use_csv and outfile_arg == default_outfile:
            raise ValueError(
                "Must set an alternate outfile when generating CSV")

    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    db = Factory.get('Database')()

    ou_cache = OuCache(db)
    bas_portal_mapping = build_ou_mappings(
        ou_cache,
        read_ou_mappings(args.mapping_file))

    aff_to_stilling_map = AffCache(db, args.employee_file)

    load_cache(db)

    affiliations = get_affiliations(db,
                                    ou_cache,
                                    bas_portal_mapping,
                                    aff_to_stilling_map)

    export_data = generate_export_data(affiliations)

    with io.open(args.outfile, mode='w', encoding='utf-8') as outfile:
        if args.use_csv:
            build_csv(outfile, export_data)
            logger.info("Wrote CSV data to %s", args.outfile)
        else:
            build_xml(outfile, export_data)
            logger.info("Wrote XML data to %s", args.outfile)

    logger.info("Done %s", parser.prog)


if __name__ == "__main__":
    main()
