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
import cereconf
from Cerebrum.modules import PosixUser
import re

class BofhdExtension(object):
    """All CallableFuncs takes user as first arg, and is responsible
    for checking neccesary permissions"""

    all_commands = {}

    def __init__(self, db):
        self.Cerebrum = db
        self.person = Person.Person(self.Cerebrum)
        self.const = self.person.const
        self.name_codes = {}
        for t in self.person.get_person_name_codes():
            self.name_codes[int(t.code)] = t.description

    def tab_foobar(self, *args):
        return ["foo", "bar", "gazonk"]

    def prompt_foobar(self, *args):
        return "Enter a joke"

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
    def account_affadd(self, user, accountname, affiliation, ou=None):
        """Add 'affiliation'@'ou' to 'accountname'.  If ou is None,
        try cereconf.default_ou """
        raise NotImplementedError, \
              "Account hasn't implemented affiliations yet"

    ## bofh> account affrem <accountname> <affiliation> <ou=>
    all_commands['account_affrem'] = Command(
        ('account', 'affrem'), AccountName(), Affiliation(), OU())
    def account_affrem(self, user, accountname, affiliation, ou=None):
        """Remove 'affiliation'@'ou' from 'accountname'.  If ou is None,
        try cereconf.default_ou"""
        raise NotImplementedError, \
              "Account hasn't implemented affiliations yet"

    ## bofh> account create <accountname> <idtype> <id> \
    ##         <affiliation=> <ou=> [<expire_date>]
    all_commands['account_create'] = Command(
        ('account', 'create'),
        AccountName(ptype="new"), PersonIdType(), PersonId(),
        Affiliation(default=1), OU(default=1), Date(optional=1),
        fs=FormatSuggestion("Created: %i", ("account_id",)))
    def account_create(self, user, accountname, idtype, id,
                       affiliation=None, ou=None, expire_date=None):
        """Create account 'accountname' belonging to 'idtype':'id'"""
        account = Account.Account(self.Cerebrum)  # TBD: Flytt denne
        account.clear()
        # TBD: set this from user
        account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        creator_id = account.entity_id
        account.clear()
        person = self.person
        person.clear()
        if idtype == 'fnr':
            person.find_by_external_id(self.const.externalid_fodselsnr, id)
        else:
            raise NotImplementedError, "Unknown idtype: %s" % idtype

        account.populate(accountname,
                         self.const.entity_person,  # Owner type
                         person.entity_id,
                         None,
                         creator_id, expire_date)
        account.write_db()
        return {'account_id': account.entity_id}

    ## bofh> account password <accountname> [<password>]
    all_commands['account_password'] = Command(
        ('account', 'password'), AccountName(), AccountPassword(optional=1))
    def account_password(self, user, accountname, password=None):
        """Set account password for 'accountname'.  If password=None,
        set random password.  Returns the set password"""
        account = self._get_account(accountname)
        if password is None:
            raise NotImplementedError, \
                  'make_passwd m� flyttes fra PosixUser til Account'
        account.set_password(password)
        account.write_db()
        return password

    ## bofh> account posix_create <accountname> <prigroup> <home=> \
    ##         <shell=> <gecos=>
    all_commands['account_posix_create'] = Command(
        ('account', 'posix_create'),
        AccountName(ptype="new"), GroupName(ptype="primary"),
        PosixHome(default=1), PosixShell(default=1), PosixGecos(default=1))
    # TODO:  Ettersom posix er optional, flytt denne til en egen fil
    def account_posix_create(self, user, accountname, prigroup, home=None,
                             shell=None, gecos=None):
        """Create a PosixUser for existing 'accountname'"""
        account = self._get_account(accountname)
        group=Group.Group(self.Cerebrum)
        group.find_by_name(prigroup)
        posix_user = PosixUser.PosixUser(self.Cerebrum)
        uid = posix_user.get_free_uid()

        if home is None:
            home = '/home/%s' % accountname
        if shell is None:
            shell = cereconf.default_shell
        posix_user.populate(account.account_id, uid, group.group_id, gecos,
                            home, shell)
        # uname = posix_user.get_name(co.account_namespace)[0][2]
        passwd = posix_user.make_passwd(None)
        posix_user.set_password(passwd)
        posix_user.write_db()

    ## bofh> account type <accountname>
    all_commands['account_type'] = Command(('account', 'type'), AccountName())
    def account_type(self, user, accountname):
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
    def group_account(self, user, accountname):
        """List all groups where 'accountname' is a (direct or
        indirect) member, and type of membership (union, intersection
        or difference)."""
        account = self._get_account(accountname)
        raise (NotImplementedError,
               "Group needs a method to list the groups where an entity is a member")

    ## bofh> group add <entityname+> <groupname+> [<op>]
    all_commands['group_add'] = Command(("group", "add"),
                                        GroupName("source", repeat=1),
                                        GroupName("destination", repeat=1),
                                        GroupOperation(optional=1))
    def group_add(self, user, src_group, dest_group,
                  operator=None):
        """Add group named src to group named dest using specified
        operator"""
        # TODO: I flg utkast til kommando-spec, kan src_group v�re
        # navn p� en entitet som ikke er gruppe
        if operator is None: operator = self.const.group_memberop_union
        if operator == 'union':   # TBD:  Need a way to map to constant
            operator = self.const.group_memberop_union
        group_s = Group.Group(self.Cerebrum)
        group_s.find_by_name(src_group)
        group_d = Group.Group(self.Cerebrum)
        group_d.find_by_name(dest_group)
        group_d.add_member(group_s, operator)
        return "OK"

    ## bofh> group create <name> [<description>]
    all_commands['group_create'] = Command(("group", "create"),
                                           GroupName(ptype="new"),
                                           Description(),
                                           fs=FormatSuggestion("Created: %i",
                                                               ("group_id",)))
    def group_create(self, user, groupname, description):
        """Create the group 'groupname' with 'description'.  Returns
        the new groups id"""

        account = Account.Account(self.Cerebrum)
        account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)  # TODO: current user
        group = Group.Group(self.Cerebrum)
        group.populate(account, self.const.group_visibility_all,
                          groupname, description)
        group.write_db()
        return {'group_id': group.entity_id}

    ## bofh> group delete <name>
    all_commands['group_delete'] = Command(("group", "delete"),
                                           GroupName("existing"))
    def group_delete(self, user, groupname):
        """Deletes the group 'groupname'"""
        raise NotImplementedError, "Feel free to implement this function"

    ## bofh> group expand <groupname>
    all_commands['group_expand'] = Command(("group", "expand"),
                                           GroupName("existing"))
    def group_expand(self, user, groupname):
        """Do full group expansion; list resulting members and their
        entity types."""
        raise NotImplementedError, "Feel free to implement this function"

    ## bofh> group expire <name> <yyyy-mm-dd>
    all_commands['group_expire'] = Command(("group", "expire"),
                                           GroupName("existing"), Date())
    def group_expire(self, user, groupname, date):
        """Set group expiration date for 'groupname' to 'date'"""
        group = self._get_group(groupname)
        group.expire_date = self.Cerebrum.Date(*([
            int(x) for x in date.split('-')]))
        group.write_db()

    ## bofh> group group <groupname>
    all_commands['group_group'] = Command(("group", "group"),
                                          GroupName("existing"))
    def group_group(self, user, groupname):
        """List all groups where 'groupname' is a (direct or
        indirect) member, and type of membership (union, intersection
        or difference)."""
        raise NotImplementedError, "Feel free to implement this function"

    ## bofh> group info <name>
    all_commands['group_info'] = Command(("group", "info"),
                                         GroupName("existing"))
    def group_info(self, user, groupname):
        """Returns some info about 'groupname'"""
        raise NotImplementedError, "Feel free to implement this function"

    ## bofh> group list <groupname>
    all_commands['group_list'] = Command(("group", "list"),
                                         GroupName("existing"))
    def group_list(self, user, groupname):
        """List direct members of group (with their entity types), in
        categories coresponding to the three membership ops.  """
        group = self._get_group(groupname)
        return group.get_members()

    ## bofh> group person <person_id>
    all_commands['group_person'] = Command(("group", "person"),
                                           GroupName("existing"))
    def group_person(self, user, personid):
        """List all groups where 'personid' is a (direct or
        indirect) member, and type of membership (union, intersection
        or difference)."""
        raise NotImplementedError, "Feel free to implement this function"

    ## bofh> group remove <entityname+> <groupname+> [<op>]
    # TODO: "entityname" er litt vagt, skal man gjette entitytype?
    all_commands['group_remove'] = Command(("group", "remove"),
                                           EntityName(repeat=1),
                                           GroupName("existing", repeat=1),
                                           GroupOperation(optional=1))
    def group_remove(self, user, entityname, groupname, op=None):
        """Remove 'entityname' from 'groupname' using specified
        operator"""
        raise NotImplementedError, "Feel free to implement this function"

    ## bofh> group visibility <name> <visibility>
    all_commands['group_visibility'] = Command(("group", "visibility"),
                                               GroupName("existing"),
                                               GroupVisibility())
    def group_visibility(self, user, groupname, visibility):
        """Change 'groupname's visibility to 'visibility'"""
        raise NotImplementedError, "What format should visibility have?"
        group = self._get_group(groupname)
        group.visibility = visibility
        group.write_db()

    #
    # person commands
    #

    ## bofh> person affadd <idtype> <id+> <affiliation> [<status> [<ou>]]
    all_commands['person_affadd'] = Command(
        ("person", "affadd"),
        PersonIdType(), PersonId(repeat=1), Affiliation(),
        AffiliationStatus(default=1), OU(default=1))
    def person_affadd(self, user, idtype, id, affiliation, status=None, ou=None):
        """Add 'affiliation'@'ou' with 'status' to person with
        'idtype'='id'.  Changes the affiliationstatus if person
        already has an affiliation at the destination"""
        raise NotImplementedError, "Feel free to implement this function"

    ## bofh> person afflist <idtype> <id>
    all_commands['person_afflist'] = Command(
        ("person", "afflist"), PersonIdType(), PersonId(repeat=1))
    def person_afflist(self, user, idtype, id):
        """Return all affiliations for person with 'idtype'='id'"""
        raise NotImplementedError, "Feel free to implement this function"

    ## bofh> person affrem <idtype> <id> <affiliation> [<ou>]
    all_commands['person_affrem'] = Command(("person", "affrem"),
                                            PersonIdType(), PersonId(repeat=1),
                                            Affiliation(), OU(default=1))
    def person_affrem(self, user, idtype, id, affiliation, ou):
        """Add 'affiliation'@'ou' with 'status' to person with 'idtype'='id'"""
        raise NotImplementedError, "Feel free to implement this function"

    ## bofh> person create <display_name> \
    ##         {<birth_date (yyyy-mm-dd)> | <id_type> <id>}
    all_commands['person_create'] = Command(
        ("person", "create"),
        PersonName(), Date(optional=1), PersonIdType(), PersonId(),
        fs=FormatSuggestion("Created: %i", ("person_id",)))
    def person_create(self, user, display_name, birth_date=None,
                      id_type=None, id=None):
        """Call to manually add a person to the database.  Created
        person-id is returned"""
        person = self.person
        person.clear()
        date = None
        if birth_date is not None:
            date = self.Cerebrum.Date(*([
                int(x) for x in birth_date.split('-')]))
        person.populate(date, self.const.gender_male,
                        description='Manualy created')
        # TDB: new constants
        person.affect_names(self.const.system_manual, self.const.name_full)
        person.populate_name(self.const.name_full,
                             display_name.encode('iso8859-1'))
        if id_type is not None:
            if id_type == 'fnr':
                person.populate_external_id(self.const.system_manual,
                                            self.const.externalid_fodselsnr,
                                            id)
        person.write_db()
        return {'person_id': person.entity_id}

    ## bofh> person delete <id_type> <id>
    all_commands['person_delete'] = Command(("person", "delete"),
                                            PersonIdType(), PersonId(repeat=1))
    def person_delete(self, user, idtype, id):
        """Remove person.  Don't do anything if there are data
        (accounts, affiliations, etc.) associatied with the person."""
        raise NotImplementedError, "Feel free to implement this function"

    ## bofh> person find {<name> | <id> [<id_type>] | <birth_date>}
    all_commands['person_find'] = Command(
        ("person", "find") ,
        Id(), PersonIdType(optional=1),
        fs=FormatSuggestion("%-15s%-30s%-10s", ("export_id", "name", "bdate"),
                            hdr="%-15s%-30s%-10s" % ("ExportID", "Name",
                                                     "Birthdate")))
    def person_find(self, user, key, keytype=None):
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
        "Navn     : %20s\nF�dt     : %20s\nKj�nn    : %20s\n"
        "person id: %20d\nExport-id: %20s",
        ("name", "birth", "gender", "pid", "expid")))
    # TBD:  Should add a generic _get_person(idtype, id) method
    def person_info(self, user, idtype, id):
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
                                          PersonNameType(), PersonName(),
                                          fs=FormatSuggestion("OK", []))
    def person_name(self, user, idtype, id, nametype, name):
        """Set name of 'nametype' to 'name' for person with 'idtype'='id'"""
        person = self._get_person(id, idtype)
        nametypeid = self._get_nametypeid(nametype)
        person.affect_names(self.const.system_manual, nametypeid)
        person.populate_name(nametypeid, name)
        person.write_db()
        return 1

    #
    # misc helper functions.
    # TODO: These should be protected so that they are not remotely callable

    def _get_account(self, id, idtype='name'):
        account = Account.Account(self.Cerebrum)  # TBD: Flytt denne
        if idtype == 'name':
            account.clear()
            account.find_by_name(id, self.const.account_namespace)
        else:
            raise NotImplementedError, "unknown idtype: '%s'" % idtype
        return account

    def _get_group(self, id, idtype='name'):
        group = Group.Group(self.Cerebrum)
        if idtype == 'name':
            group.clear()
            group.find_by_name(id)
        else:
            raise NotImplementedError, "unknown idtype: '%s'" % idtype

        return group

    def _get_person_name(self, person):
        name = None
        for ss in cereconf.PERSON_NAME_SS_ORDER:
            try:
                name = person.get_name(getattr(self.const, ss), self.const.name_full)
                break
            except Errors.NotFoundError:
                pass
            if name is None:
                try:
                    f = person.get_name(getattr(self.const, ss), self.const.name_first)
                    l = person.get_name(getattr(self.const, ss), self.const.name_last)
                    name = "%s %s" % (f, l)
                except Errors.NotFoundError:
                    pass

        if name is None:
            name = "Ukjent"
        return name

    def _get_person(self, id, idtype='fnr'):
        person = self.person
        person.clear()
        if idtype == 'fnr':
            person.find_by_external_id(self.const.externalid_fodselsnr, id)
        else:
            raise NotImplementedError, "Unknown idtype: %s" % idtype
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
