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

import copy
import datetime
import getopt
import os
import sys
import time

import mx.DateTime
from lxml import etree

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory

progname = __file__.split(os.sep)[-1]
logger = Factory.get_logger(cereconf.DEFAULT_LOGGER_TARGET)

db = Factory.get('Database')()
db.cl_init(change_program=progname)

group = Factory.get('Group')(db)
person = Factory.get('Person')(db)
const = Factory.get('Constants')(db)
account = Factory.get('Account')(db)
ou = Factory.get('OU')(db)

dumpdir = cereconf.DUMPDIR


class TempVitenskaplig(object):
    """
    Class containing all relevant information for each entry/person in the xml
    file.
    """
    def __init__(self, external_id, account_name, faculty_name, email,
                 stedkode):
        self.account_name = account_name
        self.external_id = external_id
        self.emp_type = None
        self.stedkode = stedkode
        self.email = email
        self.faculty_name = faculty_name


def set_tj_forhold(person_list, paga_data):
    """
    Update tj_forhold

    Foreach person in person_list, set tj_forhold:

    Only prosess persons which:

    - has fnr in paga file and BAS
    - has stedkode in paga file that matches stedkode from BAS
    - has stillingsprosent > 49%
    - has employment type != F
    """
    qualified_list = []
    for person in person_list:
        found = False
        for paga_person in paga_data:
            if person.external_id == paga_person['fnr']:
                # fnr from BAS also exists in paga file
                found = True
                if person.stedkode == paga_person['stedkode']:
                    # correct stedkode
                    my_prosent = str(paga_person['prosent']).split(',', 1)
                    if int(my_prosent[0]) > 49:
                        # prosent:%s is larger than 50 %
                        person.emp_type = paga_person['ansatt_type']
                        if person.emp_type != 'F':
                            qualified_person = copy.deepcopy(person)
                            qualified_list.append(qualified_person)
                            logger.debug("setting employment type:%s "
                                         "for person:%s",
                                         paga_person['ansatt_type'],
                                         person.external_id)

                        else:
                            logger.debug("person:%s has permanent job. "
                                         "NOT inserting", person.external_id)
                    else:
                        logger.warning("person:%s has prosent:%s. which is "
                                       "less than 50. NOT inserting",
                                       person.external_id, my_prosent[0])
                else:
                    # no match on stedkode
                    logger.debug("match on fnr:%s, but stedkode:%s from BAS "
                                 "does not match stedkode:%s from PAGA",
                                 person.external_id, person.stedkode,
                                 paga_person['stedkode'])
        if not found:
            logger.debug("Unable to find fnr:%s in paga file",
                         person.external_id)
    return qualified_list


