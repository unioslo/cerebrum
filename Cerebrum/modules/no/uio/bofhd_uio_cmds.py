# Copyright 2002, 2003 University of Oslo, Norway

# Denne fila implementerer er en bofhd extension som i størst mulig
# grad forsøker å etterligne kommandoene i ureg2000 sin bofh klient.
#
# Vesentlige forskjeller:
#  - det finnes ikke lengre fg/ng grupper.  Disse er slått sammen til
#    "group"
#  - det er ikke lenger mulig å lage nye pesoner under bygging av
#    konto, "person create" må kjøres først

from cmd_param import *
from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum import Group
from Cerebrum import Person
from Cerebrum import Disk
from Cerebrum import Entity
from Cerebrum.modules import PosixGroup
from Cerebrum.modules.no.uio import PrinterQuotas
from Cerebrum.Utils import Factory
from templates.letters import TemplateHandler
from server.bofhd_errors import CerebrumError
from Cerebrum.modules.no.uio import bofhd_uio_help
from Cerebrum.Constants import _CerebrumCode, _QuarantineCode
import cereconf
from Cerebrum.modules import PosixUser
import re
import sys

class BofhdExtension(object):
    """All CallableFuncs takes user as first arg, and is responsible
    for checking neccesary permissions"""

    all_commands = {}
    OU_class = Factory.get('OU')
    external_id_mappings = {}

    def __init__(self, server):
        self.server = server
        self.db = server.db
        self.person = Person.Person(self.db)
        self.const = self.person.const
        self.name_codes = {}
        for t in self.person.list_person_name_codes():
            self.name_codes[int(t.code)] = t.description
        self.person_affiliation_codes = {}
        for t in self.person.list_person_affiliation_codes():
            self.person_affiliation_codes[t.code_str] = (int(t.code), t.description)
        self.external_id_mappings['fnr'] = self.const.externalid_fodselsnr
        # TODO: str2const is not guaranteed to be unique (OK for now, though)
        self.num2const = {}
        self.str2const = {}
        for c in dir(self.const):
            tmp = getattr(self.const, c)
            if isinstance(tmp, _CerebrumCode):
                self.num2const[int(tmp)] = tmp
                self.str2const["%s" % tmp] = tmp

    def get_commands(self, uname):
        # TBD: Do some filtering on uname to remove commands
        commands = {}
        for k in self.all_commands.keys():
            commands[k] = self.all_commands[k].get_struct(self)
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
        ('group', 'def'), GroupName(help_ref="group_name_dest"), AccountName())
    def group_def(self, operator, accountname, groupname):
        account = self._get_account(accountname, actype="PosixUser")
        grp = self._get_group(groupname, grtype="PosixGroup")
        account.gid = grp.entity_id
        account.write_db()
        return "OK"

    # group delete
    all_commands['group_delete'] = Command(
        ("group", "delete"), GroupName(), YesNo(help_ref="yes_no_force", optional=True, default="No"))
    def group_delete(self, operator, groupname, force=None):
        if self._is_yes(force):
            raise NotImplementedError, "Force not implemented"
        grp = self._get_group(groupname)
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
        try:
            group_d.remove_member(src_entity.entity_id, group_operator)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return "OK"   # TBD: returns OK if user is not member of group.  correct?

    # group info
    all_commands['group_info'] = Command(
        ("group", "info"), GroupName(),
        fs=FormatSuggestion("id: %i\nSpreads: %s", ("entity_id", "spread")))
    def group_info(self, operator, groupname):
        grp = self._get_group(groupname)
        
        # TODO: Return more info about groups
        # TODO: We need a method for formating lists (here: spreads)
        #       as part of the result
        return {'entity_id': grp.entity_id,
                'spread': ",".join(["%s" % self.num2const[int(a['spread'])]
                                    for a in grp.get_spread()])}

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
                            'type': self.num2const[r[0]],
                            'id': r[1],
                            'name': self._get_entity_name(r[0], r[1])})
        return ret

    # group list_all
    all_commands['group_list_all'] = Command(
        ("group", "list_all"), SimpleString(help_ref="string_group_filter", optional=True))
    def group_list_all(self, operator, filter=None):
        raise NotImplementedError, "Feel free to implement this function"

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
        SimpleString(help_ref="string_description", optional=True))
    def group_posix_create(self, operator, group, description=None):
        raise NotImplementedError, "Feel free to implement this function"

    # group posix_delete
    all_commands['group_posix_delete'] = Command(
        ("group", "posix_delete"), GroupName(), SimpleString(help_ref="string_description"))
    def group_posix_delete(self, operator, group, description):
        raise NotImplementedError, "Feel free to implement this function"

    # group set_expire
    all_commands['group_set_expire'] = Command(
        ("group", "set_expire"), GroupName(), Date())
    def group_set_expire(self, operator, group, expire):
        raise NotImplementedError, "Feel free to implement this function"

    # group set_visibility
    all_commands['group_set_visibility'] = Command(
        ("group", "set_visibility"), GroupName(), GroupVisibility())
    def group_set_visibility(self, operator, group, visibility):
        raise NotImplementedError, "Feel free to implement this function"

    # group user
    all_commands['group_user'] = Command(
        ('group', 'user'), AccountName(), fs=FormatSuggestion(
        "%-9s %s", ("memberop", "group"), hdr="Operation Group"))
    def group_user(self, operator, accountname):
        account = self._get_account(accountname)
        group = Group.Group(self.db)
        return [{'memberop': self.num2const[r['operation']],
                 'group': self._get_entity_name(self.const.entity_group, r['group_id'])}
                for r in group.list_groups_with_entity(account.entity_id)]

    #
    # misc commands
    #

    # misc aff_status_codes
    all_commands['misc_aff_status_codes'] = Command(
        ("misc", "aff_status_codes"), )
    def misc_aff_status_codes(self, operator):
        # TODO: Define aff_status_codes for UiO
        raise NotImplementedError, "Feel free to implement this function"

    # misc affiliations
    all_commands['misc_affiliations'] = Command(
        ("misc", "affiliations"), )
    def misc_affiliations(self, operator):
        # TODO: Defile affiliations for UiO
        raise NotImplementedError, "Feel free to implement this function"

    # misc all_requests
    all_commands['misc_all_requests'] = Command(
        ("misc", "all_requests"), )
    def misc_all_requests(self, operator):
        # TODO: Add support for storing move requests
        raise NotImplementedError, "Feel free to implement this function"

    # misc checkpassw
    all_commands['misc_checkpassw'] = Command(
        ("misc", "checkpassw"), AccountPassword())
    def misc_checkpassw(self, operator, password):
        posix_user = PosixUser.PosixUser(self.db)
        try:
            posix_user.goodenough("foobar", password)
        except:
            raise CerebrumError, "Bad password: %s" % sys.exc_info()[0]
        return "OK"

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

    # misc mmove_confirm
    all_commands['misc_mmove_confirm'] = Command(
        ("misc", "mmove_confirm"), )
    def misc_mmove_confirm(self, operator):
        # TODO: Add support for storing move requests
        raise NotImplementedError, "Feel free to implement this function"

    # misc mmove_requests
    all_commands['misc_mmove_requests'] = Command(
        ("misc", "mmove_requests"), )
    def misc_mmove_requests(self, operator):
        # TODO: Add support for storing move requests
        raise NotImplementedError, "Feel free to implement this function"


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
        old_pass = ac.get_account_authentication(self.const.auth_type_md5_crypt)
        if(ac.enc_auth_type_md5_crypt(password, salt=old_pass[:old_pass.rindex('$')])
           == old_pass):
            return "Password is correct"
        return "Incorrect password"

    #
    # person commands
    #

    # person accounts
    all_commands['person_accounts'] = Command(
        ("person", "accounts"), PersonId(),
        fs=FormatSuggestion("%6i %s", ("account_id", "name"), hdr="Id     Name"))
    def person_accounts(self, operator, id):
        # TODO (haster ikke): allow id to be an accountname
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
        return self._person_create(operator, display_name, id=id)

    def _person_create(self, operator, display_name, birth_date=None,
                      id_type=None, id=None):
        person = self.person
        person.clear()
        if birth_date is not None:
            birth_date = self._parse_date(birth_date)
        person.populate(birth_date, self.const.gender_male,
                        description='Manualy created')
        # TDB: new constants
        person.affect_names(self.const.system_manual, self.const.name_full)
        person.populate_name(self.const.name_full,
                             display_name.encode('iso8859-1'))
        try:
            if id_type is not None:
                if id_type == 'fnr':
                    person.populate_external_id(self.const.system_manual,
                                                self.const.externalid_fodselsnr,
                                                id)
            person.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return {'person_id': person.entity_id}

    # person find
    all_commands['person_find'] = Command(
        ("person", "find"), PersonSearchType(), SimpleString())
    def person_find(self, operator, search_type, value):
        # TODO: Need API support for this
        if search_type == 'name':
            pass
        elif search_type == 'date':
            pass
        elif search_type == 'person_id':
            person = self._get_person(*self._map_person_id(person_id))
        raise NotImplementedError, "Feel free to implement this function"

    # person info
    all_commands['person_info'] = Command(
        ("person", "info"), PersonId(),
        fs=FormatSuggestion("Name: %s\nExport ID: %s\n", ("name", "export_id")))
    def person_info(self, operator, person_id):
        person = self._get_person(*self._map_person_id(person_id))
        # TODO: also return all affiliations for the person
        # TODO: remove """ when we get a correctly populated database
        return {'name': """person.get_name(self.const.system_cached,
                                        getattr(self.const, cereconf.DEFAULT_GECOS_NAME))""",
                'export_id': person.export_id}

    # person set_id
    all_commands['person_set_id'] = Command(
        ("person", "set_id"), PersonId(help_ref="person_id:current"),
        PersonId(help_ref="person_id:new"))
    def person_set_id(self, operator, current_id, new_id):
        person = self._get_person(*self._map_person_id(current_id))
        idtype, id = self._map_person_id(current_id)
        person.populate_external_id(self.const.system_manual,
                                    idtype, id)
        person.write_db()
        # TODO:  This currently does not work as it is not implemented in Person
        return "OK"
    
    # person student_info
    all_commands['person_student_info'] = Command(
        ("person", "student_info"), PersonId())
    def person_student_info(self, operator, person_id):
        person = self._get_person(*self._map_person_id(current_id))
        # TODO: We don't have an API for this yet
        raise NotImplementedError, "Feel free to implement this function"

    # person user_priority
    all_commands['person_user_priority'] = Command(
        ("person", "user_priority"), AccountName(), SimpleString())
    def person_user_priority(self, operator, person_id):
        # TODO: The API doesn't support this yet
        raise NotImplementedError, "Feel free to implement this function"

    #
    # printer commands
    #

    all_commands['printer_qoff'] = Command(
        ("print", "qoff"), AccountName())
    def printer_qoff(self, operator, accountname):
        account = self._get_account(accountname)
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
        entity.disable_entity_quarantine(qtype, date)
        return "OK"

    # quarantine info
    all_commands['quarantine_info'] = Command(
        ("quarantine", "info"), QuarantineType())
    def quarantine_info(self, operator, qtype):
        # TODO: I'm uncertain as to what this is supposed to do
        raise NotImplementedError, "Feel free to implement this function"

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
        entity.delete_entity_quarantine(qtype)
        return "OK"

    # quarantine set
    all_commands['quarantine_set'] = Command(
        ("quarantine", "set"), EntityType(default="account"), Id(repeat=True), QuarantineType(),
        SimpleString(help_ref="string_why"),
        SimpleString(help_ref="string_from_to"))
    def quarantine_set(self, operator, entity_type, id, qtype, why, date):
        date_start = date_end = None
        if date is not None:
            tmp = date.split("-")
            if len(tmp) == 6:
                date_start = self._parse_date("-".join(tmp[:3]))
                date_end = self._parse_date("-".join(tmp[3:]))
            else:
                date_start = self._parse_date(date)
        entity = self._get_entity(entity_type, id)
        qtype = int(self.str2const[qtype])
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
        ("spread", "add"), EntityType(), Id(), Spread())
    def spread_add(self, operator, entity_type, id, spread):
        raise NotImplementedError, "Feel free to implement this function"

    # spread info
    all_commands['spread_info'] = Command(
        ("spread", "info"), Spread())
    def spread_info(self, operator, spread):
        raise NotImplementedError, "Feel free to implement this function"

    # spread list
    all_commands['spread_list'] = Command(
        ("spread", "list"),)
    def spread_list(self, operator):
        raise NotImplementedError, "Feel free to implement this function"

    # spread remove
    all_commands['spread_remove'] = Command(
        ("spread", "remove"), EntityType(), Id(), Spread())
    def spread_remove(self, operator, entity_type, id, spread):
        raise NotImplementedError, "Feel free to implement this function"


    #
    # user commands
    #

    # user affiliation_add
    all_commands['user_affiliation_add'] = Command(
        ("user", "affiliation_add"), AccountName(), OU(), Affiliation(), AffiliationStatus())
    def user_affiliation_add(self, operator, accountname):
        raise NotImplementedError, "Feel free to implement this function"

    # user affiliation_remove
    all_commands['user_affiliation_remove'] = Command(
        ("user", "affiliation_remove"), AccountName(), OU())
    def user_affiliation_remove(self, operator, accountname):
        raise NotImplementedError, "Feel free to implement this function"

    # user affiliations
    all_commands['user_affiliations'] = Command(
        ("user", "affiliations"), AccountName())
    def user_affiliations(self, operator, accountname):
        raise NotImplementedError, "Feel free to implement this function"

    # user bcreate
    all_commands['user_bcreate'] = Command(
        ("user", "bcreate"), SimpleString(help_ref="string_filename"))
    def user_bcreate(self, operator, filename):
        raise NotImplementedError, "Feel free to implement this function"

    # user clear_created
    all_commands['user_clear_created'] = Command(
        ("user", "clear_created"), AccountName(optional=True))
    def user_clear_created(self, operator, account_name=None):
        raise NotImplementedError, "Feel free to implement this function"

    def user_create_prompt_func(self, session, *args):
        """A prompt_func on the command level should return
        {'prompt': message_string, 'map': dict_mapping}
        - prompt is simply shown.
        - map (optional) maps the user-entered value to a value that
          is returned to the server, typically when user selects from
          a list."""
        print "Got: %s" % str(args)
        all_args = list(args[:])
        if(len(all_args) == 0):
            return {'prompt': "Enter bdate, fnr or idtype"}
        arg = all_args.pop(0)
        if(len(all_args) == 0):
            person = self.person
            person.clear()
            if arg.isdigit() and len(arg) > 10:  # finn personer fra fnr
                person.find_by_external_id(self.const.externalid_fodselsnr, arg)
                c = [{'person_id': person.entity_id}]
            elif arg.find("-") != -1:
                # finn personer på fødselsdato
                c = person.find_persons_by_bdate(arg)
            else:
                raise NotImplementedError, "idtype not implemented"
            map = {}
            plist = ""
            for i in range(len(c)):
                # TODO: We should show the persons name in the list
                map["%i" % i] = int(c[i]['person_id'])
                plist += "%3i  %i\n" % (i, c[i]['person_id'])
            return {'prompt': "Num  Id\n"+plist+"Velg person fra listen", 'map': map}
        person_id = all_args.pop(0)
        if(len(all_args) == 0):
            return {'prompt': "Default filgruppe"}
        filgruppe = all_args.pop(0)
        if(len(all_args) == 0):
            return {'prompt': "Shell", 'default': 'bash'}
        shell = all_args.pop(0)
        if(len(all_args) == 0):
            return {'prompt': "Disk"}
        disk = all_args.pop(0)
        if(len(all_args) == 0):
            ret = {'prompt': "Brukernavn", 'last_arg': 1}
            posix_user = PosixUser.PosixUser(self.db)
            try:
                person = self._get_person("entity_id", person_id)
                # TODO: this requires that cereconf.DEFAULT_GECOS_NAME is name_full.  fix
                full = person.get_name(self.const.system_cached, self.const.name_full)
                lname, fname = full.split(" ", 1)
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
        posix_user.clear()
        gecos = None
        expire_date = None

        posix_user.populate(uid, group.entity_id, gecos, shell, home, 
                            disk_id=disk_id, name=uname,
                            owner_type=self.const.entity_person,
                            owner_id=person.entity_id, np_type=None,
                            creator_id=operator.get_entity_id(),
                            expire_date=expire_date)
        passwd = posix_user.make_passwd(None)
        posix_user.set_password(passwd)
        try:
            posix_user.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        operator.store_state("new_account_passwd", {'account_id': int(posix_user.entity_id),
                                                    'password': passwd})
        return {'password': passwd, 'uid': uid}

    # user delete
    all_commands['user_delete'] = Command(
        ("user", "delete"), AccountName())
    def user_delete(self, operator, accountname):
        # TODO: How do we delete accounts?
        raise NotImplementedError, "Feel free to implement this function"

    # user gecos
    all_commands['user_gecos'] = Command(
        ("user", "gecos"), AccountName(), PosixGecos())
    def user_gecos(self, operator, accountname, gecos):
        raise NotImplementedError, "Feel free to implement this function"

    # user history
    all_commands['user_history'] = Command(
        ("user", "history"), AccountName())
    def user_history(self, operator, accountname):
        raise NotImplementedError, "Feel free to implement this function"

    # user info
    all_commands['user_info'] = Command(
        ("user", "info"), AccountName(),
        fs=FormatSuggestion("entity id: %i\nSpreads: %s", ("entity_id", "spread")))
    def user_info(self, operator, accountname):
        account = self._get_account(accountname)
        # TODO: Return more info about account
        return {'entity_id': account.entity_id,
                'spread': ",".join([self.num2const[int(a['spread'])]
                                    for a in account.get_spread()])}

    # user list_created
    all_commands['user_list_created'] = Command(
        ("user", "list_created"), fs=FormatSuggestion("%6i %s", ("account_id", "password")))
    def user_list_created(self, operator):
        ret = []
        for r in operator.get_state():
            # state_type, entity_id, state_data, set_time
            if r['state_type'] == 'new_account_passwd':
                ret.append(r['state_data'])
        return ret

    # user move
    all_commands['user_move'] = Command(
        ("user", "move"), MoveType(), AccountName(), DiskId())
    def user_move(self, operator, accountname, disk_id):
        raise NotImplementedError, "Feel free to implement this function"

    # user password
    all_commands['user_password'] = Command(
        ('user', 'password'), AccountName(), AccountPassword(optional=True))
    def user_password(self, operator, accountname, password=None):
        account = self._get_account(accountname)
        if password is None:
            raise NotImplementedError, \
                  'make_passwd må flyttes fra PosixUser til Account'
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
        ('user', 'posix_create'), AccountName(), GroupName(), PosixShell(default="bash"), DiskId())
    def user_posix_create(self, operator, accountname, dfg=None, shell=None, home=None):
        raise NotImplementedError, "Feel free to implement this function"

    # user posix_delete
    all_commands['user_posix_delete'] = Command(
        ('user', 'posix_delete'), AccountName())
    def user_posix_delete(self, operator, accountname):
        raise NotImplementedError, "Feel free to implement this function"

    # user set_expire
    all_commands['user_set_expire'] = Command(
        ('user', 'set_expire'), AccountName(), Date())
    def user_set_expire(self, operator, accountname, date):
        raise NotImplementedError, "Feel free to implement this function"

    # user set_np_type
    all_commands['user_set_np_type'] = Command(
        ('user', 'set_np_type'), AccountName(), SimpleString(help_ref="string_np_type"))
    def user_set_np_type(self, operator, accountname, np_type):
        raise NotImplementedError, "Feel free to implement this function"

    # user shell
    all_commands['user_shell'] = Command(
        ("user", "shell"), AccountName(), PosixShell(default="bash"))
    def user_shell(self, operator, accountname, shell=None):
        account = self._get_account(accountname, actype="PosixUser")
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
        raise CerebrumError, "unknown shell: %s" % shell
    
    def _get_ou(self, ou_id):  # TBD: ou_id should be a string, how to encode?
        ou = OU_class(Cerebrum)
        ou.clear()
        ou.find(ou_id)
        return ou.entity_id

    def _get_group_opcode(self, operator):
        if operator is None:
            return self.const.group_memberop_union
        if operator == 'union':
            return self.const.group_memberop_union
        raise NotImplementedError, "unknown group opcode: '%s'" % operator

    def _get_person_name(self, person):
        name = None
        for ss in cereconf.PERSON_NAME_SS_ORDER:
            try:
                name = person.get_name(getattr(self.const, ss),
                                       self.const.name_full)
                break
            except Errors.NotFoundError:
                pass
            if name is None:
                try:
                    f = person.get_name(getattr(self.const, ss),
                                        self.const.name_first)
                    l = person.get_name(getattr(self.const, ss),
                                        self.const.name_last)
                    name = "%s %s" % (f, l)
                except Errors.NotFoundError:
                    pass

        if name is None:
            name = "Ukjent"
        return name

    def _get_entity(self, idtype, id):
        if idtype == 'account':
            return self._get_account(id)
        if idtype == 'person':
            return self._get_person(*self._map_person_id(id))
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
        idx = id.find(":")
        id_type = id[:idx]
        id = id[idx+1:]
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
        if type == self.const.entity_account:
            acc = self._get_account(id, idtype='id')
            return acc.account_name
        elif type == self.const.entity_group:
            group = self._get_group(id, idtype='id')
            return group.get_name(self.const.group_namespace)
        else:
            return "%s:%s" % (type, id)

    def _is_yes(self, val):
        val = val.lower()
        if(val == 'y' or val == 'yes' or val == 'ja' or val == 'j'):
            return True
        return False
        
    # TODO: the mapping of user typed description to numeric db-id for
    # codes, and from id -> description should be done in an elegant way
    def _get_affiliationid(self, code_str):
        return self.person_affiliation_codes(code_str)[0]

    def _parse_date(self, date):
        try:
            return self.db.Date(*([ int(x) for x in date.split('-')]))
        except:
            raise CerebrumError, "Illegal date: %s" % date
