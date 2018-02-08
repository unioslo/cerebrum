# -*- coding: utf-8 -*-

# Copyright 2002-2018 University of Oslo, Norway
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

import time
import re
import imaplib
import ssl
import pickle
import socket

import six

from mx import DateTime
from flanker.addresslib import address as email_validator

import cereconf
from Cerebrum import database
from Cerebrum import Entity
from Cerebrum import Errors
from Cerebrum import Metainfo
from Cerebrum.Constants import _LanguageCode
from Cerebrum import Utils
from Cerebrum.utils.email import sendmail, mail_template
from Cerebrum.modules import Email
from Cerebrum.modules.pwcheck.checker import (check_password,
                                              PasswordNotGoodEnough,
                                              RigidPasswordNotGoodEnough,
                                              PhrasePasswordNotGoodEnough)
from Cerebrum.modules.pwcheck.history import PasswordHistory
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.bofhd_user_create import BofhdUserCreateMethod
from Cerebrum.modules.bofhd.cmd_param import *
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.modules.bofhd.bofhd_utils import copy_func
from Cerebrum.modules.bofhd.auth import (BofhdAuthOpSet,
                                         AuthConstants,
                                         BofhdAuthOpTarget,
                                         BofhdAuthRole)
from Cerebrum.modules.bofhd.help import Help
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.bofhd import bofhd_core_help
from Cerebrum.modules.no.uio.bofhd_auth import BofhdAuth
from Cerebrum.modules.no.uio.access_FS import FS
from Cerebrum.modules.no.uio.DiskQuota import DiskQuota
from Cerebrum.modules.dns.Subnet import Subnet


# TBD: It would probably be cleaner if our time formats were specified
# in a non-Java-SimpleDateTime-specific way.
def format_day(field):
    fmt = "yyyy-MM-dd"                  # 10 characters wide
    return ":".join((field, "date", fmt))


def format_time(field):
    fmt = "yyyy-MM-dd HH:mm"            # 16 characters wide
    return ':'.join((field, "date", fmt))


def date_to_string(date):
    """Takes a DateTime-object and formats a standard ISO-datestring
    from it.

    Custom-made for our purposes, since the standard XMLRPC-libraries
    restrict formatting to years after 1899, and we see years prior to
    that.

    """
    if not date:
        return "<not set>"

    return "%04i-%02i-%02i" % (date.year, date.month, date.day)


class TimeoutException(Exception):
    pass


class ConnectException(Exception):
    pass


class RTQueue(Parameter):
    _type = 'rtQueue'
    _help_ref = 'rt_queue'


# TODO: move more UiO cruft from bofhd/auth.py in here
class UiOAuth(BofhdAuth):
    """Authorisation.  UiO specific operations and business logic."""

    def can_rt_create(self, operator, domain=None, query_run_any=False):
        if self.is_superuser(operator, query_run_any):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(operator,
                                                      self.const.auth_rt_create)
        return self._query_maildomain_permissions(operator,
                                                  self.const.auth_rt_create,
                                                  domain, None)

    can_rt_delete = can_rt_create

    def can_rt_address_add(self, operator, domain=None, query_run_any=False):
        if self.is_superuser(operator, query_run_any):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_rt_addr_add)
        return self._query_maildomain_permissions(operator,
                                                  self.const.auth_rt_addr_add,
                                                  domain, None)

    can_rt_address_remove = can_rt_address_add


@copy_func(
    BofhdUserCreateMethod,
    methods=['_user_create_set_account_type', '_user_create_basic',
             '_user_password']
)
class BofhdExtension(BofhdCommonMethods):
    """All CallableFuncs take user as first arg, and are responsible
    for checking necessary permissions"""

    all_commands = {}
    hidden_commands = {}
    omit_parent_commands = {'user_create'}
    parent_commands = True

    authz = UiOAuth
    external_id_mappings = {}

    # This little class is used to store connections to the LDAP servers, and
    # the LDAP modules needed. The reason for doing things like this instead
    # instead of importing the LDAP module for the entire bofhd_uio_cmds,
    # are amongst others:
    # 1. bofhd_uio_cmds is partially used at other institutions in some form,
    #    they might not have any need for, or wish, to install the LDAP module.
    # 2. If we import the module on a per-function basis, we'll loose options
    #    set in the module.
    # 3. It looks better to define a little class, than a dict of dicts, in
    #    order to organize the variables in a somewhat sane way.
    #
    # We need to connect to LDAP, in order to populate entries with the
    # 'mailPause' attribute. This attribute will be heavily used by the
    # postmasters, as they convert to murder. When we populate entries
    # with the 'mailPause' attribute directly, the postmasters will experience
    # a 3x reduction in waiting time.
    #
    # This stuff is used in _ldap_init(), _ldap_modify() and _ldap_delete(),
    # which are called from email_pause().

    class LDAPStruct:
        ldap = None
        ldapobject = None
        connection = None

        def invalidate_connection(self):
            self.connection = None

    _ldap_connect = LDAPStruct()

    def __init__(self, *args, **kwargs):
        super(BofhdExtension, self).__init__(*args, **kwargs)
        self.external_id_mappings['fnr'] = self.const.externalid_fodselsnr
        # exchange-relatert-jazz
        # currently valid language variants for UiO-Cerebrum
        # although these codes are used for distribution groups
        # they are not directly related to them. maybe these should be
        # put in a cereconf-variable somewhere in the future? (Jazz, 2013-12)
        self.language_codes = ['nb', 'nn', 'en']

        # TODO: Wait until needed / fix on import?
        self.fixup_imaplib()

    @property
    def name_codes(self):
        # TODO: Do we really need this cache?
        try:
            return self.__name_codes
        except AttributeError:
            self.__name_codes = dict()
            person = Utils.Factory.get('Person')(self.db)
            for t in person.list_person_name_codes():
                self.__name_codes[int(t['code'])] = t['description']
            return self.__name_codes

    @property
    def change_type2details(self):
        # TODO: Do we really need this cache?
        try:
            return self.__ct2details
        except AttributeError:
            self.__ct2details = dict()
            for r in self.db.get_changetypes():
                self.__ct2details[int(r['change_type_id'])] = [
                    r['category'], r['type'], r['msg_string']]
            return self.__ct2details

    @property
    def num2op_set_name(self):
        # TODO: Do we really need this cache?
        try:
            return self.__num2opset
        except AttributeError:
            self.__num2opset = dict()
            aos = BofhdAuthOpSet(self.db)
            for r in aos.list():
                self.__num2opset[int(r['op_set_id'])] = r['name']
            return self.__num2opset

    def fixup_imaplib(self):
        def nonblocking_open(self, host=None, port=None):
            import socket
            # Perhaps using **kwargs is cleaner, but this works, too.
            if host is None:
                if not hasattr(self, "host"):
                    self.host = ''
            else:
                self.host = host
            if port is None:
                if not hasattr(self, "port"):
                    self.port = 143
            else:
                self.port = port

            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setblocking(False)
            err = self.sock.connect_ex((self.host, self.port))
            # I don't think connect_ex() can ever return success immediately,
            # it has to wait for a roundtrip.
            assert err
            if err != errno.EINPROGRESS:
                raise ConnectException(errno.errorcode[err])

            ignore, wset, ignore = select.select([], [self.sock], [], 1.0)
            if not wset:
                raise TimeoutException
            err = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if err == 0:
                self.sock.setblocking(True)
                self.file = self.sock.makefile('rb')
                return
            raise ConnectException(errno.errorcode[err])
        setattr(imaplib.IMAP4, 'open', nonblocking_open)

    @classmethod
    def get_help_strings(cls):
        return bofhd_core_help.get_help_strings()

    @classmethod
    def list_commands(cls, attr):
        u""" Fetch all commands in all superclasses. """
        commands = super(BofhdExtension, cls).list_commands(attr)
        if attr == 'all_commands':
            from Cerebrum.modules.dns.bofhd_dns_cmds import BofhdExtension as\
                Dns
            # FIXME: This hack is needed until we have a proper architecture
            # for bofhd which allows mixins.
            # We know that the format suggestion in dns has no hdr, so we only
            # copy str_vars.
            commands['host_info'] = Command(
                ("host", "info"),
                SimpleString(help_ref='string_host'),
                YesNo(optional=True, help_ref='show_policy'),
                fs=FormatSuggestion(Dns.all_commands['host_info']
                                    .get_fs()['str_vars'] +
                                    [("Hostname:              %s\n"
                                      "Description:           %s",
                                      ("hostname", "desc")),
                                     ("Default disk quota:    %d MiB",
                                      ("def_disk_quota",))]))
        return commands

    def _ldap_unbind(self):
        ld = self._ldap_connect.connection
        if ld:
            try:
                ld.unbind_s()
            except self._ldap_connect.ldap.LDAPError:
                pass
            self._ldap_connect.connection = None

    def _ldap_init(self):
        """This helper function connects and binds to LDAP-servers
        specified in cereconf."""
        if self._ldap_connect.connection is None:
            # We import here, as not everyone got LDAP.
            try:
                import ldap
                from ldap import ldapobject
            except ImportError:
                raise CerebrumError('ldap module could not be imported')

            # Store the LDAP module in a LDAPStruct, this way we'll keep the
            # options between functions. These options are lost if we import
            # the module for each function that uses it.
            self._ldap_connect.ldap = ldap
            self._ldap_connect.ldapobject = ldapobject
            self._ldap_connect.__del__ = self._ldap_unbind

            # Read the password and create the binddn
            passwd = self.db._read_password(cereconf.LDAP_SYSTEM,
                                            cereconf.LDAP_UPDATE_USER)
            ld_binddn = cereconf.LDAP_BIND_DN % cereconf.LDAP_UPDATE_USER

            # Avoid indefinite blocking
            self._ldap_connect.ldap.set_option(ldap.OPT_NETWORK_TIMEOUT, 4)

            # Require TLS cert. This option should be set in
            # /etc/openldap/ldap.conf along with the cert itself,
            # but let us make sure.
            self._ldap_connect.ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT,
                                               ldap.OPT_X_TLS_DEMAND)

            server = cereconf.LDAP_MASTER

            con = ldapobject.ReconnectLDAPObject(
                "ldaps://%s/" % server,
                retry_max=cereconf.LDAP_RETRY_MAX,
                retry_delay=cereconf.LDAP_RETRY_DELAY)

            try:
                con.simple_bind_s(who=ld_binddn, cred=passwd)
            except ldap.CONFIDENTIALITY_REQUIRED:
                self.logger.warn('TLS could not be established to %s', server)
                raise CerebrumError('TLS could not be established to {}'.format(
                    server))
            except ldap.INVALID_CREDENTIALS:
                rep = ('Connection aborted to {}, invalid credentials'
                       .format(server))
                self.logger.error(rep)
                raise CerebrumError(rep)
            except ldap.SERVER_DOWN:
                con = None

            # And we store the connection in our LDAPStruct
            self._ldap_connect.connection = con

    def _ldap_modify(self, dn, attribute, *values):
        """This function modifies an LDAP entry defined by 'id' to contain an
        attribute with the given values, or to delete it if no values."""

        tries = 0
        while tries < 2:
            if not self._ldap_connect.connection:
                self._ldap_init()
                tries = 1
            tries += 1
            ld = self._ldap_connect.connection
            if not ld:
                break

            # We'll set the trait on one server, and it should spread
            # to the other servers in less than two miuntes.  This
            # eliminates race conditions when servers go up and down..
            try:
                ld.modify_s(dn, [(self._ldap_connect.ldap.MOD_REPLACE,
                            attribute, values or None)])
                return True

            except self._ldap_connect.ldap.NO_SUCH_OBJECT:
                # This error occurs if the mail-target has been created
                # and mailPause is being set before the newest LDIF has
                # been handed over to LDAP.
                break
            except self._ldap_connect.ldap.SERVER_DOWN:
                # We invalidate the connection (set it to None).
                self._ldap_connect.invalidate_connection()

        return False

    #
    # access commands
    #

    # access disk <path>
    all_commands['access_disk'] = Command(
        ('access', 'disk'),
        DiskId(),
        fs=FormatSuggestion("%-16s %-9s %s",
                            ("opset", "type", "name"),
                            hdr="%-16s %-9s %s" %
                            ("Operation set", "Type", "Name")))
    def access_disk(self, operator, path):
        disk = self._get_disk(path)[0]
        result = []
        host = Utils.Factory.get('Host')(self.db)
        try:
            host.find(disk.host_id)
            for r in self._list_access("host", host.name, empty_result=[]):
                if r['attr'] == '' or re.search("/%s$" % r['attr'], path):
                    result.append(r)
        except Errors.NotFoundError:
            pass
        result.extend(self._list_access("disk", path, empty_result=[]))
        return result or "None"

    # access group <group>
    all_commands['access_group'] = Command(
        ('access', 'group'),
        GroupName(),
        fs=FormatSuggestion("%-16s %-9s %s", ("opset", "type", "name"),
                            hdr="%-16s %-9s %s" %
                            ("Operation set", "Type", "Name")))
    def access_group(self, operator, group):
        return self._list_access("group", group)

    # access host <hostname>
    all_commands['access_host'] = Command(
        ('access', 'host'),
        SimpleString(help_ref="string_host"),
        fs=FormatSuggestion("%-16s %-16s %-9s %s",
                            ("opset", "attr", "type", "name"),
                            hdr="%-16s %-16s %-9s %s" %
                            ("Operation set", "Pattern", "Type", "Name")))
    def access_host(self, operator, host):
        return self._list_access("host", host)

    # access maildom <maildom>
    all_commands['access_maildom'] = Command(
        ('access', 'maildom'),
        SimpleString(help_ref="email_domain"),
        fs=FormatSuggestion("%-16s %-9s %s",
                            ("opset", "type", "name"),
                            hdr="%-16s %-9s %s" %
                            ("Operation set", "Type", "Name")))
    def access_maildom(self, operator, maildom):
        return self._list_access("maildom", maildom)

    # access ou <ou>
    all_commands['access_ou'] = Command(
        ('access', 'ou'),
        OU(),
        fs=FormatSuggestion("%-16s %-16s %-9s %s",
                            ("opset", "attr", "type", "name"),
                            hdr="%-16s %-16s %-9s %s" %
                            ("Operation set", "Affiliation", "Type", "Name")))
    def access_ou(self, operator, ou):
        return self._list_access("ou", ou)

    # access user <account>
    all_commands['access_user'] = Command(
        ('access', 'user'),
        AccountName(),
        fs=FormatSuggestion("%-14s %-5s %-20s %-7s %-9s %s",
                            ("opset", "target_type", "target", "attr",
                             "type", "name"),
                            hdr="%-14s %-5s %-20s %-7s %-9s %s" %
                            ("Operation set", "TType", "Target", "Attr",
                             "Type", "Name")))
    def access_user(self, operator, user):
        """This is more tricky than the others, we want to show anyone
        with access, through OU, host or disk.  (not global_XXX,
        though.)

        Note that there is no auth-type 'account', so you can't be
        granted direct access to a specific user."""

        acc = self._get_account(user)
        # Make lists of the disks and hosts associated with the user
        disks = {}
        hosts = {}
        disk = Utils.Factory.get("Disk")(self.db)
        for r in acc.get_homes():
            # Disk for archived users may not exist anymore
            try:
                disk_id = int(r['disk_id'])
            except TypeError:
                continue
            if disk_id not in disks:
                disk.clear()
                disk.find(disk_id)
                disks[disk_id] = disk.path
                if disk.host_id is not None:
                    basename = disk.path.split("/")[-1]
                    host_id = int(disk.host_id)
                    if host_id not in hosts:
                        hosts[host_id] = []
                    hosts[host_id].append(basename)
        # Look through disks
        ret = []
        for d in disks.keys():
            for entry in self._list_access("disk", d, empty_result=[]):
                entry['target_type'] = "disk"
                entry['target'] = disks[d]
                ret.append(entry)
        # Look through hosts:
        for h in hosts.keys():
            for candidate in self._list_access("host", h, empty_result=[]):
                candidate['target_type'] = "host"
                candidate['target'] = self._get_host(h).name
                if candidate['attr'] == "":
                    ret.append(candidate)
                    continue
                for dir in hosts[h]:
                    if re.match(candidate['attr'], dir):
                        ret.append(candidate)
                        break
        # TODO: check user's ou(s)
        ret.sort(lambda x, y: (cmp(x['opset'].lower(), y['opset'].lower()) or
                               cmp(x['name'], y['name'])))
        return ret

    # access global_group
    all_commands['access_global_group'] = Command(
        ('access', 'global_group'),
        fs=FormatSuggestion("%-16s %-9s %s", ("opset", "type", "name"),
                            hdr="%-16s %-9s %s" %
                            ("Operation set", "Type", "Name")))
    def access_global_group(self, operator):
        return self._list_access("global_group")

    # access global_host
    all_commands['access_global_host'] = Command(
        ('access', 'global_host'),
        fs=FormatSuggestion("%-16s %-9s %s",
                            ("opset", "type", "name"),
                            hdr="%-16s %-9s %s" %
                            ("Operation set", "Type", "Name")))
    def access_global_host(self, operator):
        return self._list_access("global_host")

    # access global_maildom
    all_commands['access_global_maildom'] = Command(
        ('access', 'global_maildom'),
        fs=FormatSuggestion("%-16s %-9s %s",
                            ("opset", "type", "name"),
                            hdr="%-16s %-9s %s" %
                            ("Operation set", "Type", "Name")))
    def access_global_maildom(self, operator):
        return self._list_access("global_maildom")

    # access global_ou
    all_commands['access_global_ou'] = Command(
        ('access', 'global_ou'),
        fs=FormatSuggestion("%-16s %-16s %-9s %s",
                            ("opset", "attr", "type", "name"),
                            hdr="%-16s %-16s %-9s %s" %
                            ("Operation set", "Affiliation", "Type", "Name")))
    def access_global_ou(self, operator):
        return self._list_access("global_ou")

    # access global_dns
    all_commands['access_global_dns'] = Command(
        ('access', 'global_dns'),
        fs=FormatSuggestion("%-16s %-16s %-9s %s",
                            ("opset", "attr", "type", "name"),
                            hdr="%-16s %-16s %-9s %s" %
                            ("Operation set", "Affiliation", "Type", "Name")))
    def access_global_dns(self, operator):
        return self._list_access("global_dns")

    def _list_access(self, target_type, target_name=None, decode_attr=str,
                     empty_result="None"):
        target_id, target_type, target_auth = self._get_access_id(target_type,
                                                                  target_name)
        ret = []
        ar = BofhdAuthRole(self.db)
        aos = BofhdAuthOpSet(self.db)
        for r in self._get_auth_op_target(target_id, target_type,
                                          any_attr=True):
            if r['attr'] is None:
                attr = ""
            else:
                attr = decode_attr(r['attr'])
            for r2 in ar.list(op_target_id=r['op_target_id']):
                aos.clear()
                aos.find(r2['op_set_id'])
                ety = self._get_entity(ident=r2['entity_id'])
                ret.append({'opset': aos.name,
                            'attr': attr,
                            'type': str(self.const.EntityType(ety.entity_type)),
                            'name': self._get_name_from_object(ety)})
        ret.sort(lambda a, b: (cmp(a['opset'], b['opset']) or
                               cmp(a['name'], b['name'])))
        return ret or empty_result

    # access grant <opset name> <who> <type> <on what> [<attr>]
    all_commands['access_grant'] = Command(
        ('access', 'grant'),
        OpSet(),
        GroupName(help_ref="id:target:group"),
        EntityType(default='group', help_ref="auth_entity_type"),
        SimpleString(help_ref="auth_target_entity"),
        SimpleString(optional=True, help_ref="auth_attribute"),
        perm_filter='can_grant_access')
    def access_grant(self, operator, opset, group, entity_type, target_name,
                     attr=None):
        return self._manipulate_access(self._grant_auth, operator, opset,
                                       group, entity_type, target_name, attr)

    # access revoke <opset name> <who> <type> <on what> [<attr>]
    all_commands['access_revoke'] = Command(
        ('access', 'revoke'),
        OpSet(),
        GroupName(help_ref="id:target:group"),
        EntityType(default='group', help_ref="auth_entity_type"),
        SimpleString(help_ref="auth_target_entity"),
        SimpleString(optional=True, help_ref="auth_attribute"),
        perm_filter='can_grant_access')
    def access_revoke(self, operator, opset, group, entity_type, target_name,
                      attr=None):
        return self._manipulate_access(self._revoke_auth, operator, opset,
                                       group, entity_type, target_name, attr)

    def _manipulate_access(self, change_func, operator, opset, group,
                           entity_type, target_name, attr):
        """This function does no validation of types itself.  It uses
        _get_access_id() to get a (target_type, entity_id) suitable for
        insertion in auth_op_target.  Additional checking for validity
        is done by _validate_access().

        Those helper functions look for a function matching the
        target_type, and call it.  There should be one
        _get_access_id_XXX and one _validate_access_XXX for each known
        target_type.

        """
        opset = self._get_opset(opset)
        gr = self.util.get_target(group, default_lookup="group",
                                  restrict_to=['Account', 'Group'])
        target_id, target_type, target_auth = self._get_access_id(
            entity_type, target_name)
        operator_id = operator.get_entity_id()
        if target_auth is None and not self.ba.is_superuser(operator_id):
            raise PermissionDenied("Currently limited to superusers")
        else:
            self.ba.can_grant_access(operator_id, target_auth,
                                     target_type, target_id, opset)
        self._validate_access(entity_type, opset, attr)
        return change_func(gr.entity_id, opset, target_id, target_type, attr,
                           group, target_name)

    def _get_access_id(self, target_type, target_name):
        """Get required data for granting access to an operation target.

        :param str target_type: The type of

        :rtype: tuple
        :returns:
            A three element tuple with information about the operation target:

              1. The entity_id of the target entity (int)
              2. The target type (str)
              3. The `intval` of the operation constant for granting access to
                 the given target entity.

        """
        func_name = "_get_access_id_%s" % target_type
        if func_name not in dir(self):
            raise CerebrumError("Unknown id type {}".format(target_type))
        return self.__getattribute__(func_name)(target_name)

    def _validate_access(self, target_type, opset, attr):
        func_name = "_validate_access_%s" % target_type
        if func_name not in dir(self):
            raise CerebrumError("Unknown type {}".format(target_type))
        return self.__getattribute__(func_name)(opset, attr)

    def _get_access_id_disk(self, target_name):
        return (self._get_disk(target_name)[1],
                self.const.auth_target_type_disk,
                self.const.auth_grant_disk)
    def _validate_access_disk(self, opset, attr):
        # TODO: check if the opset is relevant for a disk
        if attr is not None:
            raise CerebrumError("Can't specify attribute for disk access")

    def _get_access_id_group(self, target_name):
        target = self._get_group(target_name)
        return (target.entity_id, self.const.auth_target_type_group,
                self.const.auth_grant_group)
    def _validate_access_group(self, opset, attr):
        # TODO: check if the opset is relevant for a group
        if attr is not None:
            raise CerebrumError("Can't specify attribute for group access")

    # These three should *really* not be here, but due to this being the
    # place that "access grant" & friends are defined, this is where
    # the dns-derived functions need to be too
    def _get_access_id_dns(self, target):
        sub = Subnet(self.db)
        sub.find(target.split('/')[0])
        return (sub.entity_id,
                self.const.auth_target_type_dns,
                self.const.auth_grant_dns)
    def _validate_access_dns(self, opset, attr):
        # TODO: check if the opset is relevant for a dns-target
        if attr is not None:
            raise CerebrumError("Can't specify attribute for dns access")

    def _get_access_id_global_dns(self, target_name):
        if target_name:
            raise CerebrumError("You can't specify an address")
        return None, self.const.auth_target_type_global_dns, None
    def _validate_access_global_dns(self, opset, attr):
        if attr:
            raise CerebrumError("You can't specify a pattern with global_dns.")

    # access dns <dns-target>
    all_commands['access_dns'] = Command(
        ('access', 'dns'), SimpleString(),
        fs=FormatSuggestion("%-16s %-9s %-9s %s",
                            ("opset", "type", "level", "name"),
                            hdr="%-16s %-9s %-9s %s" %
                            ("Operation set", "Type", "Level", "Name")))
    def access_dns(self, operator, dns_target):
        ret = []
        if '/' in dns_target:
            # Asking for rights on subnet; IP not of interest
            for accessor in self._list_access("dns", dns_target,
                                              empty_result=[]):
                accessor["level"] = "Subnet"
                ret.append(accessor)
        else:
            # Asking for rights on IP; need to provide info about
            # rights on the IP's subnet too
            for accessor in self._list_access("dns", dns_target + '/',
                                              empty_result=[]):
                accessor["level"] = "Subnet"
                ret.append(accessor)
            for accessor in self._list_access("dns", dns_target,
                                              empty_result=[]):
                accessor["level"] = "IP"
                ret.append(accessor)
        return ret

    def _get_access_id_global_group(self, group):
        if group is not None and group != "":
            raise CerebrumError("Cannot set domain for global access")
        return None, self.const.auth_target_type_global_group, None

    def _validate_access_global_group(self, opset, attr):
        if attr is not None:
            raise CerebrumError("Can't specify attribute for global group")

    def _get_access_id_host(self, target_name):
        target = self._get_host(target_name)
        return (target.entity_id, self.const.auth_target_type_host,
                self.const.auth_grant_host)
    def _validate_access_host(self, opset, attr):
        if attr is not None:
            if attr.count('/'):
                raise CerebrumError("The disk pattern should only contain "
                                    "the last component of the path.")
            try:
                re.compile(attr)
            except re.error, e:
                raise CerebrumError("Syntax error in regexp: {}".format(e))

    def _get_access_id_global_host(self, target_name):
        if target_name is not None and target_name != "":
            raise CerebrumError("You can't specify a hostname")
        return None, self.const.auth_target_type_global_host, None
    def _validate_access_global_host(self, opset, attr):
        if attr is not None:
            raise CerebrumError("You can't specify a pattern with global_host.")

    def _get_access_id_maildom(self, dom):
        ed = self._get_email_domain(dom)
        return (ed.entity_id, self.const.auth_target_type_maildomain,
                self.const.auth_grant_maildomain)
    def _validate_access_maildom(self, opset, attr):
        if attr is not None:
            raise CerebrumError("No attribute with maildom.")

    def _get_access_id_global_maildom(self, dom):
        if dom is not None and dom != '':
            raise CerebrumError("Cannot set domain for global access")
        return None, self.const.auth_target_type_global_maildomain, None
    def _validate_access_global_maildom(self, opset, attr):
        if attr is not None:
            raise CerebrumError("No attribute with global maildom.")

    def _get_access_id_ou(self, ou):
        ou = self._get_ou(stedkode=ou)
        return (ou.entity_id, self.const.auth_target_type_ou,
                self.const.auth_grant_ou)
    def _validate_access_ou(self, opset, attr):
        if attr is not None:
            try:
                int(self.const.PersonAffiliation(attr))
            except Errors.NotFoundError:
                raise CerebrumError("Unknown affiliation '{}'".format(attr))

    def _get_access_id_global_ou(self, ou):
        if ou is not None and ou != '':
            raise CerebrumError("Cannot set OU for global access")
        return None, self.const.auth_target_type_global_ou, None
    def _validate_access_global_ou(self, opset, attr):
        if not attr:
            # This is a policy decision, and should probably be
            # elsewhere.
            raise CerebrumError("Must specify affiliation for global ou access")
        try:
            int(self.const.PersonAffiliation(attr))
        except Errors.NotFoundError:
            raise CerebrumError("Unknown affiliation: %s" % attr)

    # access list_opsets
    all_commands['access_list_opsets'] = Command(
        ('access', 'list_opsets'),
        fs=FormatSuggestion("%s", ("opset",),
                            hdr="Operation set"))
    def access_list_opsets(self, operator):
        baos = BofhdAuthOpSet(self.db)
        ret = []
        for r in baos.list():
            ret.append({'opset': r['name']})
        ret.sort(lambda x, y: cmp(x['opset'].lower(), y['opset'].lower()))
        return ret

    # access list_alterable [group/maildom/host/disk] [username]
    hidden_commands['access_list_alterable'] = Command(
        ('access', 'list_alterable'),
        SimpleString(optional=True),
        AccountName(optional=True),
        fs=FormatSuggestion("%10d %15s     %s",
                            ("entity_id", "entity_type", "entity_name")))
    def access_list_alterable(self, operator, target_type='group',
                              access_holder=None):
        """List entities that access_holder can moderate."""

        if access_holder is None:
            account_id = operator.get_entity_id()
        else:
            account = self._get_account(access_holder, actype="PosixUser")
            account_id = account.entity_id

        if not (account_id == operator.get_entity_id() or
                self.ba.is_superuser(operator.get_entity_id())):
            raise PermissionDenied("You do not have permission for this"
                                   " operation")

        result = list()
        matches = self.ba.list_alterable_entities(account_id, target_type)
        if len(matches) > cereconf.BOFHD_MAX_MATCHES_ACCESS:
            raise CerebrumError("More than {:d} ({:d}) matches. Refusing to "
                                "return result".format(
                                    cereconf.BOFHD_MAX_MATCHES_ACCESS,
                                    len(matches)))
        for row in matches:
            try:
                entity = self._get_entity(ident=row["entity_id"])
            except Errors.NotFoundError:
                self.logger.warn(
                    "Non-existent entity (%s) referenced from auth_op_target",
                    row["entity_id"])
                continue
            etype = str(self.const.EntityType(entity.entity_type))
            ename = self._get_entity_name(entity.entity_id, entity.entity_type)
            tmp = {"entity_id": row["entity_id"],
                   "entity_type": etype,
                   "entity_name": ename}
            if entity.entity_type == self.const.entity_group:
                tmp["description"] = entity.description

            result.append(tmp)
        return result
    # end access_list_alterable

    # access show_opset <opset name>
    all_commands['access_show_opset'] = Command(
        ('access', 'show_opset'),
        OpSet(),
        fs=FormatSuggestion("%-16s %-16s %s",
                            ("op", "attr", "desc"),
                            hdr="%-16s %-16s %s" %
                            ("Operation", "Attribute", "Description")))
    def access_show_opset(self, operator, opset=None):
        baos = BofhdAuthOpSet(self.db)
        try:
            baos.find_by_name(opset)
        except Errors.NotFoundError:
            raise CerebrumError("Unknown operation set: '{}'".format(opset))
        ret = []
        for r in baos.list_operations():
            entry = {'op': str(self.const.AuthRoleOp(r['op_code'])),
                     'desc': self.const.AuthRoleOp(r['op_code']).description}
            attrs = []
            for r2 in baos.list_operation_attrs(r['op_id']):
                attrs += [r2['attr']]
            if not attrs:
                attrs = [""]
            for a in attrs:
                entry_with_attr = entry.copy()
                entry_with_attr['attr'] = a
                ret += [entry_with_attr]
        ret.sort(lambda x, y: (cmp(x['op'], y['op']) or
                               cmp(x['attr'], y['attr'])))
        return ret

    # TODO
    #
    # To be able to manipulate all aspects of bofhd authentication, we
    # need a few more commands:
    #
    #   access create_opset <opset name>
    #   access create_op <opname> <desc>
    #   access delete_op <opname>
    #   access add_to_opset <opset> <op> [<attr>]
    #   access remove_from_opset <opset> <op> [<attr>]
    #
    # The opset could be implicitly deleted after the last op was
    # removed from it.

    # access list operator
    all_commands['access_list'] = Command(
        ('access', 'list'),
        SimpleString(help_ref='id:target:group'),
        SimpleString(help_ref='string_perm_target_type', optional=True),
        fs=FormatSuggestion("%-14s %-16s %-30s %-7s",
                            ("opset", "target_type", "target", "attr"),
                            hdr="%-14s %-16s %-30s %-7s" %
                            ("Operation set", "Target type", "Target",
                             "Attr")))
    def access_list(self, operator, owner, target_type=None):
        ar = BofhdAuthRole(self.db)
        aot = BofhdAuthOpTarget(self.db)
        aos = BofhdAuthOpSet(self.db)
        owner_id = self.util.get_target(owner, default_lookup="group",
                                        restrict_to=[]).entity_id
        ret = []
        for role in ar.list(owner_id):
            aos.clear()
            aos.find(role['op_set_id'])
            for r in aot.list(target_id=role['op_target_id']):
                if target_type is not None and r['target_type'] != target_type:
                    continue
                if r['entity_id'] is None:
                    target_name = "N/A"
                elif r['target_type'] == self.const.auth_target_type_maildomain:
                    # FIXME: EmailDomain is not an Entity.
                    ed = Email.EmailDomain(self.db)
                    try:
                        ed.find(r['entity_id'])
                    except (Errors.NotFoundError, ValueError):
                        self.logger.warn("Non-existing entity (e-mail domain) "
                                         "in auth_op_target {}:{:d}"
                                         .format(r['target_type'],
                                                 r['entity_id']))
                        continue
                    target_name = ed.email_domain_name
                elif r['target_type'] == self.const.auth_target_type_ou:
                    ou = self.OU_class(self.db)
                    try:
                        ou.find(r['entity_id'])
                    except (Errors.NotFoundError, ValueError):
                        self.logger.warn("Non-existing entity (ou) in "
                                         "auth_op_target %s:%d" %
                                         (r['target_type'], r['entity_id']))
                        continue
                    target_name = "%02d%02d%02d (%s)" % (ou.fakultet,
                                                         ou.institutt,
                                                         ou.avdeling,
                                                         ou.short_name)
                elif r['target_type'] == self.const.auth_target_type_dns:
                    s = Subnet(self.db)
                    # TODO: should Subnet.find() support ints as input?
                    try:
                        s.find('entity_id:%s' % r['entity_id'])
                    except (Errors.NotFoundError, ValueError):
                        self.logger.warn("Non-existing entity (subnet) in "
                                         "auth_op_target %s:%d" %
                                         (r['target_type'], r['entity_id']))
                        continue
                    target_name = "%s/%s" % (s.subnet_ip, s.subnet_mask)
                else:
                    try:
                        ety = self._get_entity(ident=r['entity_id'])
                        target_name = self._get_name_from_object(ety)
                    except (Errors.NotFoundError, ValueError):
                        self.logger.warn("Non-existing entity in "
                                         "auth_op_target %s:%d" %
                                         (r['target_type'], r['entity_id']))
                        continue
                ret.append({'opset': aos.name,
                            'target_type': r['target_type'],
                            'target': target_name,
                            'attr': r['attr'] or ""})
        ret.sort(lambda a, b: (cmp(a['target_type'], b['target_type']) or
                               cmp(a['target'], b['target'])))
        return ret

    def _get_auth_op_target(self, entity_id, target_type, attr=None,
                            any_attr=False, create=False):

        """Return auth_op_target(s) associated with (entity_id,
        target_type, attr).  If any_attr is false, return one
        op_target_id or None.  If any_attr is true, return list of
        matching db_row objects.  If create is true, create a new
        op_target if no matching row is found."""

        if any_attr:
            op_targets = []
            assert attr is None and create is False
        else:
            op_targets = None

        aot = BofhdAuthOpTarget(self.db)
        for r in aot.list(entity_id=entity_id, target_type=target_type,
                          attr=attr):
            if attr is None and not any_attr and r['attr']:
                continue
            if any_attr:
                op_targets.append(r)
            else:
                # There may be more than one matching op_target, but
                # we don't care which one we use -- we will make sure
                # not to make duplicates ourselves.
                op_targets = int(r['op_target_id'])
        if op_targets or not create:
            return op_targets
        # No op_target found, make a new one.
        aot.populate(entity_id, target_type, attr)
        aot.write_db()
        return aot.op_target_id

    def _grant_auth(self, entity_id, opset, target_id, target_type, attr,
                    entity_name, target_name):
        op_target_id = self._get_auth_op_target(target_id, target_type, attr,
                                                create=True)
        ar = BofhdAuthRole(self.db)
        rows = ar.list(entity_id, opset.op_set_id, op_target_id)
        if len(rows) == 0:
            ar.grant_auth(entity_id, opset.op_set_id, op_target_id)
            return "OK, granted %s access %s to %s %s" % (entity_name,
                                                          opset.name,
                                                          target_type,
                                                          target_name)
        return "%s already has %s access to %s %s" % (entity_name,
                                                      opset.name,
                                                      target_type,
                                                      target_name)

    def _revoke_auth(self, entity_id, opset, target_id, target_type, attr,
                     entity_name, target_name):
        op_target_id = self._get_auth_op_target(target_id, target_type, attr)
        if not op_target_id:
            raise CerebrumError("No one has matching access to {}"
                                .format(target_name))
        ar = BofhdAuthRole(self.db)
        rows = ar.list(entity_id, opset.op_set_id, op_target_id)
        if len(rows) == 0:
            return "%s doesn't have %s access to %s %s" % (entity_name,
                                                           opset.name,
                                                           target_type,
                                                           target_name)
        ar.revoke_auth(entity_id, opset.op_set_id, op_target_id)
        # See if the op_target has any references left, delete it if not.
        rows = ar.list(op_target_id=op_target_id)
        if len(rows) == 0:
            aot = BofhdAuthOpTarget(self.db)
            aot.find(op_target_id)
            aot.delete()
        return "OK, revoked %s access for %s from %s %s" % (opset.name,
                                                            entity_name,
                                                            target_type,
                                                            target_name)

    #
    # email commands
    #

    # email add_address <address or account> <address>+
    # exchange-relatert-jazz
    # made it possible to use this cmd for adding addresses
    # to dist group targets
    all_commands['email_add_address'] = Command(
        ('email', 'add_address'),
        SimpleString(help_ref="dlgroup_or_account_name"),
        EmailAddress(help_ref='email_address', repeat=True),
        perm_filter='can_email_address_add')
    def email_add_address(self, operator, name, address):
        try:
            et, acc = self._get_email_target_and_account(name)
        except CerebrumError, e:
            # check if a distribution-group with an appropriate target
            # is registered by this name
            try:
                et, grp = self._get_email_target_and_dlgroup(name)
            except CerebrumError, e:
                raise e
        if et.email_target_type == self.const.email_target_deleted:
            raise CerebrumError("Can't add e-mail address to deleted target")
        ea = Email.EmailAddress(self.db)
        lp, dom = self._split_email_address(address)
        ed = self._get_email_domain(dom)
        # TODO: change can_email_address_add so that both accounts and
        # distribution groups are checked when asserting priviledges
        # however, being "postmaster" trumps this, so assertion will be
        # correct
        self.ba.can_email_address_add(operator.get_entity_id(),
                                      account=acc, domain=ed) \
            or self.ba.is_postmaster(operator.get_entity_id())
        ea.clear()
        try:
            ea.find_by_address(address)
            raise CerebrumError("Address already exists ({})".format(address))
        except Errors.NotFoundError:
            pass
        ea.clear()
        ea.populate(lp, ed.entity_id, et.entity_id)
        ea.write_db()
        return "OK, added '{}' as email-address for '{}'".format(address, name)

    # email remove_address <account> <address>+
    # exchange-relatert-jazz
    # made it possible to use this cmd for removing addresses
    # for dist group targets
    all_commands['email_remove_address'] = Command(
        ('email', 'remove_address'),
        SimpleString(help_ref="dlgroup_or_account_name"),
        EmailAddress(repeat=True),
        perm_filter='can_email_address_delete')
    def email_remove_address(self, operator, name, address):
        try:
            et, acc = self._get_email_target_and_account(name)
        except CerebrumError, e:
            # check if a distribution-group with an appropriate target
            # is registered by this name
            try:
                et, grp = self._get_email_target_and_dlgroup(name)
            except CerebrumError, e:
                raise e
        lp, dom = self._split_email_address(address, with_checks=False)
        ed = self._get_email_domain(dom)
        self.ba.can_email_address_delete(operator.get_entity_id(),
                                         account=acc, domain=ed) \
            or self.ba.is_postmaster(operator.get_entity_id())
        return self._remove_email_address(et, address)

    def _remove_email_address(self, et, address):
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_address(address)
        except Errors.NotFoundError:
            raise CerebrumError("No such e-mail address <{}>".format(address))
        if ea.get_target_id() != et.entity_id:
            raise CerebrumError("<{}> is not associated with that target"
                                .format(address))
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
                raise CerebrumError("Can't remove primary address <{}>".format(
                    address))
        ea.delete()
        if len(addresses) > 1:
            # there is at least one address left
            return "OK, removed '{}'".format(address)
        # clean up and remove the target.
        et.delete()
        return "OK, also deleted e-mail target"

    # email reassign_address <address> <destination>
    all_commands['email_reassign_address'] = Command(
        ('email', 'reassign_address'),
        EmailAddress(help_ref='email_address'),
        AccountName(help_ref='account_name'),
        perm_filter='can_email_address_reassign')
    def email_reassign_address(self, operator, address, dest):
        source_et, source_acc = self._get_email_target_and_account(address)
        ttype = source_et.email_target_type
        if ttype not in (self.const.email_target_account,
                         self.const.email_target_deleted):
            raise CerebrumError("Can't reassign e-mail address from target "
                                "type {}".format(self.const.EmailTarget(ttype)))
        dest_acc = self._get_account(dest)
        if dest_acc.is_deleted():
            raise CerebrumError("Can't reassign e-mail address to deleted "
                                "account {}".format(dest))
        dest_et = Email.EmailTarget(self.db)
        try:
            dest_et.find_by_target_entity(dest_acc.entity_id)
        except Errors.NotFoundError:
            raise CerebrumError("Account {} has no e-mail target".format(dest))
        if dest_et.email_target_type != self.const.email_target_account:
            raise CerebrumError("Can't reassign e-mail address to target "
                                "type {}".format(self.const.EmailTarget(ttype)))
        if source_et.entity_id == dest_et.entity_id:
            return "%s is already connected to %s" % (address, dest)
        if (source_acc.owner_type != dest_acc.owner_type or
                source_acc.owner_id != dest_acc.owner_id):
            raise CerebrumError("Can't reassign e-mail address to a "
                                "different person.")

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
            return "OK, also deleted e-mail target"

        source_acc.update_email_addresses()
        return "OK, reassigned %s" % address

    all_commands['email_local_delivery'] = Command(
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

    def __email_forward_destination_allowed(self, account, address):
        """ Check if the forward is compilant with Norwegian law"""
        person = Utils.Factory.get('Person')(self.db)
        if (account.owner_type == self.const.entity_person and
                person.list_affiliations(
                    person_id=account.owner_id,
                    source_system=self.const.system_sap,
                    affiliation=self.const.affiliation_ansatt)):
            try:
                self._get_email_domain(address.split('@')[-1])
            except CerebrumError:
                return False
        return True

    # email add_forward <account>+ <address>+
    # account can also be an e-mail address for pure forwardtargets
    all_commands['email_add_forward'] = Command(
        ('email', 'add_forward'),
        AccountName(help_ref='account_name', repeat=True),
        EmailAddress(help_ref='email_address', repeat=True),
        perm_filter='can_email_forward_edit')

    def email_add_forward(self, operator, uname, address):
        """Add an email-forward to a email-target asociated with an account."""
        acc = self.Account_class(self.db)
        try:
            acc.find_by_name(uname)
        except Errors.NotFoundError:
            return 'Account {} does not exist.'.format(uname)
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

        if not self.__email_forward_destination_allowed(acc, address):
            raise CerebrumError(
                "Employees cannot forward e-mail to external addresses")

        if fw.get_forward():
            raise CerebrumError("Only one forward allowed at a time")

        fw.add_forward(addr)
        return "OK, added '%s' as forward-address for '%s'" % (
            address, uname)

    # email delete_forward address
    all_commands['email_delete_forward_target'] = Command(
        ("email", "delete_forward_target"),
        EmailAddress(help_ref='email_address'),
        fs=FormatSuggestion([("Deleted forward address: %s", ("address", ))]),
        perm_filter='can_email_forward_create')
    def email_delete_forward_target(self, operator, address):
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
                raise CerebrumError("%s is not the primary address of the target" % address)
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

    # email remove_forward <account>+ <address>+
    # account can also be an e-mail address for pure forwardtargets
    all_commands['email_remove_forward'] = Command(
        ("email", "remove_forward"),
        AccountName(help_ref="account_name", repeat=True),
        EmailAddress(help_ref='email_address', repeat=True),
        perm_filter='can_email_forward_edit')
    def email_remove_forward(self, operator, uname, address):
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
            fw.disable_local_delivery()
            return 'OK, local delivery turned off'
        addr = self._check_email_address(address)
        removed = 0
        for a in [addr]:
            if self._forward_exists(fw, a):
                fw.delete_forward(a)
                removed += 1
        if not removed:
            raise CerebrumError, "No such forward address (%s)" % addr
        return "OK, removed '%s'" % address

    def _check_email_address(self, address):
        """ Check email address syntax.

        Accepted syntax:
            - 'local'
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
            raise CerebrumError, "E-mail addresses must include the domain name"

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
        for r in fw.get_forward():
            if r['forward_to'] == addr:
                return True
        return False

    # email forward_info
    all_commands['email_forward_info'] = Command(
        ('email', 'forward_info'),
        EmailAddress(),
        perm_filter='can_email_forward_info',
        fs=FormatSuggestion([
            ('%s', ('id', ))]))

    def email_forward_info(self, operator, forward_to):
        """List owners of email forwards."""
        self.ba.can_email_forward_info(operator.get_entity_id())
        ef = Email.EmailForward(self.db)
        et = Email.EmailTarget(self.db)
        ac = Utils.Factory.get('Account')(self.db)
        ret = []

        # Different output format for different input.
        rfun = lambda r: (r if '%' not in forward_to else
                          '%-12s %s' % (r, fwd['forward_to']))

        for fwd in ef.search(forward_to):
            try:
                et.clear()
                et.find(fwd['target_id'])
                ac.clear()
                ac.find(et.email_target_entity_id)
                ret.append({'id': rfun(ac.account_name)})
            except Errors.NotFoundError:
                ret.append({'id': rfun('id:%s' % et.entity_id)})
        return ret

    # email info <account>+
    all_commands['email_info'] = Command(
        ("email", "info"),
        # AccountName(help_ref="account_name", repeat=True),
        SimpleString(help_ref="dlgroup_or_account_name", repeat=True),
        perm_filter='can_email_info',
        fs=FormatSuggestion([
        ("Type:             %s", ("target_type",)),
        ("History:          entity history id:%d", ("target_id",)),
        #
        # target_type == Account
        #
        ("Account:          %s\nMail server:      %s (%s)",
         ("account", "server", "server_type")),
        ("Primary address:  %s",
         ("def_addr", )),
        ("Alias value:      %s",
         ("alias_value", )),
        # We use valid_addr_1 and (multiple) valid_addr to enable
        # programs to get the information reasonably easily, while
        # still keeping the suggested output format pretty.
        ("Valid addresses:  %s",
         ("valid_addr_1", )),
        ("                  %s",
         ("valid_addr",)),
        ("Mail quota:       %d MiB, warn at %d%% (not enforced)",
         ("dis_quota_hard", "dis_quota_soft")),
        ("Mail quota:       %d MiB, warn at %d%% (%s used (MiB))",
         ("quota_hard", "quota_soft", "quota_used")),
        ("                  (currently %d MiB on server)",
         ("quota_server",)),
        ("HomeMDB:          %s",
         ("homemdb", )),
        # TODO: change format so that ON/OFF is passed as separate value.
        # this must be coordinated with webmail code.
        ("Forwarding:       %s",
         ("forward_1", )),
        ("                  %s",
         ("forward", )),
        # exchange-relatert-jazz
        #
        # target_type == dlgroup
        #
        ("Dl group:         %s",
         ("name", )),
        ("Group id:         %d",
         ("group_id", )),
        ("Display name:     %s",
         ("displayname", )),
        ("Primary address:  %s",
         ("primary", )),
        # We use valid_addr_1 and (multiple) valid_addr to enable
        # programs to get the information reasonably easily, while
        # still keeping the suggested output format pretty.
        #("Valid addresses:  %s",
         #("valid_addr_1", )),
        #("                  %s",
        # ("valid_addr",)),
        ("Valid addresses:  %s",
         ("aliases", )),
        ("Hidden addr list: %s",
         ('hidden', )),
        #
        # target_type == Sympa
        #
        ("Mailing list:     %s",
         ("sympa_list",)),
        ("Alias:            %s",
         ("sympa_alias_1",)),
        ("                  %s",
         ("sympa_alias",)),
        ("Request:          %s",
         ("sympa_request_1",)),
        ("                  %s",
         ("sympa_request",)),
        ("Owner:            %s",
         ("sympa_owner_1",)),
        ("                  %s",
         ("sympa_owner",)),
        ("Editor:           %s",
         ("sympa_editor_1",)),
        ("                  %s",
         ("sympa_editor",)),
        ("Subscribe:        %s",
         ("sympa_subscribe_1",)),
        ("                  %s",
         ("sympa_subscribe",)),
        ("Unsubscribe:      %s",
         ("sympa_unsubscribe_1",)),
        ("                  %s",
         ("sympa_unsubscribe",)),
        ("Delivery host:    %s",
         ("sympa_delivery_host",)),
        # target_type == multi
        ("Forward to group: %s",
         ("multi_forward_gr",)),
        ("Expands to:       %s",
         ("multi_forward_1",)),
        ("                  %s",
         ("multi_forward",)),
        # target_type == file
        ("File:             %s\n"+
         "Save as:          %s",
         ("file_name", "file_runas")),
        # target_type == pipe
        ("Command:          %s\n"+
         "Run as:           %s",
         ("pipe_cmd", "pipe_runas")),
        # target_type == RT
        ("RT queue:         %s on %s\n"+
         "Action:           %s\n"+
         "Run as:           %s",
         ("rt_queue", "rt_host", "rt_action","pipe_runas")),
        # target_type == forward
        ("Address:          %s",
         ("fw_target",)),
        ("Forwarding:       %s (%s)",
         ("fw_addr_1", "fw_enable_1")),
        ("                  %s (%s)",
         ("fw_addr", "fw_enable")),
        #
        # both account and Sympa
        #
        ("Spam level:       %s (%s)\nSpam action:      %s (%s)",
         ("spam_level", "spam_level_desc", "spam_action", "spam_action_desc")),
        ("Filters:          %s",
         ("filters",)),
        ("Status:           %s",
         ("status",)),
        ]))
    def email_info(self, operator, name):
        try:
            et, acc = self._get_email_target_and_account(name)
        except CerebrumError, e:
            # exchange-relatert-jazz
            # check if a distribution-group with an appropriate target
            # is registered by this name
            try:
                et, grp = self._get_email_target_and_dlgroup(name)
            except CerebrumError, e:
                # handle accounts with email address stored in contact_info
                try:
                    ac = self._get_account(name)
                    return self._email_info_contact_info(operator, ac)
                except CerebrumError:
                    pass
            raise e

        ttype = et.email_target_type
        ttype_name = str(self.const.EmailTarget(ttype))

        ret = []

        if ttype not in (self.const.email_target_Sympa,
                         self.const.email_target_pipe,
                         self.const.email_target_RT,
                         self.const.email_target_dl_group):
            ret += [
                {'target_type': ttype_name,
                 'target_id': et.entity_id, }
            ]

        epat = Email.EmailPrimaryAddressTarget(self.db)
        try:
            epat.find(et.entity_id)
        except Errors.NotFoundError:
            if ttype == self.const.email_target_account:
                ret.append({'def_addr': "<none>"})
        else:
            # exchange-relatert-jazz
            # drop def_addr here, it's introduced at proper placing later
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
            if not addrs: addrs = ["<none>"]
            ret.append({'valid_addr_1': addrs[0]})
            for addr in addrs[1:]:
                ret.append({"valid_addr": addr})

        if ttype == self.const.email_target_Sympa:
            ret += self._email_info_sympa(operator, name, et)
        elif ttype == self.const.email_target_dl_group:
            ret += self._email_info_dlgroup(name)
        elif ttype == self.const.email_target_multi:
            ret += self._email_info_multi(name, et)
        elif ttype == self.const.email_target_file:
            ret += self._email_info_file(name, et)
        elif ttype == self.const.email_target_pipe:
            ret += self._email_info_pipe(name, et)
        elif ttype == self.const.email_target_RT:
            ret += self._email_info_rt(name, et)
        elif ttype == self.const.email_target_forward:
            ret += self._email_info_forward(name, et)
        elif (ttype == self.const.email_target_account,
              # exchange-relatert jazz
              # This should be changed, distgroups will have
              # target_type=deleted and we will no longer
              # be able to assume "deleted" means that
              # target_entity_type is account
              # <TODO>
              ttype == self.const.email_target_deleted):
            ret += self._email_info_account(operator, acc, et, addrs)
        else:
            raise CerebrumError, ("email info for target type %s isn't "
                                  "implemented") % ttype_name

        # Only the account owner and postmaster can see account settings, and
        # that is handled properly in _email_info_account.
        if not ttype in (self.const.email_target_account,
                         self.const.email_target_deleted):
            ret += self._email_info_spam(et)
            ret += self._email_info_filters(et)
            ret += self._email_info_forwarding(et, name)
        return ret

    def _email_info_contact_info(self, operator, acc):
        """Some accounts doesn't have an e-mail account, but could have stored
        an e-mail address in the its contact_info.

        Note that this method raises an exception if no such contact_info
        address was found."""
        addresses = acc.get_contact_info(type=self.const.contact_email)
        if not addresses:
            raise CerebrumError("No contact info for: %s" % acc.account_name)
        ret = [{'target_type': 'entity_contact_info'},]
        return ret + [{'valid_addr_1': a['contact_value']} for a in addresses]

    def _email_info_account(self, operator, acc, et, addrs):
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

    def _get_valid_email_addrs(self, et, special=False, sort=False):
        """Return a list of all valid e-mail addresses for the given
        EmailTarget.  Keep special domain names intact if special is
        True, otherwise re-write them into real domain names."""
        addrs = [(r['local_part'], r['domain'])
                 for r in et.get_addresses(special=special)]
        if sort:
            addrs.sort(lambda x,y: cmp(x[1], y[1]) or cmp(x[0],y[0]))
        return ["%s@%s" % a for a in addrs]

    def _email_info_basic(self, acc, et):
        info = {}
        data = [ info ]
        if (et.email_target_type != self.const.email_target_Sympa and
            et.email_target_alias is not None):
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
        info = []
        esf = Email.EmailSpamFilter(self.db)
        try:
            esf.find(target.entity_id)
            spam_lev = self.const.EmailSpamLevel(esf.email_spam_level)
            spam_act = self.const.EmailSpamAction(esf.email_spam_action)
            info.append({'spam_level':       str(spam_lev),
                         'spam_level_desc':  spam_lev.description,
                         'spam_action':      str(spam_act),
                         'spam_action_desc': spam_act.description})
        except Errors.NotFoundError:
            pass
        return info

    def _email_info_filters(self, target):
        filters = []
        info ={}
        etf = Email.EmailTargetFilter(self.db)
        for f in etf.list_email_target_filter(target_id=target.entity_id):
            filters.append(str(Email._EmailTargetFilterCode(f['filter'])))
        if len(filters) > 0:
            info["filters"] =  ", ".join([x for x in filters]),
        else:
            info["filters"] = "None"
        return [ info ]

    def _email_info_detail(self, acc):
        info = []
        eq = Email.EmailQuota(self.db)
        try:
            eq.find_by_target_entity(acc.entity_id)
            et = Email.EmailTarget(self.db)
            et.find_by_target_entity(acc.entity_id)
            es = Email.EmailServer(self.db)
            es.find(et.email_server_id)

            # exchange-relatert-jazz
            # since Exchange-users will have a different kind of
            # server this code will not be affected at Exchange
            # roll-out It may, however, be removed as soon as
            # migration is completed (up to and including
            # "dis_quota_soft': eq.email_quota_soft})")
            if es.email_server_type == self.const.email_server_type_cyrus:
                pw = self.db._read_password(cereconf.CYRUS_HOST,
                                            cereconf.CYRUS_ADMIN)
                used = 'N/A'; limit = None
                try:
                    cyrus = Utils.CerebrumIMAP4_SSL(es.name, ssl_version=ssl.PROTOCOL_TLSv1)
                    # IVR 2007-08-29 If the server is too busy, we do not want
                    # to lock the entire bofhd.
                    # 5 seconds should be enough
                    cyrus.socket().settimeout(5)
                    cyrus.login(cereconf.CYRUS_ADMIN, pw)
                    res, quotas = cyrus.getquota("user." + acc.account_name)
                    cyrus.socket().settimeout(None)
                    if res == "OK":
                        for line in quotas:
                            try:
                                folder, qtype, qused, qlimit = line.split()
                                if qtype == "(STORAGE":
                                    used = str(int(qused)/1024)
                                    limit = int(qlimit.rstrip(")"))/1024
                            except ValueError:
                                # line.split fails e.g. because quota isn't set on server
                                folder, junk = line.split()
                                self.logger.warning("No IMAP quota set for '%s'" % acc.account_name)
                                used = "N/A"
                                limit = None
                except (TimeoutException, socket.error):
                    used = 'DOWN'
                except ConnectException, e:
                    used = str(e)
                except imaplib.IMAP4.error, e:
                    used = 'DOWN'
                info.append({'quota_hard': eq.email_quota_hard,
                             'quota_soft': eq.email_quota_soft,
                             'quota_used': used})
                if limit is not None and limit != eq.email_quota_hard:
                    info.append({'quota_server': limit})
            else:
                info.append({'dis_quota_hard': eq.email_quota_hard,
                             'dis_quota_soft': eq.email_quota_soft})
        except Errors.NotFoundError:
            pass
        # exchange-relatert-jazz
        # delivery for exchange-mailboxes is not regulated through
        # LDAP, and LDAP should not be checked there my be some need
        # to implement support for checking if delivery is paused in
        # Exchange, but at this point only very vague explanation has
        # been given and priority is therefore low
        if acc.has_spread(self.const.spread_exchange_account):
            return info
        # Check if the ldapservers have set mailPaused
        if self._email_delivery_stopped(acc.account_name):
            info.append({'status': 'Paused (migrating to new server)'})

        return info

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

    def _email_info_dlgroup(self, groupname):
        et, dl_group = self._get_email_target_and_dlgroup(groupname)
        ret = []
        # we need to make the return value conform with the
        # client requeirements
        tmpret = dl_group.get_distgroup_attributes_and_targetdata()
        for x in tmpret:
            if tmpret[x] == 'T':
                ret.append({x: 'Yes'})
                continue
            elif tmpret[x] == 'F':
                ret.append({x: 'No'})
                continue
            ret.append({x: tmpret[x]})
        return ret

    def _email_info_sympa(self, operator, addr, et):
        """Collect Sympa-specific information for a ML L{addr}."""

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
            raise CerebrumError, ("Address %s exists, but the list it points "
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

        for suffix in ("owner", "request", "editor", "subscribe", "unsubscribe"):
            ret.extend(fish_information(suffix, lp, dom, listname))
        return ret
    # end _email_info_sympa


    def _email_info_multi(self, addr, et):
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
            for row in group.search_members(group_id=group.entity_id,
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

    def _email_info_file(self, addr, et):
        account_name = "<not set>"
        if et.email_target_using_uid:
            acc = self._get_account(et.email_target_using_uid, idtype='id')
            account_name = acc.account_name
        return [{'file_name': et.get_alias(),
                 'file_runas': account_name}]

    def _email_info_pipe(self, addr, et):
        acc = self._get_account(et.email_target_using_uid, idtype='id')
        return [{'pipe_cmd': et.get_alias(), 'pipe_runas': acc.account_name}]

    def _email_info_rt(self, addr, et):
        m = re.match(self._rt_patt, et.get_alias())
        acc = self._get_account(et.email_target_using_uid, idtype='id')
        return [{'rt_action': m.group(1),
                 'rt_queue': m.group(2),
                 'rt_host': m.group(3),
                 'pipe_runas':  acc.account_name}]

    def _email_info_forward(self, addr, et):
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

    def _email_delivery_stopped(self, user):
        # Delayed import so the script can run on machines without ldap
        # module
        import ldap, ldap.filter, ldap.ldapobject
        ldapconns = [ldap.ldapobject.ReconnectLDAPObject("ldap://%s/" % server)
                     for server in cereconf.LDAP_SERVERS]
        userfilter = ("(&(target=%s)(mailPause=TRUE))" %
                      ldap.filter.escape_filter_chars(user))
        for conn in ldapconns:
            try:
                # FIXME: cereconf.LDAP_MAIL['dn'] has a bogus value, so we
                # must hardcode the DN.
                res = conn.search_s("cn=targets,cn=mail,dc=uio,dc=no",
                                    ldap.SCOPE_ONELEVEL, userfilter, ["1.1"])
                if len(res) != 1:
                    return False
            except ldap.LDAPError, e:
                self.logger.error("LDAP search failed: %s", e)
                return False

        return True

    # email show_reservation_status
    all_commands['email_show_reservation_status'] = Command(
        ('email', 'show_reservation_status'), AccountName(),
        fs=FormatSuggestion(
            [("%-9s %s", ("uname", "hide"))]),
        perm_filter='is_postmaster')

    def email_show_reservation_status(self, operator, uname):
        """Display reservation status for a person."""
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('Access to this command is restricted')
        hidden = True
        account = self._get_account(uname)
        if account.owner_type == self.const.entity_person:
            person = self._get_person('entity_id', account.owner_id)
            if person.has_e_reservation():
                hidden = True
            elif person.get_primary_account() != account.entity_id:
                hidden = True
            else:
                hidden = False
        return {'uname': uname, 'hide': 'hidden' if hidden else 'visible'}

    # email modify_name
    all_commands['email_mod_name'] = Command(
        ("email", "mod_name"),PersonId(help_ref="person_id_other"),
        PersonName(help_ref="person_name_first"),
        PersonName(help_ref="person_name_last"),
        fs=FormatSuggestion("Name and e-mail address altered for: %i",
        ("person_id",)),
        perm_filter='can_email_mod_name')
    def email_mod_name(self, operator, person_id, firstname, lastname):
        person = self._get_person(*self._map_person_id(person_id))
        self.ba.can_email_mod_name(operator.get_entity_id(), person=person,
                                   firstname=firstname, lastname=lastname)
        source_system = self.const.system_override
        person.affect_names(source_system,
                            self.const.name_first,
                            self.const.name_last,
                            self.const.name_full)
        if lastname == "":
            raise CerebrumError, "A last name is required"
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
            raise CerebrumError, "Database error: %s" % m
        return {'person_id': person.entity_id}

    # email primary_address <address>
    all_commands['email_primary_address'] = Command(
        ("email", "primary_address"),
        EmailAddress(),
        fs=FormatSuggestion([("New primary address: '%s'", ("address", ))]),
        perm_filter="is_postmaster")
    def email_primary_address(self, operator, addr):
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")

        et, ea = self._get_email_target_and_address(addr)
        if et.email_target_type == self.const.email_target_dl_group:
            return "Cannot change primary for distribution group %s" % addr
        return self._set_email_primary_address(et, ea, addr)

    def _set_email_primary_address(self, et, ea, addr):
        epat = Email.EmailPrimaryAddressTarget(self.db)
        try:
            epat.find(et.entity_id)
        except Errors.NotFoundError:
            epat.clear()
            epat.populate(ea.entity_id, parent=et)
        else:
            if epat.email_primaddr_id == ea.entity_id:
                return "No change: '%s'" % addr
            epat.email_primaddr_id = ea.entity_id
        epat.write_db()
        return {'address': addr}

    # email create_pipe <address> <uname> <command>
    all_commands['email_create_pipe'] = Command(
        ("email", "create_pipe"),
        EmailAddress(help_ref="email_address"),
        AccountName(),
        SimpleString(help_ref="command_line"),
        perm_filter="can_email_pipe_create")
    def email_create_pipe(self, operator, addr, uname, cmd):
        lp, dom = self._split_email_address(addr)
        ed = self._get_email_domain(dom)
        self.ba.can_email_pipe_create(operator.get_entity_id(), ed)
        acc = self._get_account(uname)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.entity_id)
        except Errors.NotFoundError:
            pass
        else:
            raise CerebrumError, "%s already exists" % addr
        et = Email.EmailTarget(self.db)
        if not cmd.startswith('|'):
            cmd = '|' +  cmd
        et.populate(self.const.email_target_pipe, alias=cmd,
                    using_uid=acc.entity_id)
        et.write_db()
        ea.clear()
        ea.populate(lp, ed.entity_id, et.entity_id)
        ea.write_db()
        self._register_spam_settings(addr, self.const.email_target_pipe)
        self._register_filter_settings(addr, self.const.email_target_pipe)
        return "OK, created pipe address %s" % addr

    # email delete_pipe <address>
    all_commands['email_delete_pipe'] = Command(
        ("email", "delete_pipe"),
        EmailAddress(help_ref="email_address"),
        perm_filter="can_email_pipe_create")
    def email_delete_pipe(self, operator, addr):
        lp, dom = self._split_email_address(addr, with_checks=False)
        ed = self._get_email_domain(dom)
        self.ba.can_email_pipe_create(operator.get_entity_id(), ed)
        ea = Email.EmailAddress(self.db)
        et = Email.EmailTarget(self.db)
        try:
            ea.clear()
            ea.find_by_address(addr)
        except Errors.NotFoundError:
            raise CerebrumError, "No such address %s" % addr
        try:
            et.clear()
            et.find(ea.email_addr_target_id)
        except Errors.NotFoundError:
            raise CerebrumError, "No e-mail target for %s" % addr
        for a in et.get_addresses():
            ea.clear()
            ea.find(a['address_id'])
            ea.delete()
            ea.write_db()
        et.delete()
        et.write_db()
        return "Ok, deleted pipe for address %s" % addr

    # email failure_message <username> <message>
    all_commands['email_failure_message'] = Command(
        ("email", "failure_message"),
        AccountName(help_ref="account_name"),
        SimpleString(help_ref="email_failure_message"),
        perm_filter="can_email_set_failure")
    def email_failure_message(self, operator, uname, message):
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        et, acc = self._get_email_target_and_account(uname)
        if et.email_target_type != self.const.email_target_deleted:
            raise CerebrumError, ("You can only set the failure message "
                                  "for deleted users")
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

    # email edit_pipe_command <address> <command>
    all_commands['email_edit_pipe_command'] = Command(
        ("email", "edit_pipe_command"),
        EmailAddress(),
        SimpleString(help_ref="command_line"),
        perm_filter="can_email_pipe_edit")
    def email_edit_pipe_command(self, operator, addr, cmd):
        lp, dom = self._split_email_address(addr)
        ed = self._get_email_domain(dom)
        self.ba.can_email_pipe_edit(operator.get_entity_id(), ed)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.entity_id)
        except Errors.NotFoundError:
            raise CerebrumError, "%s: No such address exists" % addr
        et = Email.EmailTarget(self.db)
        et.find(ea.email_addr_target_id)
        if not et.email_target_type in (self.const.email_target_pipe,
                                        self.const.email_target_RT):
            raise CerebrumError, "%s is not connected to a pipe or RT target" % addr
        if not cmd.startswith('|'):
            cmd = '|' +  cmd
        if et.email_target_type == self.const.email_target_RT and \
           not re.match(self._rt_patt, cmd):
            raise CerebrumError("'%s' is not a valid RT command" % cmd)
        et.email_target_alias = cmd
        et.write_db()
        return "OK, edited %s" % addr

    # email edit_pipe_user <address> <uname>
    all_commands['email_edit_pipe_user'] = Command(
        ("email", "edit_pipe_user"),
        EmailAddress(),
        AccountName(),
        perm_filter="can_email_pipe_edit")
    def email_edit_pipe_user(self, operator, addr, uname):
        lp, dom = self._split_email_address(addr)
        ed = self._get_email_domain(dom)
        self.ba.can_email_pipe_edit(operator.get_entity_id(), ed)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.entity_id)
        except Errors.NotFoundError:
            raise CerebrumError, "%s: No such address exists" % addr
        et = Email.EmailTarget(self.db)
        et.find(ea.email_addr_target_id)
        if not et.email_target_type in (self.const.email_target_pipe,
                                        self.const.email_target_RT):
            raise CerebrumError, "%s is not connected to a pipe or RT target" % addr
        et.email_target_using_uid = self._get_account(uname).entity_id
        et.write_db()
        return "OK, edited %s" % addr


    # email create_domain <domainname> <description>
    all_commands['email_create_domain'] = Command(
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
            raise CerebrumError, "%s: e-mail domain already exists" % domainname
        except Errors.NotFoundError:
            pass
        if len(desc) < 3:
            raise CerebrumError, "Please supply a better description"
        try:
            ed.populate(domainname, desc)
        except AttributeError, ae:
            raise CerebrumError(str(ae))
        ed.write_db()
        return "OK, domain '%s' created" % domainname


    # email delete_domain <domainname>
    all_commands['email_delete_domain'] = Command(
        ("email", "delete_domain"),
        SimpleString(help_ref="email_domain"),
        perm_filter="can_email_domain_create")
    def email_delete_domain(self, operator, domainname):
        """Delete an e-mail domain."""
        self.ba.can_email_archive_delete(operator.get_entity_id())

        domainname = domainname.lower()
        ed = Email.EmailDomain(self.db)
        try:
            ed.find_by_domain(domainname)
        except Errors.NotFoundError:
            raise CerebrumError, "%s: No e-mail domain by that name" % domainname

        ea = Email.EmailAddress(self.db)
        if ea.search(domain_id=ed.entity_id, fetchall=True):
            raise CerebrumError, "E-mail-domain '%s' has addresses; cannot delete" % domainname

        eed = Email.EntityEmailDomain(self.db)
        if eed.list_affiliations(domain_id=ed.entity_id):
            raise CerebrumError, "E-mail-domain '%s' associated with OUs; cannot delete" % domainname

        ed.delete()
        ed.write_db()

        return "OK, domain '%s' deleted" % domainname


    # email domain_configuration on|off <domain> <category>+
    all_commands['email_domain_configuration'] = Command(
        ("email", "domain_configuration"),
        SimpleString(help_ref="on_or_off"),
        SimpleString(help_ref="email_domain"),
        SimpleString(help_ref="email_category", repeat=True),
        perm_filter="can_email_domain_create")
    def email_domain_configuration(self, operator, onoff, domainname, cat):
        """Change configuration for an e-mail domain."""
        self.ba.can_email_domain_create(operator.get_entity_id())
        ed = self._get_email_domain(domainname)
        on = self._get_boolean(onoff)
        catcode = None
        for c in self.const.fetch_constants(self.const.EmailDomainCategory,
                                            prefix_match=cat):
            if catcode:
                raise CerebrumError, ("'%s' does not uniquely identify "+
                                      "a configuration category") % cat
            catcode = c
        if catcode is None:
            raise CerebrumError, ("'%s' does not match any configuration "+
                                  "category") % cat
        if self._sync_category(ed, catcode, on):
            return "%s is now %s" % (catcode, onoff.lower())
        else:
            return "%s unchanged" % catcode

    # email domain_set_description
    all_commands['email_domain_set_description'] = Command(
        ("email", "domain_set_description"),
        SimpleString(help_ref="email_domain"),
        SimpleString(help_ref="string_description"),
        perm_filter='can_email_domain_create')
    def email_domain_set_description(self, operator, domainname, description):
        """Set the description of an e-mail domain."""
        self.ba.can_email_domain_create(operator.get_entity_id())
        ed = self._get_email_domain(domainname)
        ed.email_domain_description = description
        ed.write_db()
        return "OK, description for domain '%s' updated" % domainname

    def _onoff(self, enable):
        if enable:
            return 'on'
        else:
            return 'off'

    def _has_category(self, domain, category):
        ccode = int(category)
        for r in domain.get_categories():
            if r['category'] == ccode:
                return True
        return False

    def _sync_category(self, domain, category, enable):
        """Enable or disable category with EmailDomain.  Returns False
        for no change or True for change."""
        if self._has_category(domain, category) == enable:
            return False
        if enable:
            domain.add_category(category)
        else:
            domain.remove_category(category)
        return True

    # email domain_info <domain>
    # this command is accessible for all
    all_commands['email_domain_info'] = Command(
        ("email", "domain_info"),
        SimpleString(help_ref="email_domain"),
        fs=FormatSuggestion([
        ("E-mail domain:    %s\n"+
         "Description:      %s",
         ("domainname", "description")),
        ("Configuration:    %s",
         ("category",)),
        ("Affiliation:      %s@%s",
         ("affil", "ou"))]))
    def email_domain_info(self, operator, domainname):
        ed = self._get_email_domain(domainname)
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

    # email add_domain_affiliation <domain> <stedkode> [<affiliation>]
    all_commands['email_add_domain_affiliation'] = Command(
        ("email", "add_domain_affiliation"),
        SimpleString(help_ref="email_domain"),
        OU(), Affiliation(optional=True),
        perm_filter="can_email_domain_create")
    def email_add_domain_affiliation(self, operator, domainname, sko, aff=None):
        self.ba.can_email_domain_create(operator.get_entity_id())
        ed = self._get_email_domain(domainname)
        try:
            ou = self._get_ou(stedkode=sko)
        except Errors.NotFoundError:
            raise CerebrumError, "Unknown OU (%s)" % sko
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
                return "OK (was %s), %d accounts updated" % \
                       (ed.email_domain_name, count)
            return "OK (no change)"

    def _update_email_for_ou(self, ou_id, aff_id):
        """Updates the e-mail addresses for all accounts where the
        given affiliation is their primary, and returns the number of
        modified accounts."""

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

    # email remove_domain_affiliation <domain> <stedkode> [<affiliation>]
    all_commands['email_remove_domain_affiliation'] = Command(
        ("email", "remove_domain_affiliation"),
        SimpleString(help_ref="email_domain"),
        OU(), Affiliation(optional=True),
        perm_filter="can_email_domain_create")
    def email_remove_domain_affiliation(self, operator, domainname, sko,
                                        aff=None):
        self.ba.can_email_domain_create(operator.get_entity_id())
        ed = self._get_email_domain(domainname)
        try:
            ou = self._get_ou(stedkode=sko)
        except Errors.NotFoundError:
            raise CerebrumError, "Unknown OU (%s)" % sko
        aff_id = None
        if aff:
            aff_id = int(self._get_affiliationid(aff))
        eed = Email.EntityEmailDomain(self.db)
        try:
            eed.find(ou.entity_id, aff_id)
        except Errors.NotFoundError:
            raise CerebrumError, "No such affiliation for domain"
        if eed.entity_email_domain_id != ed.entity_id:
            raise CerebrumError, "No such affiliation for domain"
        eed.delete()
        return "OK, removed domain-affiliation for '%s'" % domainname

    def _email_create_forward_target(self, localaddr, remoteaddr):
        """Helper method for creating a forward target.

        No auth is checked here.

        """
        lp, dom = self._split_email_address(localaddr)
        ed = self._get_email_domain(dom)
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
        self._register_spam_settings(localaddr, self.const.email_target_forward)
        self._register_filter_settings(localaddr, self.const.email_target_forward)
        return ef

    # email create_forward_target <local-address> <remote-address>
    all_commands['email_create_forward_target'] = Command(
        ("email", "create_forward_target"),
        EmailAddress(),
        EmailAddress(help_ref='email_forward_address'),
        perm_filter="can_email_forward_create")
    def email_create_forward_target(self, operator, localaddr, remoteaddr):
        """Create a forward target, add localaddr as an address
        associated with that target, and add remoteaddr as a forward
        addresses."""
        lp, dom = self._split_email_address(localaddr)
        ed = self._get_email_domain(dom)
        self.ba.can_email_forward_create(operator.get_entity_id(), ed)
        self._email_create_forward_target(localaddr, remoteaddr)
        return "OK, created forward address '%s'" % localaddr

    def _register_spam_settings(self, address, target_type):
        """Register spam settings (level/action) associated with an address."""

        et, addr = self._get_email_target_and_address(address)
        esf = Email.EmailSpamFilter(self.db)
        all_targets = [et.entity_id]
        if target_type == self.const.email_target_Sympa:
            all_targets = self._get_all_related_maillist_targets(addr.get_address())
        elif target_type == self.const.email_target_RT:
            all_targets = self._get_all_related_rt_targets(addr.get_address())
        target_type = str(target_type)
        if cereconf.EMAIL_DEFAULT_SPAM_SETTINGS.has_key(target_type):
            sl, sa = cereconf.EMAIL_DEFAULT_SPAM_SETTINGS[target_type]
            spam_level = int(self.const.EmailSpamLevel(sl))
            spam_action = int(self.const.EmailSpamAction(sa))
            for target_id in all_targets:
                et.clear()
                et.find(target_id)
                esf.clear()
                esf.populate(spam_level, spam_action, parent=et)
                esf.write_db()
    # end _register_spam_settings


    def _register_filter_settings(self, address, target_type):
        """Register spam filter settings associated with an address."""
        et, addr = self._get_email_target_and_address(address)
        etf = Email.EmailTargetFilter(self.db)
        all_targets = [et.entity_id]
        if target_type == self.const.email_target_Sympa:
            all_targets = self._get_all_related_maillist_targets(addr.get_address())
        elif target_type == self.const.email_target_RT:
            all_targets = self._get_all_related_rt_targets(addr.get_address())
        target_type = str(target_type)
        if cereconf.EMAIL_DEFAULT_FILTERS.has_key(target_type):
            for f in cereconf.EMAIL_DEFAULT_FILTERS[target_type]:
                filter_code = int(self.const.EmailTargetFilter(f))
                for target_id in all_targets:
                    et.clear()
                    et.find(target_id)
                    etf.clear()
                    etf.populate(filter_code, parent=et)
                    etf.write_db()
    # end _register_filter_settings

    # email create_sympa_list run-host delivery-host <listaddr> adm prof desc
    all_commands['email_create_sympa_list'] = Command(
        ("email", "create_sympa_list"),
        SimpleString(help_ref='string_exec_host'),
        SimpleString(help_ref='string_email_delivery_host'),
        EmailAddress(help_ref="mailing_list"),
        SimpleString(help_ref="mailing_admins"),
        SimpleString(help_ref="mailing_list_profile"),
        SimpleString(help_ref="mailing_list_description"),
        YesNo(help_ref="yes_no_force", optional=True, default="No"),
        perm_filter="can_email_list_create")
    def email_create_sympa_list(self, operator, run_host, delivery_host,
                                listname, admins, list_profile,
                                list_description, force=None):
        """Create a sympa list in Cerebrum and on the sympa server(s).

        Register all the necessary cerebrum information and make a bofhd
        request for the actual list creation.
        """

        # Check that the profile is legal
        if list_profile not in cereconf.SYMPA_PROFILES:
            raise CerebrumError("Profile %s for sympa list %s is not valid" %
                                (list_profile, listname))

        # Check that the command exec host is sane
        if run_host not in cereconf.SYMPA_RUN_HOSTS:
            raise CerebrumError("run-host %s for sympa list %s is not valid" %
                                (run_host, listname))

        metachars = "'\"$&()*;<>?[\\]`{|}~\n"
        def has_meta(s1, s2=metachars):
            """Check if any char of s1 is in s2"""
            for c in s1:
                if c in s2:
                    return True
            return False
        # end any

        # Sympa list creation command will be passed through multiple
        # exec/shells. Better be restrictive.
        if True in [has_meta(x) for x in
                    (run_host, delivery_host, listname, admins, list_profile,
                     list_description)]:
            raise CerebrumError("Illegal metacharacter in list parameter. None "
                                "of the %s are allowed." % metachars)

        delivery_host = self._get_email_server(delivery_host)
        if self._is_yes(force):
            self._create_mailing_list_in_cerebrum(operator,
                                                  self.const.email_target_Sympa,
                                                  delivery_host,
                                                  listname, force=True)
        else:
            self._create_mailing_list_in_cerebrum(operator,
                                                  self.const.email_target_Sympa,
                                                  delivery_host,
                                                  listname)
        # Now make a bofhd request to create the list itself
        admin_list = list()
        for item in admins.split(","):
            # it's a user name. That username must exist in Cerebrum
            if "@" not in item:
                self._get_account(item)
                item = item + "@ulrik.uio.no"
            admin_list.append(item)

        # Make the request.
        lp, dom = self._split_email_address(listname)
        ed = self._get_email_domain(dom)
        ea = Email.EmailAddress(self.db)
        ea.clear()
        ea.find_by_local_part_and_domain(lp, ed.entity_id)
        list_id = ea.entity_id
        # IVR 2008-08-01 TBD: this is a big ugly. We need to pass several
        # arguments to p_b_r, but we cannot really store them anywhere :( The
        # idea is then to take a small dict, pickle it, shove into state_data,
        # unpickle in p_b_r and be on our merry way. It is at the very best
        # suboptimal.
        state = {"runhost": run_host, # IVR 2008-08-01 FIXME: non-fqdn? force?
                                      # check?
                 "admins": admin_list,
                 "profile": list_profile,
                 "description": list_description,
        }
        br = BofhdRequests(self.db, self.const)

        # IVR 2009-04-17 +30 minute delay to allow changes to spread to
        # LDAP. The postmasters are nagging for that delay. All questions
        # should be directed to them (this is similar to delaying a delete
        # request).
        br.add_request(operator.get_entity_id(),
                       DateTime.now() + DateTime.DateTimeDelta(0, 0, 30),
                       self.const.bofh_sympa_create, list_id, ea.entity_id,
                       state_data=pickle.dumps(state))
        return "OK, sympa list '%s' created" % listname

    all_commands['email_create_sympa_cerebrum_list'] = Command(
        ("email", "create_sympa_cerebrum_list"),
        SimpleString(help_ref='string_email_delivery_host'),
        EmailAddress(help_ref="mailing_list"),
        YesNo(help_ref="yes_no_force", optional=True, default="No"),
        perm_filter="can_email_list_create")
    def email_create_sympa_cerebrum_list(self, operator, delivery_host, listname, force=None):
        """Create a sympa mailing list in cerebrum only"""

        delivery_host = self._get_email_server(delivery_host)
        if self._is_yes(force):
            self._create_mailing_list_in_cerebrum(operator,
                                                  self.const.email_target_Sympa,
                                                  delivery_host,
                                                  listname, force=True)
        else:
            self._create_mailing_list_in_cerebrum(operator,
                                                  self.const.email_target_Sympa,
                                                  delivery_host,
                                                  listname)
        return "OK, sympa list '%s' created in cerebrum only" % listname

    def _create_mailing_list_in_cerebrum(self, operator, target_type,
                                         delivery_host, listname, force=False):
        """Register cerebrum information (only) about a new mailing list.

        @type target_type: an EmailTarget constant
        @param target_type:
          ET specifying the mailing list we are creating.

        @type admins: basestring
        @param admins:
          This one is a tricky bugger. This is either a single value or a
          sequence thereof. If it is a sequence, then the items are separated
          by commas.

          Each item is either a user name, or an e-mail address. User names
          *MUST* exist in Cerebrum and *MUST* have e-mail addresses. E-mail
          addresses do NOT have to be registered in Cerebrum (they may, in
          fact, be external to Cerebrum).

        @type force: boolean.
        @param force:
          If True, *force* certain operations.
        """

        local_part, domain = self._split_email_address(listname)
        ed = self._get_email_domain(domain)
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

        # Then, check whether there is a user name equal to local_part.
        try:
            self._get_account(local_part)
        except CerebrumError:
            pass
        else:
            if not (local_part in ("drift",) or
                    (self.ba.is_postmaster(operator_id) and force)):
                # TBD: This exception list should probably not be hardcoded
                # here -- but it's not obvious whether it should be a cereconf
                # value (implying that only site admins can modify the list)
                # or a database table.
                raise CerebrumError("%s is an existing username" % local_part)

        # Then check whether the mailing list name is a legal one.
        if not (self._is_ok_mailing_list_name(local_part) or
                self.ba.is_postmaster(operator_id)):
            raise CerebrumError("Illegal mailing list name: %s" % listname)

        # Finally, we can start registering useful stuff
        # Register all relevant addresses for the list...
        if target_type == self.const.email_target_Sympa:
            self._register_sympa_list_addresses(listname, local_part, domain,
                                                delivery_host)
        else:
            raise CerebrumError("Unknown mail list target: %s" % target_type)
        # register auto spam and filter settings for the list
        self._register_spam_settings(listname, target_type)
        self._register_filter_settings(listname, target_type)

    # email create_sympa_list_alias <list-address> <new-alias>
    all_commands['email_create_sympa_list_alias'] = Command(
        ("email", "create_sympa_list_alias"),
        EmailAddress(help_ref="mailing_list_exist"),
        EmailAddress(help_ref="mailing_list"),
        YesNo(help_ref="yes_no_force", optional=True),
        perm_filter="can_email_list_create")
    def email_create_sympa_list_alias(self, operator, listname, address, force=False):
        """Create a secondary name for an existing Sympa list."""
        if isinstance(force, str):
            force = self._get_boolean(force)
        # The first thing we have to do is to locate the delivery
        # host. Postmasters do NOT want to allow people to specify a different
        # delivery host for alias than for the list that is being aliased. So,
        # find the ml's ET and fish out the server_id.
        self._validate_sympa_list(listname)
        local_part, domain = self._split_email_address(listname)
        ed = self._get_email_domain(domain)
        email_address = Email.EmailAddress(self.db)
        email_address.find_by_local_part_and_domain(local_part,
                                                    ed.entity_id)
        try:
            et = Email.EmailTarget(self.db)
            et.find(email_address.email_addr_target_id)
            delivery_host = Email.EmailServer(self.db)
            delivery_host.find(et.email_server_id)
        except Errors.NotFoundError:
            raise CerebrumError("Cannot alias list %s (missing delivery host)",
                                listname)

        return self._create_list_alias(operator, listname, address,
                                       self.const.email_target_Sympa,
                                       delivery_host, force_alias=force)

    def _create_list_alias(self, operator, listname, address, list_type,
                           delivery_host, force_alias=False):
        """Create an alias `address` for an existing mailing list `listname`.

        :type listname: basestring
        :param listname:
            Email address for an existing mailing list. This is the mailing
            list we are aliasing.

        :type address: basestring
        :param address: Email address which will be the alias.

        :type list_type: _EmailTargetCode instance
        :param list_type: List type we are processing.

        :type delivery_host: EmailServer instance or None.
        :param delivery_host:
          Host where delivery to the mail alias happens. It is the
          responsibility of the caller to check that this value makes sense in
          the context of the specified mailing list.
        """

        if list_type != self.const.email_target_Sympa:
            raise CerebrumError("Unknown list type %s for list %s" %
                                (self.const.EmailTarget(list_type), listname))
        lp, dom = self._split_email_address(address)
        ed = self._get_email_domain(dom)
        self.ba.can_email_list_create(operator.get_entity_id(), ed)
        self._validate_sympa_list(listname)
        if not force_alias:
            try:
                self._get_account(lp)
            except CerebrumError:
                pass
            else:
                raise CerebrumError, ("Won't create list-alias %s, as %s is an "
                                      "existing username") % (address, lp)
        self._register_sympa_list_addresses(listname, lp, dom, delivery_host)
        return "OK, list-alias '%s' created" % address

    def _report_deleted_EA(self, deleted_EA):
        """Send a message to postmasters informing them that a number of email
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
        # end email_info2string

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
        except:
            self.logger.info("Failed to send e-mail to %s", to_address)
            self.logger.info("Failed e-mail info: %s", repr(deleted_EA))
    # end _report_deleted_EA



    # email remove_sympa_list_alias <alias>
    all_commands['email_remove_sympa_list_alias'] = Command(
        ('email', 'remove_sympa_list_alias'),
        EmailAddress(help_ref='mailing_list_alias'),
        perm_filter='can_email_list_create')
    def email_remove_sympa_list_alias(self, operator, alias):
        lp, dom = self._split_email_address(alias, with_checks=False)
        ed = self._get_email_domain(dom)
        remove_addrs = [alias]
        self.ba.can_email_list_create(operator.get_entity_id(), ed)
        ea = Email.EmailAddress(self.db)
        et = Email.EmailTarget(self.db)

        for addr_format, pipe in self._sympa_addr2alias:
            addr = addr_format % {"local_part": lp,
                                  "domain": dom,}
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
        return "OK, removed alias %s and all auto registered aliases" % alias

    # email delete_sympa_list <run-host> <list-address>
    all_commands['email_delete_sympa_list'] = Command(
        ("email", "delete_sympa_list"),
        SimpleString(help_ref='string_exec_host'),
        EmailAddress(help_ref="mailing_list_exist"),
        YesNo(help_ref="yes_no_with_request"),
        fs=FormatSuggestion([("Deleted address: %s", ("address", ))]),
        perm_filter="can_email_list_delete")
    def email_delete_sympa_list(self, operator, run_host, listname,
                                force_request):
        """Remove a sympa list from cerebrum.

        @type force_request: bool
        @param force_request:
          Controls whether a bofhd request should be issued. This may come in
          handy, if we want to delete a sympa list from Cerebrum only and not
          issue any requests. misc cancel_request would have worked too, but
          it's better to merge this into one command.
        """

        # Check that the command exec host is sane
        if run_host not in cereconf.SYMPA_RUN_HOSTS:
            raise CerebrumError("run-host %s for sympa list %s is not valid" %
                                (run_host, listname))

        et, ea = self._get_email_target_and_address(listname)
        self.ba.can_email_list_delete(operator.get_entity_id(), ea)

        if et.email_target_type != self.const.email_target_Sympa:
            raise CerebrumError("email delete_sympa works on sympa lists only. "
                                "'%s' is not a sympa list (%s)" %
                                (listname,
                                 self.const.EmailTarget(et.email_target_type)))

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
        if not self._is_yes(force_request):
            return "OK, sympa list '%s' deleted (no bofhd request)" % listname

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

        return "OK, sympa list '%s' deleted (bofhd request issued)" % listname

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

        if addr.count('@') == 0:
            raise CerebrumError("E-mail address ({}) must include domain"
                                .format(addr))
        try:
            lp, dom = addr.split('@')
        except ValueError:
            raise CerebrumError("E-mail address ({}) must contain only one @"
                                .format(addr))
        if (addr != addr.lower() and dom not in
                cereconf.LDAP['rewrite_email_domain']):
            raise CerebrumError("E-mail address ({}) can't contain upper case "
                                "letters".format(addr))

        if not with_checks:
            return lp, dom

        ea = Email.EmailAddress(self.db)
        if not ea.validate_localpart(lp):
            raise CerebrumError("Invalid localpart '{}'".format(lp))
        return lp, dom

    def _validate_sympa_list(self, listname):
        """Check whether `listname` is the 'official' name for a Sympa mailing
        list.

        Raise an error, if it is not.
        """
        if self._get_sympa_list(listname) != listname:
            raise CerebrumError("%s is NOT the official Sympa list name" %
                                listname)
        return listname

    def _get_sympa_list(self, listname):
        """Try to return the 'official' sympa mailing list name, if it can at
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
            if (not et.email_target_alias or
                et.email_target_type != self.const.email_target_Sympa):
                # if it's not a Sympa ET, address cannot be sympa
                return False

            return True
        # end I_am_sympa

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

    def _get_all_related_maillist_targets(self, address):
        """This method locates and returns all ETs associated with the same ML.

        Given any address associated with a ML, this method returns all the
        ETs associated with that ML. E.g.: 'foo-subscribe@domain' for a Sympa
        ML will result in returning the ETs for 'foo@domain',
        'foo-owner@domain', 'foo-request@domain', 'foo-editor@domain',
        'foo-subscribe@domain' and 'foo-unsubscribe@domain'

        If address (EA) is not associated with a mailing list ET, this method
        raises an exception. Otherwise a list of ET entity_ids is returned.

        @type address: basestring
        @param address:
          One of the mail addresses associated with a mailing list.

        @rtype: sequence (of ints)
        @return:
          A sequence with entity_ids of all ETs related to the ML that address
          is related to.

        """

        # step 1, find the ET, check its type.
        et, ea = self._get_email_target_and_address(address)
        # Mapping from ML types to (x, y)-tuples, where x is a callable that
        # fetches the ML's official/main address, and y is a set of patterns
        # for EAs that are related to this ML.
        ml2action = {
            int(self.const.email_target_Sympa):
                (self._get_sympa_list, [x[0] for x in self._sympa_addr2alias]),
        }

        if int(et.email_target_type) not in ml2action:
            raise CerebrumError("'%s' is not associated with a mailing list" %
                                address)

        result = []
        get_official_address, patterns = ml2action[int(et.email_target_type)]
        # step 1, get official ML address (i.e. foo@domain)
        official_ml_address = get_official_address(ea.get_address())
        ea.clear()
        ea.find_by_address(official_ml_address)
        et.clear()
        et.find(ea.get_target_id())

        # step 2, get local_part and domain separated:
        local_part, domain = self._split_email_address(official_ml_address)

        # step 3, generate all 'derived'/'administrative' addresses, and
        # locate their ETs.
        result = set([et.entity_id,])
        for pattern in patterns:
            address = pattern % {"local_part": local_part, "domain": domain}

            # some of the addresses may be missing. It is not an error.
            try:
                ea.clear()
                ea.find_by_address(address)
            except Errors.NotFoundError:
                continue

            result.add(ea.get_target_id())

        return result

    def _is_ok_mailing_list_name(self, localpart):
        # originally this regexp was:^[a-z0-9.-]. postmaster however
        # needs to be able to recreate some of the older mailing lists
        # in sympa and '_' used to be a valid character in list names.
        # this may not be very wise, but the postmasters have promised
        # to be good and make sure not to abuse this :-). Jazz,
        # 2009-11-13
        if not re.match(r'^[a-z0-9.-]+$|^[a-z0-9._]+$', localpart):
            raise CerebrumError, "Illegal localpart: %s" % localpart
        if len(localpart) > 8 or localpart.count('-') or localpart == 'drift':
            return True
        return False

    # aliases that we must create for each sympa mailing list.
    # request,editor,-owner,subscribe,unsubscribe all come from sympa
    # owner- and -admin are the remnants of mailman
    _sympa_addr2alias = (
        # The first one *is* the official/primary name. Don't reshuffle.
        ('%(local_part)s@%(domain)s', "|SYMPA_QUEUE %(listname)s"),
        # Owner addresses...
        ('%(local_part)s-owner@%(domain)s', "|SYMPA_BOUNCEQUEUE %(listname)s"),
        ('%(local_part)s-admin@%(domain)s', "|SYMPA_BOUNCEQUEUE %(listname)s"),
        # Request addresses...
        ('%(local_part)s-request@%(domain)s',
             "|SYMPA_QUEUE %(local_part)s-request@%(domain)s"),
        ('owner-%(local_part)s@%(domain)s',
             "|SYMPA_QUEUE %(local_part)s-request@%(domain)s"),
        # Editor address...
        ('%(local_part)s-editor@%(domain)s',
            "|SYMPA_QUEUE %(local_part)s-editor@%(domain)s"),
        # Subscribe address...
        ('%(local_part)s-subscribe@%(domain)s',
            "|SYMPA_QUEUE %(local_part)s-subscribe@%(domain)s"),
        # Unsubscribe address...
        ('%(local_part)s-unsubscribe@%(domain)s',
            "|SYMPA_QUEUE %(local_part)s-unsubscribe@%(domain)s"),
    )
    _sympa_address_suffixes = ("-owner", "-admin", "-request", "-editor",
                               "-subscribe", "-unsubscribe",)
    _sympa_address_prefixes = ("owner-",)

    def _register_sympa_list_addresses(self, listname, local_part, domain,
                                       delivery_host):
        """Add list, request, editor, owner, subscribe and unsubscribe
        addresses to a sympa mailing list.

        :type listname: basestring
        :param listname:
          Sympa listname that the operation is about. listname is typically
          different from local_part@domain when we are creating an
          alias. local_part@domain is the alias, listname is the original
          listname. And since aliases should point to the 'original' ETs, we
          have to use listname to locate the ETs.

        :type local_part: basestring
        :param local_part: See domain

        :type domain: basestring
        :param domain:
          `local_part` and `domain` together represent a new list address that
          we want to create.

        @type delivery_host: EmailServer instance.
        @param delivery_host:
          EmailServer where e-mail to `listname` is to be delivered through.
        """

        if (delivery_host.email_server_type !=
            self.const.email_server_type_sympa):
            raise CerebrumError("Delivery host %s has wrong type %s for "
                                "sympa ML %s" %
                  (delivery_host.get_name(self.const.host_namespace),
                   self.const.EmailServerType(delivery_host.email_server_type),
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
            raise CerebrumError, ("The address %s@%s is already in use" %
                                  (local_part, domain))

        sympa = self._get_account("sympa", actype="PosixUser")
        primary_ea_created= False
        listname_lp, listname_domain = listname.split("@")

        # For each of the addresses we are supposed to create...
        for pattern, pipe_destination in self._sympa_addr2alias:
            address = pattern % locals()
            address_lp, address_domain = address.split("@")

            # pipe has to be derived from the original listname, since it's
            # used to locate the ET.
            pipe = pipe_destination % {"local_part": listname_lp,
                                       "domain": listname_domain,
                                       "listname": listname}

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
    # end _register_sympa_list_addresses


    # email create_multi <multi-address> <group>
    all_commands['email_create_multi'] = Command(
        ("email", "create_multi"),
        EmailAddress(help_ref="email_address"),
        GroupName(help_ref="group_name_dest"),
        perm_filter="can_email_multi_create")
    def email_create_multi(self, operator, addr, group):
        """Create en e-mail target of type 'multi' expanding to
        members of group, and associate the e-mail address with this
        target."""
        lp, dom = self._split_email_address(addr)
        ed = self._get_email_domain(dom)
        gr = self._get_group(group)
        self.ba.can_email_multi_create(operator.get_entity_id(), ed, gr)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.entity_id)
        except Errors.NotFoundError:
            pass
        else:
            raise CerebrumError, "Address <%s> is already in use" % addr
        et = Email.EmailTarget(self.db)
        et.populate(self.const.email_target_multi,
                    target_entity_type = self.const.entity_group,
                    target_entity_id = gr.entity_id)
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

    # email delete_multi <address>
    all_commands['email_delete_multi'] = Command(
        ("email", "delete_multi"),
        EmailAddress(help_ref="email_address"),
        fs=FormatSuggestion([("Deleted address: %s", ("address", ))]),
        perm_filter="can_email_multi_delete")
    def email_delete_multi(self, operator, addr):
        lp, dom = self._split_email_address(addr)
        ed = self._get_email_domain(dom)
        et, acc = self._get_email_target_and_account(addr)
        if et.email_target_type != self.const.email_target_multi:
            raise CerebrumError, "%s: Not a multi target" % addr
        if et.email_target_entity_type != self.const.entity_group:
            raise CerebrumError, "%s: Does not point to a group!" % addr
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
                raise CerebrumError, ("%s is not the primary address of "+
                                      "the target") % addr
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

    _rt_pipe = ("|/local/bin/rt-mailgate --action %(action)s --queue %(queue)s "
                "--url https://%(host)s/")
    # This assumes that the only RE meta character in _rt_pipe is the
    # leading pipe.
    _rt_patt = "^\\" + _rt_pipe % {'action': '(\S+)',
                                   'queue': '(\S+)',
                                   'host': '(\S+)'} + "$"

    # email rt_create queue[@host] address [force]
    all_commands['email_rt_create'] = Command(
        ("email", "rt_create"),
        RTQueue(), EmailAddress(),
        YesNo(help_ref="yes_no_force", optional=True),
        perm_filter='can_rt_create')
    def email_rt_create(self, operator, queuename, addr, force="No"):
        queue, host = self._resolve_rt_name(queuename)
        rt_dom = self._get_email_domain(host)
        op = operator.get_entity_id()
        self.ba.can_rt_create(op, domain=rt_dom)
        try:
            self._get_rt_email_target(queue, host)
        except CerebrumError:
            pass
        else:
            raise CerebrumError, "RT queue %s already exists" % queuename
        addr_lp, addr_domain_name = self._split_email_address(addr)
        addr_dom = self._get_email_domain(addr_domain_name)
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
            raise CerebrumError, "Illegal address for submission: %s" % addr
        try:
            et, ea = self._get_email_target_and_address(addr)
        except CerebrumError:
            pass
        else:
            raise CerebrumError, "Address <%s> is in use" % addr
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
            alias_dom = self._get_email_domain(dom)
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

    # email rt_delete queue[@host]
    all_commands['email_rt_delete'] = Command(
        ("email", "rt_delete"),
        EmailAddress(),
        fs=FormatSuggestion([("Deleted address: %s", ("address", ))]),
        perm_filter='can_rt_delete')
    def email_rt_delete(self, operator, queuename):
        queue, host = self._resolve_rt_name(queuename)
        rt_dom = self._get_email_domain(host)
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

    # email rt_add_address queue[@host] address
    all_commands['email_rt_add_address'] = Command(
        ('email', 'rt_add_address'),
        RTQueue(), EmailAddress(),
        perm_filter='can_rt_address_add')
    def email_rt_add_address(self, operator, queuename, address):
        queue, host = self._resolve_rt_name(queuename)
        rt_dom = self._get_email_domain(host)
        self.ba.can_rt_address_add(operator.get_entity_id(), domain=rt_dom)
        et = self._get_rt_email_target(queue, host)
        lp, dom = self._split_email_address(address)
        ed = self._get_email_domain(dom)
        if host != dom:
            self.ba.can_email_address_add(operator.get_entity_id(),
                                          domain=ed)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.entity_id)
            raise CerebrumError, "Address already exists (%s)" % address
        except Errors.NotFoundError:
            pass
        if not (self._is_ok_mailing_list_name(lp) or
                self.ba.is_postmaster(operator.get_entity_id())):
            raise CerebrumError, "Illegal queue address: %s" % address
        ea.clear()
        ea.populate(lp, ed.entity_id, et.entity_id)
        ea.write_db()
        return ("OK, added '%s' as e-mail address for '%s'" %
                (address, queuename))

    # email rt_remove_address queue address
    all_commands['email_rt_remove_address'] = Command(
        ('email', 'rt_remove_address'),
        RTQueue(), EmailAddress(),
        perm_filter='can_email_address_delete')
    def email_rt_remove_address(self, operator, queuename, address):
        queue, host = self._resolve_rt_name(queuename)
        rt_dom = self._get_email_domain(host)
        self.ba.can_rt_address_remove(operator.get_entity_id(), domain=rt_dom)
        et = self._get_rt_email_target(queue, host)
        return self._remove_email_address(et, address)

    # email rt_primary_address address
    all_commands['email_rt_primary_address'] = Command(
        ("email", "rt_primary_address"),
        RTQueue(), EmailAddress(),
        fs=FormatSuggestion([("New primary address: '%s'", ("address", ))]),
        perm_filter="can_rt_address_add")
    def email_rt_primary_address(self, operator, queuename, address):
        queue, host = self._resolve_rt_name(queuename)
        self.ba.can_rt_address_add(operator.get_entity_id(),
                                   domain=self._get_email_domain(host))
        rt = self._get_rt_email_target(queue, host)
        et, ea = self._get_email_target_and_address(address)
        if rt.entity_id != et.entity_id:
            raise CerebrumError, \
                  ("Address <%s> is not associated with RT queue %s" %
                   (address, queuename))
        return self._set_email_primary_address(et, ea, address)

    def _resolve_rt_name(self, queuename):
        """Return queue and host of RT queue as tuple."""
        if queuename.count('@') == 0:
            # Use the default host
            return queuename, "rt.uio.no"
        elif queuename.count('@') > 1:
            raise CerebrumError, "Invalid RT queue name: %s" % queuename
        return queuename.split('@')

    def _get_all_related_rt_targets(self, address):
        """This method locates and returns all ETs associated with the same RT
        queue.

        Given any address associated with a RT queue, this method returns
        all the ETs associated with that RT queue. E.g.: 'foo@domain' will return
        'foo@domain' and 'foo-comment@queuehost'

        If address (EA) is not associated with a RT queue, this method
        raises an exception. Otherwise a list of ET entity_ids is returned.

        @type address: basestring
        @param address:
          One of the mail addresses associated with a RT queue.

        @rtype: sequence (of ints)
        @return:
          A sequence with entity_ids of all ETs related to the RT queue that address
          is related to.

        """

        et = Email.EmailTarget(self.db)
        queue, host = self._get_rt_queue_and_host(address)
        targets = set([])
        for action in ("correspond", "comment"):
            alias = self._rt_pipe % { 'action': action, 'queue': queue,
                                      'host': host }
            try:
                et.clear()
                et.find_by_alias(alias)
            except Errors.NotFoundError:
                continue

            targets.add(et.entity_id)

        if not targets:
            raise CerebrumError, ("RT queue %s on host %s not found" %
                                  (queue, host))

        return targets

    # end _get_all_related_rt_targets

    def _get_rt_email_target(self, queue, host):
        et = Email.EmailTarget(self.db)
        try:
            et.find_by_alias(self._rt_pipe % { 'action': "correspond",
                                               'queue': queue, 'host': host })
        except Errors.NotFoundError:
            raise CerebrumError, ("Unknown RT queue %s on host %s" %
                                  (queue, host))
        return et

    def _get_rt_queue_and_host(self, address):
        et, addr = self._get_email_target_and_address(address)

        try:
            m = re.match(self._rt_patt, et.get_alias())
            return m.group(2), m.group(3)
        except AttributeError:
            raise CerebrumError("Could not get queue and host for %s" % address)

    # email migrate
    all_commands['email_migrate'] = Command(
        ("email", "migrate"),
        AccountName(help_ref="account_name", repeat=True),
        perm_filter='can_email_migrate')
    def email_migrate(self, operator, uname):
        acc = self._get_account(uname)
        op = operator.get_entity_id()
        self.ba.can_email_migrate(op, acc)
        for r in acc.get_spread():
            if r['spread'] == int(self.const.spread_uio_imap):
                raise CerebrumError, "%s is already an IMAP user" % uname
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

    # email move
    all_commands['email_move'] = Command(
        ("email", "move"),
        AccountName(help_ref="account_name", repeat=True),
        SimpleString(help_ref='string_email_host'),
        SimpleString(help_ref='string_email_move_type', optional=True),
        Date(optional=True),
        perm_filter='can_email_move')
    def email_move(self, operator, uname, server, move_type='file', when=None):
        acc = self._get_account(uname)
        self.ba.can_email_move(operator.get_entity_id(), acc)
        et = Email.EmailTarget(self.db)
        et.find_by_target_entity(acc.entity_id)
        old_server = et.email_server_id
        es = Email.EmailServer(self.db)
        try:
            es.find_by_name(server)
        except Errors.NotFoundError:
            raise CerebrumError, ("%s is not registered as an e-mail server") % server
        if old_server == es.entity_id:
            raise CerebrumError, "User is already at %s" % server

        # Explicitly check if move_type is 'file' or 'nofile'. Abort if it isn't
        if move_type == 'nofile':
            et.email_server_id = es.entity_id
            et.write_db()
            return "OK, updated e-mail server for %s (to %s)" % (uname, server)
        elif not move_type == 'file':
            raise CerebrumError, ("Unknown move_type '%s'; must be "
                                  "either 'file' or 'nofile'" % move_type)

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
            if not self.const.spread_uio_imap in spreads:
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
            raise CerebrumError, "can't move to non-IMAP server"
        return "OK, '%s' scheduled for move to '%s'" % (uname, server)

    # email pause
    all_commands['email_pause'] = Command(
        ("email", "pause"),
        SimpleString(help_ref='string_email_on_off'),
        AccountName(help_ref="account_name"),
        perm_filter='can_email_pause')
    def email_pause(self, operator, on_off, uname):
        et, acc = self._get_email_target_and_account(uname)

        # exchange-relatert-jazz
        # there is no point in registering mailPause for
        # Exchange mailboxes
        #if acc.has_spread(self.const.spread_exchange_account):
        #    return "Modifying mailPause for Exchange-mailboxes is not allowed!"

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
            raise CerebrumError, ('Mailpause is either \'ON\' or \'OFF\'')

    # email pause list
    all_commands['email_list_pause'] = Command(
        ("email", "list_pause"),
        perm_filter='can_email_pause',
        fs=FormatSuggestion([("Paused addresses:\n%s", ("paused", ))]),)
    def email_list_pause(self, operator):
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

    # email quota <uname>+ hardquota-in-mebibytes [softquota-in-percent]
    all_commands['email_quota'] = Command(
        ('email', 'quota'),
        AccountName(help_ref='account_name', repeat=True),
        Integer(help_ref='number_size_mib'),
        Integer(help_ref='number_percent', optional=True),
        perm_filter='can_email_set_quota')
    def email_quota(self, operator, uname, hquota,
                    squota=cereconf.EMAIL_SOFT_QUOTA):
        acc = self._get_account(uname)
        op = operator.get_entity_id()
        self.ba.can_email_set_quota(op, acc)
        if not str(hquota).isdigit() or not str(squota).isdigit():
            raise CerebrumError, "Quota must be numeric"
        hquota = int(hquota)
        squota = int(squota)
        if hquota < 100 and hquota != 0:
            raise CerebrumError, "The hard quota can't be less than 100 MiB"
        if hquota > 1024*1024:
            raise CerebrumError, "The hard quota can't be more than 1 TiB"
        if squota < 10 or squota > 99:
            raise CerebrumError, ("The soft quota must be in the interval "+
                                  "10% to 99%")
        et = Email.EmailTarget(self.db)
        try:
            et.find_by_target_entity(acc.entity_id)
        except Errors.NotFoundError:
            raise CerebrumError, ("The account %s has no e-mail data "+
                                  "associated with it") % uname
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
            # Cyrus will spew out errors telling us "user foo is not a cyrus-user".
            if not et.email_server_id:
                raise CerebrumError, ("The account %s has no e-mail server "+
                                      "associated with it") % uname
            es = Email.EmailServer(self.db)
            es.find(et.email_server_id)

            if es.email_server_type == self.const.email_server_type_cyrus:
                br = BofhdRequests(self.db, self.const)
                # if this operator has already asked for a quota change, but
                # process_bofh_requests hasn't run yet, delete the existing
                # request to avoid the annoying error message.
                for r in br.get_requests(operation=self.const.bofh_email_hquota,
                                         operator_id=op, entity_id=acc.entity_id):
                    br.delete_request(request_id=r['request_id'])
                br.add_request(op, br.now, self.const.bofh_email_hquota,
                               acc.entity_id, None)
        return "OK, set quota for '%s'" % uname

    # email add_filter filter address
    all_commands['email_add_filter'] = Command(
        ('email', 'add_filter'),
        SimpleString(help_ref='string_email_filter'),
        SimpleString(help_ref='string_email_target_name', repeat="True"),
        perm_filter='can_email_spam_settings') # _is_local_postmaster')

    def email_add_filter(self, operator, filter, address):
        """Add a filter to an existing e-mail target."""
        et, acc = self._get_email_target_and_account(address)
        self.ba.can_email_spam_settings(operator.get_entity_id(),
                                        acc, et)
        etf = Email.EmailTargetFilter(self.db)
        filter_code = self._get_constant(self.const.EmailTargetFilter, filter)

        target_ids = [et.entity_id]
        if et.email_target_type == self.const.email_target_Sympa:
            # The only way we can get here is if uname is actually an e-mail
            # address on its own.
            target_ids = self._get_all_related_maillist_targets(address)
        elif et.email_target_type == self.const.email_target_RT:
            target_ids = self._get_all_related_rt_targets(address)
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

    # email remove_filter filter address
    all_commands['email_remove_filter'] = Command(
        ('email', 'remove_filter'),
        SimpleString(help_ref='string_email_filter'),
        SimpleString(help_ref='string_email_target_name', repeat="True"),
        perm_filter='can_email_spam_settings') # _is_local_postmaster')

    def email_remove_filter(self, operator, filter, address):
        """Remove email fitler for account."""
        et, acc = self._get_email_target_and_account(address)
        self.ba.can_email_spam_settings(operator.get_entity_id(),
                                        acc, et)

        etf = Email.EmailTargetFilter(self.db)
        filter_code = self._get_constant(self.const.EmailTargetFilter, filter)
        target_ids = [et.entity_id]
        if et.email_target_type == self.const.email_target_Sympa:
            # The only way we can get here is if uname is actually an e-mail
            # address on its own.
            target_ids = self._get_all_related_maillist_targets(address)
        elif et.email_target_type == self.const.email_target_RT:
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
            raise CerebrumError("Could not find any filters %s for address %s "
                                "(or any related targets)" % (filter, address))

        return "Ok, removed filter %s for %s" % (filter, address)

    # email spam_level <level> <name>+
    # exchange-relatert-jazz
    # made it possible to use this cmd for adding spam_level
    # to dist group targets
    all_commands['email_spam_level'] = Command(
        ('email', 'spam_level'),
        SimpleString(help_ref='spam_level'),
        SimpleString(help_ref="dlgroup_or_account_name", repeat=True),
        perm_filter='can_email_spam_settings')
    def email_spam_level(self, operator, level, name):
        """Set the spam level for the EmailTarget associated with username.
        It is also possible for super users to pass the name of other email
        targets."""
        try:
            levelcode = int(self.const.EmailSpamLevel(level))
        except Errors.NotFoundError:
            raise CerebrumError("Spam level code not found: {}".format(level))
        try:
            et, acc = self._get_email_target_and_account(name)
        except CerebrumError, e:
            # check if a distribution-group with an appropriate target
            # is registered by this name
            try:
                et, grp = self._get_email_target_and_dlgroup(name)
            except CerebrumError, e:
                raise e
        self.ba.can_email_spam_settings(operator.get_entity_id(),
                                        acc, et) or \
                                        self.ba.is_postmaster(operator.get_entity_id())
        esf = Email.EmailSpamFilter(self.db)
        # All this magic with target ids is necessary to accomodate MLs (all
        # ETs "related" to the same ML should have the
        # spam settings should be processed )
        target_ids = [et.entity_id]
        # The only way we can get here is if uname is actually an e-mail
        # address on its own.
        if et.email_target_type == self.const.email_target_Sympa:
           target_ids = self._get_all_related_maillist_targets(name)
        elif et.email_target_type == self.const.email_target_RT:
           targets_ids = self._get_all_related_rt_targets(name)

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

        return "OK, set spam-level for '%s'" % name

    # email spam_action <action> <uname>+
    all_commands['email_spam_action'] = Command(
        ('email', 'spam_action'),
        SimpleString(help_ref='spam_action'),
        SimpleString(help_ref="dlgroup_or_account_name", repeat=True),
        perm_filter='can_email_spam_settings')
    def email_spam_action(self, operator, action, name):
        """Set the spam action for the EmailTarget associated with username.
        It is also possible for super users to pass the name of other email
        targets."""
        try:
            actioncode = int(self.const.EmailSpamAction(action))
        except Errors.NotFoundError:
            raise CerebrumError(
                "Spam action code not found: {}".format(action))
        try:
            et, acc = self._get_email_target_and_account(name)
        except CerebrumError, e:
            # check if a distribution-group with an appropriate target
            # is registered by this name
            try:
                et, grp = self._get_email_target_and_dlgroup(name)
            except CerebrumError, e:
                raise e
        self.ba.can_email_spam_settings(operator.get_entity_id(),
                                         acc, et) or \
                                      self.ba.is_postmaster(operator.get_entity_id())
        esf = Email.EmailSpamFilter(self.db)
        # All this magic with target ids is necessary to accomodate MLs (all
        # ETs "related" to the same ML should have the
        # spam settings should be processed )
        target_ids = [et.entity_id]
        # The only way we can get here is if uname is actually an e-mail
        # address on its own.
        if et.email_target_type == self.const.email_target_Sympa:
            target_ids = self._get_all_related_maillist_targets(name)
        elif et.email_target_type == self.const.email_target_RT:
            target_ids = self._get_all_related_rt_targets(name)

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

        return "OK, set spam-action for '%s'" % name

    # email tripnote on|off <uname> [<begin-date>]
    all_commands['email_tripnote'] = Command(
        ('email', 'tripnote'),
        SimpleString(help_ref='email_tripnote_action'),
        AccountName(help_ref='account_name'),
        SimpleString(help_ref='date', optional=True),
        perm_filter='can_email_tripnote_toggle')
    def email_tripnote(self, operator, action, uname, when=None):
        if action == 'on':
            enable = True
        elif action == 'off':
            enable = False
        else:
            raise CerebrumError, ("Unknown tripnote action '%s', choose one "+
                                  "of on or off") % action
        acc = self._get_account(uname)
        # exchange-relatert-jazz
        # For Exchange-mailboxes vacation must be registered via
        # Outlook/OWA since smart host solution for Exchange@UiO
        # could not be implemented. When migration to Exchange
        # is completed this method should be changed and adding
        # vacation for any account disallowed. Jazz (2013-11)
        if acc.has_spread(self.const.spread_exchange_account):
            return "Sorry, Exchange-users must enable vacation messages via OWA!"
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

    all_commands['email_list_tripnotes'] = Command(
        ('email', 'list_tripnotes'),
        AccountName(help_ref='account_name'),
        perm_filter='can_email_tripnote_toggle',
        fs=FormatSuggestion([
        ('%s%s -- %s: %s\n%s\n',
         ("dummy", format_day('start_date'), format_day('end_date'),
          "enable", "text"))]))
    def email_list_tripnotes(self, operator, uname):
        acc = self._get_account(uname)
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

    # email add_tripnote <uname> <text> <begin-date>[-<end-date>]
    all_commands['email_add_tripnote'] = Command(
        ('email', 'add_tripnote'),
        AccountName(help_ref='account_name'),
        SimpleString(help_ref='tripnote_text'),
        SimpleString(help_ref='string_from_to'),
        perm_filter='can_email_tripnote_edit')
    def email_add_tripnote(self, operator, uname, text, when=None):
        acc = self._get_account(uname)
        # exchange-relatert-jazz
        # For Exchange-mailboxes vacation must be registered via
        # OWA since smart host solution for Exchange@UiO
        # could not be implemented. When migration to Exchange
        # is completed this method should be changed and adding
        # vacation for any account disallowed. Jazz (2013-11)
        if acc.has_spread(self.const.spread_exchange_account):
            return "Sorry, Exchange-users must add vacation messages via OWA!"
        self.ba.can_email_tripnote_edit(operator.get_entity_id(), acc)
        date_start, date_end = self._parse_date_from_to(when)
        now = self._today()
        if date_end is not None and date_end < now:
            raise CerebrumError, "Won't add already obsolete tripnotes"
        ev = Email.EmailVacation(self.db)
        ev.find_by_target_entity(acc.entity_id)
        for v in ev.get_vacation():
            if date_start is not None and v['start_date'] == date_start:
                raise CerebrumError, ("There's a tripnote starting on %s "+
                                      "already") % str(date_start)[:10]

        # FIXME: The SquirrelMail plugin sends CR LF which xmlrpclib
        # (AFAICT) converts into LF LF.  Remove the double line
        # distance.  jbofh users have to send backslash n anyway, so
        # this won't affect common usage.
        text = text.replace('\n\n', '\n')
        text = text.replace('\\n', '\n')
        ev.add_vacation(date_start, text, date_end, enable=True)
        ev.write_db()
        return "OK, added tripnote for '%s'" % uname

    # email remove_tripnote <uname> [<when>]
    all_commands['email_remove_tripnote'] = Command(
        ('email', 'remove_tripnote'),
        AccountName(help_ref='account_name'),
        SimpleString(help_ref='date', optional=True),
        perm_filter='can_email_tripnote_edit')
    def email_remove_tripnote(self, operator, uname, when=None):
        acc = self._get_account(uname)
        self.ba.can_email_tripnote_edit(operator.get_entity_id(), acc)
        # TBD: This variable isn't used; is this call a sign of rot,
        # or is it here for input validation?
        start = self._parse_date(when)
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
                raise CerebrumError, "User %s has no stored tripnotes" % uname
            elif enabled:
                raise CerebrumError, "User %s has no enabled tripnotes" % uname
            else:
                raise CerebrumError, "User %s has no disabled tripnotes" % uname
        elif len(vacs) == 1:
            return vacs[0]['start_date']
        elif when is None:
            raise CerebrumError, ("User %s has more than one tripnote, "+
                                  "specify which one by adding the "+
                                  "start date to command") % uname
        start = self._parse_date(when)
        best = None
        for r in vacs:
            delta = abs (r['start_date'] - start)
            if best is None or delta < best_delta:
                best = r['start_date']
                best_delta = delta
        # TODO: in PgSQL, date arithmetic is in days, but casting
        # it to int returns seconds.  The behaviour is undefined
        # in the DB-API.
        if abs(int(best_delta)) > 1.5*86400:
            raise CerebrumError, ("There are no tripnotes starting "+
                                  "at %s") % when
        return best

    # email update <uname>
    # Anyone can run this command.  Ideally, it should be a no-op,
    # and we should remove it when that is true.
    all_commands['email_update'] = Command(
        ('email', 'update'),
        AccountName(help_ref='account_name', repeat=True))
    def email_update(self, operator, uname):
        acc = self._get_account(uname)
        acc.update_email_addresses()
        return "OK, updated e-mail address for '%s'" % uname

    # (email virus)

    def _get_email_target_and_address(self, address):
        """Returns a tuple consisting of the email target associated
        with address and the address object.  If there is no at-sign
        in address, assume it is an account name and return primary
        address.  Raises CerebrumError if address is unknown.
        """
        et = Email.EmailTarget(self.db)
        ea = Email.EmailAddress(self.db)
        if address.count('@') == 0:
            acc = self.Account_class(self.db)
            try:
                acc.find_by_name(address)
                # FIXME: We can't use Account.get_primary_mailaddress
                # since it rewrites special domains.
                et = Email.EmailTarget(self.db)
                et.find_by_target_entity(acc.entity_id)
                epa = Email.EmailPrimaryAddressTarget(self.db)
                epa.find(et.entity_id)
                ea.find(epa.email_primaddr_id)
            except Errors.NotFoundError:
                try:
                    dlgroup = Utils.Factory.get("DistributionGroup")(self.db)
                    dlgroup.find_by_name(address)
                    et = Email.EmailTarget(self.db)
                    et.find_by_target_entity(dlgroup.entity_id)
                    epa = Email.EmailPrimaryAddressTarget(self.db)
                    epa.find(et.entity_id)
                    ea.find(epa.email_primaddr_id)
                except Errors.NotFoundError:
                    raise CerebrumError, ("No such address: '%s'" % address)
        elif address.count('@') == 1:
            try:
                ea.find_by_address(address)
                et.find(ea.email_addr_target_id)
            except Errors.NotFoundError:
                raise CerebrumError, "No such address: '%s'" % address
        else:
            raise CerebrumError, "Malformed e-mail address (%s)" % address
        return et, ea

    def _get_email_target_and_account(self, address):
        """Returns a tuple consisting of the email target associated
        with address and the account if the target type is user.  If
        there is no at-sign in address, assume it is an account name.
        Raises CerebrumError if address is unknown."""
        et, ea = self._get_email_target_and_address(address)
        acc = None
        if et.email_target_type in (self.const.email_target_account,
                                    self.const.email_target_deleted):
            acc = self._get_account(et.email_target_entity_id, idtype='id')
        return et, acc

    def _get_email_target_and_dlgroup(self, address):
        """Returns a tuple consisting of the email target associated
        with address and the account if the target type is user.  If
        there is no at-sign in address, assume it is an account name.
        Raises CerebrumError if address is unknown."""
        et, ea = self._get_email_target_and_address(address)
        grp = None
        # what will happen if the target was a dl_group but is now
        # deleted? it's possible that we should have created a new
        # target_type = dlgroup_deleted, but it seemed redundant earlier
        # now, i'm not so sure (Jazz, 2013-12(
        if et.email_target_type in (self.const.email_target_dl_group,
                                    self.const.email_target_deleted):
            grp = self._get_group(et.email_target_entity_id, idtype='id',
                                    grtype="DistributionGroup")
        return et, grp

    def _get_address(self, etarget):
        """The argument can be
        - EmailPrimaryAddressTarget
        - EmailAddress
        - EmailTarget (look up primary address and return that, throw
        exception if there is no primary address)
        - integer (use as entity_id and look up that target's
        primary address)
        The return value is a text string containing the e-mail
        address.  Special domain names are not rewritten."""
        ea = Email.EmailAddress(self.db)
        if isinstance(etarget, (int, long, float)):
            epat = Email.EmailPrimaryAddressTarget(self.db)
            # may throw exception, let caller handle it
            epat.find(etarget)
            ea.find(epat.email_primaddr_id)
        elif isinstance(etarget, Email.EmailTarget):
            epat = Email.EmailPrimaryAddressTarget(self.db)
            epat.find(etarget.entity_id)
            ea.find(epat.email_primaddr_id)
        elif isinstance(etarget, Email.EmailPrimaryAddressTarget):
            ea.find(etarget.email_primaddr_id)
        elif isinstance(etarget, Email.EmailAddress):
            ea = etarget
        else:
            raise ValueError, "Unknown argument (%s)" % repr(etarget)
        ed = Email.EmailDomain(self.db)
        ed.find(ea.email_addr_domain_id)
        return ("%s@%s" % (ea.email_addr_local_part,
                           ed.email_domain_name))

    #
    # entity commands
    #

    # entity info
    all_commands['entity_info'] = None
    def entity_info(self, operator, entity_id):
        """Returns basic information on the given entity id"""
        entity = self._get_entity(ident=entity_id)
        return self._entity_info(entity)

    def _entity_info(self, entity):
        result = {}
        co = self.const
        result['type'] = str(co.EntityType(entity.entity_type))
        result['entity_id'] = entity.entity_id
        if entity.entity_type in \
            (co.entity_group, co.entity_account):
            result['creator_id'] = entity.creator_id
            result['create_date'] = entity.created_at
            result['expire_date'] = entity.expire_date
            # FIXME: Should be a list instead of a string, but text
            # clients doesn't know how to view such a list
            result['spread'] = ", ".join([str(co.Spread(r['spread']))
                                          for r in entity.get_spread()])
        if entity.entity_type == co.entity_group:
            result['name'] = entity.group_name
            result['description'] = entity.description
            result['visibility'] = entity.visibility
            try:
                result['gid'] = entity.posix_gid
            except AttributeError:
                pass
        elif entity.entity_type == co.entity_account:
            result['name'] = entity.account_name
            result['owner_id'] = entity.owner_id
            #result['home'] = entity.home
           # TODO: de-reference disk_id
            #result['disk_id'] = entity.disk_id
           # TODO: de-reference np_type
           # result['np_type'] = entity.np_type
        elif entity.entity_type == co.entity_person:
            result['name'] = entity.get_name(co.system_cached,
                                             getattr(co, cereconf.DEFAULT_GECOS_NAME))
            result['export_id'] = entity.export_id
            result['birthdate'] =  entity.birth_date
            result['description'] = entity.description
            result['gender'] = str(co.Gender(entity.gender))
            # make boolean
            result['deceased'] = entity.deceased_date
            names = []
            for name in entity.get_all_names():
                source_system = str(co.AuthoritativeSystem(name.source_system))
                name_variant = str(co.PersonName(name.name_variant))
                names.append((source_system, name_variant, name.name))
            result['names'] = names
            affiliations = []
            for row in entity.get_affiliations():
                affiliation = {}
                affiliation['ou'] = row['ou_id']
                affiliation['affiliation'] = str(co.PersonAffiliation(row.affiliation))
                affiliation['status'] = str(co.PersonAffStatus(row.status))
                affiliation['source_system'] = str(co.AuthoritativeSystem(row.source_system))
                affiliations.append(affiliation)
            result['affiliations'] = affiliations
        elif entity.entity_type == co.entity_ou:
            for attr in '''name acronym short_name display_name
                           sort_name'''.split():
                result[attr] = getattr(entity, attr)

        return result

    # entity accounts
    all_commands['entity_accounts'] = Command(
        ("entity", "accounts"), EntityType(default="person"), Id(),
        fs=FormatSuggestion("%7i %-10s %s", ("account_id", "name", format_day("expire")),
                            hdr="%7s %-10s %s" % ("Id", "Name", "Expire")))
    def entity_accounts(self, operator, entity_type, id):
        entity = self._get_entity(entity_type, id)
        account = self.Account_class(self.db)
        ret = []
        for r in account.list_accounts_by_owner_id(entity.entity_id,
                                                   entity.entity_type,
                                                   filter_expired=False):
            account = self._get_account(r['account_id'], idtype='id')

            ret.append({'account_id': r['account_id'],
                        'name': account.account_name,
                        'expire': account.expire_date})
        return ret

    # entity history
    all_commands['entity_history'] = Command(
        ("entity", "history"),
        Id(help_ref="id:target:account"),
        YesNo(help_ref='yes_no_all_op', optional=True, default="no"),
        Integer(optional=True, help_ref="limit_number_of_results"),
        fs=FormatSuggestion("%s [%s]: %s",
                            ("timestamp", "change_by", "message")),
        perm_filter='can_show_history')
    def entity_history(self, operator, entity, any="no", limit=100):
        ent = self.util.get_target(entity, restrict_to=[])
        self.ba.can_show_history(operator.get_entity_id(), ent)
        ret = []
        if self._get_boolean(any):
            kw = {'any_entity': ent.entity_id}
        else:
            kw = {'subject_entity': ent.entity_id}
        rows = list(self.db.get_log_events(0, **kw))
        try:
            limit = int(limit)
        except ValueError:
            raise CerebrumError, "Limit must be a number"

        for r in rows[-limit:]:
            ret.append(self._format_changelog_entry(r))
        return ret


    #
    # group commands
    #

    # FIXME - group_multi_add should later be renamed to group_add, when there's
    # enough time. group_padd and group_gadd should be removed as soon as
    # the other institutions doesn't depend on them any more.

    # group multi_add
    # jokim 2008-12-02 TBD: won't let it be used by jbofh, only wofh for now
    hidden_commands['group_multi_add'] = Command(
        ('group', 'multi_add'),
        MemberType(help_ref='member_type', default='account'),
        MemberName(help_ref='member_name_src', repeat=True),
        GroupName(help_ref='group_name_dest', repeat=True),
        perm_filter='can_alter_group')
    def group_multi_add(self, operator, member_type, src_name, dest_group):
        '''Adds a person, account or group to a given group.'''

        if member_type not in ('group', 'account', 'person', ):
            raise CerebrumError("Unknown member_type: %s" % (member_type))

        return self._group_add(operator, src_name, dest_group,
                               member_type=member_type)


    # group add
    all_commands['group_add'] = Command(
        ("group", "add"), AccountName(help_ref="account_name_src", repeat=True),
        GroupName(help_ref="group_name_dest", repeat=True),
        perm_filter='can_alter_group')
    def group_add(self, operator, src_name, dest_group):
        return self._group_add(operator, src_name, dest_group,
                               member_type="account")

    # group padd - add person to group
    all_commands['group_padd'] = Command(
        ("group", "padd"), PersonId(help_ref="id:target:person", repeat=True),
        GroupName(help_ref="group_name_dest", repeat=True),
        perm_filter='can_alter_group')
    def group_padd(self, operator, src_name, dest_group):
        return self._group_add(operator, src_name, dest_group,
                               member_type="person")
    # group gadd
    all_commands['group_gadd'] = Command(
        ("group", "gadd"), GroupName(help_ref="group_name_src", repeat=True),
        GroupName(help_ref="group_name_dest", repeat=True),
        perm_filter='can_alter_group')
    def group_gadd(self, operator, src_name, dest_group):
        return self._group_add(operator, src_name, dest_group,
                               member_type="group")

    def _group_add(self, operator, src_name, dest_group, member_type=None):
        if member_type == "group":
            src_entity = self._get_group(src_name)
        elif member_type == "account":
            src_entity = self._get_account(src_name)
        elif member_type == "person":
            try:
                src_entity = self.util.get_target(src_name,
                                                  restrict_to=['Person'])
            except Errors.TooManyRowsError:
                raise CerebrumError("Unexpectedly found more than one person")
        return self._group_add_entity(operator, src_entity, dest_group)

    def _group_add_entity(self, operator, src_entity, dest_group):
        group_d = self._get_group(dest_group)
        if operator:
            self.ba.can_alter_group(operator.get_entity_id(), group_d)
        src_name = self._get_name_from_object(src_entity)
        # Make the error message for the most common operator error
        # more friendly.  Don't treat this as an error, useful if the
        # operator has specified more than one entity.
        if group_d.has_member(src_entity.entity_id):
            return "%s is already a member of %s" % (src_name, dest_group)
        # Make sure that the src_entity does not have group_d as a
        # member already, to avoid a recursion well at export
        if src_entity.entity_type == self.const.entity_group:
            for row in src_entity.search_members(member_id=group_d.entity_id,
                                                 member_type=self.const.entity_group,
                                                 indirect_members=True,
                                                 member_filter_expired=False):
                if row['group_id'] == src_entity.entity_id:
                    return "Recursive memberships are not allowed (%s is member of %s)" % (dest_group, src_name)
        # This can still fail, e.g., if the entity is a member with a
        # different operation.
        try:
            group_d.add_member(src_entity.entity_id)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        # Warn the user about NFS filegroup limitations.
        nis_warning = ''
        for spread_name in cereconf.NIS_SPREADS:
            fg_spread = getattr(self.const, spread_name)
            for row in group_d.get_spread():
                if row['spread'] == fg_spread:
                    count = self._group_count_memberships(src_entity.entity_id,
                                                          fg_spread)
                    if count > 16:
                        nis_warning = (
                            'OK, added {source_name} to {group}\n'
                            'WARNING: {source_name} is now a member of '
                            '{amount_groups} NIS groups with spread {spread}.'
                            '\nActual membership lookups in NIS may not work '
                            'as expected if a user is member of more than 16 '
                            'NIS groups.'.format(source_name=src_name,
                                                 amount_groups=count,
                                                 spread=fg_spread,
                                                 group=dest_group))
        if nis_warning:
            return nis_warning
        return 'OK, added {source_name} to {group}'.format(
            source_name=src_name,
            group=dest_group)

    def _group_count_memberships(self, entity_id, spread):
        """Count how many groups of a given spread have entity_id as a member,
        either directly or indirectly."""

        gr = Utils.Factory.get("Group")(self.db)
        groups = list(gr.search(member_id=entity_id,
                                indirect_members=True,
                                spread=spread))
        return len(groups)
    # end _group_count_memberships


    # group add_entity
    all_commands['group_add_entity'] = None
    def group_add_entity(self, operator, src_entity_id, dest_group_id):
        """Adds a entity to a group. Both the source entity and the group
           should be entity IDs"""
        # tell _group_find later on that dest_group is a entity id
        dest_group = 'id:%s' % dest_group_id
        src_entity = self._get_entity(ident=src_entity_id)
        if not src_entity.entity_type in \
            (self.const.entity_account, self.const.entity_group):
            raise CerebrumError, \
              "Entity %s is not a legal type " \
              "to become group member" % src_entity_id
        return self._group_add_entity(operator, src_entity, dest_group)

    # group exchange_create
    all_commands['group_exchange_create'] = Command(
        ("group", "exchange_create"),
        GroupName(help_ref="group_name_new"),
        SimpleString(help_ref="group_disp_name", optional='true'),
        SimpleString(help_ref="string_dl_desc"),
        YesNo(help_ref='yes_no_from_existing', default='No'),
        fs=FormatSuggestion("Group created, internal id: %i", ("group_id",)),
        perm_filter='is_postmaster')
    def group_exchange_create(self, operator, groupname, displayname, description, from_existing=None):
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('No access to group')
        existing_group = False
        dl_group = Utils.Factory.get("DistributionGroup")(self.db)
        std_values = dl_group.ret_standard_attr_values(room=False)
        # although cerebrum supports different visibility levels
        # all groups are created visibile for all, and that vis
        # type is hardcoded. if the situation should change group
        # vis may be made into a parameter
        group_vis = self.const.group_visibility_all
        # display name language is standard for dist groups
        disp_name_language = dl_group.ret_standard_language()
        disp_name_variant = self.const.dl_group_displ_name
        managedby = cereconf.DISTGROUP_DEFAULT_ADMIN
        grp = Utils.Factory.get("Group")(self.db)
        try:
            grp.find_by_name(groupname)
            existing_group = True
        except Errors.NotFoundError:
            # nothing to do, inconsistencies are dealt with
            # further down
            pass
        if not displayname:
            displayname = groupname
        if existing_group and not self._is_yes(from_existing):
            return ('You choose not to create Exchange group from the '
                    'existing group %s' % groupname)
        try:
            if not existing_group:
                # one could imagine making a helper function in the future
                # _make_dl_group_new, as the functionality is required
                # both here and for the roomlist creation (Jazz, 2013-12)
                dl_group.new(operator.get_entity_id(),
                            group_vis,
                            groupname, description=description,
                            roomlist=std_values['roomlist'],
                            hidden=std_values['hidden'])
            else:
                dl_group.populate(roomlist=std_values['roomlist'],
                                  hidden=std_values['hidden'],
                                  parent=grp)
            dl_group.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        self._set_display_name(groupname, displayname,
                               disp_name_variant, disp_name_language)
        dl_group.create_distgroup_mailtarget()
        dl_group.add_spread(self.const.Spread(cereconf.EXCHANGE_GROUP_SPREAD))
        dl_group.write_db()
        return "Created Exchange group %s" % groupname

    # group exchange_info
    all_commands['group_exchange_info'] = Command(
        ("group", "exchange_info"), GroupName(help_ref="id:gid:name"),
        fs=FormatSuggestion([("Name:         %s\n" +
                              "Spreads:      %s\n" +
                              "Description:  %s\n" +
                              "Expire:       %s\n" +
                              "Entity id:    %i""",
                              ("name", "spread", "description",
                               format_day("expire_date"),
                               "entity_id")),
                             ("Moderator:    %s %s (%s)",
                              ('owner_type', 'owner', 'opset')),
                             ("Gid:          %i",
                              ('gid',)),
                             ("Members:      %s", ("members",)),

                             ("DisplayName:  %s",
                                 ('displayname',)),
                             ("Roomlist:     %s",
                                 ('roomlist',)),
                             ("Hidden:       %s",
                                 ('hidden',)),
                             ("PrimaryAddr:  %s",
                                 ('primary',)),
                             ("Aliases:      %s",
                                 ('aliases_1',)),
                             ("              %s",
                                 ('aliases',))]))
    def group_exchange_info(self, operator, groupname):
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('No access to group')

        co = self.const
        grp = self._get_group(groupname, grtype="DistributionGroup")
        gr_info = self._entity_info(grp)

        # Don't stop! Never give up!
        # We just delete stuff, thats faster to implement than fixing stuff.
        del gr_info['create_date']
        del gr_info['visibility']
        del gr_info['creator_id']
        del gr_info['type']
        ret = [ gr_info ]

        # find owners
        aot = BofhdAuthOpTarget(self.db)
        targets = []
        for row in aot.list(target_type='group', entity_id=grp.entity_id):
            targets.append(int(row['op_target_id']))
        ar = BofhdAuthRole(self.db)
        aos = BofhdAuthOpSet(self.db)
        for row in ar.list_owners(targets):
            aos.clear()
            aos.find(row['op_set_id'])
            id = int(row['entity_id'])
            en = self._get_entity(ident=id)
            if en.entity_type == co.entity_account:
                owner = en.account_name
            elif en.entity_type == co.entity_group:
                owner = en.group_name
            else:
                owner = '#%d' % id
            ret.append({'owner_type': str(co.EntityType(en.entity_type)),
                        'owner': owner,
                        'opset': aos.name})


        # Member stats are a bit complex, since any entity may be a
        # member. Collect them all and sort them by members.
        members = dict()
        for row in grp.search_members(group_id=grp.entity_id):
            members[row["member_type"]] = members.get(row["member_type"], 0) + 1

        # Produce a list of members sorted by member type
        ET = self.const.EntityType
        entries = ["%d %s(s)" % (members[x], str(ET(x)))
                   for x in sorted(members,
                                   lambda it1, it2:
                                     cmp(str(ET(it1)),
                                         str(ET(it2))))]

        ret.append({"members": ", ".join(entries)})
        # Find distgroup info
        roomlist = True if grp.roomlist == 'T' else False
        dgr_info = grp.get_distgroup_attributes_and_targetdata(
                                                        roomlist=roomlist)
        del dgr_info['group_id']
        del dgr_info['name']
        del dgr_info['description']

        # Yes, I'm gonna do it!
        tmp = {}
        for attr in ['displayname', 'roomlist']:
            if attr in dgr_info:
                tmp[attr] = dgr_info[attr]
        ret.append(tmp)

        tmp = {}
        for attr in ['hidden', 'primary']:
            if attr in dgr_info:
                tmp[attr] = dgr_info[attr]
        ret.append(tmp)

        if dgr_info.has_key('aliases'):
            if len(dgr_info['aliases']) > 0:
                ret.append({'aliases_1': dgr_info['aliases'].pop(0)})

            for alias in dgr_info['aliases']:
                ret.append({'aliases': alias})

        return ret

    # group exchange_remove
    all_commands['group_exchange_remove'] = Command(
        ("group", "exchange_remove"),
        GroupName(help_ref="group_name", repeat='true'),
        YesNo(help_ref='yes_no_expire_group', default='No'),
        perm_filter='is_postmaster')
    def group_exchange_remove(self, operator, groupname, expire_group=None):
        # check for appropriate priviledge
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('No access to group')
        dl_group = self._get_group(groupname, idtype='name',
                                   grtype="DistributionGroup")
        try:
            dl_group.delete_spread(self.const.Spread(cereconf.EXCHANGE_GROUP_SPREAD))
            dl_group.deactivate_dl_mailtarget()
            dl_group.demote_distribution()
        except Errors.NotFoundError:
            return "No Exchange group %s found" % groupname
        if self._is_yes(expire_group):
            # set expire in 90 dates for the remaining Cerebrum-group
            new_expire_date = DateTime.now() + DateTime.DateTimeDelta(90, 0, 0)
            dl_group.expire_date = new_expire_date
            dl_group.write_db()
        return "Exchange group data removed for %s" % groupname

    # group exchange_visibility
    all_commands['group_exchange_visibility'] = Command(
        ("group", "exchange_visibility"),
        GroupName(help_ref="group_name"),
        YesNo(optional=False, help_ref='yes_no_visible'),
        perm_filter='is_postmaster')
    def group_exchange_visibility(self, operator, groupname, visible):
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('No access to group')
        dl_group = self._get_group(groupname, idtype='name',
                                   grtype="DistributionGroup")
        visible = self._get_boolean(visible)
        dl_group.set_hidden(hidden='F' if visible else 'T')
        dl_group.write_db()
        return "OK, group {} is now {}".format(
            groupname, 'visible' if visible else 'hidden')

    # create roomlists, which are a special kind of distribution group
    # no re-use of existing groups allowed
    all_commands['group_roomlist_create'] = Command(
        ("group", "roomlist_create"),
        GroupName(help_ref="group_name_new"),
        SimpleString(help_ref="group_disp_name", optional='true'),
        SimpleString(help_ref="string_description"),
        fs=FormatSuggestion("Group created, internal id: %i", ("group_id",)),
        perm_filter='is_postmaster')

    def group_roomlist_create(self, operator, groupname, displayname,
                              description):
        """Create a new roomlist for Exchange."""
        # check for appropriate priviledge
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('No access to group')
        grp = Utils.Factory.get("Group")(self.db)
        try:
            grp.find_by_name(groupname)
            return "Cannot make an existing group into a roomlist"
        except Errors.NotFoundError:
            pass
        room_list = Utils.Factory.get("DistributionGroup")(self.db)
        std_values = room_list.ret_standard_attr_values(room=True)
        # although cerebrum supports different visibility levels
        # all groups are created visibile for all, and that vis
        # type is hardcoded. if the situation should change group
        # vis may be made into a parameter
        group_vis = self.const.group_visibility_all
        # the following attributes is not used and don't need to
        # be registered correctly
        # managedby is never exported to Exchange, hardcoded to
        # dl-dladmin@groups.uio.bo
        managedby = cereconf.DISTGROUP_DEFAULT_ADMIN
        # display name language is standard for dist groups
        disp_name_language = room_list.ret_standard_language()
        disp_name_variant = self.const.dl_group_displ_name
        # we could use _valid_address_exchange here in stead,
        # I'll leave as an exercise for a willing developer
        # :-) (Jazz, 2013-12)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_address(managedby)
        except Errors.NotFoundError:
            # should never happen unless default admin
            # dist group is deleted from Cerebrum
            return ('Default admin address does not exist, please contact'
                    ' cerebrum-drift@usit.uio.no for help!')
        if not displayname:
            displayname = groupname
        # using DistributionGroup.new(...)
        room_list.new(operator.get_entity_id(),
                      group_vis,
                      groupname, description=description,
                      roomlist=std_values['roomlist'],
                      hidden=std_values['hidden'])
        room_list.write_db()
        room_list.add_spread(self.const.Spread(cereconf.EXCHANGE_GROUP_SPREAD))
        self._set_display_name(groupname, displayname, disp_name_variant,
                               disp_name_language)
        room_list.write_db()

        # Try to set the default group moderator
        try:
            grp.clear()
            grp.find_by_name(cereconf.EXCHANGE_ROOMLIST_OWNER)
        except (Errors.NotFoundError, AttributeError):
            # If the group moderator group does not exist, or is not defined,
            # we won't set a group owner.
            pass
        else:
            op_set = BofhdAuthOpSet(self.db)
            op_set.find_by_name(cereconf.BOFHD_AUTH_GROUPMODERATOR)
            op_target = BofhdAuthOpTarget(self.db)
            op_target.populate(room_list.entity_id, 'group')
            op_target.write_db()
            role = BofhdAuthRole(self.db)
            role.grant_auth(grp.entity_id, op_set.op_set_id,
                            op_target.op_target_id)

        return "Made roomlist %s" % groupname

    ## group create
    # (all_commands is updated from BofhdCommonMethods)
    def group_create(self, operator, groupname, description):
        """Override group_create to double check that there doesn't exist an
        account with the same name.
        """
        ac = self.Account_class(self.db)
        try:
            ac.find_by_name(groupname)
        except Errors.NotFoundError:
            pass
        else:
            raise CerebrumError('An account exists with name: %s' % groupname)
        return super(BofhdExtension, self).group_create(operator, groupname,
                                                        description)

    # group request, like group create, but only send request to
    # the ones with the access to the 'group create' command
    # Currently send email to brukerreg@usit.uio.no
    all_commands['group_request'] = Command(
        ("group", "request"), GroupName(help_ref="group_name_new"),
        SimpleString(help_ref="string_description"), SimpleString(help_ref="string_spread"),
        GroupName(help_ref="group_name_moderator"))

    def group_request(self, operator, groupname, description, spread, moderator):
        opr = operator.get_entity_id()
        acc = self.Account_class(self.db)
        acc.find(opr)

        # checking if group already exists
        try:
            self._get_group(groupname)
        except CerebrumError:
            pass
        else:
            raise CerebrumError("Group %s already exists" % (groupname))

        # checking if moderator groups exist
        for mod in moderator.split(' '):
            try:
                self._get_group(mod)
            except CerebrumError:
                raise CerebrumError("Moderator group %s not found" % (mod))

        fromaddr = acc.get_primary_mailaddress()
        toaddr = cereconf.GROUP_REQUESTS_SENDTO
        if spread is None: spread = ""
        spreadstring = "(" + spread + ")"
        spreads = []
        spreads = re.split(" ", spread)
        subject = "Cerebrum group create request %s" % groupname
        body = []
        body.append("Please create a new group:")
        body.append("")
        body.append("Group-name: %s." % groupname)
        body.append("Description:  %s" % description)
        body.append("Requested by: %s" % fromaddr)
        body.append("Moderator: %s" % moderator)
        body.append("")
        body.append("group create %s \"%s\"" % (groupname, description))
        for spr in spreads:
            if spr and (self._get_constant(self.const.Spread, spr) in
                [self.const.spread_uio_nis_fg, self.const.spread_ifi_nis_fg,
                 self.const.spread_hpc_nis_fg]):
                pg = Utils.Factory.get('PosixGroup')(self.db)
                err_str = pg.illegal_name(groupname)
                if err_str:
                    if not isinstance(err_str, basestring):  # paranoia
                        err_str = 'Illegal groupname'
                    raise CerebrumError('Group-name error: {err_str}'.format(
                        err_str=err_str))
                body.append("group promote_posix %s" % groupname)
        if spread:
            body.append("spread add group %s %s" % (groupname, spreadstring))
        body.append("access grant Group-owner (%s) group %s" % (moderator, groupname))
        body.append("group info %s" % groupname)
        body.append("")
        body.append("")
        sendmail(toaddr, fromaddr, subject, "\n".join(body))
        return "Request sent to %s" % toaddr

    #  group def
    all_commands['group_def'] = Command(
        ('group', 'def'), AccountName(), GroupName(help_ref="group_name_dest"))

    def group_def(self, operator, accountname, groupname):
        account = self._get_account(accountname, actype="PosixUser")
        grp = self._get_group(groupname, grtype="PosixGroup")
        op = operator.get_entity_id()
        self.ba.can_set_default_group(op, account, grp)
        account.gid_id = grp.entity_id
        account.write_db()
        return "OK, set default-group for '%s' to '%s'" % (
            accountname, groupname)

    # group delete
    all_commands['group_delete'] = Command(
        ("group", "delete"), GroupName(), perm_filter='can_delete_group')

    def group_delete(self, operator, groupname):
        grp = self._get_group(groupname)
        self.ba.can_delete_group(operator.get_entity_id(), grp)
        if grp.group_name == cereconf.BOFHD_SUPERUSER_GROUP:
            raise CerebrumError("Can't delete superuser group")
        # exchange-relatert-jazz
        # it should not be possible to remove distribution groups via
        # bofh, as that would "orphan" e-mail target. if need be such groups
        # should be nuked using a cerebrum-side script.
        if grp.has_extension('DistributionGroup'):
            raise CerebrumError(
                "Cannot delete distribution groups, use 'group"
                " exchange_remove' to deactivate %s" % groupname)
        elif grp.has_extension('PosixGroup'):
            raise CerebrumError(
                "Cannot delete posix groups, use 'group demote_posix %s'"
                " before deleting." % groupname)
        elif grp.get_extensions():
            raise CerebrumError(
                "Cannot delete group %s, is type %r" % (groupname,
                                                        grp.get_extensions()))

        self._remove_auth_target("group", grp.entity_id)
        self._remove_auth_role(grp.entity_id)
        try:
            grp.delete()
        except self.db.DatabaseError, msg:
            if re.search("group_member_exists", str(msg)):
                raise CerebrumError(
                    ("Group is member of groups.  "
                     "Use 'group memberships group %s'") % grp.group_name)
            elif re.search("account_info_owner", str(msg)):
                raise CerebrumError(
                    ("Group is owner of an account.  "
                     "Use 'entity accounts group %s'") % grp.group_name)
            raise
        return "OK, deleted group '%s'" % groupname

    # group multi_remove
    # jokim 2008-12-02 TBD: removed from jbofh, but not wofh
    hidden_commands['group_multi_remove'] = Command(
        ("group", "multi_remove"),
        MemberType(help_ref='member_type', default='account'),
        MemberName(help_ref="member_name_src", repeat=True),
        GroupName(help_ref="group_name_dest", repeat=True),
        perm_filter='can_alter_group')
    def group_multi_remove(self, operator, member_type, src_name, dest_group):
        '''Removes a person, account or group from a given group.'''

        if member_type not in ('group', 'account', 'person', ):
            return 'Unknown member_type "%s"' % (member_type)
        self.ba.can_alter_group(operator.get_entity_id(),
                                self._get_group(dest_group))
        return self._group_remove(operator, src_name, dest_group,
                                  member_type=member_type)

    # FIXME - group_remove and group_gremove is now handled by
    # group_multi_remove(membertype='group'...), and should be removed as soon as the
    # other institutions has updated their dependency. group_multi_remove should then
    # be renamed to group_remove.

    # group remove
    all_commands['group_remove'] = Command(
        ("group", "remove"), AccountName(help_ref="account_name_member", repeat=True),
        GroupName(help_ref="group_name_dest", repeat=True))
    def group_remove(self, operator, src_name, dest_group):
        try:
            # First, check if this is a user we can set the password
            # for; if so, we should be allowed to remove this user
            # from groups, e.g. if we have LITA rights for the account
            account = self._get_account(src_name)
            self.ba.can_set_password(operator.get_entity_id(), account)
        except PermissionDenied, pd:
            # If that fails; check if we have rights pertaining to the
            # group in question
            group = self._get_group(dest_group)
            self.ba.can_alter_group(operator.get_entity_id(), group)
        return self._group_remove(operator, src_name, dest_group,
                                  member_type="account")

    # group gremove
    all_commands['group_gremove'] = Command(
        ("group", "gremove"), GroupName(help_ref="group_name_src", repeat=True),
        GroupName(help_ref="group_name_dest", repeat=True),
        perm_filter='can_alter_group')
    def group_gremove(self, operator, src_name, dest_group):
        self.ba.can_alter_group(operator.get_entity_id(),
                                self._get_group(dest_group))
        return self._group_remove(operator, src_name, dest_group,
                                  member_type="group")

    # group premove
    all_commands['group_premove'] = Command(
        ("group", "premove"), MemberName(help_ref='member_name_src', repeat=True),
        GroupName(help_ref="group_name_dest", repeat=True),
        perm_filter='can_alter_group')
    def group_premove(self, operator, src_name, dest_group):
        self.ba.can_alter_group(operator.get_entity_id(),
                                self._get_group(dest_group))
        return self._group_remove(operator, src_name, dest_group,
                                  member_type="person")

    def _group_remove(self, operator, src_name, dest_group, member_type=None):
        # jokim 2008-12-02 TBD: Is this bad? Added support for removing
        # members by their entity_id, as 'brukerinfo' (wofh) only knows
        # the entity_id.
        if isinstance(src_name, str) and not src_name.isdigit():
            idtype = 'name';
        else:
            idtype = 'id';

        if member_type == "group":
            src_entity = self._get_group(src_name, idtype=idtype)
        elif member_type == "account":
            src_entity = self._get_account(src_name, idtype=idtype)
        elif member_type == "person":
            if(idtype == 'name'):
                idtype = 'account'

            try:
                src_entity = self.util.get_target(src_name,
                          default_lookup=idtype, restrict_to=['Person'])
            except Errors.TooManyRowsError:
                raise CerebrumError("Unexpectedly found more than one person")
        else:
            raise CerebrumError("Unknown member_type: %s" % member_type)
        group_d = self._get_group(dest_group)
        return self._group_remove_entity(operator, src_entity, group_d)

    def _group_remove_entity(self, operator, member, group):
        member_name = self._get_name_from_object(member)
        if not group.has_member(member.entity_id):
            return ("%s isn't a member of %s" %
                    (member_name, group.group_name))
        if member.entity_type == self.const.entity_account:
            try:
                pu = Utils.Factory.get('PosixUser')(self.db)
                pu.find(member.entity_id)
                if pu.gid_id == group.entity_id:
                    raise CerebrumError("Can't remove %s from primary group %s" %
                                        (member_name, group.group_name))
            except Errors.NotFoundError:
                pass
        try:
            group.remove_member(member.entity_id)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return "OK, removed '%s' from '%s'" % (member_name, group.group_name)

    # group remove_entity
    all_commands['group_remove_entity'] = None
    def group_remove_entity(self, operator, member_entity, group_entity):
        group = self._get_entity(ident=group_entity)
        self.ba.can_alter_group(operator.get_entity_id(), group)
        member = self._get_entity(ident=member_entity)
        return self._group_remove_entity(operator, member, group)


    # group info
    all_commands['group_info'] = Command(
        ("group", "info"), GroupName(help_ref="id:gid:name"),
        fs=FormatSuggestion([("Name:         %s\n" +
                              "Spreads:      %s\n" +
                              "Description:  %s\n" +
                              "Expire:       %s\n" +
                              "Entity id:    %i""",
                              ("name", "spread", "description",
                               format_day("expire_date"),
                               "entity_id")),
                             ("Moderator:    %s %s (%s)",
                              ('owner_type', 'owner', 'opset')),
                             ("Gid:          %i",
                              ('gid',)),
                             ("Members:      %s", ("members",))]))
    def group_info(self, operator, groupname):
        # TODO: Group visibility should probably be checked against
        # operator for a number of commands
        try:
            grp = self._get_group(groupname, grtype="PosixGroup")
        except CerebrumError:
            if groupname.startswith('gid:'):
                gid = groupname.split(':',1)[1]
                raise CerebrumError("Could not find PosixGroup with gid=%s" % gid)
            grp = self._get_group(groupname)
        co = self.const
        ret = [ self._entity_info(grp) ]
        # find owners
        aot = BofhdAuthOpTarget(self.db)
        targets = []
        for row in aot.list(target_type='group', entity_id=grp.entity_id):
            targets.append(int(row['op_target_id']))
        ar = BofhdAuthRole(self.db)
        aos = BofhdAuthOpSet(self.db)
        for row in ar.list_owners(targets):
            aos.clear()
            aos.find(row['op_set_id'])
            id = int(row['entity_id'])
            en = self._get_entity(ident=id)
            if en.entity_type == co.entity_account:
                owner = en.account_name
            elif en.entity_type == co.entity_group:
                owner = en.group_name
            else:
                owner = '#%d' % id
            ret.append({'owner_type': str(co.EntityType(en.entity_type)),
                        'owner': owner,
                        'opset': aos.name})


        # Member stats are a bit complex, since any entity may be a
        # member. Collect them all and sort them by members.
        members = dict()
        for row in grp.search_members(group_id=grp.entity_id):
            members[row["member_type"]] = members.get(row["member_type"], 0) + 1

        # Produce a list of members sorted by member type
        ET = self.const.EntityType
        entries = ["%d %s(s)" % (members[x], str(ET(x)))
                   for x in sorted(members,
                                   lambda it1, it2:
                                     cmp(str(ET(it1)),
                                         str(ET(it2))))]

        ret.append({"members": ", ".join(entries)})
        return ret
    # end group_info


    # group list
    all_commands['group_list'] = Command(
        ("group", "list"), GroupName(),
        fs=FormatSuggestion("%-10s %-15s %-45s %-10s", ("type",
                                                        "user_name",
                                                        "full_name",
                                                        "expired"),
                            hdr="%-10s %-15s %-45s %-10s" % ("Type",
                                                             "Username",
                                                             "Fullname",
                                                             "Expired")))
    def group_list(self, operator, groupname):
        """List direct members of group"""
        def compare(a, b):
            return cmp(a['type'], b['type']) or \
                   cmp(a['user_name'], b['user_name'])
        group = self._get_group(groupname)
        ret = []
        now = DateTime.now()
        members = list(group.search_members(group_id=group.entity_id,
                                            indirect_members=False,
                                            member_filter_expired=False))
        if len(members) > cereconf.BOFHD_MAX_MATCHES and not self.ba.is_superuser(operator.get_entity_id()):
            raise CerebrumError("More than %d (%d) matches. Contact superuser "
                                "to get a listing for %s." %
                                (cereconf.BOFHD_MAX_MATCHES, len(members), groupname))
        ac = self.Account_class(self.db)
        pe = Utils.Factory.get('Person')(self.db)
        for x in self._fetch_member_names(members):
            if x['member_type'] == int(self.const.entity_account):
                ac.find(x['member_id'])
                try:
                    pe.find(ac.owner_id)
                    full_name = pe.get_name(self.const.system_cached,
                                            self.const.name_full)
                except Errors.NotFoundError:
                    full_name = ''
                user_name = x['member_name']
                ac.clear()
                pe.clear()
            else:
                full_name = x['member_name']
                user_name = '<non-account>'
            tmp = {'id': x['member_id'],
                   'type': str(self.const.EntityType(x['member_type'])),
                   'name': x['member_name'], # Compability with brukerinfo
                   'user_name': user_name,
                   'full_name': full_name,
                   'expired': None}
            if x["expire_date"] is not None and x["expire_date"] < now:
                tmp["expired"] = "expired"
            ret.append(tmp)

        ret.sort(compare)
        return ret

    def _fetch_member_names(self, iterable):
        """Locate names for elements in iterable.

        This is a convenience method. It helps us to locate names associated
        with certain member ids. For group and account members we try to fetch
        a name (there is at most one). For all other types we assume no such
        name exists.

        @type iterable: sequence (any iterable sequence) or a generator.
        @param iterable:
          A 'iterable' over db_rows that we have to map to names. Each db_row
          has a number of keys. This method examines 'member_type' and
          'member_id'. All others are ignored.

        @rtype: generator (over modified elements of L{iterable})
        @return:
          A generator over db_rows from L{iterable}. Each db_row gets an
          additional key, 'member_name' containing the name of the element or
          None, if no name can be located. The relative order of elements in
          L{iterable} is preserved. The underlying db_row objects are modified.
        """

        # TODO: hack to omit bug when inserting new key/value pairs in db_row
        ret = []

        for item in iterable:
            member_type = int(item["member_type"])
            member_id = int(item["member_id"])
            tmp = item.dict()
            tmp["member_name"] = self._get_entity_name(member_id, member_type)
            ret.append(tmp)
            #yield item
        return ret
    # end _fetch_member_names


    # group list_expanded
    all_commands['group_list_expanded'] = Command(
        ("group", "list_expanded"), GroupName(),
        fs=FormatSuggestion("%8i %10s %30s %25s",
                     ("member_id", "member_type", "member_name", "group_name"),
                     hdr="%8s %10s %30s %30s" % ("mem_id", "mem_type",
                                                 "member_name",
                                                 "is a member of group_name")))
    def group_list_expanded(self, operator, groupname):
        """List members of group after expansion"""
        group = self._get_group(groupname)
        result = list()
        type2str = lambda x: str(self.const.EntityType(int(x)))
        all_members = list(group.search_members(group_id=group.entity_id,
                                                indirect_members=True))
        if len(all_members) > cereconf.BOFHD_MAX_MATCHES and not self.ba.is_superuser(operator.get_entity_id()):
            raise CerebrumError("More than %d (%d) matches. Contact superuser"
                                "to get a listing for %s." %
                                (cereconf.BOFHD_MAX_MATCHES, len(all_members), groupname))
        for member in all_members:
            member_type = member["member_type"]
            member_id = member["member_id"]
            result.append({"member_id": member_id,
                           "member_type": type2str(member_type),
                           "member_name": self._get_entity_name(int(member_id),
                                                                member_type),
                           "group_name": self._get_entity_name(int(member["group_id"]),
                                                               self.const.entity_group),
                           })
        return result
    # end group_list_expanded

    # group personal <uname>+
    all_commands['group_personal'] = Command(
        ("group", "personal"), AccountName(repeat=True),
        fs=FormatSuggestion(
        "Personal group created and made primary, POSIX gid: %i\n"+
        "The user may have to wait a minute, then restart bofh to access\n"+
        "the 'group add' command", ("group_id",)),
        perm_filter='can_create_personal_group')
    def group_personal(self, operator, uname):
        """This is a separate command for convenience and consistency.
        A personal group is always a PosixGroup, and has the same
        spreads as the user."""
        acc = self._get_account(uname, actype="PosixUser")
        op = operator.get_entity_id()
        self.ba.can_create_personal_group(op, acc)
        # Create group
        group = self.Group_class(self.db)
        try:
            group.find_by_name(uname)
            raise CerebrumError, "Group %s already exists" % uname
        except Errors.NotFoundError:
            group.populate(creator_id=op,
                           visibility=self.const.group_visibility_all,
                           name=uname,
                           description=('Personal file group for %s' % uname))
            group.write_db()
        # Promote to PosixGroup
        pg = Utils.Factory.get('PosixGroup')(self.db)
        pg.populate(parent=group)
        try:
            pg.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        # Make user the owner of the group so he/she can administer it
        op_set = BofhdAuthOpSet(self.db)
        op_set.find_by_name(cereconf.BOFHD_AUTH_GROUPMODERATOR)
        op_target = BofhdAuthOpTarget(self.db)
        op_target.populate(group.entity_id, 'group')
        op_target.write_db()
        role = BofhdAuthRole(self.db)
        role.grant_auth(acc.entity_id, op_set.op_set_id, op_target.op_target_id)
        # Make user a member of his personal group
        self._group_add(None, uname, uname, member_type="account")
        # Add personal group-trait to group
        if hasattr(self.const, 'trait_personal_dfg'):
            pg.populate_trait(self.const.trait_personal_dfg,
                              target_id=acc.entity_id)
            pg.write_db()
        # Set group as primary group
        acc.gid_id = group.entity_id
        acc.write_db()
        return {'group_id': int(pg.posix_gid)}

    # group posix_create
    all_commands['group_promote_posix'] = Command(
        ("group", "promote_posix"), GroupName(),
        SimpleString(help_ref="string_description", optional=True),
        fs=FormatSuggestion("Group promoted to PosixGroup, posix gid: %i",
                            ("group_id",)), perm_filter='can_create_group')
    def group_promote_posix(self, operator, group, description=None):
        self.ba.can_create_group(operator.get_entity_id())
        is_posix = False
        try:
            self._get_group(group, grtype="PosixGroup")
            is_posix = True
        except CerebrumError:
            pass
        if is_posix:
            raise CerebrumError("%s is already a PosixGroup" % group)

        group=self._get_group(group)
        pg = Utils.Factory.get('PosixGroup')(self.db)
        pg.populate(parent=group)
        try:
            pg.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return {'group_id': int(pg.posix_gid)}

    # group posix_demote
    all_commands['group_demote_posix'] = Command(
        ("group", "demote_posix"), GroupName(), perm_filter='can_delete_group')

    def group_demote_posix(self, operator, group):
        try:
            grp = self._get_group(group, grtype="PosixGroup")
        except self.db.DatabaseError, msg:
            if "posix_user_gid" in str(msg):
                raise CerebrumError(
                    ("Assigned as primary group for posix user(s). "
                     "Use 'group list %s'") % grp.group_name)
            raise

        self.ba.can_delete_group(operator.get_entity_id(), grp)
        grp.demote_posix()

        return "OK, demoted '%s'" % group

    # group search
    all_commands['group_search'] = Command(
        ("group", "search"), SimpleString(help_ref="string_group_filter"),
        fs=FormatSuggestion("%8i %-16s %s", ("id", "name", "desc"),
                            hdr="%8s %-16s %s" % ("Id", "Name", "Description")),
        perm_filter='can_search_group')
    def group_search(self, operator, filter=""):
        self.ba.can_search_group(operator.get_entity_id())
        group = self.Group_class(self.db)
        if filter == "":
            raise CerebrumError, "No filter specified"
        filters = {'name': None,
                   'desc': None,
                   'spread': None,
                   'expired': "no"}
        rules = filter.split(",")
        for rule in rules:
            if rule.count(":"):
                filter_type, pattern = rule.split(":", 1)
            else:
                filter_type = 'name'
                pattern = rule
            if filter_type not in filters:
                raise CerebrumError, "Unknown filter type: %s" % filter_type
            filters[filter_type] = pattern
        if filters['name'] == '*' and len(rules) == 1:
            raise CerebrumError, "Please provide a more specific filter"
        # remap code_str to the actual constant object (the API requires it)
        if filters['spread']:
            filters['spread'] = self._get_constant(self.const.Spread,
                                                   filters["spread"])
        filter_expired = not self._get_boolean(filters['expired'])
        ret = []
        for r in group.search(spread=filters['spread'],
                              name=filters['name'],
                              description=filters['desc'],
                              filter_expired=filter_expired):
            ret.append({'id': r['group_id'],
                        'name': r['name'],
                        'desc': r['description'],
                        })
        return ret

    # group set_description
    all_commands['group_set_description'] = Command(
        ("group", "set_description"),
        GroupName(), SimpleString(help_ref="string_description"),
        perm_filter='can_alter_group')
    def group_set_description(self, operator, group, description):
        grp = self._get_group(group)
        self.ba.can_alter_group(operator.get_entity_id(), grp)
        grp.description = description
        grp.write_db()
        return "OK, description for group '%s' updated" % group

    # exchange-relatert-jazz
    # set display name, only for distribution groups and roomlists
    # for the time being, but may be interesting to use for other
    # groups as well
    all_commands['group_set_displayname'] = Command(
        ("group", 'set_display_name'),
        GroupName(help_ref="group_name"),
        SimpleString(help_ref="group_disp_name"),
        SimpleString(help_ref='display_name_language', default='nb'),
        perm_filter="is_postmaster")
    def group_set_displayname(self, operator, gname, disp_name, name_lang):
        # if this methos is to be made generic use
        # _get_group(grptype="Group")
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied('No access to group')
        name_variant = self.const.dl_group_displ_name
        self._set_display_name(gname, disp_name, name_variant, name_lang)
        return "Registered display name %s for %s" % (disp_name, gname)

    # helper method, will use in distgroup_ and roomlist_create
    # as they both require sett display_name
    def _set_display_name(self, gname, disp_name, name_var, name_lang):
        # if this method is to be of generic use the name variant must
        # be made into a parameter. it may be advisable to change
        # dl_group_displ_name into a more generic group_display_name
        # value in the future
        group = self._get_group(gname, grtype="DistributionGroup")
        if name_lang in self.language_codes:
            name_lang = int(_LanguageCode(name_lang))
        else:
            return "Could not set display name, invalid language code"
        group.add_name_with_language(name_var, name_lang,
                                     disp_name)
        group.write_db()

    # group set_expire
    all_commands['group_set_expire'] = Command(
        ("group", "set_expire"), GroupName(), Date(),
        perm_filter='can_expire_group')
    def group_set_expire(self, operator, group, expire):
        grp = self._get_group(group)
        self.ba.can_expire_group(operator.get_entity_id(), grp)
        grp.expire_date = self._parse_date(expire)
        grp.write_db()
        return "OK, set expire-date for '%s'" % group

    # group set_visibility
    all_commands['group_set_visibility'] = Command(
        ("group", "set_visibility"), GroupName(), GroupVisibility(),
        perm_filter='can_delete_group')
    def group_set_visibility(self, operator, group, visibility):
        grp = self._get_group(group)
        self.ba.can_delete_group(operator.get_entity_id(), grp)
        grp.visibility = self._get_constant(self.const.GroupVisibility,
                                            visibility, "visibility")
        grp.write_db()
        return "OK, set visibility for '%s'" % group

    # group memberships
    all_commands['group_memberships'] = Command(
        ('group', 'memberships'), EntityType(default="account"),
        Id(), Spread(optional=True, help_ref='spread_filter'),
        fs=FormatSuggestion(
        "%-9s %-18s", ("memberop", "group"),
        hdr="%-9s %-18s" % ("Operation", "Group")))
    def group_memberships(self, operator, entity_type, id,
                          spread=None):
        entity = self._get_entity(entity_type, id)
        group = self.Group_class(self.db)
        co = self.const
        if spread is not None:
            spread = self._get_constant(self.const.Spread, spread, "spread")
        ret = []
        for row in group.search(member_id=entity.entity_id, spread=spread):
            ret.append({'memberop': str(co.group_memberop_union),
                        'entity_id': row["group_id"],
                        'group': row["name"],
                        'description': row["description"],
                       })
        ret.sort(lambda a,b: cmp(a['group'], b['group']))
        return ret

    #
    # misc commands
    #

    # misc affiliations
    all_commands['misc_affiliations'] = Command(
        ("misc", "affiliations"),
        fs=FormatSuggestion("%-14s %-14s %s", ('aff', 'status', 'desc'),
                            hdr="%-14s %-14s %s" % ('Affiliation', 'Status',
                                                    'Description')))
    def misc_affiliations(self, operator):
        tmp = {}
        duplicate_check_list = list()
        for co in self.const.fetch_constants(self.const.PersonAffStatus):
            aff = six.text_type(co.affiliation)
            if aff not in tmp:
                tmp[aff] = [{'aff': aff,
                             'status': '',
                             'desc': co.affiliation.description}]
            status = six.text_type(co._get_status())
            if (aff, status) in duplicate_check_list:
                continue
            tmp[aff].append({'aff': '',
                             'status': status,
                             'desc': co.description})
            duplicate_check_list.append((aff, status))
        # fetch_constants returns a list sorted according to the name
        # of the constant.  Since the name of the constant and the
        # affiliation status usually are kept related, the list for
        # each affiliation will tend to be sorted as well.  Not so for
        # the affiliations themselves.
        keys = tmp.keys()
        keys.sort()
        ret = []
        for k in keys:
            for r in tmp[k]:
                ret.append(r)
        return ret

    all_commands['misc_change_request'] = Command(
        ("misc", "change_request"),
        Id(help_ref="id:request_id"), DateTimeString())

    def misc_change_request(self, operator, request_id, datetime):
        if not request_id:
            raise CerebrumError('Request id required')
        if not datetime:
            raise CerebrumError('Date required')
        datetime = self._parse_date(datetime)
        br = BofhdRequests(self.db, self.const)
        old_req = br.get_requests(request_id=request_id)
        if not old_req:
            raise CerebrumError("There is no request with id=%s" % request_id)
        else:
            # If there is anything, it's at most one
            old_req = old_req[0]
        # If you are allowed to cancel a request, you can change it :)
        self.ba.can_cancel_request(operator.get_entity_id(), request_id)
        br.delete_request(request_id=request_id)
        br.add_request(operator.get_entity_id(), datetime,
                       old_req['operation'], old_req['entity_id'],
                       old_req['destination_id'],
                       old_req['state_data'])
        return "OK, altered request %s" % request_id

    # misc check_password
    all_commands['misc_check_password'] = Command(
        ("misc", "check_password"), AccountPassword())
    def misc_check_password(self, operator, password):
        ac = self.Account_class(self.db)
        try:
            check_password(password, ac, structured=False)
        except RigidPasswordNotGoodEnough as e:
            # tragically converting utf-8 -> unicode -> latin1
            # since bofh still speaks latin1
            raise CerebrumError('Bad password: {err_msg}'.format(
                err_msg=str(e).decode('utf-8').encode('latin-1')))
        except PhrasePasswordNotGoodEnough as e:
            raise CerebrumError('Bad passphrase: {err_msg}'.format(
                err_msg=str(e).decode('utf-8').encode('latin-1')))
        except PasswordNotGoodEnough as e:
            # should be used for a default (no style) message
            # used for backward compatibility paranoia reasons here
            raise CerebrumError('Bad password: {err_msg}'.format(err_msg=e))
        crypt = ac.encrypt_password(self.const.Authentication("crypt3-DES"),
                                    password)
        md5 = ac.encrypt_password(self.const.Authentication("MD5-crypt"),
                                  password)
        sha256 = ac.encrypt_password(self.const.auth_type_sha256_crypt, password)
        sha512 = ac.encrypt_password(self.const.auth_type_sha512_crypt, password)
        return ("OK.\n  crypt3-DES:   %s\n  MD5-crypt:    %s\n" % (crypt, md5) +
                "  SHA256-crypt: %s\n  SHA512-crypt: %s" % (sha256, sha512))

    # misc clear_passwords
    all_commands['misc_clear_passwords'] = Command(
        ("misc", "clear_passwords"), AccountName(optional=True))
    def misc_clear_passwords(self, operator, account_name=None):
        operator.clear_state(state_types=('new_account_passwd', 'user_passwd'))
        return "OK, passwords cleared"


    all_commands['misc_dadd'] = Command(
        ("misc", "dadd"), SimpleString(help_ref='string_host'), DiskId(),
        perm_filter='can_create_disk')
    def misc_dadd(self, operator, hostname, diskname):
        host = self._get_host(hostname)
        self.ba.can_create_disk(operator.get_entity_id(), host)

        if not diskname.startswith("/"):
            raise CerebrumError("'%s' does not start with '/'" % diskname)

        if cereconf.VALID_DISK_TOPLEVELS is not None:
            toplevel_mountpoint = diskname.split("/")[1]
            if toplevel_mountpoint not in cereconf.VALID_DISK_TOPLEVELS:
                raise CerebrumError("'%s' is not a valid toplevel mountpoint"
                                    " for disks" % toplevel_mountpoint)

        disk = Utils.Factory.get('Disk')(self.db)
        disk.populate(host.entity_id, diskname, 'uio disk')
        try:
            disk.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        if len(diskname.split("/")) != 4:
            return "OK.  Warning: disk did not follow expected pattern."
        return "OK, added disk '%s' at %s" % (diskname, hostname)


    all_commands['misc_samba_mount'] = Command(
        ("misc", "samba_mount"), DiskId(),DiskId())
    def misc_samba_mount(self, operator, hostname, mountname):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        from Cerebrum.modules import MountHost
        mount_host = MountHost.MountHost(self.db)

        if hostname == 'delete':
            try:
                host = self._get_host(mountname)
                mount_host.find(host.entity_id)
                mount_host.delete_mount()
                return "Deleted %s from mount_host" % host.name

            except Errors.NotFoundError:
                raise CerebrumError, "Unknown mount_host: %s" % host.name

        elif hostname == 'list':
            if mountname == 'all':
                ename = Entity.EntityName(self.db)
                list_all = "%-16s%-16s\n" % ("host_name", "mount_name")
                for line in mount_host.list_all():
                    m_host_name = self._get_host(int(line['mount_host_id']))
                    list_all = "%s%-16s%-16s\n" % (list_all,
                                m_host_name.name, line['mount_name'])
                return list_all
            else:
                host = self._get_host(mountname)
                try:
                    mount_host.find(host.entity_id)
                    return "%s -> %s" % (mountname, mount_host.mount_name)
                except Errors.NotFoundError:
                    raise CerebrumError, "Unknown mount_host: %s" % host.name

        else:
            host = self._get_host(hostname)
            m_host = self._get_host(mountname)
            try:
                mount_host.find(host.entity_id)
                mount_host.mount_name = m_host.name
                mount_host.host_id = m_host.entity_id

            except Errors.NotFoundError:
                mount_host.populate(host.entity_id,
                                m_host.entity_id, m_host.name)

            mount_host.write_db()
            return "Updated samba mountpoint: %s on %s" % (m_host.name,
                        host.name)


    # misc dls is deprecated, and can probably be removed without
    # anyone complaining much.
    all_commands['misc_dls'] = Command(
        ("misc", "dls"), SimpleString(help_ref='string_host'),
        fs=FormatSuggestion("%-8i %-8i %s", ("disk_id", "host_id", "path",),
                            hdr="DiskId   HostId   Path"))
    def misc_dls(self, operator, hostname):
        return self.disk_list(operator, hostname)

    all_commands['disk_list'] = Command(
        ("disk", "list"), SimpleString(help_ref='string_host'),
        fs=FormatSuggestion("%-13s %11s  %s",
                            ("hostname", "pretty_quota", "path",),
                            hdr="Hostname    Default quota  Path"))
    def disk_list(self, operator, hostname):
        host = self._get_host(hostname)
        disks = {}
        disk = Utils.Factory.get('Disk')(self.db)
        hquota = host.get_trait(self.const.trait_host_disk_quota)
        if hquota:
            hquota = hquota['numval']
        for row in disk.list(host.host_id):
            disk.clear()
            disk.find(row['disk_id'])
            dquota = disk.get_trait(self.const.trait_disk_quota)
            if dquota is None:
                def_quota = None
                pretty_quota = '<none>'
            else:
                if dquota['numval'] is None:
                    def_quota = hquota
                    if hquota is None:
                        pretty_quota = '(no default)'
                    else:
                        pretty_quota = '(%d MiB)' % def_quota
                else:
                    def_quota = dquota['numval']
                    pretty_quota = '%d MiB' % def_quota
            disks[row['disk_id']] = {'disk_id': row['disk_id'],
                                     'host_id': row['host_id'],
                                     'hostname': hostname,
                                     'def_quota': def_quota,
                                     'pretty_quota': pretty_quota,
                                     'path': row['path']}
        disklist = disks.keys()
        disklist.sort(lambda x, y: cmp(disks[x]['path'], disks[y]['path']))
        ret = []
        for d in disklist:
            ret.append(disks[d])
        return ret

    all_commands['disk_quota'] = Command(
        ("disk", "quota"), SimpleString(help_ref='string_host'), DiskId(),
        SimpleString(help_ref='disk_quota_set'),
        perm_filter='can_set_disk_default_quota')
    def disk_quota(self, operator, hostname, diskname, quota):
        host = self._get_host(hostname)
        disk = self._get_disk(diskname, host_id=host.entity_id)[0]
        self.ba.can_set_disk_default_quota(operator.get_entity_id(),
                                           host=host, disk=disk)
        old = disk.get_trait(self.const.trait_disk_quota)
        if quota.lower() == 'none':
            if old:
                disk.delete_trait(self.const.trait_disk_quota)
            return "OK, no quotas on %s" % diskname
        elif quota.lower() == 'default':
            disk.populate_trait(self.const.trait_disk_quota,
                                numval=None)
            disk.write_db()
            return "OK, using host default on %s" % diskname
        elif quota.isdigit():
            disk.populate_trait(self.const.trait_disk_quota,
                                numval=int(quota))
            disk.write_db()
            return "OK, default quota on %s is %d" % (diskname, int(quota))
        else:
            raise CerebrumError, "Invalid quota value '%s'" % quota

    all_commands['misc_drem'] = Command(
        ("misc", "drem"), SimpleString(help_ref='string_host'), DiskId(),
        perm_filter='can_remove_disk')
    def misc_drem(self, operator, hostname, diskname):
        host = self._get_host(hostname)
        self.ba.can_remove_disk(operator.get_entity_id(), host)
        disk = self._get_disk(diskname, host_id=host.entity_id)[0]
        # FIXME: We assume that all destination_ids are entities,
        # which would ensure that the disk_id number can't represent a
        # different kind of entity.  The database does not constrain
        # this, however.
        br = BofhdRequests(self.db, self.const)
        if br.get_requests(destination_id=disk.entity_id):
            raise CerebrumError, ("There are pending requests. Use "+
                                  "'misc list_requests disk %s' to view "+
                                  "them.") % diskname
        account = self.Account_class(self.db)
        for row in account.list_account_home(disk_id=disk.entity_id,
                                             filter_expired=False):
            if row['disk_id'] is None:
                continue
            if row['status'] == int(self.const.home_status_on_disk):
                raise CerebrumError, ("One or more users still on disk " +
                                      "(e.g. %s)" % row['entity_name'])
            account.clear()
            account.find(row['account_id'])
            ah = account.get_home(row['home_spread'])
            account.set_homedir(
                current_id=ah['homedir_id'], disk_id=None,
                home=account.resolve_homedir(disk_path=row['path'], home=row['home']))
        self._remove_auth_target("disk", disk.entity_id)
        try:
            disk.delete()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return "OK, %s deleted" % diskname

    all_commands['misc_hadd'] = Command(
        ("misc", "hadd"), SimpleString(help_ref='string_host'),
        perm_filter='can_create_host')
    def misc_hadd(self, operator, hostname):
        self.ba.can_create_host(operator.get_entity_id())
        host = Utils.Factory.get('Host')(self.db)
        host.populate(hostname, 'uio host')
        try:
            host.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return "OK, added host '%s'" % hostname

    all_commands['misc_hrem'] = Command(
        ("misc", "hrem"), SimpleString(help_ref='string_host'),
        perm_filter='can_remove_host')
    def misc_hrem(self, operator, hostname):
        self.ba.can_remove_host(operator.get_entity_id())
        host = self._get_host(hostname)
        self._remove_auth_target("host", host.host_id)
        try:
            host.delete()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return "OK, %s deleted" % hostname

    # See hack in list_command
    def host_info(self, operator, hostname, policy=False):
        ret = []
        # More hacks follow.
        # Call the DNS module's host_info command for data:
        dns_err = None
        try:
            from Cerebrum.modules.dns.bofhd_dns_cmds import BofhdExtension as DnsCmds
            from Cerebrum.modules.dns import Utils as DnsUtils
            from Cerebrum.modules.dns.bofhd_dns_utils import DnsBofhdUtils
            zone = self.const.DnsZone("uio")
            # Avoid Python's type checking.  The BofhdExtension this
            # "self" is an instance of is different from the
            # BofhdExtension host_info expects.  By using a function
            # reference, it suffices that "self" we pass in supports
            # the same API.
            host_info = DnsCmds.__dict__.get('host_info')
            # To support the API, we add some stuff to this object.
            # Ugh.  Better hope this doesn't stomp on anything.
            self._find = DnsUtils.Find(self.db, zone)
            self.mb_utils = DnsBofhdUtils(self.db, self.logger, zone)
            self.dns_parser = DnsUtils.DnsParser(self.db, zone)
            ret = host_info(self, operator, hostname, policy=policy)
        except CerebrumError, dns_err:
            # Even though the DNS module doesn't recognise the host, the
            # standard host_info could still have some info. We should therefore
            # continue and see if we could get more info.
            pass
        # Other exceptions are faults and should cause trouble
        # TODO: make it possible to check if the DNS module are in use by the
        # active instance.

        try:
            host = self._get_host(hostname)
        except CerebrumError:
            # Only return data from the DNS module
            if dns_err is not None:
                raise dns_err
            return ret
        ret = [{'hostname': hostname,
                'desc': host.description}] + ret
        hquota = host.get_trait(self.const.trait_host_disk_quota)
        if hquota and hquota['numval']:
            ret.append({'def_disk_quota': hquota['numval']})
        return ret

    all_commands['host_disk_quota'] = Command(
        ("host", "disk_quota"), SimpleString(help_ref='string_host'),
        SimpleString(help_ref='disk_quota_set'),
        perm_filter='can_set_disk_default_quota')
    def host_disk_quota(self, operator, hostname, quota):
        host = self._get_host(hostname)
        self.ba.can_set_disk_default_quota(operator.get_entity_id(),
                                           host=host)
        old = host.get_trait(self.const.trait_host_disk_quota)
        if (quota.lower() == 'none' or quota.lower() == 'default' or
            (quota.isdigit() and int(quota) == 0)):
            # "default" doesn't make much sense, but the help text
            # says it's a valid value.
            if old:
                disk.delete_trait(self.const.trait_disk_quota)
            return "OK, no default quota on %s" % hostname
        elif quota.isdigit() and int(quota) > 0:
            host.populate_trait(self.const.trait_host_disk_quota,
                                numval=int(quota))
            host.write_db()
            return "OK, default quota on %s is %d" % (hostname, int(quota))
        else:
            raise CerebrumError("Invalid quota value '%s'" % quota)
        pass

    def _remove_auth_target(self, target_type, target_id):
        """This function should be used whenever a potential target
        for authorisation is deleted.
        """
        ar = BofhdAuthRole(self.db)
        aot = BofhdAuthOpTarget(self.db)
        for r in aot.list(entity_id=target_id, target_type=target_type):
            aot.clear()
            aot.find(r['op_target_id'])
            # We remove all auth_role entries first so that there
            # are no references to this op_target_id, just in case
            # someone adds a foreign key constraint later.
            for role in ar.list(op_target_id=r["op_target_id"]):
                ar.revoke_auth(role['entity_id'],
                               role['op_set_id'],
                               r['op_target_id'])
            aot.delete()

    def _remove_auth_role(self, entity_id):
        """This function should be used whenever a potentially
        authorised entity is deleted.
        """
        ar = BofhdAuthRole(self.db)
        aot = BofhdAuthOpTarget(self.db)
        for r in ar.list(entity_id):
            ar.revoke_auth(entity_id, r['op_set_id'], r['op_target_id'])
            # Also remove targets if this was the last reference from
            # auth_role.
            remaining = ar.list(op_target_id=r['op_target_id'])
            if len(remaining) == 0:
                aot.clear()
                aot.find(r['op_target_id'])
                aot.delete()

    all_commands['misc_list_passwords'] = Command(
        ("misc", "list_passwords"),
        fs=FormatSuggestion(
            "%-8s %-20s %s", ("account_id", "operation", "password"),
            hdr="%-8s %-20s %s" % ("Id", "Operation", "Password")))

    def misc_list_passwords(self, operator, *args):
        u""" List passwords in cache. """
        # NOTE: We keep the *args argument for backwards compability.
        cache = self._get_cached_passwords(operator)
        if not cache:
            raise CerebrumError("No passwords in session")
        return cache

    all_commands['misc_list_bofhd_request_types'] = Command(
        ("misc", "list_bofhd_request_types"),
        fs=FormatSuggestion(
            "%-20s %s", ("code_str", "description"),
            hdr="%-20s %s" % ("Code", "Description")))

    def misc_list_bofhd_request_types(self, operator):
        br = BofhdRequests(self.db, self.const)
        result = []
        for row in br.get_operations():
            result.append({"code_str": row["code_str"].lstrip("br_"),
                           "description": row["description"]})
        return result

    all_commands['misc_list_requests'] = Command(
        ("misc", "list_requests"),
        SimpleString(help_ref='string_bofh_request_search_by',
                     default='requestee'),
        SimpleString(help_ref='string_bofh_request_target',
                     default='<me>'),
        fs=FormatSuggestion(
            "%-7i %-10s %-16s %-16s %-10s %-20s %s",
            ("id", "requestee", format_time("when"), "op", "entity",
             "destination", "args"),
            hdr="%-7s %-10s %-16s %-16s %-10s %-20s %s" % (
                "Id", "Requestee", "When", "Op", "Entity", "Destination",
                "Arguments")))

    def misc_list_requests(self, operator, search_by, destination):
        br = BofhdRequests(self.db, self.const)
        ret = []

        if destination == '<me>':
            destination = self._get_account(operator.get_entity_id(), idtype='id')
            destination = destination.account_name
        if search_by == 'requestee':
            account = self._get_account(destination)
            rows = br.get_requests(operator_id=account.entity_id, given=True)
        elif search_by == 'operation':
            try:
                destination = int(self.const.BofhdRequestOp('br_'+destination))
            except Errors.NotFoundError:
                raise CerebrumError("Unknown request operation %s" % destination)
            rows = br.get_requests(operation=destination)
        elif search_by == 'disk':
            disk_id = self._get_disk(destination)[1]
            rows = br.get_requests(destination_id=disk_id)
        elif search_by == 'account':
            account = self._get_account(destination)
            rows = br.get_requests(entity_id=account.entity_id)
        else:
            raise CerebrumError("Unknown search_by criteria")

        for r in rows:
            op = self.const.BofhdRequestOp(r['operation'])
            dest = None
            ent_name = None
            if op in (self.const.bofh_move_user, self.const.bofh_move_request,
                      self.const.bofh_move_user_now):
                disk = self._get_disk(r['destination_id'])[0]
                dest = disk.path
            elif op in (self.const.bofh_move_give,):
                dest = self._get_entity_name(r['destination_id'],
                                             self.const.entity_group)
            elif op in (self.const.bofh_email_create,
                        self.const.bofh_email_move,
                        self.const.bofh_email_delete):
                dest = self._get_entity_name(r['destination_id'],
                                             self.const.entity_host)
            elif op in (self.const.bofh_sympa_create,
                        self.const.bofh_sympa_remove):
                ea = Email.EmailAddress(self.db)
                if r['destination_id'] is not None:
                    ea.find(r['destination_id'])
                    dest = ea.get_address()
                ea.clear()
                try:
                    ea.find(r['entity_id'])
                except Errors.NotFoundError:
                    ent_name = "<not found>"
                else:
                    ent_name = ea.get_address()
            if ent_name is None:
                ent_name = self._get_entity_name(r['entity_id'],
                                                 self.const.entity_account)
            if r['requestee_id'] is None:
                requestee = ''
            else:
                requestee = self._get_entity_name(r['requestee_id'],
                                                  self.const.entity_account)
            ret.append({'when': r['run_at'],
                        'requestee': requestee,
                        'op': str(op),
                        'entity': ent_name,
                        'destination': dest,
                        'args': r['state_data'],
                        'id': r['request_id']
                        })
        ret.sort(lambda a,b: cmp(a['id'], b['id']))
        return ret

    all_commands['misc_cancel_request'] = Command(
        ("misc", "cancel_request"),
        SimpleString(help_ref='id:request_id'))
    def misc_cancel_request(self, operator, req):
        if req.isdigit():
            req_id = int(req)
        else:
            raise CerebrumError, "Request-ID must be a number"
        br = BofhdRequests(self.db, self.const)
        if not br.get_requests(request_id=req_id):
            raise CerebrumError, "Request ID %d not found" % req_id
        self.ba.can_cancel_request(operator.get_entity_id(), req_id)
        br.delete_request(request_id=req_id)
        return "OK, %s canceled" % req

    all_commands['misc_reload'] = Command(
        ("misc", "reload"),
        perm_filter='is_superuser')
    def misc_reload(self, operator):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        self.server.read_config()
        return "OK, server-config reloaded"

    # ou search <pattern> <language> <spread_filter>
    all_commands['ou_search'] = Command(
        ("ou", "search"),
        SimpleString(help_ref='ou_search_pattern'),
        SimpleString(help_ref='ou_search_language', optional=True),
        Spread(help_ref='spread_filter', optional=True),
        fs=FormatSuggestion([
            (" %06s    %s", ('stedkode', 'name'))
            ],
        hdr="Stedkode   Organizational unit"))
    def ou_search(self, operator, pattern, language='nb', spread_filter=None):
        if len(pattern) == 0:
            pattern = '%' # No search pattern? Get everything!

        try:
            language = int(self.const.LanguageCode(language))
        except Errors.NotFoundError:
            raise CerebrumError, 'Unknown language "%s", try "nb" or "en"' % language

        output = []
        ou = Utils.Factory.get('OU')(self.db)

        if re.match(r'[0-9]{1,6}$', pattern):
            fak = [ pattern[0:2] ]
            inst = [ pattern[2:4] ]
            avd = [ pattern[4:6] ]

            if len(fak[0]) == 1:
                fak = [ int(fak[0]) * 10 + x for x in range(10) ]
            if len(inst[0]) == 1:
                inst = [ int(inst[0]) * 10 + x for x in range(10) ]
            if len(avd[0]) == 1:
                avd = [ int(avd[0]) * 10 + x for x in range(10) ]

            # the following loop may look scary, but we will never
            # call get_stedkoder() more than 10 times.
            for f in fak:
                for i in inst:
                    if i == '':
                        i = None
                    for a in avd:
                        if a == '':
                            a = None
                        for r in ou.get_stedkoder(fakultet=f, institutt=i,
                                                  avdeling=a):
                            ou.clear()
                            ou.find(r['ou_id'])

                            if spread_filter:
                                spread_filter_match = False
                                for spread in ou.get_spread():
                                    if str(self.const.Spread(spread[0])).lower() == spread_filter.lower():
                                        spread_filter_match = True
                                        break

                            acronym = ou.get_name_with_language(
                                         name_variant=self.const.ou_name_acronym,
                                         name_language=language,
                                         default="")
                            name = ou.get_name_with_language(
                                         name_variant=self.const.ou_name,
                                         name_language=language,
                                         default="")

                            if len(acronym) > 0:
                                acronym = "(%s) " % acronym

                            if not spread_filter or (spread_filter and spread_filter_match):
                                output.append({
                                    'stedkode': '%02d%02d%02d' % (ou.fakultet,
                                                                  ou.institutt,
                                                                  ou.avdeling),
                                    'name': "%s%s" % (acronym, name)
                                })
        else:
            for r in ou.search_name_with_language(
                                    entity_type=self.const.entity_ou,
                                    name_language=language,
                                    name=pattern,
                                    exact_match=False):
                ou.clear()
                ou.find(r['entity_id'])

                if spread_filter:
                    spread_filter_match = False
                    for spread in ou.get_spread():
                        if str(self.const.Spread(spread[0])).lower() == spread_filter.lower():
                            spread_filter_match = True
                            break

                acronym = ou.get_name_with_language(
                                         name_variant=self.const.ou_name_acronym,
                                         name_language=language,
                                         default="")
                name = ou.get_name_with_language(
                                         name_variant=self.const.ou_name,
                                         name_language=language,
                                         default="")

                if len(acronym) > 0:
                    acronym = "(%s) " % acronym

                if not spread_filter or (spread_filter and spread_filter_match):
                    output.append({
                        'stedkode': '%02d%02d%02d' % (ou.fakultet,
                                                      ou.institutt,
                                                      ou.avdeling),
                        'name': "%s%s" % (acronym, name)
                    })

        if len(output) == 0:
            if spread_filter:
                return 'No matches for "%s" with spread filter "%s"' % (pattern, spread_filter)
            return 'No matches for "%s"' % pattern

        #removes duplicate results
        seen = set()
        output_nodupes = []
        for r in output:
            t = tuple(r.items())
            if t not in seen:
                seen.add(t)
                output_nodupes.append(r)

        return output_nodupes

    # ou info <stedkode/entity_id>
    all_commands['ou_info'] = Command(
        ("ou", "info"),
        OU(help_ref='ou_stedkode_or_id'),
        fs=FormatSuggestion([
            ("Stedkode:      %s\n" +
             "Entity ID:     %i\n" +
             "Name (nb):     %s\n" +
             "Name (en):     %s\n" +
             "Quarantines:   %s\n" +
             "Spreads:       %s",
             ('stedkode', 'entity_id', 'name_nb', 'name_en', 'quarantines',
              'spreads')),
            ("Contact:       (%s) %s: %s",
             ('contact_source', 'contact_type', 'contact_value')),
            ("Address:       (%s) %s: %s%s%s %s %s",
             ('address_source', 'address_type', 'address_text', 'address_po_box',
              'address_postal_number', 'address_city', 'address_country')),
            ("Email domain:  affiliation %-7s @%s",
             ('email_affiliation', 'email_domain'))
            ]
        ))
    def ou_info(self, operator, target):
        output = []

        ou = self.util.get_target(target, default_lookup='stedkode', restrict_to=['OU'])

        acronym_nb = ou.get_name_with_language(
                                 name_variant=self.const.ou_name_acronym,
                                 name_language=self.const.language_nb,
                                 default="")
        fullname_nb = ou.get_name_with_language(
                                 name_variant=self.const.ou_name,
                                 name_language=self.const.language_nb,
                                 default="")
        acronym_en = ou.get_name_with_language(
                                 name_variant=self.const.ou_name_acronym,
                                 name_language=self.const.language_en,
                                 default="")
        fullname_en = ou.get_name_with_language(
                                 name_variant=self.const.ou_name,
                                 name_language=self.const.language_en,
                                 default="")

        if len(acronym_nb) > 0:
            acronym_nb = "(%s) " % acronym_nb

        if len(acronym_en) > 0:
            acronym_en = "(%s) " % acronym_en

        quarantines = []
        for q in ou.get_entity_quarantine(only_active=True):
            quarantines.append(str(self.const.Quarantine(q['quarantine_type'])))
        if len(quarantines) == 0:
            quarantines = ['<none>']

        spreads = []
        for s in ou.get_spread():
            spreads.append(str(self.const.Spread(s['spread'])))
        if len(spreads) == 0:
            spreads = ['<none>']

        # To support OU objects without the mixin for stedkode:
        stedkode = '<Not set>'
        if hasattr(ou, 'fakultet'):
            stedkode = '%02d%02d%02d' % (ou.fakultet, ou.institutt, ou.avdeling)

        output.append({
            'entity_id': ou.entity_id,
            'stedkode': stedkode,
            'name_nb': "%s%s" % (acronym_nb, fullname_nb),
            'name_en': "%s%s" % (acronym_en, fullname_en),
            'quarantines': ', '.join(quarantines),
            'spreads': ', '.join(spreads)
        })

        for c in ou.get_contact_info():
            output.append({
                'contact_source': str(self.const.AuthoritativeSystem(c['source_system'])),
                'contact_type': str(self.const.ContactInfo(c['contact_type'])),
                'contact_value': c['contact_value']
            })

        for a in ou.get_entity_address():
            if a['country'] is not None:
                a['country'] = ', ' + a['country']
            else:
                a['country'] = ''

            if a['p_o_box'] is not None:
                a['p_o_box'] = "PO box %s, " % a['p_o_box']
            else:
                a['p_o_box'] = ''

            if len(a['address_text']) > 0:
                a['address_text'] += ', '

            output.append({
                'address_source': str(self.const.AuthoritativeSystem(a['source_system'])),
                'address_type': str(self.const.Address(a['address_type'])),
                'address_text': a['address_text'].replace("\n", ', '),
                'address_po_box': a['p_o_box'],
                'address_city': a['city'],
                'address_postal_number': a['postal_number'],
                'address_country': a['country']
            })

        try:
            meta = Metainfo.Metainfo(self.db)
            email_info = meta.get_metainfo('sqlmodule_email')
        except Errors.NotFoundError:
            email_info = None
        if email_info:
            eed = Email.EntityEmailDomain(self.db)
            try:
                eed.find(ou.entity_id)
            except Errors.NotFoundError:
                pass
            ed = Email.EmailDomain(self.db)
            for r in eed.list_affiliations():
                affname = "<any>"
                if r['affiliation']:
                    affname = str(self.const.PersonAffiliation(r['affiliation']))
                ed.clear()
                ed.find(r['domain_id'])

                output.append({'email_affiliation': affname,
                               'email_domain': ed.email_domain_name})

        return output

    # ou tree <stedkode/entity_id> <perspective> <language>
    all_commands['ou_tree'] = Command(
        ("ou", "tree"),
        OU(help_ref='ou_stedkode_or_id'),
        SimpleString(help_ref='ou_perspective', optional=True),
        SimpleString(help_ref='ou_search_language', optional=True),
        fs=FormatSuggestion([
            ("%s%s %s",
             ('indent', 'stedkode', 'name'))
            ]
        ))
    def ou_tree(self, operator, target, ou_perspective=None, language='nb'):
        def _is_root(ou, perspective):
            if ou.get_parent(perspective) in (ou.entity_id, None):
                return True
            return False

        co = self.const

        try:
            language = int(co.LanguageCode(language))
        except Errors.NotFoundError:
            raise CerebrumError, 'Unknown language "%s", try "nb" or "en"' % language

        output = []

        perspective = None
        if ou_perspective:
            perspective = co.human2constant(ou_perspective, co.OUPerspective)
        if not ou_perspective and 'perspective' in cereconf.LDAP_OU:
            perspective = co.human2constant(cereconf.LDAP_OU['perspective'], co.OUPerspective)
        if ou_perspective and not perspective:
            raise CerebrumError, 'No match for perspective "%s". Try one of: %s' % (
                ou_perspective,
                ", ".join(str(x) for x in co.fetch_constants(co.OUPerspective))
            )
        if not perspective:
            raise CerebrumError, "Unable to guess perspective. Please specify one of: %s" % (
                ", ".join(str(x) for x in co.fetch_constants(co.OUPerspective))
            )

        target_ou = self.util.get_target(target, default_lookup='stedkode', restrict_to=['OU'])
        ou = Utils.Factory.get('OU')(self.db)

        data = {
            'parents': [],
            'target': [target_ou.entity_id],
            'children': []
        }

        prev_parent = None

        try:
            while True:
                if prev_parent:
                    ou.clear()
                    ou.find(prev_parent)

                    if _is_root(ou, perspective):
                        break

                    prev_parent = ou.get_parent(perspective)
                    data['parents'].insert(0, prev_parent)
                else:
                    if _is_root(target_ou, perspective):
                        break

                    prev_parent = target_ou.get_parent(perspective)
                    data['parents'].insert(0, prev_parent)
        except:
            raise CerebrumError, 'Error getting OU structure for %s. Is the OU valid?' % target

        for c in target_ou.list_children(perspective):
            data['children'].append(c[0])

        for d in data:
            if d is 'target':
                indent = '* ' + (len(data['parents']) -1) * '  '
            elif d is 'children':
                indent = (len(data['parents']) +1) * '  '
                if len(data['parents']) == 0:
                    indent += '  '

            for num, item in enumerate(data[d]):
                ou.clear()
                ou.find(item)

                if d is 'parents':
                    indent = num * '  '

                output.append({
                    'indent': indent,
                    'stedkode': '%02d%02d%02d' % (ou.fakultet, ou.institutt, ou.avdeling),
                    'name': ou.get_name_with_language(
                        name_variant=co.ou_name,
                        name_language=language,
                        default="")
                })

        return output


    # misc verify_password
    all_commands['misc_verify_password'] = Command(
        ("misc", "verify_password"), AccountName(), AccountPassword())
    def misc_verify_password(self, operator, accountname, password):
        ac = self._get_account(accountname)
        # Only people who can set the password are allowed to check it
        self.ba.can_set_password(operator.get_entity_id(), ac)
        if ac.verify_auth(password):
            return "Password is correct"
        ph = PasswordHistory(self.db)
        histhash = ph.encode_for_history(ac.account_name, password)
        for r in ph.get_history(ac.entity_id):
            if histhash == r['md5base64']:
                return ("The password is obsolete, it was set on %s" %
                        r['set_at'])
        return "Incorrect password"


    #
    # perm commands
    #

    # perm opset_list
    all_commands['perm_opset_list'] = Command(
        ("perm", "opset_list"),
        fs=FormatSuggestion("%-6i %s", ("id", "name"), hdr="Id     Name"),
        perm_filter='is_superuser')
    def perm_opset_list(self, operator):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        aos = BofhdAuthOpSet(self.db)
        ret = []
        for r in aos.list():
            ret.append({'id': r['op_set_id'],
                        'name': r['name']})
        return ret

    # perm opset_show
    all_commands['perm_opset_show'] = Command(
        ("perm", "opset_show"), SimpleString(help_ref="string_op_set"),
        fs=FormatSuggestion("%-6i %-16s %s", ("op_id", "op", "attrs"),
                            hdr="%-6s %-16s %s" % ("Id", "op", "Attributes")),
        perm_filter='is_superuser')
    def perm_opset_show(self, operator, name):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        aos = BofhdAuthOpSet(self.db)
        aos.find_by_name(name)
        ret = []
        for r in aos.list_operations():
            c = AuthConstants(int(r['op_code']))
            ret.append({'op': str(c),
                        'op_id': r['op_id'],
                        'attrs': ", ".join(
                ["%s" % r2['attr'] for r2 in aos.list_operation_attrs(r['op_id'])])})
        return ret

    # perm target_list
    all_commands['perm_target_list'] = Command(
        ("perm", "target_list"), SimpleString(help_ref="string_perm_target"),
        Id(optional=True),
        fs=FormatSuggestion("%-8i %-15i %-10s %-18s %s",
                            ("tgt_id", "entity_id", "target_type", "name", "attrs"),
                            hdr="%-8s %-15s %-10s %-18s %s" % (
        "TargetId", "TargetEntityId", "TargetType", "TargetName", "Attrs")),
        perm_filter='is_superuser')
    def perm_target_list(self, operator, target_type, entity_id=None):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        aot = BofhdAuthOpTarget(self.db)
        ret = []
        if target_type.isdigit():
            rows = aot.list(target_id=target_type)
        else:
            rows = aot.list(target_type=target_type, entity_id=entity_id)
        for r in rows:
            if r['target_type'] == 'group':
                name = self._get_entity_name(r['entity_id'], self.const.entity_group)
            elif r['target_type'] == 'disk':
                name = self._get_entity_name(r['entity_id'], self.const.entity_disk)
            elif r['target_type'] == 'host':
                name = self._get_entity_name(r['entity_id'], self.const.entity_host)
            else:
                name = "unknown"
            ret.append({'tgt_id': r['op_target_id'],
                        'entity_id': r['entity_id'],
                        'name': name,
                        'target_type': r['target_type'],
                        'attrs': r['attr'] or '<none>'})
        return ret

    # perm add_target
    all_commands['perm_add_target'] = Command(
        ("perm", "add_target"),
        SimpleString(help_ref="string_perm_target_type"), Id(),
        SimpleString(help_ref="string_attribute", optional=True),
        perm_filter='is_superuser')
    def perm_add_target(self, operator, target_type, entity_id, attr=None):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        if entity_id.isdigit():
            entity_id = int(entity_id)
        else:
            raise CerebrumError("Integer entity_id expected; got %r" %
                                (entity_id,))
        aot = BofhdAuthOpTarget(self.db)
        aot.populate(entity_id, target_type, attr)
        aot.write_db()
        return "OK, target id=%d" % aot.op_target_id

    # perm del_target
    all_commands['perm_del_target'] = Command(
        ("perm", "del_target"), Id(help_ref="id:op_target"),
        perm_filter='is_superuser')
    def perm_del_target(self, operator, op_target_id, attr):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        aot = BofhdAuthOpTarget(self.db)
        aot.find(op_target_id)
        aot.delete()
        return "OK, target %s, attr=%s deleted" % (op_target_id, attr)

    # perm list
    all_commands['perm_list'] = Command(
        ("perm", "list"), Id(help_ref='id:entity_ext'),
        fs=FormatSuggestion("%-8s %-8s %-8i",
                            ("entity_id", "op_set_id", "op_target_id"),
                            hdr="%-8s %-8s %-8s" %
                            ("entity_id", "op_set_id", "op_target_id")),
        perm_filter='is_superuser')
    def perm_list(self, operator, entity_id):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        if entity_id.startswith("group:"):
            entities = [ self._get_group(entity_id.split(":")[-1]).entity_id ]
        elif entity_id.startswith("account:"):
            account = self._get_account(entity_id.split(":")[-1])
            group = self.Group_class(self.db)
            entities = [account.entity_id]
            entities.extend([x["group_id"] for x in
                            group.search(member_id=account.entity_id,
                                         indirect_members=False)])
        else:
            if not entity_id.isdigit():
                raise CerebrumError("Expected entity-id")
            entities = [int(entity_id)]
        bar = BofhdAuthRole(self.db)
        ret = []
        for r in bar.list(entities):
            ret.append({'entity_id': self._get_entity_name(r['entity_id']),
                        'op_set_id': self.num2op_set_name[int(r['op_set_id'])],
                        'op_target_id': r['op_target_id']})
        return ret

    # perm grant
    all_commands['perm_grant'] = Command(
        ("perm", "grant"), Id(), SimpleString(help_ref="string_op_set"),
        Id(help_ref="id:op_target"), perm_filter='is_superuser')
    def perm_grant(self, operator, entity_id, op_set_name, op_target_id):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        bar = BofhdAuthRole(self.db)
        aos = BofhdAuthOpSet(self.db)
        aos.find_by_name(op_set_name)

        bar.grant_auth(entity_id, aos.op_set_id, op_target_id)
        return "OK, granted %s@%s to %s" % (op_set_name, op_target_id,
                                            entity_id)

    # perm revoke
    all_commands['perm_revoke'] = Command(
        ("perm", "revoke"), Id(), SimpleString(help_ref="string_op_set"),
        Id(help_ref="id:op_target"), perm_filter='is_superuser')
    def perm_revoke(self, operator, entity_id, op_set_name, op_target_id):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        bar = BofhdAuthRole(self.db)
        aos = BofhdAuthOpSet(self.db)
        aos.find_by_name(op_set_name)
        bar.revoke_auth(entity_id, aos.op_set_id, op_target_id)
        return "OK, revoked  %s@%s from %s" % (op_set_name, op_target_id,
                                            entity_id)

    # perm who_has_perm
    all_commands['perm_who_has_perm'] = Command(
        ("perm", "who_has_perm"), SimpleString(help_ref="string_op_set"),
        fs=FormatSuggestion("%-8s %-8s %-8i",
                            ("entity_id", "op_set_id", "op_target_id"),
                            hdr="%-8s %-8s %-8s" %
                            ("entity_id", "op_set_id", "op_target_id")),
        perm_filter='is_superuser')
    def perm_who_has_perm(self, operator, op_set_name):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        aos = BofhdAuthOpSet(self.db)
        aos.find_by_name(op_set_name)
        bar = BofhdAuthRole(self.db)
        ret = []
        for r in bar.list(op_set_id=aos.op_set_id):
            ret.append({'entity_id': self._get_entity_name(r['entity_id']),
                        'op_set_id': self.num2op_set_name[int(r['op_set_id'])],
                        'op_target_id': r['op_target_id']})
        return ret

    # perm who_owns
    all_commands['perm_who_owns'] = Command(
        ("perm", "who_owns"), Id(help_ref="id:entity_ext"),
        fs=FormatSuggestion("%-8s %-8s %-8i",
                            ("entity_id", "op_set_id", "op_target_id"),
                            hdr="%-8s %-8s %-8s" %
                            ("entity_id", "op_set_id", "op_target_id")),
        perm_filter='is_superuser')
    def perm_who_owns(self, operator, id):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        bar = BofhdAuthRole(self.db)
        if id.startswith("group:"):
            group = self._get_group(id.split(":")[-1])
            aot = BofhdAuthOpTarget(self.db)
            target_ids = []
            for r in aot.list(target_type='group', entity_id=group.entity_id):
                target_ids.append(r['op_target_id'])
        elif id.startswith("account:"):
            account = self._get_account(id.split(":")[-1])
            disk = Utils.Factory.get('Disk')(self.db)
            try:
                tmp = account.get_home(self.const.spread_uio_nis_user)
                disk.find(tmp[0])
            except Errors.NotFoundError:
                raise CerebrumError, "Unknown disk for user"
            aot = BofhdAuthOpTarget(self.db)
            target_ids = []
            for r in aot.list(target_type='global_host'):
                target_ids.append(r['op_target_id'])
            for r in aot.list(target_type='disk', entity_id=disk.entity_id):
                target_ids.append(r['op_target_id'])
            for r in aot.list(target_type='host', entity_id=disk.host_id):
                if (not r['attr'] or
                    re.compile(r['attr']).match(disk.path.split("/")[-1]) != None):
                    target_ids.append(r['op_target_id'])
        else:
            if not id.isdigit():
                raise CerebrumError("Expected target-id")
            target_ids = [int(id)]
        if not target_ids:
            raise CerebrumError("No target_ids for %s" % id)
        ret = []
        for r in bar.list_owners(target_ids):
            ret.append({'entity_id': self._get_entity_name(r['entity_id']),
                        'op_set_id': self.num2op_set_name[int(r['op_set_id'])],
                        'op_target_id': r['op_target_id']})
        return ret

    #
    # person commands
    #

    # person accounts
    all_commands['person_accounts'] = Command(
        ("person", "accounts"), PersonId(),
        fs=FormatSuggestion("%9i %-10s %s",
                            ("account_id", "name", format_day("expire")),
                            hdr=("%9s %-10s %s") %
                            ("Id", "Name", "Expire")))
    def person_accounts(self, operator, id):
        person = self.util.get_target(id, restrict_to=['Person', 'Group'])
        account = self.Account_class(self.db)
        ret = []
        for r in account.list_accounts_by_owner_id(person.entity_id,
                                                   owner_type=person.entity_type,
                                                   filter_expired=False):
            account = self._get_account(r['account_id'], idtype='id')

            ret.append({'account_id': r['account_id'],
                        'name': account.account_name,
                        'expire': account.expire_date})
        ret.sort(lambda a,b: cmp(a['name'], b['name']))
        return ret

    def _person_affiliation_add_helper(self, operator, person, ou, aff, aff_status):
        """Helper-function for adding an affiliation to a person with
        permission checking.  person is expected to be a person
        object, while ou, aff and aff_status should be the textual
        representation from the client"""
        aff = self._get_affiliationid(aff)
        aff_status = self._get_affiliation_statusid(aff, aff_status)
        ou = self._get_ou(stedkode=ou)

        # Assert that the person already have the affiliation
        has_aff = False
        for a in person.get_affiliations():
            if a['ou_id'] == ou.entity_id and a['affiliation'] == aff:
                if a['status'] == aff_status:
                    has_aff = True
                elif a['source_system'] == self.const.system_manual:
                    raise CerebrumError, ("Person has conflicting aff_status "
                                          "for this OU/affiliation combination")
        if not has_aff:
            self.ba.can_add_affiliation(operator.get_entity_id(),
                                        person, ou, aff, aff_status)
            if (aff == self.const.affiliation_ansatt or
                aff == self.const.affiliation_student):
                raise PermissionDenied(
                    "Student/Ansatt affiliation can only be set by automatic import routines")
            person.add_affiliation(ou.entity_id, aff,
                                   self.const.system_manual, aff_status)
            person.write_db()
        return ou, aff, aff_status

    # person affilation_add
    all_commands['person_affiliation_add'] = Command(
        ("person", "affiliation_add"), PersonId(help_ref="person_id_other"),
        OU(), Affiliation(), AffiliationStatus(),
        perm_filter='can_add_affiliation')
    def person_affiliation_add(self, operator, person_id, ou, aff, aff_status):
        try:
            person = self._get_person(*self._map_person_id(person_id))
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        ou, aff, aff_status = self._person_affiliation_add_helper(
            operator, person, ou, aff, aff_status)
        return "OK, added %s@%s to %s" % (aff, self._format_ou_name(ou), person.entity_id)

    # person affilation_remove
    all_commands['person_affiliation_remove'] = Command(
        ("person", "affiliation_remove"), PersonId(), OU(), Affiliation(),
        perm_filter='can_remove_affiliation')
    def person_affiliation_remove(self, operator, person_id, ou, aff):
        try:
            person = self._get_person(*self._map_person_id(person_id))
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        aff = self._get_affiliationid(aff)
        ou = self._get_ou(stedkode=ou)
        auth_systems = []
        for auth_sys in cereconf.BOFHD_AUTH_SYSTEMS:
            tmp=getattr(self.const, auth_sys)
            auth_systems.append(int(tmp))
        self.ba.can_remove_affiliation(operator.get_entity_id(), person, ou, aff)
        for row in person.list_affiliations(person_id=person.entity_id,
                                            affiliation=aff):
            if row['ou_id'] != int(ou.entity_id):
                continue
            if not int(row['source_system']) in auth_systems:
                person.delete_affiliation(ou.entity_id, aff,
                                          row['source_system'])
            else:
                raise CerebrumError("Cannot remove affiliation registered from an authoritative source system")
        return "OK, removed %s@%s from %s" % (aff, self._format_ou_name(ou), person.entity_id)

    # person set_bdate
    all_commands['person_set_bdate'] = Command(
        ("person", "set_bdate"), PersonId(help_ref="id:target:person"),
        Date(help_ref='date_birth'), perm_filter='can_create_person')
    def person_set_bdate(self, operator, person_id, bdate):
        self.ba.can_create_person(operator.get_entity_id())
        try:
            person = self.util.get_target(person_id, restrict_to=['Person'])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        for a in person.get_affiliations():
            if (int(a['source_system']) in
                [int(self.const.system_fs), int(self.const.system_sap)]):
                raise PermissionDenied("You are not allowed to alter birth date for this person.")
        bdate = self._parse_date(bdate)
        if bdate > self._today():
            raise CerebrumError, "Please check the date of birth, cannot register date_of_birth > now"
        person.birth_date = bdate
        person.write_db()
        return "OK, set birth date for '%s' = '%s'" % (person_id, bdate)

    # person set_name
    all_commands['person_set_name'] = Command(
        ("person", "set_name"), PersonId(help_ref="person_id_other"),
        PersonName(help_ref="person_name_first"),
        PersonName(help_ref="person_name_last"),
        fs=FormatSuggestion("Name altered for: %i", ("person_id",)),
        perm_filter='can_create_person')

    def person_set_name(self, operator, person_id, first_name, last_name):
        auth_systems = []
        for auth_sys in cereconf.BOFHD_AUTH_SYSTEMS:
            tmp = getattr(self.const, auth_sys)
            auth_systems.append(int(tmp))
        person = self._get_person(*self._map_person_id(person_id))
        self.ba.can_create_person(operator.get_entity_id())
        for a in person.get_affiliations():
            if int(a['source_system']) in auth_systems:
                raise PermissionDenied("You are not allowed to alter "
                                       "names registered in authoritative "
                                       "source_systems.")

        if last_name == "":
            raise CerebrumError("Last name is required.")

        if first_name == "":
            full_name = last_name
        else:
            full_name = " ".join((first_name, last_name))

        person.affect_names(self.const.system_manual,
                            self.const.name_first,
                            self.const.name_last,
                            self.const.name_full)

        # If first_name is an empty string, it should remain unpopulated.
        # Since it is tagged as an affected name_variant above, this will
        # trigger the original name_variant-row in the db to be deleted when
        # running write_db.
        if first_name != "":
            person.populate_name(self.const.name_first, first_name)

        person.populate_name(self.const.name_last, last_name)
        person.populate_name(self.const.name_full, full_name)

        try:
            person.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError("Database error: %s" % m)

        return {'person_id': person.entity_id}

    # person name_suggestions
    hidden_commands['person_name_suggestions'] = Command(
        ('person', 'name_suggestions'),
        PersonId(help_ref='person_id_other'))
    def person_name_suggestions(self, operator, person_id):
        """Return a list of names that the user can choose for himself. Each
        name could generate a different primary e-mail address, so this is also
        returned.

        The name varieties are generated:

        - The primary family name is used as a basis for all varieties.

        - All given names are then added in front of the family name. If the
          given name contains several names, all of these are added as a
          variety, e.g:

              family: Doe, given: John Robert
              varieties: John Doe, John Robert Doe, Robert Doe
        """
        person  = self._get_person(*self._map_person_id(person_id))
        account = self._get_account(operator.get_entity_id(), idtype='id')
        if not (self.ba.is_superuser(operator.get_entity_id()) or
                account.owner_id == person.entity_id):
            raise CerebrumError('You can only get your own names')

        # get primary last name to use for basis
        last_name = None
        for sys in cereconf.SYSTEM_LOOKUP_ORDER:
            try:
                last_name = person.get_name(getattr(self.const, sys),
                                            self.const.name_last)
                if last_name:
                    break
            except Errors.NotFoundError:
                pass
        if not last_name:
            raise CerebrumError('Found no family name for person')

        def name_combinations(names):
            """Return all different combinations of given names, while keeping
            the order intact."""
            ret = []
            for i in range(len(names)):
                ret.append([names[i]])
                ret.extend([names[i]] + nxt
                           for nxt in name_combinations(names[i+1:]))
            return ret

        names = set()
        for sys in cereconf.SYSTEM_LOOKUP_ORDER:
            try:
                name = person.get_name(getattr(self.const, sys),
                                               self.const.name_first)
            except Errors.NotFoundError:
                continue
            names.update((tuple(n) + (last_name,))
                         for n in name_combinations(name.split(' ')))
        account.clear()

        uidaddr = True
        # TODO: what if person has no primary account?
        try:
            account.find(person.get_primary_account())
            ed = Email.EmailDomain(self.db)
            ed.find(account.get_primary_maildomain())
            domain = ed.email_domain_name
            for cat in ed.get_categories():
                if int(cat['category'] == int(self.const.email_domain_category_cnaddr)):
                    uidaddr = False
        except Errors.NotFoundError:
            domain = 'ulrik.uio.no'
        if uidaddr:
            return [(name, '%s@%s' % (account.account_name, domain))
                    for name in names]
        return [(name,
                 '%s@%s' % (account.get_email_cn_given_local_part(' '.join(name)),
                            domain))
                for name in names]

    # person create
    all_commands['person_create'] = Command(
        ("person", "create"), PersonId(),
        Date(help_ref='date_birth'), PersonName(help_ref='person_name_first'),
        PersonName(help_ref='person_name_last'), OU(), Affiliation(),
        AffiliationStatus(),
        fs=FormatSuggestion("Created: %i",
        ("person_id",)), perm_filter='can_create_person')
    def person_create(self, operator, person_id, bdate, person_name_first,
                      person_name_last, ou, affiliation, aff_status):
        stedkode = ou
        try:
            ou = self._get_ou(stedkode=ou)
        except Errors.NotFoundError:
            raise CerebrumError, "Unknown OU (%s)" % ou
        try:
            aff = self._get_affiliationid(affiliation)
        except Errors.NotFoundError:
            raise CerebrumError, "Unknown affiliation type (%s)" % affiliation
        self.ba.can_create_person(operator.get_entity_id(), ou, aff)
        person = Utils.Factory.get('Person')(self.db)
        person.clear()
        # TBD: The current implementation of ._parse_date() should
        # handle None input just fine; if that implementation is
        # correct, this test can be removed.
        if bdate is not None:
            bdate = self._parse_date(bdate)
            if bdate > self._today():
                raise CerebrumError, "Please check the date of birth, cannot register date_of_birth > now"
        if person_id:
            id_type, id = self._map_person_id(person_id)
        else:
            id_type = None
        gender = self.const.gender_unknown
        if id_type is not None and id:
            if id_type == self.const.externalid_fodselsnr:
                try:
                    if fodselsnr.er_mann(id):
                        gender = self.const.gender_male
                    else:
                        gender = self.const.gender_female
                except fodselsnr.InvalidFnrError, msg:
                    raise CerebrumError("Invalid birth-no: '%s'" % msg)
                try:
                    person.find_by_external_id(self.const.externalid_fodselsnr, id)
                    raise CerebrumError("A person with that fnr already exists")
                except Errors.TooManyRowsError:
                    raise CerebrumError("A person with that fnr already exists")
                except Errors.NotFoundError:
                    pass
                person.clear()
                self._person_create_externalid_helper(person)
                person.populate_external_id(self.const.system_manual,
                                            self.const.externalid_fodselsnr,
                                            id)
        person.populate(bdate, gender,
                        description='Manually created')
        person.affect_names(self.const.system_manual, self.const.name_first, self.const.name_last)
        person.populate_name(self.const.name_first,
                             person_name_first)
        person.populate_name(self.const.name_last,
                             person_name_last)
        try:
            person.write_db()
            self._person_affiliation_add_helper(
                operator, person, stedkode, str(aff), aff_status)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return {'person_id': person.entity_id}

    def _person_create_externalid_helper(self, person):
        person.affect_external_id(self.const.system_manual,
                                  self.const.externalid_fodselsnr)
    # person find
    all_commands['person_find'] = Command(
        ("person", "find"), PersonSearchType(), SimpleString(),
        SimpleString(optional=True, help_ref="affiliation_optional"),
        fs=FormatSuggestion("%7i   %10s   %-12s  %s",
                            ('id', 'birth', 'account', 'name'),
                            hdr="%7s   %10s   %-12s  %s" % \
                            ('Id', 'Birth', 'Account', 'Name')))
    def person_find(self, operator, search_type, value, filter=None):
        # TODO: Need API support for this
        matches = []
        idcol = 'person_id'
        if filter is not None:
            try:
                filter = int(self.const.PersonAffiliation(filter))
            except Errors.NotFoundError:
                raise CerebrumError, ("Invalid affiliation '%s' (perhaps you "
                                      "need to quote the arguments?)" % filter)
        person = Utils.Factory.get('Person')(self.db)
        person.clear()
        extids = {
                'fnr':    'externalid_fodselsnr',
                'passnr': 'externalid_pass_number',
                'ssn':    'externalid_social_security_number',
                'taxid':  'externalid_tax_identification_number',
                'vatnr':  'externalid_value_added_tax_number',
                'studnr': 'externalid_studentnr',
                'sapnr':  'externalid_sap_ansattnr'
                }
        if search_type == 'name':
            if filter is not None:
                raise CerebrumError("Can't filter by affiliation "
                                    "for search type 'name'")
            if len(value.strip(" \t%_*?")) < 3:
                raise CerebrumError("You must specify at least three "
                                    "letters of the name")
            matches = person.search_person_names(name=value,
                                    name_variant=self.const.name_full,
                                    source_system=self.const.system_cached,
                                    exact_match=False,
                                    case_sensitive=(value != value.lower()))
        elif search_type in extids:
            idtype = getattr(self.const, extids[search_type], None)
            if idtype:
                matches = person.list_external_ids(
                    id_type=idtype,
                    external_id=value)
                idcol = 'entity_id'
            else:
                raise CerebrumError, "Unknown search type (%s)" % search_type
        elif search_type == 'date':
            matches = person.find_persons_by_bdate(self._parse_date(value))
        elif search_type == 'stedkode':
            ou = self._get_ou(stedkode=value)
            matches = person.list_affiliations(ou_id=ou.entity_id,
                                               affiliation=filter)
        elif search_type == 'ou':
            ou = self._get_ou(ou_id=value)
            matches = person.list_affiliations(ou_id=ou.entity_id,
                                               affiliation=filter)
        else:
            raise CerebrumError, "Unknown search type (%s)" % search_type
        ret = []
        seen = {}
        acc = self.Account_class(self.db)
        # matches may be an iterator, so force it into a list so we
        # can count the entries.
        matches = list(matches)
        if len(matches) > cereconf.BOFHD_MAX_MATCHES:
            raise CerebrumError, ("More than %d (%d) matches, please narrow "
                                  "search criteria" % (cereconf.BOFHD_MAX_MATCHES,
                                                       len(matches)))
        for row in matches:
            # We potentially get multiple rows for a person when
            # s/he has more than one source system or affiliation.
            p_id = row[idcol]
            if p_id in seen:
                continue
            seen[p_id] = True
            person.clear()
            person.find(p_id)
            if row.has_key('name'):
                pname = row['name']
            else:
                try:
                    pname = person.get_name(self.const.system_cached,
                                            getattr(self.const,
                                                    cereconf.DEFAULT_GECOS_NAME))
                except Errors.NotFoundError:
                    # Oh well, we don't know person's name
                    pname = '<none>'

            # Person.get_primary_account will not return expired
            # users.  Account.get_account_types will return the
            # accounts ordered by priority, but the highest priority
            # might be expired.
            account_name = "<none>"
            for row in acc.get_account_types(owner_id=p_id,
                                             filter_expired=False):
                acc.clear()
                acc.find(row['account_id'])
                account_name = acc.account_name
                if not acc.is_expired():
                    break

            # Ideally we'd fetch the authoritative last name, but
            # it's a lot of work.  We cheat and use the last word
            # of the name, which should work for 99.9% of the users.
            ret.append({'id': p_id,
                        'birth': date_to_string(person.birth_date),
                        'export_id': person.export_id,
                        'account': account_name,
                        'name': pname,
                        'lastname': pname.split(" ")[-1] })
        ret.sort(lambda a,b: (cmp(a['lastname'], b['lastname']) or
                              cmp(a['name'], b['name'])))
        return ret

    # person info
    all_commands['person_info'] = Command(
        ("person", "info"), PersonId(help_ref="id:target:person"),
        fs=FormatSuggestion([
        ("Name:          %s\n" +
         "Entity-id:     %i\n" +
         "Birth:         %s\n" +
         "Spreads:       %s\n" +
         "Affiliations:  %s [from %s]",
         ("name", "entity_id", "birth", "spreads",
          "affiliation_1", "source_system_1")),
        ("               %s [from %s]",
         ("affiliation", "source_system")),
        ("Names:         %s[from %s]",
         ("names", "name_src")),
        ("Contact:       %s: %s [from %s]",
         ("contact_type", "contact", "contact_src")),
        ("External id:   %s [from %s]",
         ("extid", "extid_src"))
        ]))
    def person_info(self, operator, person_id):
        try:
            person = self.util.get_target(person_id, restrict_to=['Person'])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        try:
            p_name = person.get_name(self.const.system_cached,
                                     getattr(self.const, cereconf.DEFAULT_GECOS_NAME))
            p_name = p_name + ' [from Cached]'
        except Errors.NotFoundError:
            raise CerebrumError("No name is registered for this person")
        data = [{'name': p_name,
                 'entity_id': person.entity_id,
                 'birth': date_to_string(person.birth_date),
                 'spreads': ", ".join([str(self.const.Spread(x['spread']))
                                for x in person.get_spread()])}]
        affiliations = []
        sources = []
        for row in person.get_affiliations():
            ou = self._get_ou(ou_id=row['ou_id'])
            affiliations.append("%s@%s" % (
                self.const.PersonAffStatus(row['status']),
                self._format_ou_name(ou)))
            sources.append(str(self.const.AuthoritativeSystem(row['source_system'])))
        for ss in cereconf.SYSTEM_LOOKUP_ORDER:
            ss = getattr(self.const, ss)
            person_name = ""
            for type in [self.const.name_first, self.const.name_last]:
                try:
                    person_name += person.get_name(ss, type) + ' '
                except Errors.NotFoundError:
                    continue
            if person_name:
                data.append({'names': person_name,
                             'name_src': str(
                    self.const.AuthoritativeSystem(ss))})
        if affiliations:
            data[0]['affiliation_1'] = affiliations[0]
            data[0]['source_system_1'] = sources[0]
        else:
            data[0]['affiliation_1'] = "<none>"
            data[0]['source_system_1'] = "<nowhere>"
        for i in range(1, len(affiliations)):
            data.append({'affiliation': affiliations[i],
                         'source_system': sources[i]})
        try:
            self.ba.can_get_person_external_id(operator, person)
            # Include fnr. Note that this is not displayed by the main
            # bofh-client, but some other clients (Brukerinfo, cweb) rely
            # on this data.
            for row in person.get_external_id(
                    id_type=self.const.externalid_fodselsnr):
                data.append({'fnr': row['external_id'],
                             'fnr_src': str(
                                 self.const.AuthoritativeSystem(
                                     row['source_system']
                                 )
                             )})
            # Show external ids
            for extid in (
                    'externalid_fodselsnr',
                    'externalid_sap_ansattnr',
                    'externalid_studentnr',
                    'externalid_pass_number',
                    'externalid_social_security_number',
                    'externalid_tax_identification_number',
                    'externalid_value_added_tax_number'):
                extid_const = getattr(self.const, extid, None)
                if extid_const:
                    for row in person.get_external_id(id_type=extid_const):
                        data.append({
                            'extid': str(extid_const),
                            'extid_src': str(self.const.AuthoritativeSystem(
                                row['source_system']
                            ))
                        })
        except PermissionDenied:
            pass
        # Show contact info
        for row in person.get_contact_info():
            if row['contact_type'] not in (self.const.contact_phone,
                                           self.const.contact_mobile_phone,
                                           self.const.contact_phone_private,
                                           self.const.contact_private_mobile):
                continue
            try:
                if self.ba.can_get_contact_info(
                        operator.get_entity_id(),
                        person=person,
                        contact_type=str(self.const.ContactInfo(
                            row['contact_type']))):
                    data.append({
                        'contact': row['contact_value'],
                        'contact_src': str(self.const.AuthoritativeSystem(
                            row['source_system'])),
                        'contact_type': str(self.const.ContactInfo(
                            row['contact_type']))
                    })
            except PermissionDenied:
                continue
        return data

    # person get_id
    all_commands['person_get_id'] = Command(
        ("person", "get_id"), PersonId(help_ref="person_id"),
        ExternalIdType(), SourceSystem(help_ref="source_system"),
        fs=FormatSuggestion([("ID %s for person entity %d in %s: %s",
                              ("ext_id_type",
                               "person_id",
                               "source_system",
                               "ext_id_value"))]))
    def person_get_id(self, operator, person_id, ext_id, source_system):
        """
        Returns an external id value for a person according to the specified
        source system. The command/function only returns one ID instead of all
        IDs for a person entity in order to limit the exposure of sensitive
        personal info to the bare minimum.
        """
        try:
            ext_id_const = int(self.const.EntityExternalId(ext_id))
        except Errors.NotFoundError:
            raise CerebrumError("Unknown external id: {}".format(ext_id))
        try:
            ss_const = int(self.const.AuthoritativeSystem(source_system))
        except Errors.NotFoundError:
            raise CerebrumError(
                "Unknown source system: {}".format(source_system)
            )
        try:
            person = self.util.get_target(person_id, restrict_to=['Person'])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")

        self.ba.can_get_person_external_id(operator, person)

        external_id_list = person.get_external_id(
            id_type=ext_id_const,
            source_system=ss_const
        )
        if external_id_list:
            ext_id_value = external_id_list[0]['external_id']
            return [{"ext_id_type": ext_id,
                     "person_id": person.entity_id,
                     "source_system": source_system,
                     "ext_id_value": ext_id_value}]
        else:
            raise CerebrumError("Could not find id {} for "
                                "person entity {} in system {}.".format(
                                    ext_id, person.entity_id, source_system))

    # person set_id
    all_commands['person_set_id'] = Command(
        ("person", "set_id"), PersonId(help_ref="person_id:current"),
        PersonId(help_ref="person_id:new"), SourceSystem(help_ref="source_system"))
    def person_set_id(self, operator, current_id, new_id, source_system):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        person = self._get_person(*self._map_person_id(current_id))
        idtype, id = self._map_person_id(new_id)
        self.ba.can_set_person_id(operator.get_entity_id(), person, idtype)
        if not source_system:
            ss = self.const.system_manual
        else:
            ss = int(self.const.AuthoritativeSystem(source_system))
        person.affect_external_id(ss, idtype)
        person.populate_external_id(ss, idtype, id)
        person.write_db()
        return "OK, set '%s' as new id for '%s'" % (new_id, current_id)

    # person clear_id
    all_commands['person_clear_id'] = Command(
        ("person", "clear_id"), PersonId(),
        SourceSystem(help_ref="source_system"), ExternalIdType(),
        perm_filter='is_superuser')
    def person_clear_id(self, operator, person_id, source_system, idtype):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        person = self.util.get_target(person_id, restrict_to="Person")
        ss = self.const.AuthoritativeSystem(source_system)
        try:
            int(ss)
        except Errors.NotFoundError:
            raise CerebrumError("No such source system")

        idtype = self.const.EntityExternalId(idtype)
        try:
            int(idtype)
        except Errors.NotFoundError:
            raise CerebrumError("No such external id")

        try:
            person._delete_external_id(ss, idtype)
        except:
            raise CerebrumError("Could not delete id %s:%s for %s" %
                                (idtype, source_system, person_id))
        return "OK"
    # end person_clear_id


    # person clear_name
    all_commands['person_clear_name'] = Command(
        ("person", "clear_name"),PersonId(help_ref="person_id_other"),
        SourceSystem(help_ref="source_system"),
        perm_filter='can_clear_name')
    def person_clear_name(self, operator, person_id, source_system):
        person = self.util.get_target(person_id, restrict_to="Person")
        ss = self.const.AuthoritativeSystem(source_system)
        try:
            int(ss)
        except Errors.NotFoundError:
            raise CerebrumError("No such source system")
        self.ba.can_clear_name(operator.get_entity_id(), person=person,
                               source_system=ss)
        removed = False
        for variant in (self.const.name_first, self.const.name_last, self.const.name_full):
            try:
                person.get_name(ss, variant)
            except Errors.NotFoundError:
                continue
            try:
                person._delete_name(ss, variant)
            except:
                raise CerebrumError("Could not delete %s from %s" %
                                    (str(variant).lower(), source_system))
            removed = True
        person._update_cached_names()
        if not removed:
            return ("No name to remove for %s from %s" %
                    (person_id, source_system))
        return "Removed name for %s from %s" % (person_id, source_system)

    # person student_info
    all_commands['person_student_info'] = Command(
        ("person", "student_info"), PersonId(),
        fs=FormatSuggestion([
        ("Studieprogrammer: %s, %s, %s, %s, tildelt=%s->%s privatist: %s",
         ("studprogkode", "studieretningkode", "studierettstatkode", "studentstatkode",
          format_day("dato_tildelt"), format_day("dato_gyldig_til"), "privatist")),
        ("Eksamensmeldinger: %s (%s), %s",
         ("ekskode", "programmer", format_day("dato"))),
        ("Underv.meld: %s, %s",
         ("undvkode", format_day("dato"))),
        ("Utd. plan: %s, %s, %d, %s",
         ("studieprogramkode", "terminkode_bekreft", "arstall_bekreft",
          format_day("dato_bekreftet"))),
        ("Semesterregistrert: %s - %s, registrert: %s, endret: %s",
         ("regstatus", "regformkode", format_day("dato_endring"),
          format_day("dato_regform_endret"))),
        ("Semesterbetaling: %s - %s, betalt: %s",
         ("betstatus", "betformkode", format_day('dato_betaling'))),
        ("Registrert med status_dod: %s",
         ("status_dod",)),
        ]),
        perm_filter='can_get_student_info')
    def person_student_info(self, operator, person_id):
        person_exists = False
        person = None
        try:
            person = self._get_person(*self._map_person_id(person_id))
            person_exists = True
        except CerebrumError, e:
            # Check if person exists in FS, but is not imported yet, e.g.
            # emnestudents. These should only be listed with limited
            # information.
            if person_id and len(person_id) == 11 and person_id.isdigit():
                try:
                    person_id = fodselsnr.personnr_ok(person_id)
                except:
                    raise e
                self.logger.debug('Unknown person %s, asking FS directly', person_id)
                self.ba.can_get_student_info(operator.get_entity_id(), None)
                fodselsdato, pnum = person_id[:6], person_id[6:]
            else:
                raise e
        else:
            self.ba.can_get_student_info(operator.get_entity_id(), person)
            fnr = person.get_external_id(id_type=self.const.externalid_fodselsnr,
                                         source_system=self.const.system_fs)
            if not fnr:
                raise CerebrumError("No matching fnr from FS")
            fodselsdato, pnum = fodselsnr.del_fnr(fnr[0]['external_id'])
        har_opptak = {}
        ret = []
        try:
            db = database.connect(user=cereconf.FS_USER,
                                  service=cereconf.FS_DATABASE_NAME,
                                  DB_driver=cereconf.DB_DRIVER_ORACLE)
        except database.DatabaseError, e:
            self.logger.warn("Can't connect to FS (%s)" % e)
            raise CerebrumError("Can't connect to FS, try later")
        fs = FS(db)
        for row in fs.student.get_undervisningsmelding(fodselsdato, pnum):
            ret.append({'undvkode': row['emnekode'],
                        'dato':     row['dato_endring'],})

        if person_exists:
            for row in fs.student.get_studierett(fodselsdato, pnum):
                har_opptak["%s" % row['studieprogramkode']] = \
                                row['status_privatist']
                ret.append({'studprogkode': row['studieprogramkode'],
                            'studierettstatkode': row['studierettstatkode'],
                            'studentstatkode': row['studentstatkode'],
                            'studieretningkode': row['studieretningkode'],
                            'dato_tildelt': row['dato_studierett_tildelt'],
                            'dato_gyldig_til': row['dato_studierett_gyldig_til'],
                            'privatist': row['status_privatist']})

            for row in fs.student.get_eksamensmeldinger(fodselsdato, pnum):
                programmer = []
                for row2 in fs.info.get_emne_i_studieprogram(row['emnekode']):
                    if har_opptak.has_key("%s" % row2['studieprogramkode']):
                        programmer.append(row2['studieprogramkode'])
                ret.append({'ekskode': row['emnekode'],
                            'programmer': ",".join(programmer),
                            'dato': row['dato_opprettet']})

            for row in fs.student.get_utdanningsplan(fodselsdato, pnum):
                ret.append({'studieprogramkode': row['studieprogramkode'],
                            'terminkode_bekreft': row['terminkode_bekreft'],
                            'arstall_bekreft': row['arstall_bekreft'],
                            'dato_bekreftet': row['dato_bekreftet']})

            def _ok_or_not(input):
                """Helper function for proper feedback of status."""
                if not input or input == 'N':
                    return 'Nei'
                if input == 'J':
                    return 'Ja'
                return input

            semregs = tuple(fs.student.get_semreg(fodselsdato, pnum,
                                                  only_valid=False))
            for row in semregs:
                ret.append({'regstatus': _ok_or_not(row['status_reg_ok']),
                            'regformkode': row['regformkode'],
                            'dato_endring': row['dato_endring'],
                            'dato_regform_endret': row['dato_regform_endret']})
                ret.append({'betstatus': _ok_or_not(row['status_bet_ok']),
                            'betformkode': row['betformkode'],
                            'dato_betaling': row['dato_betaling']})
            # The semreg and sembet lines should always be sent, to make it
            # easier for the IT staff to see if a student have paid or not.
            if not semregs:
                ret.append({'regstatus': 'Nei',
                            'regformkode': None,
                            'dato_endring': None,
                            'dato_regform_endret': None})
                ret.append({'betstatus': 'Nei',
                            'betformkode': None,
                            'dato_betaling': None})

        # Check is alive
        #if fs.person.is_dead(fodselsdato, pnum):
        #    ret.append({'status_dod': 'Ja'})
        db.close()
        return ret

    # person user_priority
    all_commands['person_set_user_priority'] = Command(
        ("person", "set_user_priority"), AccountName(),
        SimpleString(help_ref='string_old_priority'),
        SimpleString(help_ref='string_new_priority'))
    def person_set_user_priority(self, operator, account_name,
                                 old_priority, new_priority):
        account = self._get_account(account_name)
        person = self._get_person('entity_id', account.owner_id)
        self.ba.can_set_person_user_priority(operator.get_entity_id(), account)
        try:
            old_priority = int(old_priority)
            new_priority = int(new_priority)
        except ValueError:
            raise CerebrumError, "priority must be a number"
        ou = None
        affiliation = None
        for row in account.get_account_types(filter_expired=False):
            if row['priority'] == old_priority:
                ou = row['ou_id']
                affiliation = row['affiliation']
        if ou is None:
            raise CerebrumError("Must specify an existing priority")
        account.set_account_type(ou, affiliation, new_priority)
        account.write_db()
        return "OK, set priority=%i for %s" % (new_priority, account_name)

    all_commands['person_list_user_priorities'] = Command(
        ("person", "list_user_priorities"), PersonId(),
        fs=FormatSuggestion(
        "%8s %8i %30s %15s", ('uname', 'priority', 'affiliation', 'status'),
        hdr="%8s %8s %30s %15s" % ("Uname", "Priority", "Affiliation", "Status")))
    def person_list_user_priorities(self, operator, person_id):
        ac = Utils.Factory.get('Account')(self.db)
        person = self._get_person(*self._map_person_id(person_id))
        ret = []
        for row in ac.get_account_types(all_persons_types=True,
                                        owner_id=person.entity_id,
                                        filter_expired=False):
            ac2 = self._get_account(row['account_id'], idtype='id')
            if ac2.is_expired() or ac2.is_deleted():
                status = "Expired"
            else:
                status = "Active"
            ou = self._get_ou(ou_id=row['ou_id'])
            ret.append({'uname': ac2.account_name,
                        'priority': row['priority'],
                        'affiliation':
                        '%s@%s' % (self.const.PersonAffiliation(row['affiliation']),
                                   self._format_ou_name(ou)),
                        'status': status})
        return ret

    #
    # quarantine commands
    #

    # quarantine disable
    all_commands['quarantine_disable'] = Command(
        ("quarantine", "disable"), EntityType(default="account"), Id(),
        QuarantineType(), Date(), perm_filter='can_disable_quarantine')
    def quarantine_disable(self, operator, entity_type, id, qtype, date):
        entity = self._get_entity(entity_type, id)
        date = self._parse_date(date)
        qconst = self._get_constant(self.const.Quarantine, qtype, "quarantine")
        self.ba.can_disable_quarantine(operator.get_entity_id(), entity, qtype)

        if not entity.get_entity_quarantine(qtype=qconst):
            raise CerebrumError("%s does not have a quarantine of type %s" % (
                self._get_name_from_object(entity), qtype))

        limit = getattr(cereconf, 'BOFHD_QUARANTINE_DISABLE_LIMIT', None)
        if limit:
            if date > DateTime.today() + DateTime.RelativeDateTime(days=limit):
                return "Quarantines can only be disabled for %d days" % limit
        if date and date < DateTime.today():
            raise CerebrumError("Date can't be in the past")
        entity.disable_entity_quarantine(qconst, date)
        if not date:
            return "OK, reactivated quarantine %s for %s" % (
                qconst, self._get_name_from_object(entity))
        return "OK, disabled quarantine %s for %s" % (
            qconst, self._get_name_from_object(entity))

    # quarantine list
    all_commands['quarantine_list'] = Command(
        ("quarantine", "list"),
        fs=FormatSuggestion("%-16s  %1s  %-17s %s",
                            ('name', 'lock', 'shell', 'desc'),
                            hdr="%-15s %-4s %-17s %s" % \
                            ('Name', 'Lock', 'Shell', 'Description')))
    def quarantine_list(self, operator):
        ret = []
        for c in self.const.fetch_constants(self.const.Quarantine):
            lock = 'N'; shell = '-'
            rule = cereconf.QUARANTINE_RULES.get(str(c), {})
            if 'lock' in rule:
                lock = 'Y'
            if 'shell' in rule:
                shell = rule['shell'].split("/")[-1]
            ret.append({'name': "%s" % c,
                        'lock': lock,
                        'shell': shell,
                        'desc': c.description})
        return ret

    # quarantine remove
    all_commands['quarantine_remove'] = Command(
        ("quarantine", "remove"), EntityType(default="account"), Id(),
        QuarantineType(),
        perm_filter='can_remove_quarantine')
    def quarantine_remove(self, operator, entity_type, id, qtype):
        entity = self._get_entity(entity_type, id)
        qconst = self._get_constant(self.const.Quarantine, qtype, "quarantine")
        self.ba.can_remove_quarantine(operator.get_entity_id(), entity, qconst)

        if not entity.get_entity_quarantine(qtype=qconst):
            raise CerebrumError("%s does not have a quarantine of type %s" % (
                self._get_name_from_object(entity), qtype))

        entity.delete_entity_quarantine(qconst)

        return "OK, removed quarantine %s for %s" % (
            qconst, self._get_name_from_object (entity))

    # quarantine set
    all_commands['quarantine_set'] = Command(
        ("quarantine", "set"), EntityType(default="account"), Id(repeat=True),
        QuarantineType(), SimpleString(help_ref="string_why"),
        SimpleString(help_ref="quarantine_start_date", default="today",
                     optional=True),
        perm_filter='can_set_quarantine')
    def quarantine_set(self, operator, entity_type, id, qtype, why,
                       start_date=None):
        if not start_date or start_date == 'today':
            start_date = self._today()
        else:
            start_date = self._parse_date(start_date)
        entity = self._get_entity(entity_type, id)
        qconst = self._get_constant(self.const.Quarantine, qtype, "quarantine")
        self.ba.can_set_quarantine(operator.get_entity_id(), entity, qconst)
        rows = entity.get_entity_quarantine(qtype=qconst)
        if rows:
            raise CerebrumError("%s already has a quarantine of type %s" % (
                self._get_name_from_object(entity), qtype))
        try:
            entity.add_entity_quarantine(qconst, operator.get_entity_id(), why,
                                         start_date)
        except AttributeError:
            raise CerebrumError("Quarantines cannot be set on %s" % entity_type)
        return "OK, set quarantine %s for %s" % (
            qconst, self._get_name_from_object(entity))

    # quarantine show
    all_commands['quarantine_show'] = Command(
        ("quarantine", "show"), EntityType(default="account"), Id(),
        fs=FormatSuggestion("%-14s %-16s %-16s %-14s %-8s %s",
                            ('type', format_time('start'), format_time('end'),
                             format_day('disable_until'), 'who', 'why'),
                            hdr="%-14s %-16s %-16s %-14s %-8s %s" % \
                            ('Type', 'Start', 'End', 'Disable until', 'Who',
                             'Why')),
        perm_filter='can_show_quarantines')
    def quarantine_show(self, operator, entity_type, id):
        ret = []
        entity = self._get_entity(entity_type, id)
        self.ba.can_show_quarantines(operator.get_entity_id(), entity)
        for r in entity.get_entity_quarantine():
            acc = self._get_account(r['creator_id'], idtype='id')
            ret.append({'type': str(self.const.Quarantine(r['quarantine_type'])),
                        'start': r['start_date'],
                        'end': r['end_date'],
                        'disable_until': r['disable_until'],
                        'who': acc.account_name,
                        'why': r['description']})
        return ret
    #
    # spread commands
    #

    def _get_posix_account(self, account_id):
        """Helper function to try getting a PosixUser-object from an
        Account-id. Ideally this should be doable from self._get_entity,
        and it would probably be reasonable to make PosixUser the default
        object type to return if the PosixUser-module is used in an instance.

        @param account_id: int
        @return: a PosixUser object or None
        """
        try:
            pu = Utils.Factory.get('PosixUser')(self.db)
        except ValueError:
            return None
        else:
            try:
                pu.find(account_id)
            except Errors.NotFoundError:
                return None
            else:
                return pu

    # spread add
    all_commands['spread_add'] = Command(
        ("spread", "add"), EntityType(default='account'), Id(), Spread(),
        perm_filter='can_add_spread')
    def spread_add(self, operator, entity_type, id, spread):
        entity = self._get_entity(entity_type, id)
        spread = self._get_constant(self.const.Spread, spread, "spread")
        self.ba.can_add_spread(operator.get_entity_id(), entity, spread)

        if entity.entity_type != spread.entity_type:
            raise CerebrumError(
                "Spread '%s' is restricted to '%s', selected entity is '%s'" %
                (spread, self.const.EntityType(spread.entity_type),
                 self.const.EntityType(entity.entity_type)))
        # exchange-relatert-jazz
        # NB! no checks are implemented in the group-mixin
        # as we want to let other clients handle these spreads
        # in different manner if needed
        # dissallow spread-setting for distribution groups
        if cereconf.EXCHANGE_GROUP_SPREAD and \
                str(spread) == cereconf.EXCHANGE_GROUP_SPREAD:
            return "Please create distribution group via 'group exchange_create' in bofh"
        if entity_type == 'account':
            pu = self._get_posix_account(entity.entity_id)
            entity = pu if pu is not None else entity
        if entity.has_spread(spread):
            raise CerebrumError("entity id=%s already has spread=%s" %
                                (id, spread))
        try:
            entity.add_spread(spread)
        except (Errors.RequiresPosixError, self.db.IntegrityError) as e:
            raise CerebrumError(str(e))
        entity.write_db()
        if hasattr(self.const, 'spread_uio_nis_fg'):
            if entity_type == 'group' and spread == self.const.spread_uio_nis_fg:
                ad_spread = self.const.spread_uio_ad_group
                if not entity.has_spread(ad_spread):
                    entity.add_spread(ad_spread)
                    entity.write_db()
        return "OK, added spread %s for %s" % (
            spread, self._get_name_from_object(entity))

    # spread list
    all_commands['spread_list'] = Command(
        ("spread", "list"),
        fs=FormatSuggestion("%-14s %s", ('name', 'desc'),
                            hdr="%-14s %s" % ('Name', 'Description')))
    def spread_list(self, operator):
        """
        List out all available spreads.
        """
        ret = []
        spr = Entity.EntitySpread(self.db)
        autospreads = [self.const.human2constant(x, self.const.Spread)
                   for x in getattr(cereconf, 'GROUP_REQUESTS_AUTOSPREADS', ())]
        for s in spr.list_spreads():
            ret.append({'name': s['spread'],
                        'desc': s['description'],
                        'type': s['entity_type_str'],
                        'type_id': s['entity_type'],
                        'spread_code': s['spread_code'],
                        'auto': int(s['spread_code'] in autospreads)})
                        # int() since boolean doesn't work for brukerinfo
        return ret

    # spread remove
    all_commands['spread_remove'] = Command(
        ("spread", "remove"), EntityType(default='account'), Id(), Spread(),
        perm_filter='can_add_spread')
    def spread_remove(self, operator, entity_type, id, spread):
        entity = self._get_entity(entity_type, id)
        spread = self._get_constant(self.const.Spread, spread, "spread")
        self.ba.can_add_spread(operator.get_entity_id(), entity, spread)
        # exchange-relatert-jazz
        # make sure that if anyone uses spread remove instead of
        # group exchange_remove the appropriate clean-up is still
        # done
        if (entity_type == 'group' and
                entity.has_spread(cereconf.EXCHANGE_GROUP_SPREAD)):
            raise CerebrumError(
                "Cannot remove spread from distribution groups")
        if entity_type == 'account':
            pu = self._get_posix_account(entity.entity_id)
            entity = pu if pu is not None else entity
        if entity.has_spread(spread):
            entity.delete_spread(spread)
        else:
            txt = "Entity '%s' does not have spread '%s'" % (id, str(spread))
            raise CerebrumError, txt
        return "OK, removed spread %s from %s" % (
            spread, self._get_name_from_object(entity))

    #
    # trait commands
    #

    # trait info -- show trait values for an entity
    all_commands['trait_info'] = Command(
        ("trait", "info"), Id(help_ref="id:target:account"),
        # Since the FormatSuggestion sorts by the type and not the order of the
        # return data, we send both a string to make it pretty in jbofh, and a
        # list to be used by brukerinfo, which is ignored by jbofh.
        fs=FormatSuggestion("%s", ('text',)),
        perm_filter="can_view_trait")
    def trait_info(self, operator, ety_id):
        ety = self.util.get_target(ety_id, restrict_to=[])
        self.ba.can_view_trait(operator.get_entity_id(), ety=ety)

        ety_name = self._get_name_from_object(ety)

        text = []
        ret = []
        for trait, values in ety.get_traits().items():
            try:
                self.ba.can_view_trait(operator.get_entity_id(), trait=trait,
                                       ety=ety, target=values['target_id'])
            except PermissionDenied:
                continue

            text.append("  Trait:       %s" % str(trait))
            if values['numval'] is not None:
                text.append("    Numeric:   %d" % values['numval'])
            if values['strval'] is not None:
                text.append("    String:    %s" % values['strval'])
            if values['target_id'] is not None:
                target = self.util.get_target(int(values['target_id']))
                text.append("    Target:    %s (%s)" % (
                    self._get_entity_name(target.entity_id, target.entity_type),
                    str(self.const.EntityType(target.entity_type))))
            if values['date'] is not None:
                text.append("    Date:      %s" % values['date'])
            values['trait_name'] = str(trait)
            ret.append(values)
        if text:
            text = ["Entity:        %s (%s)" % (
                ety_name,
                str(self.const.EntityType(ety.entity_type)))] + text
            return {'text': "\n".join(text), 'traits': ret}
        return "%s has no traits" % ety_name

    # trait list -- list all entities with trait
    all_commands['trait_list'] = Command(
        ("trait", "list"), SimpleString(help_ref="trait"),
        fs=FormatSuggestion("%-16s %-16s %s", ('trait', 'type', 'name'),
                            hdr="%-16s %-16s %s" % ('Trait', 'Type', 'Name')),
        perm_filter="can_list_trait")
    def trait_list(self, operator, trait_name):
        trait = self._get_constant(self.const.EntityTrait, trait_name, "trait")
        self.ba.can_list_trait(operator.get_entity_id(), trait=trait)
        ety = self.Account_class(self.db) # exact class doesn't matter
        ret = []
        ety_type = str(self.const.EntityType(trait.entity_type))
        for row in ety.list_traits(trait, return_name=True):
            # TODO: Host, Disk and Person don't use entity_name, so name will
            # be <not set>
            ret.append({'trait': str(trait),
                        'type': ety_type,
                        'name': row['name']})
        ret.sort(lambda x,y: cmp(x['name'], y['name']))
        return ret

    # trait remove -- remove trait from entity
    all_commands['trait_remove'] = Command(
        ("trait", "remove"), Id(help_ref="id:target:account"),
        SimpleString(help_ref="trait"),
        perm_filter="can_remove_trait")
    def trait_remove(self, operator, ety_id, trait_name):
        ety = self.util.get_target(ety_id, restrict_to=[])
        trait = self._get_constant(self.const.EntityTrait, trait_name, "trait")
        self.ba.can_remove_trait(operator.get_entity_id(), ety=ety, trait=trait)

        if isinstance(ety, Utils.Factory.get('Disk')):
            ety_name = ety.path
        elif isinstance(ety, Utils.Factory.get('Person')):
            ety_name = ety.get_name(self.const.system_cached, self.const.name_full)
        else:
            ety_name = ety.get_names()[0][0]
        if ety.get_trait(trait) is None:
            return "%s has no %s trait" % (ety_name, trait)
        ety.delete_trait(trait)
        return "OK, deleted trait %s from %s" % (trait, ety_name)

    # trait set -- add or update a trait
    all_commands['trait_set'] = Command(
        ("trait", "set"), Id(help_ref="id:target:account"),
        SimpleString(help_ref="trait"),
        SimpleString(help_ref="trait_val", repeat=True),
        perm_filter="can_set_trait")
    def trait_set(self, operator, ent_name, trait_name, *values):
        ent = self.util.get_target(ent_name, restrict_to=[])
        trait = self._get_constant(self.const.EntityTrait, trait_name, "trait")
        self.ba.can_set_trait(operator.get_entity_id(), trait=trait, ety=ent)
        params = {}
        for v in values:
            if v.count('='):
                key, value = v.split('=', 1)
            else:
                key = v; value = ''
            key = self.util.get_abbr_type(key, ('target_id', 'date', 'numval',
                                                'strval'))
            if value == '':
                params[key] = None
            elif key == 'target_id':
                target = self.util.get_target(value, restrict_to=[])
                params[key] = target.entity_id
            elif key == 'date':
                # TODO: _parse_date only handles dates, not hours etc.
                params[key] = self._parse_date(value)
            elif key == 'numval':
                params[key] = int(value)
            elif key == 'strval':
                params[key] = value
        ent.populate_trait(trait, **params)
        ent.write_db()
        return "Ok, set trait %s for %s" % (trait_name, ent_name)

    # trait types -- list out the defined trait types
    all_commands['trait_types'] = Command(
        ("trait", "types"),
        fs=FormatSuggestion("%-25s %s", ('trait', 'description'),
                            hdr="%-25s %s" % ('Trait', 'Description')),
        perm_filter="can_set_trait")
    def trait_types(self, operator):
        self.ba.can_set_trait(operator.get_entity_id())
        ret = [{"trait": str(x),
                 "description": x.description}
                for x in self.const.fetch_constants(self.const.EntityTrait)]
        return sorted(ret, key=lambda x: x['trait'])

    #
    # user commands
    #

    # user affiliation_add
    all_commands['user_affiliation_add'] = Command(
        ("user", "affiliation_add"),
        AccountName(), OU(), Affiliation(), AffiliationStatus(),
        perm_filter='can_add_account_type')
    def user_affiliation_add(self, operator, accountname, ou, aff, aff_status):
        account = self._get_account(accountname)
        person = self._get_person('entity_id', account.owner_id)
        ou, aff, aff_status = self._person_affiliation_add_helper(
            operator, person, ou, aff, aff_status)
        self.ba.can_add_account_type(operator.get_entity_id(), account,
                                     ou, aff, aff_status)
        account.set_account_type(ou.entity_id, aff)

        # When adding an affiliation manually, make sure the user gets
        # the e-mail addresses associated with it automatically.  To
        # achieve this, we temporarily change the priority to 1 and
        # call write_db.  This will displace an existing priority 1 if
        # there is one, but it's not worthwhile to do this perfectly.
        for row in account.get_account_types(filter_expired=False):
            if row['ou_id'] == ou.entity_id and row['affiliation'] == aff:
                priority = row['priority']
                break
        account.set_account_type(ou.entity_id, aff, 1)
        account.write_db()
        account.set_account_type(ou.entity_id, aff, priority)
        account.write_db()
        return "OK, added %s@%s to %s" % (aff, self._format_ou_name(ou),
                                          accountname)

    # user affiliation_remove
    all_commands['user_affiliation_remove'] = Command(
        ("user", "affiliation_remove"), AccountName(), OU(), Affiliation(),
        perm_filter='can_remove_account_type')
    def user_affiliation_remove(self, operator, accountname, ou, aff):
        account = self._get_account(accountname)
        aff = self._get_affiliationid(aff)
        ou = self._get_ou(stedkode=ou)
        self.ba.can_remove_account_type(operator.get_entity_id(),
                                        account, ou, aff)
        account.del_account_type(ou.entity_id, aff)
        account.write_db()
        return "OK, removed %s@%s from %s" % (aff, self._format_ou_name(ou),
                                              accountname)

    all_commands['user_create_unpersonal'] = Command(
        ('user', 'create_unpersonal'),
        AccountName(), GroupName(), EmailAddress(),
        SimpleString(help_ref="string_np_type"),
        fs=FormatSuggestion("Created account_id=%i", ("account_id",)),
        perm_filter='can_create_user_unpersonal')

    def user_create_unpersonal(self, operator, account_name, group_name,
                               contact_address, account_type):
        owner_group = self._get_group(group_name)
        self.ba.can_create_user_unpersonal(operator.get_entity_id(),
                                           group=owner_group)

        account_type = self._get_constant(self.const.Account, account_type,
                                          "account type")
        account = self._user_create_basic(operator, owner_group, account_name,
                                          account_type)
        self._user_password(operator, account)

        # Validate the contact address
        # TBD: Check if address is instance-internal?
        _, domain = self._split_email_address(contact_address)
        ed = Email.EmailDomain(self.db)
        try:
            ed._validate_domain_name(domain)
        except AttributeError as e:
            raise CerebrumError("Invalid contact address: {}".format(e))

        # Unpersonal accounts shouldn't normally have a mail inbox, but they
        # get a forward target for the account, to be sent to those responsible
        # for the account, preferrably a sysadm mail list.
        if hasattr(self, 'entity_contactinfo_add'):
            account.add_contact_info(self.const.system_manual,
                                     self.const.contact_email,
                                     contact_address)
        # TBD: Better way of checking if email forwards are in use, by
        # checking if bofhd command is available?
        if hasattr(self, 'email_create_forward_target'):
            localaddr = '{}@{}'.format(account_name,
                                       cereconf.EMAIL_DEFAULT_DOMAIN)
            self._email_create_forward_target(localaddr, contact_address)

        quar = cereconf.BOFHD_CREATE_UNPERSONAL_QUARANTINE
        if quar:
            qconst = self._get_constant(self.const.Quarantine, quar,
                                        "quarantine")
            account.add_entity_quarantine(qconst, operator.get_entity_id(),
                                          "Not granted for global password "
                                          "auth (ask IT-sikkerhet)",
                                          self._today())
        return {'account_id': int(account.entity_id)}

    def _user_create_prompt_func(self, session, *args):
        """A prompt_func on the command level should return
        {'prompt': message_string, 'map': dict_mapping}
        - prompt is simply shown.
        - map (optional) maps the user-entered value to a value that
          is returned to the server, typically when user selects from
          a list."""
        all_args = list(args[:])

        if not all_args:
            return {'prompt': 'Person identification',
                    'help_ref': 'user_create_person_id'}
        arg = all_args.pop(0)
        if not all_args:
            c = self._find_persons(arg)
            person_map = [(('%-8s %s', 'Id', 'Name'), None)]
            for i in range(len(c)):
                person = self._get_person('entity_id', c[i]['person_id'])
                person_map.append((
                    ('%8i %s', int(c[i]['person_id']),
                     person.get_name(self.const.system_cached,
                                     self.const.name_full)),
                    int(c[i]['person_id'])))
            if not len(person_map) > 1:
                raise CerebrumError('No persons matched')
            return {'prompt': 'Choose person from list',
                    'map': person_map,
                    'help_ref': 'user_create_select_person'}
        owner_id = all_args.pop(0)
        person = self._get_person('entity_id', owner_id)
        existing_accounts = []
        account = self.Account_class(self.db)
        for r in account.list_accounts_by_owner_id(person.entity_id):
            account = self._get_account(r['account_id'], idtype='id')
            if account.expire_date:
                exp = account.expire_date.strftime('%Y-%m-%d')
            else:
                exp = '<not set>'
            existing_accounts.append('%-10s %s' % (account.account_name,
                                                   exp))
        if existing_accounts:
            existing_accounts = 'Existing accounts:\n%-10s %s\n%s\n' % (
                'uname', 'expire', '\n'.join(existing_accounts))
        else:
            existing_accounts = ''
        if existing_accounts:
            if not all_args:
                return {'prompt': '%sContinue? (y/n)' % existing_accounts}
            yes_no = all_args.pop(0)
            if not yes_no == 'y':
                raise CerebrumError('Command aborted at user request')
        if not all_args:
            aff_map = [(('%-8s %s', 'Num', 'Affiliation'), None)]
            for aff in person.get_affiliations():
                ou = self._get_ou(ou_id=aff['ou_id'])
                name = '%s@%s' % (
                    self.const.PersonAffStatus(aff['status']),
                    self._format_ou_name(ou))
                aff_map.append((('%s', name),
                                {'ou_id': int(aff['ou_id']),
                                 'aff': int(aff['affiliation'])}))
            if not len(aff_map) > 1:
                raise CerebrumError('Person has no affiliations.')
            return {'prompt': 'Choose affiliation from list', 'map': aff_map}
        all_args.pop(0)  # affiliation =
        if not all_args:
            return {'prompt': 'Shell', 'default': 'bash'}
        all_args.pop(0)  # shell =
        if not all_args:
            return {'prompt': 'Disk', 'help_ref': 'disk'}
        all_args.pop(0)  # disk =
        if not all_args:
            ret = {'prompt': 'Username', 'last_arg': True}
            posix_user = Utils.Factory.get('PosixUser')(self.db)
            try:
                person = self._get_person('entity_id', owner_id)
                fname, lname = [
                    person.get_name(self.const.system_cached, v)
                    for v in (self.const.name_first,
                              self.const.name_last)]
                sugg = posix_user.suggest_unames(
                    self.const.account_namespace, fname, lname)
                if sugg:
                    ret['default'] = sugg[0]
            except ValueError:
                pass    # Failed to generate a default username
            return ret
        if len(all_args) == 1:
            return {'last_arg': True}
        raise CerebrumError('Too many arguments')

    all_commands['user_create_personal'] = Command(
        ('user', 'create_personal'), prompt_func=_user_create_prompt_func,
        fs=FormatSuggestion("Created uid=%i", ("uid",)),
        perm_filter='can_create_user')

    def user_create_personal(self, operator, *args):
        if len(args) == 6:
            idtype, person_id, affiliation, shell, home, uname = args
        else:
            idtype, person_id, yes_no, affiliation, shell, home, uname = args
        owner_type = self.const.entity_person
        owner_id = self._get_person('entity_id', person_id).entity_id
        np_type = None

        # Only superusers should be allowed to create users with
        # capital letters in their ids, and even then, just for system
        # users
        if uname != uname.lower():
            if (not self.ba.is_superuser(operator.get_entity_id()) and
                    owner_type != self.const.entity_group):
                    raise CerebrumError(
                        'Personal account names cannot contain '
                        'capital letters')

        posix_user = Utils.Factory.get('PosixUser')(self.db)
        uid = posix_user.get_free_uid()
        shell = self._get_shell(shell)
        if home[0] != ':':  # Hardcoded path
            disk_id, home = self._get_disk(home)[1:3]
        else:
            if not self.ba.is_superuser(operator.get_entity_id()):
                raise PermissionDenied(
                    'Only superusers may use hardcoded path')
            disk_id, home = None, home[1:]
        posix_user.clear()
        gecos = None
        expire_date = None
        self.ba.can_create_user(operator.get_entity_id(), owner_id, disk_id)

        posix_user.populate(uid, None, gecos, shell, name=uname,
                            owner_type=owner_type,
                            owner_id=owner_id, np_type=np_type,
                            creator_id=operator.get_entity_id(),
                            expire_date=expire_date)
        try:
            posix_user.write_db()
            for spread in cereconf.BOFHD_NEW_USER_SPREADS:
                posix_user.add_spread(self.const.Spread(spread))
            homedir_id = posix_user.set_homedir(
                disk_id=disk_id, home=home,
                status=self.const.home_status_not_created)
            posix_user.set_home(self.const.spread_uio_nis_user, homedir_id)
            # For correct ordering of ChangeLog events, new users
            # should be signalled as "exported to" a certain system
            # before the new user's password is set.  Such systems are
            # flawed, and should be fixed.
            passwd = posix_user.make_passwd(uname)
            posix_user.set_password(passwd)
            # And, to write the new password to the database, we have
            # to .write_db() one more time...
            posix_user.write_db()
            if len(args) != 5:
                ou_id, affiliation = affiliation['ou_id'], affiliation['aff']
                self._user_create_set_account_type(posix_user, owner_id,
                                                   ou_id, affiliation)
        except self.db.DatabaseError, m:
            raise CerebrumError('Database error: {}'.format(m))
        operator.store_state('new_account_passwd',
                             {'account_id': int(posix_user.entity_id),
                              'password': passwd})
        return {'uid': uid}

    all_commands['user_reserve_personal'] = Command(
        ('user', 'reserve_personal'),
        PersonId(), AccountName(),
        fs=FormatSuggestion('Created account_id=%i', ('account_id',)),
        perm_filter='is_superuser')

    def user_reserve_personal(self, operator, person_id, uname):
        person = self._get_person(*self._map_person_id(person_id))
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied('Only superusers may reserve users')
        account = self._user_create_basic(operator, person, uname)
        self._user_password(operator, account)
        return {'account_id': int(account.entity_id)}

    all_commands['user_create_sysadm'] = Command(
        ("user", "create_sysadm"), AccountName(), OU(optional=True),
        YesNo(help_ref="yes_no_force", optional=True, default="No"),
        fs=FormatSuggestion('OK, created %s', ('accountname',)),
        perm_filter='can_create_sysadm')

    def user_create_sysadm(self, operator, accountname, stedkode=None,
                           force=None):
        """ Create a sysadm account with the given accountname.

        TBD, requirements?
            - Will add the person's primary affiliation, which must be
              of type ANSATT/tekadm.

        :param str accountname:
            Account to be created. Must include a hyphen and end with one of
            SYSADM_TYPES.

        :param str stedkode:
            Optional stedkode to place the sysadm account. Only used if a
            person have multipile valid affiliations.

        """
        SYSADM_TYPES = ('adm', 'drift', 'null')
        VALID_STATUS = (self.const.affiliation_status_ansatt_tekadm,
                        self.const.affiliation_status_ansatt_vitenskapelig)
        DOMAIN = '@ulrik.uio.no'

        self.ba.can_create_sysadm(operator.get_entity_id())

        res = re.search('^([a-z]+)-([a-z]+)$', accountname)
        if res is None:
            raise CerebrumError('Username must be on the form "foo-drift"')
        user, suffix = res.groups()
        if suffix not in SYSADM_TYPES:
            raise CerebrumError(
                'Username "%s" does not have one of these suffixes: %s' %
                (accountname, ', '.join(SYSADM_TYPES)))
        # Funky... better solutions?
        try:
            self._get_account(accountname)
        except CerebrumError:
            pass
        else:
            raise CerebrumError('Username already in use')
        account_owner = self._get_account(user)
        if account_owner.owner_type != self.const.entity_person:
            raise CerebrumError('Can only create personal sysadm accounts')
        person = self._get_person('account_name', user)

        # Need to force if person already has a sysadm account
        if not self._is_yes(force):
            ac = self.Account_class(self.db)
            suffix = '-{}'.format(suffix)
            existing = filter(lambda x: x['name'].endswith(suffix),
                              ac.search(owner_id=person.entity_id))
            if existing:
                self.logger.debug2("Existing accounts: {}".format(existing))
                raise CerebrumError(
                    'Person already has a sysadm account: {} (need to '
                    'force)'.format(existing[0]['name']))

        if stedkode is not None:
            ou = self._get_ou(stedkode=stedkode)
            ou_id = ou.entity_id
        else:
            ou_id = None
        valid_aff = person.list_affiliations(person_id=person.entity_id,
                                             source_system=self.const.system_sap,
                                             status=VALID_STATUS,
                                             ou_id=ou_id)
        status_blob = ', '.join(map(str, VALID_STATUS))
        if valid_aff == []:
            raise CerebrumError('Person has no %s affiliation' % status_blob)
        elif len(valid_aff) > 1:
            raise CerebrumError('More than than one %s affiliation, '
                                'add stedkode as argument' % status_blob)
        account = self._user_create_basic(operator, person, accountname)
        self._user_password(operator, account)
        self._user_create_set_account_type(account, person.entity_id,
                                           valid_aff[0]['ou_id'],
                                           valid_aff[0]['affiliation'],
                                           priority=900)
        account.populate_trait(code=self.const.trait_sysadm_account,
                               strval='on')
        account.write_db()
        # Promote POSIX:
        pu = Utils.Factory.get('PosixUser')(self.db)
        pu.populate(pu.get_free_uid(), None, None,
                    shell=self.const.posix_shell_bash, parent=account,
                    creator_id=operator.get_entity_id())
        pu.write_db()
        default_home_spread = self._get_constant(self.const.Spread,
                                                 cereconf.DEFAULT_HOME_SPREAD,
                                                 "spread")
        pu.add_spread(default_home_spread)
        homedir_id = pu.set_homedir(home='/',
                                    status=self.const.home_status_not_created)
        pu.set_home(default_home_spread, homedir_id)
        pu.write_db()

        account.add_spread(self.const.spread_uio_ad_account)
        account.add_contact_info(self.const.system_manual,
                                 type=self.const.contact_email,
                                 value=user+DOMAIN)
        account.write_db()
        self._email_create_forward_target(accountname+DOMAIN, user+DOMAIN)
        return {'accountname': accountname}

    def _check_for_pipe_run_as(self, account_id):
        et = Email.EmailTarget(self.db)
        try:
            et.clear()
            et.find_by_email_target_attrs(target_type=self.const.email_target_pipe,
                                          using_uid=account_id)
        except Errors.NotFoundError:
            return False
        except Errors.TooManyRowsError:
            return True
        return True

    # user delete
    all_commands['user_delete'] = Command(
        ("user", "delete"), AccountName(), perm_filter='can_delete_user')
    def user_delete(self, operator, accountname):
        # TODO: How do we delete accounts?
        account = self._get_account(accountname)
        self.ba.can_delete_user(operator.get_entity_id(), account)
        if account.is_deleted():
            raise CerebrumError, "User is already deleted"
        if self._check_for_pipe_run_as(account.entity_id):
            raise CerebrumError, ("User is associated with an e-mail pipe " +
                                  "and cannot be deleted until the pipe is " +
                                  "removed. Please notify postmaster if you " +
                                  "are not able to remove the pipe yourself.")

        # Here we'll register a bofhd_reguest to archive the content of the
        # users home directory.
        br = BofhdRequests(self.db, self.const)
        br.add_request(operator.get_entity_id(), br.now,
                       self.const.bofh_delete_user,
                       account.entity_id, None,
                       state_data=int(self.const.spread_uio_nis_user))
        return "User %s queued for deletion immediately" % account.account_name

    all_commands['user_set_disk_quota'] = Command(
        ("user", "set_disk_quota"), AccountName(), Integer(help_ref="disk_quota_size"),
        Date(help_ref="disk_quota_expire_date"), SimpleString(help_ref="string_why"),
        perm_filter='can_set_disk_quota')
    def user_set_disk_quota(self, operator, accountname, size, date, why):
        account = self._get_account(accountname)
        try:
            age = DateTime.strptime(date, '%Y-%m-%d') - DateTime.now()
        except:
            raise CerebrumError, "Error parsing date"
        why = why.strip()
        if len(why) < 3:
            raise CerebrumError, "Why cannot be blank"
        unlimited = forever = False
        if age.days > 185:
            forever = True
        try:
            size = int(size)
        except ValueError:
            raise CerebrumError, "Expected int as size"
        if size > 1024 or size < 0:    # "unlimited" for perm-check = +1024M
            unlimited = True
        self.ba.can_set_disk_quota(operator.get_entity_id(), account,
                                   unlimited=unlimited, forever=forever)
        home = account.get_home(self.const.spread_uio_nis_user)
        _date = self._parse_date(date)
        if size < 0:               # Unlimited
            size = None
        dq = DiskQuota(self.db)
        dq.set_quota(home['homedir_id'], override_quota=size,
                     override_expiration=_date, description=why)
        return "OK, quota overridden for %s" % accountname

    # user gecos
    all_commands['user_gecos'] = Command(
        ("user", "gecos"), AccountName(), PosixGecos(),
        perm_filter='can_set_gecos')
    def user_gecos(self, operator, accountname, gecos):
        account = self._get_account(accountname, actype="PosixUser")
        # Set gecos to NULL if user requests a whitespace-only string.
        self.ba.can_set_gecos(operator.get_entity_id(), account)
        # TBD: Should we allow 8-bit characters?
        try:
            gecos.encode("ascii")
        except UnicodeDecodeError:
            raise CerebrumError, "GECOS can only contain US-ASCII."
        account.gecos = gecos.strip() or None
        account.write_db()
        # TBD: As the 'gecos' attribute lives in class PosixUser,
        # which is ahead of AccountEmailMixin in the MRO of 'account',
        # the write_db() method of AccountEmailMixin will receive a
        # "no updates happened" from its call to superclasses'
        # write_db().  Is there a better way to solve this kind of
        # problem than by adding explicit calls to one if the mixin's
        # methods?  The following call will break if anyone tries this
        # code with an Email-less cereconf.CLASS_ACCOUNT.
        account.update_email_addresses()
        return "OK, set gecos for %s to '%s'" % (accountname, gecos)

    # user history
    all_commands['user_history'] = Command(
        ("user", "history"), AccountName(),
        fs=FormatSuggestion("%s [%s]: %s",
                            ("timestamp", "change_by", "message")),
        perm_filter='can_show_history')
    def user_history(self, operator, accountname):
        return self.entity_history(operator, accountname)

    # user info
    all_commands['user_info'] = Command(
        ("user", "info"), AccountName(),
        fs=FormatSuggestion([("Username:      %s\n"+
                              "Spreads:       %s\n" +
                              "Affiliations:  %s\n" +
                              "Expire:        %s\n" +
                              "Home:          %s (status: %s)\n" +
                              "Entity id:     %i\n" +
                              "Owner id:      %i (%s: %s)",
                              ("username", "spread", "affiliations",
                               format_day("expire"),
                               "home", "home_status", "entity_id", "owner_id",
                               "owner_type", "owner_desc")),
                             ("Disk quota:    %s MiB",
                              ("disk_quota",)),
                             ("DQ override:   %s MiB (until %s: %s)",
                              ("dq_override", format_day("dq_expire"), "dq_why")),
                             ("UID:           %i\n" +
                              "Default fg:    %i=%s\n" +
                              "Gecos:         %s\n" +
                              "Shell:         %s",
                              ('uid', 'dfg_posix_gid', 'dfg_name', 'gecos',
                               'shell')),
                             ("Quarantined:   %s",
                              ("quarantined",))]))
    def user_info(self, operator, accountname):
        is_posix = False
        try:
            account = self._get_account(accountname, actype="PosixUser")
            is_posix = True
        except CerebrumError:
            account = self._get_account(accountname)
        if account.is_deleted() and not self.ba.is_superuser(operator.get_entity_id()):
            raise CerebrumError("User '{}' is deleted".format(
                account.account_name))
        affiliations = []
        for row in account.get_account_types(filter_expired=False):
            ou = self._get_ou(ou_id=row['ou_id'])
            affiliations.append("%s@%s" %
                                (self.const.PersonAffiliation(row['affiliation']),
                                 self._format_ou_name(ou)))
        tmp = {'disk_id': None, 'home': None, 'status': None,
               'homedir_id': None}
        home_status = None
        spread = 'spread_uio_nis_user'
        if spread in cereconf.HOME_SPREADS:
            try:
                tmp = account.get_home(getattr(self.const, spread))
                home_status = str(self.const.AccountHomeStatus(tmp['status']))
            except Errors.NotFoundError:
                pass

        ret = {'entity_id': account.entity_id,
               'username': account.account_name,
               'spread': ",".join([str(self.const.Spread(a['spread']))
                                   for a in account.get_spread()]),
               'affiliations': (",\n" + (" " * 15)).join(affiliations),
               'expire': account.expire_date,
               'home_status': home_status,
               'owner_id': account.owner_id,
               'owner_type': str(self.const.EntityType(account.owner_type))
               }
        try:
            self.ba.can_show_disk_quota(operator.get_entity_id(), account)
            can_see_quota = True
        except PermissionDenied:
            can_see_quota = False
        if tmp['disk_id'] and can_see_quota:
            disk = Utils.Factory.get("Disk")(self.db)
            disk.find(tmp['disk_id'])
            def_quota = disk.get_default_quota()
            try:
                dq = DiskQuota(self.db)
                dq_row = dq.get_quota(tmp['homedir_id'])
                if not(dq_row['quota'] is None or def_quota is False):
                    ret['disk_quota'] = str(dq_row['quota'])
                # Only display recent quotas
                days_left = ((dq_row['override_expiration'] or DateTime.Epoch) -
                             DateTime.now()).days
                if days_left > -30:
                    ret['dq_override'] = dq_row['override_quota']
                    if dq_row['override_quota'] is not None:
                        ret['dq_override'] = str(dq_row['override_quota'])
                    ret['dq_expire'] = dq_row['override_expiration']
                    ret['dq_why'] = dq_row['description']
                    if days_left < 0:
                        ret['dq_why'] += " [INACTIVE]"
            except Errors.NotFoundError:
                if def_quota:
                    ret['disk_quota'] = "(%s)" % def_quota

        if account.owner_type == self.const.entity_person:
            person = self._get_person('entity_id', account.owner_id)
            try:
                p_name = person.get_name(self.const.system_cached,
                                         getattr(self.const,
                                                 cereconf.DEFAULT_GECOS_NAME))
            except Errors.NotFoundError:
                p_name = '<none>'
            ret['owner_desc'] = p_name
        else:
            grp = self._get_group(account.owner_id, idtype='id')
            ret['owner_desc'] = grp.group_name

        # home is not mandatory for some of the instances that "copy"
        # this user_info-method
        if tmp['disk_id'] or tmp['home']:
            ret['home'] = account.resolve_homedir(disk_id=tmp['disk_id'],
                                                  home=tmp['home'])
        else:
            ret['home'] = None
        if is_posix:
            group = self._get_group(account.gid_id, idtype='id', grtype='PosixGroup')
            ret['uid'] = account.posix_uid
            ret['dfg_posix_gid'] = group.posix_gid
            ret['dfg_name'] = group.group_name
            ret['gecos'] = account.gecos
            ret['shell'] = str(self.const.PosixShell(account.shell))
        # TODO: Return more info about account
        quarantined = None
        now = DateTime.now()
        for q in account.get_entity_quarantine():
            if q['start_date'] <= now:
                if (q['end_date'] is not None and
                    q['end_date'] < now):
                    quarantined = 'expired'
                elif (q['disable_until'] is not None and
                    q['disable_until'] > now):
                    quarantined = 'disabled'
                else:
                    quarantined = 'active'
                    break
            else:
                quarantined = 'pending'
        if quarantined:
            ret['quarantined'] = quarantined
        return ret


    def _get_cached_passwords(self, operator):
        ret = []
        for r in operator.get_state():
            # state_type, entity_id, state_data, set_time
            if r['state_type'] in ('new_account_passwd', 'user_passwd'):
                ret.append({'account_id': self._get_entity_name(
                                                  r['state_data']['account_id'],
                                                  self.const.entity_account),
                            'password': r['state_data']['password'],
                            'operation': r['state_type']})
        return ret

    all_commands['user_find'] = Command(
        ("user", "find"),
        UserSearchType(),
        SimpleString(),
        YesNo(optional=True, default='n', help_ref='yes_no_include_expired'),
        SimpleString(optional=True, help_ref="affiliation_optional"),
        fs=FormatSuggestion("%7i   %-12s %s", ('entity_id', 'username',
                                               format_day("expire")),
                            hdr="%7s   %-10s   %-12s" % ('Id', 'Username',
                                                         'Expire date')))

    def user_find(self, operator, search_type, value,
                  include_expired="no", aff_filter=None):
        acc = self.Account_class(self.db)
        if aff_filter is not None:
            try:
                aff_filter = int(self.const.PersonAffiliation(aff_filter))
            except Errors.NotFoundError:
                raise CerebrumError, "Invalid affiliation %s" % aff_filter
        filter_expired = not self._get_boolean(include_expired)

        if search_type == 'stedkode':
            ou = self._get_ou(stedkode=value)
            rows = acc.list_accounts_by_type(ou_id=ou.entity_id,
                                             affiliation=aff_filter,
                                             filter_expired=filter_expired)
        elif search_type == 'host':
            # FIXME: filtering on affiliation is not implemented
            host = self._get_host(value)
            rows = acc.list_account_home(host_id=int(host.entity_id),
                                         filter_expired=filter_expired)
        elif search_type == 'disk':
            # FIXME: filtering on affiliation is not implemented
            disk = self._get_disk(value)[0]
            rows = acc.list_account_home(disk_id=int(disk.entity_id),
                                         filter_expired=filter_expired)
        else:
            raise CerebrumError, "Unknown search type (%s)" % search_type
        seen = {}
        ret = []
        for r in rows:
            a = int(r['account_id'])
            if a in seen:
                continue
            seen[a] = True
            acc.clear()
            acc.find(a)
            ret.append({'entity_id': a,
                        'expire': acc.expire_date,
                        'username': acc.account_name})
        ret.sort(lambda x, y: cmp(x['username'], y['username']))
        return ret

    # user move prompt
    def user_move_prompt_func(self, session, *args):
        u""" user move prompt helper

        Base command:
          user move <move-type> <account-name>
        Variants
          user move immediate   <account-name> <disk-id> <reason>
          user move batch       <account-name> <disk-id> <reason>
          user move nofile      <account-name> <disk-id> <reason>
          user move hard_nofile <account-name> <disk-id> <reason>
          user move request     <account-name> <disk-id> <reason>
          user move give        <account-name> <group-name> <reason>

        """
        help_struct = Help([self, ], logger=self.logger)
        all_args = list(args)
        if not all_args:
            return MoveType().get_struct(help_struct)
        move_type = all_args.pop(0)
        if not all_args:
            return AccountName().get_struct(help_struct)
        # pop account name
        all_args.pop(0)
        if move_type in (
                "immediate", "batch", "nofile", "hard_nofile"):
            # move_type needs disk-id
            if not all_args:
                r = DiskId().get_struct(help_struct)
                r['last_arg'] = True
                return r
            return {'last_arg': True}
        elif move_type in (
                "student", "student_immediate", "confirm", "cancel"):
            # move_type doesnt need more args
            return {'last_arg': True}
        elif move_type in ("request",):
            # move_type needs disk-id and reason
            if not all_args:
                return DiskId().get_struct(help_struct)
            # pop disk id
            all_args.pop(0)
            if not all_args:
                r = SimpleString(help_ref="string_why").get_struct(help_struct)
                r['last_arg'] = True
                return r
            return {'last_arg': True}
        elif move_type in ("give",):
            # move_type needs group-name and reason
            if not all_args:
                return GroupName().get_struct(help_struct)
            # pop group-name
            all_args.pop(0)
            if not all_args:
                r = SimpleString(help_ref="string_why").get_struct(help_struct)
                r['last_arg'] = True
                return r
            return {'last_arg': True}
        raise CerebrumError("Bad user_move command ({!s})".format(move_type))

    #
    # user move <move-type> <account-name> [opts]
    #
    all_commands['user_move'] = Command(
        ("user", "move"),
        prompt_func=user_move_prompt_func,
        perm_filter='can_move_user')

    def user_move(self, operator, move_type, accountname, *args):
        """
        """
        # now strip all str / unicode arguments in order to please CRB-2172
        def strip_arg(arg):
            if isinstance(arg, basestring):
                return arg.strip()
            return arg
        args = tuple(map(strip_arg, args))
        self.logger.debug('user_move: after stripping args ({args})'.format(
            args=args))
        account = self._get_account(accountname)
        account_error = lambda reason: "Cannot move {!r}, {!s}".format(
            account.account_name, reason)

        REQUEST_REASON_MAX_LEN = 80

        def _check_reason(reason):
            if len(reason) > REQUEST_REASON_MAX_LEN:
                raise CerebrumError(
                    "Too long explanation, "
                    "maximum length is {:d}".format(REQUEST_REASON_MAX_LEN))

        if account.is_expired():
            raise CerebrumError(account_error("account is expired"))
        br = BofhdRequests(self.db, self.const)
        spread = int(self.const.spread_uio_nis_user)
        if move_type in ("immediate", "batch", "student", "student_immediate",
                         "request", "give"):
            try:
                ah = account.get_home(spread)
            except Errors.NotFoundError:
                raise CerebrumError(account_error("account has no home"))
        if move_type in ("immediate", "batch", "nofile"):
            message = ""
            disk, disk_id = self._get_disk(args[0])[:2]
            if disk_id is None:
                raise CerebrumError(account_error("bad destination disk"))
            self.ba.can_move_user(operator.get_entity_id(), account, disk_id)

            for r in account.get_spread():
                if (r['spread'] == self.const.spread_ifi_nis_user
                        and not re.match(r'^/ifi/', args[0])):
                    message += ("WARNING: moving user with %s-spread to "
                                "a non-Ifi disk.\n" %
                                self.const.spread_ifi_nis_user)
                    break

            # Let's check the disk quota settings.  We only give a an
            # information message, the actual change happens when
            # set_homedir is done.
            default_dest_quota = disk.get_default_quota()
            current_quota = None
            dq = DiskQuota(self.db)
            try:
                ah = account.get_home(spread)
            except Errors.NotFoundError:
                raise CerebrumError(account_error("account has no home"))
            try:
                dq_row = dq.get_quota(ah['homedir_id'])
            except Errors.NotFoundError:
                pass
            else:
                current_quota = dq_row['quota']
                if dq_row['quota'] is not None:
                    current_quota = dq_row['quota']
                days_left = ((dq_row['override_expiration'] or
                              DateTime.Epoch) - DateTime.now()).days
                if days_left > 0 and dq_row['override_quota'] is not None:
                    current_quota = dq_row['override_quota']

            if current_quota is None:
                # this is OK
                pass
            elif default_dest_quota is False:
                message += ("Destination disk has no quota, so the current "
                            "quota (%d) will be cleared.\n" % current_quota)
            elif current_quota <= default_dest_quota:
                message += ("Current quota (%d) is smaller or equal to the "
                            "default at destination (%d), so it will be "
                            "removed.\n") % (current_quota, default_dest_quota)

            if move_type == "immediate":
                br.add_request(operator.get_entity_id(), br.now,
                               self.const.bofh_move_user_now,
                               account.entity_id, disk_id, state_data=spread)
                message += "Command queued for immediate execution."
            elif move_type == "batch":
                br.add_request(operator.get_entity_id(), br.batch_time,
                               self.const.bofh_move_user,
                               account.entity_id, disk_id, state_data=spread)
                message += ("Move queued for execution at %s." %
                            self._date_human_readable(br.batch_time))
                # mail user about the awaiting move operation
                new_homedir = disk.path + '/' + account.account_name
                try:
                    mail_template(
                        account.get_primary_mailaddress(),
                        cereconf.USER_BATCH_MOVE_WARNING,
                        substitute={'USER': account.account_name,
                                    'TO_DISK': new_homedir})
                except Exception as e:
                    self.logger.info("Sending mail failed: %s", e)
            elif move_type == "nofile":
                ah = account.get_home(spread)
                account.set_homedir(current_id=ah['homedir_id'],
                                    disk_id=disk_id)
                account.write_db()
                message += "User moved."
            return message
        elif move_type in ("hard_nofile",):
            if not self.ba.is_superuser(operator.get_entity_id()):
                raise PermissionDenied("only superusers may use hard_nofile")
            ah = account.get_home(spread)
            account.set_homedir(current_id=ah['homedir_id'], home=args[0])
            return "OK, user moved to hardcoded homedir"
        elif move_type in (
                "student", "student_immediate", "confirm", "cancel"):
            self.ba.can_give_user(operator.get_entity_id(), account)
            if move_type == "student":
                br.add_request(operator.get_entity_id(), br.batch_time,
                               self.const.bofh_move_student,
                               account.entity_id, None, state_data=spread)
                return ("student-move queued for execution at %s" %
                        self._date_human_readable(br.batch_time))
            elif move_type == "student_immediate":
                br.add_request(operator.get_entity_id(), br.now,
                               self.const.bofh_move_student,
                               account.entity_id, None, state_data=spread)
                return "student-move queued for immediate execution"
            elif move_type == "confirm":
                r = br.get_requests(entity_id=account.entity_id,
                                    operation=self.const.bofh_move_request)
                if not r:
                    raise CerebrumError("No matching request found")
                br.delete_request(account.entity_id,
                                  operation=self.const.bofh_move_request)
                # Flag as authenticated
                br.add_request(operator.get_entity_id(), br.batch_time,
                               self.const.bofh_move_user,
                               account.entity_id, r[0]['destination_id'],
                               state_data=spread)
                return ("move queued for execution at %s" %
                        self._date_human_readable(br.batch_time))
            elif move_type == "cancel":
                # TBD: Should superuser delete other request types as well?
                count = 0
                for tmp in br.get_requests(entity_id=account.entity_id):
                    if tmp['operation'] in (
                            self.const.bofh_move_student,
                            self.const.bofh_move_user,
                            self.const.bofh_move_give,
                            self.const.bofh_move_request,
                            self.const.bofh_move_user_now):
                        count += 1
                        br.delete_request(request_id=tmp['request_id'])
                return "OK, %i bofhd requests deleted" % count
        elif move_type in ("request",):
            disk = args[0]
            why = args[1]
            disk_id = self._get_disk(disk)[1]
            _check_reason(why)
            self.ba.can_receive_user(
                operator.get_entity_id(), account, disk_id)
            br.add_request(operator.get_entity_id(), br.now,
                           self.const.bofh_move_request,
                           account.entity_id, disk_id, why)
            return "OK, request registered"
        elif move_type in ("give",):
            self.ba.can_give_user(operator.get_entity_id(), account)
            group = args[0]
            why = args[1]
            group = self._get_group(group)
            _check_reason(why)
            br.add_request(operator.get_entity_id(), br.now,
                           self.const.bofh_move_give,
                           account.entity_id, group.entity_id, why)
            return "OK, 'give' registered"

    #
    # user password
    #
    all_commands['user_password'] = Command(
        ('user', 'password'),
        AccountName(),
        AccountPassword(optional=True))

    def user_password(self, operator, accountname, password=None):
        account = self._get_account(accountname)
        self.ba.can_set_password(operator.get_entity_id(), account)
        if password is None:
            password = account.make_passwd(accountname)
        else:
            # this is a bit complicated, but the point is that
            # superusers are allowed to *specify* passwords for other
            # users if cereconf.BOFHD_SU_CAN_SPECIFY_PASSWORDS=True
            # otherwise superusers may change passwords by assigning
            # automatic passwords only.
            if self.ba.is_superuser(operator.get_entity_id()):
                if (operator.get_entity_id() != account.entity_id and
                        not cereconf.BOFHD_SU_CAN_SPECIFY_PASSWORDS):
                    raise CerebrumError("Superuser cannot specify passwords "
                                        "for other users")
            elif operator.get_entity_id() != account.entity_id:
                raise CerebrumError(
                    "Cannot specify password for another user.")
        try:
            check_password(password, account, structured=False)
        except RigidPasswordNotGoodEnough as e:
            raise CerebrumError('Bad password: {err_msg}'.format(
                err_msg=str(e).decode('utf-8').encode('latin-1')))
        except PhrasePasswordNotGoodEnough as e:
            raise CerebrumError('Bad passphrase: {err_msg}'.format(
                err_msg=str(e).decode('utf-8').encode('latin-1')))
        except PasswordNotGoodEnough as e:
            raise CerebrumError('Bad password: {err_msg}'.format(err_msg=e))
        account.set_password(password)
        account.write_db()
        operator.store_state("user_passwd",
                             {'account_id': int(account.entity_id),
                              'password': password})
        # Remove "weak password" quarantine
        for r in account.get_entity_quarantine():
            if int(r['quarantine_type']) == self.const.quarantine_autopassord:
                account.delete_entity_quarantine(
                    self.const.quarantine_autopassord)

            if int(r['quarantine_type']) == self.const.quarantine_svakt_passord:
                account.delete_entity_quarantine(
                    self.const.quarantine_svakt_passord)

        if account.is_deleted():
            return "OK.  Warning: user is deleted"
        elif account.is_expired():
            return "OK.  Warning: user is expired"
        elif account.get_entity_quarantine(only_active=True):
            return "OK.  Warning: user has an active quarantine"
        return ("Password altered. Please use misc list_passwords to view the "
                "new password, or misc print_passwords to print password "
                "letters.")

    # user promote_posix
    all_commands['user_promote_posix'] = Command(
        ('user', 'promote_posix'), AccountName(),
        PosixShell(default="bash"), DiskId(),
        perm_filter='can_create_user')
    def user_promote_posix(self, operator, accountname, shell=None, home=None):
        is_posix = False
        try:
            self._get_account(accountname, actype="PosixUser")
            is_posix = True
        except CerebrumError:
            pass
        if is_posix:
            raise CerebrumError("%s is already a PosixUser" % accountname)
        account = self._get_account(accountname)
        pu = Utils.Factory.get('PosixUser')(self.db)
        old_uid = self._lookup_old_uid(account.entity_id)
        if old_uid is None:
            uid = pu.get_free_uid()
        else:
            uid = old_uid
        shell = self._get_shell(shell)
        if not home:
            raise CerebrumError("home cannot be empty")
        elif home[0] != ':':  # Hardcoded path
            disk_id, home = self._get_disk(home)[1:3]
        else:
            if not self.ba.is_superuser(operator.get_entity_id()):
                raise PermissionDenied("only superusers may use hardcoded path")
            disk_id, home = None, home[1:]
        if account.owner_type == self.const.entity_person:
            person = self._get_person("entity_id", account.owner_id)
        else:
            person = None
        self.ba.can_create_user(operator.get_entity_id(), person, disk_id)

        pu.populate(uid, None, None, shell,
                    parent=account, creator_id=operator.get_entity_id())
        pu.write_db()
        default_home_spread = self._get_constant(self.const.Spread,
                                                 cereconf.DEFAULT_HOME_SPREAD,
                                                 "spread")
        if not pu.has_spread(default_home_spread):
            pu.add_spread(default_home_spread)

        homedir_id = pu.set_homedir(
            disk_id=disk_id, home=home,
            status=self.const.home_status_not_created)
        pu.set_home(default_home_spread, homedir_id)
        if old_uid is None:
            tmp = ', new uid=%i' % uid
        else:
            tmp = ', reused old uid=%i' % old_uid
        return "OK, promoted %s to posix user%s" % (accountname, tmp)

    # user posix_delete
    all_commands['user_demote_posix'] = Command(
        ('user', 'demote_posix'), AccountName(), perm_filter='can_create_user')
    def user_demote_posix(self, operator, accountname):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("currently limited to superusers")
        user = self._get_account(accountname, actype="PosixUser")
        user.delete_posixuser()
        return "OK, %s was demoted" % accountname

    def user_restore_prompt_func(self, session, *args):
        '''Helper function for user_restore. Will display a prompt that
        asks which affiliation should be used, and more..'''

        all_args = list(args[:])

        # Get the account name
        if not all_args:
            return {'prompt': 'Account name',
                    'help_ref': 'account_name'}
        arg = all_args.pop(0)
        ac = self._get_account(arg)

        # Print a list of affiliations registred on the accounts owner (person)
        # Prompts user to select one of these. Checks if the input is sane.
        if not all_args:
            person = self._get_person('entity_id', ac.owner_id)
            map = [(('%-8s %s', 'Num', 'Affiliation'), None)]
            for aff in person.get_affiliations():
                ou = self._get_ou(ou_id=aff['ou_id'])
                name = '%s@%s' % (self.const.PersonAffStatus(aff['status']),
                                  self._format_ou_name(ou))
                map.append((('%s', name), {'ou_id': int(aff['ou_id']),
                                           'aff': int(aff['affiliation'])}))
            if not len(map) > 1:
                raise CerebrumError('Person has no affiliations.')
            return {'prompt': 'Choose affiliation from list', 'map': map}
        arg = all_args.pop(0)
        if isinstance(arg, type({})) and arg.has_key('aff') and \
                arg.has_key('ou_id'):
            ou = arg['ou_id']
            aff = arg['aff']
        else:
            raise CerebrumError('Invalid affiliation')

        # Gets the disk the user will reside on
        if not all_args:
            return {'prompt': 'Disk',
                    'help_ref': 'disk',
                    'last_arg': True}
        arg = all_args.pop(0)
        disk = self._get_disk(arg)

        # Finishes off
        if len(all_args) == 0:
            return {'last_arg': True}

        # We'll raise an error, if there is too many arguments:
        raise CerebrumError('Too many arguments')

    # user restore
    all_commands['user_restore'] = Command(
            ('user', 'restore'), prompt_func=user_restore_prompt_func,
            perm_filter='can_create_user')
    def user_restore(self, operator, accountname, aff_ou, home):
        ac = self._get_account(accountname)
        # Check if the account is deleted or reserved
        if not ac.is_deleted() and not ac.is_reserved():
            raise CerebrumError, \
                  ('Please contact brukerreg in order to restore %s'
                  % accountname)

        # Checking to see if the home path is hardcoded.
        # Raises CerebrumError if the disk does not exist.
        if not home:
            raise CerebrumError('Home must be specified')
        elif home[0] != ':':  # Hardcoded path
            disk_id, home = self._get_disk(home)[1:3]
        else:
            if not self.ba.is_superuser(operator.get_entity_id()):
                raise PermissionDenied('Only superusers may use hardcoded path')
            disk_id, home = None, home[1:]

        # Check if the operator can alter the user
        if not self.ba.can_create_user(operator.get_entity_id(),
                                       ac, disk_id):
            raise PermissionDenied('User restore is limited')

        # We demote posix
        try:
            pu = self._get_account(accountname, actype='PosixUser')
        except CerebrumError:
            pu = Utils.Factory.get('PosixUser')(self.db)
        else:
            pu.delete_posixuser()
            pu = Utils.Factory.get('PosixUser')(self.db)

        # We remove all old group memberships
        grp = self.Group_class(self.db)
        for row in grp.search(member_id=ac.entity_id):
            grp.clear()
            grp.find(row['group_id'])
            grp.remove_member(ac.entity_id)
            grp.write_db()

        # We remove all (the old) affiliations on the account
        for row in ac.get_account_types(filter_expired=False):
            ac.del_account_type(row['ou_id'], row['affiliation'])

       # Automatic selection of affiliation. This could be used if the user
       # should not choose affiliations.
       # # Sort affiliations according to creation date (newest first), and
       # # try to save it for later. If there exists no affiliations, we'll
       # # raise an error, since we'll need an affiliation to copy from the
       # # person to the account.
       # try:
       #     tmp = sorted(pe.get_affiliations(),
       #                  key=lambda i: i['create_date'], reverse=True)[0]
       #     ou, aff = tmp['ou_id'], tmp['affiliation']
       # except IndexError:
       #     raise CerebrumError('Person must have an affiliation')

        # We set the affiliation selected by the operator.
        self._user_create_set_account_type(ac, ac.owner_id, aff_ou['ou_id'], \
                                           aff_ou['aff'])

        # And promote posix
        old_uid = self._lookup_old_uid(ac.entity_id)
        if old_uid is None:
            uid = pu.get_free_uid()
        else:
            uid = old_uid

        shell = self.const.posix_shell_bash

        # Populate the posix user, and write it to the database
        pu.populate(uid, None, None, shell, parent=ac,
                    creator_id=operator.get_entity_id())
        try:
            pu.write_db()
        except self.db.IntegrityError, e:
            self.logger.debug("IntegrityError: %s" % e)
            self.db.rollback()
            raise CerebrumError('Please contact brukerreg in order to restore')

        # Unset the expire date
        ac.expire_date = None

        # Add them spreads
        for s in cereconf.BOFHD_NEW_USER_SPREADS:
            if not ac.has_spread(self.const.Spread(s)):
                ac.add_spread(self.const.Spread(s))

        # And remove them quarantines (except those defined in cereconf)
        for q in ac.get_entity_quarantine():
            if str(self.const.Quarantine(q['quarantine_type'])) not in \
               cereconf.BOFHD_RESTORE_USER_SAVE_QUARANTINES:
                ac.delete_entity_quarantine(q['quarantine_type'])

        # We set the new homedir
        default_home_spread = self._get_constant(self.const.Spread,
                                                 cereconf.DEFAULT_HOME_SPREAD,
                                                 'spread')

        homedir_id = pu.set_homedir(
            disk_id=disk_id, home=home,
            status=self.const.home_status_not_created)
        pu.set_home(default_home_spread, homedir_id)

        # We'll set a new password and store it for printing
        passwd = ac.make_passwd(ac.account_name)
        ac.set_password(passwd)

        operator.store_state('new_account_passwd',
                             {'account_id': int(ac.entity_id),
                              'password': passwd})

        # We'll need to write to the db, in order to store stuff.
        try:
            ac.write_db()
        except self.db.IntegrityError, e:
            self.logger.debug("IntegrityError (ac.write_db): %s" % e)
            self.db.rollback()
            raise CerebrumError('Please contact brukerreg in order to restore')

        # Return string with some info
        if ac.get_entity_quarantine():
            note  = '\nNotice: Account is quarantined!'
        else:
            note = ''

        if old_uid is None:
            tmp = ', new uid=%i' % uid
        else:
            tmp = ', reused old uid=%i' % old_uid

        return '''OK, promoted %s to posix user%s.
Password altered. Use misc list_password to print or view the new password.%s'''\
        % (accountname, tmp, note)

    # user set_disk_status
    all_commands['user_set_disk_status'] = Command(
        ('user', 'set_disk_status'), AccountName(),
        SimpleString(help_ref='string_disk_status'),
        perm_filter='can_create_disk')
    def user_set_disk_status(self, operator, accountname, status):
        try:
            status = self.const.AccountHomeStatus(status)
            int(status)
        except Errors.NotFoundError:
            raise CerebrumError, "Unknown status"
        account = self._get_account(accountname)
        # this is not exactly right, we should probably
        # implement a can_set_disk_status-function, but no
        # appropriate criteria is readily available for this
        # right now
        self.ba.can_create_disk(operator.get_entity_id(),query_run_any=True)
        ah = account.get_home(self.const.spread_uio_nis_user)
        account.set_homedir(current_id=ah['homedir_id'], status=status)
        return "OK, set home-status for %s to %s" % (accountname, status)

    # user set_expire
    all_commands['user_set_expire'] = Command(
        ('user', 'set_expire'), AccountName(), Date(),
        perm_filter='can_delete_user')
    def user_set_expire(self, operator, accountname, date):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        account = self._get_account(accountname)
        # self.ba.can_delete_user(operator.get_entity_id(), account)
        account.expire_date = self._parse_date(date)
        account.write_db()
        return "OK, set expire-date for %s to %s" % (accountname, date)

    # user set_np_type
    all_commands['user_set_np_type'] = Command(
        ('user', 'set_np_type'), AccountName(), SimpleString(help_ref="string_np_type"),
        perm_filter='can_delete_user')
    def user_set_np_type(self, operator, accountname, np_type):
        account = self._get_account(accountname)
        self.ba.can_delete_user(operator.get_entity_id(), account)
        account.np_type = self._get_constant(self.const.Account, np_type,
                                             "account type")
        account.write_db()
        return "OK, set np-type for %s to %s" % (accountname, np_type)

    def user_set_owner_prompt_func(self, session, *args):
        all_args = list(args[:])
        if not all_args:
            return {'prompt': 'Account name'}
        account_name = all_args.pop(0)
        if not all_args:
            return {'prompt': 'Entity type (group/person)',
                    'default': 'person'}
        entity_type = all_args.pop(0)
        if not all_args:
            return {'prompt': 'Id of the type specified above'}
        id = all_args.pop(0)
        if entity_type == 'person':
            if not all_args:
                person = self._get_person(*self._map_person_id(id))
                map = [(("%-8s %s", "Num", "Affiliation"), None)]
                for aff in person.get_affiliations():
                    ou = self._get_ou(ou_id=aff['ou_id'])
                    name = "%s@%s" % (
                        self.const.PersonAffStatus(aff['status']),
                        self._format_ou_name(ou))
                    map.append((("%s", name),
                                {'ou_id': int(aff['ou_id']), 'aff': int(aff['affiliation'])}))
                if not len(map) > 1:
                    raise CerebrumError(
                        "Person has no affiliations.")
                return {'prompt': "Choose affiliation from list", 'map': map,
                        'last_arg': True}
        else:
            if not all_args:
                return {'prompt': "Enter np_type",
                        'help_ref': 'string_np_type',
                        'last_arg': True}
            np_type = all_args.pop(0)
        raise CerebrumError, "Client called prompt func with too many arguments"

    all_commands['user_set_owner'] = Command(
        ("user", "set_owner"), prompt_func=user_set_owner_prompt_func,
        perm_filter='is_superuser')
    def user_set_owner(self, operator, *args):
        if args[1] == 'person':
            accountname, entity_type, id, affiliation = args
            new_owner = self._get_person(*self._map_person_id(id))
        else:
            accountname, entity_type, id, np_type = args
            new_owner = self._get_entity(entity_type, id)
            np_type = self._get_constant(self.const.Account, np_type,
                                         "account type")

        account = self._get_account(accountname)
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("only superusers may assign account ownership")
        new_owner = self._get_entity(entity_type, id)
        if account.owner_type == self.const.entity_person:
            for row in account.get_account_types(filter_expired=False):
                account.del_account_type(row['ou_id'], row['affiliation'])
        account.owner_type = new_owner.entity_type
        account.owner_id = new_owner.entity_id
        if args[1] == 'group':
            account.np_type = np_type
        account.write_db()
        if new_owner.entity_type == self.const.entity_person:
            ou_id, affiliation = affiliation['ou_id'], affiliation['aff']
            self._user_create_set_account_type(account, account.owner_id,
                                               ou_id, affiliation)
        return "OK, set owner of %s to %s" % (
            accountname,  self._get_name_from_object(new_owner))

    # user shell
    all_commands['user_shell'] = Command(
        ("user", "shell"), AccountName(), PosixShell(default="bash"))
    def user_shell(self, operator, accountname, shell=None):
        account = self._get_account(accountname, actype="PosixUser")
        shell = self._get_shell(shell)
        self.ba.can_set_shell(operator.get_entity_id(), account, shell)
        account.shell = shell
        account.write_db()
        return "OK, set shell for %s to %s" % (accountname, shell)

    #
    # commands that are noe available in jbofh, but used by other clients
    #

    all_commands['get_persdata'] = None

    def get_persdata(self, operator, uname):
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        ac = self._get_account(uname)
        person_id = "entity_id:%i" % ac.owner_id
        person = self._get_person(*self._map_person_id(person_id))
        ret = {
            'is_personal': len(ac.get_account_types()),
            'fnr': [{'id': r['external_id'],
                     'source':
                     str(self.const.AuthoritativeSystem(r['source_system']))}
                     for r in person.get_external_id(id_type=self.const.externalid_fodselsnr)]
            }
        ac_types = ac.get_account_types(all_persons_types=True)
        if ret['is_personal']:
            ac_types.sort(lambda x,y: int(x['priority']-y['priority']))
            for at in ac_types:
                ac2 = self._get_account(at['account_id'], idtype='id')
                ret.setdefault('users', []).append(
                    (ac2.account_name, '%s@ulrik.uio.no' % ac2.account_name,
                     at['priority'], at['ou_id'],
                     str(self.const.PersonAffiliation(at['affiliation']))))
            # TODO: kall ac.list_accounts_by_owner_id(ac.owner_id) for
            # å hente ikke-personlige konti?
        ret['home'] = ac.resolve_homedir(disk_id=ac.disk_id, home=ac.home)
        ret['navn'] = {'cached': person.get_name(
            self.const.system_cached, self.const.name_full)}
        for key, variant in (("work_title", self.const.work_title),
                             ("personal_title", self.const.personal_title)):
            try:
                ret[key] = person.get_name_with_language(
                                      name_variant=variant,
                                      name_language=self.const.language_nb)
            except (Errors.NotFoundError, Errors.TooManyRowsError):
                pass
        return ret

    #
    # misc helper functions.
    # TODO: These should be protected so that they are not remotely callable
    #

    def _get_account(self, id, idtype=None, actype="Account"):
        if actype == 'Account':
            account = self.Account_class(self.db)
        elif actype == 'PosixUser':
            account = Utils.Factory.get('PosixUser')(self.db)
        account.clear()
        try:
            if idtype is None:
                if id.find(":") != -1:
                    idtype, id = id.split(":", 1)
                    if len(id) == 0:
                        raise CerebrumError, "Must specify id"
                else:
                    idtype = 'name'
            if idtype == 'name':
                account.find_by_name(id, self.const.account_namespace)
            elif idtype == 'id':
                if isinstance(id, str) and not id.isdigit():
                    raise CerebrumError, "Entity id must be a number"
                account.find(id)
            elif idtype == 'uid':
                if isinstance(id, str) and not id.isdigit():
                    raise CerebrumError, 'uid must be a number'
                if actype != 'PosixUser':
                    account = Utils.Factory.get('PosixUser')(self.db)
                    account.clear()
                account.find_by_uid(id)
            else:
                raise CerebrumError, "unknown idtype: '%s'" % idtype
        except Errors.NotFoundError:
            raise CerebrumError, "Could not find %s with %s=%s" % (actype, idtype, id)
        return account

    def _get_email_domain(self, name):
        ed = Email.EmailDomain(self.db)
        try:
            ed.find_by_domain(name)
        except Errors.NotFoundError:
            raise CerebrumError, "Unknown e-mail domain (%s)" % name
        return ed

    def _get_email_server(self, name):
        es = Email.EmailServer(self.db)
        try:
            if isinstance(name, (int, long)):
                es.find(name)
            else:
                es.find_by_name(name)
            return es
        except Errors.NotFoundError:
            raise CerebrumError, "Unknown mail server: %s" % name

    def _get_host(self, name):
        host = Utils.Factory.get('Host')(self.db)
        try:
            if isinstance(name, (int, long)):
                host.find(name)
            else:
                host.find_by_name(name)
            return host
        except Errors.NotFoundError:
            raise CerebrumError, "Unknown host: %s" % name

    def _get_shell(self, shell):
        return self._get_constant(self.const.PosixShell, shell, "shell")

    def _get_opset(self, opset):
        aos = BofhdAuthOpSet(self.db)
        try:
            aos.find_by_name(opset)
        except Errors.NotFoundError:
            raise CerebrumError, "Could not find op set with name %s" % opset
        return aos

    def _get_group_opcode(self, operator):
        if operator is None:
            return self.const.group_memberop_union
        if operator == 'union':
            return self.const.group_memberop_union
        if operator == 'intersection':
            return self.const.group_memberop_intersection
        if operator == 'difference':
            return self.const.group_memberop_difference
        raise CerebrumError("unknown group opcode: '%s'" % operator)

    def _get_entity(self, idtype=None, ident=None):
        if ident is None:
            raise CerebrumError("Invalid id")
        if idtype == 'account':
            return self._get_account(ident)
        if idtype == 'person':
            return self._get_person(*self._map_person_id(ident))
        if idtype == 'group':
            return self._get_group(ident)
        if idtype == 'stedkode':
            return self._get_ou(stedkode=ident)
        if idtype == 'host':
            return self._get_host(ident)
        if idtype is None:
            try:
                int(ident)
            except ValueError:
                raise CerebrumError("Expected int as id")
            ety = Entity.Entity(self.db)
            return ety.get_subclassed_object(ident)
        raise CerebrumError("Invalid idtype")

    def _get_disk(self, path, host_id=None, raise_not_found=True):
        disk = Utils.Factory.get('Disk')(self.db)
        try:
            if isinstance(path, str):
                disk.find_by_path(path, host_id)
            else:
                disk.find(path)
            return disk, disk.entity_id, None
        except Errors.NotFoundError:
            if raise_not_found:
                raise CerebrumError("Unknown disk: %s" % path)
            return disk, None, path

    def _is_yes(self, val):
        if isinstance(val, str) and val.lower() in ('y', 'yes', 'ja', 'j'):
            return True
        return False

    # The next two functions require all affiliations to be in upper case,
    # and all affiliation statuses to be in lower case.  If this changes,
    # the user will have to type exact case.
    def _get_affiliationid(self, code_str):
        try:
            c = self.const.PersonAffiliation(code_str.upper())
            # force a database lookup to see if it's a valid code
            int(c)
            return c
        except Errors.NotFoundError:
            raise CerebrumError("Unknown affiliation")

    def _get_affiliation_statusid(self, affiliation, code_str):
        try:
            c = self.const.PersonAffStatus(affiliation, code_str.lower())
            int(c)
            return c
        except Errors.NotFoundError:
            raise CerebrumError("Unknown affiliation status")


    hidden_commands['get_constant_description'] = Command(
        ("misc", "get_constant_description"),
        SimpleString(),   # constant class
        SimpleString(optional=True),
        fs=FormatSuggestion("%-15s %s",
                            ("code_str", "description")))
    def get_constant_description(self, operator, code_cls, code_str=None):
        """Fetch constant descriptions.

        There are no permissions checks for this method -- it can be called by
        anyone without any restrictions.

        @type code_cls: basestring
        @param code_cls:
          Class (name) for the constants to fetch.

        @type code_str: basestring or None
        @param code_str:
          code_str for the specific constant to fetch. If None is specified,
          *all* constants of the given type are retrieved.

        @rtype: dict or a sequence of dicts
        @return:
          Description of the specified constants. Each dict has 'code' and
          'description' keys.
        """

        if not hasattr(self.const, code_cls):
            raise CerebrumError("%s is not a constant type" % code_cls)

        kls = getattr(self.const, code_cls)
        if not issubclass(kls, self.const.CerebrumCode):
            raise CerebrumError("%s is not a valid constant class" % code_cls)

        if code_str is not None:
            c = self._get_constant(kls, code_str)
            return {"code": int(c),
                    "code_str": str(c),
                    "description": c.description}

        # Fetch all of the constants of the specified type
        return [{"code": int(x),
                 "code_str": str(x),
                 "description": x.description}
                for x in self.const.fetch_constants(kls)]
    # end get_constant_description


    def _parse_date_from_to(self, date):
        date_start = self._today()
        date_end = None
        if date:
            tmp = date.split("--")
            if len(tmp) == 2:
                if tmp[0]: # string could start with '--'
                    date_start = self._parse_date(tmp[0])
                date_end = self._parse_date(tmp[1])
            elif len(tmp) == 1:
                date_end = self._parse_date(date)
            else:
                raise CerebrumError, "Incorrect date specification: %s." % date
        return (date_start, date_end)

    def _parse_date(self, date):
        """Convert a written date into DateTime object.  Possible
        syntaxes are:

            YYYY-MM-DD       (2005-04-03)
            YYYY-MM-DDTHH:MM (2005-04-03T02:01)
            THH:MM           (T02:01)

        Time of day defaults to midnight.  If date is unspecified, the
        resulting time is between now and 24 hour into future.

        """
        if not date:
            # TBD: Is this correct behaviour?  mx.DateTime.DateTime
            # objects allow comparison to None, although that is
            # hardly what we expect/want.
            return None
        if isinstance(date, DateTime.DateTimeType):
            # Why not just return date?  Answer: We do some sanity
            # checks below.
            date = date.Format("%Y-%m-%dT%H:%M")
        if date.count('T') == 1:
            date, time = date.split('T')
            try:
                hour, min = [int(x) for x in time.split(':')]
            except ValueError:
                raise CerebrumError, "Time of day must be on format HH:MM"
            if date == '':
                now = DateTime.now()
                target = DateTime.Date(now.year, now.month, now.day, hour, min)
                if target < now:
                    target += DateTime.DateTimeDelta(1)
                date = target.Format("%Y-%m-%d")
        else:
            hour = min = 0
        try:
            y, m, d = [int(x) for x in date.split('-')]
        except ValueError:
            raise CerebrumError, "Dates must be on format YYYY-MM-DD"
        # TODO: this should be a proper delta, but rather than using
        # pgSQL specific code, wait until Python has standardised on a
        # Date-type.
        if y > 2050:
            raise CerebrumError, "Too far into the future: %s" % date
        if y < 1800:
            raise CerebrumError, "Too long ago: %s" % date
        try:
            return DateTime.Date(y, m, d, hour, min)
        except:
            raise CerebrumError, "Illegal date: %s" % date

    def _today(self):
        return self._parse_date("%d-%d-%d" % time.localtime()[:3])

    def _format_from_cl(self, format, val):
        def _get_code(get, code, fallback=None):
            def f(get, code, fallback):
                try:
                    return (1, str(get(code)))
                except Errors.NotFoundError:
                    if fallback:
                        return (2, fallback)
                    else:
                        return (2, str(code))
            if not isinstance(get, (tuple, list)):
                get = [get]
            return str(sorted([f(c, code, fallback) for c in get])[0][1])

        if val is None:
            return ''

        if format == 'affiliation':
            return _get_code(self.const.PersonAffiliation, val)
        elif format == 'disk':
            disk = Utils.Factory.get('Disk')(self.db)
            try:
                disk.find(val)
                return disk.path
            except Errors.NotFoundError:
                return "deleted_disk:%s" % val
        elif format == 'date':
            return val.date
        elif format == 'timestamp':
            return str(val)
        elif format == 'entity':
            return self._get_entity_name(int(val))
        elif format == 'extid':
            return _get_code(self.const.EntityExternalId, val)
        elif format == 'homedir':
            return 'homedir_id:%s' % val
        elif format == 'id_type':
            return _get_code(self.const.ChangeType, val)
        elif format == 'home_status':
            return _get_code(self.const.AccountHomeStatus, val)
        elif format == 'int':
            return str(val)
        elif format == 'name_variant':
            # Name variants are stored in two separate code-tables; if
            # one doesn't work, try the other
            return _get_code((self.const.PersonName, self.const.EntityNameCode), val)
        elif format == 'ou':
            ou = self._get_ou(ou_id=val)
            return self._format_ou_name(ou)
        elif format == 'quarantine_type':
            return _get_code(self.const.Quarantine, val)
        elif format == 'source_system':
            return _get_code(self.const.AuthoritativeSystem, val)
        elif format == 'spread_code':
            return _get_code(self.const.Spread, val)
        elif format == 'string':
            return str(val)
        elif format == 'trait':
            # Trait has been deleted from the DB, so we can't know which it
            # was. Therefore we return '<unknown>'
            return _get_code(self.const.EntityTrait, val, '<unknown>')
        elif format == 'value_domain':
            return _get_code(self.const.ValueDomain, val)
        elif format == 'rolle_type':
            return _get_code(self.const.EphorteRole, val)
        elif format == 'perm_type':
            return _get_code(self.const.EphortePermission, val)
        elif format == 'bool':
            if val == 'T':
                return str(True)
            elif val == 'F':
                return str(False)
            else:
                return str(bool(val))
        else:
            self.logger.warn("bad cl format: %s", repr((format, val)))
            return ''

    def _format_changelog_entry(self, row):
        dest = row['dest_entity']
        if dest is not None:
            try:
                dest = self._get_entity_name(dest)
            except Errors.NotFoundError:
                dest = repr(dest)

        this_cl_const = self.const.ChangeType(row['change_type_id'])
        if this_cl_const.msg_string is None:
            self.logger.warn('Formatting of change log entry of type %s failed, '
                             'no description defined in change type',
                             str(this_cl_const))
            msg = '{}, subject {}, destination {}'.format(
                str(this_cl_const),
                self._get_entity_name(row['subject_entity']),
                dest)
        else:
            msg = this_cl_const.msg_string % {
                'subject': self._get_entity_name(row['subject_entity']),
                'dest': dest}

        # Append information from change_params to the string.  See
        # _ChangeTypeCode.__doc__
        if row['change_params']:
            try:
                params = pickle.loads(row['change_params'])
            except TypeError:
                self.logger.error("Bogus change_param in change_id=%s, row: %s",
                                  row['change_id'], row)
                raise
        else:
            params = {}

        if this_cl_const.format:
            for f in this_cl_const.format:
                repl = {}
                for part in re.findall(r'%\([^\)]+\)s', f):
                    fmt_type, key = part[2:-2].split(':')
                    try:
                        repl['%%(%s:%s)s' % (fmt_type, key)] = self._format_from_cl(
                            fmt_type, params.get(key, None))
                    except Exception:
                        self.logger.warn("Failed applying %s to %s for change-id: %d" % (
                            part, repr(params.get(key)), row['change_id']))
                if [x for x in repl.values() if x]:
                    for k, v in repl.items():
                        f = f.replace(k, v)
                    msg += ", " + f
        by = row['change_program'] or self._get_entity_name(row['change_by'])
        return {'timestamp': row['tstamp'],
                'change_by': by,
                'message': msg}

    def _convert_ticks_to_timestamp(self, ticks):
        if ticks is None:
            return None
        return DateTime.DateTimeFromTicks(ticks)

    def _lookup_old_uid(self, account_id):
        uid = None
        for r in self.db.get_log_events(
            0, subject_entity=account_id, types=[self.const.posix_demote]):
            uid = pickle.loads(r['change_params'])['uid']
        return uid

    def _date_human_readable(self, date):
        "Convert date to something human-readable."

        if hasattr(date, "strftime"):
            return date.strftime("%Y-%m-%dT%H:%M:%S")

        return str(date)