def write_xml(qualified_list, out_file):
    """Write persondata to xml file."""
    logger.debug("Writing output to %r", out_file)
    root_members = []
    ts = time.time()
    st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

    faculty_list = []
    # generate faculty name list for easier xml generation
    for qualified in qualified_list:
        if qualified.faculty_name not in faculty_list:
            faculty_list.append(qualified.faculty_name)

    # generate xml root node
    data = etree.Element('data')

    # generate data node
    properties = etree.SubElement(data, 'properties')

    # Generate properties node with timestamp
    tstamp = etree.SubElement(properties, 'tstamp')
    tstamp.text = "%s" % st

    # generate global group which has all other groups as members
    global_group = etree.SubElement(data, 'groups')

    # create 1 group foreach entry in faculty_list
    for faculty in faculty_list:
        member_list = []
        group = etree.SubElement(global_group, 'group')
        mailtip = etree.SubElement(group, 'MailTip')
        mailtip.text = "%s Midlertidige vitenskapelige ansatte" % faculty

        displayname = etree.SubElement(group, 'displayname')
        displayname.text = "%s Midlertidige vitenskapelige ansatte" % faculty

        account_names = ''
        for qualified in qualified_list:
            if qualified.emp_type:
                # sanity check...
                if qualified.emp_type != 'F':
                    if qualified.faculty_name == faculty:
                        # make sure usernames are unique (no duplicates) within
                        # each group
                        if qualified.account_name not in member_list:
                            member_list.append(qualified.account_name)
                            account_names = '%s,%s' % (account_names,
                                                       qualified.account_name)
                            account_names = account_names.lstrip(',')
                        else:
                            logger.warn("member:%s not added to group:%s since"
                                        " the username already exists there",
                                        qualified.account_name,
                                        displayname.text)
            else:
                logger.warn("ERROR: person:%s does not have emp_type from Paga"
                            " file. person did not qualify",
                            qualified.external_id)

        acc_name = etree.SubElement(group, 'members')
        acc_name.text = "%s" % account_names
        name = etree.SubElement(group, 'name')
        name.text = "%s Midlertidige vitenskapelige ansatte" % faculty
        samaccountname = etree.SubElement(group, 'samaccountname')
        samaccountname.text = "uit.%s.midl.vit.ansatt" % faculty
        samaccountname.text = samaccountname.text.lower()
        root_members.append(samaccountname.text)

        mail = etree.SubElement(group, 'mail')
        mail.text = "%s@auto.uit.no" % samaccountname.text
        mail.text = mail.text.lower()

        mail_nick = etree.SubElement(group, 'alias')
        mail_nick.text = "%s.midl.vit.ansatt" % faculty
        mail_nick.text = mail_nick.text.lower()

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
    all_facultys = ",".join(root_members)
    samaccountname = etree.SubElement(system_group, 'samaccountname')
    samaccountname.text = "uit.midl.vit.ansatt"

    members = etree.SubElement(system_group, 'members')
    members.text = "%s" % all_facultys

    with open(out_file, 'w') as fh:
        fh.writelines(etree.tostring(data,
                                     pretty_print=True,
                                     encoding='iso-8859-1'))


#
# Read (paga) person file
#
def read_paga(filename):
    paga_person = []
    paga_dict = {}
    fh = open(filename, 'r')
    for line in fh:
        line = line.decode("iso-8859-1")
        line_data = line.split(";")

        paga_dict = {
            'fnr': line_data[0],
            'ansatt_type': line_data[39],
            'prosent': line_data[36],
            'stedkode': line_data[15],
        }
        paga_person.append(paga_dict)
    return paga_person


def get_persons(aff_status):
    """
    Get persons from database.

    Generate list of all persons (in BAS DB) with the correct affiliation
    status.

    :rtype: list
    :return:
        A list of dicts, each dict contains keys: account id, person id,
        external id, group membership
    """
    person_list = []

    for aff in aff_status:
        if aff == 'vitenskapelig':
            decoded_aff_status = int(
                const.affiliation_status_ansatt_vitenskapelig)

        # collect employee persons with affiliation = ansatt
        for row in person.list_affiliations(
                affiliation=const.affiliation_ansatt,
                status=decoded_aff_status):
            person.clear()
            data = (row['person_id'])
            person.find(data)

            external_id = person.get_external_id(
                id_type=const.externalid_fodselsnr)
            decoded_external_id = None

            # get external_id filtered by SYSTEM_LOOKUP
            for system in cereconf.SYSTEM_LOOKUP_ORDER:
                system_id = getattr(const, system)
                for id in external_id:
                    # get fnr with highest priority from SYSTEM_LOOKUP_ORDER
                    id_source = const.AuthoritativeSystem(id['source_system'])
                    if str(system_id) == str(id_source):
                        decoded_external_id = id['external_id']
                        break
                if decoded_external_id is not None:
                    break
            if decoded_external_id is None:
                # TODO: Raise Exception?
                logger.critical("no external id for person:%s. exiting", data)
                sys.exit(1)

            # Get primary account for all of persons having employee
            # affiliation
            acc_id = person.get_primary_account()
            if acc_id is not None:
                account.clear()
                account.find(acc_id)
                acc_name = account.get_account_name()
                try:
                    email = account.get_primary_mailaddress()
                except Errors.NotFoundError:
                    logger.warning("Account %s (%s) has no primary email "
                                   "address", acc_id, acc_name)
                    email = None
                ou.clear()
                try:
                    ou.find(row['ou_id'])
                except Exception:
                    logger.warning("unable to find ou_id:%s. Is it expired?",
                                   row['ou_id'])
                    continue
                faculty_sko = ou.fakultet
                my_fakultet = ou.fakultet
                my_institutt = ou.institutt
                my_avdeling = ou.avdeling

                if str(my_fakultet).__len__() == 1:
                    my_fakultet = "0%s" % my_fakultet
                if str(ou.institutt).__len__() == 1:
                    my_institutt = "0%s" % my_institutt
                if str(ou.avdeling).__len__() == 1:
                    my_avdeling = "0%s" % my_avdeling

                my_stedkode = "%s%s%s" % (my_fakultet,
                                          my_institutt,
                                          my_avdeling)
                sko_ou_id = ou.get_stedkoder(fakultet=faculty_sko,
                                             institutt=0,
                                             avdeling=0)
                my_ou_id = sko_ou_id[0]['ou_id']
                ou.clear()
                ou.find(my_ou_id)
                faculty_name = ou.get_name_with_language(const.ou_name_acronym,
                                                         const.language_nb,
                                                         default='')
                logger.debug("collecting person from BAS: %s, %s, %s, %s, %s",
                             decoded_external_id, acc_name, faculty_name,
                             email, my_stedkode)
                person_node = TempVitenskaplig(decoded_external_id, acc_name,
                                               faculty_name, email,
                                               my_stedkode)
                person_list.append(person_node)
    return person_list


