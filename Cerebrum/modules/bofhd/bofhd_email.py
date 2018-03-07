# -*- coding: utf-8 -*-
#
# Copyright 2014-2018 University of Oslo, Norway
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
""" Email commands and email utils for BofhdExtensions.

Please don't blame me for the WTF-ness in this file. It's mostly from
bofhd_uio_cmds.

The orignal commands are more or less available in:
    Cerebrum/modules/no/uio/bofhd_uio_cmds.py
    svn @ rev 17863
    git @ 1425aeab1eee56208b778afc156597f641fb9eed

There's a lot of cross dependencies between the email commands and the
lookup/helper methods, which is why everything is mangled together in this one
module.

This could look a lot better if we re-factored the helper methods, and made
some sort of callback system, where each email target type could register how
to handle addresses and targets of that type.

"""
import pickle
import re

from flanker.addresslib import address as email_validator
from mx import DateTime

import cereconf

from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum.modules import Email

from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.cmd_param import (
    AccountName,
    Affiliation,
    Command,
    EmailAddress,
    FormatSuggestion,
    GroupName,
    Integer,
    OU,
    Parameter,
    PersonId,
    PersonName,
    SimpleString,
    YesNo,
)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.modules.bofhd.utils import BofhdRequests


def format_day(field):
    """ Format day, for FormatSuggestion. """
    fmt = "yyyy-MM-dd"  # 10 characters wide
    return ":".join((field, "date", fmt))


def check_email_address(address):
    """ Check email address syntax.

    Accepted syntax:
        - <localpart>@<domain>
            localpart cannot contain @ or whitespace
            domain cannot contain @ or whitespace
            domain must have at least one '.'
        - Any string where a substring wrapped in <> brackets matches the
          above rule.
        - Valid examples: jdoe@example.com
                          <jdoe>@<example.com>
                          Jane Doe <jdoe@example.com>

    NOTE: Raises CerebrumError if address is invalid

    @rtype: str
    @return: address.strip()

    """
    address = address.strip()
    if address.find("@") == -1:
        raise CerebrumError(
            "E-mail addresses must include the domain name")

    error_msg = ("Invalid e-mail address: %s\n"
                 "Valid input:\n"
                 "jdoe@example.com\n"
                 "<jdoe>@<example.com>\n"
                 "Jane Doe <jdoe@example.com>" % address)
    # Check if we either have a string consisting only of an address,
    # or if we have an bracketed address prefixed by a name. At last,
    # verify that the email is RFC-compliant.
    if not ((re.match(r'[^@\s]+@[^@\s.]+\.[^@\s]+$', address) or
            re.search(r'<[^@>\s]+@[^@>\s.]+\.[^@>\s]+>$', address))):
        raise CerebrumError(error_msg)

    # Strip out angle brackets before running proper validation, as the
    # flanker address parser gets upset if domain is wrapped in them.
    val_adr = address.replace('<', '').replace('>', '')
    if not email_validator.parse(val_adr):
        raise CerebrumError(error_msg)
    return address


def split_address(address):
    """Split an e-mail address into local part and domain.

    :param str address:
    :return tuple:
        A tuple with the localpart and domain strings
    """
    if address.count('@') == 0:
        raise CerebrumError("Email address (%r) must include domain" % address)
    try:
        local, domain = address.split('@')
    except ValueError:
        raise CerebrumError("Email address (%r) must contain only one @" %
                            address)
    if (address != address.lower()
            and domain not in cereconf.LDAP['rewrite_email_domain']):
        raise CerebrumError("Email address (%r) can't contain upper case "
                            "letters" % address)
    return local, domain


class BofhdEmailBase(BofhdCommandBase):
    """ This is the common base for bofhd email commands. """

    @classmethod
    def get_help_strings(cls):
        # TODO: Get control of the arg help strings used, and split up
        # bofhd.help, bofhd.bofhd_core_help in usable chunks
        _, _, args = get_help_strings()
        return merge_help_strings(
            ({}, {}, args),
            ({}, {}, HELP_EMAIL_ARGS))

    #
    # Email{Target,Address,Domain} related helper functions.
    #
    def _get_email_domain_from_str(self, domain_str):
        """ Get EmailDomain from str. """
        ed = Email.EmailDomain(self.db)
        try:
            ed.find_by_domain(domain_str)
        except Errors.NotFoundError:
            raise CerebrumError("Unknown e-mail domain %r" % domain_str)
        return ed

    def _get_server_from_ident(self, ident):
        """ Get EmailServer object by identifier (name or id). """
        es = Email.EmailServer(self.db)
        try:
            if isinstance(ident, (int, long)):
                es.find(ident)
            else:
                es.find_by_name(ident)
            return es
        except Errors.NotFoundError:
            raise CerebrumError("Unknown email server (ident=%r)" % ident)

    def _get_server_from_address(self, address):
        """ Get EmailServer from address (EmailAddress or str) """
        et = self._get_email_target_for_address(address)
        try:
            host = Email.EmailServer(self.db)
            host.find(et.email_server_id)
        except Errors.NotFoundError:
            raise CerebrumError("Uknown email server"
                                " (server_id=%r, address=%r)" %
                                (et.email_server_id, address))
        return host

    def _get_email_address_from_str(self, email_str):
        """ Get EmailAddress from string. """
        if not isinstance(email_str, str):
            raise CerebrumError(
                "Invalid argument type: %s" % type(email_str))
        elif email_str.count('@') != 1:
            raise CerebrumError("Invalid email address: %s" % email_str)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_address(email_str)
        except Errors.NotFoundError:
            raise CerebrumError("No such address: '%s'" % email_str)
        return ea

    def _get_email_address_for_account(self, user_or_uname):
        """ Get primary EmailAddress for account. """
        et = self._get_email_target_for_account(user_or_uname)
        ea = Email.EmailAddress(self.db)
        try:
            epa = Email.EmailPrimaryAddressTarget(self.db)
            epa.find(et.entity_id)
            ea.find(epa.email_primaddr_id)
        except Errors.NotFoundError:
            if not isinstance(user_or_uname, str):
                user_or_uname = user_or_uname.account_name
            raise CerebrumError(
                "No primary address for '%s'" % user_or_uname)

        return ea

    def _get_email_target_for_account(self, user_or_uname):
        """ Get EmailTarget for an account (account-object or user name). """
        acc = user_or_uname
        if isinstance(acc, str):
            acc = self._get_account(user_or_uname, idtype='name')
        elif not isinstance(acc, self.Account_class):
            raise CerebrumError(
                "Invalid argument type: %s" % type(user_or_uname))

        try:
            et = Email.EmailTarget(self.db)
            et.find_by_target_entity(acc.entity_id)
        except Errors.NotFoundError:
            raise CerebrumError("No email target for %s (id:%s)" % (
                acc.account_name, acc.entity_id))

        return et

    def _get_email_target_for_address(self, address):
        """ Get EmailTarget for an email address (str or EmailAddress). """
        ea = address
        if not isinstance(ea, Email.EmailAddress):
            ea = self._get_email_address_from_str(address)

        et = Email.EmailTarget(self.db)
        try:
            et.find(ea.email_addr_target_id)
        except Errors.NotFoundError:
            raise CerebrumError("No email target for EmailAddress")
        return et

    def _get_email_target_and_address(self, uname_or_addr):
        """ Get a tuple of (EmailTarget, EmailAddress). """
        try:
            if uname_or_addr.count('@') < 1:
                ea = self._get_email_address_for_account(uname_or_addr)
            else:
                ea = self._get_email_address_from_str(uname_or_addr)
            et = self._get_email_target_for_address(ea)
            return et, ea
        except Errors.NotFoundError:
            pass

        raise CerebrumError("Could not find address '%s'" % uname_or_addr)

    def _get_email_target_and_account(self, uname_or_addr):
        """ Get a target and account from a username or email-address. """
        if uname_or_addr.count('@') < 1:
            # Assume account_name, must exist
            acc = self._get_account(uname_or_addr, idtype='name')
            et = self._get_email_target_for_account(acc)
            return et, acc

        # Assume email address
        acc = None
        et = self._get_email_target_for_address(uname_or_addr)
        if et.email_target_type in (self.const.email_target_account,
                                    self.const.email_target_deleted):
            acc = self._get_account(et.email_target_entity_id, idtype='id')
        return et, acc

    def _get_valid_email_addrs(self, et, special=False, sort=False):
        """ Return a list of all valid e-mail addresses for an EmailTarget.

        Keep special domain names intact if special is True, otherwise re-write
        them into real domain names.

        """
        addrs = [(r['local_part'], r['domain'])
                 for r in et.get_addresses(special=special)]
        if sort:
            addrs.sort(lambda x, y: cmp(x[1], y[1]) or cmp(x[0], y[0]))
        return ["%s@%s" % a for a in addrs]

    def _remove_email_address(self, et, address):
        """ Remove an email address from an email target.

        If the target has no remaining addresses, the target is removed as
        well.

        @rtype: bool
        @returns: True if the target was deleted, False if only the address was
            deleted.

        """
        ea = self._get_email_address_from_str(address)

        if ea.get_target_id() != et.entity_id:
            raise CerebrumError("<%s> is not associated with that target" %
                                address)
        addresses = et.get_addresses()
        epat = Email.EmailPrimaryAddressTarget(self.db)
        try:
            epat.find(et.entity_id)
            primary = epat.email_primaddr_id
        except Errors.NotFoundError:
            primary = None
        if primary == ea.entity_id:
            if len(addresses) == 1:
                # We're down to the last address, remove the primary
                epat.delete()
            else:
                raise CerebrumError(
                    "Can't remove primary address <%s>" % address)
        ea.delete()
        if len(addresses) > 1:
            # there is at least one address left
            return False
        # clean up and remove the target.
        et.delete()
        return True

    def _set_email_primary_address(self, et, ea):
        """ Set an email address as primary address. """
        epat = Email.EmailPrimaryAddressTarget(self.db)
        try:
            epat.find(et.entity_id)
        except Errors.NotFoundError:
            epat.clear()
            epat.populate(ea.entity_id, parent=et)
        else:
            if epat.email_primaddr_id == ea.entity_id:
                return False
            epat.email_primaddr_id = ea.entity_id
        epat.write_db()
        return True

    def _forward_exists(self, fw, addr):
        """ Check if a forward address exists in an EmailForward. """
        for r in fw.get_forward():
            if r['forward_to'] == addr:
                return True
        return False

    def _email_address_to_str(self, address):
        """ Get string from EmailAddress.

        NOTE: Special domain names are not rewritten.

        """
        if not isinstance(address, Email.EmailAddress):
            raise ValueError("Unknown argument type %s" % type(address))
        ed = Email.EmailDomain(self.db)
        ed.find(address.email_addr_domain_id)
        return ("%s@%s" % (address.email_addr_local_part,
                           ed.email_domain_name))

    def _get_address(self, target):
        """ Get an address for an EnamlAddress or EmailTarget.

        Will eventually translate an EmailAddress to string. If the target is
        an EmailTarget (or EmailPrimaryAddressTarget), we'll look up the
        (primary target and) EmailAddress for that target.

        @type target:
            EmailPrimaryAddressTarget, EmailTarget, EmailAddress or numerical.
        @param target:
            EmailTarget -> PRIMARY address, or Errors.NotFoundError
            EmailPrimaryAddressTarget or id -> address or Errors.NotFoundError
            EmailAddress -> address or Errors.NotFoundError
            other -> ValueError

        @rtype: string
        @return: The found email address as string.

        NOTE: Special domain names are not rewritten.
              Raises Errors.NotFoundError if no address can be found

        """
        tmp = target
        if isinstance(target, (int, long, float, Email.EmailTarget)):
            epat = Email.EmailPrimaryAddressTarget(self.db)
            if isinstance(target, Email.EmailTarget):
                epat.find(target.entity_id)
            else:
                epat.find(target)
            tmp = epat

        if isinstance(tmp, Email.EmailPrimaryAddressTarget):
            ea = Email.EmailAddress(self.db)
            ea.find(tmp.email_primaddr_id)
            tmp = ea

        if not isinstance(tmp, Email.EmailAddress):
            raise ValueError("Unknown argument type (%s)" % type(target))

        return self._email_address_to_str(tmp)

    def _split_email_address(self, addr, with_checks=True):
        """Split an e-mail address into local part and domain.

        Additionally, perform certain basic checks to ensure that the address
        looks sane.

        @type addr: basestring
        @param addr:
          E-mail address to split, spelled as 'foo@domain'.

        @type with_checks: bool
        @param with_checks:
          Controls whether to perform local part checks on the
          address. Occasionally we may want to sidestep this (e.g. when
          *removing* things from the database).

        @rtype: tuple of (basestring, basestring)
        @return:
          A pair, local part and domain extracted from the L{addr}.
        """
        lp, dom = split_address(addr)
        if not with_checks:
            return lp, dom

        ea = Email.EmailAddress(self.db)
        if not ea.validate_localpart(lp):
            raise CerebrumError("Invalid localpart '{}'".format(lp))
        return lp, dom

    def _is_ok_mailing_list_name(self, localpart):
        """ Validate localpart for mailing list use.

        @type localpart: str
        @param localpart: The localpart of the mailing list address.

        @rtype: bool
        @return: True if the localpart is valid, otherwise false.

        """
        # originally this regexp was:^[a-z0-9.-]. postmaster however
        # needs to be able to recreate some of the older mailing lists
        # in sympa and '_' used to be a valid character in list names.
        # this may not be very wise, but the postmasters have promised
        # to be good and make sure not to abuse this :-).
        #  - Jazz, 2009-11-13
        if not re.match(r'^[a-z0-9.-]+$|^[a-z0-9._]+$', localpart):
            raise CerebrumError("Illegal localpart: '%s'" % localpart)
        if len(localpart) > 8 or localpart.count('-') or localpart == 'drift':
            return True
        return False

    #
    # RT specific utils
    #
    # RT email lists have multiple targets. When altering filter and spam
    # settings, the changes must be applied to *all* email targets, which is
    # why we need this RT-related functionality in the base class.
    #
    def _resolve_rt_name(self, queuename):
        """Return queue and host of RT queue as tuple."""
        if queuename.count('@') == 0:
            # Use the default host
            return queuename, "rt.uio.no"
        elif queuename.count('@') > 1:
            raise CerebrumError("Invalid RT queue name: %s" % queuename)
        return queuename.split('@')

    def _get_rt_queue_and_host(self, address):
        """ Get RT queue and host from an RT address. """
        et, addr = self._get_email_target_and_address(address)

        parts = parse_rt_pipe(et.get_alias())
        try:
            return parts[1], parts[2]
        except IndexError:
            raise CerebrumError("Could not get queue and host for %s" %
                                address)

    def _get_all_related_rt_targets(self, address):
        """ Locate and return all ETs associated with the RT queue.

        Given any address associated with a RT queue, this method returns
        all the ETs associated with that RT queue. E.g.: 'foo@domain' will
        return 'foo@domain' and 'foo-comment@queuehost'

        If address (EA) is not associated with a RT queue, this method
        raises an exception. Otherwise a list of ET entity_ids is returned.

        :param string address:
            One of the mail addresses associated with a RT queue.

        :rtype: sequence (of ints)
        :return set:
            A set of entity_ids of all ETs related to the RT queue that
            address is related to.

        """
        et = Email.EmailTarget(self.db)
        queue, host = self._get_rt_queue_and_host(address)
        targets = set([])
        for action in ("correspond", "comment"):
            alias = format_rt_pipe(action, queue, host)
            try:
                et.clear()
                et.find_by_alias(alias)
            except Errors.NotFoundError:
                continue

            targets.add(et.entity_id)

        if not targets:
            raise CerebrumError("RT queue %s on host %s not found" %
                                (queue, host))

        return targets

    def _configure_spam_settings(self, email_target):
        """ Auto-configure spam settings for an email target.

        Adds spam settings for an email target according to the cereconf
        setting 'EMAIL_DEFAULT_SPAM_SETTINGS'.

        """
        target_type = self.const.EmailTarget(email_target.email_target_type)
        settings = cereconf.EMAIL_DEFAULT_SPAM_SETTINGS
        if target_type not in settings:
            return
        spam_level, spam_action = (
            int(self.const.EmailSpamLevel(settings[target_type][0])),
            int(self.const.EmailSpamAction(settings[target_type][1])))
        esf = Email.EmailSpamFilter(self.db)
        esf.populate(spam_level, spam_action, parent=email_target)
        esf.write_db()
        return True

    def _configure_filter_settings(self, email_target):
        """ Auto-configure filter settings for an email target.

        Adds spam settings for an email target according to the cereconf
        setting 'EMAIL_DEFAULT_FILTERS'.

        """
        target_type = self.const.EmailTarget(email_target.email_target_type)
        settings = cereconf.EMAIL_DEFAULT_FILTERS
        if target_type not in settings:
            return False
        filter_code = int(self.const.EmailTargetFilter(settings[target_type]))

        etf = Email.EmailTargetFilter(self.db)
        etf.populate(filter_code, parent=email_target)
        etf.write_db()
        return True

    #
    # Sympa/Maillist specific utils
    #
    # Sympa email lists have multiple targets. When altering filter and spam
    # settings, the changes must be applied to *all* email targets, which is
    # why we need this Sympa-related functionality in the base class.
    #
    def _get_sympa_list(self, listname):
        """ Try to return the 'official' sympa mailing list name, if it can at
        all be derived from listname.

        The problem here is that some lists are actually called
        foo-admin@domain (and their admin address is foo-admin-admin@domain).

        Since the 'official' names are not tagged in any way, we try to
        guess. The guesswork proceeds as follows:

        1) if listname points to a sympa ET that has a primary address, we are
           done, listname *IS* the official list name
        2) if not, then there must be a prefix/suffix (like -request) and if
           we chop it off, we can checked the chopped off part for being an
           official sympa list. The chopping off continues until we run out of
           special prefixes/suffixes.
        """

        ea = Email.EmailAddress(self.db)
        et = Email.EmailTarget(self.db)
        epat = Email.EmailPrimaryAddressTarget(self.db)

        def has_primary_to_me(address):
            try:
                ea.clear()
                ea.find_by_address(address)
                epat.clear()
                epat.find(ea.get_target_id())
                return True
            except Errors.NotFoundError:
                return False

        def I_am_sympa(address, check_suffix_prefix=True):
            try:
                ea.clear()
                ea.find_by_address(address)
            except Errors.NotFoundError:
                # If it does not exist, it cannot be sympa
                return False

            et.clear()
            et.find(ea.get_target_id())
            if ((not et.email_target_alias) or
                    et.email_target_type != self.const.email_target_Sympa):
                # if it's not a Sympa ET, address cannot be sympa
                return False
            return True

        not_sympa_error = CerebrumError("%s is not a Sympa list" % listname)
        # Simplest case -- listname is actually a sympa ML directly. It does
        # not matter whether it has a funky prefix/suffix.
        if I_am_sympa(listname) and has_primary_to_me(listname):
            return listname

        # However, if listname does not have a prefix/suffix AND it is not a
        # sympa address with a primary address, them it CANNOT be a sympa
        # address.
        local_part, domain = self._split_email_address(listname)
        if not (any(local_part.endswith(suffix)
                    for suffix in _sympa_address_suffixes)
                or any(local_part.startswith(prefix)
                       for prefix in _sympa_address_prefixes)):
            raise not_sympa_error

        # There is a funky suffix/prefix. Is listname actually such a
        # secondary address? Try to chop off the funky part and test.
        for prefix in _sympa_address_prefixes:
            if not local_part.startswith(prefix):
                continue

            lp_tmp = local_part[len(prefix):]
            addr_to_test = lp_tmp + "@" + domain
            try:
                self._get_sympa_list(addr_to_test)
                return addr_to_test
            except CerebrumError:
                pass

        for suffix in _sympa_address_suffixes:
            if not local_part.endswith(suffix):
                continue

            lp_tmp = local_part[:-len(suffix)]
            addr_to_test = lp_tmp + "@" + domain
            try:
                self._get_sympa_list(addr_to_test)
                return addr_to_test
            except CerebrumError:
                pass

        raise not_sympa_error

    def _get_maillist_targets_for_pattern(self, official_address, patterns):
        """ Locate and return all email targets.

        This is a helper function for implementations of
        _get_all_related_maillist_targets. Given the 'official' email address
        of the list, and a pattern of alternate lists names, it looks up and
        fetches the target_ids of all the list names.

        """
        # Look up the official address to get it's ID.
        et, ea = self._get_email_target_and_address(official_address)
        result = set([et.entity_id, ])

        # get local_part and domain separated:
        local_part, domain = self._split_email_address(official_address)

        # Get the ID of all 'derived' addresses
        for pattern in patterns:
            # pattern comes from _sympa_addr2alias.keys()
            address = pattern % {"local_part": local_part, "domain": domain}

            # some of the addresses may be missing. It is not an error.
            try:
                ea.clear()
                ea.find_by_address(address)
            except Errors.NotFoundError:
                continue

            result.add(ea.get_target_id())

        return result

    def _get_all_related_maillist_targets(self, address):
        """ Locate and return all email targets (addresses) for a sympa list.

        Given any address associated with a mailing list, this method returns
        all the EmailTarget id's that are associated with that mailing list.

        E.g.: 'foo-subscribe@domain' for a Sympa list will return the
        EmailTarget id's for addresses 'foo@domain', 'foo-owner@domain',
        'foo-request@domain', 'foo-editor@domain', 'foo-subscribe@domain' and
        'foo-unsubscribe@domain'

        :type str address:
            One of the mail addresses associated with a mailing list.

        :return sequence:
            A sequence with entity_ids of all EmailTargets related to the
            mailing list that address is related to.
        """
        et, ea = self._get_email_target_and_address(address)

        if et.email_target_type != self.const.email_target_Sympa:
            raise CerebrumError("'%s' is not associated with a mailing list" %
                                address)

        official_ml_address = self._get_sympa_list(ea.get_address())
        patterns = [x[0] for x in _sympa_addr2alias]

        return self._get_maillist_targets_for_pattern(official_ml_address,
                                                      patterns)


