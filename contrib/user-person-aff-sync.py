#!/usr/bin/env python
# -*- encoding: utf-8 -*-

# Copyright 2008 University of Oslo, Norway
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

"""This script synchronizes affiliations between users and persons.

Although there is a FK from account_type to person_affiliation, that FK does
not take person_affiliation_source(delete_date) into an account. So, although
the FK is there, is does not really do us any good, since in practice it looks
like we have a user affiliation that the person does not have.

In any event, this script synchronises the affiliations between users and
people. Specifically:

 - For every person in Cerebrum, list those with valid (== non-expired)
   affiliations.

 - Every person without a valid affiliation is left alone.

 - Every person with valid affiliations is checked for active accounts. An
   active account is an account without expire_date in the past.
 
 - If a person has no active accounts, it (the person) will be ignored.

 - For every active user U of a person P, U's affiliations are synchronised
   with P's. Synchronisation means that:

   1) all of P's affiliations are copied to U.

   2) Affiliations for U that do NOT exist for P will be removed, with one
      exception. One (any one, at random) of U's STUDENT affiliations are kept
      (so that the autostud framework can pick U up later). All such cases are
      reported. However, should P have an ANSATT affiliation, U will lose
      *all* of its affiliations that P does not have (STUDENT or
      otherwise). This is an exception to the exception :)

Usage:

user-person-aff-sync.py -d

... will report on all actions to be committed to the database to bring all
affiliations in sync between people and their active users.

user-person-aff-sync.py -a ANSATT -a STUDENT -a TILKNYTTET

... will synchronise ANSATT, STUDENT and TILKNYTTET affiliations, so that
users' affiliations of these 3 types match their owners'. *All* other
affiliation types will be left intact and they will NOT be touched.

If you want to combine TILKNYTTET and ANSATT to be considered as 'employee
affiliations', run this:

user-person-aff-sync.py --is-employee ANSATT --is-employee TILKNYTTET -d
"""

import getopt
import sys

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors



def has_employee(affiliations, employee_affs):
    """Check whether some of the affiliations match affiliation_ansatt.

    @type affiliations: set of tuples (affiliation_id, ou_id)
    @param affiliations:
      Affiliations to check

    @type affiliations: set of affiliations
    @param affiliations:
      Affiliation types that are considered equivalent to affiliation_ansatt.
    """

    for ou, affiliation in affiliations:
        if affiliation in employee_affs:
            return True
    return False
# end has_employee



def adjust_user_affiliations(account, account_id, owner_id,
                             owner_affiliations,
                             available_affiliations,
                             employee_affs):
    """Correct affiliations belonging to account_id.

    Correction procedure is described in __doc__.

    @type account_id: int
    @param account_id:
      Account whose affiliations we want to adjust

    @type owner_id: int
    @param owner_id:
      person_id owning the account (yes, it is a person_id)

    @type owner_affiliations: set of tuples (ou_id, affiliation)
    @param owner_affiliations:
      All affiliations belonging to owner_id. This is the basis for forcing
      affiliations on account_id.

    @type available_affiliations: set of affiliations
    @param available_affiliations:
      This set controls which affiliations will be touched by this
      script. 'x[1] for x in owner_affiliations' is guaranteed to be a subset
      of L{available_affiliations}.

      Any affiliation NOT in this set will be left alone.

    @type employee_affs: set of affiliations
    @param employee_affs:
      This set lists the affiliations that are considered equivalent to
      affiliation_ansatt in this run.
    """

    def aff2str(aff):
        return "%s @ ou_id=%s" % (str(const.PersonAffiliation(aff[1])), aff[0])

    def affs2str(affs):
        return ", ".join(aff2str(x) for x in affs)

    try:
        account.clear()
        account.find(account_id)
    except Errors.NotFoundError:
        logger.warn("Account id=%s suddenly disappeared?", account_id)
        return

    user_affiliations = set((int(x["ou_id"]), int(x["affiliation"]))
                            for x in account.get_account_types()
                            if x["affiliation"] in available_affiliations)
    person_but_not_user = owner_affiliations.difference(user_affiliations)
    user_but_not_person = user_affiliations.difference(owner_affiliations)

    if not person_but_not_user and not user_but_not_person:
        logger.debug("Account %s and owner id=%s have the same affiliations.",
                     account.account_name, owner_id)
        return

    logger.debug("Account name=%s id=%s:", account.account_name, account_id)
    logger.debug("\t%d account affiliations: %s",
                 len(user_affiliations), affs2str(user_affiliations))
    logger.debug("\t%d owner affiliations: %s",
                 len(owner_affiliations), affs2str(owner_affiliations))

    # Add affiliations that the owner has, but the account does NOT have.
    acquired_affiliations = list()
    for ou_id, affiliation in person_but_not_user:
        account.set_account_type(ou_id, affiliation)
        acquired_affiliations.append((ou_id, affiliation))

    # Remove affiliations that the account has, but the owner does NOT have.
    # (we cover everything except STUDENT here, since STUDENT are special)
    lost_affiliations = list()
    for ou_id, affiliation in user_but_not_person:
        if affiliation != const.affiliation_student:
            account.del_account_type(ou_id, affiliation)
            lost_affiliations.append((ou_id, affiliation))

    # Finally, STUDENT-affiliations are an exception
    user_student_affiliations = list(x for x in user_but_not_person if
                                     x[1] == const.affiliation_student)
    # Unless owner has an ANSATT affiliation, keep one STUDENT. Otherwise,
    # nuke them all.
    kept_affiliations = list()
    if user_student_affiliations:
        if not has_employee(owner_affiliations, employee_affs):
            kept_affiliations.append(user_student_affiliations.pop())

    # delete what's left of student affiliations
    for ou_id, affiliation in user_student_affiliations:
        account.del_account_type(ou_id, affiliation)
        lost_affiliations.append((ou_id, affiliation))

    logger.debug("Account %s (id=%s, owner=%s): got %d affiliations (%s);"
                 " lost %d affiliations (%s)",
                 account.account_name, account_id, owner_id,
                 len(acquired_affiliations), affs2str(acquired_affiliations),
                 len(lost_affiliations), affs2str(lost_affiliations))
    if kept_affiliations:
        logger.warn("Account %s id=%s kept affiliation(s) %s, even though "
                    "the owner did not have it",
                    account.account_name, account_id, affs2str(kept_affiliations))

    account.write_db()
