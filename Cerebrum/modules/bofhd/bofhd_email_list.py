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
""" Email list mixin and utils for BofhdExtensions. """
import cereconf
import cerebrum_path

import re
import pickle
from mx import DateTime

from Cerebrum import Errors
from Cerebrum.modules import Email

from Cerebrum.modules.bofhd.bofhd_email import BofhdEmailMixinBase
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.bofhd.cmd_param import Command, FormatSuggestion, \
    SimpleString, EmailAddress, YesNo


class BofhdEmailListMixinBase(BofhdEmailMixinBase):

    """ Email list related commands.

    This mixin contains bofhd functions for both Sympa and Mailman list
    systems.

    """

    # TODO: We ned to purge UIO-specific functions from this file.

    default_email_list_commands = {}

    def _get_email_server(self, name):
        """ Get EmailServer object by name. """
        es = Email.EmailServer(self.db)
        try:
            if isinstance(name, (int, long)):
                es.find(name)
            else:
                es.find_by_name(name)
            return es
        except Errors.NotFoundError:
            raise CerebrumError("Unknown mail server: %s" % name)

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

    def _is_mailing_list(self, listname):
        """ Check if L{listname} exists as a mailing list.

        If L{listname} exists as a mailing list in any subclass, then it's a
        mailing list.

        """
        # Multiple mixins will inherit from this class, so we need to make sure
        # to call the _is_mailing_list method of the next mixin if the result
        # is False.
        if (hasattr(super(BofhdEmailListMixinBase, self),
                    '_is_mailing_list') and
            getattr(super(BofhdEmailListMixinBase, self),
                    '_is_mailing_list')(listname)):
            return True

        return False

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
            # pattern comes from self._sympa_addr2alias.keys()
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

        If this method is called, it means a subclass didn't have a _get_all...
        method, or the address was not a mailing list that the subclass
        handles. This method checks if there's a valid list in any other
        potential mixins. If not, we raise a CerebrumError.

        Given any address associated with a mailing list, this method returns
        all the EmailTarget id's that are associated with that mailing list.

        E.g.: 'foo-subscribe@domain' for a Sympa list will return the
        EmailTarget id's for addresses 'foo@domain', 'foo-owner@domain',
        'foo-request@domain', 'foo-editor@domain', 'foo-subscribe@domain' and
        'foo-unsubscribe@domain'

        @type address: basestring
        @param address:
            One of the mail addresses associated with a mailing list.

        @rtype: sequence (of ints)
        @return:
            A sequence with entity_ids of all EmailTargets related to the
            mailing list that address is related to.

        """
        # Multiple mixins will inherit from this class.
        # If this method is called, it means a child class called us.
        # This happens when the child class was unable to handle the address
        # given. We need to make sure to call the _get_all... method of other
        # mixin classes.
        if hasattr(super(BofhdEmailListMixinBase, self),
                   '_get_all_related_maillist_targets'):
            return getattr(super(BofhdEmailListMixinBase, self),
                           '_get_all_related_maillist_targets')(address)

        # No other implementation of this method exists in the mro
        raise CerebrumError("'%s' is not associated with a mailing list" %
                            address)

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


class BofhdEmailSympaMixin(BofhdEmailListMixinBase):

    """ Email list related commands for the Sympa mailing list system. """

    default_sympa_commands = {}

    # TODO: Move all sympa specific methods and attributes here.

    # SYMPA SETTINGS
    #
    # aliases that we must create for each sympa mailing list.
    # -request, -editor, -owner, -subscribe, -unsubscribe all come from sympa
    # owner- and -admin are the remnants of mailman
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

    def _validate_sympa_list(self, listname):
        """ Check whether L{listname} is the 'official' name for a sympa ML.

        Raises CerebrumError if it is not.

        """
        if self._get_sympa_list(listname) != listname:
            raise CerebrumError("%s is NOT the official Sympa list name" %
                                listname)
        return listname

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

        def has_prefix(address):
            local_part, domain = self._split_email_address(address)
            return True in [local_part.startswith(x)
                            for x in self._sympa_address_prefixes]

        def has_suffix(address):
            local_part, domain = self._split_email_address(address)
            return True in [local_part.endswith(x)
                            for x in self._sympa_address_suffixes]

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
        if not (has_prefix(listname) or has_suffix(listname)):
            raise not_sympa_error

        # There is a funky suffix/prefix. Is listname actually such a
        # secondary address? Try to chop off the funky part and test.
        local_part, domain = self._split_email_address(listname)
        for prefix in self._sympa_address_prefixes:
            if not local_part.startswith(prefix):
                continue

            lp_tmp = local_part[len(prefix):]
            addr_to_test = lp_tmp + "@" + domain
            try:
                self._get_sympa_list(addr_to_test)
                return addr_to_test
            except CerebrumError:
                pass

        for suffix in self._sympa_address_suffixes:
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

    def _is_mailing_list(self, listname):
        """ Check whether L{listname} refers to a valid mailing list.

        This method checks if there's a valid list in other mixins, or this one.

        @rtype: bool
        @return:
            True if listname points to a valid sympa or mailman list. False
            otherwise.

        """
        # Sympa list?
        try:
            self._validate_sympa_list(listname)
            return True
        except CerebrumError:
            pass

        # Must call super() so that all mixins are checked
        if super(BofhdEmailSympaMixin, self)._is_mailing_list(listname):
            return True

        return False

    def _get_all_related_maillist_targets(self, address):
        """ Locate and return all email targets (addresses) for a sympa list.

        Given any address associated with a mailing list, this method returns
        all the EmailTarget id's that are associated with that mailing list.

        See method in superclass for more info.

        """
        et, ea = self._get_email_target_and_address(address)

        if et.email_target_type != self.const.email_target_Sympa:
            # Not Sympa list, let the superclass deal with it.
            return super(BofhdEmailSympaMixin,
                         self)._get_all_related_maillist_targets(address)

        official_ml_address = self._get_sympa_list(ea.get_address())
        patterns = [x[0] for x in self._sympa_addr2alias]

        return self._get_maillist_targets_for_pattern(official_ml_address,
                                                      patterns)

    def _create_sympa_list(self, operator, listname, delivery_host,
                           force=False):
        """ Create a new Sympa list in cerebrum. """
        local_part, domain = self._request_list_localpart_domain(operator,
                                                                 listname,
                                                                 force=force)
        self._register_sympa_list_addresses(listname, local_part, domain,
                                            delivery_host)
        # register auto spam and filter settings for the list
        self._register_spam_settings(listname, self.const.email_target_Sympa)
        self._register_filter_settings(listname, self.const.email_target_Sympa)

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
        for pattern, pipe_destination in self._sympa_addr2alias:
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
            for a, alias in self._sympa_addr2alias:
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
                delivery_host = self._get_email_server(et_sympa.email_server_id).name
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

    # COMMANDS

    #
    # sympa create_list <run-host> <delivery-host> <listaddr> <admins>
    #                   <profile> <desc> [force?]
    #
    default_sympa_commands['sympa_create_list'] = Command(
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

        delivery_host = self._get_email_server(delivery_host)
        force = self._is_yes(yes_no_force)
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
    # sympa delete_list <run-host> <list-address>
    #
    default_sympa_commands['sympa_remove_list'] = Command(
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
        force_request = self._is_yes(force_yes_no)

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

        deleted_EA = self.email_info(operator, listname)
        # needed for pattern interpolation below (these are actually used)
        local_part, domain = self._split_email_address(listname)
        for pattern, pipe_destination in self._sympa_addr2alias:
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

        if cereconf.INSTITUTION_DOMAIN_NAME == 'uio.no':
            self._report_deleted_EA(deleted_EA)
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
    default_sympa_commands['sympa_create_list_alias'] = Command(
        ("sympa", "create_list_alias"),
        EmailAddress(help_ref="mailing_list_exist"),
        EmailAddress(help_ref="mailing_list"),
        YesNo(help_ref="yes_no_force", optional=True),
        fs=FormatSuggestion([("List alias '%s' created", ('alias', ))]),
        perm_filter="can_email_list_create")

    def sympa_create_list_alias(self, operator, listname, address,
                                yes_no_force='No'):
        """ Create a secondary name for an existing Sympa list. """
        force = self._is_yes(yes_no_force)
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
    # email remove_sympa_list_alias <alias>
    #
    default_sympa_commands['sympa_remove_list_alias'] = Command(
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

        for addr_format, pipe in self._sympa_addr2alias:
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
    # email_create_sympa_cerebrum_list
    # TODO: WTF?
    #
    default_sympa_commands['sympa_create_list_in_cerebrum'] = Command(
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

        delivery_host = self._get_email_server(delivery_host)
        force = self._is_yes(yes_no_force)
        self._create_sympa_list(operator, listname, delivery_host, force=force)
        return {'listname': listname}

    #
    # email reassign_list_address <list-address>
    #
    # requested by bca, will be used during the migration of e-mail
    # lists from mailman to sympa this command will delete a mailman
    # target for a given list and create a sympa target without
    # creating a sympa list.
    #
    default_sympa_commands['sympa_reassign_mailman_list'] = Command(
        ("sympa", "reassign_mailman_list"),
        EmailAddress(help_ref="mailing_list"),
        SimpleString(help_ref='string_email_delivery_host'),
        YesNo(help_ref="yes_no_force", optional=True),
        perm_filter="can_email_list_create")

    def sympa_reassign_mailman_list(self, operator, listname,
                                    sympa_delivery_host, yes_no_force='No'):
        """ Reassign a Mailman list to a Sympa list.
        
        Requires the BofhdEmailMailmanMixin.

        """
        if not isinstance(self, BofhdEmailMailmanMixin):
            raise CerebrumError("No Mailman support in this version of Bofh")
        et_mailman, ea = self._get_email_target_and_address(listname)
        esf_mailman = Email.EmailSpamFilter(self.db)
        etf_mailman = Email.EmailTargetFilter(self.db)
        esf_mailman.clear()
        force_alias = self._is_yes(yes_no_force)

        try:
            esf_mailman.find(et_mailman.entity_id)
            spam_level = esf_mailman.email_spam_level
            spam_action = esf_mailman.email_spam_action
        except Errors.NotFoundError:
            spam_level = None
            spam_action = None
        mailman_filters = []
        change_filters = False
        for f in etf_mailman.list_email_target_filter(
                target_id=et_mailman.entity_id):
            if int(f['filter']) == int(self.const.email_target_filter_greylist):
                mailman_filters.append(f['filter'])
        if len(mailman_filters) == 0:
            change_filters = True
        if not self._is_mailing_list(listname):
            return "Cannot migrate a non-list target to Sympa."
        self.ba.can_email_list_create(operator.get_entity_id(), ea)
        aliases = []
        for r in et_mailman.get_addresses():
            a = "%(local_part)s@%(domain)s" % r
            if a == listname:
                continue
            if a is not None:
                aliases.append(a)

        delivery_host = self._get_email_server(sympa_delivery_host)
        self._delete_mailman_list(operator.get_entity_id(), listname, ea,
                                  target_only=True)

        # for postmaster an alias is treated in the same way as a primary
        # address it is therefore acceptable to use force_alias to allow
        # postmaster to create primary list addresses where local part
        # coincides with av registered account name in Cerebrum
        self._create_sympa_list(operator, listname, delivery_host,
                                force=force_alias)
        for address in aliases:
                self._create_sympa_list_alias(operator,
                                              listname,
                                              address,
                                              delivery_host,
                                              force_alias=force_alias)
        et_sympa, ea = self._get_email_target_and_address(listname)
        if change_filters:
            etf_sympa = Email.EmailTargetFilter(self.db)
            target_ids = [et_sympa.entity_id]
            if int(et_sympa.email_target_type) == self.const.email_target_Sympa:
                # The only way we can get here is if uname is actually an
                # e-mail address on its own.
                target_ids = self._get_all_related_maillist_targets(listname)
            for target_id in target_ids:
                try:
                    et_sympa.clear()
                    et_sympa.find(target_id)
                except Errors.NotFoundError:
                    continue
                try:
                    etf_sympa.clear()
                    etf_sympa.find(et_sympa.entity_id,
                                   self.const.email_target_filter_greylist)
                except Errors.NotFoundError:
                    continue
                etf_sympa.disable_email_target_filter(
                    self.const.email_target_filter_greylist)
                etf_sympa.write_db()

        if not spam_level and spam_action:
            return "%s (%s) %s" % (
                "Migrated mailman target to sympa target",
                listname,
                "no spam settings where found, assigned default")

        esf_sympa = Email.EmailSpamFilter(self.db)
        # All this magic with target ids is necessary to accomodate MLs (all
        # ETs "related" to the same ML should have the
        # spam settings should be processed )
        target_ids = [et_sympa.entity_id]
        # The only way we can get here is if uname is actually an e-mail
        # address on its own.
        if int(et_sympa.email_target_type) == self.const.email_target_Sympa:
            target_ids = self._get_all_related_maillist_targets(listname)
        for target_id in target_ids:
            try:
                et_sympa.clear()
                et_sympa.find(target_id)
            except Errors.NotFoundError:
                continue
            try:
                esf_sympa.clear()
                esf_sympa.find(et_sympa.entity_id)
                esf_sympa.email_spam_level = spam_level
                esf_sympa.email_spam_action = spam_action
            except Errors.NotFoundError:
                # this will not happen as standard spam settings are
                # assigned when a list is created
                continue
            esf_sympa.write_db()

        return "Migrated mailman target to sympa target (%s)" % listname


class BofhdEmailMailmanMixin(BofhdEmailListMixinBase):

    """ Email list related commands for the Mailman mailing list system. """

    default_mailman_commands = {}

    # MAILMAN SETTINGS
    #
    # The first address in the list becomes the primary address.
    _interface2addrs = {'post': ["%(local_part)s@%(domain)s"],
                        'mailcmd': ["%(local_part)s-request@%(domain)s"],
                        'mailowner': ["%(local_part)s-owner@%(domain)s",
                                      "%(local_part)s-admin@%(domain)s",
                                      "owner-%(local_part)s@%(domain)s"], }
    _mailman_pipe = "|/local/Mailman/mail/wrapper %(interface)s %(listname)s"
    _mailman_patt = r'\|/local/Mailman/mail/wrapper (\S+) (\S+)$'

    def _check_mailman_official_name(self, listname):
        mlist = self._get_mailman_list(listname)
        if mlist is None:
            raise CerebrumError("%s is not a Mailman list" % listname)
        # List names without complete e-mail address are probably legacy
        if (listname == mlist or (mlist.count('@') == 0 and
                                  listname.startswith(mlist + "@"))):
            return mlist
        raise CerebrumError(
            "%s is not the official name of the list %s" % (listname, mlist))

    def _get_mailman_list(self, listname):
        """ Return the official name for the list.

        Raises CerebrumError if listname isn't a Mailman list.

        """
        try:
            ea = Email.EmailAddress(self.db)
            ea.find_by_address(listname)
        except Errors.NotFoundError:
            raise CerebrumError("No address '%s'" % listname)
        et = Email.EmailTarget(self.db)
        et.find(ea.get_target_id())
        if not et.email_target_alias:
            raise CerebrumError("%s isn't a Mailman list" % listname)
        m = re.match(self._mailman_patt, et.email_target_alias)
        if not m:
            raise CerebrumError(
                "Unrecognised pipe command for Mailman list: %s" %
                et.email_target_alias)
        return m.group(2)

    def _is_mailing_list(self, listname):
        """ Check whether L{listname} refers to a valid mailing list.

        This method checks if there's a valid list in other mixins, or this
        one.

        @rtype: bool
        @return:
            True if listname points to a valid sympa or mailman list. False
            otherwise.

        """
        # Mailman list?
        try:
            # This is a bit ugly, because _get_mailman_list may either throw an
            # exception or return None to indicate non-valid list.
            ml = self._get_mailman_list(listname)
            if ml is not None:
                return True
        except CerebrumError:
            pass

        # Must call super() so that all mixins are checked
        if super(BofhdEmailMailmanMixin, self)._is_mailing_list(listname):
            return True

        return False

    def _get_all_related_maillist_targets(self, address):
        """ Locate and return all email targets (addresses) for a mailman list.

        Given any address associated with a mailing list, this method returns
        all the EmailTarget id's that are associated with that mailing list.

        See method in superclass for more info.

        """
        et, ea = self._get_email_target_and_address(address)

        if et.email_target_type != self.const.email_target_Mailman:
            # Not Mailman list, let the superclass deal with it.
            return super(BofhdEmailMailmanMixin,
                         self)._get_all_related_maillist_targets(address)

        official_ml_address = self._get_mailman_list(ea.get_address())
        patterns = [x[0] for x in self._interface2addrs.values()]

        return self._get_maillist_targets_for_pattern(official_ml_address,
                                                      patterns)

    def _create_mailman_list(self, operator, listname, force=False):
        """ Create a new Mailman list in cerebrum. """
        # TODO: _request does permission checks?
        local_part, domain = self._request_list_localpart_domain(operator,
                                                                 listname,
                                                                 force=force)
        self._register_mailman_list_addresses(listname, local_part, domain)
        # register auto spam and filter settings for the list
        self._register_spam_settings(listname, self.const.email_target_Mailman)
        self._register_filter_settings(listname,
                                       self.const.email_target_Mailman)

    def _delete_mailman_list(self, op, listname, ea, target_only=False):
        """ Delete mailman list with no permission checking. """
        listname = self._check_mailman_official_name(listname)
        result = []
        et = Email.EmailTarget(self.db)
        epat = Email.EmailPrimaryAddressTarget(self.db)
        list_id = ea.entity_id
        deleted_EA = self.email_info(op, listname)
        for interface in self._interface2addrs.keys():
            alias = self._mailman_pipe % {'interface': interface,
                                          'listname': listname}
            try:
                et.clear()
                et.find_by_alias(alias)
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
                    if interface == 'post':
                        result.append({'address': addr})
                et.delete()
            except Errors.NotFoundError:
                pass
        if cereconf.INSTITUTION_DOMAIN_NAME == 'uio.no':
            # TODO: RLY? Hard coded uio.no value? This should be subclassed...
            if not target_only:
                self._report_deleted_EA(deleted_EA)
                br = BofhdRequests(self.db, self.const)
                # IVR 2008-08-04 +1 hour to allow changes to spread to LDAP.
                # This way we'll have a nice SMTP-error, rather than a
                # confusing error burp from mailman.
                br.add_request(op,
                               DateTime.now() + DateTime.DateTimeDelta(0, 1),
                               self.const.bofh_mailman_remove, list_id, None,
                               listname)
        return result

    def _create_mailman_list_alias(self, operator, listname, address,
                                   force_alias=False):
        """Create an alias L{address} for an existing Mailman L{listname}.

        @type listname: basestring
        @param listname:
          Email address for an existing mailing list. This is the ML we are
          aliasing.

        @type address: basestring
        @param address:
          Email address which will be the alias.

        """
        lp, dom = self._split_email_address(address)
        ed = self._get_email_domain_from_str(dom)
        self.ba.can_email_list_create(operator.get_entity_id(), ed)
        self._check_mailman_official_name(listname)
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
        self._register_mailman_list_addresses(listname, lp, dom)

    def _register_mailman_list_addresses(self, listname, lp, dom):
        """ Add list, owner and request addresses.

        Listname is a mailing list name, which may be different from lp@dom,
        which is the basis for the local parts and domain of the addresses
        which should be added.

        """
        ed = Email.EmailDomain(self.db)
        ed.find_by_domain(dom)

        et = Email.EmailTarget(self.db)
        ea = Email.EmailAddress(self.db)
        epat = Email.EmailPrimaryAddressTarget(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.entity_id)
        except Errors.NotFoundError:
            pass
        else:
            raise CerebrumError(
                "The address %s@%s is already in use" % (lp, dom))

        mailman = self._get_account("mailman", actype="PosixUser")

        for interface in self._interface2addrs.keys():
            targ = self._mailman_pipe % {'interface': interface,
                                         'listname': listname, }
            found_target = False
            for addr_format in self._interface2addrs[interface]:
                addr = addr_format % {'local_part': lp,
                                      'domain': dom}
                addr_lp, addr_dom = addr.split('@')
                # all addresses are in same domain, do an EmailDomain
                # lookup here if  _interface2addrs changes:
                try:
                    ea.clear()
                    ea.find_by_local_part_and_domain(addr_lp,
                                                     ed.entity_id)
                    raise CerebrumError(
                        "Can't add list %s, the address %s is already in use" %
                        (listname, addr))
                except Errors.NotFoundError:
                    pass
                if not found_target:
                    et.clear()
                    try:
                        et.find_by_alias_and_account(targ, mailman.entity_id)
                    except Errors.NotFoundError:
                        et.populate(self.const.email_target_Mailman,
                                    alias=targ, using_uid=mailman.entity_id)
                        et.write_db()
                ea.clear()
                ea.populate(addr_lp, ed.entity_id, et.entity_id)
                ea.write_db()
                if not found_target:
                    epat.clear()
                    try:
                        epat.find(et.entity_id)
                    except Errors.NotFoundError:
                        epat.clear()
                        epat.populate(ea.entity_id, parent=et)
                        epat.write_db()
                    found_target = True

    def _email_info_mailman(self, et, addr):
        """ Get info about Mailman email lists.

        This method is a helper for the email_info command. It provides extra
        info about Mailman lists, and is only called if email_info encounters
        an EmailTarget of type 'mailman'.

        @rtype: list
        @return: A list of dictionaries with mailman list info.

        """
        m = re.match(self._mailman_patt, et.email_target_alias)
        if not m:
            raise CerebrumError(
                "Unrecognised pipe command for Mailman list: %s" %
                et.email_target_alias)
        # We extract the official list name from the pipe command.
        interface, listname = m.groups()
        ret = [{'mailman_list': listname}]
        if listname.count('@') == 0:
            lp = listname
            dom = addr.split('@')[1]
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
        # NB! Do NOT overwrite et (it's used in email_info after calling
        # _email_info_mailman)
        et_mailman = Email.EmailTarget(self.db)
        et_mailman.clear()
        et_mailman.find(ea.email_addr_target_id)
        addrs = self._get_valid_email_addrs(et_mailman, sort=True)
        ret += self._email_info_forwarding(et_mailman, addrs)
        aliases = []
        for r in et_mailman.get_addresses():
            a = "%(local_part)s@%(domain)s" % r
            if a == listname:
                continue
            aliases.append(a)
        if aliases:
            ret.append({'mailman_alias_1': aliases[0]})
            for idx in range(1, len(aliases)):
                ret.append({'mailman_alias': aliases[idx]})
        # all administrative addresses
        for iface in ('mailcmd', 'mailowner'):
            try:
                et_mailman.clear()
                et_mailman.find_by_alias(self._mailman_pipe %
                                         {'interface': iface,
                                          'listname': listname})
                addrs = et_mailman.get_addresses()
                if addrs:
                    ret.append({'mailman_' + iface + '_1':
                                '%(local_part)s@%(domain)s' % addrs[0]})
                    for idx in range(1, len(addrs)):
                        ret.append({'mailman_' + iface:
                                    '%(local_part)s@%(domain)s' % addrs[idx]})
            except Errors.NotFoundError:
                pass
        return ret

    # COMMANDS

    #
    # mailman create_list <list-address> [admin,admin,admin]
    #
    default_mailman_commands['mailman_create_list'] = Command(
        ("mailman", "create_list"),
        EmailAddress(help_ref="mailing_list"),
        SimpleString(help_ref="mailing_admins", optional=True),
        YesNo(help_ref="yes_no_force", optional=True),
        fs=FormatSuggestion([("Mailman list '%s' created", ("listname", ))]),
        perm_filter="can_email_list_create")

    def mailman_create_list(self, operator, listname, admins=None, force="no"):
        """ Create Mailman list.

        Create the e-mail addresses 'listname' needs to be a Mailman list.
        Also adds a request to create the list on the Mailman server.

        """
        self._create_mailman_list(operator, listname, force)
        lp, dom = self._split_email_address(listname)
        ed = self._get_email_domain_from_str(dom)
        ea = Email.EmailAddress(self.db)
        op = operator.get_entity_id()
        if admins:
            br = BofhdRequests(self.db, self.const)
            ea.clear()
            ea.find_by_local_part_and_domain(lp, ed.entity_id)
            list_id = ea.entity_id
            admin_list = []
            for addr in admins.split(","):
                if addr.count('@') == 0:
                    # TODO: Not good, this is in use by UIA
                    admin_list.append(addr + "@ulrik.uio.no")
                else:
                    admin_list.append(addr)
            ea.clear()
            try:
                ea.find_by_address(admin_list[0])
            except Errors.NotFoundError:
                raise CerebrumError("%s: unknown address" % admin_list[0])
            req = br.add_request(op, br.now, self.const.bofh_mailman_create,
                                 list_id, ea.entity_id, None)
            for addr in admin_list[1:]:
                ea.clear()
                try:
                    ea.find_by_address(addr)
                except Errors.NotFoundError:
                    raise CerebrumError("%s: unknown address" % addr)
                br.add_request(op, br.now, self.const.bofh_mailman_add_admin,
                               list_id, ea.entity_id, str(req))
        return {'listname': listname, }

    #
    # mailman remove_list <list-address>
    #
    default_mailman_commands['mailman_remove_list'] = Command(
        ("mailman", "remove_list"),
        EmailAddress(help_ref="mailing_list"),
        fs=FormatSuggestion([("List '%s' deleted", ('listname', ))]),
        perm_filter="can_email_list_delete")

    def mailman_remove_list(self, operator, listname):
        """ Delete mailman email list. """
        ea = self._get_email_address_from_str(listname)
        #et, ea = self._get_email_target_and_address(listname)
        self.ba.can_email_list_delete(operator.get_entity_id(), ea)
        return self._delete_mailman_list(operator.get_entity_id(), listname, ea)
        return {'listname': listname, }

    #
    # mailman create_list_alias <list-address> <new-alias>
    #
    default_mailman_commands['mailman_create_list_alias'] = Command(
        ("mailman", "create_list_alias"),
        EmailAddress(help_ref="mailing_list_exist"),
        EmailAddress(help_ref="mailing_list"),
        fs=FormatSuggestion([("List alias '%s' created", ('alias', ))]),
        perm_filter="can_email_list_create")

    def mailman_create_list_alias(self, operator, listname, address):
        """ Create a secondary name for an existing Mailman list. """
        self._create_mailman_list_alias(operator, listname, address,)
        # Failure results in CerebrumError
        return {'target': listname, 'alias': address, }

    #
    # mailman remove_list_alias <alias>
    #
    default_mailman_commands['mailman_remove_list_alias'] = Command(
        ('mailman', 'remove_list_alias'),
        EmailAddress(help_ref='mailing_list_alias'),
        fs=FormatSuggestion([("List alias '%s' removed", ('alias', ))]),
        perm_filter='can_email_list_create')

    def mailman_remove_list_alias(self, operator, alias):
        """ Remove existing secondary name for a Mailman list. """
        lp, dom = self._split_email_address(alias, with_checks=False)
        ed = self._get_email_domain_from_str(dom)
        self.ba.can_email_list_create(operator.get_entity_id(), ed)

        # Remove all interface addresses for the alias
        ea = Email.EmailAddress(self.db)
        et = Email.EmailTarget(self.db)
        for iface in ('post', 'mailcmd', 'mailowner'):
            for addr_format in self._interface2addrs[iface]:
                addr = addr_format % {'local_part': lp,
                                      'domain': dom}
                try:
                    ea.clear()
                    ea.find_by_address(addr)
                except Errors.NotFoundError:
                    raise CerebrumError("No such address %s" % addr)
                try:
                    et.clear()
                    et.find(ea.email_addr_target_id)
                except Errors.NotFoundError:
                    raise CerebrumError("Could not find e-mail target for %s" %
                                        addr)
                self._remove_email_address(et, addr)
        # No errors = success
        return {'alias': alias}