class BofhdEmailAuth(BofhdAuth):
    """ Auth for email-commands.

    To disallow access to an email command, you make a subclass of this class,
    and a subclass of the commands class:

        class FooAuth(BofhdAuth):
            pass

        class FooCommands(BofhdEmailCommands):
            authz = FooAuth
    """
    def _query_maildomain_permissions(self, operator,
                                      operation, domain, victim_id):
        """Permissions on e-mail domains are granted specifically."""
        if self._has_global_access(
                operator,
                operation,
                self.const.auth_target_type_global_maildomain,
                victim_id):
            return True
        if self._has_target_permissions(
                operator,
                operation,
                self.const.auth_target_type_maildomain,
                domain.entity_id,
                victim_id):
            return True
        raise PermissionDenied("No access to '%s' for e-mail domain %r" %
                               (operation.description,
                                domain.email_domain_name))

    def _is_local_postmaster(self, operator, operation,
                             account=None,
                             domain=None,
                             query_run_any=False):
        if self.is_postmaster(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(operator, operation)
        if domain:
            self._query_maildomain_permissions(operator, operation,
                                               domain, None)
        if account:
            self.is_account_owner(operator, operation, account)
        return True

    def can_email_address_add(self, operator, account=None, domain=None,
                              query_run_any=False):
        if self._is_local_postmaster(operator, self.const.auth_email_create,
                                     account, domain, query_run_any):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")

    def can_email_address_delete(self, operator, account=None, domain=None,
                                 query_run_any=False):
        # TBD: should the full email address be added to the parameters,
        # instead of just its domain?
        if self._is_local_postmaster(operator, self.const.auth_email_delete,
                                     account, domain, query_run_any):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")

    def can_email_address_reassign(self, operator, account=None, domain=None,
                                   query_run_any=False):
        if query_run_any:
            return True
        # Allow a user to manipulate his own accounts
        if account:
            owner_acc = Utils.Factory.get("Account")(self._db)
            owner_acc.find(operator)
            if (owner_acc.owner_id == account.owner_id and
                    owner_acc.owner_type == account.owner_type):
                return True
        if self._is_local_postmaster(operator,
                                     self.const.auth_email_reassign,
                                     account=account,
                                     domain=domain,
                                     query_run_any=query_run_any):
            return True
        raise PermissionDenied("Currently limited to superusers")

    # the user and local sysadmin is allowed to turn forwarding and
    # tripnote on/off
    def can_email_forward_toggle(self, operator, account=None,
                                 query_run_any=False):
        if query_run_any or (account and operator == account.entity_id):
            return True
        if self._is_local_postmaster(operator,
                                     self.const.auth_email_forward_off,
                                     account=account,
                                     domain=None,
                                     query_run_any=query_run_any):
            return True
        raise PermissionDenied("Currently limited to superusers")

    # only the user may add or remove forward addresses.
    def can_email_forward_edit(self, operator, account=None, domain=None,
                               query_run_any=False):
        if query_run_any or (account and operator == account.entity_id):
            return True
        # TODO: make a separate authentication operation for this!
        if self._is_local_postmaster(operator,
                                     self.const.auth_email_forward_off,
                                     account=account,
                                     domain=domain,
                                     query_run_any=query_run_any):
            return True
        raise PermissionDenied("Currently limited to superusers")

    def can_email_forward_create(self, operator, domain=None,
                                 query_run_any=False):
        if self._is_local_postmaster(operator,
                                     self.const.auth_email_create,
                                     account=None,
                                     domain=domain,
                                     query_run_any=query_run_any):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")

    def can_email_info(self, operator, account=None, query_run_any=False):
        """ Everyone can see basic email info. """
        return True

    def can_email_mod_name(self, operator, person=None, firstname=None,
                           lastname=None, query_run_any=False):
        """ If someone is allowed to modify a person's name.

        Only postmasters are allowed to do this by default.
        """
        if self.is_postmaster(operator, query_run_any=query_run_any):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")

    def can_email_pipe_create(self, operator,
                              domain=None, query_run_any=False):
        if self.is_postmaster(operator, query_run_any):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")

    def can_email_pipe_edit(self, operator,
                            domain=None, query_run_any=False):
        return self.can_email_pipe_create(operator,
                                          domain=domain,
                                          query_run_any=query_run_any)

    def can_email_set_failure(self, operator,
                              account=None, query_run_any=False):
        if self.is_postmaster(operator, query_run_any):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")

    def can_email_domain_create(self, operator, query_run_any=False):
        if self.is_postmaster(operator, query_run_any):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")

    def can_email_multi_create(self, operator,
                               domain=None, group=None, query_run_any=False):
        # not sure if we'll ever look at the group
        if self._is_local_postmaster(operator,
                                     self.const.auth_email_create,
                                     account=None,
                                     domain=domain,
                                     query_run_any=query_run_any):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to postmasters")

    def can_email_multi_delete(self, operator,
                               domain=None, group=None, query_run_any=False):
        # not sure if we'll ever look at the group
        if self._is_local_postmaster(operator,
                                     self.const.auth_email_delete,
                                     account=None,
                                     domain=domain,
                                     query_run_any=query_run_any):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to postmasters")

    def can_email_pause(self, operator, account=None, query_run_any=False):
        if self.is_postmaster(operator, query_run_any):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")

    def can_email_set_quota(self, operator, account=None, query_run_any=False):
        if self._is_local_postmaster(operator,
                                     self.const.auth_email_quota_set,
                                     account=account,
                                     domain=None,
                                     query_run_any=query_run_any):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")

    def can_email_spam_settings(self, operator, account=None, target=None,
                                query_run_any=False):
        if query_run_any or account:
            return self.can_email_forward_toggle(operator,
                                                 account=account,
                                                 query_run_any=query_run_any)
        if self.is_postmaster(operator):
            return True
        raise PermissionDenied("Currently limited to superusers")

    def can_email_tripnote_toggle(self, operator,
                                  account=None, query_run_any=False):
        if query_run_any or (account and operator == account.entity_id):
            return True
        if self._is_local_postmaster(operator,
                                     self.const.auth_email_vacation_off,
                                     account=account,
                                     domain=None,
                                     query_run_any=query_run_any):
            return True
        raise PermissionDenied("Currently limited to superusers")

    # or edit the tripnote messages or add new ones.
    def can_email_tripnote_edit(self, operator,
                                account=None, query_run_any=False):
        return self.can_email_forward_edit(operator,
                                           account=account,
                                           query_run_any=query_run_any)


class RTQueue(Parameter):
    """ Parameter class for RT queues. """
    _type = 'rtQueue'
    _help_ref = 'rt_queue'


_rt_pipe = '|%s --action %s --queue %s --url %s' % (
    '/local/bin/rt-mailgate', '%(action)s', '%(queue)s',
    'https://%(host)s/')


def format_rt_pipe(action, queue, host):
    """ format an RT pipe command. """
    return _rt_pipe % {
        'action': action,
        'queue': queue,
        'host': host,
    }


def parse_rt_pipe(pipestring):
    """ Parse an RT pipe command.

    :return None, tuple:
        Returns a tuple with the (action, queue, host) values in the command,
        or None if the string does not match.
    """
    p = '^\\' + format_rt_pipe('(\S+)', '(\S+)', '(\S+)') + '$'
    try:
        return re.match(p, pipestring).groups()
    except AttributeError:
        return None


_sympa_addr2alias = (
    # The first one *is* the official/primary name. Don't reshuffle.
    ('%(local_part)s@%(domain)s',
     '|SYMPA_QUEUE %(listname)s'),
    # Owner addresses...
    ('%(local_part)s-owner@%(domain)s',
     '|SYMPA_BOUNCEQUEUE %(listname)s'),
    ('%(local_part)s-admin@%(domain)s',
     '|SYMPA_BOUNCEQUEUE %(listname)s'),
    # Request addresses...
    ('%(local_part)s-request@%(domain)s',
     '|SYMPA_QUEUE %(local_part)s-request@%(domain)s'),
    ('owner-%(local_part)s@%(domain)s',
     '|SYMPA_QUEUE %(local_part)s-request@%(domain)s'),
    # Editor address...
    ('%(local_part)s-editor@%(domain)s',
     '|SYMPA_QUEUE %(local_part)s-editor@%(domain)s'),
    # Subscribe address...
    ('%(local_part)s-subscribe@%(domain)s',
     '|SYMPA_QUEUE %(local_part)s-subscribe@%(domain)s'),
    # Unsubscribe address...
    ('%(local_part)s-unsubscribe@%(domain)s',
     '|SYMPA_QUEUE %(local_part)s-unsubscribe@%(domain)s'),
)
_sympa_address_suffixes = ('-owner', '-admin', '-request', '-editor',
                           '-subscribe', '-unsubscribe',)
_sympa_address_prefixes = ('owner-',)


class BofhdEmailCommands(BofhdEmailBase):
    """ This is a mixin for email commands.

    It should supply the common denominator for all email commands at all
    institutions.

    Typically, you will inherit from this command, and disable unwanted or
    unsupported commands, or even extend or alter the behaviour of certain
    commands:

        class MyEmailCommands(BofhdEmailCommands):
            authz = MyCustomAuth
            omit_parent_commands = {'email_info', 'email_update'}
            parent_commands = True

            def email_add_address(self, *args):
                # do something extra
                return super(MyEmailCommands, self).email_add_address(*args)

    """

    all_commands = {}
    hidden_commands = {}

    authz = BofhdEmailAuth
    omit_parent_commands = set()
    parent_commands = False

    @classmethod
    def get_help_strings(cls):
        return merge_help_strings(
            super(BofhdEmailCommands, cls).get_help_strings(),
            (HELP_EMAIL_GROUP, HELP_EMAIL_CMDS, {}))

    def _get_affiliationid(self, code_str):
        try:
            c = self.const.PersonAffiliation(code_str.upper())
            # force a database lookup to see if it's a valid code
            int(c)
            return c
        except Errors.NotFoundError:
            raise CerebrumError("Unknown affiliation")

    #
    # email add_address <address or account> <address>+
    #
    all_commands['email_add_address'] = Command(
        ('email', 'add_address'),
        AccountName(help_ref='account_name'),
        EmailAddress(help_ref='email_address', repeat=True),
        fs=FormatSuggestion(
            "Ok, added '%s' as email-address for '%s'", ("address", "target")
        ),
        perm_filter='can_email_address_add')

    def email_add_address(self, operator, uname, address):
        """ Add an email address to an account. """

        # uname can be an address
        et, acc = self._get_email_target_and_account(uname)

        if et.email_target_type == self.const.email_target_deleted:
            raise CerebrumError("Can't add e-mail address to deleted target")
        ea = Email.EmailAddress(self.db)
        local, domain = self._split_email_address(address)
        ed = self._get_email_domain_from_str(domain)
        self.ba.can_email_address_add(operator.get_entity_id(),
                                      account=acc, domain=ed)
        ea.clear()
        try:
            ea.find_by_address(address)
            raise CerebrumError("Address already exists (%s)" % address)
        except Errors.NotFoundError:
            pass
        ea.clear()
        ea.populate(local, ed.entity_id, et.entity_id)
        ea.write_db()

        return {
            'address': address,
            'target': uname,
        }

    #
    # email remove_address <account> <address>+
    #
    all_commands['email_remove_address'] = Command(
        ('email', 'remove_address'),
        AccountName(),
        EmailAddress(repeat=True),
        fs=FormatSuggestion([
            ("Removed address '%s'", ('address', )),
            ("Removed target '%s'", ('target_type', ))
        ]),
        perm_filter='can_email_address_delete')

    def email_remove_address(self, operator, uname, address):
        """ Remove an email address from an account. """

        # uname can be an address
        et, acc = self._get_email_target_and_account(uname)
        local, domain = self._split_email_address(address, with_checks=False)
        ed = self._get_email_domain_from_str(domain)

        self.ba.can_email_address_delete(operator.get_entity_id(),
                                         account=acc, domain=ed)

        target_type = self.const.EmailTarget(et.email_target_type)
        retval = {'address': address, }
        if self._remove_email_address(et, address):
            retval['target_type'] = str(target_type)
        return retval

    #
    # email reassign_address <address> <destination>
    #
    all_commands['email_reassign_address'] = Command(
        ('email', 'reassign_address'),
        EmailAddress(help_ref='email_address'),
        AccountName(help_ref='account_name'),
        perm_filter='can_email_address_reassign')

    def email_reassign_address(self, operator, address, dest):
        """ Reassign address to a user account. """

        source_et, source_acc = self._get_email_target_and_account(address)
        ttype = self.const.EmailTarget(source_et.email_target_type)

        if ttype not in (self.const.email_target_account,
                         self.const.email_target_deleted):
            raise CerebrumError("Can't reassign e-mail address from"
                                " target type %s" % str(ttype))

        dest_acc = self._get_account(dest)
        self.ba.can_email_address_reassign(operator.get_entity_id(), dest_acc)

        if dest_acc.is_deleted():
            raise CerebrumError("Can't reassign e-mail address to deleted"
                                " account %s" % dest)
        dest_et = Email.EmailTarget(self.db)
        try:
            dest_et.find_by_target_entity(dest_acc.entity_id)
        except Errors.NotFoundError:
            raise CerebrumError("Account %s has no e-mail target" % dest)

        dtype = self.const.EmailTarget(dest_et.email_target_type)
        if dtype != self.const.email_target_account:
            raise CerebrumError("Can't reassign e-mail address to"
                                " target type %s" % str(dtype))

        if source_et.entity_id == dest_et.entity_id:
            # TODO: CerebrumError?
            return "%s is already connected to %s" % (address, dest)
        if (source_acc.owner_type != dest_acc.owner_type
                or source_acc.owner_id != dest_acc.owner_id):
            raise CerebrumError("Can't reassign e-mail address to a"
                                " different person")

        source_epat = Email.EmailPrimaryAddressTarget(self.db)
        try:
            source_epat.find(source_et.entity_id)
            source_epat.delete()
        except Errors.NotFoundError:
            pass

        ea = Email.EmailAddress(self.db)
        ea.find_by_address(address)
        ea.email_addr_target_id = dest_et.entity_id
        ea.write_db()

        dest_acc.update_email_addresses()

        # TODO: FormatSuggestion
        if (len(source_et.get_addresses()) == 0
                and ttype == self.const.email_target_deleted):
            source_et.delete()
            # TODO: Should return dict. Use FormatSuggestion for bofh...
            return ("OK, reassigned %s and deleted source e-mail target" %
                    address)

        source_acc.update_email_addresses()
        return "OK, reassigned %s" % address

    #
    # email local_delivery <username> on|off
    #
    all_commands['email_local_delivery'] = Command(
        ('email', 'local_delivery'),
        AccountName(help_ref='account_name'),
        SimpleString(help_ref='string_email_on_off'),
        perm_filter='can_email_forward_toggle')

    def email_local_delivery(self, operator, uname, on_off):
        """Turn on or off local delivery of E-mail."""
        acc = self._get_account(uname)
        self.ba.can_email_forward_toggle(operator.get_entity_id(), account=acc)
        fw = Email.EmailForward(self.db)
        fw.find_by_target_entity(acc.entity_id)
        on_off = on_off.lower()
        if on_off == 'on':
            fw.enable_local_delivery()
        elif on_off == 'off':
            fw.disable_local_delivery()
        else:
            raise CerebrumError("Must specify 'on' or 'off'")
        # TODO: FormatSuggestion
        return "OK, local delivery turned %s" % on_off

    #
    # email forward <username> <address> on|off
    #
    all_commands['email_forward'] = Command(
        ('email', 'forward'),
        AccountName(),
        EmailAddress(),
        SimpleString(help_ref='string_email_on_off'),
        perm_filer='can_email_forward_toggle')

    def email_forward(self, operator, uname, addr, on_off):
        """Toggle if a forward is active or not."""
        acc = self._get_account(uname)
        self.ba.can_email_forward_toggle(operator.get_entity_id(), acc)
        fw = Email.EmailForward(self.db)
        fw.find_by_target_entity(acc.entity_id)

        if addr not in [r['forward_to'] for r in fw.get_forward()]:
            raise CerebrumError("Forward address not registered in target")

        on_off = on_off.lower()
        if on_off == 'on':
            fw.enable_forward(addr)
        elif on_off == 'off':
            fw.disable_forward(addr)
        else:
            raise CerebrumError("Must specify 'on' or 'off'")
        fw.write_db()
        return "OK, forward to %s turned %s" % (addr, on_off)

    #
    # email add_forward <account>+ <address>+
    #
    # account can also be an e-mail address for pure forwardtargets
    #
    all_commands['email_add_forward'] = Command(
        ('email', 'add_forward'),
        AccountName(help_ref='account_name', repeat=True),
        EmailAddress(help_ref='email_address', repeat=True),
        perm_filter='can_email_forward_edit')

    def email_add_forward(self, operator, uname, address):
        """Add an e-mail forward."""
        et, acc = self._get_email_target_and_account(uname)
        if uname.count('@') and not acc:
            lp, dom = uname.split('@')
            ed = Email.EmailDomain(self.db)
            ed.find_by_domain(dom)
            self.ba.can_email_forward_edit(operator.get_entity_id(),
                                           domain=ed)
        else:
            self.ba.can_email_forward_edit(operator.get_entity_id(),
                                           account=acc)
        fw = Email.EmailForward(self.db)
        fw.find(et.entity_id)
        if address == 'local':
            fw.enable_local_delivery()
            return 'OK, local delivery turned on'
        addr = check_email_address(address)

        if self._forward_exists(fw, addr):
            raise CerebrumError("Forward address added already (%s)" % addr)

        fw.add_forward(addr)
        return "OK, added '%s' as forward-address for '%s'" % (address, uname)

    #
    # email delete_forward address
    #
    all_commands['email_delete_forward_target'] = Command(
        ("email", "delete_forward"),
        EmailAddress(help_ref='email_address'),
        fs=FormatSuggestion([("Deleted forward address: %s", ("address", ))]),
        perm_filter='can_email_forward_create')

    def email_delete_forward_target(self, operator, address):
        """Delete a forward target with associated aliases.

        Requires primary address.
        """

        # Allow us to delete an address, even if it is malformed.
        lp, dom = self._split_email_address(address, with_checks=False)
        ed = self._get_email_domain(dom)
        et, acc = self._get_email_target_and_account(address)
        self.ba.can_email_forward_create(operator.get_entity_id(), domain=ed)
        epat = Email.EmailPrimaryAddressTarget(self.db)
        try:
            epat.find(et.entity_id)
            # but if one exists, we require the user to supply that
            # address, not an arbitrary alias.
            if address != self._get_address(epat):
                raise CerebrumError("%s is not the primary address of "
                                    "the target" % address)
            epat.delete()
        except Errors.NotFoundError:
            # a forward address does not need a primary address
            pass

        fw = Email.EmailForward(self.db)
        try:
            fw.find(et.entity_id)
            for f in fw.get_forward():
                fw.delete_forward(f['forward_to'])
        except Errors.NotFoundError:
            # There are som stale forward targets without any address to
            # forward to, hence ignore.
            pass

        result = []
        ea = Email.EmailAddress(self.db)
        for r in et.get_addresses():
            ea.clear()
            ea.find(r['address_id'])
            result.append({'address': self._get_address(ea)})
            ea.delete()
        et.delete()
        return result

    #
    # email remove_forward <account>+ <address>+
    #
    # account can also be an e-mail address for pure forwardtargets
    #
    all_commands['email_remove_forward'] = Command(
        ("email", "remove_forward"),
        AccountName(help_ref="account_name", repeat=True),
        EmailAddress(help_ref='email_address', repeat=True),
        perm_filter='can_email_forward_edit')

    def email_remove_forward(self, operator, uname, address):
        et, acc = self._get_email_target_and_account(uname)

        if uname.count('@') and not acc:
            # TODO: Why not _split_email_address?
            lp, dom = uname.split('@')
            ed = self._get_email_domain_from_str(dom)
            self.ba.can_email_forward_edit(operator.get_entity_id(),
                                           domain=ed)
        else:
            self.ba.can_email_forward_edit(operator.get_entity_id(),
                                           account=acc)
        fw = Email.EmailForward(self.db)
        fw.find(et.entity_id)
        if address == 'local':
            fw.disable_local_delivery()
            return 'OK, local delivery turned off'
        addr = check_email_address(address)

        # TODO: Why iterate over a list with one item?
        removed = 0
        for a in [addr]:
            if self._forward_exists(fw, a):
                fw.delete_forward(a)
                removed += 1
        if not removed:
            raise CerebrumError("No such forward address (%s)" % addr)
        return "OK, removed '%s'" % addr

    #
    # email info <account>+
    #
    all_commands['email_info'] = Command(
        ("email", "info"),
        AccountName(help_ref="account_name", repeat=True),
        fs=FormatSuggestion([
            ("Target Type:      %s", ("target_type",)),
            ("Target ID:        %d", ("target_id",)),
            #
            # target_type == Account
            #
            ("Account:          %s\n"
             "Mail server:      %s (%s)", ("account",
                                           "server", "server_type")),
            ("Primary address:  %s", ("def_addr", )),
            ("Alias value:      %s", ("alias_value", )),
            # We use valid_addr_1 and (multiple) valid_addr to enable
            # programs to get the information reasonably easily, while
            # still keeping the suggested output format pretty.
            ("Valid addresses:  %s", ("valid_addr_1", )),
            ("                  %s", ("valid_addr",)),
            ("Mail quota:       %d MiB, warn at %d%% (not enforced)",
             ("dis_quota_hard", "dis_quota_soft")),
            ("Mail quota:       %d MiB, warn at %d%% (%s used (MiB))",
             ("quota_hard", "quota_soft", "quota_used")),
            ("                  (currently %d MiB on server)",
             ("quota_server",)),
            ("HomeMDB:          %s", ("homemdb", )),
            # TODO: change format so that ON/OFF is passed as separate value.
            # this must be coordinated with webmail code.
            ("Forwarding:       %s", ("forward_1", )),
            ("                  %s", ("forward", )),
            #
            # target_type == dlgroup
            #
            ("Dl group:         %s", ("name", )),
            ("Group id:         %d", ("group_id", )),
            ("Display name:     %s", ("displayname", )),
            ("Primary address:  %s", ("primary", )),
            ("Valid addresses:  %s", ("aliases", )),
            ("Hidden addr list: %s", ('hidden', )),
            #
            # target_type == Sympa
            #
            ("Mailing list:     %s", ("sympa_list",)),
            ("Alias:            %s", ("sympa_alias_1",)),
            ("                  %s", ("sympa_alias",)),
            ("Request:          %s", ("sympa_request_1",)),
            ("                  %s", ("sympa_request",)),
            ("Owner:            %s", ("sympa_owner_1",)),
            ("                  %s", ("sympa_owner",)),
            ("Editor:           %s", ("sympa_editor_1",)),
            ("                  %s", ("sympa_editor",)),
            ("Subscribe:        %s", ("sympa_subscribe_1",)),
            ("                  %s", ("sympa_subscribe",)),
            ("Unsubscribe:      %s", ("sympa_unsubscribe_1",)),
            ("                  %s", ("sympa_unsubscribe",)),
            ("Delivery host:    %s", ("sympa_delivery_host",)),
            #
            # target_type == multi
            #
            ("Forward to group: %s", ("multi_forward_gr",)),
            ("Expands to:       %s", ("multi_forward_1",)),
            ("                  %s", ("multi_forward",)),
            #
            # target_type == file
            #
            ("File:             %s\n"
             "Save as:          %s", ("file_name", "file_runas")),
            #
            # target_type == pipe
            #
            ("Command:          %s\n"
             "Run as:           %s", ("pipe_cmd", "pipe_runas")),
            #
            # target_type == RT
            #
            ("RT queue:         %s on %s\n"
             "Action:           %s\n"
             "Run as:           %s", ("rt_queue", "rt_host",
                                      "rt_action",
                                      "pipe_runas")),
            #
            # target_type == forward
            #
            ("Address:          %s", ("fw_target",)),
            ("Forwarding:       %s (%s)", ("fw_addr_1", "fw_enable_1")),
            ("                  %s (%s)", ("fw_addr", "fw_enable")),
            #
            # both account and Sympa
            #
            ("Spam level:       %s (%s)\n"
             "Spam action:      %s (%s)", ("spam_level", "spam_level_desc",
                                           "spam_action", "spam_action_desc")),
            ("Filters:          %s", ("filters",)),
            ("Status:           %s", ("status",)),
        ]),
        perm_filter='can_email_info')

    def email_info(self, operator, name):
        acc = None
        try:
            et, acc = self._get_email_target_and_account(name)
        except CerebrumError as e:
            # exchange-relatert-jazz
            # check if a distribution-group with an appropriate target
            # is registered by this name
            try:
                et, grp = self._get_email_target_and_dlgroup(name)
            except (CerebrumError, AttributeError):
                # handle accounts with email address stored in contact_info
                try:
                    ac = self._get_account(name)
                    return self._email_info_contact_info(operator, ac)
                except CerebrumError:
                    pass
            raise e

        ttype = self.const.EmailTarget(et.email_target_type)

        ret = []

        if ttype not in (self.const.email_target_Sympa,
                         self.const.email_target_pipe,
                         self.const.email_target_RT,
                         self.const.email_target_dl_group):
            ret.append({
                'target_type': str(ttype),
                'target_id': et.entity_id,
            })

        # Default address
        epat = Email.EmailPrimaryAddressTarget(self.db)
        try:
            epat.find(et.entity_id)
        except Errors.NotFoundError:
            if ttype == self.const.email_target_account:
                ret.append({'def_addr': "<none>"})
        else:
            if ttype != self.const.email_target_dl_group:
                ret.append({'def_addr': self._get_address(epat)})

        if ttype not in (self.const.email_target_Sympa,
                         # exchange-relatert-jazz
                         # drop fetching valid addrs,
                         # it's done in a proper place latter
                         self.const.email_target_dl_group):
            # We want to split the valid addresses into multiple
            # parts for MLs, so there is special code for that.
            addrs = self._get_valid_email_addrs(et, special=True, sort=True)
            if not addrs:
                addrs = ["<none>"]
            ret.append({'valid_addr_1': addrs[0]})
            for addr in addrs[1:]:
                ret.append({"valid_addr": addr})

        if ttype == self.const.email_target_Sympa:
            ret += self._email_info_sympa(operator, et, name)
        elif ttype == self.const.email_target_dl_group:
            ret += self._email_info_dlgroup(name)
        elif ttype == self.const.email_target_multi:
            ret += self._email_info_multi(et, name)
        elif ttype == self.const.email_target_file:
            ret += self._email_info_file(et, name)
        elif ttype == self.const.email_target_pipe:
            ret += self._email_info_pipe(et, name)
        elif ttype == self.const.email_target_RT:
            ret += self._email_info_rt(et, name)
        elif ttype == self.const.email_target_forward:
            ret += self._email_info_forward(et, name)
        elif (ttype == self.const.email_target_account
                or (ttype == self.const.email_target_deleted and acc)):
            ret += self._email_info_account(operator, acc, et, addrs)
        else:
            raise CerebrumError("email info for target type %s isn't "
                                "implemented" % str(ttype))

        # Only the account owner and postmaster can see account settings, and
        # that is handled properly in _email_info_account.
        if ttype not in (self.const.email_target_account,
                         self.const.email_target_deleted):
            ret += self._email_info_spam(et)
            ret += self._email_info_filters(et)
            ret += self._email_info_forwarding(et, name)

        return ret

    def _email_info_contact_info(self, operator, acc):
        """ info for accounts with email stored in contact info. """
        ret = [{'target_type': 'entity_contact_info'}, ]
        addresses = acc.get_contact_info(type=self.const.contact_email)
        if not addresses:
            raise CerebrumError("No contact info for: %s" % acc.account_name)
        for addr in addresses:
            ret.append({'valid_addr_1': addr['contact_value'], })
        return ret

    def _email_info_basic(self, acc, et):
        """ Partial email_info, basic info info. """
        info = {}
        data = [info, ]
        if (et.email_target_alias is not None
                and et.email_target_type != self.const.email_target_Sympa):
            info['alias_value'] = et.email_target_alias
        info["account"] = acc.account_name
        if et.email_server_id:
            es = Email.EmailServer(self.db)
            es.find(et.email_server_id)
            info["server"] = es.name
            info["server_type"] = str(
                self.const.EmailServerType(es.email_server_type))
        else:
            info["server"] = "<none>"
            info["server_type"] = "N/A"
        return data

    def _email_info_account(self, operator, acc, et, addrs):
        """ Partial email_info, account data. """
        ret = self._email_info_basic(acc, et)
        try:
            self.ba.can_email_info(operator.get_entity_id(), acc)
        except PermissionDenied:
            pass
        else:
            ret += self._email_info_spam(et)
            if not et.email_target_type == self.const.email_target_deleted:
                # No need to get details for deleted accounts
                ret += self._email_info_detail(acc)
            ret += self._email_info_forwarding(et, addrs)
            ret += self._email_info_filters(et)

            # Tell what addresses can be deleted:
            ea = Email.EmailAddress(self.db)
            dom = Email.EmailDomain(self.db)
            domains = acc.get_prospect_maildomains(
                use_default_domain=cereconf.EMAIL_DEFAULT_DOMAIN)
            for domain in cereconf.EMAIL_NON_DELETABLE_DOMAINS:
                dom.clear()
                dom.find_by_domain(domain)
                domains.append(dom.entity_id)
            deletables = []
            for addr in et.get_addresses(special=True):
                ea.clear()
                ea.find(addr['address_id'])
                if ea.email_addr_domain_id not in domains:
                    deletables.append(ea.get_address())
            ret.append({'deletable': deletables})
        return ret

    def _email_info_spam(self, target):
        """ Partial email_info, spam settings. """
        info = []
        spam = Email.EmailSpamFilter(self.db)
        try:
            spam.find(target.entity_id)
            spam_lev = self.const.EmailSpamLevel(spam.email_spam_level)
            spam_act = self.const.EmailSpamAction(spam.email_spam_action)
            info.append({
                'spam_level': str(spam_lev),
                'spam_level_desc':  spam_lev.description,
                'spam_action': str(spam_act),
                'spam_action_desc': spam_act.description,
            })
        except Errors.NotFoundError:
            pass
        return info

    def _email_info_filters(self, target):
        """ Partial email_info, filters. """
        filters = []
        info = {}
        etf = Email.EmailTargetFilter(self.db)
        for f in etf.list_email_target_filter(target_id=target.entity_id):
            filters.append(str(Email._EmailTargetFilterCode(f['filter'])))
        if len(filters) > 0:
            info["filters"] = ", ".join([x for x in filters]),
        else:
            info["filters"] = "<none>"
        return [info, ]

    def _email_info_forward(self, et, addr):
        """ Partial email_info for EmailTarget of type 'forward'. """
        data = []
        # et.email_target_alias isn't used for anything, it's often
        # a copy of one of the forward addresses, but that's just a
        # waste of bytes, really.
        _tf_map = {'T': 'on', 'F': 'off'}
        ef = Email.EmailForward(self.db)
        try:
            ef.find(et.entity_id)
        except Errors.NotFoundError:
            data.append({'fw_addr_1': '<none>', 'fw_enable': 'off'})
        else:
            forw = ef.get_forward()
            if forw:
                data.append({
                    'fw_addr_1': forw[0]['forward_to'],
                    'fw_enable_1': _tf_map[forw[0]['enable']],
                })
            for idx in range(1, len(forw)):
                data.append({
                    'fw_addr': forw[idx]['forward_to'],
                    'fw_enable': _tf_map[forw[idx]['enable']],
                })
        return data

    def _email_info_detail(self, acc):
        """ Partial email_info, account details. """
        return []

    def _email_info_dlgroup(self, groupname):
        """ Partial email_info, exchange dist groups. """
        return []

    def _email_info_forwarding(self, target, addrs):
        """ Partial email_info, forward addresses. """
        info = []
        forw = []
        ef = Email.EmailForward(self.db)
        ef.find(target.entity_id)
        for r in ef.get_forward():
            enabled = 'on' if (r['enable'] == 'T') else 'off'
            forw.append("%s (%s) " % (r['forward_to'], enabled))
        # for aesthetic reasons, print "+ local delivery" last
        if ef.local_delivery:
            forw.append("+ local delivery (on)")
        if forw:
            info.append({'forward_1': forw[0]})
            for idx in range(1, len(forw)):
                info.append({'forward': forw[idx]})
        return info

    def _email_info_multi(self, et, addr):
        """ Partial email_info for EmailTarget of type multi. """
        ret = []
        if et.email_target_entity_type != self.const.entity_group:
            ret.append({
                'multi_forward_gr': ('ENTITY TYPE OF %d UNKNOWN' %
                                     et.email_target_entity_id),
            })
        else:
            group = self.Group_class(self.db)
            acc = self.Account_class(self.db)
            try:
                group.find(et.email_target_entity_id)
            except Errors.NotFoundError:
                ret.append({
                    'multi_forward_gr': ('Unknown group %d' %
                                         et.email_target_entity_id),
                })
                return ret
            ret.append({'multi_forward_gr': group.group_name})

            fwds = list()
            for row in group.search_members(
                    group_id=group.entity_id,
                    member_type=self.const.entity_account):
                acc.clear()
                acc.find(row["member_id"])
                try:
                    addr = acc.get_primary_mailaddress()
                except Errors.NotFoundError:
                    addr = "(account %s has no e-mail)" % acc.account_name
                fwds.append(addr)
            if fwds:
                ret.append({'multi_forward_1': fwds[0]})
                for idx in range(1, len(fwds)):
                    ret.append({'multi_forward': fwds[idx]})
        return ret

    def _email_info_file(self, et, addr):
        """ Partial email_info for EmailTarget of type 'file'. """
        account_name = "<not set>"
        if et.email_target_using_uid:
            acc = self._get_account(et.email_target_using_uid, idtype='id')
            account_name = acc.account_name
        return [{
            'file_name': et.get_alias(),
            'file_runas': account_name,
        }]

    def _email_info_pipe(self, et, addr):
        """ Partial email_info for EmailTarget of type 'pipe'. """
        acc = self._get_account(et.email_target_using_uid, idtype='id')
        return [{
            'pipe_cmd': et.get_alias(),
            'pipe_runas': acc.account_name,
        }]

    def _email_info_rt(self, et, addr):
        """ Partial email_info for EmailTarget of type 'RT'. """
        # Delayed import to avoid circular depencency
        m = parse_rt_pipe(et.get_alias())
        acc = self._get_account(et.email_target_using_uid, idtype='id')
        return [{
            'rt_action': m[0],
            'rt_queue': m[1],
            'rt_host': m[2],
            'pipe_runas':  acc.account_name,
        }]

    def _email_info_sympa(self, operator, et, addr):
        """ Partial email_info for EmailTarget of type 'Sympa'. """
        # TODO: We should implement email_info better

        def fish_information(suffix, local_part, domain, listname):
            """Generate an entry for sympa info for the specified address.

            :return:
                A sequence of dicts suitable for merging into return value from
                email_info_sympa.
            """
            result = []
            address = "{lp}-{suffix}@{domain}".format(lp=local_part,
                                                      suffix=suffix,
                                                      domain=domain)
            target_alias = None
            for a, alias in _sympa_addr2alias:
                a = a % locals()
                if a == address:
                    target_alias = alias % locals()
                    break

            # IVR 2008-08-05 TBD Is this an error? All sympa ETs must have an
            # alias in email_target.
            if target_alias is None:
                return result

            try:
                # Do NOT change et's (parameter's) state.
                et_tmp = Email.EmailTarget(self.db)
                et_tmp.clear()
                et_tmp.find_by_alias(target_alias)
            except Errors.NotFoundError:
                return result

            addrs = et_tmp.get_addresses()
            if not addrs:
                return result

            pattern = '%(local_part)s@%(domain)s'
            result.append({'sympa_' + suffix + '_1': pattern % addrs[0]})
            for idx in range(1, len(addrs)):
                result.append({'sympa_' + suffix: pattern % addrs[idx]})
            return result

        # listname may be one of the secondary addresses.
        # email info sympatest@domain MUST be equivalent to
        # email info sympatest-admin@domain.
        # TODO: Where is _get_sympa_list?
        listname = self._get_sympa_list(addr)
        ret = [{"sympa_list": listname}]
        if listname.count('@') == 0:
            lp, dom = listname, addr.split('@')[1]
        else:
            lp, dom = listname.split('@')

        ed = Email.EmailDomain(self.db)
        ed.find_by_domain(dom)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.entity_id)
        except Errors.NotFoundError:
            raise CerebrumError("Address %s exists, but the list it points "
                                "to, %s, does not") % (addr, listname)
        # now find all e-mail addresses
        et_sympa = Email.EmailTarget(self.db)
        et_sympa.clear()
        et_sympa.find(ea.email_addr_target_id)
        addrs = self._get_valid_email_addrs(et_sympa, sort=True)
        # IVR 2008-08-21 According to postmasters, only superusers should see
        # forwarding and delivery host information
        if self.ba.is_postmaster(operator.get_entity_id()):
            if et_sympa.email_server_id is None:
                delivery_host = "N/A (this is an error)"
            else:
                delivery_host = self._get_server_from_ident(
                    et_sympa.email_server_id).name
            ret.append({"sympa_delivery_host": delivery_host})
        ret += self._email_info_forwarding(et_sympa, addrs)
        aliases = []
        for row in et_sympa.get_addresses():
            a = "%(local_part)s@%(domain)s" % row
            if a == listname:
                continue
            aliases.append(a)
        if aliases:
            ret.append({"sympa_alias_1": aliases[0]})
        for next_alias in aliases[1:]:
            ret.append({"sympa_alias": next_alias})

        for suffix in ("owner", "request", "editor", "subscribe",
                       "unsubscribe"):
            ret.extend(fish_information(suffix, lp, dom, listname))
        return ret

    #
    # email mod_name <person-id> <fname> <lname>
    #
    all_commands['email_mod_name'] = Command(
        ("email", "mod_name"),
        PersonId(help_ref="person_id_other"),
        PersonName(help_ref="person_name_first"),
        PersonName(help_ref="person_name_last"),
        fs=FormatSuggestion(
            "Name and e-mail address altered for: %i", ("person_id",)),
        perm_filter='can_email_mod_name')

    def email_mod_name(self, operator, person_id, firstname, lastname):
        """ Modify email name. """
        person = self._get_person(*self._map_person_id(person_id))
        self.ba.can_email_mod_name(operator.get_entity_id(), person=person,
                                   firstname=firstname, lastname=lastname)
        source_system = self.const.system_override
        person.affect_names(source_system,
                            self.const.name_first,
                            self.const.name_last,
                            self.const.name_full)
        if lastname == "":
            raise CerebrumError("A last name is required")
        if firstname == "":
            fullname = lastname
        else:
            fullname = firstname + " " + lastname
        person.populate_name(self.const.name_first, firstname)
        person.populate_name(self.const.name_last, lastname)
        person.populate_name(self.const.name_full, fullname)
        person._update_cached_names()
        try:
            person.write_db()
        except self.db.DatabaseError as m:
            raise CerebrumError("Database error: %s" % m)
        return {'person_id': person.entity_id}

    #
    # email primary_address <address>
    #
    all_commands['email_primary_address'] = Command(
        ("email", "primary_address"),
        EmailAddress(),
        fs=FormatSuggestion([("New primary address: '%s'", ("address", ))]),
        perm_filter="is_postmaster")

    def email_primary_address(self, operator, addr):
        """ Set primary email address. """
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")

        ea = self._get_email_address_from_str(addr)
        et = self._get_email_target_for_address(ea)

        if et.email_target_type == self.const.email_target_dl_group:
            raise CerebrumError("Cannot change primary for distribution"
                                " group %s" % addr)
        if self._set_email_primary_address(et, ea):
            return {'address': addr}
        raise CerebrumError("No change, primary address was %s" % addr)

    #
    # email set_primary_address account lp@dom
    #
    all_commands['email_set_primary_address'] = Command(
        ("email", "set_primary_address"),
        AccountName(help_ref="account_name", repeat=False),
        EmailAddress(help_ref='email_address', repeat=False),
        perm_filter='is_superuser')

    def email_set_primary_address(self, operator, uname, address):
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        et, acc = self._get_email_target_and_account(uname)
        ea = Email.EmailAddress(self.db)
        if address == '':
            return "Primary address cannot be an empty string!"
        lp, dom = address.split('@')
        ed = self._get_email_domain_from_str(dom)
        ea.clear()
        try:
            ea.find_by_address(address)
            if ea.email_addr_target_id != et.entity_id:
                raise CerebrumError("Address (%s) is in use by another user" %
                                    address)
        except Errors.NotFoundError:
            pass
        ea.populate(lp, ed.entity_id, et.entity_id)
        ea.write_db()
        if self._set_email_primary_address(et, ea):
            return "Registered %s as primary address for %s" % (address, uname)
        return "No change, %s is primary address for %s" % (address, uname)

    #
    # email create_pipe <address> <uname> <command>
    #
    all_commands['email_create_pipe'] = Command(
        ("email", "create_pipe"),
        EmailAddress(help_ref="email_address"),
        AccountName(),
        SimpleString(help_ref="command_line"),
        perm_filter="can_email_pipe_create")

    def email_create_pipe(self, operator, addr, uname, cmd):
        """ Create email pipe. """
        lp, dom = self._split_email_address(addr)
        ed = self._get_email_domain_from_str(dom)
        self.ba.can_email_pipe_create(operator.get_entity_id(), domain=ed)
        acc = self._get_account(uname, idtype='name')
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.entity_id)
        except Errors.NotFoundError:
            pass
        else:
            raise CerebrumError("%s already exists" % addr)
        et = Email.EmailTarget(self.db)
        if not cmd.startswith('|'):
            cmd = '|' + cmd
        et.populate(self.const.email_target_pipe, alias=cmd,
                    using_uid=acc.entity_id)
        et.write_db()
        ea.clear()
        ea.populate(lp, ed.entity_id, et.entity_id)
        ea.write_db()
        self._configure_spam_settings(et)
        self._configure_filter_settings(et)
        return "OK, created pipe address %s" % addr

    #
    # email delete_pipe <address>
    #
    all_commands['email_delete_pipe'] = Command(
        ("email", "delete_pipe"),
        EmailAddress(help_ref="email_address"),
        perm_filter="can_email_pipe_create")

    def email_delete_pipe(self, operator, addr):
        """ Delete email pipe. """
        lp, dom = self._split_email_address(addr, with_checks=False)
        ed = self._get_email_domain(dom)
        self.ba.can_email_pipe_create(operator.get_entity_id(), domain=ed)
        ea = Email.EmailAddress(self.db)
        et = Email.EmailTarget(self.db)
        try:
            ea.clear()
            ea.find_by_address(addr)
        except Errors.NotFoundError:
            raise CerebrumError("No such address %s" % addr)
        try:
            et.clear()
            et.find(ea.email_addr_target_id)
        except Errors.NotFoundError:
            raise CerebrumError("No e-mail target for %s" % addr)
        for a in et.get_addresses():
            ea.clear()
            ea.find(a['address_id'])
            ea.delete()
            ea.write_db()
        et.delete()
        et.write_db()
        return "Ok, deleted pipe for address %s" % addr

    #
    # email failure_message <username> <message>
    #
    all_commands['email_failure_message'] = Command(
        ("email", "failure_message"),
        AccountName(help_ref="account_name"),
        SimpleString(help_ref="email_failure_message"),
        perm_filter="can_email_set_failure")

    def email_failure_message(self, operator, uname, message):
        """ Email failure message. """
        et, acc = self._get_email_target_and_account(uname)
        self.ba.can_email_set_failure(operator.get_entity_id(), acc)

        if et.email_target_type != self.const.email_target_deleted:
            raise CerebrumError("You can only set the failure message"
                                " for deleted users")
        if message.strip() == '':
            message = None
        else:
            # It's not ideal that message contains the primary address
            # rather than the actual address given to RCPT TO.
            message = ":fail: %s: %s" % (acc.get_primary_mailaddress(),
                                         message)
        et.email_target_alias = message
        et.write_db()
        return "OK, updated %s" % uname

    #
    # email edit_pipe_command <address> <command>
    #
    all_commands['email_edit_pipe_command'] = Command(
        ("email", "edit_pipe_command"),
        EmailAddress(),
        SimpleString(help_ref="command_line"),
        perm_filter="can_email_pipe_edit")

    def email_edit_pipe_command(self, operator, addr, cmd):
        """ Edit pipe command. """
        lp, dom = self._split_email_address(addr)
        ed = self._get_email_domain_from_str(dom)
        self.ba.can_email_pipe_edit(operator.get_entity_id(), domain=ed)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.entity_id)
        except Errors.NotFoundError:
            raise CerebrumError("%s: No such address exists" % addr)
        et = Email.EmailTarget(self.db)
        et.find(ea.email_addr_target_id)
        if et.email_target_type not in (self.const.email_target_pipe,
                                        self.const.email_target_RT):
            raise CerebrumError("%s is not connected to a pipe or RT target" %
                                addr)
        if not cmd.startswith('|'):
            cmd = '|' + cmd
        if et.email_target_type == self.const.email_target_RT:
            if not parse_rt_pipe(cmd):
                raise CerebrumError("'%s' is not a valid RT command" % cmd)
        et.email_target_alias = cmd
        et.write_db()
        return "OK, edited %s" % addr

    #
    # email edit_pipe_user <address> <uname>
    #
    all_commands['email_edit_pipe_user'] = Command(
        ("email", "edit_pipe_user"),
        EmailAddress(),
        AccountName(),
        perm_filter="can_email_pipe_edit")

    def email_edit_pipe_user(self, operator, addr, uname):
        lp, dom = self._split_email_address(addr)
        ed = self._get_email_domain_from_str(dom)
        self.ba.can_email_pipe_edit(operator.get_entity_id(), domain=ed)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.entity_id)
        except Errors.NotFoundError:
            raise CerebrumError("%s: No such address exists" % addr)
        et = Email.EmailTarget(self.db)
        et.find(ea.email_addr_target_id)
        if et.email_target_type not in (self.const.email_target_pipe,
                                        self.const.email_target_RT):
            raise CerebrumError("%r is not connected to a pipe or RT target" %
                                addr)
        et.email_target_using_uid = self._get_account(uname).entity_id
        et.write_db()
        return "OK, edited %s" % addr

    #
    # email create_domain <domainname> <description>
    #
    all_commands['email_create_domain'] = Command(
        ("email", "create_domain"),
        SimpleString(help_ref="email_domain"),
        SimpleString(help_ref="string_description"),
        perm_filter="can_email_domain_create")

    def email_create_domain(self, operator, domainname, desc):
        """Create e-mail domain."""
        self.ba.can_email_domain_create(operator.get_entity_id())
        ed = Email.EmailDomain(self.db)
        domainname = domainname.lower()
        try:
            ed.find_by_domain(domainname)
            raise CerebrumError("E-mail domain '%s' already exists" %
                                domainname)
        except Errors.NotFoundError:
            pass
        if len(desc) < 3:
            raise CerebrumError("Please supply a better description")
        try:
            ed.populate(domainname, desc)
        except AttributeError as ae:
            raise CerebrumError(str(ae))
        ed.write_db()
        return "OK, domain '%s' created" % domainname

    #
    # email delete_domain <domainname>
    #
    all_commands['email_delete_domain'] = Command(
        ("email", "delete_domain"),
        SimpleString(help_ref="email_domain"),
        perm_filter="can_email_domain_create")

    def email_delete_domain(self, operator, domainname):
        """Delete e-mail domain."""
        self.ba.can_email_domain_create(operator.get_entity_id())
        ed = Email.EmailDomain(self.db)
        domainname = domainname.lower()
        try:
            ed.find_by_domain(domainname)
        except Errors.NotFoundError:
            raise CerebrumError("%s: No e-mail domain by that name" %
                                domainname)

        ea = Email.EmailAddress(self.db)
        if ea.search(domain_id=ed.entity_id, fetchall=True):
            raise CerebrumError("E-mail-domain '%s' has addresses;"
                                " cannot delete" % domainname)

        eed = Email.EntityEmailDomain(self.db)
        if eed.list_affiliations(domain_id=ed.entity_id):
            raise CerebrumError("E-mail-domain '%s' associated with OUs;"
                                " cannot delete" % domainname)

        ed.delete()
        ed.write_db()
        return "OK, domain '%s' deleted" % domainname

    #
    # email domain_configuration on|off <domain> <category>+
    #
    all_commands['email_domain_configuration'] = Command(
        ("email", "domain_configuration"),
        SimpleString(help_ref="on_or_off"),
        SimpleString(help_ref="email_domain"),
        SimpleString(help_ref="email_category", repeat=True),
        perm_filter="can_email_domain_create")

    def email_domain_configuration(self, operator, onoff, domainname, cat):
        """ Change configuration for an e-mail domain. """
        self.ba.can_email_domain_create(operator.get_entity_id())
        ed = self._get_email_domain_from_str(domainname)
        on = self._get_boolean(onoff)
        catcode = None
        for c in self.const.fetch_constants(self.const.EmailDomainCategory,
                                            prefix_match=cat):
            if catcode:
                raise CerebrumError(
                    "'%s' does not uniquely identify a configuration category"
                    % cat)
            catcode = c
        if catcode is None:
            raise CerebrumError(
                "'%s' does not match any configuration category" % cat)
        if self._sync_category(ed, catcode, on):
            return "%s is now %s" % (catcode, onoff.lower())
        else:
            return "%s unchanged" % catcode

    #
    # email domain_set_description
    #
    all_commands['email_domain_set_description'] = Command(
        ("email", "domain_set_description"),
        SimpleString(help_ref="email_domain"),
        SimpleString(help_ref="string_description"),
        perm_filter='can_email_domain_create')

    def email_domain_set_description(self, operator, domainname, description):
        """ Set the description of an e-mail domain. """
        self.ba.can_email_domain_create(operator.get_entity_id())
        ed = self._get_email_domain_from_str(domainname)
        ed.email_domain_description = description
        ed.write_db()
        return "OK, description for domain '%s' updated" % domainname

    def _has_category(self, domain, category):
        """ Check if EmailDomain has the given category. """
        ccode = int(category)
        for r in domain.get_categories():
            if r['category'] == ccode:
                return True
        return False

    def _sync_category(self, domain, category, enable):
        """ Enable or disable category with EmailDomain.

        @rtype: boolean
        @return: True for change, False for no change.

        """
        if self._has_category(domain, category) == enable:
            return False
        if enable:
            domain.add_category(category)
        else:
            domain.remove_category(category)
        return True

    #
    # email domain_info <domain>
    #
    # this command is accessible for all
    #
    all_commands['email_domain_info'] = Command(
        ("email", "domain_info"),
        SimpleString(help_ref="email_domain"),
        fs=FormatSuggestion([
            ("E-mail domain:    %s\n"
             "Description:      %s", ("domainname", "description")),
            ("Configuration:    %s", ("category",)),
            ("Affiliation:      %s@%s", ("affil", "ou"))
        ]))

    def email_domain_info(self, operator, domainname):
        """ Info about domain. """
        ed = self._get_email_domain_from_str(domainname)
        ret = []
        ret.append({
            'domainname': domainname,
            'description': ed.email_domain_description,
        })
        for r in ed.get_categories():
            ret.append({
                'category': str(self.const.EmailDomainCategory(r['category'])),
            })
        eed = Email.EntityEmailDomain(self.db)
        affiliations = {}
        for r in eed.list_affiliations(ed.entity_id):
            ou = self._get_ou(r['entity_id'])
            affname = "<any>"
            if r['affiliation']:
                affname = str(self.const.PersonAffiliation(r['affiliation']))
            affiliations[self._format_ou_name(ou)] = affname
        aff_list = affiliations.keys()
        aff_list.sort()
        for ou in aff_list:
            ret.append({
                'affil': affiliations[ou],
                'ou': ou,
            })
        return ret

    #
    # email add_domain_affiliation <domain> <stedkode> [<affiliation>]
    #
    all_commands['email_add_domain_affiliation'] = Command(
        ("email", "add_domain_affiliation"),
        SimpleString(help_ref="email_domain"),
        OU(),
        Affiliation(optional=True),
        perm_filter="can_email_domain_create")

    def email_add_domain_affiliation(self, operator,
                                     domainname, sko, aff=None):
        """ Add affiliation to domain. """
        self.ba.can_email_domain_create(operator.get_entity_id())
        ed = self._get_email_domain_from_str(domainname)
        try:
            ou = self._get_ou(stedkode=sko)
        except Errors.NotFoundError:
            raise CerebrumError("Unknown OU (%s)" % sko)
        aff_id = None
        if aff:
            aff_id = int(self._get_affiliationid(aff))
        eed = Email.EntityEmailDomain(self.db)
        try:
            eed.find(ou.entity_id, aff_id)
        except Errors.NotFoundError:
            # We have a partially initialised object, since
            # the super() call finding the OU always succeeds.
            # Therefore we must not call clear()
            eed.populate_email_domain(ed.entity_id, aff_id)
            eed.write_db()
            count = self._update_email_for_ou(ou.entity_id, aff_id)
            # Perhaps we should return the values with a format
            # suggestion instead, but the message is informational,
            # and we have three different formats so it would be
            # awkward to do "right".
            return "OK, %d accounts updated" % count
        else:
            old_dom = eed.entity_email_domain_id
            if old_dom != ed.entity_id:
                eed.entity_email_domain_id = ed.entity_id
                eed.write_db()
                count = self._update_email_for_ou(ou.entity_id, aff_id)
                ed.clear()
                ed.find(old_dom)
                return "OK (was %s), %d accounts updated" % (
                       ed.email_domain_name, count)
            return "OK (no change)"

    def _update_email_for_ou(self, ou_id, aff_id):
        """ Update the e-mail addresses for a given OU.

        Updates email-address for all accounts where the given affiliation is
        their primary, and returns the number of modified accounts.

        """
        count = 0
        acc = self.Account_class(self.db)
        acc2 = self.Account_class(self.db)
        for r in acc.list_accounts_by_type(ou_id=ou_id, affiliation=aff_id):
            acc2.clear()
            acc2.find(r['account_id'])
            primary = acc2.get_account_types()[0]
            if (ou_id == primary['ou_id'] and
                    (aff_id is None or aff_id == primary['affiliation'])):
                acc2.update_email_addresses()
                count += 1
        return count

    #
    # email remove_domain_affiliation <domain> <stedkode> [<affiliation>]
    #
    all_commands['email_remove_domain_affiliation'] = Command(
        ("email", "remove_domain_affiliation"),
        SimpleString(help_ref="email_domain"),
        OU(),
        Affiliation(optional=True),
        perm_filter="can_email_domain_create")

    def email_remove_domain_affiliation(self, operator, domainname, sko,
                                        aff=None):
        """ Remove domain affs. """
        self.ba.can_email_domain_create(operator.get_entity_id())
        ed = self._get_email_domain_from_str(domainname)
        try:
            ou = self._get_ou(stedkode=sko)
        except Errors.NotFoundError:
            raise CerebrumError("Unknown OU (%s)" % sko)
        aff_id = None
        if aff:
            aff_id = int(self._get_affiliationid(aff))
        eed = Email.EntityEmailDomain(self.db)
        try:
            eed.find(ou.entity_id, aff_id)
        except Errors.NotFoundError:
            raise CerebrumError("No such affiliation for domain")
        if eed.entity_email_domain_id != ed.entity_id:
            raise CerebrumError("No such affiliation for domain")
        eed.delete()
        return "OK, removed domain-affiliation for '%s'" % domainname

    #
    # email create_forward <local-address> <remote-address>
    #
    all_commands['email_create_forward_target'] = Command(
        ("email", "create_forward"),
        EmailAddress(),
        EmailAddress(help_ref='email_forward_address'),
        perm_filter="can_email_forward_create")

    def email_create_forward_target(self, operator, localaddr, remoteaddr):
        """ Create forward target.

        Creates a forward target, add localaddr as an address associated with
        that target, and add remoteaddr as a forward addresses.
        """
        lp, dom = self._split_email_address(localaddr)
        ed = self._get_email_domain_from_str(dom)
        self.ba.can_email_forward_create(operator.get_entity_id(), ed)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.entity_id)
        except Errors.NotFoundError:
            pass
        else:
            raise CerebrumError("Address %s already exists" % localaddr)
        et = Email.EmailTarget(self.db)
        et.populate(self.const.email_target_forward)
        et.write_db()
        ea.clear()
        ea.populate(lp, ed.entity_id, et.entity_id)
        ea.write_db()
        epat = Email.EmailPrimaryAddressTarget(self.db)
        epat.populate(ea.entity_id, parent=et)
        epat.write_db()
        ef = Email.EmailForward(self.db)
        ef.find(et.entity_id)
        addr = check_email_address(remoteaddr)
        try:
            ef.add_forward(addr)
        except Errors.TooManyRowsError:
            raise CerebrumError("Forward address added already (%s)" % addr)
        self._configure_spam_settings(et)
        self._configure_filter_settings(et)
        return "OK, created forward address '%s'" % localaddr

    #
    # email create_multi <multi-address> <group>
    #
    all_commands['email_create_multi'] = Command(
        ("email", "create_multi"),
        EmailAddress(help_ref="email_address"),
        GroupName(help_ref="group_name_dest"),
        perm_filter="can_email_multi_create")

    def email_create_multi(self, operator, addr, group):
        """ Create en e-mail target of type 'multi'. """
        lp, dom = self._split_email_address(addr)
        ed = self._get_email_domain_from_str(dom)
        gr = self._get_group(group)
        self.ba.can_email_multi_create(operator.get_entity_id(),
                                       domain=ed,
                                       group=gr)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.entity_id)
        except Errors.NotFoundError:
            pass
        else:
            raise CerebrumError("Address <%s> is already in use" % addr)
        et = Email.EmailTarget(self.db)
        et.populate(self.const.email_target_multi,
                    target_entity_type=self.const.entity_group,
                    target_entity_id=gr.entity_id)
        et.write_db()
        ea.clear()
        ea.populate(lp, ed.entity_id, et.entity_id)
        ea.write_db()
        epat = Email.EmailPrimaryAddressTarget(self.db)
        epat.populate(ea.entity_id, parent=et)
        epat.write_db()
        self._configure_spam_settings(et)
        self._configure_filter_settings(et)
        return "OK, multi-target for '%s' created" % addr

    #
    # email delete_multi <address>
    #
    all_commands['email_delete_multi'] = Command(
        ("email", "delete_multi"),
        EmailAddress(help_ref="email_address"),
        fs=FormatSuggestion([("Deleted address: %s", ("address", ))]),
        perm_filter="can_email_multi_delete")

    def email_delete_multi(self, operator, addr):
        """ Delete multi target. """
        lp, dom = self._split_email_address(addr)
        ed = self._get_email_domain_from_str(dom)
        et, acc = self._get_email_target_and_account(addr)
        if et.email_target_type != self.const.email_target_multi:
            raise CerebrumError("%s: Not a multi target" % addr)
        if et.email_target_entity_type != self.const.entity_group:
            raise CerebrumError("%s: Does not point to a group!" % addr)
        gr = self._get_group(et.email_target_entity_id, idtype="id")
        self.ba.can_email_multi_delete(operator.get_entity_id(), ed, gr)
        epat = Email.EmailPrimaryAddressTarget(self.db)
        try:
            epat.find(et.entity_id)
        except Errors.NotFoundError:
            # a multi target does not need a primary address
            pass
        else:
            # but if one exists, we require the user to supply that
            # address, not an arbitrary alias.
            if addr != self._get_address(epat):
                raise CerebrumError("%s is not the primary address of "
                                    "the target" % addr)
            epat.delete()
        # All OK, let's nuke it all.
        result = []
        ea = Email.EmailAddress(self.db)
        for r in et.get_addresses():
            ea.clear()
            ea.find(r['address_id'])
            result.append({'address': self._get_address(ea)})
            ea.delete()
        return result

    #
    # email pause
    #
    all_commands['email_pause'] = Command(
        ("email", "pause"),
        SimpleString(help_ref='string_email_on_off'),
        AccountName(help_ref="account_name"),
        perm_filter='can_email_pause')

    def email_pause(self, operator, on_off, uname):
        """ Pause email delivery. """
        et, acc = self._get_email_target_and_account(uname)
        self.ba.can_email_pause(operator.get_entity_id(), acc)

        dn = cereconf.LDAP_EMAIL_DN % et.entity_id

        conn_params = [
            cereconf.LDAP_MASTER,
            cereconf.LDAP_BIND_DN % cereconf.LDAP_UPDATE_USER,
            Utils.read_password(cereconf.LDAP_SYSTEM,
                                cereconf.LDAP_UPDATE_USER),
            cereconf.LDAP_RETRY_MAX,
            cereconf.LDAP_RETRY_DELAY, ]

        ldap = LdapUpdater()

        if on_off in ('ON', 'on'):
            et.populate_trait(self.const.trait_email_pause, et.entity_id)
            et.write_db()
            ldap.connect(*conn_params)
            r = ldap.modify(dn, "mailPause", "TRUE")
            if r:
                et.commit()
                return "mailPause set for '%s'" % uname
            else:
                et._db.rollback()
                raise CerebrumError("Error: mailPause not set for '%s'" %
                                    uname)

        elif on_off in ('OFF', 'off'):
            try:
                et.delete_trait(self.const.trait_email_pause)
                et.write_db()
            except Errors.NotFoundError:
                raise CerebrumError("Error: mailPause not unset for '%s'" %
                                    uname)

            ldap.connect(*conn_params)
            r = ldap.modify(dn, "mailPause")
            if r:
                et.commit()
                return "mailPause unset for '%s'" % uname
            else:
                et._db.rollback()
                return "Error: mailPause not unset for '%s'" % uname

        else:
            raise CerebrumError('Mailpause is either \'ON\' or \'OFF\'')

    #
    # email list_pause
    #
    all_commands['email_list_pause'] = Command(
        ("email", "list_pause"),
        perm_filter='can_email_pause',
        fs=FormatSuggestion([("Paused addresses:\n%s", ("paused", ))]),)

    def email_list_pause(self, operator):
        """ Pause email delivery to list. """
        self.ba.can_email_pause(operator.get_entity_id())
        ac = self.Account_class(self.db)
        et = Email.EmailTarget(self.db)
        ea = Email.EmailAddress(self.db)
        epa = Email.EmailPrimaryAddressTarget(self.db)

        res = []
        for row in et.list_traits(code=self.const.trait_email_pause):
            try:
                et.clear()
                et.find(row['entity_id'])
                target_type = self.const.EmailTarget(et.email_target_type)
                if target_type == self.const.email_target_account:
                    ac.clear()
                    ac.find(et.email_target_entity_id)
                    res.append(ac.account_name)
                else:
                    epa.clear()
                    epa.find_by_alias(et.email_target_alias)
                    ea.clear()
                    ea.find(epa.email_primaddr_id)
                    res.append(ea.get_address())
            except Exception as e:
                raise CerebrumError("Failed for target id=%r type=%r: %r" %
                                    (et.entity_id, target_type, e))

        return {'paused': '\n'.join(res)}

    #
    # email quota <uname>+ hardquota-in-mebibytes [softquota-in-percent]
    #
    all_commands['email_quota'] = Command(
        ('email', 'quota'),
        AccountName(help_ref='account_name', repeat=True),
        Integer(help_ref='number_size_mib'),
        Integer(help_ref='number_percent', optional=True),
        perm_filter='can_email_set_quota')

    def email_quota(self, operator, uname, hquota,
                    squota=cereconf.EMAIL_SOFT_QUOTA):
        """ Set email quota. """
        op = operator.get_entity_id()
        acc = self._get_account(uname)
        self.ba.can_email_set_quota(op, acc)
        if not all(str(arg).isdigit() for arg in (hquota, squota)):
            raise CerebrumError("Quota must be numeric")
        hquota = int(hquota)
        squota = int(squota)
        if hquota < 100 and hquota != 0:
            raise CerebrumError("The hard quota can't be less than 100 MiB")
        if hquota > 1024*1024:
            raise CerebrumError("The hard quota can't be more than 1 TiB")
        if squota < 10 or squota > 99:
            raise CerebrumError("The soft quota must be in the interval"
                                " 10% to 99%")
        et = Email.EmailTarget(self.db)
        try:
            et.find_by_target_entity(acc.entity_id)
        except Errors.NotFoundError:
            raise CerebrumError("The account %s has no e-mail data associated"
                                " with it" % uname)
        eq = Email.EmailQuota(self.db)
        change = False
        try:
            eq.find_by_target_entity(acc.entity_id)
            if eq.email_quota_hard != hquota:
                change = True
            eq.email_quota_hard = hquota
            eq.email_quota_soft = squota
        except Errors.NotFoundError:
            eq.clear()
            if hquota != 0:
                eq.populate(squota, hquota, parent=et)
                change = True
        if hquota == 0:
            eq.delete()
        else:
            eq.write_db()
        if change:
            # If we're supposed to put a request in BofhdRequests we'll have to
            # be sure that the user getting the quota is a Cyrus-user. If not,
            # Cyrus will spew out errors telling us "user foo is not a
            # cyrus-user".
            if not et.email_server_id:
                raise CerebrumError("The account %s has no e-mail server"
                                    " associated with it" % uname)
            es = Email.EmailServer(self.db)
            es.find(et.email_server_id)

            if es.email_server_type == self.const.email_server_type_cyrus:
                br = BofhdRequests(self.db, self.const)
                # if this operator has already asked for a quota change, but
                # process_bofh_requests hasn't run yet, delete the existing
                # request to avoid the annoying error message.
                for r in br.get_requests(
                        operation=self.const.bofh_email_hquota,
                        operator_id=op,
                        entity_id=acc.entity_id):
                    br.delete_request(request_id=r['request_id'])
                br.add_request(op, br.now, self.const.bofh_email_hquota,
                               acc.entity_id, None)
        return "OK, set quota for '%s'" % uname

    #
    # email add_filter filter address
    #
    all_commands['email_add_filter'] = Command(
        ('email', 'add_filter'),
        SimpleString(help_ref='string_email_filter'),
        SimpleString(help_ref='string_email_target_name', repeat="True"),
        perm_filter='can_email_spam_settings')

    def email_add_filter(self, operator, filter, address):
        """ Add a filter to an existing e-mail target. """
        et, acc = self._get_email_target_and_account(address)
        self.ba.can_email_spam_settings(operator.get_entity_id(),
                                        account=acc,
                                        target=et)
        etf = Email.EmailTargetFilter(self.db)
        filter_code = self._get_constant(self.const.EmailTargetFilter, filter)
        et, addr = self._get_email_target_and_address(address)
        target_ids = [et.entity_id]

        # TODO: How can we make this work?
        if et.email_target_type == self.const.email_target_Sympa:
            # The only way we can get here is if uname is actually an e-mail
            # address on its own.
            # This will fail if we don't have the BofhdEmailListMixin
            # TODO: Sympa
            target_ids = self._get_all_related_maillist_targets(address)
        elif int(et.email_target_type) == (self.const.email_target_RT):
            # Same, will fail if we don't have the BofhdEmailListMixin
            target_ids = self.__get_all_related_rt_targets(address)
        for target_id in target_ids:
            try:
                et.clear()
                et.find(target_id)
            except Errors.NotFoundError:
                continue

            try:
                etf.clear()
                etf.find(et.entity_id, filter_code)
            except Errors.NotFoundError:
                etf.clear()
                etf.populate(filter_code, parent=et)
                etf.write_db()

        return "Ok, registered filter %s for %s" % (filter, address)

    #
    # email remove_filter filter address
    #
    all_commands['email_remove_filter'] = Command(
        ('email', 'remove_filter'),
        SimpleString(help_ref='string_email_filter'),
        SimpleString(help_ref='string_email_target_name', repeat="True"),
        perm_filter='can_email_spam_settings')

    def email_remove_filter(self, operator, filter, address):
        """ Remove filter. """
        et, acc = self._get_email_target_and_account(address)
        self.ba.can_email_spam_settings(operator.get_entity_id(),
                                        account=acc,
                                        target=et)
        etf = Email.EmailTargetFilter(self.db)
        filter_code = self._get_constant(self.const.EmailTargetFilter, filter)
        et, addr = self._get_email_target_and_address(address)
        target_ids = [et.entity_id]
        if et.email_target_type == self.const.email_target_Sympa:
            # The only way we can get here is if uname is actually an e-mail
            # address on its own.
            #
            # This will fail if we don't have the BofhdEmailListMixin
            target_ids = self._get_all_related_maillist_targets(address)
        elif int(et.email_target_type) == (self.const.email_target_RT):
            # Same, will fail if we don't have the BofhdEmailListMixin
            target_ids = self._get_all_related_rt_targets(address)
        processed = list()
        for target_id in target_ids:
            try:
                etf.clear()
                etf.find(target_id, filter_code)
                etf.disable_email_target_filter(filter_code)
                etf.write_db()
                processed.append(target_id)
            except Errors.NotFoundError:
                pass

        if not processed:
            raise CerebrumError(
                "Could not find any filters %s for address %s "
                "(or any related targets)" % (filter, address))

        return "Ok, removed filter %s for %s" % (filter, address)

    #
    # email spam_level <level> <uname>+
    #
    all_commands['email_spam_level'] = Command(
        ('email', 'spam_level'),
        SimpleString(help_ref='spam_level'),
        AccountName(help_ref='account_name', repeat=True),
        perm_filter='can_email_spam_settings')

    def email_spam_level(self, operator, level, uname):
        """ Set the spam level for the EmailTarget associated with username.

        It is also possible for super users to pass the name of other email
        targets.

        """
        try:
            levelcode = int(self.const.EmailSpamLevel(level))
        except Errors.NotFoundError:
            raise CerebrumError("Spam level code not found: {}".format(level))
        et, acc = self._get_email_target_and_account(uname)
        self.ba.can_email_spam_settings(operator.get_entity_id(), acc, et)
        esf = Email.EmailSpamFilter(self.db)
        # All this magic with target ids is necessary to accomodate MLs (all
        # ETs "related" to the same ML should have the
        # spam settings should be processed )
        target_ids = [et.entity_id]
        # The only way we can get here is if uname is actually an e-mail
        # address on its own.
        if et.email_target_type == self.const.email_target_Sympa:
            target_ids = self._get_all_related_maillist_targets(uname)
        elif int(et.email_target_type) == self.const.email_target_RT:
            target_ids = self._get_all_related_rt_targets(uname)

        for target_id in target_ids:
            try:
                et.clear()
                et.find(target_id)
            except Errors.NotFoundError:
                continue
            try:
                esf.clear()
                esf.find(et.entity_id)
                esf.email_spam_level = levelcode
            except Errors.NotFoundError:
                esf.clear()
                esf.populate(levelcode, self.const.email_spam_action_none,
                             parent=et)
            esf.write_db()

        return "OK, set spam-level for '%s'" % uname

    #
    # email spam_action <action> <uname>+
    #
    # (This code is cut'n'paste of email_spam_level(), only the call
    # to populate() had to be fixed manually. It's hard to fix this
    # kind of code duplication cleanly.)
    #
    all_commands['email_spam_action'] = Command(
        ('email', 'spam_action'),
        SimpleString(help_ref='spam_action'),
        AccountName(help_ref='account_name', repeat=True),
        perm_filter='can_email_spam_settings')

    def email_spam_action(self, operator, action, uname):
        """Set the spam action for the EmailTarget associated with username.

        It is also possible for super users to pass the name of other email
        targets.

        """
        try:
            actioncode = int(self.const.EmailSpamAction(action))
        except Errors.NotFoundError:
            raise CerebrumError("Spam action code not found:"
                                " {}".format(action))
        et, acc = self._get_email_target_and_account(uname)
        self.ba.can_email_spam_settings(operator.get_entity_id(), acc, et)
        esf = Email.EmailSpamFilter(self.db)
        # All this magic with target ids is necessary to accomodate MLs (all
        # ETs "related" to the same ML should have the
        # spam settings should be processed )
        target_ids = [et.entity_id]
        # The only way we can get here is if uname is actually an e-mail
        # address on its own.
        if et.email_target_type == self.const.email_target_Sympa:
            target_ids = self._get_all_related_maillist_targets(uname)
        elif int(et.email_target_type) == self.const.email_target_RT:
            target_ids = self._get_all_related_rt_targets(uname)

        for target_id in target_ids:
            try:
                et.clear()
                et.find(target_id)
            except Errors.NotFoundError:
                continue

            try:
                esf.clear()
                esf.find(et.entity_id)
                esf.email_spam_action = actioncode
            except Errors.NotFoundError:
                esf.clear()
                esf.populate(self.const.email_spam_level_none, actioncode,
                             parent=et)
            esf.write_db()

        return "OK, set spam-action for '%s'" % uname

    #
    # email tripnote on|off <uname> [<begin-date>]
    #
    all_commands['email_tripnote'] = Command(
        ('email', 'tripnote'),
        SimpleString(help_ref='email_tripnote_action'),
        AccountName(help_ref='account_name'),
        SimpleString(help_ref='date', optional=True),
        perm_filter='can_email_tripnote_toggle')

    def email_tripnote(self, operator, action, uname, when=None):
        """ Turn on/off tripnote. """
        acc = self._get_account(uname)
        self.ba.can_email_tripnote_toggle(operator.get_entity_id(),
                                          account=acc)

        if action == 'on':
            enable = True
        elif action == 'off':
            enable = False
        else:
            raise CerebrumError("Unknown tripnote action %r, choose one of"
                                " 'on' or 'off'" % action)

        ev = Email.EmailVacation(self.db)
        ev.find_by_target_entity(acc.entity_id)
        # TODO: If 'enable' at this point actually is None (which, by
        # the looks of the if-else clause at the top seems
        # impossible), opposite_status won't be defined, and hence the
        # ._find_tripnote() call below will fail.
        if enable is not None:
            opposite_status = not enable
        date = self._find_tripnote(uname, ev, when, opposite_status)
        ev.enable_vacation(date, enable)
        ev.write_db()
        return "OK, set tripnote to '%s' for '%s'" % (action, uname)

    #
    # email list tripnotes <uname>
    #
    all_commands['email_list_tripnotes'] = Command(
        ('email', 'list_tripnotes'),
        AccountName(help_ref='account_name'),
        fs=FormatSuggestion([
            ("%s%s -- %s: %s\n"
             "%s\n",
             ("dummy", format_day('start_date'), format_day('end_date'),
              "enable", "text"))
        ]),
        perm_filter='can_email_tripnote_toggle'
    )

    def email_list_tripnotes(self, operator, uname):
        """ List tripnotes for a user. """
        acc = self._get_account(uname)
        self.ba.can_email_tripnote_toggle(operator.get_entity_id(),
                                          account=acc)

        try:
            self.ba.can_email_tripnote_edit(operator.get_entity_id(),
                                            account=acc)
            hide = False
        except PermissionDenied:
            hide = True

        ev = Email.EmailVacation(self.db)
        try:
            ev.find_by_target_entity(acc.entity_id)
        except Errors.NotFoundError:
            raise CerebrumError("No tripnotes for %s" % uname)

        now = self._today()
        act_date = None
        for r in ev.get_vacation():
            if r['end_date'] is not None and r['start_date'] > r['end_date']:
                self.logger.info(
                    "bogus tripnote for %s, start at %s, end at %s"
                    % (uname, r['start_date'], r['end_date']))
                ev.delete_vacation(r['start_date'])
                ev.write_db()
                continue
            if r['enable'] == 'F':
                continue
            if r['end_date'] is not None and r['end_date'] < now:
                continue
            if r['start_date'] > now:
                break
            # get_vacation() returns a list ordered by start_date, so
            # we know this one is newer.
            act_date = r['start_date']

        result = []
        for r in ev.get_vacation():
            text = r['vacation_text']
            if r['enable'] == 'F':
                enable = "OFF"
            elif r['end_date'] is not None and r['end_date'] < now:
                enable = "OLD"
            elif r['start_date'] > now:
                enable = "PENDING"
            else:
                enable = "ON"
            if act_date is not None and r['start_date'] == act_date:
                enable = "ACTIVE"
            elif hide:
                text = "<text is hidden>"
            # TODO: FormatSuggestion won't work with a format_day()
            # coming first, so we use an empty dummy string as a
            # workaround.
            result.append({
                'dummy': "",
                'start_date': r['start_date'],
                'end_date': r['end_date'],
                'enable': enable,
                'text': text,
            })
        if result:
            return result
        raise CerebrumError("No tripnotes for %s" % uname)

    #
    # email add_tripnote <uname> <text> <begin-date>[-<end-date>]
    #
    all_commands['email_add_tripnote'] = Command(
        ('email', 'add_tripnote'),
        AccountName(help_ref='account_name'),
        SimpleString(help_ref='tripnote_text'),
        SimpleString(help_ref='string_from_to'),
        perm_filter='can_email_tripnote_edit')

    def email_add_tripnote(self, operator, uname, text, when=None):
        """ Add a tripnote. """
        acc = self._get_account(uname)
        self.ba.can_email_tripnote_edit(operator.get_entity_id(), account=acc)
        date_start, date_end = self._parse_date_from_to(when)
        now = self._today()
        if date_end is not None and date_end < now:
            raise CerebrumError("Won't add already obsolete tripnotes")
        ev = Email.EmailVacation(self.db)
        ev.find_by_target_entity(acc.entity_id)
        for v in ev.get_vacation():
            if date_start is not None and v['start_date'] == date_start:
                raise CerebrumError("There's a tripnote starting on %s"
                                    " already" % str(date_start)[:10])

        # FIXME: The SquirrelMail plugin sends CR LF which xmlrpclib
        # (AFAICT) converts into LF LF.  Remove the double line
        # distance.  jbofh users have to send backslash n anyway, so
        # this won't affect common usage.
        text = text.replace('\n\n', '\n')
        text = text.replace('\\n', '\n')
        ev.add_vacation(date_start, text, date_end, enable=True)
        ev.write_db()
        return "OK, added tripnote for '%s'" % uname

    #
    # email remove_tripnote <uname> [<when>]
    #
    all_commands['email_remove_tripnote'] = Command(
        ('email', 'remove_tripnote'),
        AccountName(help_ref='account_name'),
        SimpleString(help_ref='date', optional=True),
        perm_filter='can_email_tripnote_edit')

    def email_remove_tripnote(self, operator, uname, when=None):
        """ Remove tripnote. """
        acc = self._get_account(uname)
        self.ba.can_email_tripnote_edit(operator.get_entity_id(), account=acc)
        self._parse_date(when)  # TBD: Validation or code rot?
        ev = Email.EmailVacation(self.db)
        ev.find_by_target_entity(acc.entity_id)
        date = self._find_tripnote(uname, ev, when)
        ev.delete_vacation(date)
        ev.write_db()
        return "OK, removed tripnote for '%s'" % uname

    def _find_tripnote(self, uname, ev, when=None, enabled=None):
        vacs = ev.get_vacation()
        if enabled is not None:
            nv = []
            for v in vacs:
                if (v['enable'] == 'T') == enabled:
                    nv.append(v)
            vacs = nv
        if len(vacs) == 0:
            if enabled is None:
                raise CerebrumError("User %s has no stored tripnotes" % uname)
            elif enabled:
                raise CerebrumError("User %s has no enabled tripnotes" % uname)
            else:
                raise CerebrumError("User %s has no disabled tripnotes" %
                                    uname)
        elif len(vacs) == 1:
            return vacs[0]['start_date']
        elif when is None:
            raise CerebrumError("User %r has more than one tripnote, specify"
                                " which one by adding the start date to"
                                " command" % uname)
        start = self._parse_date(when)
        best = None
        best_delta = None
        for r in vacs:
            delta = abs(r['start_date'] - start)
            if best is None or delta < best_delta:
                best = r['start_date']
                best_delta = delta
        # TODO: in PgSQL, date arithmetic is in days, but casting
        # it to int returns seconds.  The behaviour is undefined
        # in the DB-API.
        if abs(int(best_delta)) > 1.5 * 86400:
            raise CerebrumError("There are no tripnotes starting at %s" % when)
        return best

    #
    # email update <uname>
    # Anyone can run this command.  Ideally, it should be a no-op,
    # and we should remove it when that is true.
    #
    all_commands['email_update'] = Command(
        ('email', 'update'),
        AccountName(help_ref='account_name', repeat=True))

    def email_update(self, operator, uname):
        """ Email update. """
        acc = self._get_account(uname, idtype='name')
        acc.update_email_addresses()
        return "OK, updated e-mail address for '%s'" % uname


