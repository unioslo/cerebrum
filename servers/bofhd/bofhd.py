#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2002-2015 University of Oslo, Norway
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
""" Server used by clients that wants to access the cerebrum database.

Work in progress, current implementation, expect big changes


Configuration
-------------

BOFHD_CLIENT_SOCKET_TIMEOUT
    Socket timeout for clients, in seconds

BOFHD_NONLOCK_QUARANTINES
    Quarantines that does not exclude users from logging into bofh. The value
    should be an iterable of strings. Each string should be the string
    representation of a Quarantine constant.

BOFHD_MOTD_FILE
    Path to a file that contains a 'message of the day'.

BOFHD_CLIENTS
    A dictionary that maps known clients to required version. If a known client
    connects with an old version number, bofhd will append a warning to the
    MOTD.

BOFHD_SUPERUSER_GROUP
    A group of bofh superusers. Members of this group will have access to all
    bofhd commands. The value should contain the name of the group.

DB_AUTH_DIR
    General cerebrum setting. Contains the path to a folder with protected
    data.  Bofhd expects to find certain files in this directory:

    TODO: Server certificate
    TODO: Database connection -- general file, but also needed by bofhd

CEREBRUM_DATABASE_NAME
    General cerebrum setting, only used for logging the database that bofh
    connects to.

"""

import sys
import crypt
import socket

import cerebrum_path
import cereconf

import thread
import threading
import time
import SocketServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
import xmlrpclib

from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum import QuarantineHandler
from Cerebrum import https

from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.bofhd.errors import SessionExpiredError
from Cerebrum.modules.bofhd.errors import ServerRestartedError
from Cerebrum.modules.bofhd.errors import UnknownError

from Cerebrum.modules.bofhd.help import Help
from Cerebrum.modules.bofhd.xmlutils import xmlrpc_to_native, native_to_xmlrpc
from Cerebrum.modules.bofhd.utils import BofhdUtils
from Cerebrum.modules.bofhd.session import BofhdSession

# An installation *may* have many instances of bofhd running in parallel. If
# this is the case, make sure that all of the instances get their own
# logger. Otherwise, depending on the logger used, the physical entity
# representing the log (typically a file) may not cope with multiple processes
# writing to it simultaneously.
logger = Utils.Factory.get_logger("bofhd")  # The import modules use the "import" logger

thread_name = lambda: threading.currentThread().getName()
""" Get thread name. """

format_addr = lambda addr: ':'.join([str(x) for x in addr or ['err', 'err']])
""" Get ip:port formatted string from address tuple. """


