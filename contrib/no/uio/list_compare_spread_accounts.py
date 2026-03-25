#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2026 University of Oslo, Norway""
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

__doc__ = """

This script generates a list of all user accounts with a specific spread along
with the person affiliations and their organisation numbers (could be sent by
email as well).
If provided a list of users in input it would dump the same list in output but
with a different ordering and an extra column confirming whether the user has
this spread or not.
If used with the -p or --person switch this script returns a list of primary
users for persons that have the spread in question on the person object level in
the Cerebrum database.

Usage:
      list_compare_spread_accounts.py (-s|--spread     CONSTANT STRING)
                                      [-i|--input-file [PATH/]FILENAME]
                                      [-m|--mail       [PATH/]FILENAME]
                                      [-f|--file       [PATH/]FILENAME]
                                      [-p|--person]
                                      [-h|--help]

      Where:
       -s or --spread     is a mandatory argument to specify the spread used as
                          a selection criteria, e.g. spread_uio_ad_account .
       -i or --input-file is an optional argument that should be a file and the
                          path to it, that file should contain a list of user
                          names (one user name per line), this list is taken
                          and is returned as output where every user name that
                          has this spread is returned with extra comments on the
                          line detailing the affiliations with OUs for that user
                          on the person level as well as saying that he/she has
                          that spread.
       -f or --file       is an optional argument to dump the output in a file
                          with path, otherwise the output is dumped to the logs.
       -m or --mail       is an optional argument to point to the mail template
                          file with the recipients that will be mailed the
                          output of the script.
       -p or --person     is an optional argument to force looking for a spread
                          on the person object level.
       -h or --help       shows this message and all the above text and quits.
"""

import sys
import getopt
import smtplib
import email

from Cerebrum import Utils
from Cerebrum.utils.email import sendmail
from Cerebrum import Errors

logger   = Utils.Factory.get_logger("cronjob")
database = Utils.Factory.get('Database')()
person   = Utils.Factory.get('Person')(database)
account  = Utils.Factory.get('Account')(database)
co       = Utils.Factory.get('Constants')(database)
ou       = Utils.Factory.get('OU')(database)

list_target     =[]
stedkoder       = ou.get_stedkoder()
sted_koder      = {}

for k in stedkoder:
  sted_koder[k[0]]= ("%02d" %k[3]) + ("%02d" %k[4]) + ("%02d" %k[5])

# Core functions

# Generate list of users with spread
def generate_list_spread_users(input_spread):
    # Loop through all the person ID's
    for pid in dump_person_ids():
        # Check if the spread exists for the user accounts for every person and
        # push the user account in the list "list_target" if its the case.
        try:
            a = account.list_accounts_by_type(person_id=pid,
                                account_spread=int(getattr(co, input_spread)))
            generate_account_name(a,pid)
        except:
            continue
# End generate list of users with spread

# Generate list of primary users for the persons with the spread
def generate_list_person_spread_users(input_spread):
    for pid in dump_person_ids():
        # Check if the spread exists for the person and then
        # push its first user account in the list "list_target" if its the case.
        if person.get_spread():
         for k in person.get_spread():
             if int(getattr(co, input_spread)) in k:
              try:
               a = account.list_accounts_by_owner_id(pid)
               generate_account_name(a,pid)
              except:
               continue
# End generate list of primary users for persons with spread

# End core functions

# List person ID's function
def dump_person_ids():
    # Loop through all the person entities
    for p in person.list_persons():
        pid = p["person_id"]
        # Test if initialisation of person succeeds and person exists
        try:
            person.clear()
            person.find(pid)
        except Errors.NotFoundError:
               logger.warn("list_persons() reported a person, but person.find()"
                           "did not find it")
               continue
        yield pid
# End list person ID's function

# Generate account names function from account IDs dictionnary and push the 1st
# account name in a list along with all the affiliations and OUs for the person
def generate_account_name(listPersonAccounts=[],personid=None):
        account.clear()
        try:
            account.find(listPersonAccounts[0]['account_id'])
            b = account.account_name
            affs = ''
            for row in person.list_affiliations(person_id=personid):
                aff = str(co.PersonAffStatus(row['status'])) + '@' + \
                        sted_koder[row['ou_id']]
                affs = '%s \t %s' % (affs, aff)
            re = '%s \t %s' % (b, affs)
        except:
              pass
        if b:
             list_target.append(re)