# end adjust_user_affiliations



def process_affiliations(affiliations, employee_affs, db):
    """Perform affiliation sync between people and users.

    @type affiliation: sequence of (unique) CerebrumCode instances.
    @param affiliations: sequence of affiliations to consider

    @type employee_affs: sequence of (unique) CerebrumCode instances.
    @param employee_affs:
      Sequence of affiliations that are to be treated equivalent to
      affiliation_ansatt. In some cases it is useful to include more affs into
      such a set.

    @param db: Database proxy.
    """

    person = Factory.get("Person")(db)
    logger.info("Will look for these affiliations: %s", affiliations)
    logger.info("These affiliations count as ANSATT: %s", employee_affs)

    # collect person affiliations. This is the set that the users will be
    # sync-ed against.
    logger.debug("Loading person affiliations")
    person2affiliations = dict()
    for row in person.list_affiliations(affiliation=affiliations,
                                        include_deleted=False):
        person_id = int(row["person_id"])
        affiliation = int(row["affiliation"])
        ou_id = int(row["ou_id"])
        person2affiliations.setdefault(person_id, set()).add((ou_id,
                                                              affiliation))

    logger.debug("checking accounts")
    account = Factory.get("Account")(db)
    processed = set()
    for row in account.list_accounts_by_type(filter_expired=True):
        owner_id = row["person_id"]
        account_id = row["account_id"]
        if account_id in processed:
            continue
        adjust_user_affiliations(account, account_id, owner_id,
                                 person2affiliations.get(owner_id, set()),
                                 affiliations, employee_affs)
        processed.add(account_id)
# end process_affiliations



def affiliations_to_set(affiliation_class, affiliations):
    """Convert a bunch of codes to a set of affiliations.

    Users may specify affiliations either through a code (123) or through a
    code_str ('ANSATT'). This function maps such code/code_str to an existing
    constant object of the proper type.

    @type affiliation_class: a suitable CerebrumCode *class*
    @param affiliation_class:
      A class for the constants we are trying to locate. E.g. PersonAffiliation.
    """

    # remap affiliations to proper constants
    result = set()
    for item in affiliations:
        if item.isdigit():
            item = int(item)
        try:
            aff = affiliation_class(item)
            int(aff)
            result.add(aff)
        except Errors.NotFoundError:
            logger.warn("Affiliation <%s> does not exist", item)

    # if no affiliation was specified, we grab all that exist of the right
    # type.
    if not result:
        result = set(const.fetch_constants(affiliation_class))
        logger.debug("No affiliations specified explicitly. Will grab all: %s",
                     list(str(x) for x in result))
        
    return result
# end affiliations_to_set



def main():
    global logger
    logger = Factory.get_logger("console")
    opts, junk = getopt.getopt(sys.argv[1:],
                               "a:d",
                               ("affiliation=",
                                "dryrun",
                                "is-employee="))

    affiliations = list()
    dryrun = False
    employee_affs = []
    for option, value in opts:
        if option in ("-a", "--affiliation",):
            # each affiliation may be an int or a code_str from the
            # person_affiliation_code table
            affiliations.append(value)
        elif option  in ("-d", "--dryrun"):
            dryrun = True
        elif option in ("--is-employee",):
            employee_affs.append(value)


    global const
    db = Factory.get("Database")()
    db.cl_init(change_program="user-aff-sync")
    const = Factory.get("Constants")()
    affiliations = affiliations_to_set(const.PersonAffiliation,
                                       affiliations)
    employee_affs = affiliations_to_set(const.PersonAffiliation,
                                        employee_affs)
    if not employee_affs:
        employee_affs = set([const.affiliation_ansatt,])

    # Since STUDENT may be kept, depending on owner's employment affs,
    # sync'ing one without the other is meaningless
    if const.affiliation_student in affiliations:
        assert employee_affs.issubset(affiliations), \
                "It is a *BAD* idea to sync STUDENT without ANSATT"

    if dryrun:
        db.commit = db.rollback
    process_affiliations(affiliations, employee_affs, db)
    if dryrun:
        logger.debug("All changed rolled back")
        db.rollback()
    else:
        db.commit()
        logger.debug("All changes committed")
# end main


if __name__ == "__main__":
    main()
    

