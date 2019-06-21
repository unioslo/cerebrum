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
"""
Generate a list of recently created users without a password.


Format
------
The file contains one user account per line, and contains the owners norwegian
national id, the user account name, and the user account create time: '<fnr>
<uname> <datetime>'. E.g.:

::

    01017000000 olan 2019-01-01 13:00:00


History
-------
This script was previously a part of the old cerebrum_config repository. It was
moved into the main Cerebrum repository, as it was currently in use by ØFK.

The original can be found in cerebrum_config.git, as
'bin/new_accounts_wo_pass.py' at:

  commit e83e053edc03dcd399775fadd9833101637757ef
  Merge: bef67be2 3bfbd8a2
  Date:  Wed Jun 19 16:07:06 2019 +0200
"""

usage_str = """
Usage:
      new_accounts_wo_pass.py [-t | --time]
                              [-f | --file [PATH/]FILENAME]
                              [-h | --help]

      Where:
       -t or --time is an optional argument that is the number of days to go
                    back to in time in order to look for all the accounts that
                    were created after it  but that still didn't get a password
                    set.
                    Default is 180 days.
       -f or --file is an optional argument to dump the output in a file with
                    an explicit or implicit system path pointing to the file.
                    Default is dump the output to stdout.
       -l or --list is an optional argument to narrow down the search to a list
                    of usernames read from a file with an explicit or implicit
                    system path.
       -h or --help shows this message and all the above text and quits.
"""

import sys
import getopt
import mx
from Cerebrum.Utils import Factory
db = Factory.get(b'Database')()
ac = Factory.get(b'Account')(db)
pe = Factory.get(b'Person')(db)
cl = Factory.get('CLConstants')(db)

# Gives usage info or how to use the program and its options and arguments.
def usage(message=None,message2=None):
   if message is not None:
           print >>sys.stderr, "\n%s" % message
   if message2 is not None:
           print >>sys.stdout,"\n\n%s\n" % message2
   print >>sys.stderr, usage_str
# End usage

def main(argv=None):
    argv = sys.argv

    try:
        opts, args = getopt.getopt(argv[1:],
                                   "t:f:l:h",
                                   ["time=", "file=", "list","help",])
    except getopt.GetoptError, error:
          usage(message=error.msg,message2=None)
          return 1

    output_stream = sys.stdout
    time = 180
    accounts_list = []

    for opt, val in opts:
        if opt in ('-f', '--file',):
            try:
                output_stream = open(val, "w")
            except:
                sys.stdout.write("can't open file, writing to console")
        elif opt in ('-t', '--time',):
            try:
                int(val)
            except:
                    error = getopt.GetoptError
                    usage(message=error.msg,message2=None)
                    return 1
            time = int(val)
        elif opt in ('-l', '--list',):
            try:
                accounts_list = open(val, "r").read().splitlines()
            except:
                sys.stdout.write("can't open file with usernames'list, "
                                 "skipping and proceeding without filtering:\n")
        elif opt in ('-h', '--help',):
            usage(message=None,message2=None)
            return 0

    new_accounts_dict = {}
    has_password = set(r['subject_entity']
                        for r in db.get_log_events(types=cl.account_password,
                                                    sdate=(mx.DateTime.now()
                                                                      - time)))

    for r in db.get_log_events(types=cl.account_create, sdate=(mx.DateTime.now()
                                                                       - time)):
        new_accounts_dict[r['subject_entity']]= str(r['tstamp']).split(".")[0]

    for i in has_password:
        try:
            new_accounts_dict.pop(i)
        except:
            continue

    if accounts_list:
        for i in accounts_list:
            try:
                ac.clear()
                pe.clear()
                ac.find_by_name(i)
                pe.find(ac.owner_id)
                if ac.entity_id in new_accounts_dict:
                    output_stream.write((pe.get_external_id())[0][2] + " " + i +
                                                        " " + new_accounts_dict[
                                                        ac.entity_id] +
                                                        "\n")
                else:
                    output_stream.write((pe.get_external_id())[0][2] + " " + i +
                                                        "   Was either not " +
                                                        "created recently or" +
                                                        " did indeed change " +
                                                        "own password\n")
            except:
                continue
    else:
        for i in new_accounts_dict:
            try:
                ac.clear()
                pe.clear()
                ac.find(i)
                pe.find(ac.owner_id)
                output_stream.write((pe.get_external_id())[0][2] + " " +
                                                    ac.account_name + " " +
                                                    new_accounts_dict[i] + "\n")
            except:
                continue

    if output_stream not in (sys.stdout, sys.stderr):
      output_stream.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
