#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2010 University of Oslo, Norway
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

"""Report breaches of business rules for person/account/group population.

During a meeting on 2010-02-23, NMH expressed an interest in an automatic
warning system where they receive a weekly report about people/accounts where
there is an affiliation mismatch. Since NMH has 1 person = 1 account policy in
place, there is at most 1 account to check per person.

Later, this has been extended by NMH to include information about mismatches
between affiliations and group memberships.

A typical run for NMH would look something like this:

  python report-mismatched-users.py \
         -s SAP \
         -u ANSATT \
         -g ANSATT:tekadm:023200:DPIT \
         -g ANSATT:tekadm:023100:STUDIEADMIN \
         -g ANSATT:vitenskapelig:011550:fagsekimprofolk \
         -g ANSATT:vitenskapelig:011560:fagsekmusped \
         -g ANSATT:tekadm:024000:BIBLIOTEKARENE \
         -g ANSATT:tekadm:023400:Informasjon \
         -g ANSATT::011570:fagsekmusteori \
         -g ANSATT::011530:fagsekakkom \
         -g ANSATT:vitenskapelig:011510:fagsekblas \
         -g ANSATT:vitenskapelig:011540:fagsekdir \
         -g ANSATT:vitenskapelig:011520:fagsekstryk

-u lists the affiliations to consider for person-user mismatches.
-g lists groups to scan for memberships based on affiliations.
Multiple options of either kind may be provided.
"""
from cStringIO import StringIO
import getopt
import sys
import textwrap

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.utils.funcwrap import memoize
from Cerebrum.Utils import sendmail
from Cerebrum import Errors


database = Factory.get("Database")()
logger = None


@memoize
def get_group(ident):
    """Fetch a group based on its id (name or entity_id)."""
    db = Factory.get("Database")()
    group = Factory.get("Group")(db)
    if isinstance(ident, str):
        ident = ident.strip()

    if (isinstance(ident, str) and ident.isdigit() or
        isinstance(ident, (int, long))):
        group.find(int(ident))
        return group
    # Assume it's group_name
    elif isinstance(ident, str):
        group.find_by_name(ident)
        return group

    assert False, "Unknown Group ident: <<%s>>" % (ident,)
# end get_group


@memoize
def get_ou(ident):
    "Fetch an OU based on its id (stedkode, acronym or entity_id)."
    ou = Factory.get("OU")(database)
    if isinstance(ident, str):
        ident = ident.strip()

    if isinstance(ident, str) and ident.isdigit():
        # 123456 - sko
        if len(ident) == 6:
            ou.find_stedkode(int(ident[:2]),
                             int(ident[2:4]),
                             int(ident[4:]),
                             cereconf.DEFAULT_INSTITUSJONSNR)
        # just digist -- ou_id
        else:
            ou.find(int(ident))

        return ou
    # Assume it's an acronym
    elif isinstance(ident, str):
        const = Factory.get("Constants")()
        result = ou.search_name_with_language(
            entity_type=const.entity_ou,
            name_variant=const.ou_name_acronym,
            name=ident,
            name_language=const.language_nb,
            exact_match=False)
        assert len(result) == 1
        ou.find(result[0]["ou_id"])
        return ou
    # It's an ou_id
    elif isinstance(ident, (int, long)):
        ou.find(int(ident))
        return ou

    assert False, "Unknown OU ident: <<%s>>" % (ident,)
# end get_ou


@memoize
def ou_id2report(ou_id):
    """Produce a human-friendly OU designation from its ID."""

    try:
        ou = get_ou(ou_id)
        return "%02d-%02d-%02d" % (ou.fakultet, ou.institutt, ou.avdeling)
    except:
        return "ou id=%s" % str(ou_id)

    assert False, "NOTREACHED"
# end ou_id2report


def person_id2report(person_id):
    """Produce a human-friendly Person info from its ID."""

    try:
        const = Factory.get("Constants")()
        p = Factory.get("Person")(database)
        p.find(person_id)

        for ss in ("system_cached",) + cereconf.SYSTEM_LOOKUP_ORDER:
            try:
                return p.get_name(
                    const.human2constant(ss, const.AuthoritativeSystem),
                    const.name_full)
            except Errors.NotFoundError:
                pass

        return "person id=%s" % str(person_id)
    except Errors.NotFoundError:
        return "person id=%s" % str(person_id)

    assert False, "NOTREACHED"
# end person_id2report


def account_id2report(account_id):
    """Produce a human-friendly account designation from its ID."""

    try:
        account = Factory.get("Account")(database)
        account.find(account_id)
        return account.account_name
    except Errors.NotFoundError:
        return "account id=%s" % str(account_id)

    assert False, "NOTREACHED"
