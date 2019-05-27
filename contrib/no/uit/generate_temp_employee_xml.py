#! /usr/bin/env python
# -- coding: utf-8 --
#
# Copyright 2014-2019 University of Oslo, Norway
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
This script generates an xml file with information about
temporary employed scientific persons at UiT.

Format
------
The generated XML file contains a list of groups:

.. code:: xml

    <?xml version="1.0" encoding="utf-8"?>
    <data>
      <properties>
        <tstamp>2014-04-29 02:40:54.00</tstamp>
      </properties>
    <groups>
      <group>
        <MailTip>Midlertidige vitenskapelige ansatte uit.helsefak</MailTip>
        <displayname>
          Midlertidige vitenskapelige ansatte uit.helsefak
        </displayname>
        <mail>midlertidig.vitenskapelig.ansatt@helsefak.uit.no</mail>
        <alias>helsefak.midlertidig.vitenskapelig.ansatt</alias>
        <members>usernames,username.....</members>
        <name>helsefak.midlertidig.vitenskapelig.ansatt</name>
        <samaccountname>helsefak.midlertidig.vitenskapelig.ansatt</samaccountname>
      </group>
      <group>
        <MailTip>Midlertidige vitenskapelige ansatte uit</MailTip>
        <displayname>Midlertidige vitenskapelige ansatte uit</displayname>
        <mail>uit.midlertidig.vitenskapelig.ansatt@uit.no</mail>
        <alias>midlertidig.vitenskapelig.ansatt</alias>
        <members>group_samaaccountname.....</members>
        <name>uit.midlertidig.vitenskapelig.ansatt</name>
        <samaccountname>uit.midlertidig.vitenskapelig.ansatt</samaccountname>
      </group>
    </group>

