# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway

# Denne fila implementerer er en bofhd extension som i størst mulig
# grad forsøker å etterligne kommandoene i ureg2000 sin bofh klient.
#
# Vesentlige forskjeller:
#  - det finnes ikke lengre fg/ng grupper.  Disse er slått sammen til
#    "group"
#  - det er ikke lenger mulig å lage nye pesoner under bygging av
#    konto, "person create" må kjøres først

import re
import sys
import time
import pickle

import cereconf
from Cerebrum import Account
from Cerebrum import Disk
from Cerebrum import Entity
from Cerebrum import Errors
from Cerebrum import Group
from Cerebrum import Person
from Cerebrum.Constants import _CerebrumCode, _QuarantineCode, _SpreadCode,\
     _PersonAffiliationCode, _PersonAffStatusCode
from Cerebrum import Utils
from Cerebrum.modules import PasswordChecker
from Cerebrum.modules import PosixGroup
from Cerebrum.modules import PosixUser
from Cerebrum.modules.bofhd.cmd_param import *
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.modules.bofhd.auth import BofhdAuth, BofhdAuthOpSet, \
     AuthConstants, BofhdAuthOpTarget, BofhdAuthRole
# from Cerebrum.modules.no.uio import PrinterQuotas
from Cerebrum.modules.no.hist import bofhd_hist_help
from Cerebrum.modules.templates.letters import TemplateHandler

class BofhdExtension(object):
    """All CallableFuncs takes user as first arg, and is responsible
    for checking neccesary permissions"""

    all_commands = {}
    OU_class = Utils.Factory.get('OU')
    external_id_mappings = {}

    def __init__(self, server):
        self.server = server
        self.db = server.db
        self.person = Person.Person(self.db)
        self.const = self.person.const
        self.entity = Entity.Entity(self.db)
        self.name_codes = {}
        for t in self.person.list_person_name_codes():
            self.name_codes[int(t.code)] = t.description
        self.person_affiliation_codes = {}
        self.person_affiliation_statusids = {}
        for c in dir(self.const):
            const = getattr(self.const, c)
            if isinstance(const, _PersonAffStatusCode):
                self.person_affiliation_statusids.setdefault(str(const.affiliation), {})[str(const)] = const
            elif isinstance(const, _PersonAffiliationCode):
                self.person_affiliation_codes[str(const)] = const
        self.external_id_mappings['fnr'] = self.const.externalid_fodselsnr
        # TODO: str2const is not guaranteed to be unique (OK for now, though)
        self.num2const = {}
        self.str2const = {}
        for c in dir(self.const):
            tmp = getattr(self.const, c)
            if isinstance(tmp, _CerebrumCode):
                self.num2const[int(tmp)] = tmp
                self.str2const["%s" % tmp] = tmp
        self.ba = BofhdAuth(server.db)
        aos = BofhdAuthOpSet(server.db)
        self.num2op_set_name = {}
        for r in aos.list():
            self.num2op_set_name[int(r['op_set_id'])] = r['name']

    def get_commands(self, uname):
        # TBD: Do some filtering on uname to remove commands
        commands = {}
        for k in self.all_commands.keys():
            commands[k] = self.all_commands[k].get_struct(self)
        return commands

    def get_help_strings(self):
        return (bofhd_hist_help.group_help, bofhd_hist_help.command_help,
                bofhd_hist_help.arg_help)

    def get_format_suggestion(self, cmd):
        return self.all_commands[cmd].get_fs()

    #
    # group commands
    #

    # group add
    all_commands['group_add'] = Command(
        ("group", "add"), AccountName(help_ref="account_name_src", repeat=True),
        GroupName(help_ref="group_name_dest", repeat=True),
        GroupOperation(optional=True))
    def group_add(self, operator, src_name, dest_group,
                  group_operator=None):
        return self._group_add(operator, src_name, dest_group,
                               group_operator, type="account")

    # group gadd
    all_commands['group_gadd'] = Command(
        ("group", "gadd"), GroupName(help_ref="group_name_src", repeat=True),
        GroupName(help_ref="group_name_dest", repeat=True),
        GroupOperation(optional=True))
    def group_gadd(self, operator, src_name, dest_group,
                  group_operator=None):
        return self._group_add(operator, src_name, dest_group,
                               group_operator, type="group")

    def _group_add(self, operator, src_name, dest_group,
                  group_operator=None, type=None):
        group_operator = self._get_group_opcode(group_operator)
        group_s = account_s = None
        if type == "group":
            src_entity = self._get_group(src_name)
        elif type == "account":
            src_entity = self._get_account(src_name)
        group_d = self._get_group(dest_group)
        self.ba.can_alter_group(operator.get_entity_id(), group_d)
        try:
            group_d.add_member(src_entity.entity_id, src_entity.entity_type, group_operator)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return "OK"

    # group create
    all_commands['group_create'] = Command(
        ("group", "create"), GroupName(help_ref="group_name_new"),
        SimpleString(help_ref="string_description"),
        fs=FormatSuggestion("Group created as a normal group, internal id: %i", ("group_id",)))
    def group_create(self, operator, groupname, description):
        self.ba.can_create_group(operator.get_entity_id())
        g = Group.Group(self.db)
        g.populate(creator_id=operator.get_entity_id(),
                   visibility=self.const.group_visibility_all,
                   name=groupname, description=description)
        try:
            g.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return {'group_id': int(g.entity_id)}

    #  group def
    all_commands['group_def'] = Command(
        ('group', 'def'), AccountName(), GroupName(help_ref="group_name_dest"))
    def group_def(self, operator, accountname, groupname):
        account = self._get_account(accountname, actype="PosixUser")
        grp = self._get_group(groupname, grtype="PosixGroup")
        self.ba.can_alter_group(operator.get_entity_id(), grp)
        account.gid = grp.entity_id
        account.write_db()
        return "OK"

    # group delete
    all_commands['group_delete'] = Command(
        ("group", "delete"), GroupName(), YesNo(help_ref="yes_no_force", default="No"))
    def group_delete(self, operator, groupname, force=None):
        grp = self._get_group(groupname)
        self.ba.can_delete_group(operator.get_entity_id(), grp)
        if self._is_yes(force):