# TODO: We need to figure out where the db connection is *really* needed. We
#       need to either:
#         1. Fix the DBProxyConnection
#         2. Move all DB access out of the ServerImplementation and into the
#            RequestHandler.
class BofhdRequestHandler(SimpleXMLRPCRequestHandler, object):

    """Class defining all XML-RPC-callable methods.

    These methods can be called by anyone with access to the port that
    the server is running on.  Care must be taken to validate input.

    """

    def setup(self):
        """ Setup the request.

        This function will read out the BOFHD_CLIENT_SOCKET_TIMEOUT setting,
        if no other timeout is given, and apply it to the request socket.

        """
        if self.timeout is None:
            self.timeout = getattr(cereconf, 'BOFHD_CLIENT_SOCKET_TIMEOUT')
        super(BofhdRequestHandler, self).setup()

    def _dispatch(self, method, params):
        """ Call bofhd function and handle errors.

        This method is responsible for mapping the actual XMLRPC method to a
        function call (i.e. bofhd_get_commands, bofhd_run_command, bofhd_login,
        etc...)

        :raise NotImplementedError: When an unknown function is called.
        :raise CerebrumError: When known errors occurs.
        :raise UnknownError: When unhandled (server errors) occurs.

        """
        try:
            func = getattr(self, 'bofhd_' + method)
        except AttributeError:
            raise NotImplementedError('method "%s" is not supported' % method)

        try:
            ret = apply(func, xmlrpc_to_native(params))
        except CerebrumError, e:
            # Exceptions with unicode characters in the message
            # produce a UnicodeError when cast to str().  Fix by
            # encoding as utf-8
            if e.args:
                ret = "%s: %s" % (e.__class__.__name__, e.args[0])
            else:
                ret = e.__class__.__name__
            exc_type = sys.exc_info()[0]
            if isinstance(ret, unicode):
                raise exc_type(ret.encode('utf-8'))
            else:
                # Some of our exceptions throws iso8859-1 encoded
                # error-messages.  These must be encoded as utf-8 to
                # avoid client-side:
                #   org.xml.sax.SAXParseException: character not allowed
                ret = ret.decode('iso8859-1').encode('utf-8')
                raise exc_type(ret)
        except NotImplementedError, e:
            logger.warn("Not-implemented: ", exc_info=1)
            raise CerebrumError("Not Implemented: %s" % str(e))
        except TypeError, e:
            if (str(e).find("takes exactly") != -1
                    or str(e).find("takes at least") != -1
                    or str(e).find("takes at most") != -1):
                raise CerebrumError(str(e))
            logger.warn("Unexpected exception", exc_info=1)
            raise UnknownError(sys.exc_info()[0],
                               sys.exc_info()[1],
                               msg="A server error has been logged.")
        except Exception, e:
            logger.warn("Unexpected exception", exc_info=1)
            raise UnknownError(sys.exc_info()[0],
                               sys.exc_info()[1],
                               msg="A server error has been logged.")

        # TODO: Dispatch should maybe handle rollback for all methods?

        return native_to_xmlrpc(ret)

    def handle(self):
        """ Handle request and timeout. """
        # TODO: Do we need to do db.rollback here? It should probably be moved
        #       elsewhere.
        try:
            super(BofhdRequestHandler, self).handle()
        except socket.timeout, e:
            # Timeouts are not 'normal' operation.
            logger.info("[%s] timeout: %s from %s",
                        thread_name(), e, format_addr(self.client_address))
            self.close_connection = 1
            self.server.db.rollback()
        except https.SSLError, e:
            # SSLError could be a timeout, or it could be some other form of
            # error
            logger.info("[%s] SSLError: %s from %s",
                        thread_name(), e, format_addr(self.client_address))
            self.close_connection = 1
            self.server.db.rollback()
        except:
            self.server.db.rollback()
            raise

    # This method is pretty identical to the one shipped with Python,
    # except that we don't silently eat exceptions
    def do_POST(self):
        """Handles the HTTP POST request.

        Attempts to interpret all HTTP POST requests as XML-RPC calls,
        which are forwarded to the _dispatch method for handling.

        """
        # Whenever unexpected exception occurs, we'd like to include
        # as much debugging info as possible.  To avoid raising
        # NameError in the debug-printing code, we pre-initialise a
        # few central variables.
        data = params = method = None
        try:
            # get arguments
            data = self.rfile.read(int(self.headers["content-length"]))
            params, method = xmlrpclib.loads(data)

            # generate response
            try:
                logger.debug2("[%s] dispatch %s", thread_name(), method)

                response = self._dispatch(method, params)
                # wrap response in a singleton tuple
                response = (response,)
            except CerebrumError:
                # Due to the primitive XML-RPC support for exceptions,
                # we want to report any subclass of CerebrumError as
                # CerebrumError so that the client can recognize this
                # as a user-error.
                if sys.exc_type in (ServerRestartedError,
                                    SessionExpiredError,
                                    UnknownError):
                    error_class = sys.exc_type
                else:
                    error_class = CerebrumError
                response = xmlrpclib.dumps(
                    xmlrpclib.Fault(1, "%s.%s:%s" % (error_class.__module__,
                                                     error_class.__name__,
                                                     sys.exc_value)))
            except:
                logger.warn(
                    "Unexpected exception 1 (client=%r, params=%r, method=%r)",
                    self.client_address, params, method,
                    exc_info=True)
                # report exception back to server
                response = xmlrpclib.dumps(
                    xmlrpclib.Fault(1, "%s:%s" % (sys.exc_type,
                                                  sys.exc_value)))
            else:
                response = xmlrpclib.dumps(response, methodresponse=1)
        except:
            logger.warn("Unexpected exception 2 (client %r, data=%r)",
                        self.client_address, data,
                        exc_info=True)
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
            self.wfile.flush()
        logger.debug2("[%s] thread done", thread_name())

    def bofhd_login(self, uname, password):
        """ The bofhd login function. """
        account = Utils.Factory.get('Account')(self.server.db)
        try:
            account.find_by_name(uname)
        except Errors.NotFoundError:
            if isinstance(uname, unicode):
                uname = uname.encode('utf-8')
            logger.info("Failed login for %s from %s" % (
                uname, ":".join([str(x) for x in self.client_address])))
            raise CerebrumError("Unknown username or password")

        # Check quarantines
        quarantines = []  # TBD: Should the quarantine-check have a utility-API function?
        for qrow in account.get_entity_quarantine(only_active=True):
            # The quarantine found in this row is currently
            # active. Some quarantine types may not restrict
            # access to bofhd even if they otherwise result in
            # lock. Check therefore whether a found quarantine
            # should be appended
            #
            # FIXME, Jazz 2008-04-08:
            # This should probably be based on spreads or some
            # such mechanism, but quarantinehandler and the import
            # routines don't support a more appopriate solution yet
            if not (str(self.server.const.Quarantine(qrow['quarantine_type']))
                    in cereconf.BOFHD_NONLOCK_QUARANTINES):
                quarantines.append(qrow['quarantine_type'])
        qh = QuarantineHandler.QuarantineHandler(self.server.db,
                                                 quarantines)
        if qh.should_skip() or qh.is_locked():
            qua_repr = ", ".join(self.server.const.Quarantine(q).description
                                 for q in quarantines)
            raise CerebrumError("User has active lock/skip quarantines, login "
                                "denied: %s" % qua_repr)
        # Check expire_date
        if account.is_expired():
            raise CerebrumError("User is expired")
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
            raise CerebrumError("Unknown username or password")
        if isinstance(password, unicode):  # crypt.crypt don't like unicode
            # TODO: ideally we should not hardcode charset here.
            password = password.encode('iso8859-1')
        # TODO: Add API for credential verification to Account.py.
        mismatch = map(lambda e: e != crypt.crypt(password, e), enc_passwords)
        if filter(None, mismatch):
            # Use same error message as above; un-authenticated
            # parties should not be told that this in fact is a valid
            # username.
            if filter(lambda m: not m, mismatch):
                mismatch = zip(mismatch, enc_passwords)
                match = [p[1] for p in mismatch if not p[0]]
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
            raise CerebrumError("Unknown username or password")
        try:
            logger.info("Succesful login for %s from %s" % (
                uname, ":".join([str(x) for x in self.client_address])))
            session = BofhdSession(self.server.db, logger)
            session_id = session.set_authenticated_entity(
                account.entity_id, self.client_address[0])
            self.server.db.commit()
            self.server.known_sessions[session_id] = 1
            return session_id
        except Exception:
            self.server.db.rollback()
            raise

    def bofhd_logout(self, session_id):
        """ The bofhd logout function. """
        session = BofhdSession(self.server.db, logger, session_id)
        try:
            session.clear_state()
            if session_id in self.server.known_sessions:
                del(self.server.known_sessions[session_id])
            self.server.db.commit()
        except Exception:
            self.server.db.rollback()
            raise
        return "OK"

    def bofhd_get_commands(self, session_id):
        """Build a dict of the commands available to the client."""

        session = BofhdSession(self.server.db, logger, session_id)
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
            raise CerebrumError("Unexpected help request")
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

    def check_session_validity(self, session):
        """Make sure that session has not expired.

        @type session: instance of BofhdSession
        @param session: session object we are checking.

        @rtype: int
        @return:
          entity_id of the entity owning the session (i.e. which account is
          associated with that specific session_id)

        """
        session_id = session.get_session_id()
        # This is throw an exception, when session_id has expired
        entity_id = session.get_entity_id()
        if session.remote_address is None:
            session.remote_address = self.client_address

        if session_id not in self.server.known_sessions:
            self.server.known_sessions[session_id] = 1
            raise ServerRestartedError()

        return entity_id

    def bofhd_run_command(self, session_id, cmd, *args):
        """Call command with session details.

        Execute the callable function (in the correct module) with the given
        name after mapping session_id to username

        """
        # First, drop the short-lived sessions FIXME: if this is too
        # CPU-intensive, introduce a timestamp in this class, and drop the
        # short-lived sessions ONLY if more than BofhdSession._short_timeout
        session = BofhdSession(self.server.db, logger)
        session.remove_short_timeout_sessions()

        session = BofhdSession(self.server.db, logger, session_id,
                               self.client_address)
        entity_id = self.check_session_validity(session)
        self.server.db.cl_init(change_by=entity_id)
        logger.debug("Run command: %s (%s) by %i" % (cmd, args, entity_id))
        if cmd not in self.server.cmd2instance:
            raise CerebrumError("Illegal command '%s'" % cmd)
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
        except Exception:
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

        session = BofhdSession(self.server.db, logger, session_id,
                               self.client_address)
        instance, cmdObj = self.server.get_cmd_info(cmd)
        self.check_session_validity(session)
        if cmdObj._prompt_func is not None:
            logger.debug("prompt_func: %s" % str(args))
            return getattr(instance,
                           cmdObj._prompt_func.__name__)(session, *args)
        raise CerebrumError("Command %s has no prompt func" % (cmd,))

    def bofhd_get_default_param(self, session_id, cmd, *args):
        """ Get default value for a parameter.

        Returns a string. The client should append '[<returned_string>]: ' to
        its prompt.

        Will either use the function defined in the command object, or in the
        corresponding parameter object.

        """
        session = BofhdSession(self.server.db, logger, session_id)
        instance, cmdObj = self.server.get_cmd_info(cmd)

        # If the client calls this method when no default function is defined,
        # it is a bug in the client.
        if cmdObj._default is not None:
            func = cmdObj._default
        else:
            func = cmdObj._params[len(args)]._default
            if func is None:
                return ""
        return getattr(instance, func.__name__)(session, *args)


