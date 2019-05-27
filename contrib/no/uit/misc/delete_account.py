#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2017-2019 University of Tromso, Norway
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

import argparse
import logging
import time

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.legacy_users import LegacyUsers
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.utils.email import sendmail


logger = logging.getLogger(__name__)


def clear_bofhd_data(db, entity_id):
    """
    Remove bofhd state for a given entity.

    TODO: Refactor bofhd_session to make that code re-usable.
    """
    # need to delete any entries in bofhd_session_state
    # for this account_id before deleting other things
    stmt = """
    DELETE FROM bofhd_session
    WHERE account_id = :account_id
    """
    binds = {'account_id': entity_id}
    db.execute(stmt, binds)


def delete_account(db, account_id, target_id=None, dryrun=False):
    mailto_rt = False
    mailto_ad = False
    logger.info("Processing account_id=%r", account_id)

    co = Factory.get('Constants')(db)
    pe = Factory.get('Person')(db)
    ac = Factory.get('Account')(db)
    lu = LegacyUsers(db)
    try:
        ac.find(account_id)
    except Errors.NotFoundError as m:
        logger.error("No account with account_id=%r: %s", account_id, m)
        return

    pe.find(ac.owner_id)

    legacy_info = {}
    legacy_info['username'] = ac.account_name
    try:
        legacy_info['ssn'] = pe.get_external_id(
            id_type=co.externalid_fodselsnr)[0]['external_id']
    except Exception:
        legacy_info['ssn'] = None
    legacy_info['source'] = 'MANUELL'
    legacy_info['type'] = 'P'
    legacy_info['comment'] = ('%s - Deleted by delete_account.py script.' %
                              time.strftime('%Y%m%d'))
    # Will try to get primary account for SSN later on...
    legacy_info['name'] = pe.get_name(co.system_cached, co.name_full)

    try:
        for spread in ac.get_spread():
            if spread['spread'] == co.spread_uit_ad_account:
                mailto_ad = True
                break
    except Exception:
        pass

    clear_bofhd_data(db, account_id)

    # TODO: All this really should be removed by doing ac.terminate()
    delete_tables = [
        ('change_log', 'change_by'),
        ('entity_name', 'entity_id'),
        ('account_home', 'account_id'),
        ('account_type', 'account_id'),
        ('account_authentication', 'account_id'),
        ('posix_user', 'account_id'),
        ('homedir', 'account_id'),
        ('group_member', 'member_id'),
        ('bofhd_session', 'account_id'),
        ('account_info', 'account_id'),
        ('spread_expire', 'entity_id'),
        ('entity_spread', 'entity_id'),
        ('entity_quarantine', 'entity_id'),
        ('entity_trait', 'entity_id'),
        ('entity_contact_info', 'entity_id'),
        ('mailq', 'entity_id'),
        ('entity_info', 'entity_id'),
        ('entity_contact_info', 'entity_id'),
    ]

    delete_mail_tables = [
        ('mailq', 'entity_id'),
        ('email_forward', 'target_id'),
        ('email_primary_address', 'target_id'),
        ('email_address', 'target_id'),
        ('email_target', 'target_id'),
    ]

    if target_id is not None:
        binds = {'value': target_id}
        for key, value in delete_mail_tables:
            stmt = """
            DELETE FROM {table}
            WHERE {column} = :value
            """.format(table=key, column=value)
            db.execute(stmt, binds)

    for key, value in delete_tables:
        binds = {'value': account_id}
        stmt = """
        DELETE FROM {table}
        WHERE {column} = :value
        """.format(table=key, column=value)
        db.execute(stmt, binds)

    # Done deleting, now writing legacy info after trying to find (new)
    # primary account for person
    try:
        ac.clear()
        aux = pe.entity_id
        pe.clear()
        pe.find(aux)
        aux = pe.get_accounts(filter_expired=False)[0]['account_id']
        ac.find(aux)
        legacy_info['comment'] = ('%s - Duplicate of %s' %
                                  (time.strftime('%Y%m%d'),
                                   ac.account_name))
        mailto_rt = True
    except Exception:
        logger.error("Unable to find find primary account", exc_info=True)

    lu.set(**legacy_info)
    logger.info("Updated legacy table")

    # TODO: DO NOT ENABLE email dispatching without rewriting.
    #       Even when running with --commit, there is a chance that processing
    #       fails and the db will be rolled back.
    #       Email dispatch should probably be aggregated and delayed until
    #       *after* the main() db.commit().

    # Sending email to Portal queue in RT if necessary
    if False and mailto_rt and not dryrun:
        sendmail(
            toaddr='vevportal@rt.uit.no',
            fromaddr='bas-admin@cc.uit.no',
            subject=(
                'Brukernavn slettet (%s erstattes av %s)' %
                (legacy_info['user_name'], ac.account_name)),
            body=(
                'Brukernavnet %s skal erstattes av %s.' %
                (legacy_info['user_name'], ac.account_name)),
            cc=None,
            charset='iso-8859-1',
            debug=False)
        logger.info("Sent RT email")

    # Sending email to AD nybrukere if necessary
    if False and mailto_ad and not dryrun:
        # Inform about new username, if new username has AD spread
        riktig_brukernavn = ''
        if mailto_rt:
            try:
                for spread in ac.get_spread():
                    if spread['spread'] == co.spread_uit_ad_account:
                        riktig_brukernavn = (
                            ' Riktig brukernavn er %s.' % ac.account_name)
                        if ac.is_expired():
                            riktig_brukernavn += (
                                ' Imidlertid vil ikke den korrekte kontoen'
                                ' bli reaktivert før i morgen.')
                        break
            except Exception:
                logger.error(
                    "Didn't find AD-spread on primary (correct) account",
                    exc_info=True)

        sendmail(
            toaddr='nybruker2@asp.uit.no',
            fromaddr='bas-admin@cc.uit.no',
            subject='Brukernavn slettet',
            body=(
                'Brukernavnet %s er slettet i BAS.%s' %
                (legacy_info['user_name'], riktig_brukernavn)),
            cc=None,
            charset='iso-8859-1',
            debug=False)
        logger.info("Sent AD email")


