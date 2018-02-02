# -*- coding: utf-8 -*-

# Copyright 2014 University of Oslo, Norway
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
""" Email mixin and utils for BofhdExtensions.

This module contains the neccessary email functionality from UiO that other
instances copies.

Please don't blame me for the WTF-ness in this file. It's mostly from
bofhd_uio_cmds, rev 17863...  - fhl

"""
import cereconf
import cerebrum_path

import re
from mx import DateTime
from flanker.addresslib import address as email_validator

from Cerebrum.modules import Email
from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum.utils.email import sendmail, mail_template

from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase, BofhdCommonMethods
from Cerebrum.modules.bofhd.bofhd_utils import copy_func
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.cmd_param import Command, FormatSuggestion, \
    AccountName, EmailAddress, PersonId, PersonName, SimpleString, OU, \
    Affiliation, GroupName, Date, Integer


# TODO: Do we need this?
def format_day(field):
    """ Format day, for FormatSuggestion. """
    fmt = "yyyy-MM-dd"  # 10 characters wide
    return ":".join((field, "date", fmt))


class BofhdEmailMixinBase(BofhdCommandBase):

    """ This is the common base for BofhdEmailMixins.

    It serves as a common superclass, and contains shared util functions.

    """

    # TODO: We ned to purge UIO-specific functions from this file.

    #
    # Email{Target,Address,Domain} related helper functions.
    #
    def _get_email_domain_from_str(self, domain_str):
        """ Get EmailDomain from str. """
        ed = Email.EmailDomain(self.db)
        try:
            ed.find_by_domain(domain_str)
        except Errors.NotFoundError:
            raise CerebrumError("Unknown e-mail domain (%s)" % domain_str)
        return ed

    def _get_server_from_address(self, address):
        """ Get EmailServer from address (EmailAddress or str) """
        et = self._get_email_target_for_address(address)
        try:
            host = Email.EmailServer(self.db)
            host.find(et.email_server_id)
        except Errors.NotFoundError:
            raise CerebrumError("Uknown email server (id:%s)" %
                                str(et.email_server_id))
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
        """ Get a tuple of (EmailTarget, Account) from a username or email-address. """
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

    def _check_email_address(self, address):
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