# TODO: vv move to Cerebrum.modules.bofhd.server vv

class BofhdConfig(object):

    """ Container for parsing and keeping a bofhd config. """

    def __init__(self, filename=None):
        """ Initialize new config. """
        self._exts = list()  # NOTE: Must keep order!
        if filename:
            self.load_from_file(filename)

    def load_from_file(self, filename):
        """ Load config file. """
        with open(filename, 'r') as f:
            cnt = 0
            for line in f.readlines():
                cnt += 1
                if line:
                    line = line.strip()
                if not line or line.startswith('#'):
                    continue
                try:
                    mod, cls = line.split("/", 1)
                except:
                    mod, cls = None, None
                if not mod or not cls:
                    raise Exception("Parse error in '%s' on line %d: %r" %
                                    (filename, cnt, line))
                self._exts.append((mod, cls))

    def extensions(self):
        """ All extensions from config. """
        for mod, cls in self._exts:
            yield mod, cls


class BofhdServerImplementation(object):
    """ Common Server implementation. """

    def __init__(self, database=None, config_fname=None, logRequests=False, **kws):
        """ Set up a new bofhd server.

        :param Cerebrum.Database database:
            A Cerebrum database connection
        :param string config_fname:
            Filename of the bofhd config file.

        """
        super(BofhdServerImplementation, self).__init__(**kws)
        self.known_sessions = {}
        self.logRequests = logRequests
        self.db = database
        self.util = BofhdUtils(database)
        self.config = BofhdConfig(config_fname)
        self.load_extensions()

    def load_extensions(self):
        """ Load BofhdExtensions (commands and help texts).

        This will load and initialize the BofhdExtensions specified by the
        configuration.

        """
        self.const = Utils.Factory.get('Constants')(self.db)
        self.cmd2instance = {}
        self.server_start_time = time.time()
        if hasattr(self, 'cmd_instances'):
            for i in self.cmd_instances:
                reload(sys.modules[i.__module__])
        self.cmd_instances = []
        self.logger = logger

        for modfile, class_name in self.config.extensions():
            mod = Utils.dyn_import(modfile)
            cls = getattr(mod, class_name)
            instance = cls(self)
            self.cmd_instances.append(instance)

            # Map commands to BofhdExtensions
            # NOTE: Any duplicate command will be overloaded by later
            #       BofhdExtensions.
            for k in instance.all_commands.keys():
                self.cmd2instance[k] = instance
            if hasattr(instance, "hidden_commands"):
                for k in instance.hidden_commands.keys():
                    self.cmd2instance[k] = instance
        t = self.cmd2instance.keys()
        t.sort()
        for k in t:
            if not hasattr(self.cmd2instance[k], k):
                logger.warn("Warning, function '%s' is not implemented" % k)
        self.help = Help(self.cmd_instances, logger=logger)

        # Check that the help text is okay
        # Reformat the command definitions to be suitable for the help.
        cmds_for_help = dict()
        for inst in self.cmd_instances:
            cmds_for_help.update(
                dict((k, cmd.get_struct(inst)) for k, cmd
                     in inst.all_commands.iteritems()
                     if cmd and self.cmd2instance[k] == inst))
        self.help.check_consistency(cmds_for_help)

    def get_cmd_info(self, cmd):
        """Return BofhdExtension and Command object for this cmd
        """
        inst = self.cmd2instance[cmd]
        return (inst, inst.all_commands[cmd])

    # Override SocketServer.TCPServer (or subclass).
    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        super(BofhdServerImplementation, self).server_bind()

    def get_request(self):
        """ Get request socket and client address.

        This is used to log new connections.

        :rtype: tuple
        :return:
            A tuple with the request socket, and client address. The client
            address is a tuple consisting of address and port.

        """
        sock, addr = super(BofhdServerImplementation, self).get_request()
        logger.debug("[%s] new connection from %s, %r",
                     thread_name(), format_addr(addr), sock)
        return sock, addr

    def close_request(self, request):
        """ Close request socket.

        process_request either leads to:
          - finish_request, which calls shutdown_request
          - handle_error, which calls shutdown_request

        shutdown_request should call close_request, with the request socket as
        argument.

        :param SSLSocket|socketobject request: The request socket to close.

        """
        super(BofhdServerImplementation, self).close_request(request)
        logger.debug("[%s] closed connection %r", thread_name(), request)
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
        self.db.ping()