class BofhdRtAuth(BofhdEmailAuth):

    def can_rt_create(self, operator, domain=None, query_run_any=False):
        if self.is_superuser(operator, query_run_any):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_rt_create)
        return self._query_maildomain_permissions(
            operator, self.const.auth_rt_create, domain, None)

    def can_rt_delete(self, operator, **kwargs):
        return self.can_rt_create(operator, **kwargs)

    def can_rt_address_add(self, operator, domain=None, query_run_any=False):
        if self.is_superuser(operator, query_run_any):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_rt_addr_add)
        return self._query_maildomain_permissions(
            operator, self.const.auth_rt_addr_add, domain, None)

    def can_rt_address_remove(self, operator, **kwargs):
        return self.can_rt_address_add(operator, **kwargs)


class BofhdRtCommands(BofhdEmailBase):
    """ RT related commands. """

    all_commands = {}
    hidden_commands = {}

    authz = BofhdRtAuth
    omit_parent_commands = set()
    parent_commands = False

    @classmethod
    def get_help_strings(cls):
        return merge_help_strings(
            super(BofhdRtCommands, cls).get_help_strings(),
            ({}, HELP_RT_CMDS, HELP_RT_ARGS))

    def _get_rt_email_target(self, queue, host):
        """ Get the EmailTarget for an RT queue. """
        et = Email.EmailTarget(self.db)
        try:
            et.find_by_alias(format_rt_pipe("correspond", queue, host))
        except Errors.NotFoundError:
            raise CerebrumError("Unknown RT queue %s on host %s" %
                                (queue, host))
        return et

    #
    # rt create queue[@host] address [force]
    #
    all_commands['rt_create'] = Command(
        ("rt", "create"),
        RTQueue(),
        EmailAddress(),
        YesNo(help_ref="yes_no_force", optional=True),
        perm_filter='can_rt_create')

    def rt_create(self, operator, queuename, addr, force="No"):
        """ Create rt queue. """

        queue, host = self._resolve_rt_name(queuename)
        rt_dom = self._get_email_domain_from_str(host)
        op = operator.get_entity_id()
        self.ba.can_rt_create(op, domain=rt_dom)
        try:
            self._get_rt_email_target(queue, host)
        except CerebrumError:
            pass
        else:
            raise CerebrumError("RT queue %s already exists" % queuename)
        addr_lp, addr_domain_name = self._split_email_address(addr)
        addr_dom = self._get_email_domain_from_str(addr_domain_name)
        if addr_domain_name != host:
            self.ba.can_email_address_add(operator.get_entity_id(),
                                          domain=addr_dom)
        replaced_lists = []

        # Unusual characters will raise an exception, a too short name
        # will return False, which we ignore for the queue name.
        self._is_ok_mailing_list_name(queue)

        # The submission address is only allowed to be short if it is
        # equal to the queue name, or the operator is a global
        # postmaster.
        if not (self._is_ok_mailing_list_name(addr_lp) or
                addr == queue + "@" + host or
                self.ba.is_postmaster(op)):
            raise CerebrumError("Illegal address for submission: %s" % addr)

        # Check if list exists and is replaceable
        try:
            et, ea = self._get_email_target_and_address(addr)
        except CerebrumError:
            pass
        else:
            raise CerebrumError("Address <{}> is in use".format(addr))

        acc = self._get_account("exim")
        et = Email.EmailTarget(self.db)
        ea = Email.EmailAddress(self.db)
        cmd = format_rt_pipe("correspond", queue, host)
        et.populate(self.const.email_target_RT, alias=cmd,
                    using_uid=acc.entity_id)
        et.write_db()

        # Add primary address
        ea.populate(addr_lp, addr_dom.entity_id, et.entity_id)
        ea.write_db()
        epat = Email.EmailPrimaryAddressTarget(self.db)
        epat.populate(ea.entity_id, parent=et)
        epat.write_db()
        for alias in replaced_lists:
            if alias == addr:
                continue
            lp, dom = self._split_email_address(alias)
            alias_dom = self._get_email_domain_from_str(dom)
            ea.clear()
            ea.populate(lp, alias_dom.entity_id, et.entity_id)
            ea.write_db()

        # Add RT internal address
        if addr_lp != queue or addr_domain_name != host:
            ea.clear()
            ea.populate(queue, rt_dom.entity_id, et.entity_id)
            ea.write_db()

        # Moving on to the comment address
        et.clear()
        cmd = format_rt_pipe("comment", queue, host)
        et.populate(self.const.email_target_RT, alias=cmd,
                    using_uid=acc.entity_id)
        et.write_db()
        ea.clear()
        ea.populate("%s-comment" % queue, rt_dom.entity_id,
                    et.entity_id)
        ea.write_db()
        msg = "RT queue %s on %s added" % (queue, host)
        if replaced_lists:
            msg += ", replacing mailing list(s) %s" % ", ".join(replaced_lists)
        addr = queue + "@" + host

        all_targets = self._get_all_related_rt_targets(addr)

        for target_id in all_targets:
            et.clear()
            et.find(target_id)
            self._configure_spam_settings(et)
            self._configure_filter_settings(et)
        return msg

    #
    # rt delete queue[@host]
    #
    all_commands['rt_delete'] = Command(
        ("rt", "delete"),
        EmailAddress(),
        fs=FormatSuggestion([("Deleted address: %s", ("address", ))]),
        perm_filter='can_rt_delete')

    def rt_delete(self, operator, queuename):
        """ Delete RT list. """
        queue, host = self._resolve_rt_name(queuename)
        rt_dom = self._get_email_domain_from_str(host)
        self.ba.can_rt_delete(operator.get_entity_id(), domain=rt_dom)
        et = Email.EmailTarget(self.db)
        ea = Email.EmailAddress(self.db)
        epat = Email.EmailPrimaryAddressTarget(self.db)
        result = []

        for target_id in self._get_all_related_rt_targets(queuename):
            try:
                et.clear()
                et.find(target_id)
            except Errors.NotFoundError:
                continue

            epat.clear()
            try:
                epat.find(et.entity_id)
            except Errors.NotFoundError:
                pass
            else:
                epat.delete()
            for r in et.get_addresses():
                addr = '%(local_part)s@%(domain)s' % r
                ea.clear()
                ea.find_by_address(addr)
                ea.delete()
                result.append({'address': addr})
            et.delete()

        return result

    #
    # rt add_address queue[@host] address
    #
    all_commands['rt_add_address'] = Command(
        ('rt', 'add_address'),
        RTQueue(),
        EmailAddress(),
        perm_filter='can_rt_address_add')

    def rt_add_address(self, operator, queuename, address):
        """ RT add address. """
        queue, host = self._resolve_rt_name(queuename)
        rt_dom = self._get_email_domain_from_str(host)
        self.ba.can_rt_address_add(operator.get_entity_id(), domain=rt_dom)
        et = self._get_rt_email_target(queue, host)
        lp, dom = self._split_email_address(address)
        ed = self._get_email_domain_from_str(dom)
        if host != dom:
            self.ba.can_email_address_add(operator.get_entity_id(),
                                          domain=ed)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.entity_id)
            raise CerebrumError("Address already exists (%s)" % address)
        except Errors.NotFoundError:
            pass
        if not (self._is_ok_mailing_list_name(lp) or
                self.ba.is_postmaster(operator.get_entity_id())):
            raise CerebrumError("Illegal queue address: %s" % address)
        ea.clear()
        ea.populate(lp, ed.entity_id, et.entity_id)
        ea.write_db()
        return ("OK, added '%s' as e-mail address for '%s'" %
                (address, queuename))

    #
    # rt remove_address queue address
    #
    all_commands['rt_remove_address'] = Command(
        ('rt', 'remove_address'),
        RTQueue(),
        EmailAddress(),
        perm_filter='can_email_address_delete')

    def rt_remove_address(self, operator, queuename, address):
        """ RT remove address. """

        queue, host = self._resolve_rt_name(queuename)
        rt_dom = self._get_email_domain_from_str(host)
        self.ba.can_rt_address_remove(operator.get_entity_id(), domain=rt_dom)
        et = self._get_rt_email_target(queue, host)
        return self._remove_email_address(et, address)

    #
    # rt primary_address address
    #
    all_commands['rt_set_primary_address'] = Command(
        ("rt", "set_primary_address"),
        RTQueue(),
        EmailAddress(),
        fs=FormatSuggestion([("New primary address: '%s'", ("address", ))]),
        perm_filter="can_rt_address_add")

    def rt_set_primary_address(self, operator, queuename, address):
        """ RT set primary address. """

        queue, host = self._resolve_rt_name(queuename)
        self.ba.can_rt_address_add(
            operator.get_entity_id(),
            domain=self._get_email_domain_from_str(host))
        rt = self._get_rt_email_target(queue, host)
        et, ea = self._get_email_target_and_address(address)
        if rt.entity_id != et.entity_id:
            raise CerebrumError(
                "Address <%s> is not associated with RT queue %s" %
                (address, queuename))
        if self._set_email_primary_address(et, ea):
            return {'address': address}
        raise CerebrumError("%r is already primary address" % address)