##             u, i, d = grp.list_members()
##             for op, tmp in ((self.const.group_memberop_union, u),
##                             (self.const.group_memberop_intersection, i),
##                             (self.const.group_memberop_difference, d)):
##                 for m in tmp:
##                     grp.remove_member(m[1], op)
            try:
                pg = self._get_group(groupname, grtype="PosixGroup")
                pg.delete()
            except CerebrumError:
                pass   # Not a PosixGroup
        grp.delete()
        return "OK"

    # group remove
    all_commands['group_remove'] = Command(
        ("group", "remove"), AccountName(help_ref="account_name_member", repeat=True),
        GroupName(help_ref="group_name_dest", repeat=True),
        GroupOperation(optional=True))
    def group_remove(self, operator, src_name, dest_group,
                     group_operator=None):
        return self._group_remove(operator, src_name, dest_group,
                               group_operator, type="account")

    # group gremove
    all_commands['group_gremove'] = Command(
        ("group", "gremove"), GroupName(repeat=True),
        GroupName(repeat=True), GroupOperation(optional=True))
    def group_gremove(self, operator, src_name, dest_group,
                      group_operator=None):
        return self._group_remove(operator, src_name, dest_group,
                               group_operator, type="group")

    def _group_remove(self, operator, src_name, dest_group,
                      group_operator=None, type=None):
        group_operator = self._get_group_opcode(group_operator)
        group_s = account_s = None
        if type == "group":
            src_entity = self._get_group(src_name)
        elif type == "account":
            src_entity = self._get_account(src_name)
        group_d = self._get_group(dest_group)
        self.ba.can_alter_group(operator.get_entity_id(), group_d)
        try:
            group_d.remove_member(src_entity.entity_id, group_operator)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return "OK"   # TBD: returns OK if user is not member of group.  correct?

    # group info
    all_commands['group_info'] = Command(
        ("group", "info"), GroupName(),
        fs=FormatSuggestion([("id: %i\nSpreads: %s\nDescription: %s\nExpire: %s",
                              ("entity_id", "spread", "desc", "expire")),
                             ("Gid: %i", ('gid',))]))
    def group_info(self, operator, groupname):
        # TODO: Group visibility should probably be checked against
        # operator for a number of commands
        is_posix = 0
        try:
            grp = self._get_group(groupname, grtype="PosixGroup")
            is_posix = 1
        except CerebrumError:
            grp = self._get_group(groupname)
        ret = {'entity_id': grp.entity_id,
               'spread': ",".join(["%s" % self.num2const[int(a['spread'])]
                                   for a in grp.get_spread()]),
               'desc': grp.description,
               'expire': grp.expire_date}
        if is_posix:
            ret['gid'] = grp.posix_gid
        return ret

    # group list
    all_commands['group_list'] = Command(
        ("group", "list"), GroupName(),
        fs=FormatSuggestion("%-8s %-7s %6i %s", ("op", "type", "id", "name"),
                            hdr="MemberOp Type    Id     Name"))
    def group_list(self, operator, groupname):
        """List direct members of group"""
        group = self._get_group(groupname)
        ret = []
        u, i, d = group.list_members()
        for t, rows in ('union', u), ('inters.', i), ('diff', d):
            for r in rows:
                ret.append({'op': t,
                            'type': str(self.num2const[int(r[0])]),
                            'id': r[1],
                            'name': self._get_entity_name(r[0], r[1])})
        return ret

    # group list_all
    all_commands['group_list_all'] = Command(
        ("group", "list_all"), SimpleString(help_ref="string_group_filter", optional=True),
        fs=FormatSuggestion("%8i %s", ("id", "name"), hdr="%8s %s" % ("Id", "Name")))
    def group_list_all(self, operator, filter=None):
        group = Group.Group(self.db)
        ret = []
        for r in group.list_all():
            ret.append({'id': r[0],
                        'name': self._get_entity_name(self.const.entity_group, r[0])})
        return ret

    # group list_expanded
    all_commands['group_list_expanded'] = Command(
        ("group", "list_expanded"), GroupName(),
        fs=FormatSuggestion("%8i %s", ("member_id", "name"), hdr="Id       Name"))
    def group_list_expanded(self, operator, groupname):
        """List members of group after expansion"""
        group = self._get_group(groupname)
        return [{'member_id': a,
                 'name': self._get_entity_name(self.const.entity_account, a)
                 } for a in group.get_members()]

    # group posix_create
    all_commands['group_posix_create'] = Command(
        ("group", "posix_create"), GroupName(),
        SimpleString(help_ref="string_description", optional=True),
        fs=FormatSuggestion("Group created, posix gid: %i", ("group_id",)))
    def group_posix_create(self, operator, group, description=None):
        self.ba.can_create_group(operator.get_entity_id())
        group=self._get_group(group)
        pg = PosixGroup.PosixGroup(self.db)
        pg.populate(parent=group)
        try:
            pg.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return {'group_id': int(pg.posix_gid)}

    # group posix_delete
    all_commands['group_posix_delete'] = Command(
        ("group", "posix_delete"), GroupName())
    def group_posix_delete(self, operator, group):
        grp = self._get_group(group, grtype="PosixGroup")
        self.ba.can_delete_group(operator.get_entity_id(), grp)
        grp.delete()
        return "OK"
    
    # group set_expire
    all_commands['group_set_expire'] = Command(
        ("group", "set_expire"), GroupName(), Date())
    def group_set_expire(self, operator, group, expire):
        grp = self._get_group(group)
        self.ba.can_delete_group(operator.get_entity_id(), grp)
        grp.expire_date = self._parse_date(expire)
        grp.write_db()
        return "OK"

    # group set_visibility
    all_commands['group_set_visibility'] = Command(
        ("group", "set_visibility"), GroupName(), GroupVisibility())
    def group_set_visibility(self, operator, group, visibility):
        grp = self._get_group(group)
        self.ba.can_delete_group(operator.get_entity_id(), grp)
        grp.visibility = self._map_visibility_id(visibility)
        grp.write_db()
        return "OK"

    # group user
    all_commands['group_user'] = Command(
        ('group', 'user'), AccountName(), fs=FormatSuggestion(
        "%-9s %s", ("memberop", "group"), hdr="Operation Group"))
    def group_user(self, operator, accountname):
        account = self._get_account(accountname)
        group = Group.Group(self.db)
        return [{'memberop': str(self.num2const[int(r['operation'])]),
                 'group': self._get_entity_name(self.const.entity_group, r['group_id'])}
                for r in group.list_groups_with_entity(account.entity_id)]

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
        for c in dir(self.const):
            const = getattr(self.const, c)
            if isinstance(const, _PersonAffStatusCode):
                if not tmp.has_key(str(const.affiliation)):
                    tmp[str(const.affiliation)] = [
                        {'aff': str(const.affiliation), 'status': '',
                         'desc': unicode(const.affiliation._get_description(), 'iso8859-1')}]
                else:
                    tmp[str(const.affiliation)].append(
                        {'aff': '', 'status': "%s" % const,
                         'desc': unicode(const._get_description(), 'iso8859-1')})
        keys = tmp.keys()
        keys.sort()
        ret = []
        for k in keys:
            for r in tmp[k]:
                ret.append(r)
        return ret

        # TODO: Defile affiliations for UiO
        raise NotImplementedError, "Feel free to implement this function"

    # misc checkpassw
    all_commands['misc_checkpassw'] = Command(
        ("misc", "checkpassw"), AccountPassword())
    def misc_checkpassw(self, operator, password):
        pc = PasswordChecker.PasswordChecker(self.db)
        try:
            pc.goodenough(None, password, uname="foobar")
        except PasswordChecker.PasswordGoodEnoughException, m:
            raise CerebrumError, "Bad password: %s" % m
        return "OK"

    all_commands['misc_dadd'] = Command(
        ("misc", "dadd"), SimpleString(help_ref='string_host'), DiskId())
    def misc_dadd(self, operator, hostname, diskname):
        host = self._get_host(hostname)
        disk = Disk.Disk(self.db)
        disk.populate(host.entity_id, diskname, 'uio disk')
        disk.write_db()
        return "OK"

    all_commands['misc_drem'] = Command(
        ("misc", "drem"), SimpleString(help_ref='string_host'), DiskId())
    def misc_drem(self, operator, hostname, diskname):
        host = self._get_host(hostname)
        disk = Disk.Disk(db)
        disk.find_by_path(diskname, host_id=host.entity_id)
        raise NotImplementedError, "API does not support disk removal"

    all_commands['misc_hadd'] = Command(
        ("misc", "hadd"), SimpleString(help_ref='string_host'))
    def misc_hadd(self, operator, hostname):
        host = Disk.Host(self.db)
        host.populate(hostname, 'uio host')
        host.write_db()
        return "OK"

    all_commands['misc_hrem'] = Command(
        ("misc", "hrem"), SimpleString(help_ref='string_host'))
    def misc_hrem(self, operator, hostname):
        host = self._get_host(hostname)
        raise NotImplementedError, "API does not support host removal"

    # misc lmy
    all_commands['misc_lmy'] = Command(
        ("misc", "lmy"), )
    def misc_lmy(self, operator):
        # TODO: Dunno what this command is supposed to do
        raise NotImplementedError, "Feel free to implement this function"

    # misc lsko
    all_commands['misc_lsko'] = Command(
        ("misc", "lsko"), SimpleString())
    def misc_lsko(self, operator):
        # TODO: Dunno what this command is supposed to do
        raise NotImplementedError, "Feel free to implement this function"

    # misc mmove
    all_commands['misc_mmove'] = Command(
        ("misc", "mmove"),
        fs=FormatSuggestion("%-10s %-30s %-15s %-10s %-20s %s", ("requestee", "when", "op", "entity", "destination", "args"),
                            hdr="%-10s %-30s %-15s %-10s %-20s %s" % ("Requestee", "When", "Op", "Entity", "Destination", "Arguments")))
    def misc_mmove(self, operator):
        br = BofhdRequests(self.db, self.const)
        ret = []
        for r in br.get_requests(operator_id=operator.get_entity_id(), given=True):
            op = self.num2const[int(r['operation'])]
            dest = None
            if op in (self.const.bofh_move_user, self.const.bofh_move_request):
                disk = Disk.Disk(self.db)
                disk.find(r['destination_id'])
                dest = disk.path
            elif op in (self.const.bofh_move_give,):
                dest = self._get_entity_name(self.const.entity_group,
                                             r['destination_id'])
            ret.append({'when': r['run_at'],
                        'requestee': self._get_entity_name(self.const.entity_account, r['requestee_id']),
                        'op': str(op),
                        'entity': self._get_entity_name(self.const.entity_account, r['entity_id']),
                        'destination': dest,
                        'args': r['state_data']
                        })
        return ret

    # misc profile_download
    all_commands['misc_profile_download'] = Command(
        ("misc", "profile_download"), SimpleString(help_ref="string_filename"))
    def misc_profile_download(self, operator, filename):
        # TODO: Add support for up/downloading files
        # TODO: Add support for profile handling
        raise NotImplementedError, "Feel free to implement this function"

    # misc profile_upload
    all_commands['misc_profile_upload'] = Command(
        ("misc", "profile_upload"), SimpleString(help_ref="string_filename"))
    def misc_profile_upload(self, operator, filename):
        # TODO: Add support for up/downloading files
        raise NotImplementedError, "Feel free to implement this function"

    # misc user_passwd
    all_commands['misc_user_passwd'] = Command(
        ("misc", "user_passwd"), AccountName(), AccountPassword())
    def misc_user_passwd(self, operator, accountname, password):
        ac = self._get_account(accountname)
        # Only people who can set the password are allowed to check it
        self.ba.can_set_password(operator.get_entity_id(), ac)
        old_pass = ac.get_account_authentication(self.const.auth_type_md5_crypt)
        if(ac.enc_auth_type_md5_crypt(password, salt=old_pass[:old_pass.rindex('$')])
           == old_pass):
            return "Password is correct"
        return "Incorrect password"


    #
    # perm commands
    #

    # perm opset_list
    all_commands['perm_opset_list'] = Command(
        ("perm", "opset_list"), 
        fs=FormatSuggestion("%-6i %s", ("id", "name"), hdr="Id     Name"))
    def perm_opset_list(self, operator):
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
                            hdr="%-6s %-16s %s" % ("Id", "op", "Attributes")))
    def perm_opset_show(self, operator, name):
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
        "TargetId", "TargetEntityId", "TargetType", "TargetName", "Attrs")))
    def perm_target_list(self, operator, target_type, entity_id=None):
        aot = BofhdAuthOpTarget(self.db)
        ret = []
        if target_type.isdigit():
            rows = aot.list(target_id=target_type)
        else:
            rows = aot.list(target_type=target_type, entity_id=entity_id)
        for r in rows:
            if r['target_type'] == 'group':
                name = self._get_entity_name(self.const.entity_group, r['entity_id'])
            elif r['target_type'] == 'disk':
                name = self._get_entity_name(self.const.entity_disk, r['entity_id'])
            elif r['target_type'] == 'host':
                name = self._get_entity_name(self.const.entity_host, r['entity_id'])
            else:
                name = "unknown"
            ret.append({'tgt_id': r['op_target_id'],
                        'entity_id': r['entity_id'],
                        'name': name,
                        'target_type': r['target_type'],
                        'attrs': ", ".join(
                ["%s" % r2['attr'] for r2 in aot.list_target_attrs(r['op_target_id'])])})
        return ret

    # perm add_target_attr
    all_commands['perm_add_target_attr'] = Command(
        ("perm", "add_target_attr"), Id(help_ref="id:op_target"),
        SimpleString(help_ref="string_attribute"))
    def perm_add_target_attr(self, operator, op_target_id, attr):
        aot = BofhdAuthOpTarget(self.db)
        aot.find(op_target_id)
        aot.add_op_target_attr(attr)
        return "OK"

    # perm del_target_attr
    all_commands['perm_del_target_attr'] = Command(
        ("perm", "del_target_attr"), Id(help_ref="id:op_target"),
        SimpleString(help_ref="string_attribute"))
    def perm_del_target_attr(self, operator, op_target_id, attr):
        aot = BofhdAuthOpTarget(self.db)
        aot.find(op_target_id)
        aot.del_op_target_attr(attr)
        return "OK"

    # perm list
    all_commands['perm_list'] = Command(
        ("perm", "list"), Id(),
        fs=FormatSuggestion("%-8s %-8s %-8i",
                            ("entity_id", "op_set_id", "op_target_id"),
                            hdr="%-8s %-8s %-8s" %
                            ("entity_id", "op_set_id", "op_target_id")))
    def perm_list(self, operator, entity_id):
        bar = BofhdAuthRole(self.db)
        ret = []
        for r in bar.list(entity_id):
            ret.append({'entity_id': self._get_entity_name(None, r['entity_id']),
                        'op_set_id': self.num2op_set_name[int(r['op_set_id'])],
                        'op_target_id': r['op_target_id']})
        return ret

    # perm grant
    all_commands['perm_grant'] = Command(
        ("perm", "grant"), Id(), SimpleString(help_ref="string_op_set"),
        Id(help_ref="id:op_target"))
    def perm_grant(self, operator, entity_id, op_set_name, op_target_id):
        bar = BofhdAuthRole(self.db)
        bar.grant_auth(entity_id, op_set_id, op_target_id)
        return "OK"

    # perm revoke
    all_commands['perm_revoke'] = Command(
        ("perm", "revoke"), Id(), SimpleString(help_ref="string_op_set"),
        Id(help_ref="id:op_target"))
    def perm_revoke(self, operator, entity_id, op_set_name, op_target_id):
        bar = BofhdAuthRole(self.db)
        bar.revoke_auth(entity_id, op_set_id, op_target_id)
        return "OK"

    #
    # person commands
    #

    # person accounts
    all_commands['person_accounts'] = Command(
        ("person", "accounts"), PersonId(),
        fs=FormatSuggestion("%6i %s", ("account_id", "name"), hdr="Id     Name"))
    def person_accounts(self, operator, id):
        if id.find(":") == -1 and not id.isdigit():
            ac = self._get_account(id)
            id = "entity_id:%i" % ac.owner_id
        person = self._get_person(*self._map_person_id(id))
        account = Account.Account(self.db)
        ret = []
        for r in account.list_accounts_by_owner_id(person.entity_id):
            account = self._get_account(r['account_id'], idtype='id')

            ret.append({'account_id': r['account_id'],
                        'name': account.account_name})
        return ret

    # person create
    all_commands['person_create'] = Command(
        ("person", "create"), PersonId(),
        Date(), PersonName(help_ref="person_name_full"), OU(),
        Affiliation(), AffiliationStatus(),
        fs=FormatSuggestion("Created: %i",
        ("person_id",)))
    def person_create(self, operator, person_id, bdate, person_name,
                      ou, affiliation, aff_status):
        id_type, id = self._map_person_id(person_id)
        return self._person_create(operator, person_name, bdate, id_type, id)

    def _person_create(self, operator, display_name, birth_date=None,
                      id_type=None, id=None):
        self.ba.can_create_person(operator.get_entity_id())
        person = self.person
        person.clear()
        if birth_date is not None:
            birth_date = self._parse_date(birth_date)
        person.populate(birth_date, self.const.gender_male,
                        description='Manualy created')
        person.affect_names(self.const.system_manual, self.const.name_full)
        person.populate_name(self.const.name_full,
                             display_name.encode('iso8859-1'))
        try:
            if id_type is not None:
                if id_type == self.const.externalid_fodselsnr:
                    person.affect_external_id(self.const.system_manual,
                                              self.const.externalid_fodselsnr)
                    person.populate_external_id(self.const.system_manual,
                                                self.const.externalid_fodselsnr,
                                                id)
            person.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return {'person_id': person.entity_id}

    # person find
    all_commands['person_find'] = Command(
        ("person", "find"), PersonSearchType(), SimpleString(),
        fs=FormatSuggestion("%6i %-28s %10s %s", ('id', 'birth', 'export_id', 'name'),
                            hdr="%6s %-28s %10s %s" % ('Id', 'Birth', 'Exp-id', 'Name')))
    def person_find(self, operator, search_type, value):
        # TODO: Need API support for this
        matches = []
        if search_type == 'person_id':
            person = self._get_person(*self._map_person_id(person_id))
            matches = [{'person_id': person.entity_id}]
        else:
            person = self.person
            person.clear()
            if search_type == 'name':
                matches = person.find_persons_by_name(value)
            elif search_type == 'date':
                matches = person.find_persons_by_bdate(self._parse_date(value))
        ret = []
        for row in matches:
            person = self._get_person('entity_id', row['person_id'])
            ret.append({'id': row['person_id'],
                        'birth': person.birth_date,
                        'export_id': person.export_id,
                        'name': person.get_name(self.const.system_cached,
                                                getattr(self.const, cereconf.DEFAULT_GECOS_NAME))})
        return ret
    
    # person info
    all_commands['person_info'] = Command(
        ("person", "info"), PersonId(),
        fs=FormatSuggestion("Name: %s\nExport ID: %s\nBirth: %s\nAffiliations: %s", ("name", "export_id", "birth", "affiliations")))
    def person_info(self, operator, person_id):
        if person_id.find(":") == -1 and not person_id.isdigit():
            ac = self._get_account(person_id)
            person_id = "entity_id:%i" % ac.owner_id
        person = self._get_person(*self._map_person_id(person_id))
        affiliations = []
        for row in person.get_affiliations():
            ou = self._get_ou(ou_id=row['ou_id'])
            affiliations.append("%s/%s@%s" % (
                self.num2const[int(row['affiliation'])],
                self.num2const[int(row['status'])],
                ou.short_name))
        return {'name': person.get_name(self.const.system_cached,
                                        getattr(self.const, cereconf.DEFAULT_GECOS_NAME)),
                'affiliations': ", ".join(affiliations),
                'export_id': person.export_id,
                'birth': person.birth_date}

    # person set_id
    all_commands['person_set_id'] = Command(
        ("person", "set_id"), PersonId(help_ref="person_id:current"),
        PersonId(help_ref="person_id:new"))
    def person_set_id(self, operator, current_id, new_id):
        person = self._get_person(*self._map_person_id(current_id))
        idtype, id = self._map_person_id(new_id)
        self.ba.can_set_person_id(operator.get_entity_id(), person, idtype)
        person.affect_external_id(self.const.system_manual, idtype)
        person.populate_external_id(self.const.system_manual,
                                    idtype, id)
        person.write_db()
        return "OK"
    
    # person student_info
    all_commands['person_student_info'] = Command(
        ("person", "student_info"), PersonId())
    def person_student_info(self, operator, person_id):
        person = self._get_person(*self._map_person_id(person_id))
        self.ba.can_get_student_info(operator.get_entity_id(), person)
        # TODO: We don't have an API for this yet
        raise NotImplementedError, "Feel free to implement this function"

    # person user_priority
    all_commands['person_user_priority'] = Command(
        ("person", "user_priority"), AccountName(), SimpleString())
    def person_user_priority(self, operator, account_name, priority):
        account = self._get_account(account_name)
        person = self._get_person('entity_id', account.owner_id)
        self.ba.can_set_person_user_priority(operator.get_entity_id(), account)
        # TODO: The API doesn't support this yet
        raise NotImplementedError, "Feel free to implement this function"

    #
    # printer commands
    #

    all_commands['printer_qoff'] = Command(
        ("print", "qoff"), AccountName())
    def printer_qoff(self, operator, accountname):
        account = self._get_account(accountname)
        self.ba.can_alter_printerquta(operator.get_entity_id(), account)
        pq = self._get_printerquota(account.entity_id)
        if pq is None:
            return "User has no quota"
        pq.has_printerquota = 0
        pq.write_db()
        return "OK"

    all_commands['printer_qpq'] = Command(
        ("print", "qpq"), AccountName(),
        fs=FormatSuggestion("Has quota Quota Pages printed This "+
                            "term Weekly q. Term q. Max acc.\n"+
                            "%-9s %5i %13i %9i %9i %7i %8i",
                            ('has_printerquota', 'printer_quota',
                            'pages_printed', 'pages_this_semester',
                            'weekly_quota', 'termin_quota', 'max_quota')))
    def printer_qpq(self, operator, accountname):
        account = self._get_account(accountname)
        self.ba.can_query_printerquta(operator.get_entity_id(), account)
        pq = self._get_printerquota(account.entity_id)
        if pq is None:
            return "User has no quota"
        return {'printer_quota': pq.printer_quota,
                'pages_printed': pq.pages_printed,
                'pages_this_semester': pq.pages_this_semester,
                'termin_quota': pq.termin_quota,
                'has_printerquota': pq.has_printerquota,
                'weekly_quota': pq.weekly_quota,
                'max_quota': pq.max_quota}

    all_commands['printer_upq'] = Command(
        ("print", "upq"), AccountName(), SimpleString())
    def printer_upq(self, operator, accountname, pages):
        account = self._get_account(accountname)
        self.ba.can_alter_printerquta(operator.get_entity_id(), account)
        pq = self._get_printerquota(account.entity_id)
        if pq is None:
            return "User has no quota"
        # TBD: Should we check that pages is not > pq.max_quota?
        pq.printer_quota = pages
        pq.write_db()
        return "OK"

    #
    # quarantine commands
    #

    # quarantine disable
    all_commands['quarantine_disable'] = Command(
        ("quarantine", "disable"), EntityType(default="account"), Id(), QuarantineType(), Date())
    def quarantine_disable(self, operator, entity_type, id, qtype, date):
        entity = self._get_entity(entity_type, id)
        date = self._parse_date(date)
        qtype = int(self.str2const[qtype])
        self.ba.can_disable_quarantine(operator.get_entity_id(), entity, qtype)
        entity.disable_entity_quarantine(qtype, date)
        return "OK"

    # quarantine list
    all_commands['quarantine_list'] = Command(
        ("quarantine", "list"),
        fs=FormatSuggestion("%-14s %s", ('name', 'desc'),
                            hdr="%-14s %s" % ('Name', 'Description')))
    def quarantine_list(self, operator):
        ret = []
        for c in dir(self.const):
            tmp = getattr(self.const, c)
            if isinstance(tmp, _QuarantineCode):
                ret.append({'name': "%s" % tmp, 'desc': unicode(tmp._get_description(), 'iso8859-1')})
        return ret

    # quarantine remove
    all_commands['quarantine_remove'] = Command(
        ("quarantine", "remove"), EntityType(default="account"), Id(), QuarantineType())
    def quarantine_remove(self, operator, entity_type, id, qtype):
        entity = self._get_entity(entity_type, id)
        qtype = int(self.str2const[qtype])
        self.ba.can_remove_quarantine(operator.get_entity_id(), entity, qtype)
        entity.delete_entity_quarantine(qtype)
        return "OK"

    # quarantine set
    all_commands['quarantine_set'] = Command(
        ("quarantine", "set"), EntityType(default="account"), Id(repeat=True), QuarantineType(),
        SimpleString(help_ref="string_why"),
        SimpleString(help_ref="string_from_to"))
    def quarantine_set(self, operator, entity_type, id, qtype, why, date):
        date_start = self.db.TimestampFromTicks(time.time())
        date_end = None
        if date:
            tmp = date.split("--")
            if len(tmp) == 2:
                date_start = self._parse_date(tmp[0])
                date_end = self._parse_date(tmp[1])
            elif len(tmp) == 1:
                date_end = self._parse_date(date)
            else:
                raise CerebrumError, "Incorrect date specification: %s." % date
        entity = self._get_entity(entity_type, id)
        qtype = int(self.str2const[qtype])
        self.ba.can_set_quarantine(operator.get_entity_id(), entity, qtype)
        entity.add_entity_quarantine(qtype, operator.get_entity_id(), why, date_start, date_end)
        return "OK"

    # quarantine show
    all_commands['quarantine_show'] = Command(
        ("quarantine", "show"), EntityType(default="account"), Id(),
        fs=FormatSuggestion("%-14s %-30s %-30s %-30s %-8s %s",
                            ('type', 'start', 'end', 'disable_until', 'who', 'why'),
                            hdr="%-14s %-30s %-30s %-30s %-8s %s" % \
                            ('Type', 'Start', 'End', 'Disable until', 'Who', 'Why')))
    def quarantine_show(self, operator, entity_type, id):
        ret = []
        entity = self._get_entity(entity_type, id)
        self.ba.can_show_quarantines(operator.get_entity_id(), entity)
        for r in entity.get_entity_quarantine():
            acc = self._get_account(r['creator_id'], idtype='id')
            ret.append({'type': "%s" % self.num2const[int(r['quarantine_type'])],
                        'start': r['start_date'],
                        'end': r['end_date'],
                        'disable_until': r['disable_until'],
                        'who': acc.account_name,
                        'why': r['description']})
        return ret
    #
    # spread commands
    #

    # spread add
    all_commands['spread_add'] = Command(
        ("spread", "add"), EntityType(default='account'), Id(), Spread())
    def spread_add(self, operator, entity_type, id, spread):
        entity = self._get_entity(entity_type, id)
        spread = int(self.str2const[spread])
        self.ba.can_add_spread(operator.get_entity_id(), entity, spread)
        entity.add_spread(spread)
        return "OK"

    # spread list
    all_commands['spread_list'] = Command(
        ("spread", "list"),
        fs=FormatSuggestion("%-14s %s", ('name', 'desc'),
                            hdr="%-14s %s" % ('Name', 'Description')))
    def spread_list(self, operator):
        ret = []
        for c in dir(self.const):
            tmp = getattr(self.const, c)
            if isinstance(tmp, _SpreadCode):
                ret.append({'name': "%s" % tmp, 'desc': unicode(tmp._get_description(), 'iso8859-1')})
        return ret

    # spread remove
    all_commands['spread_remove'] = Command(
        ("spread", "remove"), EntityType(default='account'), Id(), Spread())
    def spread_remove(self, operator, entity_type, id, spread):
        entity = self._get_entity(entity_type, id)
        spread = int(self.str2const[spread])
        self.ba.can_add_spread(operator.get_entity_id(), entity, spread)
        entity.delete_spread(spread)
        return "OK"

    # spread accounts
    all_commands['spread_accounts'] = Command(
        ("spread", "accounts"),
        Spread(), OU(optional=True), Date(optional=True),
        fs=FormatSuggestion("%6i %s", ('account_id', 'name'),
                            hdr="Id     Name"))
