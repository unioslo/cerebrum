#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""This script creates (or reactivates) an account for a person with specified
affiliation.

Originally NMH used process_students.py to automatically create employee
(those with affiliation=TILKNYTTET) accounts. However, NMH migrated to SAP for
employment data which makes it difficult for process_students.py to create any
accounts for those who are employees only.

Thus, thus script scans for people who:

  - Have at least one specified affiliation (there may be several)
  - Do not have an account at all or
    Have an expired account or
    Have an active account without the specified affiliations

Having collected such people, the script either creates a new account (as if
by bofh's user_create) or re-activates an expired one. Reactivation in this
case means:

- Removing expire date
- Assigning correct affiliations (copy from person)
- Assigning proper spread (cereconf.BOFHD_NEW_USER_SPREADS)

Whether an account has been created or re-activated, it gets a new password
(this would be a password unknown to all not having access to change_log)

Should an account already exist AND be active, it'd receive a copy of the
affiliations from the person owner.

Typical usage pattern would be to create/reactive accounts for SAP-employees:

python create-account-for-person.py -a ANSATT
"""

import getopt
import sys

import cereconf

from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.utils.funcwrap import memoize


logger = None


@memoize
def get_system_account():
    """Return an ID for cereconf.INITIAL_ACCOUNTNAME"""

    db = Factory.get("Database")()
    account = Factory.get('Account')(db)
    account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    default_creator_id = account.entity_id
    return default_creator_id
# end get_system_account


@memoize
def ou_id2human_repr(ou_id):
    """Return a human-friendly ou identification.

    We want something like <ACRONYM>/<SKO>, i.e. NMH-MUSP/01-15-06.

    This is a convenience function, so that our logs look more
    human-friendly.
    """

    db = Factory.get("Database")()
    ou = Factory.get("OU")(db)
    const = Factory.get("Constants")()
    ou.find(ou_id)

    acronym = ou.get_name_with_language(name_variant=const.ou_name_acronym,
                                        name_language=const.language_nb,
                                        default="")
    sko = "%02d-%02d-%02d" % (int(ou.fakultet),
                              int(ou.institutt),
                              int(ou.avdeling))
    return "%s/%s (id=%s)" % (acronym, sko, ou.entity_id)
# end ou_id2human_repr


def fetch_names(person):
    """Get first, last names for an person.

    @type person: Factory.get('Person') object associated with a person_id
    @param person:
      Person we want to select the names for.

    @rtype: tuple (of 2 basestrings)
    @return:
      A tiple (first name, last name). First name may be an empty string.
    """

    const = Factory.get("Constants")()
    first = last = None

    try:
        first = person.get_name(const.system_cached, const.name_first)
    except Errors.NotFoundError:
        first = ""

    try:
        last = person.get_name(const.system_cached, const.name_last)
    except Errors.NotFoundError:
        last = person.get_name(const.system_cached, const.name_full)

    logger.debug("Person id=%s will have first=%s last=%s as names",
                 person.entity_id, first, last)
    return first, last
# end fetch_names


def copy_owners_affiliations(person, account):
    """Copy person's affiliation to account.

    @type person: Factory.get('Person') proxy associated with a person
    @param person:
      Account owner that 'supplies' the affiliations.

    @type account: Factory.get('Account') proxy associated with an account.
    @param account:
      Account owned by L{person} that 'inherits' affiliations.
    """

    assert account.owner_id == person.entity_id
    const = Factory.get("Constants")()

    for entry in person.get_affiliations():
        ou_id, affiliation = entry["ou_id"], entry["affiliation"]
        account.set_account_type(ou_id, affiliation)
        logger.debug("Account %s inherits aff=%s, ou=%s from its owner",
                     account.account_name,
                     const.PersonAffiliation(affiliation),
                     ou_id2human_repr(ou_id))

    account.write_db()
# end copy_owners_affiliations


def set_initial_spreads(account):
    """Force certain spreads on account.

    The initial spreads are taken from cereconf.BOFHD_NEW_USER_SPREADS.

    @type account: Factory.get('Account') proxy associated with an account.
    @param account:
      Account to set spreads for.
    """
    const = Factory.get("Constants")()
    for spread in cereconf.BOFHD_NEW_USER_SPREADS:
        if not account.has_spread(const.Spread(spread)):
            account.add_spread(const.Spread(spread))
            logger.debug("Assigned spread=%s to uname=%s",
                         const.Spread(spread), account.account_name)

    account.write_db()
# end set_initial_spreads


def set_password(account):
    """Register a new (random) password for account.

    @type account: Factory.get('Account') proxy associated with an account.
    @param account:
      Account to set a password for.
    """
    password = account.make_passwd(account.account_name)
    account.set_password(password)
    account.write_db()
    logger.debug("Refreshed passwd for uname=%s", account.account_name)
# end set_password


def reactivate_expired_accounts(db, person_id, accounts):
    """Re-activate expired accoutns for person_id.

    @type person_id: int
    @param person_id:
      Person id to reactive accounts for.

    @type accounts: sequence of db_rows.
    @param accounts:
      Sequence of db_rows holding account_id for all accounts belonging to
      person. They should all be expired (i.e. the only way of getting *here*
      is when a person has expired accounts only).
    """
    person = Factory.get("Person")(db)
    person.find(person_id)

    if len(accounts) != 1:
        logger.warn("Person id=%s, names=%s has multiple expired accounts. "
                    "Cowardly refusing to activate one of them automatically. "
                    "This requires manual handling.",
                    person_id, fetch_names(person))
        return

    expired_account_id = accounts[0]["account_id"]

    account = Factory.get("Account")(db)
    account.find(expired_account_id)
    first, last = fetch_names(person)
    logger.debug("Person id=%s (first=%s, last=%s) will have "
                 "account %s reactivated.",
                 person_id, first, last, account.account_name)
    account.expire_date = None
    account.write_db()
    logger.debug("Removed expire date for uname=%s", account.account_name)

    set_password(account)

    copy_owners_affiliations(person, account)

    set_initial_spreads(account)
# end reactivate_expired_accounts


def create_new_account(db, person_id):
    """Create a new account for person_id.

    Create a new account owned by person_id. This account:

      - has an automatically chosen uname
      - has the system as creator_id (cereconf.INITIAL_ACCOUNTNAME)
      - has all of the person's affiliation
      - has all of cereconf.BOFHD_NEW_USER_SPREADS spreads
      - has an automatically assigned password
    """

    const = Factory.get("Constants")()
    person = Factory.get("Person")(db)
    person.find(person_id)
    first, last = fetch_names(person)
    logger.debug("Person id=%s (first=%s, last=%s) will be assigned "
                 "a new account", person_id, first, last)

    account = Factory.get("Account")(db)
    # choose a user name
    uname = account.suggest_unames(person)[0]
    logger.debug("Selected uname=%s for person id=%s", uname, person_id)
    # create an account
    account.populate(uname, const.entity_person,
                     person.entity_id,
                     None,
                     get_system_account(), None)
    account.write_db()
    logger.debug("Created uname=%s (id=%s) for person id=%s",
                 uname, account.entity_id, person_id)

    # register password
    set_password(account)

    # register initial spreads
    set_initial_spreads(account)

    # 'inherit' owner's affiliations
    copy_owners_affiliations(person, account)
# end create_new_account


def amend_existing_account(db, account_id, person_id):
    """Fixup account_id's affiliations"""

    person = Factory.get("Person")(db)
    person.find(person_id)
    account = Factory.get("Account")(db)
    account.find(account_id)

    logger.debug("Amending uname=%s (id=%s) from person_id=%s",
                 account.account_name, account.entity_id, person_id)
    copy_owners_affiliations(person, account)
# end amend_existing_account


def create_accounts(db, candidates):
    """Create or re-activate accounts for those candidates who need it.

    People who have *NO* accounts of any kind will get one.

    People who have at least one expired account, will get (one of the
    expired) accounts re-activated.
    """

    account = Factory.get("Account")(db)
    for person_id in candidates:
        accounts = account.get_account_types(all_persons_types=True,
                                             owner_id=person_id)
        # There is an active account that is fully working, but it lacks the
        # affiliation.
        if accounts:
            amend_existing_account(db, accounts[0]["account_id"], person_id)
        else:
            accounts = account.list_accounts_by_owner_id(person_id,
                                                         filter_expired=False)
            # No accounts exist at all
            if not accounts:
                create_new_account(db, person_id)
            # There are expired accounts we can reactivate
            else:
                reactivate_expired_accounts(db, person_id, accounts)
    # end create_accounts
# end create_accounts


def collect_candidates(db, affiliations):
    """Collect all people that have one of affiliations and do NOT have a
    non-expired account.

    @param db: Database proxy

    @type affiliations: sequence of PersonAffiliation constant objects
    @param affiliations:
      Person affiliations that mark the candidates. There may be many.
    """

    result = set()
    const = Factory.get("Constants")()
    person = Factory.get("Person")(db)
    account = Factory.get("Account")(db)
    for row in person.list_affiliations(affiliation=affiliations):
        if not account.list_accounts_by_owner_id(row["person_id"]):
            logger.debug("Person id=%s is a candidate", row["person_id"])
            result.add(row["person_id"])
        elif not account.list_accounts_by_type(person_id=row["person_id"],
                                               affiliation=list(affiliations)):
            logger.debug("Person id=%s is a candidate, since (s)he has "
                         "active accounts without affs=%s",
                         row["person_id"],
                         [str(const.PersonAffiliation(x)) for x in affiliations])
            result.add(row["person_id"])
    logger.debug("Collected %d candidate(s)", len(result))
    return result
# end collect_candidates


def main():
    global logger
    logger = Factory.get_logger("cronjob")

    options, junk = getopt.getopt(sys.argv[1:],
                                  "a:d",
                                  ("affiliation=",
                                   "dryrun",))

    const = Factory.get("Constants")()
    dryrun = False
    affiliations = set()
    for option, value in options:
        if option in ("-a", "--affiliation",):
            affiliation = const.human2constant(value, const.PersonAffiliation)
            if affiliation is not None:
                affiliations.add(affiliation)
        elif option in ("-d", "--dryrun",):
            dryrun = True

    db = Factory.get("Database")()
    db.cl_init(change_program="create-account")
    candidates = collect_candidates(db, affiliations)
    create_accounts(db, candidates)

    if dryrun:
        db.rollback()
        logger.info("Rolled back all changes")
    else:
        db.commit()
        logger.info("Committed all changes")
# end main


if __name__ == "__main__":
    main()
