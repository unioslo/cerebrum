#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""Undo certain operations in Cerebrum.

This script scans the database for some entries and changes, and removes said
entries/changes, subject to certain constraints.

A typical use case for this script is to remove (completely) VirtAccounts from
Cerebrum that have not been confirmed within a specified period of time.

The code should be generic enough to be used on any installation.
"""
import argparse
import datetime
import logging

import six

import cereconf

import Cerebrum.logutils
from Cerebrum.Utils import Factory
from Cerebrum.utils import json
from Cerebrum import Entity
from Cerebrum import Errors
from Cerebrum.modules.EntityTrait import EntityTrait
from Cerebrum.modules.bofhd.auth import BofhdAuthRole
from Cerebrum.modules.bofhd.auth import BofhdAuthOpTarget
from Cerebrum.utils import date_compat
from Cerebrum.utils.date import now


logger = logging.getLogger(__name__)


def fetch_name(entity_id, db):
    """Fetch entity_id's name, ignoring errors if it does not exist. """
    ent = Entity.EntityName(db)
    try:
        ent.find(int(entity_id))
        return ", ".join(x["name"] for x in ent.get_names())
    except Errors.NotFoundError:
        return ""


def get_account(ident, database):
    """Locate and return an account.

    If nothing is found, return None.
    """
    account = Factory.get("Account")(database)
    try:
        if (isinstance(ident, six.integer_types)
                or isinstance(ident, six.string_types) and ident.isdigit()):
            account.find(int(ident))
        else:
            account.find_by_name(ident)

        return account
    except Errors.NotFoundError:
        logger.warn("Cannot locate account associated with: %s",
                    ident)
        return None

    raise RuntimeError('NOTREACHED')


def get_group(ident, database):
    """Locate and return a group.

    If nothing suitable is found, return None.
    """
    group = Factory.get("Group")(database)
    try:
        if (isinstance(ident, six.integer_types)
                or isinstance(ident, six.string_types) and ident.isdigit()):
            group.find(int(ident))
        else:
            group.find_by_name(ident)

        return group
    except Errors.NotFoundError:
        logger.warn("Cannot locate group associated with: %s",
                    ident)
        return None

    raise RuntimeError('NOTREACHED')


def remove_target_permissions(entity_id, db):
    """Remove all permissions (group owner/moderator) GIVEN TO entity_id.

    FIXME: what if entity_id is a group owner? If we yank it, the group
    remains ownerless.

    Cf bofhd_virthome_cmds.py:__remove_auth_role.
    """
    ar = BofhdAuthRole(db)
    aot = BofhdAuthOpTarget(db)
    for r in ar.list(entity_id):
        ar.revoke_auth(entity_id, r['op_set_id'], r['op_target_id'])
        # Also remove targets if this was the last reference from
        # auth_role.
        remaining = ar.list(op_target_id=r['op_target_id'])
        if len(remaining) == 0:
            aot.clear()
            aot.find(r['op_target_id'])
            aot.delete()


def remove_permissions_on_target(entity_id, db):
    """Remove all permissions GRANTED ON entity_id.

    remote_target_permissions() removes permissions held by entity_id. This
    function removes permissions held by other on entity_id.

    Cf bofhd_virthome_cmds.py:__remove_auth_target.
    """

    ar = BofhdAuthRole(db)
    aot = BofhdAuthOpTarget(db)
    for r in aot.list(entity_id=entity_id):
        aot.clear()
        aot.find(r['op_target_id'])
        # We remove all auth_role entries pointing to this entity_id
        # first.
        for role in ar.list(op_target_id=r["op_target_id"]):
            ar.revoke_auth(role['entity_id'], role['op_set_id'],
                           r['op_target_id'])
        aot.delete()