class _TCPServer(SocketServer.TCPServer, object):
    """SocketServer.TCPServer as a new-style class."""
    # Must override __init__ here to make the super() call work with only kw args.
    def __init__(self, server_address=None, RequestHandlerClass=None, bind_and_activate=True, **kws):
        # This should always call SocketServer.TCPServer
        super(_TCPServer, self).__init__(server_address=server_address,
                                         RequestHandlerClass=RequestHandlerClass,
                                         bind_and_activate=bind_and_activate,
                                         **kws)

class _ThreadingMixIn(SocketServer.ThreadingMixIn, object):
    """SocketServer.ThreadingMixIn as a new-style class."""
    pass


class BofhdServer(BofhdServerImplementation, _TCPServer):
    """Plain non-encrypted Bofhd server.

    Constructor accepts the following arguments:

      server_address        -- (ipAddr, portNumber) tuple
      RequestHandlerClass   -- class for handling XML-RPC requests
      logRequests           -- boolean
      database              -- Cerebrum Database object
      config_fname          -- name of Bofhd config file

    """
    pass


class ThreadingBofhdServer(BofhdServerImplementation,
                           _ThreadingMixIn,
                           _TCPServer):

    """Threaded non-encrypted Bofhd server.

    Constructor accepts the following arguments:

      server_address        -- (ipAddr, portNumber) tuple
      RequestHandlerClass   -- class for handling XML-RPC requests
      logRequests           -- boolean
      database              -- Cerebrum Database object
      config_fname          -- name of Bofhd config file

    """
    pass


