#!/local/python-2.2.1/bin/python2.2
# #!/usr/bin/env python

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
from Cerebrum import Database,Person,Utils,Account
import sys
import traceback
# import dumputil
import pprint

pp = pprint.PrettyPrinter(indent=4)

class ExportedFuncs:

    """These funcstions can be called by anyone with access to the
    port that the server is running on.  Care must be taken to
    validate input."""

    def __init__(self, fname):
        self.defaultSessionId = 'secret'
        self.THIS_CFU = 'this'
        self.modules = {}
        self.command2module = {}
        self.Cerebrum = Database.connect(user="cerebrum")
        self.person = Person.Person(self.Cerebrum)
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
            modref = mod.BofhdExtention(self.Cerebrum)
            self.modules[modfile] = modref
            for k in modref.all_commands.keys():
                self.command2module[k] = modfile

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
        if suggestion != None:
            return unicode(suggestion, 'iso8859-1')
        else:
            return ''

    def validate(self, argtype, arg):
        """Check if arg is a legal value for the given argtype"""
        pass
    
    def help(self, group):
        # TODO: Re-think this
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
            if pos != None:
                if group == pos.group(1):
                    correct_section = 1
                else :
                    correct_section = 0
                line = re.sub(re_section, "", line)
            # Process ¤cmd:KEY¤ markers
            if correct_section:
                pos = re.search(re_cmd, line)
                if pos != None:
                    # TODO: Check if command is legal for user
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
            for n in range(1, len(args)):            # TODO: Don't do this this way
                if args[n] == 'XNone':
                    new_args += (None,)
                else:
                    new_args += (args[n],)
            ret = func(user, *new_args)
            print "process ret: "
            pp.pprint(ret)
            return self.process_returndata(ret)
        except Exception:
            # ret = "Feil: %s" % sys.exc_info()[0]
            # print "Error: %s: %s " % (sys.exc_info()[0], sys.exc_info()[1])
            # traceback.print_tb(sys.exc_info()[2])
            raise

    def tab_complete(self, sessionid, *args):
        "Atempt to tab-complete the command."
        
        user = self.get_user_from_session(sessionid)
        modfile = self.command2module[args[0]]
        try:
            func = getattr(self.modules[modfile], args[0]+"_tab")
            ret = func(user, *args[1:])
            return self.process_returndata(ret)
        except AttributeError:
            # TODO: Make a default tab-completion function, like:
            # self.xxxx = {
            #    'get_person' : ('fg', 'add', 'user:alterable_user', 'group:alterable_group', 1)
            # }
            #
            return ("foo", "bar", "gazonk")
        except Exception:
            print "Unexpected error"
            raise

    def prompt_next_param(self, sessionid, *args):
        "Prompt for next parameter."
        
        user = self.get_user_from_session(sessionid)
        modfile = self.command2module[args[0]]
        try:
            func = getattr(self.modules[modfile], args[0]+"_prompt")
            ret = func(user, *args[1:])
            return self.process_returndata(ret)
        except AttributeError:
            # TODO: Make a default tab-completion function, like:
            # self.xxxx = {
            #    'get_person' : ('fg', 'add', 'user:alterable_user', 'group:alterable_fgroup', 1)
            # }
            #
            # self.type2text = {
            #    'alterable_user' : 'username',
            #    'alterable_fgroup' : 'filegroup'
            # }
            return "username"
        except Exception:
            print "Unexpected error"
            raise

    def process_returndata(self, ret):
        """Encode the returndata so that it is a legal XML-RPC structure."""
        # Todo: process recursive structures
        if isinstance(ret, list) or isinstance(ret, tuple):
            for x in range(len(ret)):
                if isinstance(ret[x], str):
                    ret[x] = unicode(ret[x], 'iso8859-1')
                elif ret[x] == None:
                    ret[x] = ''
            return ret
        elif isinstance(ret, dict):
            for x in ret.keys():
                if isinstance(ret[x], str):
                    ret[x] = unicode(ret[x], 'iso8859-1')
                elif ret[x] == None:
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


