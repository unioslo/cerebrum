#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2018-2019 University of Tromso, Norway
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
This program collects mobile_numbers from Difi's 'Kontakt- og
reservasjonssregister' for all persons in the given Paga file and
populates entity_contact_info table in Cerebrum.
"""

from __future__ import print_function

import argparse
import csv
import json
import logging
import sys
import urllib2

import Cerebrum.logutils
from Cerebrum import Errors
from Cerebrum.utils import phone
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.Utils import Factory, read_password


national_identity_column = 0

logger = logging.getLogger(__name__)


def format_e164(number, region="NO"):
    """
    Takes a putative phone number and returns it in E.164 format.
    Returns `None` if it is not a parsable or valid phone number.
    """
    try:
        numobj = phone.parse(number, region=region)
    except phone.NumberParseException as e:
        logger.warning("Not a phone number: %r: %s", number, e)
        return None
    if phone.is_valid(numobj):
        return phone.format(numobj)
    else:
        logger.warning("Invalid phone number: %r", number)
        return None


def get_national_identies(reader, number_of_columns):
    """
    Function that parses the uit_paga_YYYY-MM-DD.csv file and extracts all
    national identities (fødselsnummer)
    """

    national_identity = []
    i = 0
    for column in reader:
        if column[national_identity_column].isdigit():
            national_identity.append(column[national_identity_column])
            i += 1
        if i >= number_of_columns:
            break
    return national_identity


def get_mobile_list(token, social_security_number_list):
    """
    Function that takes a list of Norwegian social security numbers and returns
    a dictionary with the corresponding mobile phone number OR None as value
    and the social security number as key
    """
    opener = urllib2.build_opener()

    data = json.dumps({
        "personidentifikator": social_security_number_list,
    })
    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'Authorization': token,
    }

    request = urllib2.Request('https://oppslag.uit.no/api/person',
                              data,
                              headers)

    result_dict = {}

    try:
        for result in json.load(opener.open(request)):
            phone = None
            if (result['Status'] == 0 and
                    result['Kontaktinformasjon'] is not None):
                try:
                    phone = result['Kontaktinformasjon']
                    phone = phone['Mobiltelefonnummer']['Nummer']
                except TypeError:
                    pass
            result_dict[result['Personidentifikator']] = phone
    except urllib2.HTTPError:
        return result_dict

    return result_dict


def update_bas(db, mobile_phones):
    """
    Function to update BAS with mobile phone numbers
    """
    p = Factory.get('Person')(db)
    co = Factory.get('Constants')(db)

    for national_identity, mobile_phone in mobile_phones.items():
        logger.debug("Processing nin=%r", national_identity)
        if mobile_phone is None:
            logger.debug("No phone number in KR-REG for person, ignoring...")
            continue

        # convert number to E.164 format (+<Land code><phone number>)
        mobile_phone_e164 = format_e164(mobile_phone)

        if mobile_phone_e164 is None:
            logger.debug("Conversion of number from KR-REG failed, "
                         "ignoring...")
            continue

        p.clear()
        try:
            p.find_by_external_id(co.externalid_fodselsnr, national_identity)
        except Errors.NotFoundError:
            logger.debug("No relevant person found in Cerebrum, ignoring...")
            continue
        except Errors.TooManyRowsError:
            # This persons fnr is registered to multiple entity_ids in
            # entity_external_id table This is an error, person should not have
            # not more than one entity_id.  Don't know which person object to
            # use, return error message.
            logger.error("Multiple persons share nin=%r in Cerebrum, "
                         "ignoring...", national_identity)
            continue

        # TODO: is it better to make a list over registered ice_numbers
        #  (just once) with: p.list_contact_info(source_system =
        #  co.system_kr_reg, contact_type = co.contact_ice_phone) instead of
        #  calling get_contact_info for each person?

        ice_num_info = p.get_contact_info(source=co.system_kr_reg,
                                          type=co.contact_ice_phone)
        if len(ice_num_info) > 0:
            logger.debug("Person already has ICE num from KR-REG in BAS, "
                         "comparing it with new one from KR-REG")

            ice_num = ice_num_info[0]["contact_value"]

            if ice_num == mobile_phone_e164:
                logger.debug("New ICE num from KR-REG is same as one in BAS, "
                             "doing nothing...")
                continue
            else:
                logger.debug("ICE num from KR-REG (%s) differs from one in BAS"
                             " (%s), replacing...", mobile_phone_e164, ice_num)
                p.delete_contact_info(source=co.system_kr_reg,
                                      contact_type=co.contact_ice_phone)
                p.add_contact_info(source=co.system_kr_reg,
                                   type=co.contact_ice_phone,
                                   value=mobile_phone_e164)
        else:
            logger.debug("Person has no previous ICE number from KR-REG in "
                         "BAS, adding the new one (%s)", mobile_phone_e164)
            p.add_contact_info(source=co.system_kr_reg,
                               type=co.contact_ice_phone,
                               value=mobile_phone_e164)

        p.write_db()
    return 1


def main(inargs=None):
    # Parse arguments
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-p',
                        '--pagafile',
                        metavar='filename',
                        help='Read national identities from given Paga file',
                        required=True)
    add_commit_args(parser)

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    try:
        file_obj = open(args.pagafile, 'r')
    except IOError:
        sys.exit("Could not open file: '{}'".format(args.pagafile))
    reader = csv.reader(file_obj, delimiter=';')

    row_fetched = 0
    row_fetch_max = 1000
    row_count = sum(1 for row in file_obj)
    file_obj.seek(0)
    mobile_count = 0

    # Initialize database
    db = Factory.get('Database')()
    db.cl_init(change_program='fetch_mobile')

    logger.info("Updating BAS with ICE numbers from Difi's"
                "'Kontakt- og reservasjonssregister'.")

    # Dummy username
    token = read_password('difi', 'oppslag.uit.no')

    while row_fetched < row_count:
        # GET all national identities
        national_identies = get_national_identies(reader, row_fetch_max)
        # GET all mobile phone numbers
        mobile_phones = get_mobile_list(token, national_identies)
        # UPDATE BAS
        mobile_count += update_bas(db, mobile_phones)

        row_fetched += row_fetch_max

    logger.debug("############")
    logger.debug("Lines in pagafile: %s" % row_count)

    if mobile_count > 0:
        logger.info("%s new ICE numbers added to BAS." % mobile_count)
        if args.commit:
            db.commit()
            logger.info("Committed all changes.")
        else:
            db.rollback()
            logger.info("Dryrun. Rollback changes.")
    else:
        logger.info("No new ICE numbers found.")


if __name__ == '__main__':
    main()
