#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2012 University of Oslo, Norway
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

import sys
import getopt

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.modules.Email import EmailTarget
"""This program reports users that belong to a person, and that has an
IMAP@uio-spread without a primary email address.

    Functions:
        main():
            Parses command line parameters, and calls functions that will fetch
            the data and generate reports.

        get_accounts_wo_primary_email():
            Searches the database for user accounts that belongs to a person,
            has IMAP-spread, but is missing a primary email address.

        get_accounts_with_missing_imap_spr():
            Searches the database for user accounts that belongs to a person,
            DOESN'T have IMAP-spread, but has email target type 'account'.

        gen_html_report():
            Writes a HTML-formatted report to file or filestream.

        group_names_to_gids():
            Finds the group id's of a list of group names

        usage():
            Prints a simple program usage helptext


    The flow of execution looks like:
        main():
            - Parses command line arguments
            - Initializes database connections
            - Runs 'get_accounts_wo_primary_email()'
              OR   'get_accounts_wo_imap_spr()'
            - Runs 'gen_html_report'
            - Close output file handle

        get_accounts_wo_primary_email():
            - Looks up users that are owned by a person, and that has
              IMAP-spread.
            - Look through the list and pick out users without primary 
              email address.
"""


def usage():
    """Prints a usage string for the script."""

    print """Usage:
    %s [Options]

    Generate an HTML formatted report of accounts with IMAP spreads and missing
    primary email addresses. With the --imap_spread option, the script generates 
    an alternate report of users without IMAP spreads, but sill has email target 
    type account.

    Options:
    -o, --output <file>            The file to print the report to. Defaults to 
                                   stdout.
    -i, --include_expired          Include expired accounts.
    -s, --imap_spread              Generate the alternate report.
    -g, --exlude_groups <group(s)> Exclude users with membership in the 
                                   specified groups. Only used in conjunction 
                                   with the --imap_spread option. Comma-separated list.
    """ % sys.argv[0]


def group_names_to_gids(logger, gr, group_names=None):
    """Fetch a list of group-ids from a list of group names.
    
    @param logger:       Logger to use.
    @type  logger:       CerebrumLogger

    @param gr:           Group database connection
    @type  gr:           Cerebrum.Group.Group

    @param group_names:  List of group name strings to process. 
                         Defaults to None. 
    @type  group_names:  List of strings.

    @return List containing the group id of the groups that were found.
    """
    group_ids = []

    if group_names is not None:
        for gname in group_names:
            group = gr.search(name=gname)
            if not group:
                logger.warn('Can\'t find group with name \'%s\'.' % gname)
            if len(group) > 1:
                logger.warn('Ambivalent name, found multiple groups matching \
                             \'%s\'.' % gname) # Wildcard used
            else: 
                group_ids.append(group[0]['group_id'])

    return group_ids


def get_accounts_wo_primary_email(logger, expired=False):
    """Fetch a list of all accounts with a entity_person owner and IMAP-spread.
    
    @param logger:  Logger to use.
    @type  logger:  CerebrumLogger

    @param expired: If True, include expired accounts. Defaults to False.
    @type  expired: bool

    @param exclude: List of group name strings to exclude. Accounts that are
                    members of this group are excluded from the report.
                    Defaults to None. 
    @type  exclude: List of strings

    @return List of account names that is missing a primary email address.
    """ 

    # Database-setup
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)


    # Return-list
    users = []           # All accounts owned by a person
    users_wo_pri = []    # List to contain results
    
    # Fetch account list
    if expired:
        users = ac.search(spread=co.spread_uio_imap, 
                          owner_type=co.entity_person,
                          expire_start=None)
    else:
        users = ac.search(spread=co.spread_uio_imap, 
                          owner_type=co.entity_person)

    for user in users:
    
        # Select the account
        ac.clear()
        try:
            ac.find(user['account_id'])
        except Errors.NotFoundError:
            logger.error('Can\'t find account with id %d' % user['account_id'])
            continue

        try:
            ac.get_primary_mailaddress()
        except Errors.NotFoundError:
            users_wo_pri.append(ac.account_name)

    return users_wo_pri