def verify_file(personfile):
    """
    Verify that file personfile exists. Exit if not
    """
    if not os.path.isfile(personfile):
        logger.critical("ERROR: File:%s does not exist. Exiting", personfile)
        sys.exit(1)


def main():
    global person_list

    today = mx.DateTime.today().strftime("%Y-%m-%d")
    person_file = None
    aff_status = 'vitenskapelig'
    out_mal = "temp_emp_%s.xml" % today
    out_file = os.path.join(dumpdir, out_mal)

    try:
        opts, args = getopt.getopt(
            sys.argv[1:],
            'p:o:ha:',
            ['person_file=', 'ou_file=', 'help', 'aff_status='])
    except getopt.GetoptError as m:
        usage(1, m)

    for opt, val in opts:
        if opt in('-p', '--person_file'):
            person_file = val
        if opt in('-o', '--out'):
            out_file = val
        if opt in('-a', '--aff_status'):
            aff_status = val
        if opt in('-h', '--help'):
            msg = 'display help information'
            usage(1, msg)
    if not out_file or not person_file:
        msg = "you must spesify person file and out file"
        usage(1, msg)
        raise SystemExit(1)

    verify_file(person_file)

    # generate personlist from BAS
    logger.info("Fetching persons...")
    person_list = get_persons([aff_status])
    logger.info("Found %d persons", len(person_list))

    # read paga file
    logger.info("Reading persons from %r ...", person_file)
    paga_data = read_paga(person_file)
    logger.info("Found %d items", len(paga_data))

    # Add tj.Forhold data for each person
    logger.info("Setting employment type...")
    qualified_list = set_tj_forhold(person_list, paga_data)
    logger.info("Found %d qualified", len(qualified_list))

    # write xml file
    write_xml(qualified_list, out_file)
    logger.info("Wrote list to %r", out_file)


def usage(exitcode=0, msg=None):
    help_text = """
    This script generates an xml file with information about
    temporary employed scientific persons at UiT.

    usage:: %s <-p person_file> [-t <employee_type>] <-o outfile.xml> [-h]

    options:
       [--logger-name]      - Where to log
       [-p | --person_file] - Source file containing person info (from paga)
       [-a | --aff_status]  - one or more of (vitenskapelig,drgrad,gjest,etc).
                              This is a comma separated list.
                              Default value is: vitenskapelig
       [-o | --out]         - Destination xml file
       [-h | --help]        - This text

    """ % (progname,)
    if msg:
        print msg
    print help_text
    sys.exit(exitcode)


if __name__ == '__main__':
    main()