class BofhdEmailMixin(BofhdEmailMixinBase):

    """ This is a mixin for email commands.

    It should supply the common denominator for all email commands at all
    institutions. This way, we won't have to 'copy' email commands to
    BofhdExtensions.

    To use a email command in a BofhdExtension:

        class BofhdExtension(BofhdCommonBase, BofhdEmailMixin):
            all_commands['email_info'] = default_email_commands['email_info']

    To extend or replace an email-command:

        class BofhdExtension(BofhdCommonBase, BofhdEmailMixin):
            all_commands['email_info'] = default_email_commands['email_info']
            def email_info(...):
                # If we are extending:
                # info = super(BofhdExtension, self).email_info()
                # info['foo'] = 'bar'
                # return info

            # OR
            all_commands['email_info'] = Command()
            def email_info(...):
                # If we are extending:
                # info = super(BofhdExtension, self).email_info()
                # info['foo'] = 'bar'
                # return info

    """

    default_email_commands = {}

    # INPUT HELPERS

    def _parse_date_from_to(self, date):
        """ Parse date range string. """
        date_start = self._today()
        date_end = None
        if date:
            tmp = date.split("--")
            if len(tmp) == 2:
                if tmp[0]:  # string could start with '--'
                    date_start = self._parse_date(tmp[0])
                date_end = self._parse_date(tmp[1])
            elif len(tmp) == 1:
                date_end = self._parse_date(date)
            else:
                raise CerebrumError("Incorrect date specification: %s." % date)
        return (date_start, date_end)

    # COMMANDS

    #
    # email add_address <address or account> <address>+
    #
    default_email_commands['email_add_address'] = Command(
        ('email', 'add_address'),
        AccountName(help_ref='account_name'),
        EmailAddress(help_ref='email_address', repeat=True),
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
        # TODO: Should return dict. Use FormatSuggestion for bofh...
        return "OK, added '%s' as email-address for '%s'" % (address, uname)

    #
    # email remove_address <account> <address>+
    #
    default_email_commands['email_remove_address'] = Command(
        ('email', 'remove_address'),
        AccountName(), EmailAddress(repeat=True),
        perm_filter='can_email_address_delete')

    def email_remove_address(self, operator, uname, address):
        """ Remove an email address from an account. """

        # uname can be an address
        et, acc = self._get_email_target_and_account(uname)
        local, domain = self._split_email_address(address, with_checks=False)
        ed = self._get_email_domain_from_str(domain)

        self.ba.can_email_address_delete(operator.get_entity_id(),
                                         account=acc, domain=ed)
        # TODO: Should return dict. Use FormatSuggestion for bofh...
        if self._remove_email_address(et, address):
            return "OK, removed '%s', and email target" % address
        return "OK, removed '%s'" % address

    #
    # email reassign_address <address> <destination>
    #
    default_email_commands['email_reassign_address'] = Command(
        ('email', 'reassign_address'),
        EmailAddress(help_ref='email_address'),
        AccountName(help_ref='account_name'),
        perm_filter='can_email_address_reassign')

    def email_reassign_address(self, operator, address, dest):
        """ Reassign address to a user account. """

        source_et, source_acc = self._get_email_target_and_account(address)
        ttype = source_et.email_target_type

        if ttype not in (self.const.email_target_account,
                         self.const.email_target_deleted):
            raise CerebrumError(
                "Can't reassign e-mail address from target type %s" %
                self.const.EmailTarget(ttype))

        dest_acc = self._get_account(dest, idtype='name')
        if dest_acc.is_deleted():
            raise CerebrumError(
                "Can't reassign e-mail address to deleted account %s" % dest)
        dest_et = Email.EmailTarget(self.db)
        try:
            dest_et.find_by_target_entity(dest_acc.entity_id)
        except Errors.NotFoundError:
            raise CerebrumError("Account %s has no e-mail target" % dest)
        if dest_et.email_target_type != self.const.email_target_account:
            raise CerebrumError(
                "Can't reassign e-mail address to target type %s" %
                self.const.EmailTarget(ttype))
        if source_et.entity_id == dest_et.entity_id:
            # TODO: Should return dict. Use FormatSuggestion for bofh...
            return "%s is already connected to %s" % (address, dest)
        if (source_acc.owner_type != dest_acc.owner_type or
                source_acc.owner_id != dest_acc.owner_id):
            raise CerebrumError(
                "Can't reassign e-mail address to a different person.")

        self.ba.can_email_address_reassign(operator.get_entity_id(),
                                           dest_acc)

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

        if (len(source_et.get_addresses()) == 0 and
                ttype == self.const.email_target_deleted):
            source_et.delete()
            # TODO: Should return dict. Use FormatSuggestion for bofh...
            return ("OK, reassigned %s and deleted source e-mail target" %
                    address)

        source_acc.update_email_addresses()
        # TODO: Should return dict. Use FormatSuggestion for bofh...
        return "OK, reassigned %s" % address

    #
    # email local_delivery <account> "on"/"off"
    #
    default_email_commands['email_local_delivery'] = Command(
        ('email', 'local_delivery'),
        AccountName(help_ref='account_name'),
        SimpleString(help_ref='string_email_on_off'),
        perm_filter='can_email_forward_toggle')

    def email_local_delivery(self, operator, uname, on_off):
        """Turn on or off local delivery of E-mail."""
        acc = self._get_account(uname)
        self.ba.can_email_forward_toggle(operator.get_entity_id(), acc)
        fw = Email.EmailForward(self.db)
        fw.find_by_target_entity(acc.entity_id)
        on_off = on_off.lower()
        if on_off == 'on':
            fw.enable_local_delivery()
        elif on_off == 'off':
            fw.disable_local_delivery()
        else:
            raise CerebrumError("Must specify 'on' or 'off'")
        return "OK, local delivery turned %s" % on_off

    #
    # email forward <account> <address> "on"/"off"
    #
    default_email_commands['email_forward'] = Command(
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
    # account can also be an e-mail address for pure forwardtargets
    #
    default_email_commands['email_add_forward'] = Command(
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
            self.ba.can_email_forward_edit(operator.get_entity_id(), acc)
        fw = Email.EmailForward(self.db)
        fw.find(et.entity_id)
        if address == 'local':
            fw.enable_local_delivery()
            return 'OK, local delivery turned on'
        addr = self._check_email_address(address)

        if self._forward_exists(fw, addr):
            raise CerebrumError("Forward address added already (%s)" % addr)

        fw.add_forward(addr)
        return "OK, added '%s' as forward-address for '%s'" % (address, uname)

    #
    # email delete_forward address
    #
    default_email_commands['email_delete_forward'] = Command(
        ("email", "delete_forward"),
        EmailAddress(help_ref='email_address'),
        fs=FormatSuggestion([("Deleted forward address: %s", ("address", ))]),
        perm_filter='can_email_forward_create')

    def email_delete_forward(self, operator, address):
        """Delete a forward target with associated aliases. Requires primary
        address."""

        # Allow us to delete an address, even if it is malformed.
        lp, dom = self._split_email_address(address, with_checks=False)
        ed = self._get_email_domain(dom)
        et, acc = self._get_email_target_and_account(address)
        self.ba.can_email_forward_edit(operator.get_entity_id(), domain=ed)
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
    # account can also be an e-mail address for pure forwardtargets
    #
    default_email_commands['email_remove_forward'] = Command(
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
            self.ba.can_email_forward_edit(operator.get_entity_id(), acc)
        fw = Email.EmailForward(self.db)
        fw.find(et.entity_id)
        if address == 'local':
            fw.disable_local_delivery()
            return 'OK, local delivery turned off'
        addr = self._check_email_address(address)
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
    default_email_commands['email_info'] = Command(
        ("email", "info"),
        AccountName(help_ref="account_name", repeat=True),
        perm_filter='can_email_info',
        fs=FormatSuggestion([
            ("Target ID:        %d\n"
             "Target Type:      %s", ("target_id", "target_type", )),
            #
            # target_type == Account
            #
            ("Account:          %s", ("account",)),
            ("Mail server:      %s (%s)", ("server", "server_type")),
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
            # target_type == multi
            ("Forward to group: %s", ("multi_forward_gr",)),
            ("Expands to:       %s", ("multi_forward_1",)),
            ("                  %s", ("multi_forward",)),
            # target_type == file
            ("File:             %s\n" +
             "Save as:          %s", ("file_name", "file_runas")),
            # target_type == pipe
            ("Command:          %s\n" +
             "Run as:           %s", ("pipe_cmd", "pipe_runas")),
            # target_type == RT
            ("RT queue:         %s on %s\n" +
             "Action:           %s\n" +
             "Run as:           %s", ("rt_queue", "rt_host",
                                      "rt_action", "pipe_runas")),
            # target_type == forward
            ("Address:          %s", ("fw_target",)),
            ("Forwarding:       %s (%s)", ("fw_addr_1", "fw_enable_1")),
            ("                  %s (%s)", ("fw_addr", "fw_enable")),
            #
            # both account and Sympa
            #
            ("Spam level:       %s (%s)\n" +
             "Spam action:      %s (%s)", ("spam_level", "spam_level_desc",
                                           "spam_action", "spam_action_desc")),
            ("Filters:          %s", ("filters",)),
            ("Status:           %s", ("status",)),
        ]))

    def email_info(self, operator, uname):
        try:
            et, acc = self._get_email_target_and_account(uname)
        except CerebrumError, e:
            try:
                # Accounts with email address stored in contact_info
                ac = self._get_account(uname, idtype='name')
                return self._email_info_contact_info(operator, ac)
            except CerebrumError:
                pass
            raise e

        ttype = et.email_target_type
        ttype_name = str(self.const.EmailTarget(ttype))

        ret = [
            {'target_type': ttype_name,
             'target_id': et.entity_id, },
        ]

        # Default address
        try:
            ret.append({'def_addr': self._get_address(et), })
        except Errors.NotFoundError:
            if ttype == self.const.email_target_account:
                ret.append({'def_addr': "<none>"})
            # No else?

        if ttype != self.const.email_target_Sympa:
            # We want to split the valid addresses into multiple
            # parts for MLs, so there is special code for that.
            addrs = self._get_valid_email_addrs(et, special=True, sort=True)
            if not addrs:
                addrs = ["<none>"]
            ret.append({'valid_addr_1': addrs[0]})
            for addr in addrs[1:]:
                ret.append({"valid_addr": addr})

        # TODO: The sympa email_info belongs in
        #       bofhd_email_list.py
        if (ttype == self.const.email_target_Sympa and
                hasattr(self, '_email_info_sympa')):
            # TODO: What if the constant doesn't exist?
            ret += getattr(self, '_email_info_sympa')(operator, et, uname)
        elif ttype == self.const.email_target_multi:
            ret += self._email_info_multi(et, uname)
        elif ttype == self.const.email_target_file:
            ret += self._email_info_file(et, uname)
        elif ttype == self.const.email_target_pipe:
            ret += self._email_info_pipe(et, uname)
        elif ttype == self.const.email_target_RT:
            # TODO: What if the constant doesn't exist?
            ret += self._email_info_rt(et, uname)
        elif ttype == self.const.email_target_forward:
            ret += self._email_info_forward(et, uname)
        elif (ttype == self.const.email_target_account or
              ttype == self.const.email_target_deleted):
            ret += self._email_info_account(operator, acc, et, addrs)
        else:
            raise CerebrumError(
                "'email info' for target type '%s' isn't implemented" %
                ttype_name)

        # Only the account owner and postmaster can see account settings, and
        # that is handled properly in _email_info_account.
        if ttype not in (self.const.email_target_account,
                         self.const.email_target_deleted):
            ret += self._email_info_spam(et)
            ret += self._email_info_filters(et)
            ret += self._email_info_forwarding(et, uname)

        # TODO: This ret-value is UGLY.
        return ret

    def _email_info_contact_info(self, operator, acc):
        """ info for accounts with email stored in contact info. """
        addresses = acc.get_contact_info(type=self.const.contact_email)
        if not addresses:
            raise CerebrumError("No contact info for '%s'" % acc.account_name)
        ret = [{'target_type': 'entity_contact_info', }, ]
        ret.append({'valid_addr_1': addresses[0]['contact_value']})
        for addr in addresses[1:]:
            ret.append({"valid_addr": addr['contact_value']})
        return ret

    def _email_info_account(self, operator, acc, et, addrs):
        """ Partial email_info, account data. """
        # TODO: WTF?!
        self.ba.can_email_info(operator.get_entity_id(), acc)
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

    def _email_info_basic(self, acc, et):
        info = {}
        data = [info, ]
        if (et.email_target_alias is not None and
            et.email_target_type != self.const.email_target_Sympa):
            info['alias_value'] = et.email_target_alias
        info["account"] = acc.account_name
        if et.email_server_id:
            es = Email.EmailServer(self.db)
            es.find(et.email_server_id)
            info["server"] = es.name
            type = int(es.email_server_type)
            info["server_type"] = str(self.const.EmailServerType(type))
        else:
            info["server"] = "<none>"
            info["server_type"] = "N/A"
        return data

    def _email_info_spam(self, target):
        """ Get spam settings for an EmailTarget. """
        info = []
        spam = Email.EmailSpamFilter(self.db)
        try:
            spam.find(target.entity_id)
            spam_lev = self.const.EmailSpamLevel(spam.email_spam_level)
            spam_act = self.const.EmailSpamAction(spam.email_spam_action)
            info.append({'spam_level':       str(spam_lev),
                         'spam_level_desc':  spam_lev.description,
                         'spam_action':      str(spam_act),
                         'spam_action_desc': spam_act.description})
        except Errors.NotFoundError:
            pass
        return info

    def _email_info_filters(self, target):
        """ Get filter settings for EmailTarget. """
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

    def _email_info_detail(self, acc):
        """ Get email account details.

        This method should be implemented differently for each subclass.
        Typical information would be quotas, usage, pause state, ...

        """
        raise CerebrumError("email_info_detail not implemented")
        return []

    def _email_info_forwarding(self, target, addrs):
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
            ret.append({'multi_forward_gr': 'ENTITY TYPE OF %d UNKNOWN' %
                        et.email_target_entity_id})
        else:
            group = self.Group_class(self.db)
            acc = self.Account_class(self.db)
            try:
                group.find(et.email_target_entity_id)
            except Errors.NotFoundError:
                ret.append({'multi_forward_gr': 'Unknown group %d' %
                            et.email_target_entity_id})
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
        return [{'file_name': et.get_alias(),
                 'file_runas': account_name}]

    def _email_info_pipe(self, et, addr):
        """ Partial email_info for EmailTarget of type 'pipe'. """
        acc = self._get_account(et.email_target_using_uid, idtype='id')
        return [{'pipe_cmd': et.get_alias(), 'pipe_runas': acc.account_name}]

    def _email_info_rt(self, et, addr):
        """ Partial email_info for EmailTarget of type 'RT'. """
        m = re.match(self._rt_patt, et.get_alias())
        acc = self._get_account(et.email_target_using_uid, idtype='id')
        return [{'rt_action': m.group(1),
                 'rt_queue': m.group(2),
                 'rt_host': m.group(3),
                 'pipe_runas':  acc.account_name}]

    def _email_info_forward(self, et, addr):
        """ Partial email_info for EmailTarget of type 'forward'. """
        data = []
        # et.email_target_alias isn't used for anything, it's often
        # a copy of one of the forward addresses, but that's just a
        # waste of bytes, really.
        ef = Email.EmailForward(self.db)
        try:
            ef.find(et.entity_id)
        except Errors.NotFoundError:
            data.append({'fw_addr_1': '<none>', 'fw_enable': 'off'})
        else:
            forw = ef.get_forward()
            if forw:
                data.append({'fw_addr_1': forw[0]['forward_to'],
                             'fw_enable_1': self._onoff(forw[0]['enable'])})
            for idx in range(1, len(forw)):
                data.append({'fw_addr': forw[idx]['forward_to'],
                             'fw_enable': self._onoff(forw[idx]['enable'])})
        return data

    def _is_email_delivery_stopped(self, ldap_target):
        """ Test if email delivery is turned off in LDAP for a user. """
        import ldap
        import ldap.filter
        import ldap.ldapobject
        ldapconns = [ldap.ldapobject.ReconnectLDAPObject("ldap://%s/" % server)
                     for server in cereconf.LDAP_SERVERS]
        target_filter = ("(&(target=%s)(mailPause=TRUE))" %
                         ldap.filter.escape_filter_chars(ldap_target))
        for conn in ldapconns:
            try:
                # FIXME: cereconf.LDAP_MAIL['dn'] has a bogus value, so we
                # must hardcode the DN.
                res = conn.search_s("cn=targets,cn=mail,dc=uio,dc=no",
                                    ldap.SCOPE_ONELEVEL, target_filter,
                                    ["1.1"])
                if len(res) != 1:
                    return False
            except ldap.LDAPError, e:
                self.logger.error("LDAP search failed: %s", e)
                return False
        return True


    #
    # email modify_name
    #
    default_email_commands['email_mod_name'] = Command(
        ("email", "mod_name"),
        PersonId(help_ref="person_id_other"),
        PersonName(help_ref="person_name_first"),
        PersonName(help_ref="person_name_last"),
        fs=FormatSuggestion(
            "Name and e-mail address altered for: %i",
            ("person_id",)),
        perm_filter='is_postmaster')

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
            raise CerebrumError("Last name is required")
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
        except self.db.DatabaseError, m:
            raise CerebrumError("Database error: %s" % m)
        return {'person_id': person.entity_id}

    #
    # email primary_address <address>
    #
    default_email_commands['email_primary_address'] = Command(
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

        # TODO: Fix FormatString and return value
        if self._set_email_primary_address(et, ea):
            return {'address': addr}
        return "No change, primary address was %s" % addr

    #
    # email set_primary_address account lp@dom
    #
    default_email_commands['email_set_primary_address'] = Command(
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
    default_email_commands['email_create_pipe'] = Command(
        ("email", "create_pipe"),
        EmailAddress(help_ref="email_address"),
        AccountName(),
        SimpleString(help_ref="command_line"),
        perm_filter="can_email_pipe_create")

    def email_create_pipe(self, operator, addr, uname, cmd):
        """ Create email pipe. """
        lp, dom = self._split_email_address(addr)
        ed = self._get_email_domain_from_str(dom)
        self.ba.can_email_pipe_create(operator.get_entity_id(), ed)
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
        self._register_spam_settings(addr, self.const.email_target_pipe)
        self._register_filter_settings(addr, self.const.email_target_pipe)
        return "OK, created pipe address %s" % addr

    #
    # email delete_pipe <address>
    #
    default_email_commands['email_delete_pipe'] = Command(
        ("email", "delete_pipe"),
        EmailAddress(help_ref="email_address"),
        perm_filter="can_email_pipe_create")

    def email_delete_pipe(self, operator, addr):
        """ Delete email pipe. """
        lp, dom = self._split_email_address(addr, with_checks=False)
        ed = self._get_email_domain(dom)
        self.ba.can_email_pipe_create(operator.get_entity_id(), ed)
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
    default_email_commands['email_failure_message'] = Command(
        ("email", "failure_message"),
        AccountName(help_ref="account_name"),
        SimpleString(help_ref="email_failure_message"),
        perm_filter="can_email_set_failure")

    def email_failure_message(self, operator, uname, message):
        """ Email failure message. """
        et, acc = self._get_email_target_and_account(uname)
        if et.email_target_type != self.const.email_target_deleted:
            raise CerebrumError(
                "You can only set the failure message for deleted users")
        self.ba.can_email_set_failure(operator.get_entity_id(), acc)
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
    default_email_commands['email_edit_pipe_command'] = Command(
        ("email", "edit_pipe_command"),
        EmailAddress(),
        SimpleString(help_ref="command_line"),
        perm_filter="can_email_pipe_edit")

    def email_edit_pipe_command(self, operator, addr, cmd):
        """ Edit pipe command. """
        lp, dom = self._split_email_address(addr)
        ed = self._get_email_domain_from_str(dom)
        self.ba.can_email_pipe_edit(operator.get_entity_id(), ed)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.entity_id)
        except Errors.NotFoundError:
            raise CerebrumError("%s: No such address exists" % addr)
        et = Email.EmailTarget(self.db)
        et.find(ea.email_addr_target_id)
        if not et.email_target_type in (self.const.email_target_pipe,
                                        self.const.email_target_RT):
            raise CerebrumError(
                "%s is not connected to a pipe or RT target" % addr)
        if not cmd.startswith('|'):
            cmd = '|' + cmd
        if (et.email_target_type == self.const.email_target_RT and
           (not re.match(self._rt_patt, cmd))):
            raise CerebrumError("'%s' is not a valid RT command" % cmd)
        et.email_target_alias = cmd
        et.write_db()
        return "OK, edited %s" % addr

    #
    # email edit_pipe_user <address> <uname>
    #
    default_email_commands['email_edit_pipe_user'] = Command(
        ("email", "edit_pipe_user"),
        EmailAddress(),
        AccountName(),
        perm_filter="can_email_pipe_edit")

    def email_edit_pipe_user(self, operator, addr, uname):
        """ Pipe user? """
        lp, dom = self._split_email_address(addr)
        ed = self._get_email_domain_from_str(dom)
        self.ba.can_email_pipe_edit(operator.get_entity_id(), ed)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.entity_id)
        except Errors.NotFoundError:
            raise CerebrumError("%s: No such address exists" % addr)
        et = Email.EmailTarget(self.db)
        et.find(ea.email_addr_target_id)
        if (not et.email_target_type) in (self.const.email_target_pipe,
                                          self.const.email_target_RT):
            raise CerebrumError(
                "'%s' is not connected to a pipe or RT target" % addr)
        et.email_target_using_uid = self._get_account(uname).entity_id
        et.write_db()
        return "OK, edited %s" % addr

    #
    # email create_domain <domainname> <description>
    #
    default_email_commands['email_create_domain'] = Command(
        ("email", "create_domain"),
        SimpleString(help_ref="email_domain"),
        SimpleString(help_ref="string_description"),
        perm_filter="can_email_domain_create")

    def email_create_domain(self, operator, domainname, desc):
        """Create e-mail domain."""
        self.ba.can_email_archive_delete(operator.get_entity_id())
        ed = Email.EmailDomain(self.db)
        # Domainnames need to be lowercase, both when creating as well
        # as looking for them.
        domainname = domainname.lower()
        try:
            ed.find_by_domain(domainname)
            raise CerebrumError(
                "E-mail domain '%s' already exists" % domainname)
        except Errors.NotFoundError:
            pass
        if len(desc) < 3:
            raise CerebrumError("Please supply a better description")
        try:
            ed.populate(domainname, desc)
        except AttributeError, ae:
            raise CerebrumError(str(ae))
        ed.write_db()
        return "OK, domain '%s' created" % domainname

    #
    # email delete_domain <domainname>
    #
    default_email_commands['email_delete_domain'] = Command(
        ("email", "delete_domain"),
        SimpleString(help_ref="email_domain"),
        perm_filter="can_email_domain_create")

    def email_delete_domain(self, operator, domainname):
        """Delete e-mail domain."""
        self.ba.can_email_archive_delete(operator.get_entity_id())

        domainname = domainname.lower()
        ed = Email.EmailDomain(self.db)
        try:
            ed.find_by_domain(domainname)
        except Errors.NotFoundError:
            raise CerebrumError(
                "%s: No e-mail domain by that name" % domainname)

        ea = Email.EmailAddress(self.db)
        if ea.search(domain_id=ed.entity_id, fetchall=True):
            raise CerebrumError(
                "E-mail-domain '%s' has addresses; cannot delete" % domainname)

        eed = Email.EntityEmailDomain(self.db)
        if eed.list_affiliations(domain_id=ed.entity_id):
            raise CerebrumError(
                "E-mail-domain '%s' associated with OUs; cannot delete" %
                domainname)

        ed.delete()
        ed.write_db()

        return "OK, domain '%s' deleted" % domainname

    #
    # email domain_configuration on|off <domain> <category>+
    #
    default_email_commands['email_domain_configuration'] = Command(
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
    default_email_commands['email_domain_set_description'] = Command(
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

    def _onoff(self, enable):
        """ Bool to 'on' or 'off'. """
        if enable:
            return 'on'
        else:
            return 'off'

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
    # this command is accessible for all
    #
    default_email_commands['email_domain_info'] = Command(
        ("email", "domain_info"),
        SimpleString(help_ref="email_domain"),
        fs=FormatSuggestion([
            ("E-mail domain:    %s\n" +
             "Description:      %s", ("domainname", "description")),
            ("Configuration:    %s", ("category",)),
            ("Affiliation:      %s@%s", ("affil", "ou"))
        ]))

    def email_domain_info(self, operator, domainname):
        """ Info about domain. """
        ed = self._get_email_domain_from_str(domainname)
        ret = []
        ret.append({'domainname': domainname,
                    'description': ed.email_domain_description})
        for r in ed.get_categories():
            ret.append({'category':
                        str(self.const.EmailDomainCategory(r['category']))})
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
            ret.append({'affil': affiliations[ou], 'ou': ou})
        return ret

    #
    # email add_domain_affiliation <domain> <stedkode> [<affiliation>]
    #
    default_email_commands['email_add_domain_affiliation'] = Command(
        ("email", "add_domain_affiliation"),
        SimpleString(help_ref="email_domain"),
        OU(),
        Affiliation(optional=True),
        perm_filter="can_email_domain_create")

    def email_add_domain_affiliation(self, operator, domainname, sko, aff=None):
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
    default_email_commands['email_remove_domain_affiliation'] = Command(
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
    default_email_commands['email_create_forward'] = Command(
        ("email", "create_forward"),
        EmailAddress(),
        EmailAddress(help_ref='email_forward_address'),
        perm_filter="can_email_forward_create")

    def email_create_forward(self, operator, localaddr, remoteaddr):
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
        addr = self._check_email_address(remoteaddr)
        try:
            ef.add_forward(addr)
        except Errors.TooManyRowsError:
            raise CerebrumError("Forward address added already (%s)" % addr)
        self._register_spam_settings(localaddr,
                                     self.const.email_target_forward)
        self._register_filter_settings(localaddr,
                                       self.const.email_target_forward)
        return "OK, created forward address '%s'" % localaddr

    def _register_spam_settings(self, address, target_type):
        """ Register spam settings.

        Registers spam settings (level/action) associated with an address.

        """
        et, addr = self._get_email_target_and_address(address)
        esf = Email.EmailSpamFilter(self.db)
        all_targets = [et.entity_id]
        if target_type == self.const.email_target_Sympa:
            # This will fail if we don't have the BofhdEmailListMixin
            all_targets = getattr(self, '_get_all_related_maillist_targets')(
                addr.get_address())
        elif target_type == self.const.email_target_RT:
            # Same, will fail if we don't have the BofhdEmailListMixin
            all_targets = getattr(self, '_get_all_related_rt_targets')(
                addr.get_address())
        target_type = str(target_type)
        if target_type in cereconf.EMAIL_DEFAULT_SPAM_SETTINGS:
            sl, sa = cereconf.EMAIL_DEFAULT_SPAM_SETTINGS[target_type]
            spam_level = int(self.const.EmailSpamLevel(sl))
            spam_action = int(self.const.EmailSpamAction(sa))
            for target_id in all_targets:
                et.clear()
                et.find(target_id)
                esf.clear()
                esf.populate(spam_level, spam_action, parent=et)
                esf.write_db()

    def _register_filter_settings(self, address, target_type):
        """Register spam filter settings associated with an address."""
        et, addr = self._get_email_target_and_address(address)
        etf = Email.EmailTargetFilter(self.db)
        all_targets = [et.entity_id]
        if target_type == self.const.email_target_Sympa:
            # This will fail if we don't have the BofhdEmailListMixin
            all_targets = getattr(self, '_get_all_related_maillist_targets')(
                addr.get_address())
        elif target_type == self.const.email_target_RT:
            # Same, will fail if we don't have the BofhdEmailListMixin
            all_targets = getattr(self, '_get_all_related_rt_targets')(
                addr.get_address())
        target_type = str(target_type)
        if target_type in cereconf.EMAIL_DEFAULT_FILTERS:
            for f in cereconf.EMAIL_DEFAULT_FILTERS[target_type]:
                filter_code = int(self.const.EmailTargetFilter(f))
                for target_id in all_targets:
                    et.clear()
                    et.find(target_id)
                    etf.clear()
                    etf.populate(filter_code, parent=et)
                    etf.write_db()

    def _report_deleted_EA(self, deleted_EA):
        """ Inform postmaster about deleted EmailAddesses.

        Sends a message to postmasters informing them that a number of email
        addresses are about to be deleted.

        postmasters requested on 2009-08-19 that they want to be informed when
        an e-mail list's aliases are being deleted (to have a record, in case
        the operation is to be reversed). The simplest solution is to send an
        e-mail informing them when something is deleted.

        """
        if not deleted_EA:
            return

        def email_info2string(EA):
            """Map whatever email_info returns to something human-friendly"""

            def dict2line(d):
                filtered_keys = ("spam_action_desc", "spam_level_desc",)
                return "\n".join("%s: %s" % (str(key), str(d[key]))
                                 for key in d
                                 if key not in filtered_keys)

            result = list()
            for item in EA:
                if isinstance(item, dict):
                    result.append(dict2line(item))
                else:
                    result.append(repr(item))

            return "\n".join(result)

        to_address = "postmaster-logs@usit.uio.no"
        from_address = "cerebrum-logs@usit.uio.no"
        try:
            sendmail(toaddr=to_address,
                     fromaddr=from_address,
                     subject="Removal of e-mail addresses in Cerebrum",
                     body="""
This is an automatically generated e-mail.

The following e-mail list addresses have just been removed from Cerebrum. Keep
this message, in case a restore is requested later.

Addresses and settings:

%s
                       """ % email_info2string(deleted_EA))

        # We don't want this function ever interfering with bofhd's
        # operation. If it fails -- screw it.
        except Exception:
            self.logger.info("Failed to send e-mail to %s", to_address)
            self.logger.info("Failed e-mail info: %s", repr(deleted_EA))

    #
    # email create_multi <multi-address> <group>
    #
    default_email_commands['email_create_multi'] = Command(
        ("email", "create_multi"),
        EmailAddress(help_ref="email_address"),
        GroupName(help_ref="group_name_dest"),
        perm_filter="can_email_multi_create")

    def email_create_multi(self, operator, addr, group):
        """ Create en e-mail target of type 'multi'. """
        lp, dom = self._split_email_address(addr)
        ed = self._get_email_domain_from_str(dom)
        gr = self._get_group(group)
        self.ba.can_email_multi_create(operator.get_entity_id(), ed, gr)
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
        self._register_spam_settings(addr, self.const.email_target_multi)
        self._register_filter_settings(addr, self.const.email_target_multi)
        return "OK, multi-target for '%s' created" % addr

    #
    # email delete_multi <address>
    #
    default_email_commands['email_delete_multi'] = Command(
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
                raise CerebrumError(
                    "%s is not the primary address of the target" % addr)
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
    # email migrate
    #
    default_email_commands['email_migrate'] = Command(
        ("email", "migrate"),
        AccountName(help_ref="account_name", repeat=True),
        perm_filter='can_email_migrate')

    def email_migrate(self, operator, uname):
        """ Migrate email. """
        acc = self._get_account(uname)
        op = operator.get_entity_id()
        self.ba.can_email_migrate(op, acc)
        for r in acc.get_spread():
            if r['spread'] == int(self.const.spread_uio_imap):
                raise CerebrumError("%s is already an IMAP user" % uname)
        acc.add_spread(self.const.spread_uio_imap)
        if op != acc.entity_id:
            # the local sysadmin should get a report as well, if
            # possible, so change the request add_spread() put in so
            # that he is named as the requestee.  the list of requests
            # may turn out to be empty, ie. processed already, but this
            # unlikely race condition is too hard to fix.
            br = BofhdRequests(self.db, self.const)
            for r in br.get_requests(operation=self.const.bofh_email_move,
                                     entity_id=acc.entity_id):
                br.delete_request(request_id=r['request_id'])
                br.add_request(op, r['run_at'], r['operation'], r['entity_id'],
                               r['destination_id'], r['state_data'])
        return 'OK'

    #
    # email move
    #
    default_email_commands['email_move'] = Command(
        ("email", "move"),
        AccountName(help_ref="account_name", repeat=True),
        SimpleString(help_ref='string_email_host'),
        SimpleString(help_ref='string_email_move_type', optional=True),
        Date(optional=True),
        perm_filter='can_email_move')

    def email_move(self, operator, uname, server, move_type='file', when=None):
        """ Email move. """
        acc = self._get_account(uname)
        self.ba.can_email_move(operator.get_entity_id(), acc)
        et = Email.EmailTarget(self.db)
        et.find_by_target_entity(acc.entity_id)
        old_server = et.email_server_id
        es = Email.EmailServer(self.db)
        try:
            es.find_by_name(server)
        except Errors.NotFoundError:
            raise CerebrumError("%s is not registered as an e-mail server" %
                                server)
        if old_server == es.entity_id:
            raise CerebrumError("User is already at %s" % server)

        # Explicitly check if move_type is 'file' or 'nofile'.
        # Abort if it isn't
        if move_type == 'nofile':
            et.email_server_id = es.entity_id
            et.write_db()
            return "OK, updated e-mail server for %s (to %s)" % (uname, server)
        elif not move_type == 'file':
            raise CerebrumError(
                "Unknown move_type '%s'; must be either 'file' or 'nofile'" %
                move_type)

        # TODO: Remove this when code has been checked after migrating to
        # murder.
        raise CerebrumError("Only 'nofile' is to be used at this time.")

        if when is None:
            when = DateTime.now()
        else:
            when = self._parse_date(when)
            if when < DateTime.now():
                raise CerebrumError("Request time must be in the future")

        if es.email_server_type == self.const.email_server_type_cyrus:
            spreads = [int(r['spread']) for r in acc.get_spread()]
            br = BofhdRequests(self.db, self.const)
            if self.const.spread_uio_imap not in spreads:
                # UiO's add_spread mixin will not do much since
                # email_server_id is set to a Cyrus server already.
                acc.add_spread(self.const.spread_uio_imap)
            # Create the mailbox.
            req = br.add_request(operator.get_entity_id(), when,
                                 self.const.bofh_email_create,
                                 acc.entity_id, es.entity_id)
            # Now add a move request.
            br.add_request(operator.get_entity_id(), when,
                           self.const.bofh_email_move,
                           acc.entity_id, es.entity_id, state_data=req)
            # Norwegian (nynorsk) names:
            wdays_nn = ["måndag", "tysdag", "onsdag", "torsdag",
                        "fredag", "laurdag", "søndag"]
            when_nn = "%s %d. kl %02d:%02d" % \
                      (wdays_nn[when.day_of_week],
                       when.day, when.hour, when.minute - when.minute % 10)
            nth_en = ["th"] * 32
            nth_en[1] = nth_en[21] = nth_en[31] = "st"
            nth_en[2] = nth_en[22] = "nd"
            nth_en[3] = nth_en[23] = "rd"
            when_en = "%s %d%s at %02d:%02d" % \
                      (DateTime.Weekday[when.day_of_week],
                       when.day, nth_en[when.day],
                       when.hour, when.minute - when.minute % 10)
            try:
                mail_template(acc.get_primary_mailaddress(),
                              cereconf.USER_EMAIL_MOVE_WARNING,
                              sender="postmaster@usit.uio.no",
                              substitute={'USER': acc.account_name,
                                          'WHEN_EN': when_en,
                                          'WHEN_NN': when_nn})
            except Exception, e:
                self.logger.info("Sending mail failed: %s", e)
        else:
            # TBD: should we remove spread_uio_imap ?
            # It does not do much good to add to a bofh request, mvmail
            # can't handle this anyway.
            raise CerebrumError("can't move to non-IMAP server")
        return "OK, '%s' scheduled for move to '%s'" % (uname, server)

    #
    # email pause
    #
    default_email_commands['email_pause'] = Command(
        ("email", "pause"),
        SimpleString(help_ref='string_email_on_off'),  # why not yesno?
        AccountName(help_ref="account_name"),
        perm_filter='can_email_pause')

    def email_pause(self, operator, on_off, uname):
        """ Pause email delivery. """
        et, acc = self._get_email_target_and_account(uname)
        self.ba.can_email_pause(operator.get_entity_id(), acc)
        self._ldap_init()

        dn = cereconf.LDAP_EMAIL_DN % et.entity_id

        if on_off in ('ON', 'on'):
            et.populate_trait(self.const.trait_email_pause, et.entity_id)
            et.write_db()
            r = self._ldap_modify(dn, "mailPause", "TRUE")
            if r:
                et.commit()
                return "mailPause set for '%s'" % uname
            else:
                et._db.rollback()
                return "Error: mailPause not set for '%s'" % uname

        elif on_off in ('OFF', 'off'):
            try:
                et.delete_trait(self.const.trait_email_pause)
                et.write_db()
            except Errors.NotFoundError:
                return "Error: mailPause not unset for '%s'" % uname

            r = self._ldap_modify(dn, "mailPause")
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
    default_email_commands['email_list_pause'] = Command(
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
            et.clear()
            et.find(row['entity_id'])
            if self.const.EmailTarget(et.email_target_type) == \
               self.const.email_target_account:
                ac.clear()
                ac.find(et.email_target_entity_id)
                res.append(ac.account_name)
            else:
                epa.clear()
                epa.find_by_alias(et.email_target_alias)
                ea.clear()
                ea.find(epa.email_primaddr_id)
                res.append(ea.get_address())

        return {'paused': '\n'.join(res)}

    #
    # email quota <uname>+ hardquota-in-mebibytes [softquota-in-percent]
    #
    default_email_commands['email_quota'] = Command(
        ('email', 'quota'),
        AccountName(help_ref='account_name', repeat=True),
        Integer(help_ref='number_size_mib'),
        Integer(help_ref='number_percent', optional=True),
        perm_filter='can_email_set_quota')

    def email_quota(self, operator, uname, hquota,
                    squota=cereconf.EMAIL_SOFT_QUOTA):
        """ Set email quota. """
        acc = self._get_account(uname)
        op = operator.get_entity_id()
        self.ba.can_email_set_quota(op, acc)
        if not str(hquota).isdigit() or not str(squota).isdigit():
            raise CerebrumError("Quota must be numeric")
        hquota = int(hquota)
        squota = int(squota)
        if hquota < 100 and hquota != 0:
            raise CerebrumError("The hard quota can't be less than 100 MiB")
        if hquota > 1024*1024:
            raise CerebrumError("The hard quota can't be more than 1 TiB")
        if squota < 10 or squota > 99:
            raise CerebrumError(
                "The soft quota must be in the interval 10% to 99%")
        et = Email.EmailTarget(self.db)
        try:
            et.find_by_target_entity(acc.entity_id)
        except Errors.NotFoundError:
            raise CerebrumError(
                "The account %s has no e-mail data associated with it" % uname)
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
                raise CerebrumError(
                    "The account %s has no e-mail server associated with it" %
                    uname)
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
    default_email_commands['email_add_filter'] = Command(
        ('email', 'add_filter'),
        SimpleString(help_ref='string_email_filter'),
        SimpleString(help_ref='string_email_target_name', repeat="True"),
        perm_filter='is_postmaster')

    def email_add_filter(self, operator, filter, address):
        """ Add a filter to an existing e-mail target. """
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        etf = Email.EmailTargetFilter(self.db)
        filter_code = self._get_constant(self.const.EmailTargetFilter, filter)
        et, addr = self._get_email_target_and_address(address)
        target_ids = [et.entity_id]
        if et.email_target_type == self.const.email_target_Sympa:
            # The only way we can get here is if uname is actually an e-mail
            # address on its own.
            # This will fail if we don't have the BofhdEmailListMixin
            target_ids = getattr(self,
                                 '_get_all_related_maillist_targets')(address)
        elif int(et.email_target_type) == (self.const.email_target_RT):
            # Same, will fail if we don't have the BofhdEmailListMixin
            target_ids = getattr(self, '_get_all_related_rt_targets')(address)
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
    default_email_commands['email_remove_filter'] = Command(
        ('email', 'remove_filter'),
        SimpleString(help_ref='string_email_filter'),
        SimpleString(help_ref='string_email_target_name', repeat="True"),
        perm_filter='is_postmaster')

    def email_remove_filter(self, operator, filter, address):
        """ Remove filter. """
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        etf = Email.EmailTargetFilter(self.db)
        filter_code = self._get_constant(self.const.EmailTargetFilter, filter)
        et, addr = self._get_email_target_and_address(address)
        target_ids = [et.entity_id]
        if et.email_target_type == self.const.email_target_Sympa:
            # The only way we can get here is if uname is actually an e-mail
            # address on its own.
            #
            # This will fail if we don't have the BofhdEmailListMixin
            target_ids = getattr(self,
                                 '_get_all_related_maillist_targets')(address)
        elif int(et.email_target_type) == (self.const.email_target_RT):
            # Same, will fail if we don't have the BofhdEmailListMixin
            target_ids = getattr(self, '_get_all_related_rt_targets')(address)
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

    # email spam_level <level> <uname>+
    default_email_commands['email_spam_level'] = Command(
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
            # This will fail if we don't have the BofhdEmailListMixin
            target_ids = getattr(self,
                                 '_get_all_related_maillist_targets')(uname)
        elif int(et.email_target_type) == self.const.email_target_RT:
            # Same, will fail if we don't have the BofhdEmailListMixin
            target_ids = getattr(self, '_get_all_related_rt_targets')(uname)

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
    default_email_commands['email_spam_action'] = Command(
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
            raise CerebrumError(
                "Spam action code not found: {}".format(action))
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
            # This will fail if we don't have the BofhdEmailListMixin
            target_ids = getattr(self,
                                 '_get_all_related_maillist_targets')(uname)
        elif int(et.email_target_type) == self.const.email_target_RT:
            # Same, will fail if we don't have the BofhdEmailListMixin
            target_ids = getattr(self, '_get_all_related_rt_targets')(uname)

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
    default_email_commands['email_tripnote'] = Command(
        ('email', 'tripnote'),
        SimpleString(help_ref='email_tripnote_action'),
        AccountName(help_ref='account_name'),
        SimpleString(help_ref='date', optional=True),
        perm_filter='can_email_tripnote_toggle')

    def email_tripnote(self, operator, action, uname, when=None):
        """ Turn on/off tripnote. """

        if action == 'on':
            enable = True
        elif action == 'off':
            enable = False
        else:
            raise CerebrumError(
                "Unknown tripnote action '%s', choose one of on or off" %
                action)
        acc = self._get_account(uname)
        self.ba.can_email_tripnote_toggle(operator.get_entity_id(), acc)
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
    default_email_commands['email_list_tripnotes'] = Command(
        ('email', 'list_tripnotes'),
        AccountName(help_ref='account_name'),
        perm_filter='can_email_tripnote_toggle',
        fs=FormatSuggestion([
            ("%s%s -- %s: %s\n" +
             "%s\n", ("dummy", format_day('start_date'), 
                      format_day('end_date'), "enable", "text"))
        ]))

    def email_list_tripnotes(self, operator, uname):
        """ List tripnotes for a user. """
        acc = self._get_account(uname, idtype='name')
        self.ba.can_email_tripnote_toggle(operator.get_entity_id(), acc)

        try:
            self.ba.can_email_tripnote_edit(operator.get_entity_id(), acc)
            hide = False
        except:
            hide = True

        ev = Email.EmailVacation(self.db)
        try:
            ev.find_by_target_entity(acc.entity_id)
        except Errors.NotFoundError:
            return "No tripnotes for %s" % uname

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
            result.append({'dummy': "",
                           'start_date': r['start_date'],
                           'end_date': r['end_date'],
                           'enable': enable,
                           'text': text})
        if result:
            return result
        else:
            return "No tripnotes for %s" % uname

    #
    # email add_tripnote <uname> <text> <begin-date>[-<end-date>]
    #
    default_email_commands['email_add_tripnote'] = Command(
        ('email', 'add_tripnote'),
        AccountName(help_ref='account_name'),
        SimpleString(help_ref='tripnote_text'),
        SimpleString(help_ref='string_from_to'),
        perm_filter='can_email_tripnote_edit')

    def email_add_tripnote(self, operator, uname, text, when=None):
        """ Add a tripnote. """
        acc = self._get_account(uname, idtype='name')
        self.ba.can_email_tripnote_edit(operator.get_entity_id(), acc)
        date_start, date_end = self._parse_date_from_to(when)
        now = self._today()
        if date_end is not None and date_end < now:
            raise CerebrumError("Won't add already obsolete tripnotes")
        ev = Email.EmailVacation(self.db)
        ev.find_by_target_entity(acc.entity_id)
        for v in ev.get_vacation():
            if date_start is not None and v['start_date'] == date_start:
                raise CerebrumError(
                    "There's a tripnote starting on %s already" %
                    str(date_start)[:10])

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
    default_email_commands['email_remove_tripnote'] = Command(
        ('email', 'remove_tripnote'),
        AccountName(help_ref='account_name'),
        SimpleString(help_ref='date', optional=True),
        perm_filter='can_email_tripnote_edit')

    def email_remove_tripnote(self, operator, uname, when=None):
        """ Remove tripnote. """
        acc = self._get_account(uname)
        self.ba.can_email_tripnote_edit(operator.get_entity_id(), acc)
        # TBD: This variable isn't used; is this call a sign of rot,
        # or is it here for input validation?
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
            raise CerebrumError(
                "User %s has more than one tripnote, specify which "
                "one by adding the start date to command" % uname)
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
        if abs(int(best_delta)) > 1.5*86400:
            raise CerebrumError("There are no tripnotes starting at %s" % when)
        return best

    #
    # email update <uname>
    # Anyone can run this command.  Ideally, it should be a no-op,
    # and we should remove it when that is true.
    #
    default_email_commands['email_update'] = Command(
        ('email', 'update'),
        AccountName(help_ref='account_name', repeat=True))

    def email_update(self, operator, uname):
        """ Email update. """
        acc = self._get_account(uname, idtype='name')
        acc.update_email_addresses()
        return "OK, updated e-mail address for '%s'" % uname
