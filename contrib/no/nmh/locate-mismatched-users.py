#!/usr/bin/env python
# -*- encoding: latin-1 -*-

"""Report affiliation mismatches between people and their accounts.

During a meeting on 2010-02-23, NMH expressed an interest in an automatic
warning system where they receive a weekly report about people/accounts where
there is an affiliation mismatch. Since NMH has 1 person = 1 account policy in
place, there is at most 1 account to check per person.

Specifically, for each person P in Cerebrum carrying a specific affiliation:

* Locate the corresponding *active* user
* If person's affiliations match user's' -> we are done with P
* If the *active* user does not exist -> report an error
* If the *active* user exists but does NOT have an affiliation -> report an error.
* If the *active* user exists but has an affiliation that P does not have ->
  report an error.

Once mismatched users a collected, compile a report and e-mail it to NMH.
"""

from cStringIO import StringIO
import getopt
import sys

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.Utils import simple_memoize



def fetch_persons(affiliations, source):
    """Collect all person for this run.

    @param affiliations:
      A sequence of affiliations to collect (i.e. we collect all people who
      have at least of the the affiliations listed).

    @rtype: dict (person_id -> set of pairs (aff, status))
    @return:
      Dictionary mapping person_id to sequence of affiliations
    """

    db = Factory.get("Database")()
    const = Factory.get("Constants")()
    person = Factory.get("Person")(db)
    result = dict()
    for row in person.list_affiliations(affiliation=affiliations,
                                        source_system=source,
                                        include_deleted=False):
        # FIXME: What about source system here?
        person_affs = person.list_affiliations(person_id=row["person_id"])
        result.setdefault(row["person_id"], set()).update(
            (x["affiliation"], x["ou_id"])
            for x in person_affs)

    logger.debug("Collected %d people matching affiliation%s%s",
                 len(result),                 
                 len(affiliations) != 1 and "s " or " ",
                 ", ".join(str(const.PersonAffiliation(x))
                           for x in affiliations))
    return result
# end fetch_persons



def collect_mismatched_users(person2affiliations):
    """Find mismatched users wrt to person's affiliations.

    We are interested in collecting users that have an affiliation set
    different from persons.
    """

    db = Factory.get("Database")()
    account = Factory.get("Account")(db)
    const = Factory.get("Constants")()

    accountless = set()
    multi_account = dict()
    mismatched = dict()

    for person_id in person2affiliations:
        accounts = list(account.list_accounts_by_owner_id(person_id,
                                                          filter_expired=True))
        if len(accounts) < 1:
            accountless.add(person_id)
        elif len(accounts) > 1:
            multi_account.setdefault(person_id, set()).update(x["account_id"]
                                                              for x in accounts)
        else:
            account_id = accounts[0]["account_id"]
            aff_set = set()
            
            for row in account.list_accounts_by_type(account_id=account_id):
                aff_set.add((row["affiliation"], row["ou_id"]))

            if person2affiliations[person_id] != aff_set:
                mismatched[account_id] = (person2affiliations[person_id],
                                          aff_set)

    return accountless, multi_account, mismatched
# end collect_mismatched_users



def prepare_report(affiliations, accountless, multi_account, mismatched):
    """Generate a report to be e-mailed.
    """

    db = Factory.get("Database")()
    person = Factory.get("Person")(db)
    account = Factory.get("Account")(db)
    ou = Factory.get("OU")(db)
    const = Factory.get("Constants")(db)

    def pid2name(person_id):
        try:
            person.clear()
            person.find(person_id)
            return person.get_name(const.system_cached,
                                   const.name_full)
        except Errors.NotFoundError:
            return ""
    # end pid2name

    def uid2name(account_id):
        try:
            account.clear()
            account.find(account_id)
            return account.account_name
        except Errors.NotFoundError:
            return ""
    # end uid2name

    @simple_memoize
    def ouid2name(ou_id):
        try:
            ou.clear()
            ou.find(ou_id)
            return "%02d-%02d-%02d" % (ou.fakultet, ou.institutt, ou.avdeling)
        except Errors.NotFoundError:
            return ""
    # end ouid2name

    def uid2owner(account_id):
        try:
            account.clear()
            account.find(account_id)
            return account.owner_id
        except Errors.NotFoundError:
            return None
    # end uid2owner

    def affs2str(affiliations):
        return "{" + ", ".join(sorted("%s@%s" % (const.PersonAffiliation(x),
                                                 ouid2name(y))
                                      for x, y in affiliations)) + "}"

    
    sink = StringIO()
    sink.write("Person-user mismatch report for affiliations %s\n" %
               ", ".join(sorted(str(const.PersonAffiliation(x))
                                for x in affiliations)))
    sink.write("Summary:\n")
    sink.write("%d accountless people\n"
               "%d people with multiple active accounts\n"
               "%s people with person<->account affiliation mismatch\n" %
               (len(accountless), len(multi_account), len(mismatched)))

    if accountless:
        sink.write("Accountless peple:\n")
        for person_id in accountless:
            sink.write("\tPerson %s (id=%s) has no active accounts\n" % 
                       (pid2name(person_id), person_id))

    if multi_account:
        sink.write("People with multiple accounts:\n")
        for person_id in multi_account:
            accounts = multi_account[person_id]
            sink.write("\tPerson %s (id=%s) has %d active accounts:\n" %
                       (pid2name(person_id), person_id, len(accounts),
                        ", ".join(sorted(uid2name(x) for x in accounts))))

    if mismatched:
        sink.write("People with mismatched affiliations:\n")
        for account_id in mismatched:
            person_affs, account_affs = mismatched[account_id]
            owner_id = uid2owner(account_id)
            sink.write("\tPerson %s (id=%s)'s affiliations do not match "
                       "account's %s (id=%s) affs: %s != %s\n" %
                       (pid2name(owner_id),
                        owner_id,
                        uid2name(account_id),
                        account_id,
                        affs2str(person_affs),
                        affs2str(account_affs)))

    return sink.getvalue()
# end prepare_report



def main():
    global logger
    logger = Factory.get_logger("cronjob")

    options, junk = getopt.getopt(sys.argv[1:],
                                  "a:s:",
                                  ("affiliation=",
                                   "source-system=",))

    affiliations = set()
    source = None
    
    const = Factory.get("Constants")()
    for option, value in options:
        if option in ("-a", "--affiliation"):
            if const.human2constant(value, const.PersonAffiliation):
                affiliations.add(const.human2constant(value,
                                                      const.PersonAffiliation))
            else:
                logger.error("Wrong affiliation specification: %s", value)
        elif option in ("-s", "--source-system",):
            source_system = const.human2constant(value,
                                                 const.AuthoritativeSystem)

    assert source_system is not None, "Missing source system"
    assert len(affiliations) > 0, "Missing affiliation filter"
    
    persons = fetch_persons(affiliations, source)
    accountless, multi_account, mismatched = collect_mismatched_users(persons)
    report = prepare_report(affiliations, accountless, multi_account,
                            mismatched)
    logger.debug(report)
# end main



if __name__ == "__main__":
    main()