History
-------
kbj005 2015.02.25: Copied from Leetah.
"""
from __future__ import unicode_literals

import argparse
import csv
import datetime
import logging
import os

import six
from lxml import etree

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.utils.argutils import get_constant

logger = logging.getLogger(__name__)


class Employment(object):
    """
    Class containing all relevant information for each person/role
    """
    def __init__(self, person_id, external_id, account_name,
                 faculty_name, email, stedkode):
        self.person_id = person_id
        self.account_name = account_name
        self.external_id = external_id
        self.stedkode = stedkode
        self.email = email
        self.faculty_name = faculty_name

    def __repr__(self):
        return '<person_id=%r account=%r sko=%r>' % (self.person_id,
                                                     self.account_name,
                                                     self.stedkode)


class OuCache(object):
    """Cache required ou information."""

    def __init__(self, db):
        ou_ids = self.ou_ids = {}
        ou_skos = self.ou_skos = {}
        logger.info('Caching OU data...')
        co = Factory.get('Constants')(db)
        ou = Factory.get('OU')(db)
        for row in ou.get_stedkoder():
            ou.clear()
            ou.find(row['ou_id'])
            sko = "%02d%02d%02d" % (ou.fakultet, ou.institutt, ou.avdeling)
            ou_ids[row['ou_id']] = ou_skos[sko] = {
                'sko': sko,
                'faculty': "%02d0000" % (ou.fakultet, ),
                'name': ou.get_name_with_language(co.ou_name_acronym,
                                                  co.language_nb,
                                                  default=''),
            }
        # Quick sanity check
        for ou_dict in ou_ids.values():
            if ou_dict['faculty'] not in ou_skos:
                logger.error("No faculty=%r found for ou=%r",
                             ou_dict['faculty'], ou_dict)
        logger.info('cached %d ous (%d ou sko)',
                    len(ou_ids), len(ou_skos))

    def get_sko(self, ou_id):
        return self.ou_ids[ou_id]['sko']

    def get_faculty_name(self, ou_id):
        faculty_sko = self.ou_ids[ou_id]['faculty']
        return self.ou_skos[faculty_sko]['name']


def filter_employees(persons, employee_data):
    """
    Filter out unqualified persons accoring to employee data.

    :type person_list: iterable
    :param person_list:
        An iterable of :py:class:`Employment` objects.

    :type employee_data: dict
    :param employee_data:
        A dict that maps from fnr to employee data from paga.

    The result will only include person objects which:

    - has fnr in paga file and BAS
    - has stedkode in paga file that matches stedkode from BAS
    - has stillingsprosent > 49%
    - has employment type != F
    """
    for person in persons:
        if person.external_id not in employee_data:
            logger.warning("Unable to find person=%s in employee_data",
                           repr(person))
            continue

        for employment in employee_data[person.external_id]:
            if person.stedkode != employment['stedkode']:
                logger.debug("Mismatch on sko for person=%s (stedkode=%r)",
                             repr(person), employment['stedkode'])
                # Note: There may exist another person object whith the correct
                #       stedkode?
                continue

            # TODO: Why don't we check for value < 50?
            if employment['prosent'] <= 49:
                logger.warning("Skipping person=%s with employment "
                               "%r%% < 50%%",
                               repr(person), employment['prosent'])
                continue
            if not employment['ansatt_type']:
                logger.error("Missing employment type for person=%s, skipping",
                             repr(person))
                continue
            if employment['ansatt_type'] == 'F':
                logger.debug("Skipping person=%s with employment type=%r",
                             repr(person), employment['ansatt_type'])
                # TODO: This may be incorrect?
                #       Should the person be exported if *any* of the
                #       employments contains 'F'? They are now!
                continue

            logger.info("Including employment for person=%s, type=%r",
                        repr(person), employment['ansatt_type'])
            person.emp_type = employment['ansatt_type']
            yield person


def write_xml(qualified_list, out_file):
    """Write persondata to xml file."""
    logger.debug("Writing output to %r", out_file)

    # Organize qualified by faculty name, TODO: Use ordereddict/defaultdict
    faculty_list = []
    by_faculty = dict()
    for qualified in qualified_list:
        if qualified.faculty_name not in faculty_list:
            faculty_list.append(qualified.faculty_name)
            by_faculty[qualified.faculty_name] = list()
        if qualified not in by_faculty[qualified.faculty_name]:
            by_faculty[qualified.faculty_name].append(qualified)

    # generate xml root node
    data = etree.Element('data')

    # generate data node
    properties = etree.SubElement(data, 'properties')

    # Generate properties node with timestamp
    tstamp = etree.SubElement(properties, 'tstamp')
    tstamp.text = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # generate global group which has all other groups as members
    global_group = etree.SubElement(data, 'groups')

    # create 1 group foreach entry in faculty_list
    root_members = []
    for faculty in faculty_list:
        group = etree.SubElement(global_group, 'group')
        mailtip = etree.SubElement(group, 'MailTip')
        mailtip.text = "%s Midlertidige vitenskapelige ansatte" % faculty

        displayname = etree.SubElement(group, 'displayname')
        displayname.text = "%s Midlertidige vitenskapelige ansatte" % faculty

        member_list = []
        for qualified in by_faculty[faculty]:
            # make sure usernames are unique (no duplicates) within
            # each group
            if qualified.account_name not in member_list:
                member_list.append(qualified.account_name)
            else:
                logger.warning("Duplicate member=%r of group=%r",
                               qualified.account_name, displayname.text)

        acc_name = etree.SubElement(group, 'members')
        acc_name.text = ','.join(member_list)
        name = etree.SubElement(group, 'name')
        name.text = "%s Midlertidige vitenskapelige ansatte" % faculty
        samaccountname = etree.SubElement(group, 'samaccountname')
        samaccountname.text = ("uit.%s.midl.vit.ansatt" % (faculty,)).lower()
        root_members.append(samaccountname.text)

        mail = etree.SubElement(group, 'mail')
        mail.text = ("%s@auto.uit.no" % (samaccountname.text,)).lower()

        mail_nick = etree.SubElement(group, 'alias')
        mail_nick.text = ("%s.midl.vit.ansatt" % (faculty,)).lower()

    #
    # generate root group
    #

    # generate system group containing list of all the other groups
    system_group = etree.SubElement(global_group, 'group')

    mailtip = etree.SubElement(system_group, 'MailTip')
    mailtip.text = "Midlertidige vitenskapelige ansatte UiT"

    displayname = etree.SubElement(system_group, 'displayname')
    displayname.text = "Midlertidige vitenskapelige ansatte UiT"

    mail = etree.SubElement(system_group, 'mail')
    mail.text = "uit.midl.vit.ansatt@auto.uit.no"

    alias = etree.SubElement(system_group, 'alias')
    alias.text = "uit.midl.vit.ansatt"

    name = etree.SubElement(system_group, 'name')
    name.text = "Midlertidig vitenskapelige ansatte UiT"

    # create list of all facultys
    samaccountname = etree.SubElement(system_group, 'samaccountname')
    samaccountname.text = "uit.midl.vit.ansatt"

    members = etree.SubElement(system_group, 'members')
    members.text = ",".join(root_members)

    with open(out_file, 'w') as fh:
        fh.write(etree.tostring(data,
                                pretty_print=True,
                                encoding='iso-8859-1'))


def read_employee_data(filename, encoding='iso-8859-1', charsep=';'):
    """Read and decode entried from the paga CSV file."""
    logger.info("Reading employee data from file=%r (encoding=%r, charsep=%r)",
                filename, encoding, charsep)
    count = 0
    with open(filename, mode='rb') as f:
        for data in csv.DictReader(f, delimiter=charsep.encode(encoding)):
            paga_dict = {k.decode(encoding): v.decode(encoding)
                         for k, v in data.items()}
            # PAGA uses ',' as a decimal separator
            pct = float(paga_dict['St.andel'].replace(',', '.'))
            yield {
                'fnr': paga_dict['Fødselsnummer'],
                'ansatt_type': paga_dict['Tj.forh.'],
                'prosent': pct,
                'stedkode': paga_dict['Org.nr.'],
            }
            count += 1
    logger.info("Read %d entries from file", count)


def get_persons(db, affiliation_status_types):
    """
    Get persons from database.

    Generate list of all persons (in BAS DB) with the correct affiliation
    status.

    :param affiliation_status_types:
        An iterable of PersonAffStatus affiliations to find

    :rtype: list
    :return:
        A list of dicts, each dict contains keys: account id, person id,
        external id, group membership
    """
    const = Factory.get('Constants')(db)
    person = Factory.get('Person')(db)
    account = Factory.get('Account')(db)

    sys_lookup_order = tuple((
        const.human2constant(value, const.AuthoritativeSystem)
        for value in cereconf.SYSTEM_LOOKUP_ORDER))
    logger.debug("system_lookup_order: %r", map(six.text_type,
                                                sys_lookup_order))

    ou_cache = OuCache(db)

    def select_extid(entity_id, id_type):
        """ Get preferred fnr for a given person_id. """
        ext_ids = {int(r['source_system']): r['external_id']
                   for r in person.search_external_ids(
                        entity_id=entity_id,
                        source_system=sys_lookup_order,
                        id_type=id_type)}
        for pref in sys_lookup_order:
            if ext_ids.get(int(pref)):
                return ext_ids[int(pref)]
        raise Errors.NotFoundError("No fnr for person_id=%r" % (entity_id,))

    count = 0

    logger.info("Fetching persons with affiliations %r ...",
                map(six.text_type, affiliation_status_types))
    for affst in affiliation_status_types:
        # TODO: Do we ever want anything else than vitenskapelige?
        #       Could we just do a search on all affs in aff_status in one go?
        logger.debug("Processing aff=%r", affst)
        for row in person.list_affiliations(affiliation=affst.affiliation,
                                            status=affst):
            person_id = row['person_id']

            for id_type in (const.externalid_fodselsnr,
                            const.externalid_pass_number):
                try:
                    external_id = select_extid(person_id, id_type)
                except Errors.NotFoundError:
                    logger.debug("Person person_id=%r has no id_type=%s",
                                 person_id, id_type)
                    continue
                else:
                    # Found valid id_type
                    break
            else:
                # For loop completed wo/ break, no valid id_type
                raise RuntimeError("No valid external ids for person_id=%r" %
                                   (person_id, ))

            person.clear()
            person.find(person_id)

            primary_acc_id = person.get_primary_account()
            if primary_acc_id is None:
                logger.warning("No primary account for person_id=%r, skipping",
                               person_id)
                continue
            # Get primary account for all of persons having employee
            # affiliation
            account.clear()
            account.find(primary_acc_id)
            acc_name = account.account_name
            try:
                email = account.get_primary_mailaddress()
            except Errors.NotFoundError:
                logger.warning("No email address for account_id=%r (%s)",
                               account.account_id, account.account_name)
                email = None

            my_stedkode = ou_cache.get_sko(row['ou_id'])
            faculty_name = ou_cache.get_faculty_name(row['ou_id'])

            logger.debug("Found candidate person_id=%r in db", person_id)
            emp = Employment(person_id, external_id, acc_name, faculty_name,
                             email, my_stedkode)
            count += 1
            yield emp
    logger.info("Found %d persons in database", count)


default_log_preset = getattr(cereconf, 'DEFAULT_LOGGER_TARGET', 'cronjob')
default_in_file = os.path.join(cereconf.DUMPDIR, 'paga/uit_paga_last.csv')
default_out_file = os.path.join(
    cereconf.DUMPDIR,
    "temp_emp_%s.xml" % datetime.date.today().strftime("%Y-%m-%d"))
default_aff_status = 'ANSATT/vitenskapelig'


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Generate a scientific employments XML file",
    )
    parser.add_argument(
        '-p', '--person-file',
        dest='in_filename',
        help='Read and import persons from %(metavar)s (%(default)s)',
        default=default_in_file,
        metavar='<filename>',
    )
    parser.add_argument(
        '-o', '--out-file',
        dest='out_filename',
        help='Write XML file to %(metavar)s (%(default)s)',
        default=default_out_file,
        metavar='<filename>',
    )
    aff_status_arg = parser.add_argument(
        '-a', '--aff-status',
        dest='aff_status',
        action='append',
        help=('Add a person affiliation status to be included in the output.'
              'The argument can be repeated. If no aff-status arguments are '
              'given, %s will be used as a default' % (default_aff_status,)),
        metavar='<aff>',
    )

    add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf(default_log_preset, args)

    logger.info('Start of %s', parser.prog)
    logger.debug('args: %r', args)

    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)

    aff_status = [
        get_constant(db, parser, co.PersonAffStatus, v, aff_status_arg)
        for v in (args.aff_status or (default_aff_status,))]
    logger.info("Affiliations: %r", map(six.text_type, aff_status))

    person_file = args.in_filename
    out_file = args.out_filename

    if not person_file:
        raise ValueError("Invalid input filename %r" % (person_file, ))
    if not os.path.exists(person_file):
        raise IOError("Input file %r does not exist" % (person_file, ))
    if not out_file:
        raise ValueError("Invalid output filename %r" % (out_file, ))

    # generate personlist from BAS
    persons = list(get_persons(db, aff_status))

    # read paga file
    employee_data = {}
    for d in read_employee_data(person_file):
        employee_data.setdefault(d['fnr'], []).append(d)

    # Select all persons that qualify accoring to paga_data
    logger.info("Filtering by employment type...")
    qualified_list = list(filter_employees(persons, employee_data))
    logger.info("Found %d qualified", len(qualified_list))

    # write xml file
    write_xml(qualified_list, out_file)
    logger.info("Wrote employee groups to %r", out_file)


if __name__ == '__main__':
    main()
