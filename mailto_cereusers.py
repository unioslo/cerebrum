#! /usr/bin/env python
# -*- coding: iso8859-1 -*-
"""This script sends email to users in cerebrum based on groups and accounts."""


import cerebrum_path
import cereconf

import sys
import getopt
import mx

from Cerebrum import Entity
from Cerebrum import Utils
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.Constants import Constants

logger = db = default_logger = None

db = Factory.get('Database')()
default_logger = 'console'



def get_members_from_group(group_object, account_object, group_name, member_type_accepted):
    group_object.clear()
    gr = group_object
    ac = account_object

    tmp_members = []

    try:
        gr.find_by_name(group_name)
        logger.info("Group %s found." % group_name)
    except Exception:
        logger.warn("Group %s not found." % group_name)
        return []
 
    raw_list = gr.list_members()[0]
    for member in raw_list:
        member_type = 0 # member tuple index for member type
        member_id = 1 # member tuple index for member id

        if member[member_type] == member_type_accepted:
            ac.clear()
            try:
                ac.find(member[member_id])
            except Exception:
                logger.warn("Member of group %s is not a valid account (%s). Skipping this account!" % group_name, member[member_id])
                continue
            
            tmp_members.append(ac.get_account_name())

    return tmp_members




def main():
    global logger, db, default_logger

    logger = Factory.get_logger(default_logger)
    
    try:
        opts,args = getopt.getopt(sys.argv[1:], \
                                  'g:G:a:A:E:s:d',\
                                  ['group=', 'group_file=', 'account=', 'account_file=', 'email_file=', 'sender=', 'dryrun'])
    except getopt.GetoptError:
        usage()

    group = group_file = account = account_file = email_file = sender = None
    dryrun = False

    for opt,val in opts:
        if opt in('-g','--group'):
            group = val
        elif opt in('-G','--group_file'):
            group_file = val
        elif opt in('-a','--account'):
            account = val
        elif opt in('-A','--account_file'):
            account_file = val
        elif opt in('-E','--email_file'):
            email_file = val
        elif opt in('-s','--sender'):
            sender = val
        elif opt in('-d','--dryrun'):
            dryrun = True

    if email_file is None:
        logger.error("A filename with email contents must be given")
        usage()
    elif group is None and group_file is None and account is None and account_file is None:
        logger.error("At least one group or account must be indicated.")
        usage()
    elif sender is None:
        logger.error("A sender email must be specified")
        usage()


    # Processing e-mail file
    try:
        f = open(email_file, 'r')
        subject = f.readline().strip()
        body = ''
        for char in f:
            body = body + char
        f.close()
        
        logger.info("File %s containing email content read. \n   *** EMAIL ***\nSUBJECT\n%s\n\nBODY\n%s   *************" %
                    (file, subject, body))
    except Exception:
        logger.error("File %s not found." % email_file)
        sys.exit(1)


    # Preparing to get email accounts
    gr = Factory.get('Group')(db)
    ac = Factory.get('Account')(db)
    co = Factory.get('Constants')(db)

    # Only mail to account members of groups
    account_type_id = co.entity_account

    # List of accounts to send email to
    accounts_list = []


    # Process groups from command line
    if group is not None:
        groups = group.split(",")
        for group in groups:
            members = get_members_from_group(gr, ac,  group, account_type_id)
            accounts_list.extend(members)


    # Process groups from file
    if group_file is not None:
        try:
            f = open(group_file, 'r')
            for line in f:
                members = get_members_from_group(gr, ac, line.strip(), account_type_id)
                accounts_list.extend(members)
            f.close()
        except Exception, msg:
            logger.error("File %s not found. Error: %s" % (group_file, msg))


    # Process accounts from command line
    if account is not None:
        accounts = account.split(",")
        for account in accounts:
            accounts_list.append(account)


    # Process accounts from file
    if account_file is not None:
        try:
            f = open(account_file, 'r')
            for line in f:
                accounts_list.append(line.strip())
            f.close()
        except Exception:
            logger.error("File %s not found" % account_file)


    to_list = ''
    logger.info("Building list of recipients....")

    # Skip repeated accounts and map accounts to mail addresses...
    accounts_list.sort()
    previous = ''
    for member in accounts_list:
        if member == previous:
            continue
        previous = member
        
        ac.clear()
        try:
            ac.find_by_name(member)
        except Exception:
            logger.warn("Invalid member account: %s. Skipping this one!" % member)
            continue
            
        try:
            email = ac.get_primary_mailaddress()
            if to_list != '':
                to_list = to_list + ','
            to_list = to_list + email
        except Errors.NotFoundError:
            logger.warn("Primary email address not found for %s!" % member)

    if to_list == '':
        logger.warn("No recipients on the list. Email will not be sent.")
    else:
        logger.info("List of recipients:\n   *************\n%s\n   *************" % to_list)
    
        if not dryrun:
            logger.info("Sending email...")
            Utils.sendmail(to_list, sender, subject, body, cc=sender, charset='iso-8859-1', debug=False)
        else:
            logger.info("Dryrun. Not sending email.")

    logger.info("Finished")

    
    

def usage():
    print """
    usage:: python mailto_cereusers.py 
    -g | --group : group, or comma separated list with groups to send email to
    -G | --group_file: file with one group on each line
    -a | --account : account, or comma separated list with accounts to send email to
    -A | --account_file: file with one account on each line
    -E | --email_file  : file with email contents. Subject in first line, body in the rest of the file
    -s | --sender: sender's email
    -d | --dryrun: will not send out email, only show to whom emails would be sent, and email content
    """
    sys.exit(1)



if __name__=='__main__':
    main()