class BofhdSympaAuth(BofhdEmailAuth):

    # All the list things are in BofhdEmailAuth
    def can_email_list_create(self, operator,
                              domain=None, query_run_any=False):
        if self.is_postmaster(operator, query_run_any):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")

    def can_email_list_delete(self, operator,
                              domain=None, query_run_any=False):
        return self.can_email_list_create(operator,
                                          domain=domain,
                                          query_run_any=query_run_any)


class BofhdSympaCommands(BofhdEmailBase):
    """ Email list related commands for the Sympa mailing list system. """

    all_commands = {}
    hidden_commands = {}

    authz = BofhdSympaAuth
    omit_parent_commands = set()
    parent_commands = False

    @classmethod
    def get_help_strings(cls):
        return merge_help_strings(
            super(BofhdSympaCommands, cls).get_help_strings(),
            (HELP_SYMPA_GROUP, HELP_SYMPA_CMDS, HELP_SYMPA_ARGS))

    def _request_list_localpart_domain(self, operator, listname, force=False):
        """ Request localpart and domain for new listname.

        This method checks if the given user can create a list with the given
        name. It will raise an error if the list cannot be created for the
        following reasons:
         - Mailing list exists
         - Mailing list name is illegal
         - Local part is a user, and the operator is not permitted to override
           this

        @param operator: The calling operator
        @param listname:
            The listname to validate and split into localpart and domain.
        @param force:
            True if the operation should be forced, even if a user exists with
            the same localpart.

        @return: tuple(str(localpart), str(somain))

        """
        local_part, domain = self._split_email_address(listname)
        ed = self._get_email_domain_from_str(domain)
        operator_id = operator.get_entity_id()
        # NOTE: Do not remove, this is where access control happens in the
        #       bofhd commands!
        self.ba.can_email_list_create(operator_id, ed)
        email_address = Email.EmailAddress(self.db)
        # First, check whether the address already exists
        try:
            email_address.find_by_local_part_and_domain(local_part,
                                                        ed.entity_id)
        except Errors.NotFoundError:
            pass
        else:
            raise CerebrumError("Mail address %s already exists" % listname)

        # Then check whether the mailing list name is a legal one.
        if not (self._is_ok_mailing_list_name(local_part) or
                self.ba.is_postmaster(operator_id)):
            raise CerebrumError("Illegal mailing list name '%s'" % listname)

        # Then, check whether there is a user name equal to local_part.
        try:
            self._get_account(local_part, idtype='name')
        except CerebrumError:
            pass
        else:
            if not (local_part in ('drift',) or
                    (self.ba.is_postmaster(operator_id) and force)):
                # TBD: This exception list should probably not be hardcoded
                # here -- but it's not obvious whether it should be a cereconf
                # value (implying that only site admins can modify the list)
                # or a database table.
                raise CerebrumError("%s is an existing username" % local_part)

        return (local_part, domain)

    def _validate_sympa_list(self, listname):
        """ Check whether L{listname} is the 'official' name for a sympa ML.

        Raises CerebrumError if it is not.
        """
        if self._get_sympa_list(listname) != listname:
            raise CerebrumError("%s is NOT the official Sympa list name" %
                                listname)
        return listname

    def _is_mailing_list(self, listname):
        """ Check whether L{listname} refers to a valid mailing list.

        :rtype: bool
        :return: True if listname points to a valid Sympa list, else False.

        """
        try:
            self._validate_sympa_list(listname)
            return True
        except CerebrumError:
            return False

    def _create_sympa_list(self, operator, listname, delivery_host,
                           force=False):
        """ Create a new Sympa list in cerebrum. """
        local_part, domain = self._request_list_localpart_domain(operator,
                                                                 listname,
                                                                 force=force)
        self._register_sympa_list_addresses(listname, local_part, domain,
                                            delivery_host)

        # register auto spam and filter settings for the list
        all_targets = self._get_all_related_maillist_targets(listname)
        et = Email.EmailTarget(self.db)
        for target_id in all_targets:
            et.clear()
            et.find(target_id)
            self._configure_spam_settings(et)
            self._configure_filter_settings(et)

    def _create_sympa_list_alias(self, operator, listname, address,
                                 delivery_host, force_alias=False):
        """Create an alias L{address} for an existing Sympa L{listname}.

        @type listname: basestring
        @param listname:
          Email address for an existing mailing list. This is the ML we are
          aliasing.

        @type address: basestring
        @param address:
          Email address which will be the alias.

        @type delivery_host: EmailServer instance or None.
        @param delivery_host: Host where delivery to the mail alias happens.

        """
        lp, dom = self._split_email_address(address)
        ed = self._get_email_domain_from_str(dom)
        # NOTE: Do not remove! This is where access control happens in the
        # bofhd commands
        self.ba.can_email_list_create(operator.get_entity_id(), ed)
        self._validate_sympa_list(listname)

        if not force_alias:
            try:
                self._get_account(lp, idtype='name')
            except CerebrumError:
                pass
            else:
                raise CerebrumError(
                    "Won't create list-alias %s, beause %s is a username" %
                    (address, lp))

        # we _don't_ check for "more than 8 characters in local
        # part OR it contains hyphen" since we assume the people
        # who have access to this command know what they are doing
        self._register_sympa_list_addresses(listname, lp, dom, delivery_host)

    def _register_sympa_list_addresses(self, listname, local_part, domain,
                                       delivery_host):
        """ Register all neccessary sympa addresses.

        Add list, request, editor, owner, subscribe and unsubscribe addresses
        to a sympa mailing list.

        @type listname: basestring
        @param listname:
            Sympa listname that the operation is about. listname is typically
            different from local_part@domain when we are creating an alias.
            local_part@domain is the alias, listname is the original listname.
            And since aliases should point to the 'original' ETs, we have to
            use listname to locate the ETs.

        @type local_part: basestring
        @param local_part: See domain

        @type domain: basestring
        @param domain:
            L{local_part} and domain together represent a new list address that
            we want to create.

        @type delivery_host: EmailServer instance.
        @param delivery_host:
            EmailServer where e-mail to L{listname} is to be delivered through.

        """

        if (delivery_host.email_server_type !=
                self.const.email_server_type_sympa):
            raise CerebrumError(
                "Delivery host %s has wrong type (%s) for sympa list %s" % (
                    delivery_host.get_name(self.const.host_namespace),
                    self.const.EmailServerType(
                        delivery_host.email_server_type),
                    listname))

        ed = Email.EmailDomain(self.db)
        ed.find_by_domain(domain)

        et = Email.EmailTarget(self.db)
        ea = Email.EmailAddress(self.db)
        epat = Email.EmailPrimaryAddressTarget(self.db)
        try:
            ea.find_by_local_part_and_domain(local_part, ed.entity_id)
        except Errors.NotFoundError:
            pass
        else:
            raise CerebrumError(
                "The address %s@%s is already in use" % (local_part, domain))

        sympa = self._get_account('sympa', idtype='name', actype='PosixUser')
        primary_ea_created = False
        listname_lp, listname_domain = listname.split("@")

        # For each of the addresses we are supposed to create...
        for pattern, pipe_destination in _sympa_addr2alias:
            address = pattern % locals()
            address_lp, address_domain = address.split("@")

            # pipe has to be derived from the original listname, since it's
            # used to locate the ET.
            pipe = pipe_destination % {'local_part': listname_lp,
                                       'domain': listname_domain,
                                       'listname': listname}

            # First check whether the address already exist. It should not.
            try:
                ea.clear()
                ea.find_by_local_part_and_domain(address_lp, ed.entity_id)
                raise CerebrumError("Can't add list %s as the address %s "
                                    "is already in use" % (listname,
                                                           address))
            except Errors.NotFoundError:
                pass

            # Then find the target for this particular email address. The
            # target may already exist, though.
            et.clear()
            try:
                et.find_by_alias_and_account(pipe, sympa.entity_id)
            except Errors.NotFoundError:
                et.populate(self.const.email_target_Sympa,
                            alias=pipe, using_uid=sympa.entity_id,
                            server_id=delivery_host.entity_id)
                et.write_db()

            # Then create the email address and associate it with the ET.
            ea.clear()
            ea.populate(address_lp, ed.entity_id, et.entity_id)
            ea.write_db()

            # And finally, the primary address. The first entry in
            # _sympa_addr2alias will match. Do not reshuffle that tuple!
            if not primary_ea_created:
                epat.clear()
                try:
                    epat.find(et.entity_id)
                except Errors.NotFoundError:
                    epat.clear()
                    epat.populate(ea.entity_id, parent=et)
                    epat.write_db()
                primary_ea_created = True

    def _email_info_sympa(self, operator, et, addr):
        """ Collect Sympa-specific information for a ML L{addr}. """

        def fish_information(suffix, local_part, domain, listname):
            """Generate an entry for sympa info for the specified address.

            @type address: basestring
            @param address:
              Is the address we are looking for (we locate ETs based on the
              alias value in _sympa_addr2alias).
            @type et: EmailTarget instance

            @rtype: sequence (of dicts of basestring to basestring)
            @return:
              A sequence of dicts suitable for merging into return value from
              email_info_sympa.
            """

            result = []
            address = "%(local_part)s-%(suffix)s@%(domain)s" % locals()
            target_alias = None
            for a, alias in _sympa_addr2alias:
                a = a % locals()
                if a == address:
                    target_alias = alias % locals()
                    break

            # IVR 2008-08-05 TBD Is this an error? All sympa ETs must have an
            # alias in email_target.
            if target_alias is None:
                return result

            try:
                # Do NOT change et's (parameter's) state.
                et_tmp = Email.EmailTarget(self.db)
                et_tmp.clear()
                et_tmp.find_by_alias(target_alias)
            except Errors.NotFoundError:
                return result

            addrs = et_tmp.get_addresses()
            if not addrs:
                return result

            pattern = '%(local_part)s@%(domain)s'
            result.append({'sympa_' + suffix + '_1': pattern % addrs[0]})
            for idx in range(1, len(addrs)):
                result.append({'sympa_' + suffix: pattern % addrs[idx]})
            return result
        # end fish_information

        # listname may be one of the secondary addresses.
        # email info sympatest@domain MUST be equivalent to
        # email info sympatest-admin@domain.
        listname = self._get_sympa_list(addr)
        ret = [{"sympa_list": listname}]
        if listname.count('@') == 0:
            lp, dom = listname, addr.split('@')[1]
        else:
            lp, dom = listname.split('@')

        ed = Email.EmailDomain(self.db)
        ed.find_by_domain(dom)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.entity_id)
        except Errors.NotFoundError:
            raise CerebrumError(
                "Address %s exists, but the list it points to, %s, does not" %
                (addr, listname))
        # now find all e-mail addresses
        et_sympa = Email.EmailTarget(self.db)
        et_sympa.clear()
        et_sympa.find(ea.email_addr_target_id)
        addrs = self._get_valid_email_addrs(et_sympa, sort=True)
        # IVR 2008-08-21 According to postmasters, only superusers should see
        # forwarding and delivery host information
        if self.ba.is_postmaster(operator.get_entity_id()):
            if et_sympa.email_server_id is None:
                delivery_host = "N/A (this is an error)"
            else:
                delivery_host = self._get_server_from_ident(
                    et_sympa.email_server_id).name
            ret.append({"sympa_delivery_host": delivery_host})
        ret += self._email_info_forwarding(et_sympa, addrs)
        aliases = []
        for row in et_sympa.get_addresses():
            a = "%(local_part)s@%(domain)s" % row
            if a == listname:
                continue
            aliases.append(a)
        if aliases:
            ret.append({"sympa_alias_1": aliases[0]})
        for next_alias in aliases[1:]:
            ret.append({"sympa_alias": next_alias})

        for suffix in ("owner", "request", "editor", "subscribe",
                       "unsubscribe"):
            ret.extend(fish_information(suffix, lp, dom, listname))

        return ret

    #
    # sympa create_list <run-host> <delivery-host> <listaddr> <admins>
    #                   <profile> <desc> [force?]
    #
    all_commands['sympa_create_list'] = Command(
        ("sympa", "create_list"),
        SimpleString(help_ref='string_exec_host'),
        SimpleString(help_ref='string_email_delivery_host'),
        EmailAddress(help_ref="mailing_list"),
        SimpleString(help_ref="mailing_admins"),
        SimpleString(help_ref="mailing_list_profile"),
        SimpleString(help_ref="mailing_list_description"),
        YesNo(help_ref="yes_no_force", optional=True, default="No"),
        fs=FormatSuggestion([("Sympa list '%s' created", ('listname', ))]),
        perm_filter="can_email_list_create")

    def sympa_create_list(self, operator, run_host, delivery_host, listname,
                          admins, list_profile, list_description,
                          yes_no_force="No"):
        """ Create a sympa list in Cerebrum and on the sympa server(s).

        Registers all the necessary cerebrum information and make a bofhd
        request for the actual list creation.

        """
        # Check that the profile is legal
        if list_profile not in cereconf.SYMPA_PROFILES:
            raise CerebrumError("Profile %s for sympa list %s is not valid" %
                                (list_profile, listname))

        # Check that the command exec host is sane
        if run_host not in cereconf.SYMPA_RUN_HOSTS:
            raise CerebrumError("run-host '%s' for list '%s' is not valid" %
                                (run_host, listname))

        metachars = "'\"$&()*;<>?[\\]`{|}~\n"

        def has_meta(s1, s2=metachars):
            """Check if any char of s1 is in s2"""
            for c in s1:
                if c in s2:
                    return True
            return False

        # Sympa list creation command will be passed through multiple
        # exec/shells. Better be restrictive.
        if True in [has_meta(x) for x in
                    (run_host, delivery_host, listname, admins, list_profile,
                     list_description)]:
            raise CerebrumError(
                "Illegal metacharacter in list parameter. Allowed: '%s'" %
                metachars)

        delivery_host = self._get_server_from_ident(delivery_host)
        force = self._get_boolean(yes_no_force)
        self._create_sympa_list(operator, listname, delivery_host, force=force)
        # Now make a bofhd request to create the list itself
        admin_list = list()
        for item in admins.split(","):
            # it's a user name. That username must exist in Cerebrum
            if "@" not in item:
                self._get_account(item)
                # TODO: Not good, this is in use by UIA
                item = item + "@ulrik.uio.no"
            admin_list.append(item)

        # Make the request.
        lp, dom = self._split_email_address(listname)
        ed = self._get_email_domain_from_str(dom)
        ea = Email.EmailAddress(self.db)
        ea.clear()
        ea.find_by_local_part_and_domain(lp, ed.entity_id)
        list_id = ea.entity_id
        # IVR 2008-08-01 TBD: this is a big ugly. We need to pass several
        # arguments to p_b_r, but we cannot really store them anywhere :( The
        # idea is then to take a small dict, pickle it, shove into state_data,
        # unpickle in p_b_r and be on our merry way. It is at the very best
        # suboptimal.
        state = {"runhost": run_host,  # IVR 2008-08-01 FIXME: non-fqdn? force?
                                       # check?
                 "admins": admin_list,
                 "profile": list_profile,
                 "description": list_description, }
        br = BofhdRequests(self.db, self.const)

        # IVR 2009-04-17 +30 minute delay to allow changes to spread to
        # LDAP. The postmasters are nagging for that delay. All questions
        # should be directed to them (this is similar to delaying a delete
        # request).
        br.add_request(operator.get_entity_id(),
                       DateTime.now() + DateTime.DateTimeDelta(0, 0, 30),
                       self.const.bofh_sympa_create, list_id, ea.entity_id,
                       state_data=pickle.dumps(state))
        return {'listname': listname}

    #
    # sympa remove_list <run-host> <list-address>
    #
    all_commands['sympa_remove_list'] = Command(
        ("sympa", "remove_list"),
        SimpleString(help_ref='string_exec_host'),
        EmailAddress(help_ref="mailing_list_exist"),
        YesNo(help_ref="yes_no_with_request"),
        fs=FormatSuggestion([("Sympa list '%s' deleted (bofhd request: %s)",
                              ('listname', 'request', ))]),
        perm_filter="can_email_list_delete")

    def sympa_remove_list(self, operator, run_host, listname, force_yes_no):
        """ Remove a sympa list from cerebrum.

        @type force_request: bool
        @param force_request:
          Controls whether a bofhd request should be issued. This may come in
          handy, if we want to delete a sympa list from Cerebrum only and not
          issue any requests. misc cancel_request would have worked too, but
          it's better to merge this into one command.

        """
        force_request = self._get_boolean(force_yes_no)

        # Check that the command exec host is sane
        if run_host not in cereconf.SYMPA_RUN_HOSTS:
            raise CerebrumError("run-host '%s' for list '%s' is not valid" %
                                (run_host, listname))

        et, ea = self._get_email_target_and_address(listname)
        self.ba.can_email_list_delete(operator.get_entity_id(), ea)

        if et.email_target_type != self.const.email_target_Sympa:
            raise CerebrumError("'%s' is not a sympa list (type: %s)" % (
                listname, self.const.EmailTarget(et.email_target_type)))

        epat = Email.EmailPrimaryAddressTarget(self.db)
        list_id = ea.entity_id
        # Now, there are *many* ETs/EAs associated with one sympa list. We
        # have to wipe them all out.
        if not self._validate_sympa_list(listname):
            raise CerebrumError("Illegal sympa list name: '%s'", listname)

        # needed for pattern interpolation below (these are actually used)
        local_part, domain = self._split_email_address(listname)
        for pattern, pipe_destination in _sympa_addr2alias:
            address = pattern % locals()
            # For each address, find the target, and remove all email
            # addresses for that target (there may be many addresses for the
            # same target).
            try:
                ea.clear()
                ea.find_by_address(address)
                et.clear()
                et.find(ea.get_target_id())
                epat.clear()
                try:
                    epat.find(et.entity_id)
                except Errors.NotFoundError:
                    pass
                else:
                    epat.delete()
                # Wipe all addresses...
                for row in et.get_addresses():
                    addr = '%(local_part)s@%(domain)s' % row
                    ea.clear()
                    ea.find_by_address(addr)
                    ea.delete()
                et.delete()
            except Errors.NotFoundError:
                pass

        if not force_request:
            return {'listname': listname, 'request': False}

        br = BofhdRequests(self.db, self.const)
        state = {'run_host': run_host,
                 'listname': listname}
        br.add_request(operator.get_entity_id(),
                       # IVR 2008-08-04 +1 hour to allow changes to spread to
                       # LDAP. This way we'll have a nice SMTP-error, rather
                       # than a confusing error burp from sympa.
                       DateTime.now() + DateTime.DateTimeDelta(0, 1),
                       self.const.bofh_sympa_remove,
                       list_id, None, state_data=pickle.dumps(state))

        return {'listname': listname, 'request': True}

    #
    # sympa create_list_alias <list-address> <new-alias>
    #
    all_commands['sympa_create_list_alias'] = Command(
        ("sympa", "create_list_alias"),
        EmailAddress(help_ref="mailing_list_exist"),
        EmailAddress(help_ref="mailing_list"),
        YesNo(help_ref="yes_no_force", optional=True),
        fs=FormatSuggestion([("List alias '%s' created", ('alias', ))]),
        perm_filter="can_email_list_create")

    def sympa_create_list_alias(self, operator, listname, address,
                                yes_no_force='No'):
        """ Create a secondary name for an existing Sympa list. """
        force = self._get_boolean(yes_no_force)
        # The first thing we have to do is to locate the delivery
        # host. Postmasters do NOT want to allow people to specify a different
        # delivery host for alias than for the list that is being aliased. So,
        # find the ml's ET and fish out the server_id.
        self._validate_sympa_list(listname)
        local_part, domain = self._split_email_address(listname)
        ed = self._get_email_domain_from_str(domain)
        email_address = Email.EmailAddress(self.db)
        email_address.find_by_local_part_and_domain(local_part,
                                                    ed.entity_id)
        try:
            delivery_host = self._get_server_from_address(email_address)
        except CerebrumError:
            raise CerebrumError("Cannot alias list %s (missing delivery host)",
                                listname)

        # TODO: Look at perms (are now done by _register)
        self._create_sympa_list_alias(operator, listname, address,
                                      delivery_host, force_alias=force)
        return {'target': listname, 'alias': address, }

    #
    # sympa remove_list_alias <alias>
    #
    all_commands['sympa_remove_list_alias'] = Command(
        ('sympa', 'remove_list_alias'),
        EmailAddress(help_ref='mailing_list_alias'),
        fs=FormatSuggestion([("List alias '%s' removed", ('alias', ))]),
        perm_filter='can_email_list_create')

    def sympa_remove_list_alias(self, operator, alias):
        """ Remove Sympa list aliases. """
        lp, dom = self._split_email_address(alias, with_checks=False)
        ed = self._get_email_domain_from_str(dom)
        self.ba.can_email_list_create(operator.get_entity_id(), ed)

        ea = Email.EmailAddress(self.db)
        et = Email.EmailTarget(self.db)

        for addr_format, pipe in _sympa_addr2alias:
            addr = addr_format % {"local_part": lp,
                                  "domain": dom, }
            try:
                ea.clear()
                ea.find_by_address(addr)
            except Errors.NotFoundError:
                # Even if one of the addresses is missing, it does not matter
                # -- we are removing the alias anyway. The right thing to do
                # here is to continue, as if deletion worked fine. Note that
                # the ET belongs to the original address, not the alias, so if
                # we don't delete it when the *alias* is removed, we should
                # still be fine.
                continue

            try:
                et.clear()
                et.find(ea.email_addr_target_id)
            except Errors.NotFoundError:
                raise CerebrumError("Could not find e-mail target for %s" %
                                    addr)

            # nuke the address, and, if it's the last one, nuke the target as
            # well.
            self._remove_email_address(et, addr)
        return {'alias': alias}

    #
    # sympa create_list_in_cerebrum
    #
    all_commands['sympa_create_list_in_cerebrum'] = Command(
        ("sympa", "create_list_in_cerebrum"),
        SimpleString(help_ref='string_email_delivery_host'),
        EmailAddress(help_ref="mailing_list"),
        YesNo(help_ref="yes_no_force", optional=True, default="No"),
        fs=FormatSuggestion([("Sympa list '%s' created (only in Cerebrum)",
                              ('listname', ))]),
        perm_filter="can_email_list_create")

    def sympa_create_list_in_cerebrum(self, operator, delivery_host, listname,
                                      yes_no_force=None):
        """ Create a sympa mailing list in cerebrum only. """

        delivery_host = self._get_server_from_ident(delivery_host)
        force = self._get_boolean(yes_no_force)
        self._create_sympa_list(operator, listname, delivery_host, force=force)
        return {'listname': listname}


