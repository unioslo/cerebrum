#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2002-2016 University of Oslo, Norway
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
""" Request handler for bofhd.

Configuration
-------------
This module actively uses the cereconf variables:

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


Metrics
-------

<prefix>.bofhd.dispatch.<method>
    Each dispatch to a function 'bofhd_<method>' is counted (e.g. bofhd_motd or
    bofhd_logout).

<prefix>.bofhd.login.<result>
    Each call to bofhd_login is counted per <result> (allow, deny-creds,
    deny-expire, deny-quarantine, deny-error).

<prefix>.bofhd.command.<func>
    Each call to bofhd_run_command is timed and counted per command:

    <prefix>.bofhd.command.<func>.time measures command duration
    <prefix>.bofhd.command.<func>.success counts successful executions
    <prefix>.bofhd.command.<func>.error counts failed executions


History
-------
This class used to be a part of the bofhd server script itself. It was
moved to a separate module after:

    commit ff3e3f1392a951a059020d56044f8017116bb69c
    Merge: c57e8ee 61f02de
    Date:  Fri Mar 18 10:34:58 2016 +0100

"""

from __future__ import unicode_literals

import cereconf

import io
import socket
import warnings
import xmlrpclib
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
from xml.parsers.expat import ExpatError

import six

from Cerebrum import (
    Errors,
    QuarantineHandler,
    https,
)
from Cerebrum.Utils import Factory
from Cerebrum.modules import statsd
from Cerebrum.modules.bofhd.errors import (
    CerebrumError,
    ServerRestartedError,
    SessionExpiredError,
    UnknownError,
)
from Cerebrum.modules.bofhd.session import BofhdSession
from Cerebrum.modules.bofhd.xmlutils import xmlrpc_to_native, native_to_xmlrpc


fault_codes = {CerebrumError: 1}


def format_addr(addr):
    """ Get ip:port formatted string from address tuple. """
    return ':'.join((six.text_type(x) for x in addr or ['err', 'err']))


def exc_to_text(e):
    """ Get an error text from an exception. """
    try:
        text = six.text_type(e)
    except UnicodeError:
        # We don't want error handling to fail. Decode without failing, and
        # issue a warning so that the exception can be fixed.
        text = bytes(e).decode('utf-8', 'replace')
        warnings.warn("Non-unicode data in exception {!r}".format(e),
                      UnicodeWarning)
    return text


