#!/local/python-2.2.1/bin/python2.2
# #!/usr/bin/env python2.2

# Copyright 2002 University of Oslo, Norway
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

# $Id$

#
# Server used by clients that wants to access the cerebrum database.
#
# Work in progress, current implementation, expect big changes
#

from SimpleXMLRPCServer import SimpleXMLRPCServer
import re
import socket
# import xmlrpclib
from Cerebrum import Database,Person,Utils,Account,Errors,cereconf
from Cerebrum.modules import PosixUser
import sys
import traceback
from cmd_param import *
# import dumputil
import pprint

pp = pprint.PrettyPrinter(indent=4)

class ExportedFuncs(object):

    """

    These functions can be called by anyone with access to the port
    that the server is running on.  Care must be taken to validate
    input.

    """

    def __init__(self, Cerebrum, fname):
        self.defaultSessionId = 'secret'
        self.THIS_CFU = 'this'
        self.modules = {}           # Maps modulenames to a module reference
        self.command2module = {}    # Maps a command to a modulename
        self.Cerebrum = Cerebrum
        self.person = Person.Person(self.Cerebrum)
        self.const = self.person.const
        self.cfu = CallableFuncs(self)
        self.modules[self.THIS_CFU] = self.cfu

        # Add reference to module containg the given function
        for k in self.cfu.all_commands.keys():
            self.command2module[k] = self.THIS_CFU
            
        f = file(fname)
        while 1:
            line = f.readline()
            if not line: break
            if line[0] == '#':
                continue

            # Import module, create an instance of it, and update
            # mapping between command and the module implementing it.
            # Sub-modules may override functions.
            modfile = line.strip()
            mod = Utils.dyn_import(modfile)
            modref = mod.BofhdExtension(self.Cerebrum)
            self.modules[modfile] = modref
            for k in modref.all_commands.keys():
                self.command2module[k] = modfile
        t = self.command2module.keys()
        t.sort()
        for k in t:
            if getattr(self.modules[self.command2module[k]], k, None) is None:
                print "Warning, function '%s' is not implemented" % k
        
    def login(self, uname, password):
        if(uname != 'runefro'):
            raise "CerebrumError", "Invalid user"
        return self.defaultSessionId

    def get_commands(self, sessionid):
        # Build a tuple of tuples describing the commands available to
        # the client

        if(sessionid != self.defaultSessionId):
            raise "CerebrumError", "Authentication failure"
        else:
            commands = self.modules[self.THIS_CFU].get_commands("uname")
            for mn in self.modules.keys():
                if mn == self.THIS_CFU: continue
                newcmd = self.modules[mn].get_commands("uname")
                for k in newcmd.keys():
                    commands[k] = newcmd[k]
            return commands

    def get_format_suggestion(self, cmd):
        modfile = self.command2module[cmd]
        suggestion = self.modules[modfile].get_format_suggestion(cmd)
        if suggestion is not None:
            return unicode(suggestion, 'iso8859-1')
        else:
            return ''

    def validate(self, argtype, arg):
        """Check if arg is a legal value for the given argtype"""
        pass
    
    def help(self, group):
        # TBD: Re-think this
        # Show help by parsing the help file.  This is only partially implemented
        f = file("help.txt")
        if group == '':
            group = "general"
        re_strip = re.compile(r"¤", re.DOTALL)
        re_section = re.compile(r"¤section:([^¤]+)¤", re.DOTALL)
        re_cmd = re.compile(r"¤cmd:([^¤]+)¤", re.DOTALL)
        ret = ''
        correct_section = 0
        while 1:
            line = f.readline()
            if not line: break
            if line[0] == '#':
                continue
            # Find correct section
            pos = re.search(re_section, line)
            if pos is not None:
                if group == pos.group(1):
                    correct_section = 1
                else :
                    correct_section = 0
                line = re.sub(re_section, "", line)
            # Process ¤cmd:KEY¤ markers
            if correct_section:
                pos = re.search(re_cmd, line)
                if pos is not None:
                    # TBD: Check if command is legal for user
                    line = re.sub(re_cmd, pos.group(1), line)
                    line = re.sub(re_strip, "", line)
                ret = ret + line
        return unicode(ret.strip(), 'iso8859-1')

    def run_command(self, sessionid, *args):
        """Execute the callable function (in the correct module) with
        the given name after mapping sessionid to username"""

        user = self.get_user_from_session(sessionid)

        print "Run command: %s (%s)" % (args[0], args)
        modfile = self.command2module[args[0]]
        func = getattr(self.modules[modfile], args[0])
        try:
            new_args = ()
            for n in range(1, len(args)):
                if args[n] == 'XNone':     # TBD: Don't do this this way
                    new_args += (None,)
                else:
                    new_args += (args[n],)
                # TBD: Hvis vi får lister/tupler som input, skal func
                # kalles flere ganger
                if isinstance(args[n], list) or isinstance(args[n], tuple):
                    raise NotImplemetedError, "tuple argumenter ikke implemetert enda"
            ret = func(user, *new_args)
            print "process ret: "
            pp.pprint(ret)
            self.Cerebrum.commit()
            return self.process_returndata(ret)
        except Exception:
            # ret = "Feil: %s" % sys.exc_info()[0]
            # print "Error: %s: %s " % (sys.exc_info()[0], sys.exc_info()[1])
            # traceback.print_tb(sys.exc_info()[2])
            self.Cerebrum.rollback()
            raise

    ## Prompting and tab-completion works pretty much the same way.
    ## First we check if the function 'name' has a function named
    ## 'name_prompt' (or 'name_tab'), and uses this.  If no such
    ## function is defined, we check the Parameter object to find out
    ## what to do.

    def tab_complete(self, sessionid, *args):
        "Atempt to tab-complete the command."
        
        user = self.get_user_from_session(sessionid)
        func, modref, param = self._lookupParamInfo(args[0], "_tab", len(args)-1)
        if func is not None:
            ret = func(user, *args[1:])
        else:
            if param._tab_func is None:
                ret = ()
            else:
                ret = getattr(modref, param._tab_func)(user, *args[1:])
        return self.process_returndata(ret)

    def prompt_next_param(self, sessionid, *args):
        "Prompt for next parameter."

        user = self.get_user_from_session(sessionid)
        func, modref, param = self._lookupParamInfo(args[0], "_prompt", len(args)-1)
        if func is not None:
            ret = func(user, *args[1:])
            return self.process_returndata(ret)
        else:
            if param._prompt_func is None:
                if param._name is not None:
                    return param._prompt % param._name  # TBD: set this explicitly
                else:
                    return param._prompt
            else:
                return getattr(modref, param._prompt_func)(user, *args[1:])

    def _lookupParamInfo(self, cmd, fext, nargs):
        modref = self.modules[ self.command2module[cmd] ]
        try:
            func = getattr(modref, cmd+fext)
            return (func, None, None, None)
        except AttributeError:
            pass
        cmdspec = modref.all_commands[cmd]
        assert(nargs < len(cmdspec._params)) # prompt skal ikke kalles hvis for mange argumenter(?)
        return (None, modref, cmdspec._params[nargs])

    def process_returndata(self, ret):
        """Encode the returndata so that it is a legal XML-RPC structure."""
        # Todo: process recursive structures
        if isinstance(ret, list) or isinstance(ret, tuple):
            for x in range(len(ret)):
                if isinstance(ret[x], str):
                    ret[x] = unicode(ret[x], 'iso8859-1')
                elif ret[x] is None:
                    ret[x] = ''
            return ret
        elif isinstance(ret, dict):
            for x in ret.keys():
                if isinstance(ret[x], str):
                    ret[x] = unicode(ret[x], 'iso8859-1')
                elif ret[x] is None:
                    ret[x] = ''
            return ret
        else:
            if isinstance(ret, str):
                ret = unicode(ret, 'iso8859-1')
            return ret

    def get_user_from_session(self, sessionid):
        """Map sessionid to an existing authenticated user"""
        if(1 == 0):
            raise "CerebrumError", "Authentication failure"
        return 'runefro'

