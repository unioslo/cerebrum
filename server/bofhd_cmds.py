# Copyright 2002, 2003 University of Oslo, Norway
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

from cmd_param import *
from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum import Group
from Cerebrum import Person
from templates.letters import TemplateHandler
from bofhd_errors import CerebrumError
import cereconf
from Cerebrum.modules import PosixUser
import re

class BofhdExtension(object):
    """All CallableFuncs takes user as first arg, and is responsible
    for checking neccesary permissions"""

    all_commands = {}
    OU_class = Factory.get('OU')

    def __init__(self, db):
        self.Cerebrum = db
        self.person = Person.Person(self.Cerebrum)
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
    # account commands
    #

    ## bofh> account affadd <accountname> <affiliation> <ou=>
    all_commands['account_affadd'] = Command(
        ('account', 'affadd'), AccountName(), Affiliation(), OU())
    def account_affadd(self, operator, accountname, affiliation, ou=None):
        """Add 'affiliation'@'ou' to 'accountname'.  If ou is None,
        try cereconf.default_ou """
        acc = self._get_account(accountname)
        if ou is None:
            ou = cereconf.DEFAULT_OU
        ou = self._get_ou(ou)
        aff = self._get_affiliationid(affiliation)
        acc.add_account_type(self.owner_id, ou.ou_id, aff)

    ## bofh> account affrem <accountname> <affiliation> <ou=>
    all_commands['account_affrem'] = Command(
        ('account', 'affrem'), AccountName(), Affiliation(), OU())
    def account_affrem(self, operator, accountname, affiliation, ou=None):
        """Remove 'affiliation'@'ou' from 'accountname'.  If ou is None,
        try cereconf.default_ou"""
        acc = self._get_account(accountname)
        if ou is None:
            ou = cereconf.DEFAULT_OU
        ou = self._get_ou(ou)
        aff = self._get_affiliationid(affiliation)
        acc.del_account_type(self.owner_id, ou.ou_id, aff)

    ## bofh> account create <accountname> <idtype> <id> \
    ##         <affiliation=> <ou=> [<expire_date>]
    all_commands['account_create'] = Command(
        ('account', 'create'),
        AccountName(ptype="new"), PersonIdType(), PersonId(),
        Affiliation(default="True"), OU(default="True"), Date(optional=True),
        fs=FormatSuggestion("Created with id: %i", ("account_id",)))
    def account_create(self, operator, accountname, idtype, id,
                       affiliation=None, ou=None, expire_date=None):
        """Create account 'accountname' belonging to 'idtype':'id'"""
        account = account = Account.Account(self.Cerebrum)
        account.clear()
        person = self._get_person(id, idtype)
        account.populate(accountname,
                         self.const.entity_person,  # Owner type
                         person.entity_id,
                         None,
                         operator, expire_date)
        try:
            account.write_db()
        except self.Cerebrum.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return {'account_id': account.entity_id}

    ## bofh> account password <accountname> [<password>]
    all_commands['account_password'] = Command(
        ('account', 'password'), AccountName(ptype=""), AccountPassword(optional=True))
    def account_password(self, operator, accountname, password=None):
        """Set account password for 'accountname'.  If password=None,
        set random password.  Returns the set password"""
        account = self._get_account(accountname)
        if password is None:
            raise NotImplementedError, \
                  'make_passwd må flyttes fra PosixUser til Account'
        account.set_password(password)
        try:
            account.write_db()
        except self.Cerebrum.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        operator.store_state("account_passwd", {'account_id': int(account.entity_id),
                                                'password': password})
        return password

    ## bofh> account posix_create <accountname> <prigroup> <home=> \
    ##         <shell=> <gecos=>
    def default_posix_create_home(self, operator, accountname, prigroup):
        return '/home/%s' % accountname
    all_commands['account_posix_create'] = Command(
        ('account', 'posix_create'),
        AccountName(ptype="existing"), GroupName(ptype="primary"),
        PosixHome(default=default_posix_create_home), PosixShell(default="bash"),
        PosixGecos(default="foobar"),
        fs=FormatSuggestion("Created with password: %s", ("password", )))
    # TODO:  Ettersom posix er optional, flytt denne til en egen fil
    def account_posix_create(self, operator, accountname, prigroup, home,
                             shell=None, gecos=None):
        """Create a PosixUser for existing 'accountname'"""
        account = self._get_account(accountname)
        group=self._get_group(prigroup)
        posix_user = PosixUser.PosixUser(self.Cerebrum)
        uid = posix_user.get_free_uid()

        if shell == 'bash':
            shell = self.const.posix_shell_bash
        disk_id = None
        try:
            host = None
            if home.find(":") != -1:
                host, path = home.split(":")
            else:
                path = home
            disk = Disk.Disk(self.Cerebrum)
            disk.find_by_path(path, host)
            home = None
            disk_id = disk.entity_id
        except Errors.NotFoundError:
            pass
        except Errors.TooManyRowsError:
            raise CerebrumError, "The home path is not unique in the Disks table"
        posix_user.clear()
        posix_user.populate(uid, group.entity_id, gecos,
                            home, shell, disk_id=disk_id, parent=account)
        # uname = posix_user.get_name(co.account_namespace)[0][2]
        passwd = posix_user.make_passwd(None)
        posix_user.set_password(passwd)
        try: 
            posix_user.write_db()
        except self.Cerebrum.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        operator.store_state("new_account_passwd", {'account_id': int(account.entity_id),
                                                    'password': passwd})
        return {'password': passwd}

    ## bofh> account type <accountname>
    all_commands['account_type'] = Command(('account', 'type'), AccountName())
    def account_type(self, operator, accountname):
        """Return a tuple-of-tuples with information on affiliations
        for 'accountname' where the inner tuples has the format
        (affiliation, status, ou)"""
        raise NotImplementedError, \
              "Account hasn't implemented affiliations yet"

    #
    # group commands
    #

    ## bofh> group account <accountname>
    all_commands['group_account'] = Command(('group', 'account'),
                                            AccountName())
    def group_account(self, operator, accountname):
        """List all groups where 'accountname' is a (direct or
        indirect) member, and type of membership (union, intersection
        or difference)."""
        account = self._get_account(accountname)
        raise (NotImplementedError,
               "Group needs a method to list the groups where an"
               " entity is a member")

    ## bofh> group add <accountname+> <groupname+> [<op>]
    all_commands['group_add'] = Command(("group", "add"),
                                        AccountName(ptype="source", repeat=True),
                                        GroupName(ptype="destination", repeat=True),
                                        GroupOperation(optional=True))
    def group_add(self, operator, src_name, dest_group,
                  group_operator=None):
        return self._group_add(operator, src_name, dest_group,
                               group_operator, type="account")

    ## bofh> group gadd <groupname+> <groupname+> [<op>]
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
        """Add entity named src to group named dest using specified
        operator"""
        group_operator = self._get_group_opcode(group_operator)
        group_s = account_s = None
        if type == "group":
            src_entity = self._get_group(src_name)
        elif type == "account":
            src_entity = self._get_account(src_name)
        group_d = self._get_group(dest_group)
        try: 
            group_d.add_member(src_entity, group_operator)
        except self.Cerebrum.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return "OK"

    ## bofh> group create <name> [<description>]
    all_commands['group_create'] = Command(("group", "create"),
                                           GroupName(ptype="new"),
                                           Description(),
                                           fs=FormatSuggestion("Created: %i",
                                                               ("group_id",)))
    def group_create(self, operator, groupname, description):
        """Create the group 'groupname' with 'description'.  Returns
        the new groups id"""

        group = Group.Group(self.Cerebrum)
        group.populate(operator, self.const.group_visibility_all,
                          groupname, description)
        try: 
            group.write_db()
        except self.Cerebrum.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return {'group_id': group.entity_id}

    ## bofh> group delete <name>
    all_commands['group_delete'] = Command(("group", "delete"),
                                           GroupName(ptype="existing"))
    def group_delete(self, operator, groupname):
        """Deletes the group 'groupname'"""
        raise NotImplementedError, "Feel free to implement this function"

    ## bofh> group expand <groupname>
    all_commands['group_expand'] = Command(("group", "expand"),
                                           GroupName(ptype="existing"))
    def group_expand(self, operator, groupname):
        """Do full group expansion; list resulting members and their
        entity types."""
        raise NotImplementedError, "Feel free to implement this function"

    ## bofh> group expire <name> <yyyy-mm-dd>
    all_commands['group_expire'] = Command(("group", "expire"),
                                           GroupName(ptype="existing"), Date())
    def group_expire(self, operator, groupname, date):
        """Set group expiration date for 'groupname' to 'date'"""
        group = self._get_group(groupname)
        group.expire_date = self._parse_date(date)
        try:
            group.write_db()
        except self.Cerebrum.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m

    ## bofh> group group <groupname>
    all_commands['group_group'] = Command(("group", "group"),
                                          GroupName(ptype="existing"))
    def group_group(self, operator, groupname):
        """List all groups where 'groupname' is a (direct or
        indirect) member, and type of membership (union, intersection
        or difference)."""
        raise NotImplementedError, "Feel free to implement this function"

    ## bofh> group info <name>
    all_commands['group_info'] = Command(("group", "info"),
                                         GroupName(ptype="existing"))
    def group_info(self, operator, groupname):
        """Returns some info about 'groupname'"""
        raise NotImplementedError, "Feel free to implement this function"

    ## bofh> group list <groupname>
    all_commands['group_list'] = Command(
        ("group", "list"), GroupName(ptype="existing"),
        fs=FormatSuggestion("%i", ("member_id",), hdr="Members ids"))
    def group_list(self, operator, groupname):
        """List direct members of group (with their entity types), in
        categories coresponding to the three membership ops.  """
        
        group = self._get_group(groupname)
        return [{'member_id': a} for a in group.get_members()]

    ## bofh> group person <person_id>
    all_commands['group_person'] = Command(("group", "person"),
                                           GroupName(ptype="existing"))
    def group_person(self, operator, personid):
        """List all groups where 'personid' is a (direct or
        indirect) member, and type of membership (union, intersection
        or difference)."""
        raise NotImplementedError, "Feel free to implement this function"

    ## bofh> group remove <accountname+> <groupname+> [<op>]
    all_commands['group_remove'] = Command(("group", "remove"),
                                           AccountName(ptype="member", repeat=True),
                                           GroupName(ptype="remove from", repeat=True),
                                           GroupOperation(optional=True))
    def group_remove(self, operator, src_name, dest_group,
                     group_operator=None):
        """Remove 'acountname' from 'groupname' using specified
        operator"""
        return self._group_remove(operator, src_name, dest_group,
                               group_operator, type="account")

    ## bofh> group gremove <accountname+> <groupname+> [<op>]
    all_commands['group_gremove'] = Command(("group", "gremove"),
                                            GroupName(ptype="member", repeat=True),
                                            GroupName(ptype="remove from", repeat=True),
                                            GroupOperation(optional=True))
    def group_gremove(self, operator, src_name, dest_group,
                      group_operator=None):
        """Remove 'groupname' from 'groupname' using specified
        operator"""
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
            group_d.remove_member(src_entity, group_operator)
        except self.Cerebrum.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return "OK"   # TBD: returns OK if user is not member of group.  correct?
        
    ## bofh> group visibility <name> <visibility>
    all_commands['group_visibility'] = Command(("group", "visibility"),
                                               GroupName(ptype="existing"),
                                               GroupVisibility())
    def group_visibility(self, operator, groupname, visibility):
        """Change 'groupname's visibility to 'visibility'"""
        raise NotImplementedError, "What format should visibility have?"
        group = self._get_group(groupname)
        group.visibility = visibility
        try:
            group.write_db()
        except self.Cerebrum.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m

    #
    # person commands
    #

    ## bofh> person affadd <idtype> <id+> <affiliation> [<status> [<ou>]]
    all_commands['person_affadd'] = Command(
        ("person", "affadd"),
        PersonIdType(), PersonId(repeat=True), Affiliation(),
        AffiliationStatus(default="True"), OU(default="True"))
    def person_affadd(self, operator, idtype, id, affiliation,
                      status=None, ou=None):
        """Add 'affiliation'@'ou' with 'status' to person with
        'idtype'='id'.  Changes the affiliationstatus if person
        already has an affiliation at the destination"""
        raise NotImplementedError, "Feel free to implement this function"

    ## bofh> person afflist <idtype> <id>
    all_commands['person_afflist'] = Command(
        ("person", "afflist"), PersonIdType(), PersonId(repeat=True))
    def person_afflist(self, operator, idtype, id):
        """Return all affiliations for person with 'idtype'='id'"""
        raise NotImplementedError, "Feel free to implement this function"

    ## bofh> person affrem <idtype> <id> <affiliation> [<ou>]
    all_commands['person_affrem'] = Command(("person", "affrem"),
                                            PersonIdType(),
                                            PersonId(repeat=True),
                                            Affiliation(), OU(default="True"))
    def person_affrem(self, operator, idtype, id, affiliation, ou):
        """Add 'affiliation'@'ou' with 'status' to person with 'idtype'='id'"""
        raise NotImplementedError, "Feel free to implement this function"

    ## bofh> person create <display_name> <id_type> <id>
    all_commands['person_create'] = Command(
        ("person", "create"),
        PersonName(), PersonIdType(), PersonId(),
        fs=FormatSuggestion("Created: %i", ("person_id",)))
    def person_create(self, operator, display_name, 
                      id_type=None, id=None):
        return self._person_create(operator, display_name, id_type=id_type, id=id)
        
    ## bofh> person bcreate <display_name> <birth_date (yyyy-mm-dd)>
    all_commands['person_bcreate'] = Command(
        ("person", "bcreate"),
        PersonName(), Date(),
        fs=FormatSuggestion("Created: %i", ("person_id",)))
    def person_bcreate(self, operator, display_name, birth_date=None):
        return self._person_create(operator, display_name, birth_date=birth_date)

    def _person_create(self, operator, display_name, birth_date=None,
                      id_type=None, id=None):
        """Call to manually add a person to the database.  Created
        person-id is returned"""
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
        except self.Cerebrum.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return {'person_id': person.entity_id}

    ## bofh> person delete <id_type> <id>
    all_commands['person_delete'] = Command(("person", "delete"),
                                            PersonIdType(),
                                            PersonId(repeat=True))
    def person_delete(self, operator, idtype, id):
        """Remove person.  Don't do anything if there are data
        (accounts, affiliations, etc.) associatied with the person."""
        raise NotImplementedError, "Feel free to implement this function"

    ## bofh> person find {<name> | <id> [<id_type>] | <birth_date>}
    all_commands['person_find'] = Command(
        ("person", "find") ,
        Id(), PersonIdType(optional=True),
        fs=FormatSuggestion("%-15s%-30s%-10s", ("export_id", "name", "bdate"),
                            hdr="%-15s%-30s%-10s" % ("ExportID", "Name",
                                                     "Birthdate")))
    def person_find(self, operator, key, keytype=None):
        """Search for person with 'key'.  If keytype is not set, it is
        assumed to be a date on the format YYYY-MM-DD, or a name"""
        personids = ()
        person = self.person
        person.clear()
        if keytype is None:  # Is name or date (YYYY-MM-DD)
            m = re.match(r'(\d{4})-(\d{2})-(\d{2})', key)
            if m is not None:
                # dato sok
                personids = person.find_persons_by_bdate(key)
            else:
                # navn sok
                raise NotImplementedError, \
                      "Feel free to implement this function"
        else:
            raise NotImplementedError, "What keytypes do exist?"
        ret = ()
        for p in personids:
            person.clear()
            person.find(p.person_id)
            name = self._get_person_name(person)
            ret = ret + ({'export_id' : person.export_id, 'name' : name,
                          'bdate': str(person.birth_date)},)
        return ret

    ## bofh> person info <idtype> <id>
    all_commands['person_info'] = Command(("person", "info"), PersonIdType(),
                                          PersonId(), fs=FormatSuggestion(
        "Navn     : %20s\nFødt     : %20s\nKjønn    : %20s\n"
        "person id: %20d\nExport-id: %20s",
        ("name", "birth", "gender", "pid", "expid")))
    def person_info(self, operator, idtype, id):
        """Returns some info on person with 'idtype'='id'"""
        person = self._get_person(id, idtype)
        name = self._get_person_name(person)
        return {'name': name, 'pid': person.entity_id,
                'expid': person.export_id, 'birth': str(person.birth_date),
                'gender': str(self.const.map_const(person.gender)),
                'dead': person.deceased, 'desc': person.description or ''}

    ## bofh> person name <id_type> {<export_id> | <fnr>} <name_type> <name>
    all_commands['person_name'] = Command(("person", "name"),
                                          PersonIdType(), PersonId(),
                                          PersonNameType(), PersonName())
    def person_name(self, operator, idtype, id, nametype, name):
        """Set name of 'nametype' to 'name' for person with 'idtype'='id'"""
        person = self._get_person(id, idtype)
        nametypeid = self._get_nametypeid(nametype)
        person.affect_names(self.const.system_manual, nametypeid)
        person.populate_name(nametypeid, name)
        try:
            person.write_db()
        except self.Cerebrum.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m           
        return "OK"

    ## bofh> misc pprint <printer> <template=>
    all_commands['misc_pprint'] = Command(
        ("misc", "pprint"), SimpleString(ptype="printername"),
        SimpleString(ptype="template", default="True"))
    def misc_pprint(self, operator, printer, template='new_password',
                    lang='no', type='ps'):
        """Print password sheets"""
        ret = []
        tpl = TemplateHandler(lang, template, type)
        n = 1
        for x in operator.get_state():
            if x['state_type'] == 'account_passwd':
                dta = x['state_data']
                # TODO: Should send this to printer
                ret.append('/tmp/out.%i.ps' % n)
                n += 1
                f = open(ret[-1], 'w')
                # TODO:  probably want to extract more data
                f.write(tpl.apply_template(
                    'body', {'theusername': dta['account_id'],
                             'thepassword': dta['password']}))
                f.close()
        return str(ret)

    #
    # misc helper functions.
    # TODO: These should be protected so that they are not remotely callable

    def _get_account(self, id, idtype='name'):
        account = Account.Account(self.Cerebrum)  # TBD: Flytt denne
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
        group = Group.Group(self.Cerebrum)
        try:
            if idtype == 'name':
                group.clear()
                group.find_by_name(id)
            else:
                raise NotImplementedError, "unknown idtype: '%s'" % idtype
        except Errors.NotFoundError:
            raise CerebrumError, "Could not find group with %s=%s" % (idtype, id)
        return group

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
            return self.Cerebrum.Date(*([ int(x) for x in date.split('-')]))
        except:
            raise CerebrumError, "Illegal date: %s" % date
