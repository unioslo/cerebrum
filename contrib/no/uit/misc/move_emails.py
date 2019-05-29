#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

#
# This script reads data exported from our HR system PAGA.
# It is a simple CSV file.
#

import getopt
import sys
import os
import mx.DateTime

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors

# Init
db = Factory.get('Database')()
ac = Factory.get('Account')(db)
pe = Factory.get('Person')(db)
co = Factory.get('Constants')(db)

logger = Factory.get_logger("console")

default_maildomain = cereconf.NO_MAILBOX_DOMAIN_EMPLOYEES


def process_change(from_acc, to_acc, maildomain, primary):
    from_id = to_id = maildomain_id = primary_id = acc_target_id = None

    # Validate and get acc_id
    try:
        ac.clear()
        ac.find_by_name(from_acc)
        from_id = ac.entity_id
    except Errors.NotFoundError:
        logger.error("Account to move e-mails from not found: %s" % from_acc)
        sys.exit(1)

    # Validate and get acc_id
    try:
        ac.clear()
        ac.find_by_name(to_acc)
        to_id = ac.entity_id
    except Errors.NotFoundError:
        logger.error("Account to move e-mails to not found: %s" % to_acc)
        sys.exit(1)

    # Validate ang get maildomain_id
    try:
        maildomain_id = db.query_1("""SELECT domain_id
                                      FROM [:table schema=cerebrum name=email_domain]
                                      WHERE domain = :domain""",
                                   {'domain': maildomain, })
    except Errors.TooManyRowsError:
        raise Errors.TooManyRowsError
    except Errors.NotFoundError:
        logger.error("Maildomain not found: %s" % maildomain)
        sys.exit(1)

    # Get email target for account that shall receive new accounts
    try:
        acc_target_id = db.query_1("""SELECT target_id
                                      FROM [:table schema=cerebrum name=email_target]
                                      WHERE target_entity_id = :to_id""",
                                   {'to_id': to_id, })
    except Errors.TooManyRowsError:
        raise Errors.TooManyRowsError
    except Errors.NotFoundError:
        logger.error("E-mailtarget not found for %s" % to_acc)
        sys.exit(1)

    # If primary set to true, get address_id of primary address for from_acc
    #    - only gets the ID successfully if the primary is part of the current domain
    if primary:
        try:
            primary_id = db.query_1("""
                SELECT 
                    epa.address_id
                FROM 
                    [:table schema=cerebrum name=email_primary_address] AS epa,
                    [:table schema=cerebrum name=email_target] AS et,
                    [:table schema=cerebrum name=email_address] AS ea
                WHERE
                    et.target_entity_id = :from_id AND
                    et.target_id = epa.target_id AND
                    epa.address_id = ea.address_id AND
                    ea.domain_id = :domain_id""",
                                    {'from_id': from_id,
                                     'domain_id': maildomain_id})
        except Errors.TooManyRowsError:
            raise Errors.TooManyRowsError
        except Errors.NotFoundError:
            logger.warn("Primary address not found for %s in domain %s" % (
            from_acc, maildomain))
            primary_id = None

    # Delete primary address for from_acc, if this is among the addresses to be moved
    logger.info("Deleting primary email from current owner")
    db.execute("""
        DELETE FROM
            [:table schema=cerebrum name=email_primary_address]
        WHERE
            address_id IN (
                     SELECT
                         b.address_id
                     FROM
                         [:table schema=cerebrum name=email_target] a,
                         [:table schema=cerebrum name=email_address] b
                     WHERE
                         a.target_id = b.target_id AND
                         b.domain_id = :maildomain_id AND
                         a.target_entity_id = :from_id
            )
    """, {'maildomain_id': maildomain_id, 'from_id': from_id})

    # Move emails from one account to the other
    logger.info("Moving emails")
    db.execute("""
        UPDATE
            [:table schema=cerebrum name=email_address]
        SET
            target_id = :acc_target_id
        WHERE
            address_id IN (
                     SELECT
                         b.address_id
                     FROM
                         [:table schema=cerebrum name=email_target] a,
                         [:table schema=cerebrum name=email_address] b
                     WHERE
                         a.target_id = b.target_id AND
                         b.domain_id = :maildomain_id AND
                         a.target_entity_id = :from_id
            )
    """, {'acc_target_id': acc_target_id, 'maildomain_id': maildomain_id,
          'from_id': from_id})

    # Set new primary address if primary_id address is OK 
    if primary_id is not None:
        logger.info("Setting primary address for new owner %s" % to_acc)
        db.execute("""
            UPDATE
                [:table schema=cerebrum name=email_primary_address]
            SET
                address_id = :primary_id
            WHERE
                target_id = :acc_target_id""",
                   {'primary_id': primary_id, 'acc_target_id': acc_target_id});

    # Update ad_email table if current domain is the ad_email domain
    if primary and default_maildomain == maildomain:
        try:
            # Only attempt to update ad_emailtable if the from acc has an entry here
            db.query_1("""SELECT account_name
                          FROM [:table schema=cerebrum name=ad_email]
                          WHERE account_name = :from_acc""",
                       {'from_acc': from_acc, })
            logger.info(
                "Updating ad_email table from %s to %s" % (from_acc, to_acc))
            db.execute("""DELETE FROM ad_email WHERE account_name = :to_acc""",
                       {'to_acc': to_acc});
            db.execute(
                """UPDATE ad_email SET account_name = :to_acc WHERE account_name = :from_acc""",
                {'to_acc': to_acc, 'from_acc': from_acc});
        except Errors.TooManyRowsError:
            raise Errors.TooManyRowsError
        except Errors.NotFoundError:
            logger.info("Couldn't update ad_email table from %s to %s" % (
            from_acc, to_acc))
    elif default_maildomain == maildomain:
        logger.info("Deleting ad_email table for %s" % from_acc)
        db.execute("""DELETE FROM ad_email WHERE account_name = :from_acc""",
                   {'from_acc': from_acc});


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'f:t:pm:d',
                                   ['from=', 'to=', 'primary', 'maildomain=',
                                    'dryrun'])
    except getopt.GetoptError:
        usage(1)

    from_acc = to_acc = maildomain = None
    dryrun = primary = False
    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage()
        elif opt in ('-f', '--from'):
            from_acc = val
        elif opt in ('-t', '--to'):
            to_acc = val
        elif opt in ('-m', '--maildomain'):
            maildomain = val
        elif opt in ('-p', '--primary'):
            primary = True
        elif opt in ('-d', '--dryrun'):
            dryrun = True

    if maildomain is None:
        maildomain = default_maildomain

    if from_acc is None or to_acc is None or from_acc == to_acc:
        usage(1)

    logger.info("Starting to process")
    process_change(from_acc, to_acc, maildomain, primary)

    if (dryrun):
        db.rollback()
        logger.info("Dryrun, rollback changes")
    else:
        db.commit()
        logger.info("Committing all changes to DB")


def usage(exit_code=0):
    print """This script moves all e-mailaddresses in a given domain from one account to another
    -f | --from:       account name to move e-mailaddresses from
    -t | --to:         account name to move e-mailaddresses to
    -m | --maildomain: maildomain to process. Defaults to %s
    -p | --primary:    set from's primary address as to's primary address
    -d | --dryrun:     roll back changes in the end
    -h | --help:       this help message""" % (default_maildomain)

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