def get_accounts_with_missing_imap_spr(logger, expired=False, exclude=None):
    """Fetch a list of all accounts with a entity_person owner and IMAP-spread.
    
    @param logger:  Logger to use.
    @type  logger:  CerebrumLogger

    @param expired: If True, include expired accounts. Defaults to False.
    @type  expired: bool

    @param exclude: List of group name strings to exclude. Accounts that are
                    members of this group are excluded from the report.
                    Defaults to None. 
    @type  exclude: List of strings

    @return List of account names that is missing a primary email address.
    """ 

    # Database-setup
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    gr = Factory.get('Group')(db)
    et = EmailTarget(db)

    accounts = []        # All accounts owned by a person
    group_ids = []       # Group id's of the groups to exclude 
    users_wo_imap = []   # List to contain results

    group_ids = group_names_to_gids(logger, gr, exclude)

    # Fetch account list
    if expired:
        accounts = ac.search(owner_type=co.entity_person,
                             expire_start=None)
    else:
        accounts = ac.search(owner_type=co.entity_person)
    
    for account in accounts:
        ac.clear()
        try:
            ac.find(account['account_id'])
        except Errors.NotFoundError, e:
            logger.error('Can\'t find account with id \'%d\'' % 
                         account['account_id'])
            continue

        # Ignore if account is deleted or reserved
        if ac.is_deleted() or ac.is_reserved():
            continue

        # Ignore if account has imap spread
        if co.spread_uio_imap in [row['spread'] for row in ac.get_spread()]:
            continue

        # Check for group membership
        gr.clear()
        is_member = False
        for group_id in group_ids:
            try:
                gr.find(group_id)
                if gr.has_member(ac.entity_id):
                    is_member = True
                    logger.debug('Ignoring %(account)s, member of %(group)s' % 
                                 {"account":ac.account_name, 
                                  "group":gr.group_name})
                    break
            except Errors.NotFoundError, e:
                logger.error('Can\'t find group with id %d' % group_id)
                continue

        if is_member:
            continue

        # Find EmailTarget for account
        et.clear()
        try:
            et.find_by_target_entity(ac.entity_id)
        except Errors.NotFoundError:
            logger.error('No email targets for account with id %d' % 
                         account['account_id'])
            continue


        if et.email_target_type == co.email_target_account:
            users_wo_imap.append(ac.account_name)

    return users_wo_imap


def gen_html_report(output, title, account_names):
    output.write("""<html>
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">
        <title>%s</title>
    </head>
    <body>
    """ % title)
    
    output.write('<h2>%d accounts</h2>\n' % len(account_names))
    output.write('<h3>Usernames</h3>\n')
    output.write('<ul>\n')
    
    for name in account_names:
        output.write('<li>%s</li>\n' % name)

    output.write('</ul>\n</body>\n</html>\n')


def main(argv=None):
    """Main runtime as a function, for invoking the script from other scripts /
    interactive python session.
    
    @param argv: Script args, see 'usage' for details. Defaults to 'sys.argv'
    @type  argv: List of string arguments.
    """

    # Get logger
    logger = Factory.get_logger('cronjob')

    # Default opts
    output = sys.stdout
    expired = False
    noimap = False
    exclude = []

    ## Parse args
    if not argv:
        argv = sys.argv

    try:
        opts, args = getopt.getopt(argv[1:], 
                                   "ieg:so:", 
                                   ["include_expired", "exclude_groups=", 
                                    "imap_spread", "output="])
    except getopt.GetoptError, e:
        logger.error(e)
        usage()
        return 1

    for o, v in opts:
        if o in ('-o', '--output'):
            try:
                output = open(v, 'w')
            except IOError, e:
                logger.error(e)
                sys.exit(1)
        if o in ('-i', '--include_expired'):
            expired = True
        if o in ('-s', '--imap_spread'):
            noimap = True
        if o in ('-g', '--exclude_groups'):
            exclude.extend(v.split(','))


    if exclude and not noimap:
        logger.error('Excluding groups are only permitted in conjunction with \
                     the --imap_spread option')


    # Generate selected report
    if noimap is False:
        logger.info('Start reporting accounts without primary email address')
        accs = get_accounts_wo_primary_email(logger, expired)
        gen_html_report(output, "Accounts without primary email address", accs)
        logger.info('Done reporting accounts without primary email address')
    else:
        logger.info('Start reporting accounts without IMAP spread')
        accs = get_accounts_with_missing_imap_spr(logger, expired, exclude)
        gen_html_report(output, "Accounts without IMAP spread", accs)
        logger.info('Done reporting accounts without IMAP spread')

    # Close output if we explicitly opened a file for writing
    if not output is sys.stdout:
        output.close()


# If started as a program
if __name__ == "__main__":
    sys.exit(main())