def get_target_id(db, entity_id):
    """ Get email target_id for an entity_id. """
    stmt = """
    SELECT target_id FROM email_target
    WHERE target_entity_id = :entity_id
    """
    try:
        target_id = db.query_1(stmt, {'entity_id': int(entity_id)})
        logger.info("Found target_id=%r for entity_id=%r",
                    target_id, entity_id)
    except Exception:
        logger.info("No target_id for entity_id=%r", entity_id)
        target_id = None
    return target_id


def process_account(db, account_id, dryrun):
    target_id = get_target_id(db, account_id)
    try:
        delete_account(db,
                       account_id=account_id,
                       target_id=target_id,
                       dryrun=dryrun)
    except Exception:
        logger.critical('Unable to delete account_id=%r', account_id)
        raise


def read_integers(filename):
    """Read integers from a file, one value per line."""
    logger.info("Reading integers from %r", filename)
    count = 0
    with open(filename, 'r') as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                field = line.split(',')[0]
                yield int(field)
                count += 1
            except Exception as e:
                logger.error("Invalid value on line %d: %s (%s)",
                             lineno, line, e)
                continue
    logger.info("Found %d integers in %r", count, filename)


def main(inargs=None):
    parser = argparse.ArgumentParser(description="Delete accounts")
    what = parser.add_mutually_exclusive_group(required=True)
    what.add_argument(
        '-f', '--file',
        dest='filename',
        help="Delete account_ids found in %(metavar)s",
        metavar='filename',
    )
    what.add_argument(
        '-a', '--account',
        dest='account_id',
        type=int,
        help="Delete account with %(metavar)s",
        metavar='account_id',
    )
    add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('tee', args)

    logger.info('Start of %s', parser.prog)
    logger.debug('args: %r', args)

    dryrun = not args.commit

    db = Factory.get('Database')()

    if args.filename:
        for account_id in read_integers(args.filename):
            process_account(db, account_id, dryrun)
    else:
        process_account(db, args.account_id, dryrun)

    if args.commit:
        logger.info('Commiting changes')
        db.commit()
    else:
        db.rollback()
        logger.info('Rolling back changes')
    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
