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
import cereconf

import sys
import socket
import xmlrpclib
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
from xml.parsers.expat import ExpatError

from Cerebrum import https
from Cerebrum import Errors
from Cerebrum import QuarantineHandler
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.xmlutils import xmlrpc_to_native, native_to_xmlrpc
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.bofhd.errors import SessionExpiredError
from Cerebrum.modules.bofhd.errors import ServerRestartedError
from Cerebrum.modules.bofhd.errors import UnknownError
from Cerebrum.modules.bofhd.session import BofhdSession

from Cerebrum.modules import statsd


format_addr = lambda addr: ':'.join([str(x) for x in addr or ['err', 'err']])
""" Get ip:port formatted string from address tuple. """


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
        except NotImplementedError as e:
            self.logger.warn(u'Not-implemented: ', exc_info=1)
            raise CerebrumError(u'Not Implemented: {!s}'.format(str(e)))
        except TypeError as e:
            if (str(e).find("takes exactly") != -1 or
                    str(e).find("takes at least") != -1 or
                    str(e).find("takes at most") != -1):
                raise CerebrumError(str(e))
            self.logger.error(u'Unexpected exception', exc_info=1)
            raise UnknownError(sys.exc_info()[0],
                               sys.exc_info()[1],
                               msg=u'A server error has been logged.')
        except Exception as e:
            self.logger.error(u'Unexpected exception', exc_info=1)
            raise UnknownError(sys.exc_info()[0],
                               sys.exc_info()[1],
                               msg=u'A server error has been logged.')
        finally:
            self.db_close()

        return native_to_xmlrpc(ret)

    def handle(self):
        """ Handle request and timeout. """
        try:
            super(BofhdRequestHandler, self).handle()
        except socket.timeout, e:
            # Timeouts are not 'normal' operation.
            self.logger.info(u'timeout: %s from %s',
                             e, format_addr(self.client_address))
            self.close_connection = 1
        except https.SSLError, e:
            # SSLError could be a timeout, or it could be some other form of
            # error
            self.logger.info(u'SSLError: %s from %s',
                             e, format_addr(self.client_address))
            self.close_connection = 1

    def do_POST(self):
        """Handles the HTTP POST request.

        Attempts to interpret all HTTP POST requests as XML-RPC calls,
        which are forwarded to the _dispatch method for handling.

        Will also encode known and unknown exceptions as XMLRPC Faults to the
        client.
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
                self.logger.debug2(u'dispatch %s', method)

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
            except Exception:
                self.logger.warn(
                    u'Unexpected exception 1 (client=%r, params=%r, method=%r)',
                    self.client_address, params, method,
                    exc_info=True)
                # report exception back to server
                response = xmlrpclib.dumps(
                    xmlrpclib.Fault(1, "%s:%s" % (sys.exc_type,
                                                  sys.exc_value)))
            else:
                response = xmlrpclib.dumps(response, methodresponse=1)
        except ExpatError as e:
            # a malformed XMLRPC request should end up here.
            self.logger.warn(
                u'ExpatError ({code}) - malformed XML content detected '
                u'(client {client}, data={data})'.format(
                    code=e.code,
                    client=self.client_address,
                    data=data))
            self.send_response(500)
            self.end_headers()
        except Exception:
            self.logger.error(
                u'Unexpected exception 2 (client %r, data=%r)',
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
        self.logger.debug2(u'thread done')

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
            if not (str(Quarantine(qrow['quarantine_type'])) in nonlock):
                active.append(qrow['quarantine_type'])
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
                if isinstance(uname, unicode):
                    uname = uname.encode('utf-8')
                self.logger.info(
                    u'Failed login for %s from %s: unknown username',
                    uname, format_addr(self.client_address))
                raise CerebrumError("Unknown username or password")

            if isinstance(password, unicode):  # crypt.crypt don't like unicode
                # TODO: ideally we should not hardcode charset here.
                password = password.encode('iso8859-1')
            if not account.verify_auth(password):
                stats.incr('deny-creds')
                self.logger.info(
                    u'Failed login for %s from %s: password mismatch',
                    uname, format_addr(self.client_address))
                raise CerebrumError("Unknown username or password")

            # Check quarantines
            quarantines = self._get_quarantines(account)
            if quarantines:
                stats.incr('deny-quarantine')
                self.logger.info(
                    'Failed login for %s from %s: quarantines %s',
                    uname, format_addr(self.client_address),
                    ', '.join(quarantines))
                raise CerebrumError(
                    'User has active quarantines, login denied: %s' %
                    ', '.join(quarantines))

            # Check expire_date
            if account.is_expired():
                stats.incr('deny-expire')
                self.logger.info(
                    'Failed login for %s from %s: account expired',
                    uname, format_addr(self.client_address))
                raise CerebrumError('User is expired, login denied')

            try:
                self.logger.info(
                    'Successful login for %s from %s',
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
            # suggestion['str'] = unicode(suggestion['str'], 'iso8859-1')
            return suggestion
        # TODO:  Would be better to allow xmlrpc-wrapper to handle None
        return ''

    def bofhd_get_motd(self, client_id=None, client_version=None):
        ret = ""
        if cereconf.BOFHD_MOTD_FILE is not None:
            f = file(cereconf.BOFHD_MOTD_FILE)
            for line in f.readlines():
                ret += line.decode('utf8')
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

        self.logger.debug(u'Run command: %s (%s) by %i', cmd, args, entity_id)
        if cmd not in self.server.classmap:
            raise CerebrumError(u"Illegal command '{!s}'".format(cmd))

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
            self.logger.debug(u'prompt_func: %r', args)
            instance = cls(self.db, self.logger)
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