##  -> Format: brukernavn:pw:OU:Firstname:Lastname:Affiliation:Affiliationstatuscode

    def spread_accounts(self, operator, spread, sko=None, cdate=None):
        # *args
        spread = int(self.str2const[spread])
##         sko = cdate = None
##         while args:
##             arg = args.pop(0)
##             els = arg.split('-')
##             if (len(els) == 3 and
##                 len(els[0]) == 4 and len(els[1]) == 2 and len(els[2]) == 2):
##                 cdate = arg
##             elif len(els) == 1:
##                 sko = arg
##             else:
        if sko is not None:
            sko = self._get_ou(stedkode=sko)
        if cdate is not None:
            cdate = self._parse_date(cdate)
        ret = []
        for e_id in self.entity.list_all_with_spread(spread):
            try:
                account = self._get_account(e_id, idtype='id')
            except CerebrumError:
                # Feil entity_type?
                continue
            atypes = account.get_account_types()
            if (sko is not None and
                int(sko.entity_id) not in [int(t.ou_id) for t in atypes]):
                # Account har ikke riktig stedkode.
                continue
            if (cdate is not None and cdate > account.create_date):
                # Account er eldre enn den angitte cdate.
                continue

            # Finn en (tilfeldig) av stedkodene brukeren har
            # tilknytning til.
            try:
                if sko is None:
                    sko = self._get_ou(atypes[0].ou_id)
                stedkode = "%02d%02d%02d" % (sko.fakultet, sko.institutt,
                                             sko.avdeling)
            except:
                stedkode = ''

            # Finn brukerens nyeste passord, i klartekst.
            pwd_rows = [row for row in
                        self.db.get_log_events(0, (self.const.account_password,))
                        if row.dest_entity == account.entity_id]
            try:
                pwd = pickle.loads(pwd_rows[-1].change_params)['password']
            except:
                pwd = ''

            # Finn personen som eier brukeren, og dermed dennes for-
            # og etternavn.
            person = self._get_person('entity_id', account.owner_id)

            # Finn en (tilfeldig) affiliation, og tilsvarende -status,
            # for brukeren.
            try:
                aff = self.num2const[int(atypes[0].affiliation)]
                affstatus = [self.num2const[int(x.status)] for x in
                             person.get_affiliations()
                             if (x.affiliation == atypes[0].affiliation and
                                 x.ou_id == atypes[0].ou_id)]
            except:
                aff = affstatus = ''
            ret.append("%(brukernavn)s:%(pwd):%(sko)s:%(fname)s:%(lname)s:"+
                       "%(aff)s:%(affstatus)s" %
                       {'brukernavn': account.account_name,
                        'pwd': pwd,
                        'sko': stedkode,
                        'fname': person.get_name(self.const.system_cached,
                                                 self.const.name_first),
                        'lname': person.get_name(self.const.system_cached,
                                                 self.const.name_last),
                        'aff': aff,
                        'affstatus': affstatus
                        })
        return ret

    #
    # user commands
    #

    # user affiliation_add
    all_commands['user_affiliation_add'] = Command(
        ("user", "affiliation_add"), AccountName(), OU(), Affiliation(), AffiliationStatus())
    def user_affiliation_add(self, operator, accountname, ou, aff, aff_status):
        account = self._get_account(accountname)
        aff = self._get_affiliationid(aff)
        aff_status = self._get_affiliation_statusid(aff, aff_status)
        ou = self._get_ou(stedkode=ou)
        person = self._get_person('entity_id', account.owner_id)
        self.ba.can_add_affiliation(operator.get_entity_id(), person, ou, aff, aff_status)

        # Assert that the person already have the affiliation
        has_aff = 0
        for a in person.get_affiliations():
            if a['ou_id'] == ou.entity_id and a['affiliation'] == aff:
                if a['status'] <> aff_status:
                    raise CerebrumError, "Person has conflicting aff_status for this ou/affiliation combination"
                has_aff = 1
                break
        if not has_aff:
            person.add_affiliation(ou.entity_id, aff,
                                   self.const.system_manual, aff_status)
            person.write_db()
        account.set_account_type(ou.entity_id, aff)
        account.write_db()
        return "OK, added %s@%s to %s" % (aff, ou.entity_id, account.owner_id)
    
    # user affiliation_remove
    all_commands['user_affiliation_remove'] = Command(
        ("user", "affiliation_remove"), AccountName(), OU(), Affiliation())
    def user_affiliation_remove(self, operator, accountname, ou, aff): 
        account = self._get_account(accountname)
        aff = self._get_affiliationid(aff)
        ou = self._get_ou(stedkode=ou)
        person = self._get_person('entity_id', account.owner_id)
        self.ba.can_remove_affiliation(operator.get_entity_id(), person, ou, aff)
        account.del_account_type(ou.entity_id, aff)
        account.write_db()
        return "OK"

    # user bcreate
    all_commands['user_bcreate'] = Command(
        ("user", "bcreate"), SimpleString(help_ref="string_filename"))
    def user_bcreate(self, operator, filename):
        raise NotImplementedError, "Feel free to implement this function"

    # user clear_created
    all_commands['user_clear_created'] = Command(
        ("user", "clear_created"), AccountName(optional=True))
    def user_clear_created(self, operator, account_name=None):
        operator.clear_state(state_types=('new_account_passwd', 'user_passwd'))
        return "OK"

    def user_create_prompt_func(self, session, *args):
        """A prompt_func on the command level should return
        {'prompt': message_string, 'map': dict_mapping}
        - prompt is simply shown.
        - map (optional) maps the user-entered value to a value that
          is returned to the server, typically when user selects from
          a list."""
        all_args = list(args[:])
        if(len(all_args) == 0):
            return {'prompt': "Enter bdate, fnr or idtype"}
        arg = all_args.pop(0)
        if(len(all_args) == 0):
            person = self.person
            person.clear()
            if arg.isdigit() and len(arg) > 10:  # finn personer fra fnr
                try:
                    person.find_by_external_id(self.const.externalid_fodselsnr, arg)
                except Errors.NotFoundError:
                    raise CerebrumError, "Could not find that person"
                c = [{'person_id': person.entity_id}]
            elif arg.find("-") != -1:
                # finn personer på fødselsdato
                c = person.find_persons_by_bdate(arg)
            else:
                raise NotImplementedError, "idtype not implemented"
            map = [(("%-8s %s", "Id", "Name"), None)]
            for i in range(len(c)):
                person = self._get_person("entity_id", c[i]['person_id'])
                # TODO: We should show the persons name in the list
                map.append((
                    ("%8i %s", int(c[i]['person_id']),
                     person.get_name(self.const.system_cached, self.const.name_full)),
                    int(c[i]['person_id'])))
            return {'prompt': "Velg person fra listen", 'map': map}
        person_id = all_args.pop(0)
        if(len(all_args) == 0):
            return {'prompt': "Default filgruppe"}
        filgruppe = all_args.pop(0)
        if(len(all_args) == 0):
            return {'prompt': "Shell", 'default': 'bash'}
        shell = all_args.pop(0)
        if(len(all_args) == 0):
            return {'prompt': "Disk", 'help_ref': 'disk'}
        disk = all_args.pop(0)
        if(len(all_args) == 0):
            ret = {'prompt': "Brukernavn", 'last_arg': 1}
            posix_user = PosixUser.PosixUser(self.db)
            try:
                person = self._get_person("entity_id", person_id)
                # TODO: this requires that cereconf.DEFAULT_GECOS_NAME is name_full.  fix
                full = person.get_name(self.const.system_cached, self.const.name_full)
                fname, lname = full.split(" ", 1)
                sugg = posix_user.suggest_unames(self.const.account_namespace, fname, lname)
                if len(sugg) > 0:
                    ret['default'] = sugg[0]
            except ValueError:
                pass    # Failed to generate a default username
            return ret
        raise CerebrumError, "Client called prompt func with too many arguments"

    # user create
    all_commands['user_create'] = Command(
        ('user', 'create'), prompt_func=user_create_prompt_func,
        fs=FormatSuggestion("Created uid=%i, password=%s", ("uid", "password")))
    def user_create(self, operator, idtype, person_id, filegroup, shell, home, uname):
        person = self._get_person("entity_id", person_id)
        group=self._get_group(filegroup)
        posix_user = PosixUser.PosixUser(self.db)
        uid = posix_user.get_free_uid()
        shell = self._get_shell(shell)
        disk_id, home = self._get_disk(home)
        if home is not None:
            if home[0] == ':':
                home = home[1:]
            else:
                raise CerebrumError, "Invalid disk"
        posix_user.clear()
        gecos = None
        expire_date = None
        self.ba.can_create_user(operator.get_entity_id(), person, disk_id)

        posix_user.populate(uid, group.entity_id, gecos, shell, home, 
                            disk_id=disk_id, name=uname,
                            owner_type=self.const.entity_person,
                            owner_id=person.entity_id, np_type=None,
                            creator_id=operator.get_entity_id(),
                            expire_date=expire_date)
        passwd = posix_user.make_passwd(uname)
        posix_user.set_password(passwd)
        try:
            posix_user.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        operator.store_state("new_account_passwd", {'account_id': int(posix_user.entity_id),
                                                    'password': passwd})
        return {'password': passwd, 'uid': uid}

    def user_rcreate_prompt_func(self, session, *args):
        """A prompt_func on the command level should return
        {'prompt': message_string, 'map': dict_mapping}
        - prompt is simply shown.
        - map (optional) maps the user-entered value to a value that
          is returned to the server, typically when user selects from
          a list."""
        all_args = list(args[:])
        if(len(all_args) == 0):
            return {'prompt': "Enter bdate, fnr or idtype"}
        arg = all_args.pop(0)
        if(len(all_args) == 0):
            person = self.person
            person.clear()
            if arg.isdigit() and len(arg) > 10:  # finn personer fra fnr
                try:
                    person.find_by_external_id(self.const.externalid_fodselsnr, arg)
                except Errors.NotFoundError:
                    raise CerebrumError, "Could not find that person"
                c = [{'person_id': person.entity_id}]
            elif arg.find("-") != -1:
                # finn personer på fødselsdato
                c = person.find_persons_by_bdate(arg)
            else:
                raise NotImplementedError, "idtype not implemented"
            map = [(("%-8s %s", "Id", "Name"), None)]
            for i in range(len(c)):
                person = self._get_person("entity_id", c[i]['person_id'])
                # TODO: We should show the persons name in the list
                map.append((
                    ("%8i %s", int(c[i]['person_id']),
                     person.get_name(self.const.system_cached, self.const.name_full)),
                    int(c[i]['person_id'])))
            return {'prompt': "Velg person fra listen", 'map': map}
        person_id = all_args.pop(0)
