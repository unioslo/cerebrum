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
""" RT Email mixin and utils for BofhdExtensions.

NOTE: This mixin is (for now) untested. 

We probably need the BofhdEmailMixin in our MRO as well.

"""
import cereconf
import cerebrum_path

import re

from Cerebrum import Errors
from Cerebrum.modules import Email

from Cerebrum.modules.bofhd.bofhd_email import BofhdEmailMixinBase
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.bofhd.cmd_param import Command, FormatSuggestion, \
    Parameter, EmailAddress, YesNo


class RTQueue(Parameter):

    """ Parameter class for RT queues. """

    _type = 'rtQueue'
    _help_ref = 'rt_queue'


class BofhdEmailRTMixin(BofhdEmailMixinBase):

    """ RT related functions. """

    # TODO: RT ise only in use at UiO. This class has not been tested.
    # TODO: We should probably assert that BofhdCommonBase abd BofhdEmailMixin
    #       is in the MRO. Nothing will work otherwise.

    default_email_rt_commands = {}

    #
    # RT settings
    #

    # Pipe function for RT
    _rt_pipe = '|%s --action %s --queue %s --url %s' % (
        '/local/bin/rt-mailgate', '%(action)s', '%(queue)s',
        'https://%(host)s/')

    # This assumes that the only RE meta character in _rt_pipe is the
    # leading pipe.
    _rt_patt = "^\\" + _rt_pipe % {'action': '(\S+)',
                                   'queue': '(\S+)',
                                   'host': '(\S+)'} + "$"

    #
    # Helper functions
    #

    def _resolve_rt_name(self, queuename):
        """Return queue and host of RT queue as tuple."""
        if queuename.count('@') == 0:
            # Use the default host
            return queuename, "rt.uio.no"
        elif queuename.count('@') > 1:
            raise CerebrumError("Invalid RT queue name: %s" % queuename)
        return queuename.split('@')

    def __get_all_related_rt_targets(self, address):
        """ Locate and return all ETs associated with the RT queue.

        Given any address associated with a RT queue, this method returns
        all the ETs associated with that RT queue. E.g.: 'foo@domain' will
        return 'foo@domain' and 'foo-comment@queuehost'

        If address (EA) is not associated with a RT queue, this method
        raises an exception. Otherwise a list of ET entity_ids is returned.

        @type address: basestring
        @param address:
          One of the mail addresses associated with a RT queue.

        @rtype: sequence (of ints)
        @return:
          A sequence with entity_ids of all ETs related to the RT queue that
          address is related to.

        """
        et = Email.EmailTarget(self.db)
        queue, host = self._get_rt_queue_and_host(address)
        targets = set([])
        for action in ("correspond", "comment"):
            alias = self._rt_pipe % {'action': action, 'queue': queue,
                                     'host': host, }
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

    def _get_rt_email_target(self, queue, host):
        """ Get EmailTarget for an RT queue. """
        et = Email.EmailTarget(self.db)
        try:
            et.find_by_alias(self._rt_pipe % {'action': "correspond",
                                              'queue': queue, 'host': host, })
        except Errors.NotFoundError:
            raise CerebrumError("Unknown RT queue %s on host %s" %
                                (queue, host))
        return et

    def _get_rt_queue_and_host(self, address):
        """ Get RT queue and host. """
        et, addr = self._get_email_target_and_address(address)

        try:
            m = re.match(self._rt_patt, et.get_alias())
            return m.group(2), m.group(3)
        except AttributeError:
            raise CerebrumError("Could not get queue and host for %s" %
                                address)

    #
    # email rt_create queue[@host] address [force]
    #
    default_email_rt_commands['email_rt_create'] = Command(
        ("email", "rt_create"),
        RTQueue(),
        EmailAddress(),
        YesNo(help_ref="yes_no_force", optional=True),
        perm_filter='can_rt_create')

    def email_rt_create(self, operator, queuename, addr, force="No"):
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
        cmd = self._rt_pipe % {'action': "correspond",
                               'queue': queue, 'host': host}
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
        cmd = self._rt_pipe % {'queue': queue, 'action': "comment",
                               'host': host}
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
        self._register_spam_settings(addr, self.const.email_target_RT)
        self._register_filter_settings(addr, self.const.email_target_RT)
        return msg

    #
    # email rt_delete queue[@host]
    #
    default_email_rt_commands['email_rt_delete'] = Command(
        ("email", "rt_delete"),
        EmailAddress(),
        fs=FormatSuggestion([("Deleted address: %s", ("address", ))]),
        perm_filter='can_rt_delete')

    def email_rt_delete(self, operator, queuename):
        """ Delete RT list. """
        queue, host = self._resolve_rt_name(queuename)
        rt_dom = self._get_email_domain_from_str(host)
        self.ba.can_rt_delete(operator.get_entity_id(), domain=rt_dom)
        et = Email.EmailTarget(self.db)
        ea = Email.EmailAddress(self.db)
        epat = Email.EmailPrimaryAddressTarget(self.db)
        result = []

        for target_id in self.__get_all_related_rt_targets(queuename):
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
    # email rt_add_address queue[@host] address
    #
    default_email_rt_commands['email_rt_add_address'] = Command(
        ('email', 'rt_add_address'),
        RTQueue(),
        EmailAddress(),
        perm_filter='can_rt_address_add')

    def email_rt_add_address(self, operator, queuename, address):
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
    # email rt_remove_address queue address
    #
    default_email_rt_commands['email_rt_remove_address'] = Command(
        ('email', 'rt_remove_address'),
        RTQueue(),
        EmailAddress(),
        perm_filter='can_email_address_delete')

    def email_rt_remove_address(self, operator, queuename, address):
        """ RT remove address. """

        queue, host = self._resolve_rt_name(queuename)
        rt_dom = self._get_email_domain_from_str(host)
        self.ba.can_rt_address_remove(operator.get_entity_id(), domain=rt_dom)
        et = self._get_rt_email_target(queue, host)
        return self._remove_email_address(et, address)

    #
    # email rt_primary_address address
    #
    default_email_rt_commands['email_rt_primary_address'] = Command(
        ("email", "rt_primary_address"),
        RTQueue(),
        EmailAddress(),
        fs=FormatSuggestion([("New primary address: '%s'", ("address", ))]),
        perm_filter="can_rt_address_add")

    def email_rt_primary_address(self, operator, queuename, address):
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
        return self._set_email_primary_address(et, ea, address)

