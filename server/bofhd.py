#!/usr/bin/env python
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
import mx
import socket
import cerebrum_path
import cereconf
if sys.version_info < (2, 3):
    from Cerebrum.extlib import timeoutsocket
    use_new_timeout = False
else:
    use_new_timeout = True
    # Doesn't work with m2crypto:
    # socket.setdefaulttimeout(cereconf.BOFHD_CLIENT_SOCKET_TIMEOUT)
import thread
import threading
import time
import pickle
import SocketServer
import SimpleXMLRPCServer
import xmlrpclib
import getopt
import traceback
import random
from random import Random

try:
    from M2Crypto import SSL
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

# import SecureXMLRPCServer

from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum import QuarantineHandler
from Cerebrum.modules.bofhd.errors import CerebrumError, \
     ServerRestartedError, SessionExpiredError
from Cerebrum.modules.bofhd.help import Help
from Cerebrum.modules.bofhd.xmlutils import \
     xmlrpc_to_native, native_to_xmlrpc

Account_class = Utils.Factory.get('Account')

logger = Utils.Factory.get_logger("bofhd")  # The import modules use the "import" logger

# TBD: Is a BofhdSession class a good idea?  It could (optionally)
# take a session_id argument when instantiated, and should have
# methods for setting and retrieving state info for that particular
# session.
class BofhdSession(object):
    def __init__(self, db, id=None):
        self._db = db
        self._id = id
        self._entity_id = None
        self._owner_id = None

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
            # /dev/random doesn't provide enough bytes
            f = open('/dev/urandom')
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
            self._entity_id, self.auth_time = self._db.query_1("""
            SELECT account_id, auth_time
            FROM [:table schema=cerebrum name=bofhd_session]
            WHERE session_id=:session_id""", {'session_id': self._id})
            if int(Random().random()*10) == 0:   # about 10% propability of update
                self._db.execute("""
                UPDATE [:table schema=cerebrum name=bofhd_session]
                SET last_seen=[:now]
                WHERE session_id=:session_id""", {'session_id': self._id})
        except Errors.NotFoundError:
            raise SessionExpiredError, "Authentication failure: session expired. You must login again"
        return self._entity_id

    def get_owner_id(self):
        if self._owner_id is None:
            account_id = self.get_entity_id()
            ac = Account_class(self._db)
            ac.find(account_id)
            self._owner_id = int(ac.owner_id)
        return self._owner_id

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

    def get_state(self, state_type=None):
        """Retrieve all state tuples for ``session_id``."""
        if state_type is not None:
            where = "AND state_type=:state_type"
        else:
            where = ""
        ret = self._db.query("""
        SELECT state_type, entity_id, state_data, set_time
        FROM [:table schema=cerebrum name=bofhd_session_state]
        WHERE session_id=:session_id %s
        ORDER BY set_time""" % where, {
            'session_id': self._id,
            'state_type': state_type})
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
        try:
            func = getattr(self, 'bofhd_' + method)
        except AttributeError:
            raise Exception('method "%s" is not supported' % method)
        try:
            ret = apply(func, xmlrpc_to_native(params))
        except CerebrumError, e:
            # Exceptions with unicode characters in the message
            # produce a UnicodeError when cast to str().  Fix by
            # encoding as utf-8
            if e.args:
                ret = "%s: %s"  % (e.__class__.__name__, e.args[0])
            else:
                ret = e.__class__.__name__
            if isinstance(ret, unicode):
                raise sys.exc_info()[0], ret.encode('utf-8')
            else:
                raise sys.exc_info()[0], ret
        except NotImplementedError, e:
            logger.warn("Not-implemented: ", exc_info=1)
            raise CerebrumError, "NotImplemented: %s" % str(e)
        except TypeError, e:
            if (str(e).find("takes exactly") != -1 or
                str(e).find("takes at most") != -1):
                raise CerebrumError, str(e)
            logger.warn("Unexpected exception", exc_info=1)
            ret = "Unknown error (a server error has been logged)."
            raise sys.exc_info()[0], ret
        except Exception, e:
            logger.warn("Unexpected exception", exc_info=1)
            # ret = ":".join((":Exception:" + type(e).__name__, "Unknown error."))
            ret = "Unknown error (a server error has been logged)."
            raise sys.exc_info()[0], ret
        return native_to_xmlrpc(ret)

    def handle(self):
        if not use_new_timeout:
            if not use_encryption:
                self.connection.set_timeout(cereconf.BOFHD_CLIENT_SOCKET_TIMEOUT)
            try:
                super(BofhdRequestHandler, self).handle()
            except timeoutsocket.Timeout, msg:
                logger.debug("Timeout: %s from %s" % (
                    msg, ":".join([str(x) for x in self.client_address])))
                self.server.db.rollback()
        else:
            if not use_encryption:
                self.connection.settimeout(cereconf.BOFHD_CLIENT_SOCKET_TIMEOUT)
            try:
                super(BofhdRequestHandler, self).handle()
            except socket.timeout, msg:
                logger.debug("Timeout: %s from %s" % (
                    msg, ":".join([str(x) for x in self.client_address])))
                self.server.db.rollback()

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
                logger.debug2(
                    "[%s] dispatch %s" % (threading.currentThread().getName(), method))

                response = self._dispatch(method, params)
                # wrap response in a singleton tuple
                response = (response,)
            except CerebrumError, e:
                # Due to the primitive XML-RPC support for exceptions,
                # we want to report any subclass of CerebrumError as
                # CerebrumError so that the client can recognize this
                # as a user-error.
                # TODO: This is not a perfect solution...
                if sys.exc_type in (ServerRestartedError, SessionExpiredError):
                    error_class = sys.exc_type
                else:
                    error_class = CerebrumError
                response = xmlrpclib.dumps(
                    xmlrpclib.Fault(1, "%s:%s" % (error_class, sys.exc_value))
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
        logger.debug2("End of" + threading.currentThread().getName())
        
    def finish(self):
        if self.use_encryption:
            self.request.set_shutdown(SSL.SSL_RECEIVED_SHUTDOWN |
                                      SSL.SSL_SENT_SHUTDOWN)
            self.request.close()
        else:
            super(BofhdRequestHandler, self).finish()
    
    def bofhd_login(self, uname, password):
        account = Account_class(self.server.db)
        try:
            account.find_by_name(uname)
        except Errors.NotFoundError:
            logger.info("Failed login for %s from %s" % (
                uname, ":".join([str(x) for x in self.client_address])))
            raise CerebrumError, "Unknown username or password"

        # Check quarantines
        quarantines = []      # TBD: Should the quarantine-check have a utility-API function?
        now = mx.DateTime.now()
        for qrow in account.get_entity_quarantine():
            if (qrow['start_date'] <= now
                and (qrow['end_date'] is None or qrow['end_date'] >= now)
                and (qrow['disable_until'] is None
                     or qrow['disable_until'] < now)):
                # The quarantine found in this row is currently
                # active.
                quarantines.append(qrow['quarantine_type'])            
        qh = QuarantineHandler.QuarantineHandler(
            self.server.db, quarantines)
        if qh.should_skip() or qh.is_locked():
            raise CerebrumError, "User has active lock/skip quarantines, login denied"

        # Check password
        enc_passwords = []
        for auth in (self.server.const.auth_type_md5_crypt,
                     self.server.const.auth_type_crypt3_des):
            try:
                enc_pass = account.get_account_authentication(auth)
                if enc_pass:            # Ignore empty password hashes
                    enc_passwords.append(enc_pass)
            except Errors.NotFoundError:
                pass
        if not enc_passwords:
            logger.info("Missing password for %s from %s" % (uname,
                        ":".join([str(x) for x in self.client_address])))
            raise CerebrumError, "Unknown username or password"
        if isinstance(password, unicode):  # crypt.crypt don't like unicode
            # TODO: ideally we should not hardcode charset here.
            password = password.encode('iso8859-1')
        # TODO: Add API for credential verification to Account.py.
        mismatch = map(lambda e: e <> crypt.crypt(password, e), enc_passwords)
        if filter(None, mismatch):
            # Use same error message as above; un-authenticated
            # parties should not be told that this in fact is a valid
            # username.
            if filter(lambda m: not m, mismatch):
                mismatch = zip(mismatch, enc_passwords)
                match    = [p[1] for p in mismatch if not p[0]]
                mismatch = [p[1] for p in mismatch if p[0]]
                if filter(lambda c: c < '!' or c > '~', password):
                    chars = 'chars, including [^!-~]'
                else:
                    chars = 'good chars'
                logger.info("Password (%d %s) for user %s matches"
                            " auth_data '%s' but not '%s'"
                            % (len(password), chars, uname,
                               "', '".join(match), "', '".join(mismatch)))
            logger.info("Failed login for %s from %s" % (
                uname, ":".join([str(x) for x in self.client_address])))
            raise CerebrumError, "Unknown username or password"
        try:
            logger.info("Succesful login for %s from %s" % (
                uname, ":".join([str(x) for x in self.client_address])))
            session = BofhdSession(self.server.db)
            session_id = session.set_authenticated_entity(account.entity_id)
            self.server.db.commit()
            self.server.known_sessions[session_id] = 1
            return session_id
        except Exception:
            self.server.db.rollback()
            raise

    def bofhd_logout(self, session_id):
        session = BofhdSession(self.server.db, session_id)
        try:
            session.clear_state()
            if self.server.known_sessions.has_key(session_id):
                del(self.server.known_sessions[session_id])
            self.server.db.commit()
        except Exception:
            self.server.db.rollback()
            raise
        return "OK"

    def bofhd_get_commands(self, session_id):
        """Build a dict of the commands available to the client."""

        session = BofhdSession(self.server.db, session_id)
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
            cereconf.BOFHD_CLIENTS.get(client_id, '') > client_version):
            ret += "You do not seem to run the latest version of the client\n"
        return ret[:-1]
