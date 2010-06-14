#!/usr/bin/env python
# -*- encoding: iso-8859-1 -*-

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

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.Utils import simple_memoize
from Cerebrum import Errors
from Cerebrum.modules.EntityTrait import EntityTrait
from Cerebrum.modules.bofhd.auth import BofhdAuthOpSet
from Cerebrum.modules.bofhd.auth import BofhdAuthRole
from Cerebrum.modules.bofhd.auth import BofhdAuthOpTarget
from Cerebrum import Entity
from Cerebrum.Database import DatabaseError



GRACE_PERIOD = DateTimeDelta(3)
logger = Factory.get_logger("cronjob")

 

def fetch_name(entity_id, db):
    """Fetch entity_id's name, ignoring errors if it does not exist.
    """

    ent = Entity.EntityName(db)
    try:
        ent.find(int(entity_id))
        return ", ".join(x["name"] for x in ent.get_names())
    except Errors.NotFoundError:
        return ""
# end fetch_name



def disable_account(account_id, db):
    """Disable account corresponding to account_id.

    Once disabled, an account is just a placeholder for the username. It has
    no other value/associated attributes.

    NB! We keep entity_contact_info around, since we may want to know at least
    some human-'relatable' info about the account after it's disabled
    """
    
    #
    # Remove spreads
    # Remove traits
    # Remove all permissions
    # Remove from groups
    # Remove change_log entries
    # Set expire date to yesterday
    # 

    const = Factory.get("Constants")()
    account = Factory.get("Account")(db)
    account.find(account_id)

    # Remove all spreads
    for row in account.get_spread():
        account.delete_spread(row["spread"])

    # Remove all traits
    for trait_code in account.get_traits():
        account.delete_trait(trait_code)

    # Remove all permissions (group owner/moderator)
    # FIXME: what if account is group owner? If we yank it, the group remains
    # ownerless.
    # Kill the permissions granted to this account
    ar = BofhdAuthRole(db)
    aot = BofhdAuthOpTarget(db)
    for r in ar.list(account.entity_id):
        ar.revoke_auth(account.entity_id, r['op_set_id'], r['op_target_id'])
        # Also remove targets if this was the last reference from
        # auth_role.
        remaining = ar.list(op_target_id=r['op_target_id'])
        if len(remaining) == 0:
            aot.clear()
            aot.find(r['op_target_id'])
            aot.delete()

    # Kill group memberships
    group = Factory.get("Group")(db)
    for row in group.search(member_id=account.entity_id,
                            filter_expired=False):
        group.find(row["group_id"])
        group.remove_member(account.entity_id)

    # Kill change_log entries (this includes requests)
    for row in db.get_log_events(subject_entity=account.entity_id):
        db.remove_log_event(row["change_id"])

    account.expire_date = now() - DateTimeDelta(1)
    account.write_db()
# end disable_account



def delete_account(account, db):
    """Perform deletion of account.
    """

    disable_account(account.entity_id, db)
    # Kill the account
    a_id, a_name = account.entity_id, account.account_name
    account.delete()
    # This may be a rollback -- that behaviour is controlled by the command line.
    db.commit()
    logger.debug("Deleted account %s (id=%s)", a_name, a_id)
# end delete_account



def disable_expired_accounts(db):
    """Delete (nuke) all accounts that have expire_date in the past. 

    FAT-ASS WARNING:
    This probably should not be run, unless there is a user-warning system in
    place. Users are gonna be pissed, if we nuke the expired accounts without
    advanced warning.
    """

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
# end disable_expired_accounts

    

