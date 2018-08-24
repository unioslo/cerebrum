#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2010-2018 University of Oslo, Norway
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

""" Report breaches of business rules for person/account/group population.

During a meeting on 2010-02-23, NMH expressed an interest in an automatic
warning system where they receive a weekly report about people/accounts where
there is an affiliation mismatch. Since NMH has 1 person = 1 account policy in
place, there is at most 1 account to check per person.

Later, this has been extended by NMH to include information about mismatches
between affiliations and group memberships.

A typical run for NMH would look something like this:

  python report-mismatched-users.py \\
         -s SAP \\
         -u ANSATT \\
         -g ANSATT:tekadm:023200:DPIT \\
         -g ANSATT:tekadm:023100:STUDIEADMIN \\
         -g ANSATT:vitenskapelig:011550:fagsekimprofolk \\
         -g ANSATT:vitenskapelig:011560:fagsekmusped \\
         -g ANSATT:tekadm:024000:BIBLIOTEKARENE \\
         -g ANSATT:tekadm:023400:Informasjon \\
         -g ANSATT::011570:fagsekmusteori \\
         -g ANSATT::011530:fagsekakkom \\
         -g ANSATT:vitenskapelig:011510:fagsekblas \\
         -g ANSATT:vitenskapelig:011540:fagsekdir \\
         -g ANSATT:vitenskapelig:011520:fagsekstryk

-u lists the affiliations to consider for person-user mismatches.
-g lists groups to scan for memberships based on affiliations.

Multiple options of either kind may be provided.
"""
from __future__ import absolute_import, print_function, unicode_literals

import argparse
import collections
import itertools
import logging
import sys
import textwrap
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formatdate
from io import StringIO

import flanker.addresslib.address
import six

import cereconf
import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import ParserContext, UnicodeType, codec_type, get_constant
from Cerebrum.utils.email import send_message
from Cerebrum.utils.funcwrap import memoize


logger = logging.getLogger(__name__)


@memoize
def get_ou(db, ou_id):
    "Fetch an OU based on its id (stedkode, acronym or entity_id)."
    ou = Factory.get("OU")(db)
    ou.find(ou_id)
    return ou


@memoize
def get_person(db, person_id):
    pe = Factory.get("Person")(db)
    pe.find(person_id)
    return pe


@memoize
def get_account(db, account_id):
    ac = Factory.get("Account")(db)
    ac.find(account_id)
    return ac


@memoize
def get_group(db, group_id):
    gr = Factory.get("Group")(db)
    gr.find(group_id)
    return gr


@memoize
def get_lookup_order(db):
    co = Factory.get("Constants")(db)
    return [
        sys for sys in itertools.chain(
            [co.system_cached],
            (co.human2constant(c, co.AuthoritativeSystem)
             for c in cereconf.SYSTEM_LOOKUP_ORDER))
        if sys is not None]


@memoize
def format_ou(ou):
    """Produce a human-friendly OU designation."""
    try:
        return "%02d-%02d-%02d" % (ou.fakultet, ou.institutt, ou.avdeling)
    except:
        return "ou id=%s" % str(ou.entity_id)


@memoize
def format_account(ac):
    """Produce a human-friendly OU designation."""
    return ac.account_name


@memoize
def format_person(pe):
    co = Factory.get("Constants")(pe._db)
    for source_system in get_lookup_order(pe._db):
        try:
            return pe.get_name(source_system, co.name_full)
        except Errors.NotFoundError:
            return 'person id=%s' % str(pe.entity_id)


