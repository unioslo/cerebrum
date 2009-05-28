#!/usr/bin/python
# -*- coding: iso8859-1 -*-
#
# Copyright 2004 University of Oslo, Norway
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
This script is a UiT specific export script for exporting data to an alias file
"""

import sys
import time
import os
import os.path
import getopt

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory

db=Factory.get('Database')()
co=Factory.get('Constants')(db)
logger_name = cereconf.DEFAULT_LOGGER_TARGET

date = time.localtime()
date_today = "%02d%02d%02d" % (date[0], date[1], date[2])
default_alias_file = os.path.join(cereconf.DUMPDIR,'alias','aliases_%s' % date_today)
default_forward_file = os.path.join(cereconf.CB_SOURCEDATA_PATH, 'ad', 'AD_forward_export.csv')


def usage():
    print """This program exports BAS exchange emails to an alias file. 

The forwarded option allows to export e-mails that are forwarded 
in exhange when the useraccount in BAS has expired (or if the 
account doesn't exist in BAS - but that's a secret).

    Usage: [options]
    -a | --alias-file : export file
    -f | --forwarded : file with e-mails forwarded in exchange
    -l | --logger-name : name of logger target
    -h | --help : this text """   
    sys.exit(1)


def get_aliases():
    """Gets all active email accounts and their active """

    ac = Factory.get('Account')(db)

    # Build email export
    export = []
    logger.info("Retrieving email lists from db")
    emails_list = {}
    emails_list = ac.getdict_uname2mailinfo()

    wanted_domains = [cereconf.NO_MAILBOX_DOMAIN_EMPLOYEES,]

    logger.info("Processing email list")
    for user in emails_list.keys():
        for email in emails_list[user]:
            if email['domain'] in wanted_domains:
                export.append("%s%s\n" % ((email['local_part'] + ':').ljust(30), '@'.join([user, cereconf.EMAIL_DEFAULT_DOMAIN])))

    logger.info("DataCaching finished")
    return export


def get_forwards(existing, forward_file):

    wanted_domains = [cereconf.NO_MAILBOX_DOMAIN_EMPLOYEES,]
    existing = "\n".join(existing)
    forwards = []

    if(0 == os.path.isfile(forward_file)):
        logger.critical("File %s does not exist." % forward_file)
        sys.exit(1)
    else:

        fp = open(forward_file,"r")
        for line in fp:
            if ((line[0] != '\n') or (line[0] != "#")):
                line = line.rstrip()
                uname,email_address = line.split(",")
                try:
                    local_part,domain = email_address.split("@")

                    if not domain in wanted_domains:
                        logger.error("Invalid domain for forwarded e-mail: %s (%s)" % (domain, email_address))
                        continue
                    elif uname not in existing:
                        forwards.append("%s%s\n" % ((uname + ':').ljust(30), '@'.join([uname, cereconf.EMAIL_DEFAULT_DOMAIN])))
                        forwards.append("%s%s\n" % ((local_part + ':').ljust(30), '@'.join([uname, cereconf.EMAIL_DEFAULT_DOMAIN])))
                except:
                    logger.error("Invalid email address for forwarded e-mail: %s" % email_address)
                    continue
        return forwards


def main():
    global logger, logger_name
    
    try:
        opts,args = getopt.getopt(sys.argv[1:],'a:l:f:h',
                                ['alias-file=', 'forwarded=', 'logger-name', 'help'])
    except getopt.GetoptError:
        usage()

    alias_file = default_alias_file
    forward_file = default_forward_file
    
    help = 0
    for opt,val in opts:
        if opt in ('-a','--alias-file'):
            alias_file = val
        if opt in ('-f','--forwarded'):
            forward_file = val
        if opt in ('-l','--logger-name'):
            logger_name = val
        if opt in('-h','--help'):
            usage()

    logger = Factory.get_logger(logger_name)

    # Get aliases from cerebrum
    export = get_aliases()
    # Get additional aliases from exchange forwards
    export.extend(get_forwards(export, forward_file))

    fh=open(alias_file,'w')
    fh.writelines(export)
    fh.close()

if __name__ == '__main__':
    main()

