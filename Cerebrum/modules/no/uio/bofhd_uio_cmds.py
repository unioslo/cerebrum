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
from Cerebrum.modules import PosixGroup
from Cerebrum.Utils import Factory
from templates.letters import TemplateHandler
from bofhd_errors import CerebrumError
import cereconf
from Cerebrum.modules import PosixUser
import re

# This is just documentation, will be removed:
help = """
group   Gruppe-kommando
           add     user+ gruppe - Melde accounts inn
           gadd    gruppe+ gruppe - Melde grupper inn
           remove  user+ gruppe - Melde accounts ut
           gremove  gruppe+ gruppe - Melde grupper ut
           user    user+ - Liste alle gruppene til en account
           create   - Byggge en ny gruppe
           def     user+ gruppe - Sette default gruppe
           destroy group+ - Sletter gruppen
           info group    - viser litt info om gruppen
           ls group - Liste alle direkte medlemmer i en gruppe
           lsexp group - Liste alle ekspanderte medlemmer i en gruppe
user    Brukerrelaterte kommandoer
           create   - bygge brukere
           passwd  user+ - Sett et tilfeldig passord på brukeren
           info    user - vis info om en bruker
           accounts <idtype> <id> - vis brukernavn for person
           delete   - slette en gitt bruker
           lcreated         - oversikt over byggede brukere
           move    user hvor - Flytte en gitt bruker
           shell   user1 user2 ... shell - Sette loginshell for en bruker
           splatt  user1 user2 ... [-why "begrunnelse"] - Sperrer brukers konto
print   Skriver relaterte kommandoer
           qoff    user+ ... - Skru av kvote på en bruker
           qpq     user+ - Vise informasjon om en brukers skrivekvote
           upq     user tall - Oppdaterer brukerens skriverkvote
person  Personrelaterte kommandoer
           create <display_name> <id_type> <id> - bygger en person
           bcreate <display_name> <birth_date (yyyy-mm-dd)>
"""