def delete_common(entity_id, db):
    """Remove information from the database common to whichever entity we are
    deleting.
    """
    # Remove spreads
    # Remove traits
    # Remove all permissions
    # Remove from all groups
    # Remove change_log entries
    const = Factory.get("Constants")()
    logger.debug("Deleting common parts for entity %s (id=%s)",
                 fetch_name(entity_id, db), entity_id)

    es = Entity.EntitySpread(db)
    es.find(entity_id)
    logger.debug("Deleting spreads: %s",
                 ", ".join(str(const.Spread(x["spread"]))
                           for x in es.get_spread()))
    for row in es.get_spread():
        es.delete_spread(row["spread"])

    et = EntityTrait(db)
    et.find(entity_id)
    logger.debug("Deleting traits: %s",
                 ", ".join(str(x) for x in et.get_traits()))
    # copy(), since delete_trait and get_traits work on the same dict. This is
    # so silly.
    for trait_code in et.get_traits().copy():
        et.delete_trait(trait_code)

    remove_target_permissions(entity_id, db)

    remove_permissions_on_target(entity_id, db)

    # Kill change_log entries
    logger.debug("Cleaning change_log of references to %s", entity_id)
    # Kill change_log entries (this includes requests linked to this entity)
    for row in db.get_log_events(subject_entity=entity_id):
        db.remove_log_event(row["change_id"])


def remove_from_groups(entity_id, db):
    """ Remove entity from groups and clean change log. """
    group = Factory.get("Group")(db)
    clconst = Factory.get("CLConstants")()

    for row in group.search(member_id=entity_id,
                            filter_expired=False):
        group.clear()
        group.find(row["group_id"])
        logger.debug("Removing %s as member of %s (id=%s)",
                     entity_id, group.group_name, group.entity_id)
        group.remove_member(entity_id)

    for row in db.get_log_events(subject_entity=entity_id,
                                 types=[clconst.group_rem]):
        db.remove_log_event(row["change_id"])


def disable_account(account_id, db):
    """Disable account corresponding to account_id.

    Once disabled, an account is just a placeholder for the username. It has
    no other value/associated attributes.

    NB! We keep entity_contact_info around, since we may want to know at least
    some human-'relatable' info about the account after it's disabled
    """
    account = get_account(account_id, db)
    if not account:
        return

    # If the account has already been deleted, we cannot disable it any
    # further.
    if account.is_deleted():
        return

    delete_common(account.entity_id, db)

    account.expire_date = datetime.date.today() + datetime.timedelta(days=1)
    account.write_db()
    logger.debug("Disabled account %s (id=%s)",
                 account.account_name, account.entity_id)


def delete_account(account, db):
    """ Perform deletion of account. """
    disable_account(account.entity_id, db)
    # Kill the account
    a_id, a_name = account.entity_id, account.account_name
    account.delete()
    # This may be a rollback -- that behaviour is controlled by the command
    # line.
    db.commit()
    logger.debug("Deleted account %s (id=%s)", a_name, a_id)


def disable_expired_accounts(db):
    """Delete (nuke) all accounts that have expire_date in the past. """
    logger.info("Disabling expired accounts")
    const = Factory.get("Constants")(db)
    account = Factory.get("Account")(db)
    for row in account.list(filter_expired=False):
        # do NOT touch non-VH accounts.
        if row["np_type"] not in (const.virtaccount_type,
                                  const.fedaccount_type):
            continue

        expire_date = date_compat.get_date(row["expire_date"])
        if not expire_date or expire_date >= datetime.date.today():
            continue

        # Ok, it's an expired VH. Kill it
        disable_account(row["account_id"], db)
        db.commit()
    logger.debug("Disabled all expired accounts")


