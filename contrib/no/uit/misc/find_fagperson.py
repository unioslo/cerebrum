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

"""
Reads a text file containing fnr and returns a csv file of all fnrs existing in the database and their accounts.
The csv file contains: <fnr>;<username>;<notes..if any>
"""
from __future__ import print_function

# Generic imports
import argparse
import os 
import sys

# cerebrum imports
import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors



# global variables
__doc__="""
    Reads a txt file containing fnrs and returns a csv file containing <fnr>;[username];[notes]
    for all fnrs having active accounts.
"""
db = Factory.get('Database')()
ac = Factory.get('Account')(db)
pe = Factory.get('Person')(db)
co = Factory.get('Constants')(db)



# print to stderr
def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

#
# Return True if file exists, False if not
#
def file_exists(filename):
    if(os.path.isfile(filename) == False):
        return False
    else:
        return True


# 
# process each line:
# remove newlines, and space and and make sure each fnr consists of 11 digits.
#   append leading zero if first or last part consits of 6/5 digits and first digit is nonzero
#
def process_line(line):
    line = line.strip()
    first_part,second_part = line.split(",",1)
    if first_part.isdigit():
        if len(first_part) == 5 and first_part[0] != '0':
            first_part ="0%s" % first_part
    if second_part.isdigit():
        if len(second_part) == 4 and second_part[0] != '0':
            second_part = "0%s" % second_part
    ready_fnr ="%s%s" % (first_part,second_part)
    
    return ready_fnr
    
            

#
# Read input file
# and make sure to return a 11 digit fnr for each entry
#
def read_file(input_file,output_file):
    fnrs = []
    print ("Reading file: %s" % input_file)
    print ("Writing to file: %s" % output_file)
    fh = open(input_file,'r')
    for lines in fh.readlines():
        line = process_line(lines)
        if line.isdigit() and len(line) == 11:
            fnrs.append(line)
        else:
            eprint("Unable to process line:%s. Not on propper format" % line) 
    return fnrs


#
# Read fnr_list and return a dict of persons having active UiT accounts today
# dict format is: {'fnr':{'username' : [username],'note' : [notes..if any]}}
#
def get_accounts(fnr_list):
    fagpersons_dict = {}
    for fnr in fnr_list:
        person_dict = {'username' : '', 'note' : ''}
        pe.clear()
        try:
            pe.find_by_external_id(co.externalid_fodselsnr,fnr,source_system = co.system_fs)
        except Errors.NotFoundError:
            errormsg = "does not exist in cerebrum. Skipping..."
            person_dict['note'] = errormsg
        else:
            # persons exits in cerebrum. now try to find the accounts
            try:
                # this should only return active accounts
                accounts = pe.get_accounts(filter_expired = False)
            except Errors.NotFoundError:
                errormsg = "This person has no accounts"
                person_dict['note'] = errormsg
            # some ppl har multiple accounts (sito). Make sure sito accounts are filtered
            for account in accounts:
                ac.clear()
                ac.find(account[0])
                username = ac.get_account_name()
                if len(username) == 6 and username[-1] != 's':
                    # this is a uit account. add it
                    person_dict['username'] = username
                if ac.is_expired() == True:
                    person_dict['note'] = 'is expired'
        fagpersons_dict[fnr] = person_dict
    return fagpersons_dict


#
# Write output to file on csv format: <fnr>;[[username]|[error message]
#
def write_to_file(fagperson_dict,output_file):
    fh = open(output_file,"w")
    fh.writelines("<fnr>;<brukernavn>;<kommentar>\n")
    for fnr,items in fagperson_dict.iteritems():

            fh.writelines("%s;%s;%s\n" % (fnr,items['username'],items['note']))
    fh.close()

#
# Main function
#
def main(args=None):
    parser = argparse.ArgumentParser(description=__doc__)
    
    parser.add_argument('--input','-i',
                        required=False,
                        dest='input_file',
                        default = None,
                        action='store',
                        help='Input filename')
    parser.add_argument('--output','-o',
                        required=False,
                        dest='output_file',
                        default = None,
                        action='store',
                        help='Output filename')
    args = parser.parse_args()
    
    
    #This test really should have been done natively in argparse..another time..
    if args.input_file != None and args.output_file != None:
        if(file_exists(args.input_file)):
            fnr_list = read_file(args.input_file,args.output_file)
            fagpersons = get_accounts(fnr_list)
            write_to_file(fagpersons,args.output_file)
        else:
            # input file does not exist. print error message and exit
            eprint("file :%s does not exist. Exiting.." % args.input_file)
    else:
        # 
        parser.print_help(sys.stderr)


#
# Kickstart main function
#
if __name__ == '__main__':
    main()