class SSLServer(_TCPServer):

    """ Basic SSL server. """

    def __init__(self, ssl_config=None, bind_and_activate=True, **kws):
        """ Initialize a basic SSL Server.

        :param tuple server_address:
            A tuple with the listening socket address. The tuple should contain
            the bind address or ip, and the bind port.
        :param type RequestHandlerClass:
            The request handler class, preferably a subtype of
            SimpleXMLRPCRequestHandler.
        :param https.SSLConfig ssl_config:
            A configuration object with SSL parameters.
        :param boolean bind_and_activate:
            If bind and activate should be performed on init.

        """
        assert isinstance(ssl_config, https.SSLConfig)
        self.ssl_config = ssl_config

        # We cannot let the superclss perform bind_and_activate before we wrap
        # the socket.
        super(SSLServer, self).__init__(bind_and_activate=False, **kws)

        self.socket = ssl_config.wrap_socket(self.socket, server=True)

        if bind_and_activate:
            self.server_bind()
            self.server_activate()


class SSLBofhdServer(BofhdServerImplementation, SSLServer):

    """SSL-enabled Bofhd server.

    Constructor accepts the following arguments:

      server_address        -- (ipAddr, portNumber) tuple
      RequestHandlerClass   -- class for handling XML-RPC requests
      logRequests           -- boolean
      database              -- Cerebrum Database object
      config_fname          -- name of Bofhd config file
      ssl_context           -- SSL.Context object

    """
    pass