def delete_unconfirmed_accounts(account_np_type, db):
    """Delete (nuke) all accounts that have stayed unconfirmed too long.

    If an account (of account_np_type) has existed unconfirmed for longer than
    GRACE_PERIOD since unconfirmed change_log event has been set, delete it.

    FIXME: What about partial failures? I.e. do we want to commit after each
    deletion?
    """
    logger.info("Deleting unconfirmed accounts of type '%s'",
                six.text_type(account_np_type))
    grace_period = date_compat.get_timedelta(cereconf.GRACE_PERIOD,
                                             allow_none=False)
    logger.debug('grace period: %r', grace_period)

    clconst = Factory.get("CLConstants")(db)
    account = Factory.get("Account")(db)
    for row in db.get_log_events(types=clconst.va_pending_create):
        tstamp = date_compat.get_datetime_tz(row["tstamp"])
        if now() - tstamp <= grace_period:
            continue

        account_id = int(row["subject_entity"])
        try:
            account.clear()
            account.find(account_id)
        except Errors.NotFoundError:
            # FIXME: is this the right thing to do? Maybe a warn()?
            logger.info("change_id %s (event %s) @ date=%s points to "
                        "account name=%s (id=%s) "
                        "that no longer exists (cl event will be deleted)",
                        row["change_id"],
                        str(clconst.ChangeType(row["change_type_id"])),
                        tstamp.strftime('%F %T'),
                        fetch_name(row["subject_entity"], db),
                        row["subject_entity"])
            db.remove_log_event(row["change_id"])
            db.commit()
            continue

        if account.np_type != account_np_type:
            continue

        change_log_res = db.get_log_events(
            subject_entity=account_id, change_by=account_id)

        if change_log_res:
            for entry in change_log_res:
                db.remove_log_event(entry["change_id"])

        logger.debug(
            "Account %s (id=%s) has event %s @ %s and will be deleted",
            account.account_name,
            account.entity_id,
            str(clconst.ChangeType(clconst.va_pending_create)),
            tstamp.strftime("%Y-%m-%d"))

        delete_account(account, db)
        db.commit()
    logger.debug("All unconfirmed accounts deleted")


def delete_unconfirmed_virtaccounts(db):
    const = Factory.get('Constants')(db)
    return delete_unconfirmed_accounts(const.virtaccount_type, db)


def delete_stale_events(cl_events, db):
    """Remove all events of type cl_events older than GRACE_PERIOD.

    cl_events is an iterable listing change_log event types that we want
    expunged. These events cannot require any state change in Cerebrum (other
    than their own deletion). It is the caller's responsibility to check that
    this is so.
    """
    if not isinstance(cl_events, (list, tuple, set)):
        cl_events = [cl_events, ]

    clconst = Factory.get("CLConstants")()
    typeset_request = ", ".join(str(clconst.ChangeType(x))
                                for x in cl_events)
    logger.info("Deleting stale requests: %s", typeset_request)
    max_invite_period = date_compat.get_timedelta(cereconf.MAX_INVITE_PERIOD,
                                                  allow_none=False)
    logger.debug('max age: %r', max_invite_period)
    grace_period = date_compat.get_timedelta(cereconf.GRACE_PERIOD,
                                             allow_none=False)
    logger.debug('grace period: %r', grace_period)

    for event in db.get_log_events(types=cl_events):
        tstamp = date_compat.get_datetime_tz(event["tstamp"])
        timeout = grace_period
        try:
            params = json.loads(event["change_params"])
            if params['timeout'] is not None:
                timeout = datetime.timedelta(days=int(params['timeout']))
                logger.debug('Timeout set to %s for %s',
                             (now() + timeout).strftime('%Y-%m-%d'),
                             event['change_id'])

                if timeout > max_invite_period:
                    logger.warning('Too long timeout (%s) for for %s',
                                   timeout.strftime('%Y-%m-%d'),
                                   event['change_id'])
                    timeout = max_invite_period
        except KeyError:
            pass
        if now() - tstamp <= timeout:
            continue

        logger.debug("Deleting stale event %s (@%s) for entity %s (id=%s)",
                     str(clconst.ChangeType(event["change_type_id"])),
                     tstamp.strftime("%Y-%m-%d"),
                     fetch_name(event["subject_entity"], db),
                     event["subject_entity"])

        db.remove_log_event(event["change_id"])
        db.commit()

    logger.debug("Deleted all stale requests: %s", typeset_request)


def find_and_disable_account(uname, database):
    """Force expiration date for a specific account, regardless of its
    attributes.

    This works for VA/FA only.

    WARNING! DO NOT take this lightly. People are gonna be pissed if we yank
    their accounts left and right
    """
    logger.debug("Trying to disable account: %s", uname)
    account = get_account(uname, database)
    if account is None:
        return
    disable_account(account.entity_id, database)
    logger.debug("Disabled account: %s", uname)