##     def validate(self, argtype, arg):
##         """Check if arg is a legal value for the given argtype"""
##         pass

    def bofhd_help(self, session_id, *group):
        logger.debug("Help: %s" % str(group))
        commands = self.bofhd_get_commands(session_id)
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

    def bofhd_run_command(self, session_id, cmd, *args):
        """Execute the callable function (in the correct module) with
        the given name after mapping session_id to username"""

        session = BofhdSession(self.server.db, session_id)
        entity_id = session.get_entity_id()
        session.remote_address=self.client_address
        if not self.server.known_sessions.has_key(session_id):
            self.server.known_sessions[session_id] = 1
            raise ServerRestartedError()
        self.server.db.cl_init(change_by=entity_id)
        logger.debug("Run command: %s (%s) by %i" % (cmd, args, entity_id))
        if not self.server.cmd2instance.has_key(cmd):
            raise CerebrumError, "Illegal command '%s'" % cmd
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
        except (self.server.db.IntegrityError,
                self.server.db.OperationalError), m:
            self.server.db.rollback()
            raise CerebrumError, "DatabaseError: %s" % m
        except Exception:
            # ret = "Feil: %s" % sys.exc_info()[0]
            # print "Error: %s: %s " % (sys.exc_info()[0], sys.exc_info()[1])
            # traceback.print_tb(sys.exc_info()[2])
            self.server.db.rollback()
            raise

    def bofhd_call_prompt_func(self, session_id, cmd, *args):
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
        session = BofhdSession(self.server.db, session_id)
        instance, cmdObj = self.server.get_cmd_info(cmd)
        if cmdObj._prompt_func is not None:
            logger.debug("prompt_func: %s" % str(args))
            return getattr(instance, cmdObj._prompt_func.__name__)(session, *args)
        raise CerebrumError, "Command has no prompt func"
        
    def bofhd_get_default_param(self, session_id, cmd, *args):
        """Get default value for a parameter.  Returns a string.  The
        client should append '[<returned_string>]: ' to its prompt.

        Will either use the function defined in the command object, or
        in the corresponding parameter object.
        """
        session = BofhdSession(self.server.db, session_id)
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
        self.config_fname = config_fname
        self.read_config()
        self.known_sessions = {}

    def read_config(self):
        self.const = Utils.Factory.get('Constants')(self.db)
        self.cmd2instance = {}
        self.server_start_time = time.time()
        if hasattr(self, 'cmd_instances'):
            for i in self.cmd_instances:
                reload(sys.modules[i.__module__])
        self.cmd_instances = []
        self.logger = logger

        config_file = file(self.config_fname)
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

    def close_request(self, request):
        # Check that the database is alive and well by creating a new
        # cursor.
        #
        # As close_request() is called without any except: in
        # SocketServer.BaseServer.handle_request(), any exception here
        # will actually cause bofhd to die.  This is probably what we
        # want to happen when a database connection unexpextedly goes
        # down; anything resembling automatic reconnection magic could
        # alter the crashed state of the database, making debugging
        # more difficult.
        csr = self.db.cursor()
        csr.close()

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
            
        def server_bind(self):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            SocketServer.TCPServer.server_bind(self)

    # TODO: Check if it is sufficient to do something like:
    # class ThreadingSSLBofhdServer(SSL.ThreadingSSLServer, SSLBofhdServer)
    class ThreadingSSLBofhdServer(SSL.ThreadingSSLServer, BofhdServer):

        def __init__(self, database, config_fname, addr, requestHandler,
                     ssl_context):
            super(SSLBofhdServer, self).__init__(addr, requestHandler,
                                                 ssl_context)
            BofhdServer.__init__(self, database, config_fname)
            self.logRequests = 0

        def server_bind(self):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            SocketServer.TCPServer.server_bind(self)