class LdapUpdater(object):
    """ Simple ldap update utility.

    This simple ldap module wrapper enables the command `email pause` to modify
    LDAP objects directly
    """

    @property
    def ldap(self):
        """ delayed import of the ldap module. """
        try:
            import ldap as _ldap_module
        except ImportError:
            raise AttributeError('ldap module not available')
        return _ldap_module

    @property
    def connection(self):
        """ cached connection object. """
        getattr(self, '_connection', None)

    @connection.setter
    def connection(self, connection):
        setattr(self, '_connection', connection)

    @connection.deleter
    def connection(self):
        if hasattr(self, '_connection'):
            delattr(self, '_connection')

    def connect(self, server, bind_dn, password, retry_max, retry_delay):
        """ Connect to an ldap server and bind. """
        # Avoid indefinite blocking
        self.ldap.set_option(self.ldap.OPT_NETWORK_TIMEOUT, 4)

        # Require TLS cert. This option should be set in
        # /etc/openldap/ldap.conf along with the cert itself,
        # but let us make sure.
        self.ldap.set_option(self.ldap.OPT_X_TLS_REQUIRE_CERT,
                             self.ldap.OPT_X_TLS_DEMAND)

        con = self.ldap.ldapobject.ReconnectLDAPObject("ldaps://%s/" % server,
                                                       retry_max=retry_max,
                                                       retry_delay=retry_delay)

        try:
            con.simple_bind_s(who=bind_dn, cred=password)
        except self.ldap.CONFIDENTIALITY_REQUIRED:
            err_fmt = 'TLS could not be established to %r'
            self.logger.warn(err_fmt, server)
            raise CerebrumError(err_fmt % server)
        except self.ldap.INVALID_CREDENTIALS:
            err_fmt = 'Connection aborted to %r, invalid credentials'
            self.logger.error(err_fmt, server)
            raise CerebrumError(err_fmt % server)
        except self.ldap.SERVER_DOWN:
            con = None

        # And we store the connection
        self.connection = con

    def __del__(self):
        # try to unbind when object goes out of scope
        self.unbind()

    def modify(self, dn, attribute, *values):
        if not self.connection:
            return False

        # We'll set the trait on one server, and it should spread
        # to the other servers in less than two miuntes.  This
        # eliminates race conditions when servers go up and down..
        try:
            self.connection.modify_s(
                dn,
                [(self.ldap.MOD_REPLACE, attribute, values or None)])
            return True

        except self.ldap.NO_SUCH_OBJECT:
            # This error occurs if the mail-target has been created
            # and mailPause is being set before the newest LDIF has
            # been handed over to LDAP.
            pass
        except self.ldap.SERVER_DOWN:
            # We invalidate the connection (set it to None).
            del self.connection

        return False

    def unbind(self):
        if self.connection is not None:
            try:
                self.connection.unbind_s()
            except self.ldap.LDAPError:
                pass
            del self.connection