class BofhdExtension(object):
    """All CallableFuncs takes user as first arg, and is responsible
    for checking neccesary permissions"""

    all_commands = {}
    OU_class = Factory.get('OU')

    def __init__(self, db):
        self.db = db
        self.person = Person.Person(self.db)
        self.const = self.person.const
        self.name_codes = {}
        for t in self.person.list_person_name_codes():
            self.name_codes[int(t.code)] = t.description
        self.person_affiliation_codes = {}
        for t in self.person.list_person_affiliation_codes():
            self.person_affiliation_codes[t.code_str] = (int(t.code), t.description)

    def get_commands(self, uname):
        # TBD: Do some filtering on uname to remove commands
        commands = {}
        for k in self.all_commands.keys():
            commands[k] = self.all_commands[k].get_struct()
        return commands

    def get_format_suggestion(self, cmd):
        return self.all_commands[cmd].get_fs()

    #
    # group commands
    #

    all_commands['group_add'] = Command(
        ("group", "add"), AccountName(ptype="source", repeat=True),
        GroupName(ptype="destination", repeat=True),
        GroupOperation(optional=True))
    def group_add(self, operator, src_name, dest_group,
                  group_operator=None):
        return self._group_add(operator, src_name, dest_group,
                               group_operator, type="account")

    all_commands['group_gadd'] = Command(("group", "gadd"),
                                        GroupName(ptype="source", repeat=True),
                                        GroupName(ptype="destination", repeat=True),
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

    all_commands['group_remove'] = Command(
        ("group", "remove"), AccountName(ptype="member", repeat=True),
        GroupName(ptype="remove from", repeat=True),
        GroupOperation(optional=True))
    def group_remove(self, operator, src_name, dest_group,
                     group_operator=None):
        return self._group_remove(operator, src_name, dest_group,
                               group_operator, type="account")

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

    all_commands['group_account'] = Command(
        ('group', 'user'), AccountName(), fs=FormatSuggestion(
        "%-9i %i", ("memberop", "group"), hdr="Operation Group id"))
    def group_account(self, operator, accountname):
        account = self._get_account(accountname)
        group = Group.Group(self.db)
        return [{'memberop': r['operation'], 'group': r['group_id']}
                for r in group.list_groups_with_entity(account.entity_id)]

    all_commands['group_create'] = Command(
        ("group", "create"), GroupName(ptype="new"), Description(),
        fs=FormatSuggestion("Created with posixgid: %i", ("group_id",)))
    def group_create(self, operator, groupname, description):
        pg = PosixGroup.PosixGroup(self.db)
        pg.populate(creator_id=operator.get_entity_id(),
                    visibility=self.const.group_visibility_all,
                    name=groupname, description=description)
        try:
            pg.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return {'group_id': int(pg.posix_gid)}

    all_commands['account_def'] = Command(
        ('group', 'def'), AccountName(ptype=""), GroupName(ptype="existing"))
    def account_def(self, operator, accountname, groupname):
        account = self._get_account(accountname)
        raise NotImplementedError, "Feel free to implement this function"

    all_commands['group_destroy'] = Command(
        ("group", "destroy"), GroupName(ptype="existing"))
    def group_destroy(self, operator, groupname):
        raise NotImplementedError, "Feel free to implement this function"

    all_commands['group_info'] = Command(
        ("group", "info"), GroupName(ptype="existing"))
    def group_info(self, operator, groupname):
        raise NotImplementedError, "Feel free to implement this function"

    all_commands['group_list'] = Command(
        ("group", "ls"), GroupName(ptype="existing"),
        fs=FormatSuggestion("%-2s %-5i %i", ("op", "type", "id"),
                            hdr="Op Type  Id"))
    def group_list(self, operator, groupname):
        """List direct members of group"""
        group = self._get_group(groupname)
        ret = []
        u, i, d = group.list_members()
        for r in u:
            ret.append({'op': 'u', 'type': r[0], 'id': r[1]})
        for r in i:
            ret.append({'op': 'i', 'type': r[0], 'id': r[1]})
        for r in d:
            ret.append({'op': 'd', 'type': r[0], 'id': r[1]})
        return ret

    all_commands['group_list_expanded'] = Command(
        ("group", "lsexp"), GroupName(ptype="existing"),
        fs=FormatSuggestion("%i", ("member_id",), hdr="Members ids"))
    def group_list_expanded(self, operator, groupname):
        """List members of group after expansion"""
        group = self._get_group(groupname)
        return [{'member_id': a} for a in group.get_members()]

    #
    # user commands
    #

    ## Enter bdate, fnr or idtype> 130472
    ## <liste med kandidater>
    ## Select person> 4
    ## <klienten må mappe 4 -> person_id e.l.>
    ##
    ## Enter bdate, fnr or idtype> 13047201234
    ## OK
    ##
    ## Enter bdate, fnr or idtype> personid
    ## Enter id> 72
    ## OK

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
                person = self._get_person(person_id, "id")
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

    all_commands['user_create'] = Command(
        ('user', 'create'), prompt_func=user_create_prompt_func,
        fs=FormatSuggestion("Created uid=%i, password=%s", ("uid", "password")))
    def user_create(self, operator, idtype, person_id, filegroup, shell, home, uname):
        person = self._get_person(person_id, "id")
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

    all_commands['account_password'] = Command(
        ('user', 'password'), AccountName(ptype=""), AccountPassword(optional=True))
    def account_password(self, operator, accountname, password=None):
        account = self._get_account(accountname)
        if password is None:
            raise NotImplementedError, \
                  'make_passwd må flyttes fra PosixUser til Account'
        account.set_password(password)
        try:
            account.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        operator.store_state("account_passwd", {'account_id': int(account.entity_id),
                                                'password': password})
        return password

    all_commands['account_info'] = Command(
        ("user", "info"), AccountName(ptype="existing"))
    def account_info(self, operator, accountname):
        raise NotImplementedError, "Feel free to implement this function"

    all_commands['account_accounts'] = Command(("user", "accounts"),
                                         PersonIdType(), PersonId())
    def account_accounts(self, operator, id_type, id):
        raise NotImplementedError, "Feel free to implement this function"

    all_commands['account_delete'] = Command(("user", "delete"),
                                         AccountName(ptype="existing"))
    def account_delete(self, operator, accountname):
        raise NotImplementedError, "Feel free to implement this function"

    all_commands['account_lcreated'] = Command(("user", "lcreated"))
    def account_lcreated(self, operator):
        raise NotImplementedError, "Feel free to implement this function"

    all_commands['account_move'] = Command(
        ("user", "move"), AccountName(ptype="existing"), DiskId())
    def account_move(self, operator, accountname, disk_id):
        raise NotImplementedError, "Feel free to implement this function"

    all_commands['account_shell'] = Command(
        ("user", "shell"), AccountName(ptype="existing"), PosixShell(default="bash"))
    def account_shell(self, operator, accountname, shell=None):
        raise NotImplementedError, "Feel free to implement this function"

    all_commands['account_splatt'] = Command(
        ("user", "splatt"), AccountName(ptype="existing"), Description(prompt="Why"))
    def account_splatt(self, operator, accountname, shell=None):
        raise NotImplementedError, "Feel free to implement this function"

    #
    # printer commands
    #

    all_commands['printer_qoff'] = Command(
        ("print", "qoff"), AccountName(ptype="existing"))
    def printer_qoff(self, operator, accountname):
        raise NotImplementedError, "Feel free to implement this function"

    all_commands['printer_qpq'] = Command(
        ("print", "qpq"), AccountName(ptype="existing"))
    def printer_qpq(self, operator, accountname):
        raise NotImplementedError, "Feel free to implement this function"

    all_commands['printer_upq'] = Command(
        ("print", "upq"), AccountName(ptype="existing"), Description(prompt="# sider"))
    def printer_upq(self, operator, accountname, pages):
        raise NotImplementedError, "Feel free to implement this function"


    #
    # person commands
    #

    all_commands['person_create'] = Command(
        ("person", "create"), PersonName(), PersonIdType(),
        PersonId(), fs=FormatSuggestion("Created: %i",
        ("person_id",)))
    def person_create(self, operator, display_name,
                      id_type=None, id=None):
        return self._person_create(operator, display_name, id_type=id_type, id=id)

    all_commands['person_bcreate'] = Command(
        ("person", "bcreate"), PersonName(), Date(),
        fs=FormatSuggestion("Created: %i", ("person_id",)))
    def person_bcreate(self, operator, display_name, birth_date=None):
        return self._person_create(operator, display_name, birth_date=birth_date)

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

    #
    # misc helper functions.
    # TODO: These should be protected so that they are not remotely callable
    #

    def _get_account(self, id, idtype='name'):
        account = Account.Account(self.db)  # TBD: Flytt denne
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

    def _get_group(self, id, idtype='name'):
        group = Group.Group(self.db)
        try:
            if idtype == 'name':
                group.clear()
                group.find_by_name(id)
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

    def _get_person(self, id, idtype='fnr'):
        person = self.person
        person.clear()
        try:
            if idtype == 'fnr':
                person.find_by_external_id(self.const.externalid_fodselsnr, id)
            elif idtype == 'id':
                person.find(id)
            else:
                raise NotImplementedError, "Unknown idtype: %s" % idtype
        except Errors.NotFoundError:
            raise CerebrumError, "Could not find person with %s=%s" % (idtype, id)
        return person

    def _get_nametypeid(self, nametype):
        if nametype == 'first':
            return self.const.name_first
        elif nametype == 'last':
            return self.const.name_last
        elif nametype == 'full':
            return self.const.name_full
        else:
            raise NotImplementedError, "unkown nametype: %s" % nametye

    # TODO: the mapping of user typed description to numeric db-id for
    # codes, and from id -> description should be done in an elegant way
    def _get_affiliationid(self, code_str):
        return self.person_affiliation_codes(code_str)[0]

    def _parse_date(self, date):
        try:
            return self.db.Date(*([ int(x) for x in date.split('-')]))
        except:
            raise CerebrumError, "Illegal date: %s" % date
