# #!/usr/bin/env python2.2

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

    all_commands = {
        ## bofh> account affadd <accountname> <affiliation> <ou=>
        'account_affadd': Command(('account', 'affadd'),
                                  AccountName(), Affiliation(), OU()),
        ## bofh> account affrem <accountname> <affiliation> <ou=>
        'account_affrem': Command(('account', 'affrem'),
                                  AccountName(), Affiliation(), OU()),
        ## bofh> account create <accountname> <idtype> <id> <affiliation=> <ou=> [<expire_date>]
        'account_create': Command(('account', 'create'),
                                  AccountName(ptype="new"),
                                  PersonIdType(), PersonId(),
                                  Affiliation(default=1),
                                  OU(default=1), Date(optional=1),
                                  fs=FormatSuggestion("Created: %i",
                                                   ("account_id",))),
        ## bofh> account password <accountname> [<password>]
        'account_password': Command(('account', 'password'),
                                  AccountName(), AccountPassword(optional=1)),
        ## bofh> account posix_create <accountname> <prigroup> <home=> <shell=> <gecos=>
        'account_posix_create': Command(('account', 'posix_create'),
                                        AccountName(ptype="new"), GroupName(ptype="primary"),
                                        PosixHome(default=1),
                                        PosixShell(default=1),
                                        PosixGecos(default=1)),
        ## bofh> account type <accountname>
        'account_type': Command(('account', 'type'), AccountName()),
        ## bofh> group account <accountname>
        'group_account': Command(('group', 'account'), AccountName()),
        ## bofh> group add <entityname+> <groupname+> [<op>]
        'group_add': Command(("group", "add"), GroupName("source", repeat=1),
                             GroupName("destination", repeat=1),
                             GroupOperation(optional=1)),
        ## bofh> group create <name> [<description>]
        'group_create': Command(("group", "create"), GroupName(ptype="new"), Description(),
                                fs=FormatSuggestion("Created: %i",("group_id",))),
        ## bofh> group delete <name>
        'group_delete': Command(("group", "delete"), GroupName("existing")),
        ## bofh> group expand <groupname>
        'group_expand': Command(("group", "expand"), GroupName("existing")),
        ## bofh> group expire <name> <yyyy-mm-dd>
        'group_expire': Command(("group", "expire"), GroupName("existing"), Date()),
        ## bofh> group group <groupname>
        'group_group': Command(("group", "group"), GroupName("existing")),
        ## bofh> group info <name>
        'group_info': Command(("group", "info"), GroupName("existing")),
        ## bofh> group list <groupname>
        'group_list': Command(("group", "list"), GroupName("existing")),
        ## bofh> group person <person_id>
        'group_person': Command(("group", "person"), GroupName("existing")),
        ## bofh> group remove <entityname+> <groupname+> [<op>]
        # TODO: "entityname" er litt vagt, skal man gjette entitytype?
        'group_remove': Command(("group", "remove"),
                                EntityName(repeat=1), GroupName("existing", repeat=1),
                                GroupOperation(optional=1)),
        ## bofh> group visibility <name> <visibility>
        'group_visibility': Command(("group", "visibility"),
                                    GroupName("existing"), GroupVisibility()),
        ## bofh> person affadd <idtype> <id+> <affiliation> [<status> [<ou>]]
        'person_affadd': Command(("person", "affadd"), PersonIdType(),
                                 PersonId(repeat=1), Affiliation(),
                                 AffiliationStatus(default=1), OU(default=1)),
        ## bofh> person afflist <idtype> <id>
        'person_afflist': Command(("person", "afflist"), PersonIdType(),
                                 PersonId(repeat=1)),
        ## bofh> person affrem <idtype> <id> <affiliation> [<ou>]
        'person_affrem': Command(("person", "affrem"), PersonIdType(),
                                 PersonId(repeat=1), Affiliation(),
                                 OU(default=1)),
        ## bofh> person create <display_name> {<birth_date (yyyy-mm-dd)> | <id_type> <id>}
        'person_create': Command(("person", "create"), PersonName(),
                                 Date(optional=1), PersonIdType(),
                                 PersonId(),
                                  fs=FormatSuggestion("Created: %i",
                                                   ("person_id",))),
        ## bofh> person delete <id_type> <id>
        'person_delete': Command(("person", "delete"), PersonIdType(),
                                 PersonId(repeat=1)),
        ## bofh> person find {<name> | <id> [<id_type>] | <birth_date>}
        'person_find': Command(("person", "find") , Id(),
                               PersonIdType(optional=1),
                               fs=FormatSuggestion("%-15s%-30s%-10s",
                                                   ("export_id", "name", "bdate"),
                                                   hdr="%-15s%-30s%-10s" %
                                                   ("ExportID", "Name", "Birthdate"))),
        ## bofh> person info <idtype> <id>
        'person_info': Command(("person", "info"), PersonIdType(),
                               PersonId(), fs=FormatSuggestion(
        "Navn     : %20s\nFødt     : %20s\nKjønn    : %20s\n"
        "person id: %20d\nExport-id: %20s",
        ("name", "birth", "gender", "pid", "expid"))),
        ## bofh> person name <id_type> {<export_id> | <fnr>} <name_type> <name>
        'person_name': Command(("person", "name"), PersonIdType(),
                               PersonId(), PersonNameType(), PersonName(),
                               fs=FormatSuggestion("OK", []))
        }

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

    def account_affadd(self, user, accountname, affiliation, ou=None):
        """Add 'affiliation'@'ou' to 'accountname'.  If ou is None,
        try cereconf.default_ou """
        raise NotImplementedError, "Account hasn't implemented affiliations yet"

    def account_affrem(self, user, accountname, affiliation, ou=None):
        """Remove 'affiliation'@'ou' from 'accountname'.  If ou is None,
        try cereconf.default_ou"""
        raise NotImplementedError, "Account hasn't implemented affiliations yet"

    def account_create(self, user, accountname, idtype, id,
                       affiliation=None, ou=None, expire_date=None):
        """Create account 'accountname' belonging to 'idtype':'id'"""
        account = Account.Account(self.Cerebrum)  # TBD: Flytt denne
        account.clear()
        account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)  # TBD: set this from user
        creator_id = account.entity_id
        account.clear()
        person = self.person
        person.clear()
        if idtype == 'fnr':
            person.find_by_external_id(self.const.externalid_fodselsnr, id)
        else:
            raise NotImplemetedError, "Unknown idtype: %s" % idtype
        
        account.populate(accountname,
                         self.const.entity_person,  # Owner type
                         person.entity_id,
                         None, 
                         creator_id, expire_date)
        account.write_db()
        return {'account_id': account.entity_id}

    def account_password(self, user, accountname, password=None):
        """Set account password for 'accountname'.  If password=None,
        set random password.  Returns the set password"""
        account = self._get_account(accountname)
        if password is None:
            raise NotImplementedError, 'make_passwd må flyttes fra PosixUser til Account'
        account.set_password(password)
        account.write_db()
        return password

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

    def account_type(self, user, accountname):
        """Return a tuple-of-tuples with information on affiliations
        for 'accountname' where the inner tuples has the format
        (affiliation, status, ou)"""
        raise NotImplementedError, "Account hasn't implemented affiliations yet"

    #
    # group commands
    #

    def group_account(self, user, accountname):
        """List all groups where 'accountname' is a (direct or
        indirect) member, and type of membership (union, intersection
        or difference)."""
        account = self._get_account(accountname)
        raise (NotImplemetedError,
               "Group needs a method to list the groups where an entity is a member")

    def group_add(self, user, src_group, dest_group,
                  operator=None):
        """Add group named src to group named dest using specified
        operator"""
        # TODO: I flg utkast til kommando-spec, kan src_group være
        # navn på en entitet som ikke er gruppe
        if operator is None: operator = self.const.group_memberop_union
        if operator == 'union':   # TBD:  Need a way to map to constant
            operator = self.const.group_memberop_union
        group_s = Group.Group(self.Cerebrum)
        group_s.find_by_name(src_group)
        group_d = Group.Group(self.Cerebrum)
        group_d.find_by_name(dest_group)
        group_d.add_member(group_s, operator)
        return "OK"

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
    
    def group_delete(self, user, groupname):
        """Deletes the group 'groupname'"""
        raise NotImplemetedError, "Feel free to implement this function"
    
    def group_expand(self, user, groupname):
        """Do full group expansion; list resulting members and their
        entity types."""
        raise NotImplemetedError, "Feel free to implement this function"
    
    def group_expire(self, user, groupname, date):
        """Set group expiration date for 'groupname' to 'date'"""
        group = self._get_group(groupname)
        group.expire_date = self.Cerebrum.Date(*([int(x) for x in date.split('-')]))
        group.write_db()
    
    def group_group(self, user, groupname):
        """List all groups where 'groupname' is a (direct or
        indirect) member, and type of membership (union, intersection
        or difference)."""        
        raise NotImplemetedError, "Feel free to implement this function"
    
    def group_info(self, user, groupname):
        """Returns some info about 'groupname'"""
        raise NotImplemetedError, "Feel free to implement this function"
    
    def group_list(self, user, groupname):
        """List direct members of group (with their entity types), in
        categories coresponding to the three membership ops.  """
        group = self._get_group(groupname)
        return group.get_members()
    
    def group_person(self, user, personid):
        """List all groups where 'personid' is a (direct or
        indirect) member, and type of membership (union, intersection
        or difference)."""        
        raise NotImplemetedError, "Feel free to implement this function"
    
    def group_remove(self, user, entityname, groupname, op=None):
        """Remove 'entityname' from 'groupname' using specified
        operator"""
        raise NotImplemetedError, "Feel free to implement this function"
    
    def group_visibility(self, user, groupname, visibility):
        """Change 'groupname's visibility to 'visibility'"""
        raise NotImplemetedError, "What format should visibility have?"
        group = self._get_group(groupname)
        group.visibility = visibility
        group.write_db()
    
    #
    # person commands
    #

    def person_affadd(self, user, idtype, id, affiliation, status=None, ou=None):
        """Add 'affiliation'@'ou' with 'status' to person with
        'idtype'='id'.  Changes the affiliationstatus if person
        already has an affiliation at the destination"""
        raise NotImplemetedError, "Feel free to implement this function"
    
    def person_afflist(self, user, idtype, id):
        """Return all affiliations for person with 'idtype'='id'"""
        raise NotImplemetedError, "Feel free to implement this function"
    
    def person_affrem(self, user, idtype, id, affiliation, ou):
        """Add 'affiliation'@'ou' with 'status' to person with 'idtype'='id'"""
        raise NotImplemetedError, "Feel free to implement this function"
    
    def person_create(self, user, display_name, birth_date=None, id_type=None, id=None):
        """Call to manually add a person to the database.  Created
        person-id is returned"""
        person = self.person
        person.clear()
        date = None
        if birth_date is not None:
            date = self.Cerebrum.Date(*([int(x) for x in birth_date.split('-')]))
        person.populate(date, self.const.gender_male, description='Manualy created')
        person.affect_names(self.const.system_manual, self.const.name_full) # TDB: new constants
        person.populate_name(self.const.name_full, display_name.encode('iso8859-1'))
        if(id_type is not None):
            if id_type == 'fnr':
                person.populate_external_id(self.const.system_manual,
                                            self.const.externalid_fodselsnr, id)
        person.write_db()
        return {'person_id': person.entity_id}

    def person_delete(self, user, idtype, id):
        """Remove person.  Don't do anything if there are data
        (accounts, affiliations, etc.) associatied with the person."""
        raise NotImplemetedError, "Feel free to implement this function"

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
                raise NotImplemetedError, "Feel free to implement this function"
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

    # TBD:  Should add a generic _get_person(idtype, id) method
    def person_info(self, user, idtype, id):
        """Returns some info on person with 'idtype'='id'"""
        person = self._get_person(id, idtype)
        name = self._get_person_name(person)
        return {'name': name, 'pid': person.entity_id,
                'expid': person.export_id, 'birth': str(person.birth_date),
                'gender': str(self.const.map_const(person.gender)),
                'dead': person.deceased, 'desc': person.description or ''}

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
            raise NotImplemetedError, "unknown idtype: '%s'" % idtype
        return account

    def _get_group(self, id, idtype='name'):
        group = Group.Group(self.Cerebrum)
        if idtype == 'name':
            group.clear()
            group.find_by_name(id)
        else:
            raise NotImplemetedError, "unknown idtype: '%s'" % idtype
        
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
            raise NotImplemetedError, "Unknown idtype: %s" % idtype
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
        