#
# email help_strings
#

HELP_EMAIL_GROUP = {
    'email': "E-mail commands",
}

HELP_EMAIL_CMDS = {
    'email': {
        "email_add_address":
            "Add an alias address",
        "email_remove_address":
            "Remove an alias address",
        "email_add_filter":
            "Add a target filter",
        "email_remove_filter":
            "Remove target_filter",
        "email_reassign_address":
            "Move an address from one account to another",
        "email_update":
            "Update default address and aliases associated with account",
        "email_create_domain":
            "Create a new e-mail domain",
        "email_delete_domain":
            "Delete an e-mail domain",
        "email_create_forward_target":
            "Create a new e-mail forward target",
        "email_domain_info":
            "View information about an e-mail domain",
        "email_add_domain_affiliation":
            "Connect a OU to an e-mail domain",
        "email_remove_domain_affiliation":
            "Remove link between OU and e-mail domain",
        "email_domain_configuration":
            "Configure settings for an e-mail domain",
        "email_domain_set_description":
            "Set the description of an e-mail domain",
        "email_failure_message":
            "Customise the failure message for a deleted account",
        "email_forward":
            "Turn e-mail forwarding for a user on/off",
        "email_add_forward":
            "Add a forward address",
        "email_remove_forward":
            "Remove a forward address",
        "email_local_delivery":
            "Turn on/off local e-mail delivery for an account with a forward "
            "address",
        "email_info":
            "View e-mail information about a user or address",
        "email_create_multi":
            "Make an e-mail target which expands to the members of a group",
        "email_create_pipe":
            "Make an e-mail target which points to a pipe",
        "email_delete_pipe":
            "Delete an e-mail target that points to a pipe",
        "email_delete_sympa_list":
            "Remove a Sympa list's addresses",
        "email_delete_multi":
            "Remove a multi target and all its addresses",
        "email_delete_forward_target":
            "Delete an e-mail forward target",
        "email_edit_pipe_command":
            "Change the command the pipe or RT target runs",
        "email_edit_pipe_user":
            "Change the account the pipe or RT target runs as",
        "email_mod_name":
            "Override name for person (to be used in e-mail address)",
        "email_primary_address":
            "Changes the primary address for the e-mail target to the "
            "specified value",
        "email_set_primary_address":
            "Changes the primary address for the e-mail target to the "
            "specified value",
        "email_quota":
            "Change a user's storage quota for e-mail",
        "email_spam_action":
            "How to handle target's spam",
        "email_spam_level":
            "Change target's tolerance for spam",
        "email_tripnote":
            "Turn vacation messages on/off",
        "email_add_tripnote":
            "Add vacation message",
        "email_list_tripnotes":
            "List user's vacation messages",
        "email_remove_tripnote":
            "Remove vacation message",
        "email_pause":
            "Turn delivery pause on or off",
        "email_list_pause":
            "List all mailtargets with paused delivery",
    },
}

