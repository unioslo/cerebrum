#!/usr/bin/env python2.2

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

import sys
import crypt
import md5
import socket
import SimpleXMLRPCServer
from random import Random

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum import Account
from Cerebrum.Utils import Factory
from Cerebrum import Utils
from server.bofhd_errors import CerebrumError
import traceback

# TBD: Is a BofhdSession class a good idea?  It could (optionally)
# take a session_id argument when instantiated, and should have
# methods for setting and retrieving state info for that particular
# session.
class BofhdSession(object):
    def __init__(self, db, id=None):
        self._db = db
        self._id = id
        self._entity_id = None

    def set_authenticated_entity(self, entity_id):
        """Create persistent entity/session mapping; return new session_id.

        This method assumes that entity_id is already sufficiently
        authenticated, so the actual authentication of entity_id
        authentication must be done before calling this method.

        """
        r = Random().random()           # TODO: strong-random
        # TBD: We might want to assert that `entity_id` does in fact
        # exist (if that isn't taken care of by constraints on table
        # 'bofhd_session').
        m = md5.new("%s-ok%s" % (entity_id, r))
        session_id = m.hexdigest()
        # TBD: Is it OK for table 'bofhd_session' to have multiple
        # rows for the same `entity_id`?
        self._db.execute("""
        INSERT INTO [:table schema=cerebrum name=bofhd_session]
          (session_id, account_id, auth_time)
        VALUES (:session_id, :account_id, [:now])""", {
            'session_id': session_id,
            'account_id': entity_id
            })
        self._entity_id = entity_id
        self._id = session_id
        return session_id

    def get_entity_id(self):
        if self._id is None:
            # TBD: Proper exception class?
            raise RuntimeError, \
                  "Unable to get entity_id; not associated with any session."
        if self._entity_id is not None:
            return self._entity_id
        try:
            self._entity_id = self._db.query_1("""
            SELECT account_id
            FROM [:table schema=cerebrum name=bofhd_session]
            WHERE session_id=:session_id""", {'session_id': self._id})
        except Errors.NotFoundError:
            raise CerebrumError, "Authentication failure"
        return self._entity_id

    def store_state(self, state_type, state_data, entity_id):
        """Add state tuple to ``session_id``."""
        return self._db.execute("""
        INSERT INTO [:table schema=cerebrum name=bofhd_session_state]
          (session_id, state_type, entity_id, state_data, set_time)
        VALUES (:session_id, :state_type, :entity_id, :state_data, [:now])""",
                        {'session_id': self._id,
                         'state_type': state_type,
                         'entity_id': entity_id,
                         'state_data': state_data
                         })

    def get_state(self):
        """Retrieve all state tuples for ``session_id``."""
        return self._db.query("""
        SELECT state_type, entity_id, state_data, set_time
        FROM [:table schema=cerebrum name=bofhd_session_state]
        WHERE session_id=:session_id
        ORDER BY set_time""", {'session_id': self._id}) 


class BofhdRequestHandler(SimpleXMLRPCServer.SimpleXMLRPCRequestHandler):

    """Class defining all XML-RPC-callable methods.

    These methods can be called by anyone with access to the port that
    the server is running on.  Care must be taken to validate input.

    """

    def _dispatch(self, method, params):
        # Translate params between Python objects and XML-RPC-usable
        # structures.  We could have used marshal.{loads,dumps} here,
        # but then the Java client would have trouble
        # encoding/decoding requests/responses.
        def wash_params(obj):
            if isinstance(obj, (str, unicode)):
                if obj == ':None':
                    return None
                elif obj.startswith(":"):
                    return obj[1:]
                return obj
            elif isinstance(obj, (tuple, list)):
                obj_type = type(obj)
                return obj_type([wash_params(x) for x in obj])
            elif isinstance(obj, dict):
                obj_type = type(obj)
                return obj_type([(wash_params(x), wash_params(obj[x]))
                                 for x in obj])
            elif isinstance(obj, (int, long, float)):
                return obj
            else:
                raise ValueError, "Unrecognized parameter type: '%r'" % obj

        def wash_response(obj):
            if obj is None:
                return ':None'
            elif isinstance(obj, (str, unicode)):
                if obj.startswith(":"):
                    return ":" + obj
                return obj
            elif isinstance(obj, (tuple, list)):
                obj_type = type(obj)
                return obj_type([wash_response(x) for x in obj])
            elif isinstance(obj, dict):
                obj_type = type(obj)
                return obj_type([(wash_response(x), wash_response(obj[x]))
                                 for x in obj])
            elif isinstance(obj, (int, long, float)):
                return obj
            else:
                raise ValueError, "Unrecognized parameter type: '%r'" % obj
        try:
            func = getattr(self, 'bofhd_' + method)
        except AttributeError:
            raise Exception('method "%s" is not supported' % method)
        try:
            ret = apply(func, wash_params(params))
        except CerebrumError, e:
            ret = ":".join((":Exception:", type(e).__name__, str(e)))
            raise sys.exc_info()[0], ret
        except Exception, e:
            print "Caught: %s" % sys.exc_info()[0]
            traceback.print_exc()