class ThreadingSSLBofhdServer(BofhdServerImplementation,
                              _ThreadingMixIn,
                              SSLServer):
    """SSL-enabled threaded Bofhd server.

    Constructor accepts the following arguments:

      server_address        -- (ipAddr, portNumber) tuple
      RequestHandlerClass   -- class for handling XML-RPC requests
      logRequests           -- boolean
      database              -- Cerebrum Database object
      config_fname          -- name of Bofhd config file
      ssl_context           -- SSL.Context object

    """
    pass

# TODO: ^^ move to Cerebrum.modules.bofhd.server ^^

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
            obj = self.active_connections[thread_name()]
        except KeyError:
            # TODO:
            # - limit max # of simultaneously used db-connections
            # - reduce size of free_pool when size > N
            _db_pool_lock.acquire()
            logger.debug("[%s] alloc new db-handle", thread_name())
            running_threads = []
            for t in threading.enumerate():
                running_threads.append(t.getName())
            logger.debug("  Threads: " + str(running_threads))
            for p in self.active_connections.keys():
                if p not in running_threads:
                    logger.debug("  Close " + p)
                    # self.active_connections[p].close()
                    self.free_pool.append(self.active_connections[p])
                    del(self.active_connections[p])
            if not self.free_pool:
                obj = self._obj_class()
            else:
                obj = self.free_pool.pop(0)
            self.active_connections[thread_name()] = obj
            logger.debug("  Open: " + str(self.active_connections.keys()))
            _db_pool_lock.release()
        return getattr(obj, attrib)