_db_pool_lock = thread.allocate_lock()

class ProxyDBConnection(object):

    """ProxyDBConnection asserts that each thread gets its own
    instance of the class specified in __init__.  We maintain a pool
    of such class-objects, so that we may re-use the object when the
    thread it belonged to has terminated.

    The class works by overriding __getattr__.  Thus, when one says
    db.<anything>, this method is called.
    """

    def __init__(self, obj_class):
        self._obj_class = obj_class
        self.active_connections = {}
        self.free_pool = []

    def __getattr__(self, attrib):
        try:
            obj = self.active_connections[threading.currentThread().getName()]
        except KeyError:
            # TODO: 
            # - limit max # of simultaneously used db-connections
            # - reduce size of free_pool when size > N
            _db_pool_lock.acquire()
            logger.debug("Alloc new db-handle for " +
                         threading.currentThread().getName())
            running_threads = []
            for t in threading.enumerate():
                running_threads.append(t.getName())
            logger.debug("  Threads: " + str(running_threads))
            for p in self.active_connections.keys():
                if p not in running_threads:
                    logger.debug("  Close " + p)
                    #self.active_connections[p].close()
                    self.free_pool.append(self.active_connections[p])
                    del(self.active_connections[p])
            if not self.free_pool:
                obj = self._obj_class()
            else:
                obj = self.free_pool.pop(0)
            self.active_connections[threading.currentThread().getName()] = obj
            logger.debug("  Open: " + str(self.active_connections.keys()))
            _db_pool_lock.release()
        return getattr(obj, attrib)