#        if(len(all_args) == 0):
#            return {'prompt': "Default filgruppe"}
#        filgruppe = all_args.pop(0)
#        if(len(all_args) == 0):
#            return {'prompt': "Shell", 'default': 'bash'}
#        shell = all_args.pop(0)
        if(len(all_args) == 0):
            return {'prompt': "Disk", 'help_ref': 'disk'}
        disk = all_args.pop(0)
        if(len(all_args) == 0):
            ret = {'prompt': "Brukernavn", 'last_arg': 1}
            user = PosixUser.PosixUser(self.db)
            try:
                person = self._get_person("entity_id", person_id)
                # TODO: this requires that cereconf.DEFAULT_GECOS_NAME is name_full.  fix
                full = person.get_name(self.const.system_cached, self.const.name_full)
                fname, lname = full.split(" ", 1)
                sugg = user.suggest_unames(self.const.account_namespace, fname, lname)
                if len(sugg) > 0:
                    ret['default'] = sugg[0]
            except ValueError:
                pass    # Failed to generate a default username
            return ret
        raise CerebrumError, "Client called prompt func with too many arguments"



    # user rcreate
    all_commands['user_rcreate'] = Command(
        ('user', 'reserve'), prompt_func=user_rcreate_prompt_func,
        fs=FormatSuggestion("Created uid=%i, password=%s", ("uname", "password")))
    def user_rcreate(self, operator, idtype, person_id, home, uname):
        person = self._get_person("entity_id", person_id)
        #group=self._get_group(filegroup)
        user = Account.Account(self.db)
        #uid = posix_user.get_free_uid()
        #shell = self._get_shell(shell)
        disk_id, home = self._get_disk(home)
        if home is not None:
            if home[0] == ':':
                home = home[1:]
            else:
                raise CerebrumError, "Invalid disk"
        user.clear()
        #gecos = None
        expire_date = None
        self.ba.can_create_user(operator.get_entity_id(), person, disk_id)

        user.populate(name=uname, owner_type=self.const.entity_person,
                      owner_id=person.entity_id, np_type=None,
                      creator_id=operator.get_entity_id(),
                      expire_date=expire_date, home=home, disk_id=disk_id)
                              
        passwd = user.make_passwd(uname)
        user.set_password(passwd)
        try:
            user.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        operator.store_state("new_account_passwd", {'account_id': int(user.entity_id),
                                                    'password': passwd})
        return {'password': passwd, 'uname': uname}

    # user delete
    all_commands['user_delete'] = Command(
        ("user", "delete"), AccountName())
    def user_delete(self, operator, accountname):
        # TODO: How do we delete accounts?
        account = self._get_account(accountname)
        self.ba.can_delete_user(operator.get_entity_id(), account)
        br = BofhdRequests(self.db, self.const)
        br.add_request(operator.get_entity_id(), br.now,
                       self.const.bofh_delete_user,
                       account.entity_id, None)
        return "User queued for deletion"

        # raise NotImplementedError, "Feel free to implement this function"

    # user gecos
    all_commands['user_gecos'] = Command(
        ("user", "gecos"), AccountName(), PosixGecos())
    def user_gecos(self, operator, accountname, gecos):
        account = self._get_account(accountname, actype="PosixUser")
        # Set gecos to NULL if user requests a whitespace-only string.
        self.ba.can_set_gecos(operator.get_entity_id(), account)
        account.gecos = gecos.strip() or None
        account.write_db()
        return "OK"

    # user history
    all_commands['user_history'] = Command(
        ("user", "history"), AccountName())
    def user_history(self, operator, accountname):
        raise NotImplementedError, "Feel free to implement this function"

    # user info
    all_commands['user_info'] = Command(
        ("user", "info"), AccountName(),
        fs=FormatSuggestion([("entity id: %i\nSpreads: %s\nAffiliations: %s",
                              ("entity_id", "spread", "affiliations")),
                             ("uid: %i\ndfg: %i\ngecos: %s\nshell: %s",
                              ('uid', 'dfg', 'gecos', 'shell'))]))
    def user_info(self, operator, accountname):
        is_posix = 0
        try: 
            account = self._get_account(accountname, actype="PosixUser")
            is_posix = 1
        except CerebrumError:
            account = self._get_account(accountname)
        affiliations = []
        for row in account.get_account_types():
            ou = self._get_ou(ou_id=row['ou_id'])
            affiliations.append("%s@%s" % (self.num2const[int(row['affiliation'])],
                                           ou.short_name))
        ret = {'entity_id': account.entity_id,
               'spread': ",".join(["%s" % self.num2const[int(a['spread'])]
                                   for a in account.get_spread()]),
               'affiliations': ",".join(affiliations)}
        if is_posix:
            ret['uid'] = account.posix_uid
            ret['dfg'] = account.gid_id
            ret['gecos'] = account.gecos
            ret['shell'] = str(self.num2const[int(account.shell)])
        # TODO: Return more info about account
        return ret


    def _map_template(self, num=None):
        """If num==None: return list of avail templates, else return
        selected template """
        tpls = []
        n = 1
        for k in cereconf.BOFHD_TEMPLATES.keys():
            for tpl in cereconf.BOFHD_TEMPLATES[k]:
                tpls.append("%s:%s.%s" % (k, tpl[0], tpl[1]))
                if num is not None and n == int(num):
                    return (k, tpl[0], tpl[1])
                n += 1
        if num is not None:
            raise CerebrumError, "Unknown template selected"
        return tpls

    def _get_cached_passwords(self, operator):
        ret = []
        for r in operator.get_state():
            # state_type, entity_id, state_data, set_time
            if r['state_type'] in ('new_account_passwd', 'user_passwd'):
                ret.append({'account_id': self._get_entity_name(
                    self.const.entity_account, r['state_data']['account_id']),
                            'password': r['state_data']['password'],
                            'operation': r['state_type']})
        return ret

    # user list_passwords
    def user_list_passwords_prompt_func(self, session, *args):
        """  - Går inn i "vis-info-om-oppdaterte-brukere-modus":
  1 Skriv ut passordark
  1.1 Lister ut templates, ber bofh'er om å velge en
  1.1.[0] Spesifiser skriver (for template der dette tillates valgt av
          bofh'er)
  1.1.1 Lister ut alle aktuelle brukernavn, ber bofh'er velge hvilke
        som skal skrives ut ('*' for alle).
  1.1.2 (skriv ut ark/brev)
  2 List brukernavn/passord til skjerm
  """
        all_args = list(args[:])
        if(len(all_args) == 0):
            return {'prompt': "Velg#",
                    'map': [(("Alternativer",), None),
                            (("Skriv ut passordark",), "skriv"),
                            (("List brukernavn/passord til skjerm",), "skjerm")]}
        arg = all_args.pop(0)
        if(arg == "skjerm"):
            return {'last_arg': 1}
        if(len(all_args) == 0):
            map = [(("Alternativer",), None)]
            n = 1
            for t in self._map_template():
                map.append(((t,), n))
                n += 1
            return {'prompt': "Velg template #", 'map': map,
                    'help_ref': 'print_select_template'}
        arg = all_args.pop(0)
        tpl_lang, tpl_name, tpl_type = self._map_template(arg)
        if not tpl_lang.endswith("-letter"):
            if(len(all_args) == 0):
                return {'prompt': 'Oppgi skrivernavn'}
            skriver = all_args.pop(0)
        if(len(all_args) == 0):
            n = 1
            map = [(("%8s %s", "uname", "operation"), None)]
            for row in self._get_cached_passwords(session):
                map.append((("%-12s %s", row['account_id'], row['operation']), n))
                n += 1
            if n == 1:
                raise CerebrumError, "no users"
            return {'prompt': 'Velg bruker(e)', 'last_arg': 1,
                    'map': map, 'raw': 1,
                    'help_ref': 'print_select_range'}

    all_commands['user_list_passwords'] = Command(
        ("user", "list_passwords"), prompt_func=user_list_passwords_prompt_func,
        fs=FormatSuggestion("%-8s %-20s %s", ("account_id", "operation", "password"),
                            hdr="%-8s %-20s %s" % ("Id", "Operation", "Password")))
    def user_list_passwords(self, operator, *args):
        if args[0] == "skjerm":
            return self._get_cached_passwords(operator)
        args = list(args[:])
        args.pop(0)
        tpl_lang, tpl_name, tpl_type = self._map_template(args.pop(0))
        skriver = None
        if not tpl_lang.endswith("-letter"):
            skriver = args.pop(0)
        selection = args.pop(0)
        cache = self._get_cached_passwords(operator)
        th = TemplateHandler(tpl_lang, tpl_name, tpl_type)
        out, out_name = Utils.make_temp_file()
        if th._hdr is not None:
            out.write(th._hdr)
        for n in self._parse_range(selection):
            n -= 1
            mapping = {'Brukernavn': cache[n]['account_id'],
                       'Passord': cache[n]['password']}
            out.write(th.apply_template('body', mapping))
        if th._footer is not None:
            out.write(th._footer)
        out.close()
        # TODO: pick up out_name and send it to printer, running
        # through latex if tpl_type == 'tex'
        return "OK: %s/%s.%s spooled @ %s for %s" % (
            tpl_lang, tpl_name, tpl_type, skriver, selection)

    # user move
    def user_move_prompt_func(self, session, *args):
        all_args = list(args[:])
        print all_args
        if(len(all_args) == 0):
            mt = MoveType()
            return mt.get_struct(self)
        mtype = all_args.pop(0)
        if(len(all_args) == 0):
            an = AccountName()
            return an.get_struct(self)
        ac_name = all_args.pop(0)
        if mtype in ("immediate", "batch", "nofile"):
            if(len(all_args) == 0):
                di = DiskId()
                r = di.get_struct(self)
                r['last_arg'] = 1
                return r
            return {'last_arg': 1}
        elif mtype in ("student", "student_immediate", "confirm", "cancel"):
            return {'last_arg': 1}
        elif mtype in ("request",):
            if(len(all_args) == 0):
                di = DiskId()
                return di.get_struct(self)
            disk = all_args.pop(0)
            if(len(all_args) == 0):
                ss = SimpleString(help_ref="string_why")
                r = ss.get_struct(self)
                r['last_arg'] = 1
                return r
            return {'last_arg': 1}
        elif mtype in ("give",):
            if(len(all_args) == 0):
                who = GroupName()
                return who.get_struct(self)
            who = all_args.pop(0)
            if(len(all_args) == 0):
                ss = SimpleString(help_ref="string_why")
                r = ss.get_struct(self)
                r['last_arg'] = 1
                return r
            return {'last_arg': 1}
        raise CerebrumError, "Bad user_move command (%s)" % mtype
        
    all_commands['user_move'] = Command(
        ("user", "move"), prompt_func=user_move_prompt_func)
    def user_move(self, operator, move_type, accountname, *args):
        account = self._get_account(accountname)
        br = BofhdRequests(self.db, self.const)
        if move_type in ("immediate", "batch", "nofile"):
            disk = args[0]
            disk_id, home = self._get_disk(disk)
            self.ba.can_move_user(operator.get_entity_id(), account, disk_id)
            if disk_id is None and move_type != "nofile":
                raise CerebrumError, "Bad destination disk"
            if move_type == "immediate":
                br.add_request(operator.get_entity_id(), br.now,
                               self.const.bofh_move_user,
                               account.entity_id, disk_id)
                return "Command queued for immediate execution"
            elif move_type == "batch":
                br.add_request(operator.get_entity_id(), br.batch_time,
                               self.const.bofh_move_user,
                               account.entity_id, disk_id)
                return "move queued for execution at %s" % br.batch_time
            elif move_type == "nofile":
                account.disk_id = disk_id
                account.home = home
                account.write_db()
                return "OK, user moved"
        elif move_type in ("student", "student_immediate", "confirm", "cancel"):
            self.ba.can_give_user(operator.get_entity_id(), account)
            if move_type == "student":
                br.add_request(operator.get_entity_id(), br.batch_time,
                               self.const.bofh_move_student,
                               account.entity_id, None)
                return "student-move queued for execution at %s" % br.batch_time
            elif move_type == "student_immediate":
                br.add_request(operator.get_entity_id(), br.now,
                               const.bofh_move_student,
                               account.entity_id, None)
                return "student-move queued for immediate execution"
            elif move_type == "confirm":
                r = br.get_requests(entity_id=account.entity_id,
                                    operation=self.const.bofh_move_request)
                if len(r) < 1:
                    raise CerebrumError, "No matching request found"
                br.delete_request(account.entity_id,
                                  operation=self.const.bofh_move_request)
                # Flag as authenticated
                br.add_request(operator.get_entity_id(), br.batch_time,
                               self.const.bofh_move_user,
                               account.entity_id, r[0]['destination_id'])
                return "move queued for execution at %s" % br.batch_time
            elif move_type == "cancel":
                br.delete_request(account.entity_id,
                                  operator_id=operator.get_entity_id())
                return "OK, move data deleted"
        elif move_type in ("request",):
            disk, why = args[0], args[1]
            disk_id, home = self._get_disk(disk)
            self.ba.can_receive_user(operator.get_entity_id(), account, disk_id)
            br.add_request(operator.get_entity_id(), br.now,
                           self.const.bofh_move_request,
                           account.entity_id, disk_id, why)
            return "OK, request registered"
        elif move_type in ("give",):
            self.ba.can_give_user(operator.get_entity_id(), account)
            group, why = args[0], args[1]
            group = self._get_group(group)
            br.add_request(operator.get_entity_id(), br.now, self.const.bofh_move_give,
                           account.entity_id, group.entity_id, why)
            return "OK, 'give' registered"

    # user password
    all_commands['user_password'] = Command(
        ('user', 'password'), AccountName(), AccountPassword(optional=True))
    def user_password(self, operator, accountname, password=None):
        account = self._get_account(accountname)
        self.ba.can_set_password(operator.get_entity_id(), account)
        if password is None:
            password = account.make_passwd(accountname)
        try:
            pc = PasswordChecker.PasswordChecker(self.db)
            pc.goodenough(account, password)
        except PasswordChecker.PasswordGoodEnoughException, m:
            raise CerebrumError, "Bad password: %s" % m
        account.set_password(password)
        try:
            account.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        operator.store_state("user_passwd", {'account_id': int(account.entity_id),
                                             'password': password})
        return "OK"
    
    # user posix_create
    all_commands['user_posix_create'] = Command(
        ('user', 'posix_create'), AccountName(), GroupName(),
        PosixShell(default="bash"), DiskId())
    def user_posix_create(self, operator, accountname, dfg=None, shell=None,
                          home=None):
        account = self._get_account(accountname)
        pu = PosixUser.PosixUser(self.db)
        uid = pu.get_free_uid()
        group = self._get_group(dfg, grtype='PosixGroup')
        shell = self._get_shell(shell)
        disk_id, home = self._get_disk(home)
        person = self._get_person("entity_id", account.owner_id)
        self.ba.can_create_user(operator.get_entity_id(), person, disk_id)
        pu.populate(uid, group.entity_id, None, shell, home=home,
                    disk_id=disk_id, parent=account)
        pu.write_db()
        return "OK"

    # user posix_delete
    all_commands['user_posix_delete'] = Command(
        ('user', 'posix_delete'), AccountName())
    def user_posix_delete(self, operator, accountname):
        raise NotImplementedError, "Feel free to implement this function"

    # user set_expire
    all_commands['user_set_expire'] = Command(
        ('user', 'set_expire'), AccountName(), Date())
    def user_set_expire(self, operator, accountname, date):
        account = self._get_account(accountname)
        self.ba.can_delete_user(operator.get_entity_id(), account)
        account.expire_date = self._parse_date(date)
        account.write_db()

    # user set_np_type
    all_commands['user_set_np_type'] = Command(
        ('user', 'set_np_type'), AccountName(), SimpleString(help_ref="string_np_type"))
    def user_set_np_type(self, operator, accountname, np_type):
        account = self._get_account(accountname)
        self.ba.can_delete_user(operator.get_entity_id(), account)
        account.np_type = self._map_np_type(np_type)
        account.write_db()

    # user shell
    all_commands['user_shell'] = Command(
        ("user", "shell"), AccountName(), PosixShell(default="bash"))
    def user_shell(self, operator, accountname, shell=None):
        account = self._get_account(accountname, actype="PosixUser")
        self.ba.can_set_shell(operator.get_entity_id(), account, shell)
        shell = self._get_shell(shell)
        account.shell = shell
        account.write_db()
        return "OK"

    # user student_create
    all_commands['user_student_create'] = Command(
        ('user', 'student_create'), PersonId())
    def user_student_create(self, operator, person_id):
        raise NotImplementedError, "Feel free to implement this function"

    #
    # misc helper functions.
    # TODO: These should be protected so that they are not remotely callable
    #

    def _get_account(self, id, idtype='name', actype="Account"):
        if actype == 'Account':
            account = Account.Account(self.db)
        elif actype == 'PosixUser':
            account = PosixUser.PosixUser(self.db)
        account.clear()
        try:
            if idtype == 'name':
                account.find_by_name(id, self.const.account_namespace)
            elif idtype == 'id':
                account.find(id)
            else:
                raise NotImplementedError, "unknown idtype: '%s'" % idtype
        except Errors.NotFoundError:
            raise CerebrumError, "Could not find account with %s=%s" % (idtype, id)
        return account

    def _get_host(self, name):
        host = Disk.Host(self.db)
        try:
            host.find_by_name(name)
            return host
        except Errors.NotFoundError:
            raise CerebrumError, "Unkown host: %s" % name

    def _get_group(self, id, idtype='name', grtype="Group"):
        if grtype == "Group":
            group = Group.Group(self.db)
        elif grtype == "PosixGroup":
            group = PosixGroup.PosixGroup(self.db)
        try:
            group.clear()
            if idtype == 'name':
                group.find_by_name(id)
            elif idtype == 'id':
                group.find(id)
            else:
                raise NotImplementedError, "unknown idtype: '%s'" % idtype
        except Errors.NotFoundError:
            raise CerebrumError, "Could not find group with %s=%s" % (idtype, id)
        return group

    def _get_shell(self, shell):
        if shell == 'bash':
            return self.const.posix_shell_bash
        return int(self.str2const[shell])
    
    def _get_ou(self, ou_id=None, stedkode=None):
        ou = self.OU_class(self.db)
        ou.clear()
        if ou_id is not None:
            ou.find(ou_id)
        else:
            ou.find_stedkode(stedkode[0:2], stedkode[2:4], stedkode[4:6])
        return ou

    def _get_group_opcode(self, operator):
        if operator is None:
            return self.const.group_memberop_union
        if operator == 'union':
            return self.const.group_memberop_union
        raise NotImplementedError, "unknown group opcode: '%s'" % operator

    def _get_entity(self, idtype, id):
        if idtype == 'account':
            return self._get_account(id)
        if idtype == 'person':
            return self._get_person(*self._map_person_id(id))
        if idtype == 'group':
            return self._get_group(id)
        raise CerebrumError, "Invalid idtype"
    
    def _get_person(self, idtype, id):
        person = self.person
        person.clear()
        try:
            if isinstance(idtype, _CerebrumCode):
                person.find_by_external_id(idtype, id)
            elif idtype == 'entity_id':
                person.find(id)
            else:
                raise CerebrumError, "Unkown idtype"
        except Errors.NotFoundError:
            raise CerebrumError, "Could not find person with %s=%s" % (idtype, id)
        return person

    def _map_person_id(self, id):
        """Map <idtype:id> to const.<idtype>, id.  Recognices
        fødselsnummer without <idtype>.  Also recognizes entity_id"""
        if id.isdigit() and len(id) >= 10:
            return self.const.externalid_fodselsnr, id
        id_type, id = id.split(":", 1)
        if id_type != 'entity_id':
            id_type = self.external_id_mappings.get(id_type, None)
        if id_type is not None:
            return id_type, id
        raise CerebrumError, "Unkown person_id type"

    def _get_printerquota(self, account_id):
        pq = PrinterQuotas.PrinterQuotas(self.db)
        try:
            pq.find(account_id)
            return pq
        except Errors.NotFoundError:
            return None

    def _get_nametypeid(self, nametype):
        if nametype == 'first':
            return self.const.name_first
        elif nametype == 'last':
            return self.const.name_last
        elif nametype == 'full':
            return self.const.name_full
        else:
            raise NotImplementedError, "unkown nametype: %s" % nametye

    def _get_entity_name(self, type, id):
        if type is None:
            ety = Entity.Entity(self.db)
            ety.find(id)
            type = self.num2const[int(ety.entity_type)]
        if type == self.const.entity_account:
            acc = self._get_account(id, idtype='id')
            return acc.account_name
        elif type == self.const.entity_group:
            group = self._get_group(id, idtype='id')
            return group.get_name(self.const.group_namespace)
        elif type == self.const.entity_disk:
            disk = Disk.Disk(self.db)
            disk.find(id)
            return disk.path
        elif type == self.const.entity_host:
            host = Disk.Host(self.db)
            host.find(id)
            return host.name
        else:
            return "%s:%s" % (type, id)

    def _get_disk(self, home):
        disk_id = None
        try:
            host = None
            if home.find(":") != -1:
                host, path = home.split(":")
            else:
                path = home
            disk = Disk.Disk(self.db)
            disk.find_by_path(path, host)
            home = None
            disk_id = disk.entity_id
        except Errors.NotFoundError:
            pass
        return disk_id, home

    def _map_np_type(self, np_type):
        # TODO: Assert _AccountCode
        return int(self.str2const[np_type])
        
    def _map_visibility_id(self, visibility):
        # TODO: Assert _VisibilityCode
        return int(self.str2const[visibility])


    def _is_yes(self, val):
        if isinstance(val, str) and val.lower() in ('y', 'yes', 'ja', 'j'):
            return True
        return False
        
    def _get_affiliationid(self, code_str):
        return self.person_affiliation_codes[code_str]

    def _get_affiliation_statusid(self, affiliation, code_str):
        return self.person_affiliation_statusids[str(affiliation)][code_str]

    def _parse_date(self, date):
        if not date:
            return None
        try:
            return self.db.Date(*([ int(x) for x in date.split('-')]))
        except:
            raise CerebrumError, "Illegal date: %s" % date

    def _parse_range(self, selection):
        lst = []
        for part in selection.split():
            idx = part.find('-')
            if idx != -1:
                for n in range(int(part[:idx]), int(part[idx+1:])+1):
                    if n not in lst:
                        lst.append(n)
            else:
                part = int(part)
                if part not in lst:
                    lst.append(part)
        lst.sort()
        return lst