class BofhdRequestHandler(SimpleXMLRPCRequestHandler, object):

    """Class defining all XML-RPC-callable methods.

    These methods can be called by anyone with access to the port that
    the server is running on.  Care must be taken to validate input.

    """
    def db_get(self):
        u""" A transactional database connection. """
        try:
            return self.__db
        except AttributeError:
            self.__db = Factory.get('Database')()
            return self.__db

    def db_close(self):
        u""" Closes database connection in `self.db`. """
        try:
            self.__db.close()
            del self.__db
        except AttributeError:
            pass

    def db_rollback(self):
        u""" Rolls back database transaction in `self.db`. """
        try:
            return self.__db.rollback()
        except AttributeError:
            return None

    def db_commit(self):
        u""" Commits database transaction in `self.db`. """
        try:
            return self.__db.commit()
        except AttributeError:
            return None

    db = property(fget=db_get, fdel=db_close, doc=db_get.__doc__)

    @property
    def logger(self):
        return self.server.logger

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

        stats_client = statsd.make_client(self.server.stats_config,
                                          prefix="bofhd.dispatch")
        stats_client.incr(method)

        try:
            ret = apply(func, xmlrpc_to_native(params))
        except CerebrumError as e:
            exc_type = type(e)
            raise exc_type(exc_to_text(e))
        except NotImplementedError as e:
            self.logger.error('NotImplemented', exc_info=1)
            raise CerebrumError('Not implemented: {!s}'.format(exc_to_text(e)))
        except TypeError as e:
            err = exc_to_text(e)
            if (err.find("takes exactly") != -1
                    or err.find("takes at least") != -1
                    or err.find("takes at most") != -1):
                raise CerebrumError(err)
            self.logger.error('Unexpected exception', exc_info=1)
            raise UnknownError(type(e),
                               err,
                               msg='A server error has been logged.')
        except Exception as e:
            self.logger.error('Unexpected exception', exc_info=1)
            raise UnknownError(type(e),
                               exc_to_text(e),
                               msg='A server error has been logged.')
        finally:
            self.db_close()
        return native_to_xmlrpc(ret)

    def handle(self):
        """ Handle request and timeout. """
        try:
            super(BofhdRequestHandler, self).handle()
        except socket.timeout as e:
            # Timeouts are not 'normal' operation.
            self.logger.info('timeout: %s from %s',
                             exc_to_text(e), format_addr(self.client_address))
            self.close_connection = 1
        except https.SSLError as e:
            # SSLError could be a timeout, or it could be some other form of
            # error
            self.logger.info('SSLError: %s from %s',
                             exc_to_text(e), format_addr(self.client_address))
            self.close_connection = 1

    def send_xmlrpc_response(self, message):
        self._send_raw_xmlrpc((message,))

    def send_xmlrpc_error(self, exc):
        code = fault_codes.get(exc.__class__, 2)
        fault = xmlrpclib.Fault(code, self._format_xmlrpc_fault(exc))
        self._send_raw_xmlrpc(fault)

    def _send_raw_xmlrpc(self, body):
        try:
            # xmlrpclib.dumps() takes either xmlrpclib.Fault
            # or a tuple of return parameters
            payload = xmlrpclib.dumps(body, methodresponse=True)
        except:
            self.logger.error("Unable to serialize to XML-RPC: %r", body, exc_info=True)
            self.send_error(500)
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/xml")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            self.wfile.flush()

    @staticmethod
    def _format_xmlrpc_fault(exc):
        """ Get XMLRPC fault string from an exception. """
        # Stringify the exception type
        err_type = six.text_type(type(exc).__name__)
        if isinstance(exc, CerebrumError):
            # Include module name in CerebrumError and subclasses
            if type(exc) in (ServerRestartedError, SessionExpiredError,
                             UnknownError):
                # Client *should* know this
                err_type = u'{0.__module__}.{0.__name__}'.format(type(exc))
            else:
                # Use superclass
                err_type = u'{0.__module__}.{0.__name__}'.format(CerebrumError)

        return u'{err_type}:{err_msg}'.format(err_type=err_type,
                                              err_msg=exc_to_text(exc))

    def do_POST(self):
        """
        Handles HTTP POST requests.

        All POST requests are assumed to be valid XML-RPC structures.
        Once deserialized they are forwarded to ``_dispatch()``.

        Exceptions that occur within ``_dispatch()`` are encoded
        and returned as ``xmlrpclib.Fault``s, where the error code 1
        indicates a Cerebrum issue and 2 an unexpected internal error.
        """
        data = params = method = None

        # Check for required Content-Length
        try:
            content_length = self.headers["content-length"]
        except KeyError:
            self.logger.warn("Missing Content-Length (client=%r)", self.client_address)
            self.send_error(411)
            return

        # Read and parse request data
        #
        # A note on encoding: xmlrpclib expects a bytestring, and assumes utf-8
        # encoding unless otherwise specified in the root element.
        # Any non-ascii data is returned from `loads` as unicode-objects, and
        # anything else as ascii-bytestrings.
        try:
            data = self.rfile.read(int(content_length))
            params, method = xmlrpclib.loads(data)
        except ExpatError:
            self.logger.warn(
                "Unable to deserialize request to XML-RPC (client=%r, data=%r)",
                self.client_address,
                data,
                exc_info=True,
            )
            self.send_error(400)
            return
        except:
            self.logger.warn(
                "Unknown client error (client=%r, data=%r)",
                self.client_address,
                data,
                exc_info=True,
            )
            self.send_error(400)
            return

        # XML-RPC structure is decoded and valid, try to dispatch
        try:
            self.logger.debug("dispatch method=%r", method)
            rv = self._dispatch(method, params)
        except CerebrumError as e:
            self.send_xmlrpc_error(e)
        except Exception as e:
            self.logger.warn(
                "Unexpected exception (client=%r, params=%r, method=%r)",
                self.client_address,
                params,
                method,
                exc_info=True,
            )
            self.send_xmlrpc_error(e)
        else:
            self.send_xmlrpc_response(rv)

    def _get_quarantines(self, account):
        """ Fetch a list of active lockout quarantines for account.

        :param Cerebrum.Account account: The account to fetch quarantines for.

        :return list:
            A list of strings representing each active, lockout quarantines
            that affects the account.
        """
        const = Factory.get('Constants')(self.db)
        Quarantine = const.Quarantine
        nonlock = getattr(cereconf, 'BOFHD_NONLOCK_QUARANTINES', [])
        active = []

        for q_type in (qrow['quarantine_type'] for qrow
                       in account.get_entity_quarantine(only_active=True)):
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
            if six.text_type(Quarantine(q_type)) not in nonlock:
                active.append(q_type)
        qh = QuarantineHandler.QuarantineHandler(self.db, active)
        if qh.should_skip() or qh.is_locked():
            return [Quarantine(q).description for q in active]
        return []

    def bofhd_login(self, uname, password):
        """ Authenticate and create session.

        :param string uname: The username
        :param string password: The password, preferably in latin-1

        :return string:
            If authentication is successful, a session_id registered in
            BofhdSession is returned. This session_id can be used to run
            commands that requires authentication.

        :raise CerebrumError: If the user is not allowed to log in.

        """
        stats_client = statsd.make_client(self.server.stats_config,
                                          prefix="bofhd.login")

        account = Factory.get('Account')(self.db)
        with stats_client.pipeline() as stats:
            try:
                account.find_by_name(uname)
            except Errors.NotFoundError:
                stats.incr('deny-creds')
                self.logger.info(
                    'Failed login for %r from %r: unknown username',
                    uname, format_addr(self.client_address))
                raise CerebrumError("Unknown username or password")

            if not account.verify_auth(password):
                stats.incr('deny-creds')
                self.logger.info(
                    'Failed login for %r from %r: password mismatch',
                    uname, format_addr(self.client_address))
                raise CerebrumError("Unknown username or password")

            # Check quarantines
            quarantines = self._get_quarantines(account)
            if quarantines:
                stats.incr('deny-quarantine')
                self.logger.info(
                    'Failed login for %r from %r: quarantines %s',
                    uname, format_addr(self.client_address), quarantines)
                raise CerebrumError(
                    'User has active quarantines, login denied: %s' %
                    ', '.join(quarantines))

            # Check expire_date
            if account.is_expired():
                stats.incr('deny-expire')
                self.logger.info(
                    'Failed login for %r from %r: account expired',
                    uname, format_addr(self.client_address))
                raise CerebrumError('User is expired, login denied')

            try:
                self.logger.info(
                    'Successful login for %r from %r',
                    uname, format_addr(self.client_address))
                session = BofhdSession(self.db, self.logger)
                session_id = session.set_authenticated_entity(
                    account.entity_id, self.client_address[0])
                self.db_commit()
                self.server.sessions[session_id] = str(account.entity_id)
                stats.incr('allow')
                return session_id
            except Exception:
                stats.incr('deny-error')
                self.db_rollback()
                raise

    def bofhd_logout(self, session_id):
        """ The bofhd logout function. """
        session = BofhdSession(self.db, self.logger, session_id)
        # TODO: statsd - gauge active user sessions?
        try:
            session.clear_session()
            if session_id in self.server.sessions:
                del(self.server.sessions[session_id])
            self.db_commit()
        except Exception:
            self.db_rollback()
            raise
        return "OK"

    def __cache_commands(self, ident):
        # TODO: Does this belong in the server?
        if ident not in self.server.commands:
            self.server.commands[ident] = dict()
        for cls in self.server.extensions:
            inst = cls(self.db, self.logger)
            commands = inst.get_commands(ident)
            # Check if implementation is available (see server.load_extensions)
            for key, cmd in commands.iteritems():
                if not key:
                    continue
                if key not in self.server.classmap:
                    continue
                if cls is not self.server.classmap[key]:
                    continue
                self.server.commands[ident][key] = cmd.get_struct(
                    self.server.cmdhelp)
        try:
            return self.server.commands[ident]
        except KeyError:
            return {}

    def bofhd_get_commands(self, session_id):
        """Build a dict of the commands available to the client."""
        session = BofhdSession(self.db, self.logger, session_id)
        ident = int(session.get_entity_id())
        if not ident:
            return {}
        try:
            return self.server.commands[ident]
        except KeyError:
            return self.__cache_commands(ident)

    def bofhd_get_format_suggestion(self, cmd):
        suggestion = self.server.classmap[cmd].get_format_suggestion(cmd)
        if suggestion is not None:
            return suggestion
        # TODO:  Would be better to allow xmlrpc-wrapper to handle None
        return ''

    def bofhd_get_motd(self, client_id=None, client_version=None):
        ret = ""
        if cereconf.BOFHD_MOTD_FILE is not None:
            with io.open(cereconf.BOFHD_MOTD_FILE, encoding='utf-8') as f:
                ret = f.read()
        if (client_id is not None and
                cereconf.BOFHD_CLIENTS.get(client_id, '') > client_version):
            ret += "You do not seem to run the latest version of the client\n"
        return ret[:-1]

    def bofhd_help(self, session_id, *group):
        commands = self.bofhd_get_commands(session_id)
        if len(group) == 0:
            ret = self.server.cmdhelp.get_general_help(commands)
        elif group[0] == 'arg_help':
            ret = self.server.cmdhelp.get_arg_help(group[1])
        elif len(group) == 1:
            ret = self.server.cmdhelp.get_group_help(commands, *group)
        elif len(group) == 2:
            ret = self.server.cmdhelp.get_cmd_help(commands, *group)
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

        if session_id not in self.server.sessions:
            self.server.sessions[session_id] = str(entity_id)
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
        session = BofhdSession(self.db, self.logger)
        session.remove_short_timeout_sessions()
        self.db_commit()

        # Set up session object
        session = BofhdSession(self.db, self.logger, session_id,
                               self.client_address)
        entity_id = self.check_session_validity(session)
        self.db.cl_init(change_by=entity_id)

        self.logger.info(u'Run command: %s (%r) by %i', cmd, args, entity_id)
        if cmd not in self.server.classmap:
            raise CerebrumError("Illegal command {!r}".format(cmd))

        implementation = self.server.classmap[cmd](self.db, self.logger)
        func = getattr(implementation, cmd)

        # We know cmd is a safe statsd-prefix, since it's also a valid
        # attribute name
        stats_client = statsd.make_client(
            self.server.stats_config,
            prefix='bofhd.command.{0}'.format(cmd))

        with stats_client.pipeline() as stats:
            with stats.timer('time'):
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
                    self.db_commit()
                    # TBD: What should be returned if `args' contains tuple,
                    # indicating that `func` should be called multiple times?
                    stats.incr('success')
                    return self.db.pythonify_data(ret)
                except Exception:
                    self.db_rollback()
                    stats.incr('error')
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
        session = BofhdSession(self.db, self.logger, session_id,
                               self.client_address)
        cls, cmdObj = self.server.get_cmd_info(cmd)
        self.check_session_validity(session)
        if cmdObj._prompt_func is not None:
            self.logger.debug('prompt_func: %r', args)
            instance = cls(self.db, self.logger)
            return getattr(instance,
                           cmdObj._prompt_func.__name__)(session, *args)
        raise CerebrumError("Command %r has no prompt func" % (cmd,))

    def bofhd_get_default_param(self, session_id, cmd, *args):
        """ Get default value for a parameter.

        Returns a string. The client should append '[<returned_string>]: ' to
        its prompt.

        Will either use the function defined in the command object, or in the
        corresponding parameter object.

        """
        session = BofhdSession(self.db, self.logger, session_id)
        cls, cmdObj = self.server.get_cmd_info(cmd)

        # If the client calls this method when no default function is defined,
        # it is a bug in the client.
        if cmdObj._default is not None:
            func = cmdObj._default
        else:
            func = cmdObj._params[len(args)]._default
            if func is None:
                return ""
        instance = cls(self.db, self.logger)
        return getattr(instance, func.__name__)(session, *args)