class CallableFuncs:

    """All CallableFuncs takes user as first arg, and is responsible
    for checking neccesary permissions"""

    def __init__(self, exportedFuncs):
        self.ef = exportedFuncs
        # The format of this dict is documented in adminprotocol.html
        self.all_commands = {
            'get_person' : ('person', 'info', 'number', 1),
            'user_lbdate' : ('user', 'lbdate', 'number', 1),
            'user_create' : ('user', 'create', 'person_id', 'np_type', 'expire_date', 'uname', 'uid', 'gid', 'gecos', 'home', 'shell', 0)
            }
        self.name_codes = {}
        for t in self.ef.person.get_person_name_codes():
            self.name_codes[t.code] = t.description
        
    def get_commands(self, uname):
        # TODO: Do some filtering on uname to remove commands
        commands = {}
        for k in self.all_commands.keys():
            commands[k] = self.all_commands[k]
        return commands

    def get_format_suggestion(self, cmd):
        suggestions = {
            'get_person' : "Navn     : %20s\nFødt     : %20s\nKjønn    : %20s\nperson id: %20s\nExport-id: %20s¤name;birth;gender;pid;expid",
            'user_lbdate' : 'Fødselsnr(todo, currently person_id) : %10s    Navn: %s¤p_id;name',
            'user_create' : 'Passord: %s¤password'
            }
        return suggestions.get(cmd)

    def user_lbdate(self, user, date):
        ret = ()
        person = self.ef.person
        for p_id in person.find_persons_by_bdate(date):
            print "Looking for %s" % p_id.person_id
            person.find(p_id.person_id)
            name = person.get_name(person.const.system_lt, person.const.name_full)  # TODO: SourceSystem
            ret = ret + ({'p_id' : p_id.person_id, 'name' : name},)
        if len(ret) == 0:
            return ()
        return ret

    def user_create(self, user, person_id, np_type, expire_date, uname, uid, gid, gecos, home, shell):
        creator_id = 888888    # TODO: Set this
        # person.find(person_id)
        try:
            account = Account.Account(self.ef.Cerebrum)  # TODO: Flytt denne
            account.clear()
            account.populate(self.ef.person.const.entity_person,  # TODO: definer egen e.l
                             person_id,
                             np_type, 
                             creator_id, expire_date)

            # populate_posix_user(user_uid, gid, gecos, home, shell):
            account.populate_posix_user(uid, gid, gecos,
                                        home, shell)
            
            account.affect_domains(self.ef.person.const.entity_accname_default)
            account.populate_name(self.ef.person.const.entity_accname_default, uname)
            
            passwd = "dette er et MD5 passord"
            account.affect_auth_types(self.ef.person.const.auth_type_md5)
            account.populate_authentication_type(self.ef.person.const.auth_type_md5, passwd)
            
            account.write_db()
            self.ef.Cerebrum.commit()
            return {'password' : passwd}
        except Database.DatabaseError:
            self.ef.Cerebrum.rollback()
            # TODO: Log something here
        raise "Something went wrong"

    def get_person(self, user, fnr):
        person = self.ef.person
        person.find_by_external_id('fodselsnr', fnr)
        name = person.get_name('full')
        
        return {'name' : name, 'pid' : person.person_id,
                'expid' : person.export_id, 'birth' :str(person.birth_date),
                'gender' : person.gender, 'dead' : person.deceased,
                'desc' : person.description or ''}

if __name__ == '__main__':
    # Loop for an available port while testing to avoid already bound error
    for port in range(8000,8005):
        try:
            print "Server starting at port: %d" % port
            server = SimpleXMLRPCServer(("localhost", port))
            server.register_instance(ExportedFuncs("config.dat"))
            server.serve_forever()
        except socket.error:
            print "Failed, trying another port"
            pass
