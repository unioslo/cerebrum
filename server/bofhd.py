#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

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
import time
import pickle
import SimpleXMLRPCServer
import xmlrpclib
import getopt
from random import Random

try:
    from M2Crypto import SSL
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

# import SecureXMLRPCServer

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum import Account
from Cerebrum.Utils import Factory
from Cerebrum import Utils
from Cerebrum.extlib import logging
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.bofhd.help import Help
import traceback

logging.fileConfig(cereconf.LOGGING_CONFIGFILE)
logger = logging.getLogger("console")  # The import modules use the "import" logger

# TBD: Is a BofhdSession class a good idea?  It could (optionally)
# take a session_id argument when instantiated, and should have
# methods for setting and retrieving state info for that particular
# session.
class BofhdSession(object):
    def __init__(self, db, id=None):
        self._db = db
        self._id = id
        self._entity_id = None


    def _remove_old_sessions(self):
        """We remove any authenticated session-ids that was
        authenticated more than 1 week ago, or hasn't been used
        frequently enough to have last_seen < 1 day"""
        auth_threshold = time.time() - 3600*24*7
        seen_threshold = time.time() - 3600*24
        auth_threshold = self._db.TimestampFromTicks(auth_threshold)
        seen_threshold = self._db.TimestampFromTicks(seen_threshold)
        self._db.execute("""
        DELETE FROM [:table schema=cerebrum name=bofhd_session_state]
        WHERE exists (SELECT 'foo'
                      FROM[:table schema=cerebrum name=bofhd_session]
                      WHERE bofhd_session.session_id = bofhd_session_state.session_id AND
                            (bofhd_session.auth_time < :auth OR
                             bofhd_session.last_seen < :last))""",
                         {'auth': auth_threshold,
                          'last': seen_threshold})
        self._db.execute("""
        DELETE FROM [:table schema=cerebrum name=bofhd_session]
        WHERE auth_time < :auth OR last_seen < :last""",
                         {'auth': auth_threshold,
                          'last': seen_threshold})
        
    # TODO: we should remove all state information older than N
    # seconds
    def set_authenticated_entity(self, entity_id):
        """Create persistent entity/session mapping; return new session_id.

        This method assumes that entity_id is already sufficiently
        authenticated, so the actual authentication of entity_id
        authentication must be done before calling this method.

        """
        try:
            f = open('/dev/random')
            r = f.read(48)
        except IOError:
            r = Random().random()
        # TBD: We might want to assert that `entity_id` does in fact
        # exist (if that isn't taken care of by constraints on table
        # 'bofhd_session').
        m = md5.new("%s-ok%s" % (entity_id, r))
        session_id = m.hexdigest()
        # TBD: Is it OK for table 'bofhd_session' to have multiple
        # rows for the same `entity_id`?
        self._db.execute("""
        INSERT INTO [:table schema=cerebrum name=bofhd_session]
          (session_id, account_id, auth_time, last_seen)
        VALUES (:session_id, :account_id, [:now], [:now])""", {
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
            if int(Random().random()*10) == 0:   # about 10% propability of update
                self._db.execute("""
                UPDATE [:table schema=cerebrum name=bofhd_session]
                SET last_seen=[:now]
                WHERE session_id=:session_id""", {'session_id': self._id})
        except Errors.NotFoundError:
            raise CerebrumError, "Authentication failure: session expired. You must login again"
        return self._entity_id

    def store_state(self, state_type, state_data, entity_id=None):
        """Add state tuple to ``session_id``."""
        # TODO: assert that there is space for state_data
        return self._db.execute("""
        INSERT INTO [:table schema=cerebrum name=bofhd_session_state]
          (session_id, state_type, entity_id, state_data, set_time)
        VALUES (:session_id, :state_type, :entity_id, :state_data, [:now])""",
                        {'session_id': self._id,
                         'state_type': state_type,
                         'entity_id': entity_id,
                         'state_data': pickle.dumps(state_data)
                         })

    def get_state(self):
        """Retrieve all state tuples for ``session_id``."""
        ret = self._db.query("""
        SELECT state_type, entity_id, state_data, set_time
        FROM [:table schema=cerebrum name=bofhd_session_state]
        WHERE session_id=:session_id
        ORDER BY set_time""", {'session_id': self._id})
        for r in ret:
            r['state_data'] = pickle.loads(r['state_data'])
        return ret

    def clear_state(self, state_types=None):
        """Remove state in the server, such as cached passwords, or
        when logging out."""
        if state_types is None:
            state_types = ('*',)
        for state in state_types:
            sql = """
            DELETE FROM [:table schema=cerebrum name=bofhd_session_state]
            WHERE session_id=:session_id
            """
            if state <> '*':
                sql += " AND state_type=:state"
            self._db.execute(sql, {'session_id': self._id,
                                   'state': state})
            if state == '*':
                self._db.execute("""
                DELETE FROM [:table schema=cerebrum name=bofhd_session]
                WHERE session_id=:session_id
                """, {'session_id': self._id})
        self._remove_old_sessions()

class BofhdRequestHandler(SimpleXMLRPCServer.SimpleXMLRPCRequestHandler,
                          object):

    """Class defining all XML-RPC-callable methods.

    These methods can be called by anyone with access to the port that
    the server is running on.  Care must be taken to validate input.

    """

    use_encryption = CRYPTO_AVAILABLE

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

        def wash_response(obj, no_unicodify=0):
            if obj is None:
                return ':None'
            elif isinstance(obj, (str, unicode)):
                if isinstance(obj, str) and not no_unicodify:
                    obj = unicode(obj, 'iso8859-1')
                if obj.startswith(":"):
                    return ":" + obj
                return obj
            elif isinstance(obj, (tuple, list)):
                obj_type = type(obj)
                return obj_type([wash_response(x) for x in obj])
            elif isinstance(obj, dict):
                obj_type = type(obj)
                return obj_type([(wash_response(x, no_unicodify=1), wash_response(obj[x]))
                                 for x in obj])
            elif isinstance(obj, (int, long, float)):
                return obj
            elif str(type(obj)) == "<type 'DateTime'>":  # TODO: use isinstance instead
                # TODO: This only works for Postgres.  Needs support
                # in Database.py as the Python database API doesn't
                # define any return type for Date
                return xmlrpclib.DateTime(obj.localtime().tuple())
            else:
                raise ValueError, "Unrecognized parameter type: '%r'" % obj
        try:
            func = getattr(self, 'bofhd_' + method)
        except AttributeError:
            raise Exception('method "%s" is not supported' % method)
        try:
            ret = apply(func, wash_params(params))
        except CerebrumError, e:
            # ret = ":".join((":Exception:", type(e).__name__, str(e)))
            ret = str(e)
            raise sys.exc_info()[0], ret
        except NotImplementedError, e:
            logger.warn("Not-implemented: ", exc_info=1)
            raise CerebrumError, "NotImplemented: %s" % str(e)
        except TypeError, e:
            if str(e).find("takes exactly") != -1:
                raise CerebrumError, str(e)
            logger.warn("Unexpected exception", exc_info=1)
            ret = "Unknown error (a server error has been logged)."
            raise sys.exc_info()[0], ret
        except Exception, e:
            logger.warn("Unexpected exception", exc_info=1)
            # ret = ":".join((":Exception:" + type(e).__name__, "Unknown error."))
            ret = "Unknown error (a server error has been logged)."
            raise sys.exc_info()[0], ret
        return wash_response(ret)

    # This method is pretty identical to the one shipped with Python,
    # except that we don't silently eat exceptions
    def do_POST(self):
        """Handles the HTTP POST request.

        Attempts to interpret all HTTP POST requests as XML-RPC calls,
        which are forwarded to the _dispatch method for handling.
        """

        try:
            # get arguments
            data = self.rfile.read(int(self.headers["content-length"]))
            params, method = xmlrpclib.loads(data)

            # generate response
            try:
                response = self._dispatch(method, params)
                # wrap response in a singleton tuple
                response = (response,)
            except CerebrumError, e:
                response = xmlrpclib.dumps(
                    xmlrpclib.Fault(1, "%s:%s" % (sys.exc_type, sys.exc_value))
                    )                
            except:
                logger.warn("Unexpected exception 1", exc_info=1)
                # report exception back to server
                response = xmlrpclib.dumps(
                    xmlrpclib.Fault(1, "%s:%s" % (sys.exc_type, sys.exc_value))
                    )
            else:
                response = xmlrpclib.dumps(response, methodresponse=1)
        except:
            logger.warn("Unexpected exception 2", exc_info=1)
            # internal error, report as HTTP server error
            self.send_response(500)
            self.end_headers()
        else:
            # got a valid XML RPC response
            self.send_response(200)
            self.send_header("Content-type", "text/xml")
            self.send_header("Content-length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

            # shut down the connection
            self.wfile.flush()
            self.connection.shutdown(1)

    def finish(self):
        if self.use_encryption:
            self.request.set_shutdown(SSL.SSL_RECEIVED_SHUTDOWN |
                                      SSL.SSL_SENT_SHUTDOWN)
            self.request.close()
        else:
            super(BofhdRequestHandler, self).finish()
    
    def bofhd_login(self, uname, password):
        account = Account.Account(self.server.db)
        try:
            account.find_by_name(uname)
            enc_pass = account.get_account_authentication(
                self.server.const.auth_type_md5_crypt)
        except Errors.NotFoundError:
            logger.info("Failed login for %s from %s" % (
                uname, ":".join([str(x) for x in self.client_address])))
            raise CerebrumError, "Unknown username or password"
        # TODO: Add API for credential verification to Account.py.
        if enc_pass <> crypt.crypt(password, enc_pass):
            # Use same error message as above; un-authenticated
            # parties should not be told that this in fact is a valid
            # username.
            logger.info("Failed login for %s from %s" % (
                uname, ":".join([str(x) for x in self.client_address])))
            raise CerebrumError, "Unknown username or password"
        try:
            logger.info("Succesful login for %s from %s" % (
                uname, ":".join([str(x) for x in self.client_address])))
            session = BofhdSession(self.server.db)
            session_id = session.set_authenticated_entity(account.entity_id)
            self.server.db.commit()
            return session_id
        except Exception:
            self.server.db.rollback()
            raise

    def bofhd_logout(self, sessionid):
        session = BofhdSession(self.server.db, sessionid)
        try:
            session.clear_state()
            self.server.db.commit()
        except Exception:
            self.server.db.rollback()
            raise
        return "OK"

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
                    logger.info("Skipping: %s" % k)
                    continue
                commands[k] = newcmd[k]
        return commands

    def bofhd_get_format_suggestion(self, cmd):
        suggestion = self.server.cmd2instance[cmd].get_format_suggestion(cmd)
        if suggestion is not None:
            # suggestion['str'] = unicode(suggestion['str'], 'iso8859-1')
            pass
        else:
            # TODO:  Would be better to allow xmlrpc-wrapper to handle None
            return ''
        return suggestion

    def bofhd_get_motd(self, client_id=None, client_version=None):
        ret = ""
        if cereconf.BOFHD_MOTD_FILE is not None:
            f = file(cereconf.BOFHD_MOTD_FILE)
            for line in f.readlines():
                ret += line
        if (client_id is not None and
            cereconf.BOFHD_CLIENTS.get(client_id, '') != client_version):
            ret += "You do not seem to run the latest version of the client\n"
        return ret[:-1]
##     def validate(self, argtype, arg):
##         """Check if arg is a legal value for the given argtype"""
##         pass

    def bofhd_help(self, sessionid, *group):
        logger.debug("Help: %s" % str(group))
        commands = self.bofhd_get_commands(sessionid)
        if len(group) == 0:
            ret = self.server.help.get_general_help(commands)
        elif group[0] == 'arg_help':
            ret = self.server.help.get_arg_help(group[1])
        elif len(group) == 1:
            ret = self.server.help.get_group_help(commands, *group)
        elif len(group) == 2:
            ret = server.help.get_cmd_help(commands, *group)
        else:
            raise CerebrumError, "Unexpected help request"
        return ret

    def _run_command_with_tuples(self, func, session, args, myret):
        next_tuple = -1
        for n in range(len(args)):
            if isinstance(args[n], (tuple, list)):
                next_tuple = n
                break
        if next_tuple == -1:
            myret.append(func(session, *args))
        else:
            for x in args[next_tuple]:
                new_args = args[:next_tuple] + (x,) + args[next_tuple+1:]
                self._run_command_with_tuples(func, session, new_args, myret)

    def bofhd_run_command(self, sessionid, cmd, *args):
        """Execute the callable function (in the correct module) with
        the given name after mapping sessionid to username"""

        session = BofhdSession(self.server.db, sessionid)
        entity_id = session.get_entity_id()
        self.server.db.cl_init(change_by=entity_id)
        logger.debug("Run command: %s (%s)" % (cmd, args))
        func = getattr(self.server.cmd2instance[cmd], cmd)

        try:
            has_tuples = False
            for x in args:
                if isinstance(x, (tuple, list)):
                    has_tuples = True
                    break
            ret = []
            self._run_command_with_tuples(func, session, args, ret)
            if not has_tuples:
                ret = ret[0]
            self.server.db.commit()
            # TBD: What should be returned if `args' contains tuple,
            # indicating that `func` should be called multiple times?
            return self.server.db.pythonify_data(ret)
        except self.server.db.IntegrityError, m:
            # TODO: Sometimes we also get an OperationalError, we
            # should trap this as well, probably with a more
            # user-friendly message
            self.server.db.rollback()
            raise CerebrumError, "DatabaseError: %s" % m
        except Exception:
            # ret = "Feil: %s" % sys.exc_info()[0]
            # print "Error: %s: %s " % (sys.exc_info()[0], sys.exc_info()[1])
            # traceback.print_tb(sys.exc_info()[2])
            self.server.db.rollback()
            raise

    def bofhd_call_prompt_func(self, sessionid, cmd, *args):
        """Return a dict with information on how to prompt for a
        parameter.  The dict can contain the following keys:
        - prompt : message string
        - help_ref : reference to help for this argument
        - last_arg : if this argument is the last.  If only this key
          is present, the client will send the command as it is.
        - default : default value
        - map : maps the user-entered value to a value that
          is returned to the server, typically when user selects from
          a list.  It is a list-of lists, where the inner list is like:
          (("%5s %s", 'foo', 'bar'), return-value).  The first row is
          used as header
        - raw : don't use map after all"""
        session = BofhdSession(self.server.db, sessionid)
        instance, cmdObj = self.server.get_cmd_info(cmd)
        if cmdObj._prompt_func is not None:
            logger.debug("prompt_func: %s" % str(args))
            return getattr(instance, cmdObj._prompt_func.__name__)(session, *args)
        raise CerebrumError, "Command has no prompt func"
        
    def bofhd_get_default_param(self, sessionid, cmd, *args):
        """Get default value for a parameter.  Returns a string.  The
        client should append '[<returned_string>]: ' to its prompt.

        Will either use the function defined in the command object, or
        in the corresponding parameter object.
        """
        session = BofhdSession(self.server.db, sessionid)
        instance, cmdObj = self.server.get_cmd_info(cmd)

        # If the client calls this method when no default function is defined,
        # it is a bug in the client.
        if cmdObj._default is not None:
            func = cmdObj._default
        else:
            func = cmdObj._params[len(args)]._default
            if func is None:
                return ""
        return getattr(instance, func.__name__)(session, *args)  # TODO: er dette rett syntax?

class BofhdServer(object):
    def __init__(self, database, config_fname):
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
            instance = cls(self)
            self.cmd_instances.append(instance)
            for k in instance.all_commands.keys():
                self.cmd2instance[k] = instance
        t = self.cmd2instance.keys()
        t.sort()
        for k in t:
            if not hasattr(self.cmd2instance[k], k):
                logger.warn("Warning, function '%s' is not implemented" % k)
        self.help = Help(self.cmd_instances)

    def get_cmd_info(self, cmd):
        """Return BofhdExtension and Command object for this cmd
        """
        inst = self.cmd2instance[cmd]
        return (inst, inst.all_commands[cmd])

class StandardBofhdServer(SimpleXMLRPCServer.SimpleXMLRPCServer, BofhdServer):
    def __init__(self, database, config_fname, addr, requestHandler,
                 logRequests=1):
        super(StandardBofhdServer, self).__init__(addr, requestHandler)
        BofhdServer.__init__(self, database, config_fname)
    
    def server_bind(self):
        import socket
        import SocketServer
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        SocketServer.TCPServer.server_bind(self)

if CRYPTO_AVAILABLE:
    class SSLBofhdServer(SSL.SSLServer, BofhdServer): # SSL.ThreadingSSLServer

        def __init__(self, database, config_fname, addr, requestHandler,
                     ssl_context):
            super(SSLBofhdServer, self).__init__(addr, requestHandler,
                                                 ssl_context)
            BofhdServer.__init__(self, database, config_fname)
            self.logRequests = 0

def usage():
    print """Usage: bofhd.py -c filename [-t keyword]
  -c | --config-file <filename>: use as config file
  -t | --test-help <keyword>: check help consistency
  --unencrypted: don't use https
"""

if __name__ == '__main__':
    opts, args = getopt.getopt(sys.argv[1:], 'c:t:p:',
                               ['config-file=', 'test-help=',
                                'port=', 'unencrypted'])
    use_encryption = CRYPTO_AVAILABLE
    conffile = None
    port = 8000
    for opt, val in opts:
        if opt in ('-c', '--config-file'):
            conffile = val
        elif opt in ('-p', '--port'):
            port = int(val)
        elif opt in ('-t', '--test-help'):
            # This is a bit icky.  What we want to accomplish is to
            # fetch the results from a bofhd_get_commands client
            # command.
            server = BofhdServer(Factory.get('Database')(), conffile)
            commands = {}
            for inst in server.cmd_instances:
                newcmd = inst.get_commands(None)
                for k in newcmd.keys():
                    if inst is not server.cmd2instance[k]:
                        print "Skipping:", k
                        continue
                    commands[k] = newcmd[k]
            if val == '':
                print server.help.get_general_help(commands)
            elif val.find(":") >= 0:
                print server.help.get_cmd_help(commands, *val.split(":"))
            elif val == 'check':
                server.help.check_consistency(commands)
            else:
                print server.help.get_group_help(commands, val)
            sys.exit()
        elif opt in ('--unencrypted',):
            use_encryption = False

    BofhdRequestHandler.use_encryption = use_encryption
            
    if conffile is None:
        usage()
        sys.exit()
        
    print "Server starting at port: %d" % port
    if use_encryption:
        # from echod_lib import init_context
        def init_context(protocol, certfile, cafile, verify, verify_depth=10):
            ctx = SSL.Context(protocol)
            ctx.load_cert(certfile)
            ctx.load_client_ca(cafile)
            ctx.load_verify_info(cafile)
            ctx.set_verify(verify, verify_depth)
            ctx.set_allow_unknown_ca(1)
            ctx.set_session_id_ctx('echod')
            ctx.set_info_callback()
            print dir(ctx)
            return ctx

        ctx = init_context('sslv23', '%s/server.cert' % cereconf.DB_AUTH_DIR,
                           '%s/ca.pem' % cereconf.DB_AUTH_DIR,
                           SSL.verify_none)
        ctx.set_tmp_dh('%s/dh1024.pem' % cereconf.DB_AUTH_DIR)
        server = SSLBofhdServer(Factory.get('Database')(), conffile,
                                ("0.0.0.0", port), BofhdRequestHandler, ctx)
    else:
        server = StandardBofhdServer(Factory.get('Database')(), conffile,
                                ("0.0.0.0", port), BofhdRequestHandler)
    server.serve_forever()
