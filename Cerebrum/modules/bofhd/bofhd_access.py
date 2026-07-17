# -*- coding: utf-8 -*-
#
# Copyright 2014-2024 University of Oslo, Norway
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
"""
This module contains the access command group and commands for bofhd.

.. important::
   These classes should not be used directly.  Always make subclasses of
   BofhdCommandBase classes, and add a proper auth class/mixin to the class
   authz.

The `access` commands can be used to inspect and modify permissions in bofhd.
These commands are closely related to the :mod:`.bofhd_perm_cmds` command
module.  These two modules should be reviewed and probably merged to one
unified command group.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import collections
import logging
import re
import six

import cereconf

from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum.modules import Email
from Cerebrum.modules.bofhd.auth import (
    BofhdAuth,
    BofhdAuthOpSet,
    BofhdAuthOpTarget,
    BofhdAuthRole,
)
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.cmd_param import (
    AccountName,
    Command,
    DiskId,
    EntityType,
    FormatSuggestion,
    GroupName,
    OpSet,
    OU,
    SimpleString,
    get_format_suggestion_table,
)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings

logger = logging.getLogger(__name__)


class BofhdAccessAuth(BofhdAuth):
    """Auth for access * commands"""

    def can_grant_access(self, operator, operation=None, target_type=None,
                         target_id=None, opset=None, query_run_any=False):
        """
        Check if operator can grant a role/opset to an entity.

        If :mod:`.bofhd_perm_cmds` are in use, then `perm grant` (and
        `can_add_auth_role` will allow for this as well.
        """
        if self.is_superuser(operator):
            return True

        if query_run_any:
            for op in (self.const.auth_grant_disk,
                       self.const.auth_grant_group,
                       self.const.auth_grant_host,
                       self.const.auth_grant_maildomain,
                       self.const.auth_grant_ou):
                if self._has_operation_perm_somewhere(operator, op):
                    return True
            return False

        if operation is None:
            # operation is typically empty for global targets
            raise PermissionDenied("Currently limited to superusers")

        op_attr = None if opset is None else opset.name
        if self._has_target_permissions(
                operator=operator,
                operation=operation,
                target_type=target_type,
                target_id=target_id,
                victim_id=None,
                operation_attr=op_attr):
            return True

        if op_attr:
            raise PermissionDenied("No access to %s on %s"
                                   % (op_attr, target_type))

        raise PermissionDenied("No access to %s" % (target_type,))

    def can_list_account_access(self, operator,
                                account_id=None, query_run_any=False):
        """
        Access control for access_list_alterable
        """
        if query_run_any:
            return True

        if self.is_superuser(operator):
            return True

        if operator == account_id:
            return True

        raise PermissionDenied(
            "You do not have permission for this operation")


class BofhdAccessCommands(BofhdCommonMethods):
    """Bofhd extension with access commands"""

    all_commands = {}
    hidden_commands = {}
    authz = BofhdAccessAuth

    @classmethod
    def get_help_strings(cls):
        return merge_help_strings(
            super(BofhdAccessCommands, cls).get_help_strings(),
            (HELP_ACCESS_GROUP, HELP_ACCESS_CMDS, HELP_ACCESS_ARGS),
        )

    # Format suggestion for results directly from `_access_list` helper
    _access_list_fs = get_format_suggestion_table(
        ("opset", "Operation set", 16, "s", True),
        ("type", "Type", 10, "s", True),
        ("name", "Name", 30, "s", True),
    )

    #
    # access disk <path>
    #
    all_commands['access_disk'] = Command(
        ('access', 'disk'),
        DiskId(),
        fs=_access_list_fs,
    )

    def access_disk(self, operator, path):
        disk = self._get_disk(path)[0]
        result = []

        # check for access to all disks on disk-host
        host = Utils.Factory.get('Host')(self.db)
        try:
            host.find(disk.host_id)
        except Errors.NotFoundError:
            pass
        else:
            for r in self._list_access("host", host.name):
                if r['attr'] == '' or re.search("/%s$" % r['attr'], path):
                    result.append(r)

        # check for specific access to disk
        result.extend(self._list_access("disk", path))
        if not result:
            raise CerebrumError("No access granted to disk: " + repr(path))
        return result

    #
    # access group <group>
    #
    all_commands['access_group'] = Command(
        ('access', 'group'),
        GroupName(help_ref='group_name_id'),
        fs=_access_list_fs,
    )

    def access_group(self, operator, group):
        results = self._list_access("group", group)
        if not results:
            raise CerebrumError("No access granted to group: " + repr(group))
        return results

    #
    # access host <hostname>
    #
    all_commands['access_host'] = Command(
        ('access', 'host'),
        SimpleString(help_ref="string_host"),
        fs=get_format_suggestion_table(
            # TODO: this is _access_list_fs with an extra attr column
            #       maybe just include attr in _access_list_fs ?
            ("opset", "Operation set", 16, "s", True),
            ("attr", "Pattern", 16, "s", True),
            ("type", "Type", 10, "s", True),
            ("name", "Name", 30, "s", True),
        ),
    )

    def access_host(self, operator, host):
        results = self._list_access("host", host)
        if not results:
            raise CerebrumError("No access granted to host: " + repr(host))
        return results

    #
    # access maildom <maildom>
    #
    all_commands['access_maildom'] = Command(
        ('access', 'maildom'),
        SimpleString(help_ref="email_domain"),
        fs=_access_list_fs,
    )

    def access_maildom(self, operator, maildom):
        results = self._list_access("maildom", maildom)
        if not results:
            raise CerebrumError("No access granted to email domain: "
                                + repr(maildom))
        return results

    #
    # access ou <ou>
    #
    all_commands['access_ou'] = Command(
        ('access', 'ou'),
        OU(),
        fs=get_format_suggestion_table(
            # TODO: this is _access_list_fs with an extra attr column
            #       maybe just include attr in _access_list_fs ?
            ("opset", "Operation set", 16, "s", True),
            ("attr", "Affiliation", 16, "s", True),
            ("type", "Type", 10, "s", True),
            ("name", "Name", 30, "s", True),
        ),
    )

    def access_ou(self, operator, ou):
        results = self._list_access("ou", ou)
        if not results:
            raise CerebrumError("No access granted to org unit: " + repr(ou))
        return results

    #
    # access user <account>
    #
    all_commands['access_user'] = Command(
        ('access', 'user'),
        AccountName(),
        fs=get_format_suggestion_table(
            ("opset", "Operation set", 14, "s", True),
            ("target_type", "TType", 5, "s", True),
            ("target", "Target", 20, "s", True),
            ("attr", "Attr", 7, "s", True),
            ("name", "Name", 20, "s", True),
        ),
    )

    def access_user(self, operator, user):
        # This is more tricky than the others, we want to show anyone with
        # access, through OU, host or disk.  (not global_XXX, though.)
        #
        # Note that there is no auth-type 'account', so you can't be granted
        # direct access to a specific user.

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
            for entry in self._list_access("disk", d):
                entry['target_type'] = "disk"
                entry['target'] = disks[d]
                ret.append(entry)
        # Look through hosts:
        for h in hosts.keys():
            for candidate in self._list_access("host", h):
                candidate['target_type'] = "host"
                candidate['target'] = self._get_host(h).name
                if candidate['attr'] == "":
                    ret.append(candidate)
                    continue
                for path in hosts[h]:
                    if re.match(candidate['attr'], path):
                        ret.append(candidate)
                        break
        # TODO: check user's ou(s)
        ret.sort(key=lambda r: (r['opset'].lower(), r['name']))
        if not ret:
            raise CerebrumError("No access granted to user: " + repr(user))
        return ret

    #
    # access global_group
    #
    all_commands['access_global_group'] = Command(
        ('access', 'global_group'),
        fs=_access_list_fs,
    )

    def access_global_group(self, operator):
        results = self._list_access("global_group")
        if not results:
            raise CerebrumError("No access granted to global group")
        return results

    #
    # access global_host
    #
    all_commands['access_global_host'] = Command(
        ('access', 'global_host'),
        fs=_access_list_fs,
    )

    def access_global_host(self, operator):
        results = self._list_access("global_host")
        if not results:
            raise CerebrumError("No access granted to global host")
        return results

    #
    # access global_maildom
    #
    all_commands['access_global_maildom'] = Command(
        ('access', 'global_maildom'),
        fs=_access_list_fs,
    )

    def access_global_maildom(self, operator):
        results = self._list_access("global_maildom")
        if not results:
            raise CerebrumError("No access granted to global email domain")
        return results

    #
    # access global_ou
    #
    all_commands['access_global_ou'] = Command(
        ('access', 'global_ou'),
        fs=_access_list_fs,
    )

    def access_global_ou(self, operator):
        results = self._list_access("global_ou")
        if not results:
            raise CerebrumError("No access granted to global org unit")
        return results

    # TODO: Define all_commands['access_global_person'] ?
    def access_global_person(self, operator):
        results = self._list_access("global_person")
        if not results:
            raise CerebrumError("No access granted to global person")
        return results

    #
    # access grant <opset name> <who> <type> <on what> [<attr>]
    #
    all_commands['access_grant'] = Command(
        ('access', 'grant'),
        OpSet(),
        GroupName(help_ref="id:target:group"),
        EntityType(default='group', help_ref="auth_entity_type"),
        SimpleString(optional=True, help_ref="auth_target_entity"),
        SimpleString(optional=True, help_ref="auth_attribute"),
        perm_filter='can_grant_access',
    )

    def access_grant(self, operator, opset, group, entity_type,
                     target_name=None, attr=None):
        return self._manipulate_access(self._grant_auth, operator, opset,
                                       group, entity_type, target_name, attr)

    #
    # access revoke <opset name> <who> <type> <on what> [<attr>]
    #
    all_commands['access_revoke'] = Command(
        ('access', 'revoke'),
        OpSet(),
        GroupName(help_ref="id:target:group"),
        EntityType(default='group', help_ref="auth_entity_type"),
        SimpleString(optional=True, help_ref="auth_target_entity"),
        SimpleString(optional=True, help_ref="auth_attribute"),
        perm_filter='can_grant_access',
    )

    def access_revoke(self, operator, opset, group, entity_type,
                      target_name=None, attr=None):
        return self._manipulate_access(self._revoke_auth, operator, opset,
                                       group, entity_type, target_name, attr)

    #
    # access list_opsets
    #
    all_commands['access_list_opsets'] = Command(
        ('access', 'list_opsets'),
        fs=FormatSuggestion(
            "%s", ("opset",),
            hdr="Operation set",
        ),
    )

    def access_list_opsets(self, operator):
        baos = BofhdAuthOpSet(self.db)
        ret = []
        for r in baos.list():
            ret.append({'opset': r['name']})
        ret.sort(key=lambda r: r['opset'].lower())
        return ret

    #
    # access list_alterable [group] [username]
    #
    # Note: This command is used from Brukerinfo
    #
    hidden_commands['access_list_alterable'] = Command(
        ('access', 'list_alterable'),
        SimpleString(optional=True),
        AccountName(optional=True),
        fs=FormatSuggestion(
            "%s %s", ("entity_name", "description")
        ),
        perm_filter='can_list_account_access',
    )

    def access_list_alterable(self, operator, target_type='group',
                              access_holder=None):
        """List entities that access_holder can moderate."""

        if access_holder is None:
            account_id = operator.get_entity_id()
        else:
            account = self._get_account(access_holder, actype="PosixUser")
            account_id = account.entity_id

        self.ba.can_list_account_access(operator.get_entity_id(),
                                        account_id=account_id)

        result = []
        matches = self.Group_class(self.db).search(
            admin_id=account_id,
            admin_by_membership=True
        )
        matches += self.Group_class(self.db).search(
            moderator_id=account_id,
            moderator_by_membership=True
        )
        if len(matches) > cereconf.BOFHD_MAX_MATCHES_ACCESS:
            raise CerebrumError("More than {:d} ({:d}) matches. Refusing to "
                                "return result".format(
                                    cereconf.BOFHD_MAX_MATCHES_ACCESS,
                                    len(matches)))
        for row in matches:
            try:
                group = self._get_group(row['group_id'])
            except Errors.NotFoundError:
                logger.warn(
                    "Non-existent entity (%s) referenced from auth_op_target",
                    row["entity_id"])
                continue
            tmp = {
                "entity_name": group.group_name,
                "description": group.description,
                "expire_date": group.expire_date,
            }
            if tmp not in result:
                result.append(tmp)
        return result

    #
    # access show_opset <opset name>
    #
    all_commands['access_show_opset'] = Command(
        ('access', 'show_opset'),
        OpSet(),
        fs=get_format_suggestion_table(
            ("op", "Operation", 16, "s", True),
            ("attr", "Attribute", 16, "s", True),
            ("desc", "Description", 30, "s", True),
        ),
    )

    def access_show_opset(self, operator, opset):
        baos = self._get_opset(opset)

        results = []
        for op_row in baos.list_operations():
            op = self.const.AuthRoleOp(op_row['op_code'])

            # we want one row per attr ...
            attrs = [op_attr['attr']
                     for op_attr in baos.list_operation_attrs(op_row['op_id'])]

            # ... or just one row if no attrs
            for a in (attrs or [""]):
                results.append({
                    'op': six.text_type(op),
                    'desc': op.description,
                    'attr': a,
                })

        results.sort(key=lambda r: (r['op'], r['attr']))
        return results

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

    #
    # access list <owner> [target_type]
    #
    all_commands['access_list'] = Command(
        ('access', 'list'),
        SimpleString(help_ref='id:target:group'),
        SimpleString(help_ref='string_perm_target_type_access', optional=True),
        fs=get_format_suggestion_table(
            ("opset", "Operation set", 14, "s", True),
            ("target_type", "Target type", 16, "s", True),
            ("target", "Target", 30, "s", True),
            ("attr", "Attr", 7, "s", True),
        ),
    )

    def access_list(self, operator, owner, target_type=None):
        """
        List everything an account or group can operate on. Only direct
        ownership is reported: the entities an account can access due to group
        memberships will not be listed. This does not include unpersonal users
        owned by groups.

        :param operator: operator in bofh session
        :param owner: str name of owner object
        :param target_type: the type of the target
        :return: List of everything an account or group can operate on
        """

        ar = BofhdAuthRole(self.db)
        aot = BofhdAuthOpTarget(self.db)
        aos = BofhdAuthOpSet(self.db)
        co = self.const
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
                elif r['target_type'] == co.auth_target_type_maildomain:
                    # FIXME: EmailDomain is not an Entity.
                    ed = Email.EmailDomain(self.db)
                    try:
                        ed.find(r['entity_id'])
                    except (Errors.NotFoundError, ValueError):
                        logger.warn("Non-existing entity (e-mail domain) "
                                    "in auth_op_target %s:%d",
                                    r['target_type'],
                                    r['entity_id'])
                        continue
                    target_name = ed.email_domain_name
                elif r['target_type'] == co.auth_target_type_ou:
                    ou = self.OU_class(self.db)
                    try:
                        ou.find(r['entity_id'])
                    except (Errors.NotFoundError, ValueError):
                        logger.warn("Non-existing entity (ou) in "
                                    "auth_op_target %s:%d",
                                    r['target_type'], r['entity_id'])
                        continue
                    target_name = "%02d%02d%02d (%s)" % (ou.fakultet,
                                                         ou.institutt,
                                                         ou.avdeling,
                                                         ou.short_name)
                else:
                    try:
                        ety = self._get_entity(ident=r['entity_id'])
                        target_name = self._get_name_from_object(ety)
                    except (Errors.NotFoundError, ValueError):
                        logger.warn("Non-existing entity in "
                                    "auth_op_target %s:%d",
                                    r['target_type'], r['entity_id'])
                        continue
                ret.append({
                    'opset': aos.name,
                    'target_type': r['target_type'],
                    'target': target_name,
                    'attr': r['attr'] or "",
                })
        ret.sort(key=lambda r: (r['target_type'], r['target']))
        return ret

    #
    # Helper methods
    #

    def _list_access(self, target_type, target_name=None):
        """ List all opsets + attrs that grants access to a given target. """
        # Look up target data with Access* class
        target_getter = _TargetTypeMap.get_helper(target_type)(self.db)
        target_id, target_type, _ = target_getter.get(target_name)

        ar = BofhdAuthRole(self.db)
        aos = BofhdAuthOpSet(self.db)

        ret = []
        for r in self._get_auth_op_target(target_id, target_type,
                                          any_attr=True):
            attr = r['attr'] or ""
            for r2 in ar.list(op_target_id=r['op_target_id']):
                aos.clear()
                aos.find(r2['op_set_id'])
                ety = self._get_entity(ident=r2['entity_id'])
                ret.append({
                    'opset': aos.name,
                    'attr': attr,
                    'type': six.text_type(self.const.EntityType(
                        ety.entity_type)),
                    'name': self._get_name_from_object(ety),
                })

        ret.sort(key=lambda r: (r['opset'], r['name']))
        return ret

    def _manipulate_access(self, change_func, operator, opset, group,
                           entity_type, target_name, attr):
        """ Grant or revoke access to a given target.  """
        opset = self._get_opset(opset)
        gr = self.util.get_target(group, default_lookup="group",
                                  restrict_to=['Account', 'Group'])

        # Look up target data with Access* class
        target_getter = _TargetTypeMap.get_helper(entity_type)(self.db)
        target_id, target_type, target_auth = target_getter.get(target_name)

        self.ba.can_grant_access(
            operator=operator.get_entity_id(),
            operation=target_auth,
            target_type=target_type,
            target_id=target_id,
            opset=opset,
        )
        validator = _TargetTypeMap.get_helper(entity_type)
        validator(self.db).validate(attr)
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
        cls = _TargetTypeMap.get_helper(target_type)
        return cls(self.db).get(target_name)

    def _revoke_auth(self, entity_id, opset, target_id, target_type, attr,
                     entity_name, target_name):
        ar = BofhdAuthRole(self.db)

        op_target_id = self._get_auth_op_target(target_id, target_type, attr)
        if op_target_id:
            rows = ar.list(entity_id, opset.op_set_id, op_target_id)
        else:
            # There isn't even an op_target, we can't have any matching roles
            rows = []
        if len(rows) == 0:
            raise CerebrumError(
                "%s doesn't have %s access to %s %s"
                % (entity_name, opset.name, six.text_type(target_type),
                   target_name))
        ar.revoke_auth(entity_id, opset.op_set_id, op_target_id)
        # See if the op_target has any references left, delete it if not.
        rows = ar.list(op_target_id=op_target_id)
        if len(rows) == 0:
            aot = BofhdAuthOpTarget(self.db)
            aot.find(op_target_id)
            aot.delete()
        return "OK, revoked %s access for %s from %s %s" % (
            opset.name, entity_name, six.text_type(target_type), target_name)

    def _grant_auth(self, entity_id, opset, target_id, target_type, attr,
                    entity_name, target_name):
        op_target_id = self._get_auth_op_target(target_id, target_type, attr,
                                                create=True)
        ar = BofhdAuthRole(self.db)
        rows = ar.list(entity_id, opset.op_set_id, op_target_id)
        if len(rows) == 0:
            ar.grant_auth(entity_id, opset.op_set_id, op_target_id)
            return "OK, granted %s access %s to %s %s" % (
                entity_name, opset.name, six.text_type(target_type),
                target_name)
        raise CerebrumError(
            "%s already has %s access to %s %s"
            % (entity_name, opset.name, six.text_type(target_type),
               target_name))


class AccessBase(object):
    """ Abstract util to look up targets, and validate new targets. """

    def __init__(self, db):
        self.db = db
        child_logger = logger.getChild(type(self).__name__)
        # TODO: Find a better way to pass the needed helper methods in here
        self.am = BofhdCommonMethods(self.db, child_logger)

    @property
    def const(self):
        return self.am.const

    def get(self, target_name):
        # Look up auth target info for a given target of this type
        # Returns a tuple with (<entity-id>, <target-type>, <grant-op-code>)
        # <target-type> *must* be given, while <entity-id> or <grant-op-code>
        # may not exist
        #
        # If no <grant-op-code> is returned, then only superusers can grant
        # access to this target-type
        #
        # If no <entity> exists for the given target-type/ident, then no
        # entity-id is returned.
        raise NotImplementedError()

    def validate(self, attr):
        # Validate an attribute for use with a given target
        # Should raise an exception if the attribute is unacceptable
        raise NotImplementedError()


class AccessDisk(AccessBase):

    def get(self, target_name):
        return (self.am._get_disk(target_name)[1],
                self.am.const.auth_target_type_disk,
                self.am.const.auth_grant_disk)

    def validate(self, attr):
        if attr is not None:
            raise CerebrumError("Can't specify attribute for disk access")


class AccessGroup(AccessBase):

    def get(self, target):
        target = self.am._get_group(target)
        return (target.entity_id, self.am.const.auth_target_type_group,
                self.am.const.auth_grant_group)

    def validate(self, attr):
        if attr is not None:
            raise CerebrumError("Can't specify attribute for group access")


class AccessHost(AccessBase):

    def get(self, target_name):
        target = self.am._get_host(target_name)
        return (target.entity_id, self.am.const.auth_target_type_host,
                self.am.const.auth_grant_host)

    def validate(self, attr):
        if attr is not None:
            if attr.count('/'):
                raise CerebrumError("The disk pattern should only contain "
                                    "the last component of the path.")
            try:
                re.compile(attr)
            except re.error as e:
                raise CerebrumError("Syntax error in regexp: {}".format(e))


class AccessGlobalGroup(AccessBase):

    def get(self, group):
        if group is not None and group != "":
            raise CerebrumError("Cannot set group for global access")
        return (None, self.am.const.auth_target_type_global_group, None)

    def validate(self, attr):
        if attr is not None:
            raise CerebrumError("Can't specify attribute for global group")


class AccessGlobalHost(AccessBase):

    def get(self, target_name):
        if target_name is not None and target_name != "":
            raise CerebrumError("You can't specify a hostname")
        return (None, self.am.const.auth_target_type_global_host, None)

    def validate(self, attr):
        if attr is not None:
            raise CerebrumError(
                "You can't specify a pattern with global_host.")


class AccessGlobalMaildom(AccessBase):

    def get(self, dom):
        if dom is not None and dom != '':
            raise CerebrumError("Cannot set domain for global access")
        return (None, self.am.const.auth_target_type_global_maildomain, None)

    def validate(self, attr):
        if attr is not None:
            raise CerebrumError("No attribute with global maildom.")


class AccessGlobalOu(AccessBase):

    def get(self, ou):
        if ou is not None and ou != '':
            raise CerebrumError("Cannot set OU for global access")
        return (None, self.am.const.auth_target_type_global_ou, None)

    def validate(self, attr):
        if not attr:
            # This is a policy decision, and should probably be
            # elsewhere.
            raise CerebrumError(
                "Must specify affiliation for global ou access")
        try:
            int(self.am.const.PersonAffiliation(attr))
        except Errors.NotFoundError:
            raise CerebrumError("Unknown affiliation: %s" % attr)


class AccessMaildom(AccessBase):

    def get(self, dom):
        ed = Email.EmailDomain(self.db)
        try:
            ed.find_by_domain(dom)
        except Errors.NotFoundError:
            raise CerebrumError("Unknown e-mail domain (%s)" % dom)
        return (ed.entity_id,
                self.am.const.auth_target_type_maildomain,
                self.am.const.auth_grant_maildomain)

    def validate(self, attr):
        if attr is not None:
            raise CerebrumError("No attribute with maildom.")


class AccessOu(AccessBase):

    def get(self, ou):
        ou = self.am._get_ou(stedkode=ou)
        return (ou.entity_id, self.am.const.auth_target_type_ou,
                self.am.const.auth_grant_ou)

    def validate(self, attr):
        if attr is not None:
            try:
                int(self.am.const.PersonAffiliation(attr))
            except Errors.NotFoundError:
                raise CerebrumError("Unknown affiliation '{}'".format(attr))


class AccessGlobalPerson(AccessBase):
    def get(self, person):
        # if person is not None and person != "":
        #     raise CerebrumError("Cannot set domain for global access")
        return None, self.am.const.auth_target_type_global_person, None

    def validate(self, attr):
        if attr:
            raise CerebrumError(
                "You can't specify a pattern with global_person.")


class _TargetTypeMap(collections.Mapping):
    """ Mapping class for AccessBase implementations. """

    operations = {
        'disk': AccessDisk,
        'group': AccessGroup,
        'global_group': AccessGlobalGroup,
        'global_person': AccessGlobalPerson,
        'host': AccessHost,
        'global_host': AccessGlobalHost,
        'maildom': AccessMaildom,
        'global_maildom': AccessGlobalMaildom,
        'ou': AccessOu,
        'global_ou': AccessGlobalOu,
    }

    def __len__(self):
        return len(self.operations)

    def __getitem__(self, item):
        return self.operations[item]

    def __iter__(self):
        return iter(self.operations)

    @classmethod
    def get_helper(cls, target_type):
        if target_type in cls.operations:
            return cls.operations[target_type]
        else:
            raise CerebrumError("Unknown target type: " + repr(target_type))


#
# Access help strings
#

HELP_ACCESS_GROUP = {
    'access': "Access (authorisation) related commands",
}

HELP_ACCESS_CMDS = {
    'access': {
        'access_grant':
            "Grant authorisation to perform the operations in opset "
            "<set> on <entity> of type <type> to the members of group <group>."
            "  The meaning of <attr> depends on <type>.",
        'access_disk':
            "List who's authorised to operate on disk <disk>",
        'access_global_group':
            "List who's authorised to operate on all groups",
        'access_global_host':
            "List who's authorised to operate on all hosts",
        'access_global_maildom':
            "List who's authorised to operate on all e-mail domains",
        'access_global_ou':
            "List who's authorised to operate on all OUs",
        'access_group':
            "List who's authorised to operate on group <gname>",
        'access_host':
            "List who's authorised to operate on host <hostname>",
        'access_list':
            "List everything an account or group can operate on.  Only direct "
            "ownership is reported: the entities an account can access due to "
            "group memberships will not be listed. This does not include "
            "unpersonal users owned by groups.",
        'access_list_opsets':
            "List all operation sets",
        'access_maildom':
            "List who's authorised to operate on e-mail domain <domain>",
        'access_ou':
            "List who's authorised to operate on OU <ou>",
        'access_revoke':
            "Revoke authorisation",
        'access_show_opset':
            "List the operations included in the operation set",
        'access_user':
            "List who's authorised to operate on account <uname>",
    },
}

HELP_ACCESS_ARGS = {

}
