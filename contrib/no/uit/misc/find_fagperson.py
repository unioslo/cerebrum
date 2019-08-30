#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2019 University of Oslo, Norway
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

from __future__ import print_function

# Generic imports
import argparse
import os.path
import io

# cerebrum imports
import logging
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.utils.csvutils import UnicodeDictWriter

"""
    Reads a txt file containing fnrs and returns a csv file containing:
     <fnr>;[username];[comments]
"""


# process each line:
# remove newlines, and space and and make sure each fnr consists of 11 digits.
#   append leading zero if first or last part consits of 6/5 digits and first
#   digit is nonzero
#
def process_line(line):
    line = line.strip()
    first_part, second_part = line.split(",", 1)
    if first_part.isdigit():
        if len(first_part) == 5 and first_part[0] != '0':
            first_part = "0%s" % first_part
    if second_part.isdigit():
        if len(second_part) == 4 and second_part[0] != '0':
            second_part = "0%s" % second_part
    ready_fnr = "%s%s" % (first_part, second_part)
    return ready_fnr


# Read input file
# and make sure to return a 11 digit fnr for each entry
#
def read_file(input_file, output_file, logger):
    fnrs = []
    logger.info("Reading file: %s" % input_file)
    logger.info("Writing file: %s" % output_file)
    fh = open(input_file, 'r')
    for lines in fh.readlines():
        line = process_line(lines)
        if line.isdigit() and len(line) == 11:
            fnrs.append(line)
        else:
            logger.warn("Unable to process line:%s. Not on proper format"
                        % line)
    return fnrs


#
# Read fnr_list and return a dict of persons having active UiT accounts today
# dict format is: {'fnr':{'username' : [username],'note' : [notes..if any]}}
#
def get_accounts(fnr_list, db):
    ac = Factory.get('Account')(db)
    pe = Factory.get('Person')(db)
    co = Factory.get('Constants')(db)
    fagpersons_dict = {}

    for fnr in fnr_list:
        person_dict = {'username': '', 'note': ''}
        pe.clear()
        try:
            pe.find_by_external_id(co.externalid_fodselsnr,
                                   fnr, source_system=co.system_fs)
        except Errors.NotFoundError:
            person_dict['note'] = ("does not exist in cerebrum with source=FS."
                                   " Skipping.")
        else:
            # persons exits in cerebrum. now try to find the accounts
            try:
                # this should only return active accounts
                accounts = pe.get_accounts(filter_expired=False)
            except Errors.NotFoundError:
                person_dict['note'] = "This person has no accounts"
            # some ppl har multiple accounts (sito). Make sure sito accounts
            # are filtered
            for account in accounts:
                ac.clear()
                ac.find(account[0])
                username = ac.get_account_name()
                if len(username) == 6 and username[-1] != 's':
                    # this is a uit account. add it
                    person_dict['username'] = username
                if ac.is_expired():
                    person_dict['note'] = 'is expired'
        fagpersons_dict[fnr] = person_dict
    return fagpersons_dict


# Write output to file on csv format: <fnr>;[[username]|[error message]
#
def write_to_file(fagperson_dict, output_file, logger):
    column_names = ['fnr', 'username', 'comment']
    errors = 'replace'
    with io.open(output_file, 'w', encoding='UTF-8', errors=errors) as stream:
        try:
            writer = UnicodeDictWriter(stream, column_names)
            writer.writeheader()
            for fnr, items in fagperson_dict.iteritems():
                writer.writerow({'fnr': fnr, 'username': items['username'],
                                'comment': items['note']})
        except Exception as m:
            logger.error("Unexpected error. Reason:%s" % m)


#
# Main function
#
def main(args=None):
    db = Factory.get('Database')()
    logger = logging.getLogger(__name__)
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument('--input', '-i',
                        required=True,
                        dest='input_file',
                        help='Input filename')
    parser.add_argument('--output', '-o',
                        required=True,
                        dest='output_file',
                        help='Output filename')
    args = parser.parse_args()

    if(os.path.isfile(args.input_file)):
        fnr_list = read_file(args.input_file, args.output_file, logger)
        fagpersons = get_accounts(fnr_list, db)
        write_to_file(fagpersons, args.output_file, logger)
    else:
        # input file does not exist. print error message and exit
        logger.error("file :%s does not exist. Exiting." % args.input_file)


#
# Kickstart main function
#
if __name__ == '__main__':
    main()