HELP_EMAIL_ARGS = {
    'email_address':
        ['address', 'Enter email',
         'Specify a valid email address'],
    'email_category':
        ['category', 'Enter email category',
         "An email categody for the domain. Legal categories include:\n"
         " - noexport     don't include domain in data exports\n"
         " - cnaddr       primary address is firstname.lastname\n"
         " - uidaddr      primary address is username\n"
         " - all_uids     all usernames are valid e-mail addresses\n"
         " - UIO_GLOBALS  direct Postmaster etc. to USIT", ],
    'email_failure_message':
        ['message', 'Enter failure message'],
    'email_forward_address':
        ['forward_to_address', 'Enter forward address',
         'A valid email address to forward to'],
    'email_forward_action':
        ['action', 'Enter forward action',
         "Legal forward actions:\n - on\n - off\n - local"],
    'email_tripnote_action':
        ['action', 'Enter tripnote action',
         "Legal tripnote actions:\n - on\n - off"],
    'spam_action':
        ['spam action', 'Enter spam action',
         "Choose one of\n"
         " 'dropspam'    Reject messages classified as spam\n"
         " 'spamfolder'  Deliver spam to a separate IMAP folder\n"
         " 'noaction'    Deliver spam just like legitimate email"],
    'spam_level':
        ['spam level', 'Enter spam level',
         "Choose one of\n"
         " 'aggressive_spam' Filter everything that resembles spam\n"
         " 'most_spam'       Filter most emails that looks like spam\n"
         " 'standard_spam'   Only filter email that obviously is spam\n"
         " 'no_filter'       No email will be filtered as spam"],
    'string_email_filter':
        ['email_filter', 'Enter e-mail filter type',
         "Legal filter types:\n- greylist\n- uioonly"],
    'string_email_on_off':
        ['email_on_off', 'ON/OFF',
         "Specify ON or OFF", ],
    'string_email_target_name':
        ['email_target_name', 'Enter e-mail target name',
         "Target name should be a valid e-mail address"],
}