# end account_id2report


def fetch_persons(affiliations, source):
    """Collect all persons for this run.

    @param affiliations:
      A sequence of affiliations used as a starting point for collecting
      people (i.e. we collect affiliation information for all people who have
      at least one aff from affiliations).

    @rtype: dict (person_id -> set of (aff, status, ou_id))
    @return:
      Dictionary mapping person_id to sequence of affiliations.
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
            (x["affiliation"], x["status"], x["ou_id"])
            for x in person_affs)

    logger.debug("Collected %d people matching affiliation%s%s",
                 len(result),
                 len(set(affiliations)) != 1 and "s " or " ",
                 ", ".join(set(str(const.PersonAffiliation(x))
                               for x in affiliations)))

    # Alas, we can't look at people alone. A person maybe without an affiliation
    # (say, it has been deleted) whereas his/her account may still have the
    # affiliation. I.e. we need to scan the accounts with affiliations from
    # L{affiliations} AND adjoin the correponding person entries to the result.
    additional = 0
    account = Factory.get("Account")(db)
    for row in account.list_accounts_by_type(affiliation=affiliations):
        person_id = row["person_id"]
        # we've already registered affs for this person...
        if person_id in result:
            continue

        # at this point account_id has the right affs, but person_id does NOT
        # have a single affiliation of the right kind.
        person_affs = person.list_affiliations(person_id=row["person_id"])
        result.setdefault(row["person_id"], set()).update(
            (x["affiliation"], x["status"], x["ou_id"])
            for x in person_affs)
        additional += 1

    logger.debug("Collected %d additional people from users's affiliation%s%s",
                 additional,
                 len(set(affiliations)) != 1 and "s " or " ",
                 ", ".join(set(str(const.PersonAffiliation(x))
                               for x in affiliations)))
    return result
# end fetch_persons


def person_user_mismatch(person2affiliations):
    """Collect mismatching person-user pairs.

    In this particular case we compare (aff, ou_id) only (i.e. affiliation
    status is irrelevant here)
    """

    db = Factory.get("Database")()
    account = Factory.get("Account")(db)

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
            account_affs = set()

            for row in account.list_accounts_by_type(account_id=account_id):
                account_affs.add((row["affiliation"], row["ou_id"]))

            person_affs = set((x[0], x[2]) for x in person2affiliations[person_id])
            if person_affs != account_affs:
                mismatched[account_id] = (person_affs, account_affs)

    return accountless, multi_account, mismatched
# end person_user_mismatch


def prepare_user_mismatch_report(affiliations, accountless, multi_account, mismatched):
    """Generate a person-user mismatch report."""
    db = Factory.get("Database")()
    account = Factory.get("Account")(db)
    const = Factory.get("Constants")(db)

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
                                                 ou_id2report(y))
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
                       (person_id2report(person_id), person_id))

    if multi_account:
        sink.write("People with multiple accounts:\n")
        for person_id in multi_account:
            accounts = multi_account[person_id]
            sink.write("\tPerson %s (id=%s) has %d active accounts:\n%s" %
                       (person_id2report(person_id), person_id, len(accounts),
                        ", ".join(sorted(account_id2report(x)
                                         for x in accounts))))

    if mismatched:
        sink.write("People with mismatched affiliations:\n")
        for account_id in mismatched:
            person_affs, account_affs = mismatched[account_id]
            owner_id = uid2owner(account_id)
            sink.write("\tPerson %s (id=%s)'s affiliations do not match "
                       "account's %s (id=%s) affs: %s != %s\n" %
                       (person_id2report(owner_id),
                        owner_id,
                        account_id2report(account_id),
                        account_id,
                        affs2str(person_affs),
                        affs2str(account_affs)))

    return sink.getvalue()
# end prepare_user_mismatch_report


def groups_matching_user_affs(user_affs, aff2groups):
    """Collect group_ids matching (aff, status, ou_id) in user_affs.

    Return all group_ids where the owner of user_affs must be a member
    according to the current rule set.
    """

    required = set()
    for aff, status, ou_id in user_affs:
        required.add(aff2groups.get((aff, None, None)))
        required.add(aff2groups.get((aff, status, None)))
        required.add(aff2groups.get((aff, None, ou_id)))
        required.add(aff2groups.get((aff, status, ou_id)))

    required.discard(None)
    return required
# end groups_matching_person_affs


def load_group_members(aff2groups):
    """Collect all members of specified groups.

    @return:
      A mapping group_id -> set of (member) entity_ids
    """

    def fetch_group_name(group_id):
        try:
            group.clear()
            group.find(group_id)
            return group.group_name
        except Errors.NotFoundError:
            return ""
    # end fetch_group_name

    db = Factory.get("Database")()
    group = Factory.get("Group")(db)
    result = dict()
    for group_id in aff2groups.itervalues():
        if group_id in result:
            continue

        result[group_id] = set(x["member_id"]
                               for x in group.search_members(group_id=group_id))

    logger.debug("Loaded members for %s group(s) in total", len(result))
    for group_id in result:
        logger.debug("Group %s (id=%s) => %s member(s)",
                     fetch_group_name(group_id), group_id,
                     len(result[group_id]))
    return result
# end load_group_members


def remap_people_to_accounts(person2affiliations):
    """Remap person_id to the corresponding account.

    person2affiliation is a dict from person_id to the set of
    affiliations. This function remaps person_id to account_id and returns a
    similar data structure. Since NMH has a one-to-one correspondance between
    account_ids and person_ids, this is a meaningful operation.
    """

    account = Factory.get("Account")(database)
    result = dict()
    # person_id -> account_id
    person2account = dict((r["owner_id"], r["account_id"])
                          for r in account.search())
    for person_id in person2affiliations:
        value = person2affiliations[person_id]
        if person_id not in person2account:
            logger.info("Person %s (id=%s) has no account",
                        person_id2report(person_id), person_id)
            continue

        # FIXME: copy.deepcopy(value)?
        result[person2account[person_id]] = value

    logger.debug("Remapped %d people->aff-seq to %s account->aff-seq",
                 len(person2affiliations),
                 len(result))
    return result
# end remap_people_to_accounts


def user_group_mismatch(user2affiliations, aff2groups):
    """Return which groups which accounts should be a member of (but aren't).

    @param aff2groups:
      Mapping key -> group_id, where key designates an affiliation
      (i.e. (aff,), (aff,status), (aff,ou_id) or (aff,status,ou_id)).

    @return:
      A dict mapping user_id to a set of group_ids where user_id should
      have been a member.
    """

    # group_id -> set of member_ids
    members = load_group_members(aff2groups)
    # account_id -> set of group_id where account_id should have been a member,
    # but is not
    mismatched_users = dict()

    for account_id in user2affiliations:
        user_affs = user2affiliations[account_id]
        groups_required = groups_matching_user_affs(user_affs, aff2groups)
        missing = set(group_id
                      for group_id in groups_required
                      if account_id not in members[group_id])
        if missing:
            mismatched_users[account_id] = missing

    return mismatched_users
# end user_group_mismatch


def prepare_user_group_mismatch_report(aff2groups, mismatches):
    """Generate a report for user<->group mismatches.

    @aff2groups:
      Data structure mapping affiliations to group memberships.

    @param mismatches:
      A mapping from account_id to a sequence of group_ids where the person
      should have been a member but is not.
    """

    @memoize
    def affkey2string(tpl):
        components = [str(const.PersonAffiliation(tpl[0])),]
        if tpl[1]:
            # aff status' str() grabs affiliation as well.
            components[0] = str(const.PersonAffStatus(tpl[1]))
        if tpl[2]:
            ou = get_ou(tpl[2])
            acronym = ou.get_name_with_language(
                name_variant=const.ou_name_acronym,
                name_language=const.language_nb,
                default="")
            components.append("@%s (%s)" % (ou_id2report(ou.entity_id),
                                            acronym))
        return "".join(components)
    # end affkey2string

    const = Factory.get("Constants")()
    sink = StringIO()
    sink.write("User-group mismatch report for affiliations %s\n" %
               ", ".join(sorted(set(affkey2string(x)
                                    for x in aff2groups))))
    sink.write("\nThere are %s accounts in total who are not members of "
               "all groups they should be members of:\n\n" % len(mismatches))

    for account_id in mismatches:
        missing_groups = mismatches[account_id]
        missing = ", ".join("group %s (id=%s)" % (g.group_name, g.entity_id)
                            for g in (get_group(x) for x in missing_groups))
        sink.write("* Account %s (id=%s) should have been a member of: "
                   "%s\n" % (account_id2report(account_id), account_id, missing))

    return sink.getvalue()
# end prepare_user_group_mismatch_report


def cli_quadruple2dict(seq):
    """Map human-friendly command-line args to an internal data structure.

    Human launch this job with arguments formatted thus::

      --person-group-match ANSATT:tekadm:sko:group1
      --person-group-match ANSATT:::group2

    i.e. the format is <affiliation>:<status>:<ou>:<group>

    The idea is that humans can specify each of the 4 components in any
    reasonable format (by name or id) and this method remaps that into a
    suitable data structure (key -> group_id, where key is a tuple (aff,
    status, ou_id). 

    <status> may be skipped as may <ou>. Affiliation and group and compulsory.

    The dict itself looks like {key: group_id}. The key is (aff, status,
    ou_id), where status and ou_id may be None.
    """

    def human2affstatus(ident):
        if not ident:
            return None

        status = const.human2constant(ident, const.PersonAffStatus)
        if status:
            return status

        # Final attempt, look for substring match. It's quite fishy, thus not
        # exactly official:
        result = list()
        for cnst in const.fetch_constants(const.PersonAffStatus):
            if ident in str(cnst):
                result.append(cnst)

        if len(result) == 1:
            return result[0]

        assert False, "Could not locate aff status for %s" % (ident,)
    # end human2affstatus

    const = Factory.get("Constants")()
    db = Factory.get("Database")()
    ou = Factory.get("OU")(db)
    split_points = 3
    result = dict()
    for item in seq:
        components = item.split(":", split_points)
        if len(components) != split_points+1:
            logger.warn("Defective item = %s. Skipped", item)

        affiliation, status, ou, group = components

        affiliation = const.human2constant(affiliation, const.PersonAffiliation)
        if status:
            status = human2affstatus(status)
        if ou:
            ou = get_ou(ou)

        group = get_group(group)

        key = [int(affiliation), None, None]
        if status:
            key[1] = int(status)
        if ou:
            key[2] = int(ou.entity_id)

        key = tuple(key)
        if key in result:
            logger.error("Multiple values for key %s. Group %s (id=%s) ignored",
                         key, group.group_name, group.entity_id)
            continue

        result[tuple(key)] = group.entity_id

    return result
# end cli_quadruple2dict


def send_report(report, subject, to, cc=None):
    """E-mail a generated report to the designated recipients."""

    message_width = 76
    wrapper = textwrap.TextWrapper(width=message_width,
                                   subsequent_indent="  ",)
    pretty_message = "\n".join(wrapper.fill(x)
                               for x in report.split("\n"))
    sendmail(to,
             "cerebrum-nmh@usit.uio.no", # From:
             subject,
             pretty_message,
             cc=cc)
# end send_report


def main(argv):
    opts, junk = getopt.getopt(argv[1:],
                               "g:u:s:",
                               ("user-group-mismatch=",
                                "person-user-mismatch=",
                                "source-system=",
                                "to=",
                                "cc=",
                                "subject="))
    group_mismatch = set()
    user_mismatch = set()
    source_system = None
    const = Factory.get("Constants")()
    recipient = subject = cc_recipient = None
    for option, value in opts:
        if option in ("-u", "--person-user-mismatch",):
            user_mismatch.add(value)
        elif option in ("-s", "--source-system",):
            source_system = const.human2constant(value,
                                                 const.AuthoritativeSystem)
        elif option in ("-g", "--user-group-mismatch",):
            group_mismatch.add(value)
        elif option in ("--to",):
            recipient = value
        elif option in ("--subject",):
            subject = value
        elif option in ("--cc",):
            cc_recipient = value

    assert source_system is not None, "Missing source system"

    reports = []
    if group_mismatch:
        group_mismatch_rules = cli_quadruple2dict(group_mismatch)
        # The first element of every key is always the affilation
        affiliations = tuple(x[0] for x in group_mismatch_rules)
        persons = fetch_persons(affiliations, source_system)
        accounts = remap_people_to_accounts(persons)
        mismatched = user_group_mismatch(accounts, group_mismatch_rules)
        reports.append(prepare_user_group_mismatch_report(group_mismatch_rules,
                                                          mismatched))
    if user_mismatch:
        affiliations = tuple(const.human2constant(x, const.PersonAffiliation)
                             for x in user_mismatch)
        persons = fetch_persons(affiliations, source_system)
        reports.append(prepare_user_mismatch_report(affiliations,
                                                    *person_user_mismatch(persons)))

    if reports:
        if recipient and subject:
            send_report("\n".join(reports),
                        subject,
                        recipient,
                        cc_recipient)
        else:
            message_width = 76
            wrapper = textwrap.TextWrapper(width=message_width,
                                           subsequent_indent="  ",)
            pretty_message = "\n".join(wrapper.fill(x)
                                       for x in "\n".join(reports).split("\n"))
            logger.debug("Report to send:\n%s", pretty_message)
# end main


if __name__ == "__main__":
    logger = Factory.get_logger("cronjob")
    main(sys.argv[:])