def test_help(config, target):
    """ Run a consistency-check of help texts and exit.

    Note: For this to work, Cerebrum must be set up with a
    cereconf.BOFHD_SUPERUSER_GROUP with at least one member.

    :param string config: The path of the bofhd configuration file.
    :param string target: The help texts test

    """
    db = Utils.Factory.get('Database')()
    server = BofhdServerImplementation(database=db, config_fname=config)
    error = lambda reason: SystemExit("Cannot list help texts: %s" % reason)

    # Fetch superuser
    try:
        const = Utils.Factory.get("Constants")()
        group = Utils.Factory.get('Group')(db)
        group.find_by_name(cereconf.BOFHD_SUPERUSER_GROUP)
        superusers = [int(x["member_id"]) for x in group.search_members(
            group_id=group.entity_id, indirect_members=True,
            member_type=const.entity_account)]
        some_superuser = superusers[0]
    except AttributeError:
        raise error("No superuser group defined in cereconf")
    except Errors.NotFoundError:
        raise error("Superuser group %s not found" %
                    cereconf.BOFHD_SUPERUSER_GROUP)
    except IndexError:
        raise error("No superusers in %s" % cereconf.BOFHD_SUPERUSER_GROUP)

    # Fetch commands
    commands = {}
    for inst in server.cmd_instances:
        newcmd = inst.get_commands(some_superuser)
        for k in newcmd.keys():
            if inst is not server.cmd2instance[k]:
                print "Skipping:", k
                continue
            commands[k] = newcmd[k]

    # Action
    if target == '' or target == 'all' or target == 'general':
        print server.help.get_general_help(commands)
    elif target == 'check':
        server.help.check_consistency(commands)
    elif target.find(":") >= 0:
        print server.help.get_cmd_help(commands, *target.split(":"))
    else:
        print server.help.get_group_help(commands, target)
    raise SystemExit()


if __name__ == '__main__':
    import argparse

    auth_dir = lambda f: "%s/%s" % (getattr(cereconf, 'DB_AUTH_DIR', '.'), f)

    argp = argparse.ArgumentParser(description=u"The Cerebrum bofh server")
    argp.add_argument('-c', '--config-file',
                      required=True,
                      default=None,
                      dest='conffile',
                      metavar='<config>',
                      help=u"The bofh configuration file")
    argp.add_argument('-H', '--host',
                      default='0.0.0.0',
                      metavar='<hostname>',
                      help='Host binding IP-address or domain name')
    argp.add_argument('-p', '--port',
                      default=8000,
                      type=int,
                      metavar='<port>',
                      help='Listen port')
    argp.add_argument('--unencrypted',
                      default=True,
                      action='store_false',
                      dest='use_encryption',
                      help='Run the server without encryption')
    argp.add_argument('-m', '--multi-threaded',
                      default=False,
                      action='store_true',
                      dest='multi_threaded',
                      help='Run multi-threaded (experimental)')
    argp.add_argument('-t', '--test-help',
                      default=None,
                      dest='test_help',
                      metavar='<test type>',
                      help='Check the consistency of help texts')
    argp.add_argument('--ca',
                      default=auth_dir('ca.pem'),
                      dest='ca_file',
                      metavar='<PEM-file>',
                      help='CA certificate chain')
    argp.add_argument('--cert',
                      default=auth_dir('server.cert'),
                      dest='cert_file',
                      metavar='<PEM-file>',
                      help='Server certificate and private key')
    args = argp.parse_args()

    if args.test_help is not None:
        test_help(args.conffile, args.test_help)
        # Will exit

    logger.info("Server (%s) connected to DB '%s' starting at port: %d",
                "multi-threaded" if args.multi_threaded else "single-threaded",
                cereconf.CEREBRUM_DATABASE_NAME, args.port)

    if args.multi_threaded:
        db = ProxyDBConnection(Utils.Factory.get('Database'))
    else:
        db = Utils.Factory.get('Database')()

    # All BofhdServerImplementations share these arguments
    server_args = {
        'server_address': (args.host, args.port),
        'database': db,
        'config_fname': args.conffile
    }

    if args.use_encryption:
        logger.info("Server using encryption")
        ssl_config = https.SSLConfig(ca_certs=args.ca_file,
                                     certfile=args.cert_file)
        ssl_config.set_ca_validate(ssl_config.OPTIONAL)
        server_args['ssl_config'] = ssl_config

        if args.multi_threaded:
            cls = ThreadingSSLBofhdServer
        else:
            cls = SSLBofhdServer
    else:
        logger.warning("Server *NOT* using encryption")

        if args.multi_threaded:
            cls = ThreadingBofhdServer
        else:
            cls = BofhdServer
    server = cls(**server_args)
    server.serve_forever()