HELP_RT_GROUP = {
    'rt': 'Request Tracker email commands',
}

HELP_RT_CMDS = {
    'rt': {
        "rt_add_address":
            "Add a valid address for RT queue",
        "rt_create":
            "Create an e-mail target for Request Tracker",
        "rt_delete":
            "Delete Request Tracker addresses",
        "rt_set_primary_address":
            "Change which address to rewrite to",
        "rt_remove_address":
            "Remove a valid address from the RT target",
    }
}

HELP_RT_ARGS = {
    'rt_queue':
        ['queue[@host]', 'Enter name of RT queue',
         "Format is <queue>@<host>. If <host> is the default host,"
         " it can be omitted."],
}

HELP_SYMPA_GROUP = {
    'sympa': "Sympa maillist commands",
}

HELP_SYMPA_CMDS = {
    'sympa': {
        'sympa_create_list':
            "Add addresses needed for a Sympa list",
        'sympa_remove_list':
            "Remove a sympa list from Cerebrum",
        'sympa_create_list_alias':
            "Add an alias for a Sympa list.  This also adds additional "
            "addresses (e.g. -owner, -request, etc.)",
        'sympa_remove_list_alias':
            "Remove an alias for a Sympa list. This also removes additional "
            "administrative addresses (-owner, -request, etc.)",
        'sympa_create_list_in_cerebrum':
            "Add addresses needed for a Sympa list (Cerebrum only)",
    },
}

HELP_SYMPA_ARGS = {
    'string_exec_host':
        ['run_host', 'Enter hostname',
         'Hostname (fqdn) of the host where cmmands are executed'],
    'string_email_delivery_host':
        ['delivery_host', 'Enter hostname',
         'Hostname for email delivery. Example: lister-test'],
    'mailing_admins':
        ['addresses', 'Enter admins (comma-separated)',
         'A comma separated list of administrators for the mailing list'],
    'mailing_list':
        ['address', 'Enter address',
         'Address for a mailing list'],
    'mailing_list_alias':
        ['address', 'Enter alias',
         'Alias for a mailing list'],
    'mailing_list_exist':
        ['address', 'Enter address',
         'Address of an existing mailing list'],
    'mailing_list_profile':
        ['list_profile', 'Enter profile',
         'A mailing list profile'],
    'mailing_list_description':
        ['list_description', 'Enter description',
         'Description of mailing list'],
}