def fetch_persons(db, source_system, affiliations):
    """Collect all persons for this run.

    @param affiliations:
      A sequence of affiliations used as a starting point for collecting
      people (i.e. we collect affiliation information for all people who have
      at least one aff from affiliations).

    @rtype: dict (person_id -> set of (aff, status, ou_id))
    @return:
      Dictionary mapping person_id to sequence of affiliations.
    """
    pe = Factory.get("Person")(db)
    ac = Factory.get("Account")(db)
    result = dict()
    for row in pe.list_affiliations(affiliation=affiliations,
                                    source_system=source_system,
                                    include_deleted=False):
        # FIXME: What about source system here?
        person_affs = pe.list_affiliations(person_id=row["person_id"])
        result.setdefault(row["person_id"], set()).update(
            (x["affiliation"], x["status"], x["ou_id"])
            for x in person_affs)

    logger.debug("Collected %d people matching affiliation%s %s",
                 len(result),
                 len(set(affiliations)) != 1 and "s" or "",
                 ", ".join(set(six.text_type(x) for x in affiliations)))

    # Alas, we can't look at people alone. A person maybe without an aff
    # (say, it has been deleted) whereas his/her account may still have the
    # affiliation. I.e. we need to scan the accounts with affiliations from
    # L{affiliations} AND adjoin the correponding person entries to the result.
    additional = 0
    for row in ac.list_accounts_by_type(affiliation=affiliations):
        person_id = row["person_id"]
        # we've already registered affs for this person...
        if person_id in result:
            continue

        # at this point account_id has the right affs, but person_id does NOT
        # have a single affiliation of the right kind.
        person_affs = pe.list_affiliations(person_id=person_id)
        result.setdefault(person_id, set()).update(
            (x["affiliation"], x["status"], x["ou_id"])
            for x in person_affs)
        additional += 1

    logger.debug("Collected %d additional people from user affiliation%s %s",
                 additional,
                 len(set(affiliations)) != 1 and "s" or "",
                 ", ".join(set(six.text_type(x) for x in affiliations)))
    return result


def person_user_mismatch(db, person2affiliations):
    """Collect mismatching person-user pairs.

    In this particular case we compare (aff, ou_id) only (i.e. affiliation
    status is irrelevant here)
    """
    account = Factory.get("Account")(db)

    accountless = set()
    multi_account = collections.defaultdict(set)
    mismatched = dict()

    for person_id in person2affiliations:
        accounts = list(account.list_accounts_by_owner_id(person_id,
                                                          filter_expired=True))
        if len(accounts) < 1:
            accountless.add(person_id)
        elif len(accounts) > 1:
            multi_account[person_id].update(x["account_id"] for x in accounts)
        else:
            account_id = accounts[0]["account_id"]
            account_affs = set()

            for row in account.list_accounts_by_type(account_id=account_id):
                account_affs.add((row["affiliation"], row["ou_id"]))

            person_affs = set((x[0], x[2])
                              for x in person2affiliations[person_id])
            if person_affs != account_affs:
                mismatched[account_id] = (person_affs, account_affs)

    return accountless, dict(multi_account), mismatched


def format_user_report(db, affiliations, accountless, multi_account,
                         mismatched):
    """Generate a person-user mismatch report."""
    co = Factory.get('Constants')(db)

    def uid2owner(account_id):
        ac = get_account(db, account_id)
        return ac.owner_id

    def affs2str(affiliations):
        return "{" + ", ".join(
            sorted("%s@%s" % (six.text_type(co.PersonAffiliation(x)),
                              format_ou(get_ou(db, y)))
                   for x, y in affiliations)) + "}"

    sink = StringIO()
    sink.write("Person-user mismatch report for affiliations %s\n" %
               ", ".join(sorted(six.text_type(co.PersonAffiliation(x))
                                for x in affiliations)))
    sink.write("Summary:\n")
    sink.write("%d people with no active accounts\n"
               "%d people with multiple active accounts\n"
               "%s people with person<->account affiliation mismatch\n" %
               (len(accountless), len(multi_account), len(mismatched)))

    if accountless:
        sink.write("People no active accounts:\n")
        for person_id in accountless:
            sink.write("\tPerson %s (id=%s) has no active accounts\n" %
                       (format_person(get_person(db, person_id)), person_id))

    if multi_account:
        sink.write("People with multiple accounts:\n")
        for person_id in multi_account:
            accounts = multi_account[person_id]
            sink.write("\tPerson %s (id=%s) has %d active accounts:\n%s" %
                       (format_person(get_person(db, person_id)),
                        person_id,
                        len(accounts),
                        ", ".join(
                           sorted(format_account(get_account(db, x))
                                  for x in accounts))))

    if mismatched:
        sink.write("People with mismatched affiliations:\n")
        for account_id in mismatched:
            person_affs, account_affs = mismatched[account_id]
            owner_id = uid2owner(account_id)
            sink.write("\tPerson %s (id=%s)'s affiliations do not match "
                       "account's %s (id=%s) affs: %s != %s\n" %
                       (format_person(get_person(db, owner_id)),
                        owner_id,
                        format_account(get_account(db, account_id)),
                        account_id,
                        affs2str(person_affs),
                        affs2str(account_affs)))

    return sink.getvalue()


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