class CallableFuncs(object):
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
                                  OU(default=1), Date(optional=1)),

        ## bofh> account password <accountname> [<password>]
        'account_password': Command(('account', 'password'),
                                  AccountName(), AccountPassword(optional=1)),
        ## bofh> account posix_create <accountname> <prigroup> <home=> <shell=> <gecos=>
        'account_posix_create': Command(('account', 'posix_create'),
                                        AccountName(), GroupName(),
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
        'group_create': Command(("group", "create"), GroupName("new"), Description()),
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
                                 PersonId()),
        ## bofh> person delete <id_type> <id>
        'person_delete': Command(("person", "delete"), PersonIdType(),
                                 PersonId(repeat=1)),
        ## bofh> person find {<name> | <id> [<id_type>] | <birth_date>}
        'person_find': Command(("person", "find") , Id(),
                               PersonIdType(optional=1)),
        ## bofh> person info <idtype> <id>
        'person_info': Command(("person", "info"), PersonIdType(),
                               PersonId()),
        ## bofh> person name <id_type> {<export_id> | <fnr>} <name_type> <name>
        'person_name': Command(("person", "name"), PersonIdType(),
                               PersonId(), PersonNameType(), PersonName())
        }

    def __init__(self, exportedFuncs):
        self.ef = exportedFuncs
        self.const = self.ef.const
        self.name_codes = {}
        for t in self.ef.person.get_person_name_codes():
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
        suggestions = {
            'get_person' : "Navn     : %20s\nFødt     : %20s\nKjønn    : %20s\nperson id: %20s\nExport-id: %20s¤name;birth;gender;pid;expid",
            'user_lbdate' : 'Fødselsnr(todo, currently person_id) : %10s    Navn: %s¤p_id;name',
            'user_create' : 'Username: %8s   Passord: %s¤uname;password'
            }
        return suggestions.get(cmd)

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
        creator_id = 888888    # TBD: set this from user
        account = Account.Account(self.ef.Cerebrum)  # TBD: Flytt denne
        account.clear()
        person = self.ef.person
        person.clear()
        if idtype == 'fnr':
            person.find_by_external_id(self.const.externalid_fodselsnr, id)
        else:
            raise NotImplemetedError, "Unknown idtype: %s" % idtype
        
        account.populate(accountname,
                         self.const.entity_person,  # Owner type
                         person.person_id,
                         None, 
                         creator_id, expire_date)
        account.write_db()
        return account.account_id

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
        group=Group.Group(self.ef.Cerebrum)
        group.find_by_name(prigroup)
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
            operator = co.group_memberop_union
        group_s = Group.Group(self.ef.Cerebrum)
        group_s.find_by_name(src_group)
        group_d = Group.Group(self.ef.Cerebrum)
        group_d.find_by_name(dest_group)
        group_d.add_member(group_s, operator)

    def group_create(self, user, groupname, description):
        """Create the group 'groupname' with 'description'.  Returns
        the new groups id"""
        raise NotImplemetedError, "Feel free to implement this function"
    
    def group_delete(self, user, groupname):
        """Deletes the group 'groupname'"""
        raise NotImplemetedError, "Feel free to implement this function"
    
    def group_expand(self, user, groupname):
        """Do full group expansion; list resulting members and their
        entity types."""
        raise NotImplemetedError, "Feel free to implement this function"
    
    def group_expire(self, user, groupname, date):
        """Set group expiration date for 'groupname' to 'date'"""
        group = _get_group(groupname)
        group.expire_date = self.ef.Cerebrum.Date(*([int(x) for x in date.split('-')]))
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
        group = _get_group(groupname)
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
        group = _get_group(groupname)
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
        person = self.ef.person
        person.clear()
        date = self.ef.Cerebrum.Date(*([int(x) for x in birth_date.split('-')]))
        person.populate(date, self.const.gender_male, description='Manualy created')
        person.affect_names(self.const.system_manual, self.const.name_full) # TDB: new constants
        person.populate_name(self.const.name_full, display_name.encode('iso8859-1'))
        if(id_type is not None):
            if id_type == 'fnr':
                person.populate_external_id(self.const.system_manual,
                                            self.const.externalid_fodselsnr, id)
        person.write_db()
        return person.person_id

    def person_delete(self, user, idtype, id):
        """Remove person.  Don't do anything if there are data
        (accounts, affiliations, etc.) associatied with the person."""
        raise NotImplemetedError, "Feel free to implement this function"

    def person_find(self, key, keytype):
        """Search for person with 'key'.  If keytype is not set, it is
        assumed to be a date on the format YYYY-MM-DD, or a name"""
        personids = ()
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
        person = self.ef.person
        person.clear()
        for p in personids:
            person.find(p_id.person_id)
            name = person.get_name(self.const.system_lt, self.const.name_full)  # TBD: SourceSystem
            ret = ret + ({'p_id' : p_id.person_id, 'name' : name},)
        return ret

    # TBD:  Should add a generic _get_person(idtype, id) method
    def person_info(self, user, idtype, id):
        """Returns some info on person with 'idtype'='id'"""
        person = _get_person(id, idtype)
        name = None
        for ss in cereconf.PERSON_NAME_SS_ORDER:
            try:
                name = person.get_name(getattr(self.const, ss), self.const.name_full)
                break
            except Errors.NotFoundError:
                raise NotImplemetedError, "Feel free to implement this function"
        
        return {'name': name, 'pid': person.person_id,
                'expid': person.export_id, 'birth': str(person.birth_date),
                'gender': person.gender, 'dead': person.deceased,
                'desc': person.description or ''}

    def person_name(self, user, idtype, id, nametype, name):
        """Set name of 'nametype' to 'name' for person with 'idtype'='id'"""
        # TODO: Map nametype to Constant
        person = _get_person(id, idtype)
        person.affect_names(self.const.system_manual, nametype)
        person.populate_name(nametype, name)
        person.write_db()

    #
    # misc helper functions.
    # TODO: These should be protected so that they are not remotely callable

    def _get_account(self, id, idtype='name'):
        account = Account.Account(self.ef.Cerebrum)  # TBD: Flytt denne
        if idtype == 'name':
            account.clear()
            account.find_account_by_name(self.const.account_namespace, accountname)
        else:
            raise NotImplemetedError, "unknown idtype: '%s'" % idtype
        return account

    def _get_group(self, id, idtype='name'):
        group = Group.Group(self.ef.Cerebrum)
        if idtype == 'name':
            group.clear()
            group.find_by_name(id)
        else:
            raise NotImplemetedError, "unknown idtype: '%s'" % idtype
        
        return group

    def _get_person(self, id, idtype='fnr'):
        person = self.ef.person
        if idtype == 'fnr':
            person.find_by_external_id(self.const.externalid_fodselsnr, id)
        else:
            raise NotImplemetedError, "Unknown idtype: %s" % idtype
        return person

if __name__ == '__main__':
    # Loop for an available port while testing to avoid already bound error
    for port in range(8000,8005):
        try:
            print "Server starting at port: %d" % port
            server = SimpleXMLRPCServer(("0.0.0.0", port))
            server.register_instance(ExportedFuncs(Database.connect(),
                                                   "config.dat"))
            server.serve_forever()
        except socket.error:
            print "Failed, trying another port"
            pass
