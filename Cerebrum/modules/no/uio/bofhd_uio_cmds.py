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
import os

import cereconf
from Cerebrum import Account
from Cerebrum import Cache
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
from Cerebrum.modules.bofhd.auth import BofhdAuth, BofhdAuthOpSet, AuthConstants, BofhdAuthOpTarget, BofhdAuthRole
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uio import PrinterQuotas
from Cerebrum.modules.no.uio import bofhd_uio_help
from Cerebrum.modules.templates.letters import TemplateHandler

class BofhdExtension(object):
    """All CallableFuncs takes user as first arg, and is responsible
    for checking neccesary permissions"""

    all_commands = {}
    OU_class = Utils.Factory.get('OU')
    external_id_mappings = {}
    format_time = "date:dd.MM.yy HH:mm"
    format_day = "date:dd.MM.yy"

    def __init__(self, server):
        self.server = server
        self.db = server.db
        self.person = Person.Person(self.db)
        self.const = self.person.const
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
        self.ba = BofhdAuth(self.db)
        aos = BofhdAuthOpSet(self.db)
        self.num2op_set_name = {}
        for r in aos.list():
            self.num2op_set_name[int(r['op_set_id'])] = r['name']
        self.change_type2details = {}
        for r in self.db.get_changetypes():
            self.change_type2details[int(r['change_type_id'])] = [
                r['category'], r['type'], r['msg_string']]

        self._cached_client_commands = Cache.Cache(mixins=[Cache.cache_mru,
                                                           Cache.cache_slots],
                                                   size=500)

    def get_commands(self, account_id):
        try:
            return self._cached_client_commands[int(account_id)]
        except KeyError:
            pass
        commands = {}
        for k in self.all_commands.keys():
            tmp = self.all_commands[k]
            if tmp is not None:
                if tmp.perm_filter:
                    if not getattr(self.ba, tmp.perm_filter)(account_id, query_run_any=True):
                        continue
                commands[k] = tmp.get_struct(self)
        self._cached_client_commands[int(account_id)] = commands
        return commands

    def get_help_strings(self):
        return (bofhd_uio_help.group_help, bofhd_uio_help.command_help,
                bofhd_uio_help.arg_help)

    def get_format_suggestion(self, cmd):
        return self.all_commands[cmd].get_fs()

    #
    # group commands
    #

    # group add
    all_commands['group_add'] = Command(
        ("group", "add"), AccountName(help_ref="account_name_src", repeat=True),
        GroupName(help_ref="group_name_dest", repeat=True),
        GroupOperation(optional=True), perm_filter='can_alter_group')
    def group_add(self, operator, src_name, dest_group,
                  group_operator=None):
        return self._group_add(operator, src_name, dest_group,
                               group_operator, type="account")

    # group gadd
    all_commands['group_gadd'] = Command(
        ("group", "gadd"), GroupName(help_ref="group_name_src", repeat=True),
        GroupName(help_ref="group_name_dest", repeat=True),
        GroupOperation(optional=True), perm_filter='can_alter_group')
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
        fs=FormatSuggestion("Group created as a normal group, internal id: %i", ("group_id",)),
        perm_filter='can_create_group')
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
        account.gid_id = grp.entity_id
        account.write_db()
        return "OK"

    # group delete
    all_commands['group_delete'] = Command(
        ("group", "delete"), GroupName(), YesNo(help_ref="yes_no_force", default="No"),
        perm_filter='can_delete_group')
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
        GroupOperation(optional=True), perm_filter='can_alter_group')
    def group_remove(self, operator, src_name, dest_group,
                     group_operator=None):
        return self._group_remove(operator, src_name, dest_group,
                               group_operator, type="account")

    # group gremove
    all_commands['group_gremove'] = Command(
        ("group", "gremove"), GroupName(repeat=True),
        GroupName(repeat=True), GroupOperation(optional=True),
        perm_filter='can_alter_group')
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
        fs=FormatSuggestion([("Spreads: %s\nDescription: %s\nExpire: %s\nentity id: %i",
                              ("spread", "desc", "expire:%s" % format_day, "entity_id")),
                             ("Gid: %i", ('gid',))]))
    def group_info(self, operator, groupname):
        # TODO: Group visibility should probably be checked against
        # operator for a number of commands
        is_posix = False
        try:
            grp = self._get_group(groupname, grtype="PosixGroup")
            is_posix = True
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
        u, i, d = group.list_members(get_entity_name=True)
        for t, rows in ('union', u), ('inters.', i), ('diff', d):
            for r in rows:
                ret.append({'op': t,
                            'type': str(self.num2const[int(r[0])]),
                            'id': r[1],
                            'name': r[2]})
        return ret

    # group list_all
    all_commands['group_list_all'] = Command(
        ("group", "list_all"), SimpleString(help_ref="string_group_filter", optional=True),
        fs=FormatSuggestion("%8i %s", ("id", "name"), hdr="%8s %s" % ("Id", "Name")),
        perm_filter='is_superuser')
    def group_list_all(self, operator, filter=None):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers (is is slooow)")
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
        return [{'member_id': a[0],
                 'name': a[1]
                 } for a in group.get_members(get_entity_name=True)]

    # group posix_create
    all_commands['group_promote_posix'] = Command(
        ("group", "promote_posix"), GroupName(),
        SimpleString(help_ref="string_description", optional=True),
        fs=FormatSuggestion("Group promoted to PosixGroup, posix gid: %i",
                            ("group_id",)), perm_filter='can_create_group')
    def group_promote_posix(self, operator, group, description=None):
        self.ba.can_create_group(operator.get_entity_id())
        try:
            self._get_group(group, grtype="PosixGroup")
            raise CerebrumError("%s is already a PosixGroup" % group)
        except Errors.NotFountEddor:
            pass

        group=self._get_group(group)
        pg = PosixGroup.PosixGroup(self.db)
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
        grp = self._get_group(group, grtype="PosixGroup")
        self.ba.can_delete_group(operator.get_entity_id(), grp)
        grp.delete()
        return "OK"
    
    # group set_expire
    all_commands['group_set_expire'] = Command(
        ("group", "set_expire"), GroupName(), Date(), perm_filter='can_delete_group')
    def group_set_expire(self, operator, group, expire):
        grp = self._get_group(group)
        self.ba.can_delete_group(operator.get_entity_id(), grp)
        grp.expire_date = self._parse_date(expire)
        grp.write_db()
        return "OK"

    # group set_visibility
    all_commands['group_set_visibility'] = Command(
        ("group", "set_visibility"), GroupName(), GroupVisibility(),
        perm_filter='can_delete_group')
    def group_set_visibility(self, operator, group, visibility):
        grp = self._get_group(group)
        self.ba.can_delete_group(operator.get_entity_id(), grp)
        grp.visibility = self._map_visibility_id(visibility)
        grp.write_db()
        return "OK"

    # group user
    all_commands['group_user'] = Command(
        ('group', 'user'), AccountName(), fs=FormatSuggestion(
        "%-9s %-18s %s", ("memberop", "group", "spreads"),
        hdr="%-9s %-18s %s" % ("Operation", "Group", "Spreads")))
    def group_user(self, operator, accountname):
        account = self._get_account(accountname)
        group = Group.Group(self.db)
        ret = []
        for row in group.list_groups_with_entity(account.entity_id):
            grp = self._get_group(row['group_id'], idtype="id")
            ret.append({'memberop': str(self.num2const[int(row['operation'])]),
                        'group': grp.group_name,
                        'spreads': ",".join(["%s" % self.num2const[int(a['spread'])]
                                             for a in grp.get_spread()])})
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
    all_commands['misc_change_request'] = Command(
        ("misc", "change_request"), Id(), Date())
    def misc_change_request(self, operator, request_id, date):
        date = self._parse_date(date)
        br = BofhdRequests(self.db, self.const)
        old_req = br.get_requests(request_id=request_id)[0]
        if old_req['requestee_id'] != operator.get_entity_id():
            raise PermissionDenied("You are not the requestee")
        br.delete_request(request_id=request_id)
        br.add_request(operator.get_entity_id(), date,
                       old_req['operation'], old_req['entity_id'],
                       old_req['destination_id'],
                       old_req['state_data'])
        return "OK"

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

    # misc clear_passwords
    all_commands['misc_clear_passwords'] = Command(
        ("misc", "clear_passwords"), AccountName(optional=True))
    def misc_clear_passwords(self, operator, account_name=None):
        operator.clear_state(state_types=('new_account_passwd', 'user_passwd'))
        return "OK"


    all_commands['misc_dadd'] = Command(
        ("misc", "dadd"), SimpleString(help_ref='string_host'), DiskId(),
        perm_filter='is_superuser')
    def misc_dadd(self, operator, hostname, diskname):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        host = self._get_host(hostname)
        disk = Disk.Disk(self.db)
        disk.populate(host.entity_id, diskname, 'uio disk')
        disk.write_db()
        return "OK"

    all_commands['misc_dls'] = Command(
        ("misc", "dls"), SimpleString(help_ref='string_host'),
        fs=FormatSuggestion("%-8i %-8i %s", ("disk_id", "host_id", "path",),
                            hdr="DiskId   HostId   Path"))
    def misc_dls(self, operator, hostname):
        host = self._get_host(hostname)
        disk = Disk.Disk(self.db)
        ret = []
        for row in disk.list(host.host_id):
            ret.append({'disk_id': row['disk_id'],
                        'host_id': row['host_id'],
                        'path': row['path']})
        return ret

    all_commands['misc_drem'] = Command(
        ("misc", "drem"), SimpleString(help_ref='string_host'), DiskId(),
        perm_filter='is_superuser')
    def misc_drem(self, operator, hostname, diskname):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        host = self._get_host(hostname)
        disk = Disk.Disk(self.db)
        disk.find_by_path(diskname, host_id=host.entity_id)
        raise NotImplementedError, "API does not support disk removal"

    all_commands['misc_hadd'] = Command(
        ("misc", "hadd"), SimpleString(help_ref='string_host'),
        perm_filter='is_superuser')
    def misc_hadd(self, operator, hostname):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        host = Disk.Host(self.db)
        host.populate(hostname, 'uio host')
        host.write_db()
        return "OK"

    all_commands['misc_hrem'] = Command(
        ("misc", "hrem"), SimpleString(help_ref='string_host'),
        perm_filter='is_superuser')
    def misc_hrem(self, operator, hostname):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        host = self._get_host(hostname)
        raise NotImplementedError, "API does not support host removal"

    # misc list_passwords
    def misc_list_passwords_prompt_func(self, session, *args):
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
        if not all_args:
            return {'prompt': "Velg#",
                    'map': [(("Alternativer",), None),
                            (("Skriv ut passordark",), "skriv"),
                            (("List brukernavn/passord til skjerm",), "skjerm")]}
        arg = all_args.pop(0)
        if(arg == "skjerm"):
            return {'last_arg': True}
        if not all_args:
            map = [(("Alternativer",), None)]
            n = 1
            for t in self._map_template():
                map.append(((t,), n))
                n += 1
            return {'prompt': "Velg template #", 'map': map,
                    'help_ref': 'print_select_template'}
        arg = all_args.pop(0)
        tpl_lang, tpl_name, tpl_type = self._map_template(arg)
        if not tpl_lang.endswith("letter"):
            if not all_args:
                return {'prompt': 'Oppgi skrivernavn'}
            skriver = all_args.pop(0)
        if not all_args:
            n = 1
            map = [(("%8s %s", "uname", "operation"), None)]
            for row in self._get_cached_passwords(session):
                map.append((("%-12s %s", row['account_id'], row['operation']), n))
                n += 1
            if n == 1:
                raise CerebrumError, "no users"
            return {'prompt': 'Velg bruker(e)', 'last_arg': True,
                    'map': map, 'raw': True,
                    'help_ref': 'print_select_range'}

    all_commands['misc_list_passwords'] = Command(
        ("misc", "list_passwords"), prompt_func=misc_list_passwords_prompt_func,
        fs=FormatSuggestion("%-8s %-20s %s", ("account_id", "operation", "password"),
                            hdr="%-8s %-20s %s" % ("Id", "Operation", "Password")))
    def misc_list_passwords(self, operator, *args):
        if args[0] == "skjerm":
            return self._get_cached_passwords(operator)
        args = list(args[:])
        args.pop(0)
        tpl_lang, tpl_name, tpl_type = self._map_template(args.pop(0))
        skriver = None
        if not tpl_lang.endswith("letter"):
            skriver = args.pop(0)
        else:
            skriver = cereconf.PRINT_PRINTER
        selection = args.pop(0)
        cache = self._get_cached_passwords(operator)
        th = TemplateHandler(tpl_lang, tpl_name, tpl_type)
        tmp_dir = Utils.make_temp_dir(prefix="bofh_spool")
        out_name = "%s/%s.%s" % (tmp_dir, "job", tpl_type)
        out = file(out_name, "w")
        if th._hdr is not None:
            out.write(th._hdr)
        ret = []
        
        for n in self._parse_range(selection):
            n -= 1
            account = self._get_account(cache[n]['account_id'])
            mapping = {'uname': cache[n]['account_id'],
                       'password': cache[n]['password'],
                       'account_id': account.entity_id,
                       'lopenr': ''}
            if tpl_lang.endswith("letter"):
                mapping['barcode'] = '%s/barcode_%s.eps' % (
                    tmp_dir, account.entity_id)
                th.make_barcode(account.entity_id, mapping['barcode'])
            person = self._get_person('entity_id', account.owner_id)
            fullname = person.get_name(self.const.system_cached, self.const.name_full)
            mapping['fullname'] =  fullname
            if tpl_lang.endswith("letter"):
                try:
                    address = person.get_entity_address(source=self.const.system_fs,
                                                        type=self.const.address_post)
                except Errors.NotFoundError:
                    try:
                        address = person.get_entity_address(source=self.const.system_lt,
                                                            type=self.const.address_post)
                    except Errors.NotFoundError:
                        ret.append("Error: Couldn't get authtoritative address for %s" % account.account_name)
                        continue
                if not address:
                    ret.append("Error: Couldn't get authtoritative address for %s" % account.account_name)
                    continue
                address = address[0]
                alines = address['address_text'].split("\n")+[""]
                mapping['address_line1'] = fullname
                mapping['address_line2'] = alines[0]
                mapping['address_line3'] = alines[1]
                mapping['zip'] = address['postal_number']
                mapping['city'] = address['city']
                mapping['country'] = address['country']

                mapping['birthdate'] = person.birth_date.strftime('%Y-%m-%d')
                mapping['emailadr'] =  "TODO"  # We probably don't need to support this...

            out.write(th.apply_template('body', mapping))
        if th._footer is not None:
            out.write(th._footer)
        out.close()
        try:
            th.spool_job(out_name, tpl_type, skriver, skip_lpr=0,
                         logfile="%s/spool.log" % tmp_dir)
        except IOError, msg:
            raise CerebrumError(msg)
        ret.append("OK: %s/%s.%s spooled @ %s for %s" % (
            tpl_lang, tpl_name, tpl_type, skriver, selection))
        return "\n".join(ret)

    # misc mmove
    all_commands['misc_list_requests'] = Command(
        ("misc", "list_requests"),
        fs=FormatSuggestion("%-6i %-10s %-14s %-15s %-10s %-20s %s",
                            ("id", "requestee", "when:%s" % format_time,
                             "op", "entity", "destination", "args"),
                            hdr="%-6s %-10s %-14s %-15s %-10s %-20s %s" % (
        "Id", "Requestee", "When", "Op", "Entity", "Destination", "Arguments")))
    def misc_list_requests(self, operator):
        br = BofhdRequests(self.db, self.const)
        ret = []
        for r in br.get_requests(operator_id=operator.get_entity_id(),
                                 given=True):
            op = self.num2const[int(r['operation'])]
            dest = None
            if op in (self.const.bofh_move_user, self.const.bofh_move_request):
                disk = Disk.Disk(self.db)
                disk.find(r['destination_id'])
                dest = disk.path
            elif op in (self.const.bofh_move_give,):
                dest = self._get_entity_name(self.const.entity_group,
                                             r['destination_id'])
            print "R: %s" % r['run_at']
            ret.append({'when': r['run_at'],
                        'requestee': self._get_entity_name(self.const.entity_account, r['requestee_id']),
                        'op': str(op),
                        'entity': self._get_entity_name(self.const.entity_account, r['entity_id']),
                        'destination': dest,
                        'args': r['state_data'],
                        'id': r['request_id']
                        })
        return ret

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

    # perm add_target
    all_commands['perm_add_target'] = Command(
        ("perm", "add_target"), SimpleString(help_ref="string_perm_target_type"),
        Id(), perm_filter='is_superuser')
    def perm_add_target(self, operator, target_type, op_target_id):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        aot = BofhdAuthOpTarget(self.db)
        aot.populate(op_target_id, target_type)
        aot.write_db()
        return "OK"

    # perm add_target_attr
    all_commands['perm_add_target_attr'] = Command(
        ("perm", "add_target_attr"), Id(help_ref="id:op_target"),
        SimpleString(help_ref="string_attribute"),
        perm_filter='is_superuser')
    def perm_add_target_attr(self, operator, op_target_id, attr):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        aot = BofhdAuthOpTarget(self.db)
        aot.find(op_target_id)
        aot.add_op_target_attr(attr)
        return "OK"

    # perm del_target
    all_commands['perm_del_target'] = Command(
        ("perm", "del_target"), Id(help_ref="id:op_target"),
        perm_filter='is_superuser')
    def perm_del_target(self, operator, op_target_id):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        aot = BofhdAuthOpTarget(self.db)
        aot.find(op_target_id)
        aot.delete()
        return "OK"

    # perm del_target_attr
    all_commands['perm_del_target_attr'] = Command(
        ("perm", "del_target_attr"), Id(help_ref="id:op_target"),
        SimpleString(help_ref="string_attribute"), perm_filter='is_superuser')
    def perm_del_target_attr(self, operator, op_target_id, attr):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
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
                            ("entity_id", "op_set_id", "op_target_id")),
        perm_filter='is_superuser')
    def perm_list(self, operator, entity_id):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
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
        Id(help_ref="id:op_target"), perm_filter='is_superuser')
    def perm_grant(self, operator, entity_id, op_set_name, op_target_id):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        bar = BofhdAuthRole(self.db)
        bar.grant_auth(entity_id, op_set_id, op_target_id)
        return "OK"

    # perm revoke
    all_commands['perm_revoke'] = Command(
        ("perm", "revoke"), Id(), SimpleString(help_ref="string_op_set"),
        Id(help_ref="id:op_target"), perm_filter='is_superuser')
    def perm_revoke(self, operator, entity_id, op_set_name, op_target_id):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
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
        Date(help_ref='date_birth'), PersonName(help_ref="person_name_full"), OU(),
        Affiliation(), AffiliationStatus(),
        fs=FormatSuggestion("Created: %i",
        ("person_id",)), perm_filter='can_create_person')
    def person_create(self, operator, person_id, bdate, person_name,
                      ou, affiliation, aff_status):
        self.ba.can_create_person(operator.get_entity_id())
        person = self.person
        person.clear()
        if bdate is not None:
            bdate = self._parse_date(bdate)
        id_type, id = self._map_person_id(person_id)
        gender = self.const.gender_unknown
        if id_type is not None and id:
            if id_type == self.const.externalid_fodselsnr:
                if fodselsnr.er_mann(id):
                    gender = self.const.gender_male
                else:
                    gender = self.const.gender_female
                person.affect_external_id(self.const.system_manual,
                                          self.const.externalid_fodselsnr)
                person.populate_external_id(self.const.system_manual,
                                            self.const.externalid_fodselsnr,
                                            id)
        person.populate(bdate, gender,
                        description='Manualy created')
        person.affect_names(self.const.system_manual, self.const.name_full)
        person.populate_name(self.const.name_full,
                             person_name.encode('iso8859-1'))
        ou = self._get_ou(stedkode=ou)
        aff = self._get_affiliationid(affiliation)
        aff_status = self._get_affiliation_statusid(aff, aff_status)
        try:
            person.write_db()
            person.add_affiliation(ou.entity_id, aff,
                                   self.const.system_manual, aff_status)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return {'person_id': person.entity_id}

    # person find
    all_commands['person_find'] = Command(
        ("person", "find"), PersonSearchType(), SimpleString(),
        fs=FormatSuggestion("%6i %-8s %10s %s", ('id', 'birth:%s' % format_day, 'export_id', 'name'),
                            hdr="%6s %-8s %10s %s" % ('Id', 'Birth', 'Exp-id', 'Name')))
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
        fs=FormatSuggestion("Name: %s\nExport ID: %s\nBirth: %s\nAffiliations: %s",
                            ("name", "export_id", "birth:%s" % format_day, "affiliations")))
    def person_info(self, operator, person_id):
        person = self._get_person(*self._map_person_id(person_id))
        affiliations = []
        for row in person.get_affiliations():
            ou = self._get_ou(ou_id=row['ou_id'])
            affiliations.append("%s/%s@%s" % (
                self.num2const[int(row['affiliation'])],
                self.num2const[int(row['status'])],
                self._format_ou_name(ou)))
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
        ("person", "student_info"), PersonId(), perm_filter='can_get_student_info')
    def person_student_info(self, operator, person_id):
        person = self._get_person(*self._map_person_id(person_id))
        self.ba.can_get_student_info(operator.get_entity_id(), person)
        # TODO: We don't have an API for this yet
        raise NotImplementedError, "Feel free to implement this function"

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
        old_priority = int(old_priority)
        new_priority = int(new_priority)
        ou = None
        affiliation = None
        for row in account.get_account_types():
            if row['priority'] == old_priority:
                ou = row['ou_id']
                affiliation = row['affiliation']
        if ou is None:
            raise CerebrumError("Must specify an existing priority")
        account.set_account_type(ou, affiliation, new_priority)
        account.write_db()
        return "OK"

    all_commands['person_list_user_priorities'] = Command(
        ("person", "list_user_priorities"), PersonId(),
        fs=FormatSuggestion(
        "%8s %8i %s", ('uname', 'priority', 'affiliation'),
        hdr="%8s %8s %s" % ("Uname", "Priority", "Affiliation")))
    def person_list_user_priorities(self, operator, person_id):
        ac = Account.Account(self.db)
        person = self._get_person(*self._map_person_id(person_id))
        ret = []
        for row in ac.get_account_types(all_persons_types=True,
                                        owner_id=person.entity_id):
            ac2 = self._get_account(row['account_id'], idtype='id')
            ou = self._get_ou(ou_id=row['ou_id'])
            ret.append({'uname': ac2.account_name,
                        'priority': row['priority'],
                        'affiliation': '%s@%s' % (
                self.num2const[int(row['affiliation'])], self._format_ou_name(ou))})
            ## This seems to trigger a wierd python bug:
            ## self.num2const[int(row['affiliation'], self._format_ou_name(ou))])})
        return ret
    #
    # printer commands
    #

    all_commands['printer_qoff'] = Command(
        ("print", "qoff"), AccountName(), perm_filter='can_alter_printerquota')
    def printer_qoff(self, operator, accountname):
        account = self._get_account(accountname)
        self.ba.can_alter_printerquta(operator.get_entity_id(), account)
        pq = self._get_printerquota(account.entity_id)
        if pq is None:
            return "User has no quota"
        pq.has_printerquota = False
        pq.write_db()
        return "Quota disabled"

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
        ("print", "upq"), AccountName(), SimpleString(), perm_filter='can_alter_printerquota')
    def printer_upq(self, operator, accountname, pages):
        account = self._get_account(accountname)
        self.ba.can_alter_printerquta(operator.get_entity_id(), account)
        pq = self._get_printerquota(account.entity_id)
        if pq is None:
            return "User has no quota"
        try:
            pages = int(pages)
        except ValueError:
            raise CerebrumError("Enter an integer")
        if pages > pq.max_quota:
            raise CerebrumError("Quota too high, max is %i" % (
                pq.max_quota or 0))
        pq.printer_quota = pages
        pq.write_db()
        return "OK"

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
                ret.append({'name': "%s" % tmp,
                            'desc': unicode(tmp._get_description(), 'iso8859-1')})
        return ret

    # quarantine remove
    all_commands['quarantine_remove'] = Command(
        ("quarantine", "remove"), EntityType(default="account"), Id(), QuarantineType(),
        perm_filter='can_remove_quarantine')
    def quarantine_remove(self, operator, entity_type, id, qtype):
        entity = self._get_entity(entity_type, id)
        qtype = int(self.str2const[qtype])
        self.ba.can_remove_quarantine(operator.get_entity_id(), entity, qtype)
        entity.delete_entity_quarantine(qtype)
        return "OK"

    # quarantine set
    all_commands['quarantine_set'] = Command(
        ("quarantine", "set"), EntityType(default="account"), Id(repeat=True),
        QuarantineType(), SimpleString(help_ref="string_why"),
        SimpleString(help_ref="string_from_to"), perm_filter='can_set_quarantine')
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
        if entity_type != 'account':
            raise CerebrumError("Quarantines can only be set on accounts")
        entity.add_entity_quarantine(qtype, operator.get_entity_id(), why, date_start, date_end)
        return "OK"

    # quarantine show
    all_commands['quarantine_show'] = Command(
        ("quarantine", "show"), EntityType(default="account"), Id(),
        fs=FormatSuggestion("%-14s %-14s %-14s %-14s %-8s %s",
                            ('type', 'start:%s' % format_time,
                             'end:%s' % format_time,
                             'disable_until:%s' % format_day, 'who', 'why'),
                            hdr="%-14s %-14s %-14s %-14s %-8s %s" % \
                            ('Type', 'Start', 'End', 'Disable until', 'Who', 'Why')),
        perm_filter='can_show_quarantines')
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
        ("spread", "add"), EntityType(default='account'), Id(), Spread(),
        perm_filter='can_add_spread')
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
        ("spread", "remove"), EntityType(default='account'), Id(), Spread(),
        perm_filter='can_add_spread')
    def spread_remove(self, operator, entity_type, id, spread):
        entity = self._get_entity(entity_type, id)
        spread = int(self.str2const[spread])
        self.ba.can_add_spread(operator.get_entity_id(), entity, spread)
        entity.delete_spread(spread)
        return "OK"

    #
    # user commands
    #

    # user affiliation_add
    all_commands['user_affiliation_add'] = Command(
        ("user", "affiliation_add"), AccountName(), OU(), Affiliation(), AffiliationStatus(),
        perm_filter='can_add_affiliation')
    def user_affiliation_add(self, operator, accountname, ou, aff, aff_status):
        account = self._get_account(accountname)
        aff = self._get_affiliationid(aff)
        aff_status = self._get_affiliation_statusid(aff, aff_status)
        ou = self._get_ou(stedkode=ou)
        person = self._get_person('entity_id', account.owner_id)
        self.ba.can_add_affiliation(operator.get_entity_id(), person, ou, aff, aff_status)

        # Assert that the person already have the affiliation
        has_aff = False
        for a in person.get_affiliations():
            if a['ou_id'] == ou.entity_id and a['affiliation'] == aff:
                if a['status'] <> aff_status:
                    raise CerebrumError, "Person has conflicting aff_status for this ou/affiliation combination"
                has_aff = True
                break
        if not has_aff:
            if (aff == self.const.affiliation_ansatt or
                aff == self.const.affiliation_student):
                raise PermissionDenied(
                    "Student/Ansatt affiliation can only be set by FS/LT")
            person.add_affiliation(ou.entity_id, aff,
                                   self.const.system_manual, aff_status)
            person.write_db()
        account.set_account_type(ou.entity_id, aff)
        account.write_db()
        return "OK, added %s@%s to %s" % (aff, self._format_ou_name(ou), account.owner_id)
    
    # user affiliation_remove
    all_commands['user_affiliation_remove'] = Command(
        ("user", "affiliation_remove"), AccountName(), OU(), Affiliation(),
        perm_filter='can_remove_affiliation')
    def user_affiliation_remove(self, operator, accountname, ou, aff): 
        account = self._get_account(accountname)
        aff = self._get_affiliationid(aff)
        ou = self._get_ou(stedkode=ou)
        person = self._get_person('entity_id', account.owner_id)
        self.ba.can_remove_affiliation(operator.get_entity_id(), person, ou, aff)
        account.del_account_type(ou.entity_id, aff)
        account.write_db()
        return "OK"

    def _user_create_prompt_func_helper(self, ac_type, session, *args):
        """A prompt_func on the command level should return
        {'prompt': message_string, 'map': dict_mapping}
        - prompt is simply shown.
        - map (optional) maps the user-entered value to a value that
          is returned to the server, typically when user selects from
          a list."""
        all_args = list(args[:])

        if not all_args:
            return {'prompt': "Person identification", 'help_ref': "user_create_person_id"}
        arg = all_args.pop(0)
        if arg.startswith("group:"):
            group_owner = True
        else:
            group_owner = False
        if not all_args or group_owner:
            if group_owner:
                group = self._get_group(arg.split(":")[1])
                if all_args:
                    all_args.insert(0, group.entity_id)
                else:
                    all_args = [group.entity_id]
            else:
                c = self._find_persons(arg)
                map = [(("%-8s %s", "Id", "Name"), None)]
                for i in range(len(c)):
                    person = self._get_person("entity_id", c[i]['person_id'])
                    # TODO: We should show the persons name in the list
                    map.append((
                        ("%8i %s", int(c[i]['person_id']),
                         person.get_name(self.const.system_cached, self.const.name_full)),
                        int(c[i]['person_id'])))
                return {'prompt': "Velg person fra listen", 'map': map,
                        'help_ref': 'user_create_select_person'}
        owner_id = all_args.pop(0)
        if not group_owner:
            if not all_args:
                map = [(("%-8s %s", "Num", "Affiliation"), None)]
                person = self._get_person("entity_id", owner_id)
                for aff in person.get_affiliations():
                    if aff['affiliation'] == int(self.const.affiliation_ansatt):
                        map.append((("%s", str(self.const.affiliation_ansatt)),
                                    int(self.const.affiliation_ansatt)))
                    if aff['affiliation'] == int(self.const.affiliation_student):
                        map.append((("%s", str(self.const.affiliation_student)),
                                    int(self.const.affiliation_student)))
                tmp = self.person_affiliation_statusids[str(self.const.affiliation_manuell)]
                for k in tmp.keys():
                    map.append((("MANUELL:%s", str(tmp[k])), int(tmp[k])))
                return {'prompt': "Velg affiliation fra listen", 'map': map}
            affiliation = all_args.pop(0)
        else:
            if not all_args:
                return {'prompt': "Oppgi np_type"}
            np_type = all_args.pop(0)
        if ac_type == 'PosixUser':
            if not all_args:
                return {'prompt': "Default filgruppe"}
            filgruppe = all_args.pop(0)
            if not all_args:
                return {'prompt': "Shell", 'default': 'bash'}
            shell = all_args.pop(0)
            if not all_args:
                return {'prompt': "Disk", 'help_ref': 'disk'}
            disk = all_args.pop(0)
        if not all_args:
            ret = {'prompt': "Brukernavn", 'last_arg': True}
            posix_user = PosixUser.PosixUser(self.db)
            if not group_owner:
                try:
                    person = self._get_person("entity_id", owner_id)
                    # TODO: this requires that cereconf.DEFAULT_GECOS_NAME is name_full.  fix
                    full = person.get_name(self.const.system_cached, self.const.name_full)
                    fname, lname = full.split(" ", 1)
                    sugg = posix_user.suggest_unames(self.const.account_namespace, fname, lname)
                    if sugg:
                        ret['default'] = sugg[0]
                except ValueError:
                    pass    # Failed to generate a default username
            return ret
        raise CerebrumError, "Client called prompt func with too many arguments"

    def user_create_prompt_func(self, session, *args):
        return self._user_create_prompt_func_helper('PosixUser', session, *args)

    def _user_create_set_account_type(self, account, owner_id, affiliation):
        ou = self._get_ou(stedkode=cereconf.DEFAULT_OU)
        person = self._get_person('entity_id', owner_id)
        if not (affiliation == self.const.affiliation_ansatt or
                affiliation == self.const.affiliation_student):
            tmp = self.person_affiliation_statusids[str(self.const.affiliation_manuell)]
            for k in tmp.keys():
                if affiliation == int(tmp[k]):
                    break
            affiliation = tmp[k].affiliation
            has_affiliation = False
            for a in person.get_affiliations():
                if (a['ou_id'] == ou.entity_id and
                    a['affiliation'] == int(tmp[k].affiliation)):
                    has_affiliation = True
            if not has_affiliation:
                person.add_affiliation(ou.entity_id, tmp[k].affiliation,
                                       self.const.system_manual, tmp[k])
        else:
            for aff in person.get_affiliations():
                if aff['affiliation'] == int(self.const.affiliation_ansatt):
                    ou = self._get_ou(aff['ou_id'])
                if aff['affiliation'] == int(self.const.affiliation_student):
                    ou = self._get_ou(aff['ou_id'])
        account.set_account_type(ou.entity_id, affiliation)
        
    # user create
    all_commands['user_create'] = Command(
        ('user', 'create'), prompt_func=user_create_prompt_func,
        fs=FormatSuggestion("Created uid=%i", ("uid",)),
        perm_filter='can_create_user')
    def user_create(self, operator, *args):
        if len(args) == 6:
            group_id, np_type, filegroup, shell, home, uname = args
            owner_type = self.const.entity_group
            owner_id = self._get_group(group_id.split(":")[1]).entity_id
            np_type = int(self.str2const[np_type])
        else:
            idtype, person_id, affiliation, filegroup, shell, home, uname = args
            owner_type = self.const.entity_person
            owner_id = self._get_person("entity_id", person_id).entity_id
            np_type = None
            
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
        self.ba.can_create_user(operator.get_entity_id(), owner_id, disk_id)

        posix_user.populate(uid, group.entity_id, gecos, shell, home, 
                            disk_id=disk_id, name=uname,
                            owner_type=owner_type,
                            owner_id=owner_id, np_type=np_type,
                            creator_id=operator.get_entity_id(),
                            expire_date=expire_date)
        passwd = posix_user.make_passwd(uname)
        posix_user.set_password(passwd)
        try:
            posix_user.write_db()
            if len(args) != 6:
                self._user_create_set_account_type(posix_user, owner_id, affiliation)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        operator.store_state("new_account_passwd", {'account_id': int(posix_user.entity_id),
                                                    'password': passwd})
        return {'uid': uid}

    # user delete
    all_commands['user_delete'] = Command(
        ("user", "delete"), AccountName(), perm_filter='can_delete_user')
    def user_delete(self, operator, accountname):
        # TODO: How do we delete accounts?
        account = self._get_account(accountname)
        self.ba.can_delete_user(operator.get_entity_id(), account)
        br = BofhdRequests(self.db, self.const)
        br.add_request(operator.get_entity_id(), br.now,
                       self.const.bofh_delete_user,
                       account.entity_id, None)
        return "User %s queued for deletion immeadeately" % account.account_name

        # raise NotImplementedError, "Feel free to implement this function"

    # user gecos
    all_commands['user_gecos'] = Command(
        ("user", "gecos"), AccountName(), PosixGecos(),
        perm_filter='can_set_gecos')
    def user_gecos(self, operator, accountname, gecos):
        account = self._get_account(accountname, actype="PosixUser")
        # Set gecos to NULL if user requests a whitespace-only string.
        self.ba.can_set_gecos(operator.get_entity_id(), account)
        account.gecos = gecos.strip() or None
        account.write_db()
        return "OK"

    # user history
    all_commands['user_history'] = Command(
        ("user", "history"), AccountName(),
        perm_filter='can_show_history')
    def user_history(self, operator, accountname):
        account = self._get_account(accountname)
        self.ba.can_show_history(operator.get_entity_id(), account)
        ret = []
        for r in self.db.get_log_events(0, subject_entity=account.entity_id):
            dest = r['dest_entity']
            if dest is not None:
                self._get_entity_name(None, dest)
            msg = self.change_type2details[int(r['change_type_id'])][2] % {
                'subject': self._get_entity_name(None, r['subject_entity']),
                'dest': dest}
            by = r['change_program'] or self._get_entity_name(None, r['change_by'])
            ret.append("%s [%s]: %s" % (r['tstamp'], by, msg))
        return "\n".join(ret)

    # user info
    all_commands['user_info'] = Command(
        ("user", "info"), AccountName(),
        fs=FormatSuggestion([("Spreads: %s\nAffiliations: %s\n"+
                              "Expire: %s\nHome: %s\nentity id: %i",
                              ("spread", "affiliations", "expire:%s" % format_day, "home", "entity_id")),
                             ("uid: %i\ndefault fg: %i=%s\ngecos: %s\nshell: %s",
                              ('uid', 'dfg_posix_gid', 'dfg_name', 'gecos', 'shell'))]))
    def user_info(self, operator, accountname):
        is_posix = False
        try: 
            account = self._get_account(accountname, actype="PosixUser")
            is_posix = True
        except CerebrumError:
            account = self._get_account(accountname)
        if account.is_deleted() and not self.ba.is_superuser(operator.get_entity_id()):
            raise CerebrumError("User is deleted")
        affiliations = []
        for row in account.get_account_types():
            ou = self._get_ou(ou_id=row['ou_id'])
            affiliations.append("%s@%s" % (self.num2const[int(row['affiliation'])],
                                           self._format_ou_name(ou)))
        ret = {'entity_id': account.entity_id,
               'spread': ",".join(["%s" % self.num2const[int(a['spread'])]
                                   for a in account.get_spread()]),
               'affiliations': ",".join(affiliations),
               'expire': account.expire_date,
               'home': account.home}
        if account.disk_id is not None:
            disk = Disk.Disk(self.db)
            disk.find(account.disk_id)
            ret['home'] = "%s/%s" % (disk.path, account.account_name)

        if is_posix:
            group = self._get_group(account.gid_id, idtype='id', grtype='PosixGroup')
            ret['uid'] = account.posix_uid
            ret['dfg_posix_gid'] = group.posix_gid
            ret['dfg_name'] = group.group_name
            ret['gecos'] = account.gecos
            ret['shell'] = str(self.num2const[int(account.shell)])
        # TODO: Return more info about account
        return ret


    def _map_template(self, num=None):
        """If num==None: return list of avail templates, else return
        selected template """
        tpls = []
        n = 1
        keys = cereconf.BOFHD_TEMPLATES.keys()
        keys.sort()
        for k in keys:
            for tpl in cereconf.BOFHD_TEMPLATES[k]:
                tpls.append("%s:%s.%s (%s)" % (k, tpl[0], tpl[1], tpl[2]))
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

    # user move
    def user_move_prompt_func(self, session, *args):
        all_args = list(args[:])
        print all_args
        if not all_args:
            mt = MoveType()
            return mt.get_struct(self)
        mtype = all_args.pop(0)
        if not all_args:
            an = AccountName()
            return an.get_struct(self)
        ac_name = all_args.pop(0)
        if mtype in ("immediate", "batch", "nofile", "hard_nofile"):
            if not all_args:
                di = DiskId()
                r = di.get_struct(self)
                r['last_arg'] = True
                return r
            return {'last_arg': True}
        elif mtype in ("student", "student_immediate", "confirm", "cancel"):
            return {'last_arg': True}
        elif mtype in ("request",):
            if not all_args:
                di = DiskId()
                return di.get_struct(self)
            disk = all_args.pop(0)
            if not all_args:
                ss = SimpleString(help_ref="string_why")
                r = ss.get_struct(self)
                r['last_arg'] = True
                return r
            return {'last_arg': True}
        elif mtype in ("give",):
            if not all_args:
                who = GroupName()
                return who.get_struct(self)
            who = all_args.pop(0)
            if not all_args:
                ss = SimpleString(help_ref="string_why")
                r = ss.get_struct(self)
                r['last_arg'] = True
                return r
            return {'last_arg': True}
        raise CerebrumError, "Bad user_move command (%s)" % mtype
        
    all_commands['user_move'] = Command(
        ("user", "move"), prompt_func=user_move_prompt_func,
        perm_filter='can_move_user')
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
        elif move_type in ("hard_nofile",):
            if not self.ba.is_superuser(operator.get_entity_id()):
                raise PermissionDenied("only superusers may use hard_nofile")
            account.home = args[0]
            account.disk_id = None
            account.write_db()
            return "OK, user moved to hardcoded homedir"
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
                if not r:
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
                return "OK, move request deleted"
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
    all_commands['user_promote_posix'] = Command(
        ('user', 'promote_posix'), AccountName(), GroupName(),
        PosixShell(default="bash"), DiskId(),
        perm_filter='can_create_user')
    def user_promote_posix(self, operator, accountname, dfg=None, shell=None,
                          home=None):
        try:
            self._get_account(accountname, actype="PosixUser")
            raise CerebrumError("%s is already a PosixUser" % accountname)
        except Errors.NotFoundError:
            pass
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
    all_commands['user_demote_posix'] = Command(
        ('user', 'demote_posix'), AccountName(), perm_filter='can_create_user')
    def user_demote_posix(self, operator, accountname):
        raise NotImplementedError, "Feel free to implement this function"

    def user_create_basic_prompt_func(self, session, *args):
        return self._user_create_prompt_func_helper('Account', session, *args)
    
    # user create
    all_commands['user_reserve'] = Command(
        ('user', 'create_reserve'), prompt_func=user_create_basic_prompt_func,
        fs=FormatSuggestion("Created account_id=%i", ("account_id",)),
        perm_filter='can_create_user')
    def user_reserve(self, operator, idtype, person_id, affiliation, uname):
        person = self._get_person("entity_id", person_id)
        account = Account.Account(self.db)
        account.clear()
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("only superusers may reserve users")
        account.populate(uname,
                         self.const.entity_person,  # Owner type
                         person.entity_id,
                         None,                      # np_type
                         operator.get_entity_id(),  # creator_id
                         None)                      # expire_date
        passwd = account.make_passwd(uname)
        account.set_password(passwd)
        try:
            account.write_db()
            self._user_create_set_account_type(account, person.entity_id, affiliation)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        operator.store_state("new_account_passwd", {'account_id': int(account.entity_id),
                                                    'password': passwd})
        return {'account_id': int(account.entity_id)}

    # user set_expire
    all_commands['user_set_expire'] = Command(
        ('user', 'set_expire'), AccountName(), Date(),
        perm_filter='can_delete_user')
    def user_set_expire(self, operator, accountname, date):
        account = self._get_account(accountname)
        self.ba.can_delete_user(operator.get_entity_id(), account)
        account.expire_date = self._parse_date(date)
        account.write_db()
        return "OK"

    # user set_np_type
    all_commands['user_set_np_type'] = Command(
        ('user', 'set_np_type'), AccountName(), SimpleString(help_ref="string_np_type"),
        perm_filter='can_delete_user')
    def user_set_np_type(self, operator, accountname, np_type):
        account = self._get_account(accountname)
        self.ba.can_delete_user(operator.get_entity_id(), account)
        account.np_type = self._map_np_type(np_type)
        account.write_db()
        return "OK"

    all_commands['user_set_owner'] = Command(
        ("user", "set_owner"), AccountName(), EntityType(default='person'),
        Id(), perm_filter='is_superuser')
    def user_set_owner(self, operator, accountname, entity_type, id):
        account = self._get_account(accountname)
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("only superusers may assign account ownership")
        new_owner = self._get_entity(entity_type, id)
        if account.owner_type == self.const.entity_person:
            for row in account.get_account_types():
                account.del_account_type(row['ou_id'], row['affiliation'])
        account.owner_type=new_owner.entity_type
        account.owner_id=new_owner.entity_id
        account.write_db()
        return "OK"

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
    # commands that are noe available in jbofh, but used by other clients
    #

    all_commands['get_persdata'] = None

    def get_persdata(self, operator, uname):
        ac = self._get_account(uname)
        person_id = "entity_id:%i" % ac.owner_id
        person = self._get_person(*self._map_person_id(person_id))
        ret = {
            'is_personal': len(ac.get_account_types()),
            'fnr': [{'id': r['external_id'],
                     'source': "%s" % self.num2const[r['source_system']]}
                    for r in person.get_external_id(id_type=self.const.externalid_fodselsnr)]
            }
        ac_types = ac.get_account_types(all_persons_types=True)        
        if ret['is_personal']:
            ac_types.sort(lambda x,y: int(x['priority']-y['priority']))
            for at in ac_types:
                ac2 = self._get_account(at['account_id'], idtype='id')
                ret.setdefault('users', []).append(
                    (ac2.account_name, '%s@UIO_HOST' % ac2.account_name,
                     at['priority'], at['ou_id'], "%s" % self.num2const[int(at['affiliation'])]))
            # TODO: kall ac.list_accounts_by_owner_id(ac.owner_id) for
            # å hente ikke-personlige konti?
        if ac.home is not None:
            ret['home'] = ac.home
        else:
            disk = Disk.Disk(self.db)
            disk.find(ac.disk_id)
            ret['home'] = '%s/%s' % (disk.path, ac.account_name)
        ret['navn'] = {'cached': person.get_name(
            self.const.system_cached, self.const.name_full)}
        try:
            ret['work_title'] = person.get_name(
                self.const.system_lt, self.const.name_work_title)
        except Errors.NotFoundError:
            pass
        try:
            ret['personal_title'] = person.get_name(
                self.const.system_lt, self.const.name_personal_title)
        except Errors.NotFoundError:
            pass
        return ret

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
            raise CerebrumError, "Could not find %s with %s=%s" % (actype, idtype, id)
        return account

    def _get_host(self, name):
        host = Disk.Host(self.db)
        try:
            host.find_by_name(name)
            return host
        except Errors.NotFoundError:
            raise CerebrumError, "Unkown host: %s" % name

    def _get_group(self, id, idtype=None, grtype="Group"):
        if grtype == "Group":
            group = Group.Group(self.db)
        elif grtype == "PosixGroup":
            group = PosixGroup.PosixGroup(self.db)
        try:
            group.clear()
            if idtype is None:
                if id.isdigit():
                    idtype='id'
                else:
                    idtype='name'
            if idtype == 'name':
                group.find_by_name(id)
            elif idtype == 'id':
                group.find(id)
            else:
                raise NotImplementedError, "unknown idtype: '%s'" % idtype
        except Errors.NotFoundError:
            raise CerebrumError, "Could not find %s with %s=%s" % (grtype, idtype, id)
        return group

    def _get_shell(self, shell):
        if shell == 'bash':
            return self.const.posix_shell_bash
        return int(self.str2const[shell])
    
    def _format_ou_name(self, ou):
        return "%s (%02i%02i%02i)" % (ou.short_name, ou.fakultet,
                                      ou.institutt, ou.avdeling)

    def _get_ou(self, ou_id=None, stedkode=None):
        ou = self.OU_class(self.db)
        ou.clear()
        if ou_id is not None:
            ou.find(ou_id)
        else:
            ou.find_stedkode(stedkode[0:2], stedkode[2:4], stedkode[4:6],
                             institusjon=cereconf.DEFAULT_INSTITUSJONSNR)
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

    def _find_persons(self, arg):
        if arg.isdigit() and len(arg) > 10:  # finn personer fra fnr
            arg = 'fnr:%s' % arg
        ret = []
        person = self.person
        person.clear()
        if arg.find("-") != -1:
            # finn personer på fødselsdato
            ret = person.find_persons_by_bdate(arg)
        elif arg.find(":") != -1:
            idtype, id = arg.split(":")
            if idtype == 'exp':
                raise NotImplementedError, "Lack API support for this"
            elif idtype == 'fnr':
                for ss in [self.const.system_fs, self.const.system_lt,
                           self.const.system_manual, self.const.system_ureg]:
                    try:
                        person.clear()
                        person.find_by_external_id(self.const.externalid_fodselsnr, id,
                                                   source_system=ss)
                        ret.append({'person_id': person.entity_id})
                    except Errors.NotFoundError:
                        pass
        else:
            raise CerebrumError, "Unable to parse person id"
        return ret
    
    def _get_person(self, idtype, id):
        person = self.person
        person.clear()
        try:
            if str(idtype) == 'account_name':
                ac = self._get_account(id)
                id = ac.owner_id
                idtype = "entity_id"
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
        if id.find(":") == -1:
            return "account_name", id

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
            raise CerebrumError("Unknown disk: %s" % home)
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
        for k in self.person_affiliation_codes.keys():
            if k.lower() == code_str.lower():
                return self.person_affiliation_codes[k]
        raise CerebrumError("Unknown affiliation")

    def _get_affiliation_statusid(self, affiliation, code_str):
        for k in self.person_affiliation_statusids[str(affiliation)].keys():
            if k.lower() == code_str.lower():
                return self.person_affiliation_statusids[str(affiliation)][k]
        raise CerebrumError("Unknown affiliation status")

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