def load_group_members(db, aff2groups):
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

    group = Factory.get("Group")(db)
    result = dict()
    for group_id in aff2groups.itervalues():
        if group_id in result:
            continue

        result[group_id] = set(
            x["member_id"]
            for x in group.search_members(group_id=group_id))

    logger.debug("Loaded members for %s group(s) in total", len(result))
    for group_id in result:
        logger.debug("Group %s (id=%s) => %s member(s)",
                     fetch_group_name(group_id), group_id,
                     len(result[group_id]))
    return result


def remap_people_to_accounts(db, person2affiliations):
    """Remap person_id to the corresponding account.

    person2affiliation is a dict from person_id to the set of
    affiliations. This function remaps person_id to account_id and returns a
    similar data structure. Since NMH has a one-to-one correspondance between
    account_ids and person_ids, this is a meaningful operation.
    """
    result = dict()

    for person_id in person2affiliations:
        pe = get_person(db, person_id)
        account_id = pe.get_primary_account()
        if account_id is None:
            logger.info("Person %s (id=%s) has no account",
                        format_person(get_person(db, person_id)), person_id)
            continue
        result[account_id] = person2affiliations[person_id]

    logger.debug("Remapped %d people->aff-seq to %s account->aff-seq",
                 len(person2affiliations),
                 len(result))
    return result


def user_group_mismatch(db, user2affiliations, rules):
    """Return which groups which accounts should be a member of (but aren't).

    @param aff2groups:
      Mapping key -> group_id, where key designates an affiliation
      (i.e. (aff,), (aff,status), (aff,ou_id) or (aff,status,ou_id)).

    @return:
      A dict mapping user_id to a set of group_ids where user_id should
      have been a member.
    """

    # group_id -> set of member_ids
    members = load_group_members(db, rules)
    # account_id -> set of group_id where account_id should have been a member,
    # but is not
    mismatched_users = dict()

    for account_id in user2affiliations:
        user_affs = user2affiliations[account_id]
        groups_required = groups_matching_user_affs(user_affs, rules)
        missing = set(group_id
                      for group_id in groups_required
                      if account_id not in members[group_id])
        if missing:
            mismatched_users[account_id] = missing

    return mismatched_users


def format_group_report(db, rules, mismatches):
    """Generate a report for user<->group mismatches.

    @rules:
      Data structure mapping affiliations to group memberships.

    @param mismatches:
      A mapping from account_id to a sequence of group_ids where the person
      should have been a member but is not.
    """
    co = Factory.get("Constants")(db)

    @memoize
    def affkey2string(tpl):
        components = [six.text_type(co.PersonAffiliation(tpl[0]))]
        if tpl[1]:
            # aff status' str() grabs affiliation as well.
            components[0] = six.text_type(co.PersonAffStatus(tpl[1]))
        if tpl[2]:
            ou = get_ou(db, tpl[2])
            acronym = ou.get_name_with_language(
                name_variant=co.ou_name_acronym,
                name_language=co.language_nb,
                default="")
            components.append("@%s (%s)" % (format_ou(ou), acronym))
        return "".join(components)

    sink = StringIO()
    sink.write("User-group mismatch report for affiliations %s\n" %
               ", ".join(sorted(set(affkey2string(x)
                                    for x in rules))))
    sink.write("\nThere are %s accounts in total who are not members of "
               "all groups they should be members of:\n\n" % len(mismatches))

    for account_id in mismatches:
        account = get_account(db, account_id)
        missing_groups = mismatches[account_id]
        missing = ", ".join(
            "group %s (id=%s)" % (g.group_name, g.entity_id)
            for g in (get_group(db, x) for x in missing_groups))
        sink.write("* Account %s (id=%s) should have been a member of: "
                   "%s\n" % (format_account(account), account_id, missing))

    return sink.getvalue()


