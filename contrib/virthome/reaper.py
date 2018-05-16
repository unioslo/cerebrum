#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""Undo certain operations in Cerebrum.

This script scans the database for some entries and changes, and removes said
entries/changes, subject to certain constraints.

A typical use case for this script is to remove (completely) VirtAccounts from
Cerebrum that have not been confirmed within a specified period of time.

The code should be generic enough to be used on any installation.
"""

import getopt
import sys

from mx.DateTime import now
from mx.DateTime import DateTimeDelta

import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.utils import json
from Cerebrum import Errors, Entity
from Cerebrum.modules.EntityTrait import EntityTrait
from Cerebrum.modules.bofhd.auth import BofhdAuthRole
from Cerebrum.modules.bofhd.auth import BofhdAuthOpTarget
from Cerebrum.Entity import EntitySpread


logger = Factory.get_logger("cronjob")


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
        if (isinstance(ident, (int, long))
                or isinstance(ident, str) and ident.isdigit()):
            account.find(int(ident))
        else:
            account.find_by_name(ident)

        return account
    except Errors.NotFoundError:
        logger.warn("Cannot locate account associated with: %s",
                    ident)
        return None

    assert False, "NOTREACHED"


def get_group(ident, database):
    """Locate and return a group.

    If nothing suitable is found, return None.
    """
    group = Factory.get("Group")(database)
    try:
        if (isinstance(ident, (int, long))
                or isinstance(ident, str) and ident.isdigit()):
            group.find(int(ident))
        else:
            group.find_by_name(ident)

        return group
    except Errors.NotFoundError:
        logger.warn("Cannot locate group associated with: %s",
                    ident)
        return None

    assert False, "NOTREACHED"


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

    es = EntitySpread(db)
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
    const = Factory.get("Constants")()

    for row in group.search(member_id=entity_id,
                            filter_expired=False):
        group.clear()
        group.find(row["group_id"])
        logger.debug("Removing %s as member of %s (id=%s)",
                     entity_id, group.group_name, group.entity_id)
        group.remove_member(entity_id)

    for row in db.get_log_events(subject_entity=entity_id,
                                 types=[const.group_rem]):
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

    account.expire_date = now() - DateTimeDelta(1)
    account.write_db()
    logger.debug("Disabled account %s (id=%s)",
                 account.account_name, account.entity_id)


def delete_account(account, db):
    """ Perform deletion of account. """
    disable_account(account.entity_id, db)
    # Kill the account
    a_id, a_name = account.entity_id, account.account_name
    account.delete()
    # This may be a rollback -- that behaviour is controlled by the command line.
    db.commit()
    logger.debug("Deleted account %s (id=%s)", a_name, a_id)


def disable_expired_accounts(db):
    """Delete (nuke) all accounts that have expire_date in the past. """
    logger.debug("Disabling expired accounts")
    const = Factory.get("Constants")(db)
    account = Factory.get("Account")(db)
    for row in account.list(filter_expired=False):
        # do NOT touch non-VH accounts.
        if row["np_type"] not in (const.virtaccount_type,
                                  const.fedaccount_type):
            continue

        if row["expire_date"] >= now():
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
    logger.debug("Deleting unconfirmed accounts")
    const = Factory.get("Constants")(db)
    account = Factory.get("Account")(db)
    for row in db.get_log_events(types=const.va_pending_create):
        tstamp = row["tstamp"]
        if now() - tstamp <= cereconf.GRACE_PERIOD:
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
                        str(const.ChangeType(row["change_type_id"])),
                        tstamp.strftime("%F %T"),
                        fetch_name(row["subject_entity"], db),
                        row["subject_entity"])
            db.remove_log_event(row["change_id"])
            db.commit()
            continue

        if account.np_type != account_np_type:
            continue

        logger.debug(
            "Account %s (id=%s) has event %s @ %s and will be deleted",
            account.account_name,
            account.entity_id,
            str(const.ChangeType(const.va_pending_create)),
            tstamp.strftime("%Y-%m-%d"))

        delete_account(account, db)
        db.commit()
    logger.debug("All unconfirmed accounts deleted")


def delete_stale_events(cl_events, db):
    """Remove all events of type cl_events older than GRACE_PERIOD.

    cl_events is an iterable listing change_log event types that we want
    expunged. These events cannot require any state change in Cerebrum (other
    than their own deletion). It is the caller's responsibility to check that
    this is so.
    """

    if not isinstance(cl_events, (list, tuple, set)):
        cl_events = [cl_events, ]

    const = Factory.get("Constants")()
    typeset_request = ", ".join(str(const.ChangeType(x))
                                for x in cl_events)
    logger.debug("Deleting stale requests: %s", typeset_request)
    for event in db.get_log_events(types=cl_events):
        tstamp = event["tstamp"]
        timeout = cereconf.GRACE_PERIOD
        try:
            params = json.loads(event["change_params"])
            if params['timeout'] is not None:
                timeout = DateTimeDelta(params['timeout'])
                logger.debug('Timeout set to %s for %s',
                             (now() + timeout).strftime('%Y-%m-%d'),
                             event['change_id'])

                if timeout > cereconf.MAX_INVITE_PERIOD:
                    logger.warning('Too long timeout (%s) for for %s',
                                   timeout.strftime('%Y-%m-%d'),
                                   event['change_id'])
                    timeout = cereconf.MAX_INVITE_PERIOD
        except KeyError:
            pass
        if now() - tstamp <= timeout:
            continue

        logger.debug("Deleting stale event %s (@%s) for entity %s (id=%s)",
                     str(const.ChangeType(event["change_type_id"])),
                     event["tstamp"].strftime("%Y-%m-%d"),
                     fetch_name(event["subject_entity"], db),
                     event["subject_entity"])

        db.remove_log_event(event["change_id"])
        db.commit()

    logger.debug("Deleted all stale requests: %s", typeset_request)


def enforce_user_constraints(db):
    """ Check a number of business rules for our users. """
    account = Factory.get("Account")(db)
    const = Factory.get("Constants")()
    for row in account.list(filter_expired=False):
        # We check FA/VA only
        if row["np_type"] not in (const.fedaccount_type,
                                  const.virtaccount_type):
            continue

        account.clear()
        account.find(row["entity_id"])
        # Expiration is not set -> force it to default
        if row["expire_date"] is None:
            logger.warn("Account %s (id=%s) is missing expiration date.",
                        account.account_name,
                        account.entity_id)
            account.expire_date = now() + account.DEFAULT_ACCOUNT_LIFETIME
            account.write_db()

        # Expiration is too far in the future -> force it to default
        if row["expire_date"] - now() > account.DEFAULT_ACCOUNT_LIFETIME:
            logger.warn("Account %s (id=%s) has expire date too far in the"
                        " future.", account.account_name, account.entity_id)
            account.expire_date = now() + account.DEFAULT_ACCOUNT_LIFETIME
            account.write_db()


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
    logger.debug("Deleting group %s (id=%s)", gname, gid)


def main(argv):
    # This script performs actions that are too dangerous to be left to
    # single-letter arguments. Thus, long options only.
    options, junk = getopt.getopt(argv, "",
                                  ("remove-unconfirmed-virtaccounts",
                                   "remove-stale-email-requests",
                                   "remove-group-invitations",
                                   "disable-expired-accounts",
                                   "remove-stale-group-modifications",
                                   "remove-stale-password-recover",
                                   "disable-account=",
                                   "delete-account=",
                                   "delete-group=",
                                   "with-commit",))

    db = Factory.get("Database")()
    db.cl_init(change_program="Grim reaper")
    # This script does a lot of dangerous things. Let's be a tad more
    # prudent.
    try_commit = db.rollback

    const = Factory.get("Constants")()
    actions = list()
    #
    # NB! We can safely ignore processing va_reset_expire_date -- if the user
    # does not do anything, it'll be disabled (including removal of the
    # va_reset_expire_date) within cereconf.EXPIRE_WARN_WINDOW days.
    for option, value in options:
        if option in ("--remove-unconfirmed-virtaccounts",):
            # Handles va_pending_create
            actions.append(lambda db:
                           delete_unconfirmed_accounts(const.virtaccount_type,
                                                       db))
        elif option in ("--remove-stale-email-requests",):
            actions.append(lambda db:
                           delete_stale_events(const.va_email_change, db))
        elif option in ("--remove-group-invitations",):
            actions.append(lambda db:
                           delete_stale_events(const.va_group_invitation, db))
        elif option in ("--disable-expired-accounts",):
            actions.append(disable_expired_accounts)
        elif option in ("--remove-stale-group-modifications",):
            actions.append(lambda db:
                           delete_stale_events((const.va_group_owner_swap,
                                                const.va_group_moderator_add,),
                                               db))
        elif option in ("--remove-stale-password-recover",):
            actions.append(lambda db:
                           delete_stale_events(const.va_password_recover, db))
        elif option in ("--with-commit",):
            try_commit = db.commit

        #
        # These options are for manual runs. It makes no sense to use these
        # in an automatic job scheduler (cron, bofhd, etc)
        elif option in ("--disable-account",):
            uname = value
            actions.append(lambda db: find_and_disable_account(uname, db))
        elif option in ("--delete-account",):
            uname = value
            actions.append(lambda db: find_and_delete_account(uname, db))
        elif option in ("--delete-group",):
            gname = value
            actions.append(lambda db: find_and_delete_group(gname, db))

    db.commit = try_commit

    for action in actions:
        action(db)

    # commit/rollback changes to the database.
    try_commit()


if __name__ == "__main__":
    main(sys.argv[1:])