##            self.log_traceback()
            ret = ":".join((":Exception:" + type(e).__name__, "Unknown error."))
            raise sys.exc_info()[0], ret
        return wash_response(ret)

    def bofhd_login(self, uname, password):
        account = Account.Account(self.server.db)
        try:
            account.find_by_name(uname)
            enc_pass = account.get_account_authentication(
                self.server.const.auth_type_md5)
        except Errors.NotFoundError:
            raise CerebrumError, "Invalid user"
        # TODO: Add API for credential verification to Account.py.
        if enc_pass <> crypt.crypt(password, enc_pass):
            # Use same error message as above; un-authenticated
            # parties should not be told that this in fact is a valid
            # username.
            raise CerebrumError, "Invalid user"
        try:
            session = BofhdSession(self.server.db)
            session_id = session.set_authenticated_entity(account.entity_id)
            self.server.db.commit()
            return session_id
        except Exception:
            self.server.db.rollback()
            raise

    def bofhd_get_commands(self, sessionid):
        """Build a dict of the commands available to the client."""

        session = BofhdSession(self.server.db, sessionid)
        entity_id = session.get_entity_id()
        commands = {}
        for inst in self.server.cmd_instances:
            newcmd = inst.get_commands(entity_id)
            for k in newcmd.keys():
                if inst is not self.server.cmd2instance[k]:
                    # If module B is imported after module A, and both
                    # implement 'command', only the implementation in
                    # the latter module will actually be callable.
                    #
                    # However, A.get_commands() and B.get_commands()
                    # might not agree on whether or not the
                    # authenticated user should be allowed to invoke
                    # 'command'.
                    #
                    # Hence, to avoid including overridden,
                    # non-callable functions in our return value, we
                    # verify that the module in
                    # self.command2module[command] matches the module
                    # whose .get_commands() we're processing.
                    print "Skipping:", k
                    continue
                commands[k] = newcmd[k]
        return commands

    def bofhd_get_format_suggestion(self, cmd):
        suggestion = self.server.cmd2instance[cmd].get_format_suggestion(cmd)
        if suggestion is not None:
            suggestion['str'] = unicode(suggestion['str'], 'iso8859-1')
        else:
            # TODO:  Would be better to allow xmlrpc-wrapper to handle None
            return ''
        return suggestion

##     def validate(self, argtype, arg):
##         """Check if arg is a legal value for the given argtype"""
##         pass

    def bofhd_help(self, *group):
        # TBD: Re-think this.
        # Show help by parsing the help file.
        # This is only partially implemented.
        f = file("help.txt")
        ret = ''
        while 1:
            line = f.readline()
            if not line: break
            if line[0] == '#':
                continue
            ret = ret + line
        ret = ret + "End of help text"
        return unicode(ret.strip(), 'iso8859-1')

    def bofhd_run_command(self, sessionid, cmd, *args):
        """Execute the callable function (in the correct module) with
        the given name after mapping sessionid to username"""

        session = BofhdSession(self.server.db, sessionid)
        entity_id = session.get_entity_id()

        print "Run command: %s (%s)" % (cmd, args)
        func = getattr(self.server.cmd2instance[cmd], cmd)

        try:
            for x in args:
                if isinstance(x, tuple):
                    raise NotImplementedError, "Tuple params not implemented."
            # TBD: It would probably be better to pass the full
            # `session`, and not merely `entity_id`, to `func`.
            ret = func(entity_id, *args)
            self.server.db.commit()
            # TBD: What should be returned if `args' contains tuple,
            # indicating that `func` should be called multiple times?
            return self.server.db.pythonify_data(ret)
        except Exception:
            # ret = "Feil: %s" % sys.exc_info()[0]
            # print "Error: %s: %s " % (sys.exc_info()[0], sys.exc_info()[1])
            # traceback.print_tb(sys.exc_info()[2])
            self.server.db.rollback()
            raise

    ## Prompting and tab-completion works pretty much the same way.
    ## First we check if the function 'name' has a function named
    ## 'name_prompt' (or 'name_tab'), and uses this.  If no such
    ## function is defined, we check the Parameter object to find out
    ## what to do.

    def bofhd_tab_complete(self, sessionid, cmd, *args):
        "Attempt to TAB-complete the command."

        session = BofhdSession(self.server.db, sessionid)
        entity_id = session.get_entity_id()
        func, inst, param = self.server.get_param_info(cmd, "_tab", len(args))
        if func is not None:
            ret = func(entity_id, *args)
        else:
            if param._tab_func is None:
                ret = ()
            else:
                ret = getattr(inst, param._tab_func)(user, *args)
        return ret

    def bofhd_prompt_next_param(self, sessionid, cmd, *args):
        "Prompt for next parameter."

        session = BofhdSession(self.server.db, sessionid)
        entity_id = session.get_entity_id()
        func, inst, param = self.server.get_param_info(cmd, "_prompt",
                                                       len(args))
        if func is not None:
            return func(entity_id, *args)
        else:
            if param._prompt_func is None:
                return param.getPrompt()
            else:
                return getattr(inst, param._prompt_func)(entity_id, *args)