# End generate account names function

# Email sending function
def send_mail(mail_to, mail_from, subject, body, mail_cc=None):
    """Function for sending the output as email.
    """
    try:
        sendmail(mail_to, mail_from, subject, body, cc=mail_cc)
    except smtplib.SMTPRecipientsRefused as e:
        failed_recipients = e.recipients
        logger.error("Failed to send report <%d>", len(failed_recipients))
        for email, condition in failed_recipients.iteritems():
            logger.error("Failed to send report: %s", condition)
    except smtplib.SMTPException as msg:
        logger.error("Error sending to %s: %s" % (mail_to, msg))
        return False
    return True
# End email sending function

# Gives usage info or how to use the program and its options and arguments.
def usage(message=None,message2=None):
   if message is not None:
           print("\n%s" % message, file=sys.stderr)
   if message2 is not None:
           print("\n\n%s\n" % message2, file=sys.stdout)
   print(__doc__, file=sys.stderr)
# End usage

# Main function

def main(argv=None):
    argv = sys.argv
    try:
        opts, args = getopt.getopt(argv[1:],
                                   "s:i:f:m:ph",
                                   ["spread=","input-file=","file=","mail=",
                                    "person","help",])
    except getopt.GetoptError as error:
          usage(message=error.msg,message2=None)
          return 1

    output_stream = sys.stdout
    filein     = None
    spread     = None
    email_info = None
    person_spd = False

#   Trap the arguments and switches given to the script from the command line
    for opt, val in opts:
        if opt in ('-s', '--spread',):
            try:
                spread = str(val)
            except:
                logger.error("can't assign the spread value, exiting.")
                return 1
        elif opt in ('-f', '--file',):
            try:
                output_stream = open(val, "w")
            except:
                logger.error("can't open file, writing to console")
        elif opt in ('-i', '--input-file',):
            try:
                filein = open(val, "r")
            except:
                logger.error("can't open file: "+val+" continuing without")
        elif opt in ('-m','--mail'):
            try:
                f = open(val)
                msg = email.message_from_file(f)
                f.close()
                email_info = {
                    'Subject': msg['Subject'],
                    'To': msg['To'],
                    'From': msg['From'],
                    'Cc': msg['Cc'],
                    'Body': msg.get_payload(decode=1)
                }
            except IOError as e:
                logger.error('Mail body file: \'%s\'' % e)
                sys.exit(2)
        elif opt in ('-p', '--person',):
            person_spd = True
        elif opt in ('-h', '--help',):
            usage(message=None,message2=None)
            return 0

#   Code execution
    if hasattr(co, spread):
        if person_spd:
            generate_list_person_spread_users(spread)
        else:
            generate_list_spread_users(spread)
    else:
       logger.error("Wrong spread, or a spread value is not provided, look in "
                    "the database for valid values.")
       usage(message=None,message2=None)
       return 1
    if email_info:
        body = email_info['Body']
        d = ('\n'.join(map(str, list_target)))
        body = body.replace('${REPORT}', d)
        send_mail(email_info['To'], email_info['From'], email_info['Subject'],
                  body, email_info['Cc'])
        logger.info("Email sent to " + email_info['To'] + " and " +
                                                  email_info['Cc'] + " (copy).")
    if filein:
        c = filein.read().splitlines()
        for i in list_target:
            e = (i.split(' \t '))[0]
            if e in c:
                h = c.index(e)
                c.pop(h)
                c.insert(h, i + " has spread: " + spread)
        for k in c:
            output_stream.write(k +"\n")
    else:
        for j in list_target:
            output_stream.write(j+"\n")
    if output_stream not in (sys.stdout, sys.stderr):
      output_stream.close()
    return 0

# End main


if __name__ == "__main__":
    sys.exit(main())
