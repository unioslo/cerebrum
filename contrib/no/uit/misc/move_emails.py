#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2002 - 2019 University of Oslo, Norway
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
This script moves all e-mailaddresses in a given domain from one account to
another. It reads data exported from our HR system PAGA from a simple CSV file.
"""

import argparse
import sys
import logging

import cereconf
import Cerebrum.logutils
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.Utils import Factory
from Cerebrum import Errors

logger = logging.getLogger(__name__)

DEFAULT_MAIL_DOMAIN = cereconf.NO_MAILBOX_DOMAIN_EMPLOYEES


def process_change(from_acc, to_acc, maildomain, primary, db):
    # Init
    ac = Factory.get('Account')(db)
    primary_id = None

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
        maildomain_id = db.query_1(
            """
            SELECT domain_id 
            FROM [:table schema=cerebrum name=email_domain]
            WHERE domain = :domain
            """,
            {'domain': maildomain, }
        )
    except Errors.TooManyRowsError:
        raise Errors.TooManyRowsError
    except Errors.NotFoundError:
        logger.error("Maildomain not found: %s" % maildomain)
        sys.exit(1)

    # Get email target for account that shall receive new accounts
    try:
        acc_target_id = db.query_1(
            """
            SELECT target_id
            FROM [:table schema=cerebrum name=email_target]
            WHERE target_entity_id = :to_id
            """,
            {'to_id': to_id, }
        )
    except Errors.TooManyRowsError:
        raise Errors.TooManyRowsError
    except Errors.NotFoundError:
        logger.error("E-mailtarget not found for %s" % to_acc)
        sys.exit(1)

    # If primary set to true, get address_id of primary address for from_acc
    #    - only gets the ID successfully if the primary is part of the current
    #    domain
    if primary:
        try:
            primary_id = db.query_1(
                """
                SELECT epa.address_id
                FROM 
                    [:table schema=cerebrum name=email_primary_address] AS epa,
                    [:table schema=cerebrum name=email_target] AS et,
                    [:table schema=cerebrum name=email_address] AS ea
                WHERE
                    et.target_entity_id = :from_id AND
                    et.target_id = epa.target_id AND
                    epa.address_id = ea.address_id AND
                    ea.domain_id = :domain_id
                """,
                {
                    'from_id': from_id,
                    'domain_id': maildomain_id
                }
            )
        except Errors.TooManyRowsError:
            raise Errors.TooManyRowsError
        except Errors.NotFoundError:
            logger.warn("Primary address not found for %s in domain %s" % (
                from_acc, maildomain))
            primary_id = None

    # Delete primary address for from_acc, if this is among the addresses to be
    # moved
    logger.info("Deleting primary email from current owner")
    db.execute(
        """
        DELETE FROM [:table schema=cerebrum name=email_primary_address]
        WHERE address_id IN (
            SELECT b.address_id
            FROM
                [:table schema=cerebrum name=email_target] a,
                [:table schema=cerebrum name=email_address] b
            WHERE
                a.target_id = b.target_id AND
                b.domain_id = :maildomain_id AND
                a.target_entity_id = :from_id
            )
        """,
        {
            'maildomain_id': maildomain_id,
            'from_id': from_id
        }
    )

    # Move emails from one account to the other
    logger.info("Moving emails")
    db.execute(
        """
        UPDATE [:table schema=cerebrum name=email_address]
        SET target_id = :acc_target_id
        WHERE address_id IN (
            SELECT b.address_id
            FROM
                [:table schema=cerebrum name=email_target] a,
                [:table schema=cerebrum name=email_address] b
            WHERE
                a.target_id = b.target_id AND
                b.domain_id = :maildomain_id AND
                a.target_entity_id = :from_id
        )
        """,
        {
            'acc_target_id': acc_target_id,
            'maildomain_id': maildomain_id,
            'from_id': from_id
        }
    )

    # Set new primary address if primary_id address is OK 
    if primary_id is not None:
        logger.info("Setting primary address for new owner %s" % to_acc)
        db.execute(
            """
            UPDATE [:table schema=cerebrum name=email_primary_address]
            SET address_id = :primary_id
            WHERE target_id = :acc_target_id
            """,
            {
                'primary_id': primary_id,
                'acc_target_id': acc_target_id
            }
        )

    # Update ad_email table if current domain is the ad_email domain
    if primary and DEFAULT_MAIL_DOMAIN == maildomain:
        try:
            # Only attempt to update ad_emailtable if the from acc has an
            # entry here
            db.query_1(
                """
                SELECT account_name
                FROM [:table schema=cerebrum name=ad_email]
                WHERE account_name = :from_acc
                """,
                {'from_acc': from_acc, }
            )
            logger.info(
                "Updating ad_email table from %s to %s" % (from_acc, to_acc))
            db.execute(
                """
                DELETE FROM ad_email 
                WHERE account_name = :to_acc
                """,
                {'to_acc': to_acc}
            )
            db.execute(
                """
                UPDATE ad_email 
                SET account_name = :to_acc 
                WHERE account_name = :from_acc
                """,
                {
                    'to_acc': to_acc,
                    'from_acc': from_acc
                }
            )
        except Errors.TooManyRowsError:
            raise Errors.TooManyRowsError
        except Errors.NotFoundError:
            logger.info("Couldn't update ad_email table from %s to %s" % (
                from_acc, to_acc))
    elif DEFAULT_MAIL_DOMAIN == maildomain:
        logger.info("Deleting ad_email table for %s" % from_acc)
        db.execute(
            """
            DELETE FROM ad_email 
            WHERE account_name = :from_acc
            """,
            {'from_acc': from_acc}
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-f', '--from_acc',
        required=True,
        help='account name to move e-mailaddresses from'
    )
    parser.add_argument(
        '-t', '--to_acc',
        required=True,
        help='account name to move e-mailaddresses to'
    )
    parser.add_argument(
        '-m', '--maildomain',
        default=DEFAULT_MAIL_DOMAIN,
        help='maildomain to process. Defaults to {}'.format(
            DEFAULT_MAIL_DOMAIN)
    )
    parser.add_argument(
        '-p', '--primary',
        action='store_true',
        help="set from's primary address as to's primary address"
    )
    parser = add_commit_args(parser, default=True)

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()
    Cerebrum.logutils.autoconf('console', args)

    if args.from_acc == args.to_acc:
        logger.error('Arguments "from" and "to" are not allowed to be the same'
                     ' value!')
        sys.exit()

    logger.info("Starting to process")
    db = Factory.get('Database')()
    process_change(args.from_acc, args.to_acc, args.maildomain, args.primary,
                   db)

    if args.commit:
        db.commit()
        logger.info("Committing all changes to DB")
    else:
        db.rollback()
        logger.info("Dryrun, rollback changes")


if __name__ == '__main__':
    main()
