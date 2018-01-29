#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2009 University of Oslo, Norway
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
This program provides simple statistics about new persons created in
Cerebrum.
"""

import sys
import getopt
from mx import DateTime

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.email import sendmail


db = Factory.get('Database')()
constants = Factory.get('Constants')(db)
account = Factory.get('Account')(db)
person = Factory.get('Person')(db)
logger = Factory.get_logger("cronjob")
log_events = [constants.person_create, ]


def get_new_persons(sdate, change_program=None):
    new_persons = []
    for row in db.get_log_events(sdate=sdate, types=log_events,
                                 change_program=change_program):
        logger.debug("New person: %s" % row['subject_entity'])
        new_persons.append(row['subject_entity'])
    return new_persons


def report_new_persons(new_persons):
    report = ["New persons", "", "entity_id  account", "-" * 18]
    for p in new_persons:
        try:
            person.clear()
            person.find(p)
            tmp = "%8s  " % p
            p_account = person.get_primary_account()
            if p_account:
                account.clear()
                account.find(p_account)
                tmp += account.account_name
            report.append(tmp)
        except Errors.NotFoundError:
            logger.error("Couldn't find person %s" % p)
    return '\n'.join(report)


def usage(exitcode=0):
    print """\nUsage: %s [options]

    --help            Prints this message.
    --dryrun          Print report, don't send mail
    --start-date      Start date for events. Default is yesterday
    --change-program  Specify which program that created the person
    --mail-to         Mail recipient
    --mail-from       From header

    'start-date' must be given in standard ISO format, i.e. YYYY-MM-DD.

    """ % (sys.argv[0])
    sys.exit(exitcode)


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hds:c:t:f:",
                                   ["help", "dryrun", "start-date=",
                                    "change-program=", "mail-to=",
                                    "mail-from="])
    except getopt.GetoptError:
        usage(1)

    change_program = None
    mail_to = None
    mail_from = None
    dryrun = False
    sdate = DateTime.now() - 1
    for opt, val in opts:
        if opt in ('-h', '--help',):
            usage()
        if opt in ('-d', '--dryrun',):
            dryrun = True
        elif opt in ('-s', '--start-date',):
            try:
                sdate = DateTime.ISO.ParseDate(val)
            except ValueError:
                logger.error("Incorrect date format")
                usage(exitcode=2)
        elif opt in ('-c', '--change-program',):
            change_program = val
        elif opt in ('-t', '--mail-to',):
            mail_to = val
        elif opt in ('-f', '--mail-from',):
            mail_from = val

    new_persons = get_new_persons(sdate, change_program=change_program)
    if new_persons:
        msg = report_new_persons(new_persons)
        if change_program:
            subject = "New persons from %s since %s" % (change_program, sdate.date)
        else:
            subject = "New persons since %s" % sdate.date
        if mail_to and not dryrun:
            sendmail(mail_to, mail_from, subject, msg)
        else:
            print msg


if __name__ == '__main__':
    main()