class BofhdServer(SimpleXMLRPCServer.SimpleXMLRPCServer, object):

    def __init__(self, database, config_fname, addr,
                 requestHandler=BofhdRequestHandler, logRequests=1):
        super(BofhdServer, self).__init__(addr, requestHandler, logRequests)
        self.db = database
        self.const = Factory.get('Constants')(database)
        self.cmd2instance = {}
        self.cmd_instances = []

        config_file = file(config_fname)
        while True:
            line = config_file.readline()
            if not line:
                break
            line = line.strip()
            if line[0] == '#' or not line:
                continue
            # Import module and create an instance of it; update
            # mapping from command name to a class instance with a
            # method that implements that command.  This means that
            # any command's implementation can be overridden by
            # providing a new implementation in a later class.
            modfile, class_name = line.split("/", 1)
            mod = Utils.dyn_import(modfile)
            cls = getattr(mod, class_name)
            instance = cls(database)
            self.cmd_instances.append(instance)
            for k in instance.all_commands.keys():
                self.cmd2instance[k] = instance
        t = self.cmd2instance.keys()
        t.sort()
        for k in t:
            if not hasattr(self.cmd2instance[k], k):
                print "Warning, function '%s' is not implemented" % k

    def get_param_info(self, cmd, fext, nargs):
        """Return ``fext`` info for parameter #``nargs`` of ``cmd``.

        Returns a tuple indicating how to get ``fext``-type
        information on parameter #``nargs`` of command ``cmd``.  The
        tuple has the following structure:

          (function, modref, param)

        `function`: Either None or a function that can be called with
           arguments (`authenticated user`, param_1, ..., param_nargs)
           to get ``fext``-type info on param_nargs.

        `modref`: None iff `function` is not None; otherwise the
           module-specific BofhdExtension object where command `cmd`
           is defined.

        `param`: None iff `function` is not None; otherwise the
           Parameter object corresponding to parameter # `nargs` of
           command `cmd`.

        """
        inst = self.cmd2instance[cmd]
        try:
            func = getattr(inst, cmd+fext)
            return (func, None, None)
        except AttributeError:
            pass
        cmdspec = inst.all_commands[cmd]
        # prompt skal ikke kalles hvis for mange argumenter(?)
        if nargs > len(cmdspec._params):
            raise ValueError, \
                  "Too many args (%d) for command '%s'." % (nargs, cmd)
        return (None, inst, cmdspec._params[nargs])

    def server_bind(self):
        import socket
        import SocketServer
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        SocketServer.TCPServer.server_bind(self)

def find_config_dat():
    # XXX This should get the path from configure
    for filename in ("server/config.dat",
                     "config.dat",
                     "/etc/cerebrum/config.dat",
                     "/tmp/cerebrum/etc/cerebrum/config.dat"):
        try:
            print "Testing filename ",filename
            f = file(filename)
            if (f):
                return filename
        except:
            continue
    return "config.dat"

if __name__ == '__main__':
    conffile = find_config_dat()
    # Loop for an available port while testing to avoid already bound error
    for port in range(8000,8005):
        try:
            print "Server starting at port: %d" % port
            if not cereconf.ENABLE_BOFHD_CRYPTO:
                server = BofhdServer(Factory.get('Database')(), conffile,
                                     ("0.0.0.0", port))
            else:
                from server import MySimpleXMLRPCServer
                from M2Crypto import SSL

                ctx = MySimpleXMLRPCServer.init_context('sslv23', 'server.pem',
                                                        'ca.pem',
                                                        SSL.verify_none)
                ctx.set_tmp_dh('dh1024.pem')
                server = MySimpleXMLRPCServer.SimpleXMLRPCServer(('',port),ctx)

##             server.register_instance(ExportedFuncs(Factory.get('Database')(),
##                                                    conffile))
            server.serve_forever()
        except socket.error:
            print "Failed, trying another port"
            pass
