#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2011 University of Oslo, Norway
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

"""This script is a tool used to check active accounts in Cerebrum.
Check and list summary or detail information of the Cerebrum users and
active accounts with specific input numbers. Check the number of the
active Cerebrum accounts for persons and send email as alarm when
the number is greater than allowed.
"""
import sys
import getopt
from Cerebrum.Utils import Factory
from Cerebrum.utils.email import sendmail

logger = Factory.get_logger("console")
db = Factory.get('Database')()
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)
pr = Factory.get('Person')(db)


def usage(msg=None, exit_status=0):
    if msg is not None:
        logger.debug(msg)
    print """Usage: %s [options]

    -s, --summary   This option is default. List the overview
                    information for the active accounts in Cerebrum.

    -d, --detail    List the informaiton of personal_id and account_ids
                    for each person.

    --min [Nr1]     The default vaule for Nr1 is 1. Check the persons
                    who have more than Nr1 active accounts in Cerebrum.

    --max [Nr2]     Check the persons who have less than Nr2 active
                    accounts in Cerebrum.

    -h, --help      See this help infomation and exit.

    """ % sys.argv[0]
    sys.exit(exit_status)


def accountNr(minimum, maxmum, accs):
    """
    Compare the number of accounts in the 'accs' list for each person
    with the input option number 'minimum' and 'maxmum'.
    """
    if maxmum:
        if len(accs) >= minimum and len(accs) <= maxmum:
            return True
        else:
            return False
    elif not maxmum:
        if len(accs) >= minimum:
            return True
        else:
            return False


def checkACaccount(minimum,maxmum,detail,report_type,stream):
    """
    Check the accounts for each person and report the results into
    print or file. Return the person_ids whose number of accounts is
    between 'minimum' and 'maxmum'.  'detail' controls if report the
    account_names for each person_id.  'report_type' shows the way of
    reporting the checking results (print on screen, write into a
    file, send email). 'stream' is the output file stream for writting
    data.
    """
    logger.info("Checking active accounts of Cerebrum in range (%s,%s)" %(minimum,maxmum))
    nr_person = 0
    persons = ''
    for row in pr.list_persons():
        pr.clear()
        pr.find(row['person_id'])  
        accs = pr.get_accounts()
        call = accountNr(minimum,maxmum,accs) # judge the number of accounts for this person
        if call:
            length = len(accs)
            nr_person += 1
            persons += "\n%s" % str(row['person_id'])
            if detail:
                acc = ''
                for rowA in accs:
                    ac.clear()
                    ac.find(rowA['account_id']) 
                    acc += ac.account_name
                    acc += " "
                if report_type == 'mail':
                    continue
                elif report_type == 'screen':
                    print "Person %s has %s accounts: %s" % (row['person_id'], length, acc)  
                elif report_type == 'file':
                    stream.write("%s\t\t%s\t\t%s\n" % (row['person_id'], length, acc)) 
    if not maxmum:
        msg = "%s persons have at least  %s active accounts" % (nr_person, minimum)
        logger.debug(msg)
    elif maxmum:
        msg = "%s persons have active accounts between %s and %s" % (nr_person, minimum, maxmum)
        logger.debug(msg)
    if report_type == 'mail':
        pass
    elif report_type == 'screen':                    
        print msg
    elif report_type == 'file':
        stream.write("\n%s\n\n" % msg)
    logger.info("Checking active accounts in range (%s,%s) - done" %(minimum,maxmum))
    return persons


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hsdf:',
                                   ['help', 'summary', 'detail',
                                    'min=', 'max=',
                                    'mail-to=', 'mail-from=',
                                    'file='])
    except getopt.GetoptError:
        usage("Argument error!", 1)

    detail = False
    minimum = 1  
    maxmum = None
    report_type = 'screen'
    outputstream = sys.stdout
    mail_to = None
    mail_from = None
    persons = 'person_id'
    
    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage()
        elif opt in ('-s', '--summary'):
            pass
        elif opt in ('-d', '--detail'):
            detail = True
        elif opt in ('--min'):
            minimum = int(val)
            if minimum < 0:
                usage("Error: the value of parameter --min should be at least 1", 2)
        elif opt in ('--max'):
            maxmum = int(val)
            if maxmum < 0:
                usage("Error: the value of parameter --max should be at least 1", 3)
        elif opt in ('-f', '--file'):
            report_type = 'file'
            outputstream = open(val, 'w')
            outputstream.write("==== Results of checking active accounts in Cerebrum ====\n")
            outputstream.write("person_id\tNr_accounts\taccount_names\n")
        elif opt in ('--mail-to'):
            report_type = 'mail'
            mail_to = val
        elif opt in ('--mail-from'):
            mail_from = val
        else:
            usage("Error: Unknown parameter '%s'" % opt, 4)

    persons += checkACaccount(minimum,maxmum,detail,report_type,outputstream)
          
    if mail_to:
        count = persons.count("\n")
        subject = "Warning: these following %s persons have more than %s active accounts." % (count,minimum)
        sendmail(mail_to, mail_from, subject, persons)


if __name__ == '__main__':
    main()