def make_rules(db, parser, tuple_rules, arg):
    """ Validate and normalize the affiliation to group tuples.

    :return dict:
        A mapping from tuple(affiliation_code, status_code, ou_id) to group_id
    """
    co = Factory.get("Constants")(db)

    def _get_aff(const_value):
        const = co.human2constant(const_value, co.PersonAffiliation)
        if const:
            return const
        raise ValueError("Invalid affiliation %r" % (const_value, ))

    def _get_status(affiliation, const_value):
        const = None
        for c in co.fetch_constants(co.PersonAffStatus):
            if (c.affiliation == affiliation and
                    c.status_str == const_value):
                const = c
                break
        else:
            c = co.human2constant(const_value, co.PersonAffStatus)
            if c and c.affiliation == affiliation:
                const = c
        if not const:
            raise ValueError("Invalid affiliation status %r" % (const_value, ))
        return const

    def _get_ou(ident):
        ou = Factory.get("OU")(db)
        if ident.isdigit() and len(ident) == 6:
            ou.find_stedkode(int(ident[:2]),
                             int(ident[2:4]),
                             int(ident[4:]),
                             cereconf.DEFAULT_INSTITUSJONSNR)
        elif ident.isdigit():
            ou.find(int(ident))
        else:
            # Assume it's an acronym
            result = ou.search_name_with_language(
                entity_type=co.entity_ou,
                name_variant=co.ou_name_acronym,
                name=ident,
                name_language=co.language_nb,
                exact_match=False)
            if len(result) > 1:
                raise ValueError("Multiple OUs matching %r" % (ident, ))
            ou.find(result[0]["ou_id"])
        return ou

    def _get_group(ident):
        group = Factory.get("Group")(db)
        if ident.isdigit():
            group.find(int(ident))
        else:
            group.find_by_name(ident)
        return group

    result = dict()

    for rule in tuple_rules:
        with ParserContext(parser, arg):
            affiliation = _get_aff(rule[0])
            group = _get_group(rule[3])

            key = tuple((
                int(affiliation),
                int(_get_status(affiliation, rule[1])) if rule[1] else None,
                int(_get_ou(rule[2]).entity_id) if rule[2] else None,
            ))

        if key in result:
            logger.error(
                "Multiple values for key %s. Group %s (id=%s) ignored",
                key, group.group_name, group.entity_id)
            continue

        result[key] = group.entity_id

    return result


def format_report(report, max_width=76, indent="  "):
    wrapper = textwrap.TextWrapper(width=max_width, subsequent_indent=indent)
    return "\n".join(wrapper.fill(x) for x in report.split("\n"))


def make_group_report(db, source_system, rules):
    logger.info("Generating affiliation group membership report")
    affiliations = tuple(x[0] for x in rules)
    persons = fetch_persons(db, source_system, affiliations)

    accounts = remap_people_to_accounts(db, persons)
    mismatched = user_group_mismatch(db, accounts, rules)
    return format_group_report(db, rules, mismatched)


def make_user_report(db, source_system, affiliations):
    logger.info("Generating person-user reports")
    persons = fetch_persons(db, source_system, affiliations)

    (acc_none, acc_multi, acc_mismatch) = person_user_mismatch(db, persons)
    return format_user_report(db, affiliations, acc_none, acc_multi,
                              acc_mismatch)


def install_mail_subparser(parser):
    """ Adds email arguments to a parser.

    :return callable:
        A function that checks if all the required options are given, iff any
        email options are given.
    """
    # TODO: Generalize and put into argutils?
    return validate


def send_report(args, report):
    """E-mail a generated report to the designated recipients."""
    charset = args.mail_codec.name
    msg = MIMEText(report, _charset=charset)
    msg['Subject'] = Header(args.mail_subject.strip(), charset)
    msg['From'] = args.mail_from.strip().encode('ascii')
    msg['To'] = ', '.join(addr.strip()
                          for addr in args.mail_to).encode('ascii')
    if args.mail_cc:
        msg['Cc'] = ', '.join(args.mail_cc).encode('ascii')
    msg['Date'] = formatdate(localtime=True)

    return send_message(
        msg,
        from_addr=args.mail_from.strip(),
        to_addrs=list(itertools.chain(args.mail_to, args.mail_cc)))


def write_report(stream, report):
    stream.write(report)
    stream.write("\n")
    stream.flush()


def group_rule(value):
    parts = value.split(':')
    return tuple(
        parts.pop(0).strip() if len(parts) else ''
        for _ in range(4))


def email_address(value):
    value = value.decode('ascii').strip()
    if flanker.addresslib.address.is_email(value):
        return value
    raise ValueError('invalid email address')


DEFAULT_FILE_ENCODING = 'utf-8'
DEFAULT_MAIL_ENCODING = 'utf-8'
DEFAULT_MAIL_FROM = 'cerebrum-nmh@usit.uio.no'