def usage(exitcode=0):
    print """Usage: bofhd.py -c filename [-t keyword]
  -c | --config-file <filename>: use as config file
  -t | --test-help <keyword>: check help consistency
  -m : run multithreaded (experimental)
  -p | --port num: run on alternative port (default: 8000)
  --unencrypted: don't use https
"""
    sys.exit(exitcode)

if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'c:t:p:m',
                                   ['config-file=', 'test-help=',
                                    'port=', 'unencrypted',
                                    'multi-threaded'])
    except getopt.GetoptError:
        usage(1)
        
    use_encryption = CRYPTO_AVAILABLE
    conffile = None
    port = 8000
    multi_threaded = False
    for opt, val in opts:
        if opt in ('-c', '--config-file'):
            conffile = val
        elif opt in ('-m', '--multi-threaded'):
            multi_threaded = True
        elif opt in ('-p', '--port'):
            port = int(val)
        elif opt in ('-t', '--test-help'):
            # This is a bit icky.  What we want to accomplish is to
            # fetch the results from a bofhd_get_commands client
            # command.
            server = BofhdServer(Utils.Factory.get('Database')(), conffile)
            commands = {}
            db = Utils.Factory.get('Database')()
            group = Utils.Factory.get('Group')(db)
            group.find_by_name(cereconf.BOFHD_SUPERUSER_GROUP)
            some_superuser = [int(i) for i in group.get_members()][0]
            for inst in server.cmd_instances:
                newcmd = inst.get_commands(some_superuser)
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
        
    logger.info("Server starting at port: %d" % port)
    if multi_threaded:
        db = ProxyDBConnection(Utils.Factory.get('Database'))
    else:
        db = Utils.Factory.get('Database')()
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
            return ctx

        ctx = init_context('sslv23', '%s/server.cert' % cereconf.DB_AUTH_DIR,
                           '%s/ca.pem' % cereconf.DB_AUTH_DIR,
                           SSL.verify_none)
        ctx.set_tmp_dh('%s/dh1024.pem' % cereconf.DB_AUTH_DIR)
        if multi_threaded:
            server = ThreadingSSLBofhdServer(db, conffile,
                                    ("0.0.0.0", port), BofhdRequestHandler, ctx)
        else:
            server = SSLBofhdServer(db, conffile,
                                    ("0.0.0.0", port), BofhdRequestHandler, ctx)
    else:
        if multi_threaded:
            new_class = type('ThreadingBofhdServer',
                             (SocketServer.ThreadingMixIn, StandardBofhdServer), {})
            server = new_class(db, conffile,
                               ("0.0.0.0", port), BofhdRequestHandler)
        else:
            server = StandardBofhdServer(db, conffile,
                                         ("0.0.0.0", port), BofhdRequestHandler)
    server.serve_forever()

# arch-tag: 65c53099-96e5-4d49-aa19-18b9800f26d6