def delete_unconfirmed_accounts(account_np_type, db):
    """Delete (nuke) all accounts that have stayed unconfirmed too long.

    If an account (of account_np_type) has existed unconfirmed for longer than
    GRACE_PERIOD since unconfirmed change_log event has been set, delete it.

    FIXME: What about partial failures? I.e. do we want to commit after each
    deletion?
    """

    const = Factory.get("Constants")(db)
    account = Factory.get("Account")(db)
    for row in db.get_log_events(types=const.va_pending_create):
        tstamp = row["tstamp"]
        if now() - tstamp <= GRACE_PERIOD:
            continue

        account_id = int(row["subject_entity"])
        try:
            account.clear()
            account.find(account_id)
        except Errors.NotFoundError:
            # FIXME: is this the right thing to do? Maybe a warn()?
            logger.info("change_id %s (event %s) points to account %s (id=%s) "
                        "that no longer exists (cl event will be deleted)",
                        row["change_id"],
                        str(const.ChangeType(row["change_type_id"])),
                        fetch_name(row["subject_entity"], db),
                        row["subject_entity"])
            db.remove_log_event(row["change_id"])
            db.commit()
            continue

        if account.np_type != account_np_type:
            continue

        logger.debug("Account %s (id=%s) has event %s @ %s and will be deleted",
                     account.account_name, account.entity_id,
                     str(const.ChangeType(const.va_pending_create)),
                     tstamp.strftime("%Y-%m-%d"))

        delete_account(account, db)
        db.commit()
# end delete_unconfirmed_accounts



def delete_stale_events(cl_events, db):
    """Remove all events of type cl_events older than GRACE_PERIOD.

    cl_events is an iterable listing change_log event types that we want
    expunged. These events cannot require any state change in Cerebrum (other
    than their own deletion). It is the caller's responsibility to check that
    this is so.
    """

    const = Factory.get("Constants")()
    for event in db.get_log_events(types=cl_events):
        tstamp = event["tstamp"]
        if now() - tstamp <= GRACE_PERIOD:
            continue

        logger.debug("Deleting stale event (@%s) %s for entity %s (id=%s)",
                     event["tstamp"].strftime("%Y-%m-%d"),
                     str(const.ChangeType(event["change_type_id"])),
                     fetch_name(event["subject_entity"], db),
                     event["subject_entity"])
        
        db.remove_log_event(event["change_id"])
        db.commit()
# end delete_stale_events



def enforce_user_constraints(db):
    """Check a number of business rules for our users.
    """

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
# end enforce_user_constraints



def get_account(ident, database):
    """Locate and return an account.

    If nothing is found, return None.
    """

    account = Factory.get("Account")(database)
    try:
        if (isinstance(ident, (int, long)) or 
            isinstance(ident, str) and ident.isdigit()):
            account.find(int(ident))
        else:
            account.find_by_name(ident)

        return account
    except Errors.NotFoundError:
        logger.warn("Cannot locate account associated with: %s",
                    ident)
        return None

    assert False, "NOTREACHED"
# end get_account



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
# end find_and_disable_account



def find_and_delete_account(uname, database):
    """Completely remove an account from the database.

    This may come in handy for maintenance tasks. If for some reason we want
    an account completely obliterated, this is the method to call.
    """

    account = get_account(uname, database)
    if account is None:
        return

    delete_account(account, database)
# end find_and_delete_account



def find_and_delete_group(gname, database):
    """Completely remove a group from the database.
    """

    pass
# end find_and_delete_group



def main(argv):
    # This script performs actions that are too dangerous to be left to
    # single-letter arguments. Thus, long options only.
    options, junk = getopt.getopt(argv, "",
                                  ("remove-unconfirmed-virtaccounts",
                                   "remove-stale-email-requests",
                                   "remove-group-invitations",
                                   "disable-expired-accounts",
                                   "disable-account=",
                                   "delete-account=",
                                   "with-commit",))

    db = Factory.get("Database")()
    db.cl_init(change_program="Grim reaper")
    # This script does a lot of dangerous things. Let's be a tad more
    # prudent. 
    try_commit = db.rollback

    const = Factory.get("Constants")()
    actions = list()
    for option, value in options:
        if option in ("--remove-unconfirmed-virtaccounts",):
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
        elif option in ("--disable-account",):
            uname = value
            actions.append(lambda db: find_and_disable_account(uname, db))
        elif option in ("--delete-account",):
            uname= value
            actions.append(lambda db: find_and_delete_account(uname, db))
        elif option in ("--with-commit",):
            try_commit = db.commit

    db.commit = try_commit

    for action in actions:
        action(db)

    # commit/rollback changes to the database.
    try_commit()
# end main



if __name__ == "__main__":
    main(sys.argv[1:])