def main(inargs=None):
    parser = argparse.ArgumentParser(description='')

    source_args = parser.add_argument_group('Report parameters')
    ss_arg = source_args.add_argument(
        '-s', '--source-system',
        required=True)
    affs_arg = source_args.add_argument(
        '-u', '--person-user-mismatch',
        action='append',
        default=[],
        dest='user_select',
        help='Report on user accounts for persons with %(metavar)s',
        metavar='AFFILIATION')
    rule_arg = source_args.add_argument(
        '-g', '--user-group-mismatch',
        action='append',
        default=[],
        dest='group_select',
        type=group_rule,
        help='Report on users missing for the affiliation -> group rule',
        metavar='AFF:status:sko:group')

    file_args = parser.add_argument_group('Report file')
    file_args.add_argument(
        '-f', '--output-file',
        type=argparse.FileType('w'),
        default=None,
        help="Write report to file, '-' for stdout")
    file_args.add_argument(
        '-e', '--output-encoding',
        type=codec_type,
        default=DEFAULT_FILE_ENCODING,
        help="Write file using the given encoding (default: %(default)s)")

    mail_args = parser.add_argument_group('Report email')
    to_arg = mail_args.add_argument(
        '--to',
        action='append',
        default=[],
        dest='mail_to',
        type=email_address,
        help="Send an email report to %(metavar)s",
        metavar='ADDR')
    cc_arg = mail_args.add_argument(
        '--cc',
        action='append',
        default=[],
        dest='mail_cc',
        type=email_address,
        help="Also send email report to %(metavar)s",
        metavar='ADDR')
    from_arg = mail_args.add_argument(
        '--from',
        default=DEFAULT_MAIL_FROM,
        dest='mail_from',
        type=email_address,
        help="Send reports from %(metavar)s",
        metavar='ADDR')
    subj_arg = mail_args.add_argument(
        '--subject',
        dest='mail_subject',
        type=UnicodeType(),
        help="Also send email report to %(metavar)s",
        metavar='ADDR')
    mail_args.add_argument(
        '--encoding',
        dest='mail_codec',
        type=codec_type,
        default=DEFAULT_MAIL_ENCODING,
        help="Charset to use for email (default: %(default)s")

    def check_mail_args(args):
        args_set = [arg for arg in (to_arg, from_arg, subj_arg, cc_arg)
                    if getattr(args, arg.dest) != arg.default]
        args_missing = [arg for arg in (to_arg, from_arg, subj_arg)
                        if not bool(getattr(args, arg.dest))]
        if len(args_set) > 0 and len(args_missing) > 0:
            parser.error(argparse.ArgumentError(
                args_set[0],
                "missing {0}".format(
                    ', '.join('/'.join(m.option_strings)
                              for m in args_missing))))
        return len(args_set) > 0

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    send_mail = check_mail_args(args)

    if not any((args.user_select, args.group_select)):
        parser.error("No selections given - nothing to do")

    if not any((send_mail, args.output_file)):
        parser.error("No destination for report - nothing to do")

    db = Factory.get("Database")()
    co = Factory.get("Constants")(db)

    source_system = get_constant(db, parser, co.AuthoritativeSystem,
                                 args.source_system, ss_arg)
    user_affs = [get_constant(db, parser, co.PersonAffiliation, c, affs_arg)
                 for c in args.user_select]
    group_rules = make_rules(db, parser, args.group_select, rule_arg)

    # Start of script
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start of script %s', parser.prog)
    logger.debug('args: %r', args)
    logger.info("Affiliations for user report: %r", args.user_select)
    logger.info("Rules for group report: %r", args.group_select)
    logger.info("Sending email report: %r", send_mail)
    if send_mail:
        logger.debug("mail to      : %r", args.mail_to)
        logger.debug("mail cc      : %r", args.mail_cc)
        logger.debug("mail from    : %r", args.mail_from)
        logger.debug("mail subject : %r", args.mail_subject)

    reports = []

    if group_rules:
        reports.append(make_group_report(db, source_system, group_rules))

    if user_affs:
        reports.append(make_user_report(db, source_system, user_affs))

    if not reports:
        logger.warning("Nothing to report")

    report = format_report("\n".join(reports))

    if reports and send_mail:
        send_report(args, report)

    if args.output_file:
        write_report(args.output_file, report)
        if args.output_file is not sys.stdout:
            args.output_file.close()
        logger.info("Wrote report to %r", args.output_file.name)


if __name__ == "__main__":
    main()