def find_and_delete_account(uname, database):
    """Completely remove an account from the database.

    This may come in handy for maintenance tasks. If for some reason we want
    an account completely obliterated, this is the method to call.
    """

    account = get_account(uname, database)
    if account is None:
        return

    delete_account(account, database)


def find_and_delete_group(gname, database):
    """ Completely remove a group from the database. """

    group = get_group(gname, database)
    if group is None:
        return

    gname, gid = group.group_name, group.entity_id
    remove_from_groups(group.entity_id, database)
    delete_common(group.entity_id, database)

    group.delete()
    logger.debug("Deleted group %s (id=%s)", gname, gid)


def delete_stale_event_action(*event_types):
    """
    Create a callback that deletes all stale events of the given type(s).
    """
    if not event_types:
        raise TypeError('expects at least one argument (got %d)' %
                        len(event_types))

    def do_delete_event(db):
        clconst = Factory.get('CLConstants')(db)
        events = []

        # validate and map event_types
        for event_attr in event_types:
            events.append(getattr(clconst, event_attr))

        return delete_stale_events(events, db)
    return do_delete_event


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Delete stale events, accounts, or groups',
    )

    db_args = parser.add_argument_group('Database')
    commit_mutex = db_args.add_mutually_exclusive_group()
    commit_mutex.add_argument(
        '--with-commit', '--commit',
        dest='commit',
        action='store_true',
        default=False,
    )
    commit_mutex.add_argument(
        '--dryrun',
        dest='commit',
        action='store_false',
        default=False,
    )

    maintenance = parser.add_argument_group('Maintenance tasks')
    maintenance.add_argument(
        '--remove-unconfirmed-virtaccounts',
        dest='actions',
        action='append_const',
        const=delete_unconfirmed_virtaccounts,
    )
    maintenance.add_argument(
        '--disable-expired-accounts',
        dest='actions',
        action='append_const',
        const=disable_expired_accounts,
    )
    maintenance.add_argument(
        '--remove-stale-email-requests',
        dest='actions',
        action='append_const',
        const=delete_stale_event_action('va_email_change'),
    )
    maintenance.add_argument(
        '--remove-group-invitations',
        dest='actions',
        action='append_const',
        const=delete_stale_event_action('va_group_invitation'),
    )
    maintenance.add_argument(
        '--remove-stale-group-modifications',
        dest='actions',
        action='append_const',
        const=delete_stale_event_action('va_group_admin_swap',
                                        'va_group_moderator_add'),
    )
    maintenance.add_argument(
        '--remove-stale-password-recover',
        dest='actions',
        action='append_const',
        const=delete_stale_event_action('va_password_recover'),
    )

    manual = parser.add_argument_group('Manual tasks')
    manual.add_argument(
        "--disable-account",
        dest='disable_accounts',
        action='append',
        metavar='<account_name>',
    )
    manual.add_argument(
        "--delete-account",
        dest='delete_accounts',
        action='append',
        metavar='<account_name>',
    )
    manual.add_argument(
        "--delete-group",
        dest='delete_groups',
        action='append',
        metavar='<group_name>',
    )

    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start: %s', parser.prog)

    db = Factory.get("Database")()
    db.cl_init(change_program="Grim reaper")

    # This script does a lot of dangerous things. Let's be a tad more
    # prudent.
    if args.commit:
        try_commit = db.commit
    else:
        try_commit = db.rollback

    db.commit = try_commit

    for action in (args.actions or ()):
        action(db)

    for uname in (args.disable_accounts or ()):
        logger.info('disable user: %s', uname)
        find_and_disable_account(uname, db)

    for uname in (args.delete_accounts or ()):
        logger.info('delete user: %s', uname)
        find_and_delete_account(uname, db)

    for gname in (args.delete_groups or ()):
        logger.info('delete group: %s', gname)
        find_and_delete_group(gname, db)

    # Note: some changes may already be commited/rolled back depending on how
    # each action handles db transactions
    if args.commit:
        db.commit()
        logger.info("changes commited")
    else:
        db.rollback()
        logger.info("changes rolled back (dryrun)")

    logger.info('Done: %s', parser.prog)


if __name__ == "__main__":
    main()
