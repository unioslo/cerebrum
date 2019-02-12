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
""" Server implementations for bofhd.

History
-------

This class used to be a part of the bofhd server script itself. It was
moved to a separate module after:

    commit ff3e3f1392a951a059020d56044f8017116bb69c
    Merge: c57e8ee 61f02de
    Date:  Fri Mar 18 10:34:58 2016 +0100

"""
import logging
import signal
import socket
import SocketServer
import sys
import time

from Cerebrum import Utils
from Cerebrum import Cache
from Cerebrum import https
from Cerebrum.Utils import Factory
from Cerebrum.utils.funcwrap import memoize
from Cerebrum.modules.bofhd.handler import BofhdRequestHandler, format_addr
from Cerebrum.modules.bofhd.help import Help
from Cerebrum.modules.statsd import config as statsd_config


logger = logging.getLogger(__name__)


class BofhdServerImplementation(object):
    """
    Common Server implementation.

    To get a functional server implementation, this class should be mixed in
    with a py:class:`SocketServer.BaseServer` implementation. E.g.:

    ::

        BofhdServer = type(
            'BofhdServer',
            (BofhdServerImplementation, SocketServer.TCPServer),
            {})

    """

    def __init__(
            self, bofhd_config=None, logRequests=False, logger=None, **kws):
        """ Set up a new bofhd server.

        :param BofhdConfig bofhd_config:
            A bofhd extension configuration.

        """
        self.__config = bofhd_config
        self.logger = logger.getChild('BofhdServerImplementation')
        super(BofhdServerImplementation, self).__init__(**kws)
        # TODO: logRequests is not really used anywhere?
        #       At least not here nor in SocketServer
        self.logRequests = logRequests
        self.load_extensions()
        # TODO: Not really used either
        self.server_start_time = time.time()

    @property
    @memoize
    def classmap(self):
        u""" Map of command_names and implementation classes.

        Each key is an implemented and callable command, and the value is its
        implementation class.
        """
        return Cache.Cache()

    @property
    def cmdhelp(self):
        """ Combined Help structure for all extensions. """
        try:
            return self.__help
        except AttributeError:
            self.__help = Help(self.extensions, logger=self.logger)
            return self.__help

    @property
    @memoize
    def commands(self):
        """ Cache of commands that a user has access to.

        It should contain info on every accessible command for every
        authenticated user:
            commands[entity_id][command_name] = Command.get_struct()
        """
        return Cache.Cache(
            mixins=[Cache.cache_mru, Cache.cache_slots, Cache.cache_timeout],
            size=500,
            timeout=60 * 60)

    @property
    @memoize
    def sessions(self):
        """ A cache that maps session id to entity id. """
        # Needed? Only used to throw ServerRestartedError...
        return Cache.Cache()

    @property
    @memoize
    def stats_config(self):
        """ Config for storing metrics using statsd. """
        try:
            return statsd_config.load_config()
        except Exception as e:
            self.logger.error("could not load statsd config (%r)", e)
            # default config
            return statsd_config.StatsConfig()

    def _log_help_text_mismatch(self):
        u""" Verify consistency of `self.cmdhelp`.

        Reports mismatch between loaded extensions and available help texts
        using the logger.
        """
        # Check that the help text is okay
        # Reformat the command definitions to be suitable for the help.
        cmds_for_help = dict()
        for cls in self.extensions:
            cmds_for_help.update(
                dict((cmdname, command.get_struct(self.cmdhelp))
                     for cmdname, command
                     in cls.list_commands('all_commands').iteritems()
                     if command and cmdname and self.classmap[cmdname] == cls))

        self.__help.check_consistency(cmds_for_help)

    def _log_command_mismatch(self):
        u""" Verify consistency of `self.classmap`.

        Reports mismatch between loaded extensions and available commands using
        the logger.
        """
        def fmt_class(cls):
            return '{0.__module__}/{0.__name__}'.format(cls)
        for cls in self.extensions:
            commands = cls.list_commands('all_commands')
            for key, cmd in commands.iteritems():
                if not key:
                    self.logger.warn('Skipping: Unnamed command %r', cmd)
                    continue
                if key not in self.classmap:
                    self.logger.warn('Skipping: No command %r in class map',
                                     key)
                    continue
                if cls is not self.classmap[key]:
                    self.logger.info(
                        'Skipping: Duplicate command %r'
                        ' (skipping=%s, using=%s)',
                        key,
                        fmt_class(cls),
                        fmt_class(self.classmap[key]))
                    continue

    def load_extensions(self):
        """ Load BofhdExtensions (commands and help texts).

        This will load and initialize the BofhdExtensions specified by the
        configuration.

        """
        self.extensions = getattr(self, 'extensions', set())
        for cls in self.extensions:
            # Reload existing modules
            reload(sys.modules[cls.__module__])
        self.extensions = set()

        self.classmap.clear()
        self.commands.clear()

        for module_name, class_name in self.__config.extensions():
            mod = Utils.dyn_import(module_name)
            # TODO: Make dyn_import support class name
            try:
                cls = getattr(mod, class_name)
            except AttributeError:
                raise ImportError("Module '{}' has no class '{}'"
                                  .format(module_name, class_name))
            self.extensions.add(cls)

            # Map commands to BofhdExtensions
            # NOTE: Any duplicate command will be overloaded by later
            #       BofhdExtensions.
            for rpc in cls.list_commands('all_commands').keys():
                self.classmap[rpc] = cls
            for rpc in cls.list_commands('hidden_commands').keys():
                self.classmap[rpc] = cls

        # Check that all calls are implemented
        for rpc in sorted(self.classmap.keys()):
            if not hasattr(self.classmap[rpc], rpc):
                self.logger.warn("Warning, command %r is not implemented", rpc)
        self.__help = Help(self.extensions, logger=self.logger)

        self._log_help_text_mismatch()
        self._log_command_mismatch()

    def get_cmd_info(self, rpc_name):
        """Return BofhdExtension and Command object for this cmd
        """
        cls = self.classmap[rpc_name]
        return (cls, cls.list_commands('all_commands')[rpc_name])

    # Override SocketServer.TCPServer (or subclass).
    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        super(BofhdServerImplementation, self).server_bind()
        if hasattr(self, 'server_address'):
            logger.info("Ready to accept connections on %r",
                        format_addr(self.server_address))
        else:
            logger.info("Ready to accept connections")

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
        logger.debug("closed connection %r", request)


class _SigAlrmTimeout(object):
    """
    Context to handle timeouts in a block of code.

    .. warning::
        Only one alarm signal can be scheduled at a time! If anything else
        within the code block sets up or resets a ``signal.alarm()``, or messes
        with the ``signal.SIGALRM`` handler without resetting handlers
        appropriately, this may fail spectacularly!
    """

    class Timeout(Exception):
        """ exception raised on SIGALRM. """
        pass

    def __init__(self, seconds):
        self.timeout = int(seconds)

    @classmethod
    def timeout_handler(cls, signum, frame):
        raise cls.Timeout()

    def __enter__(self):
        self._prev_handler = signal.signal(signal.SIGALRM,
                                           self.timeout_handler)
        signal.alarm(self.timeout)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        signal.alarm(0)
        if self._prev_handler is not None:
            signal.signal(signal.SIGALRM, self._prev_handler)
        del self._prev_handler


class _TCPServer(SocketServer.TCPServer, object):
    """SocketServer.TCPServer as a new-style class."""
    # Must override __init__ here to make the super() call work with only kw
    # args.

    get_request_timeout = 5

    def __init__(
            self,
            server_address=None,
            RequestHandlerClass=BofhdRequestHandler,
            bind_and_activate=True,
            get_request_timeout=get_request_timeout,
            **kws):
        # This should always call SocketServer.TCPServer
        super(_TCPServer, self).__init__(
            server_address=server_address,
            RequestHandlerClass=RequestHandlerClass,
            bind_and_activate=bind_and_activate,
            **kws)
        self.get_request_timeout = int(get_request_timeout)

    def _handle_request_noblock(self):
        """
        Handle one request, without blocking.

        Overrides py:class:`SocketServer.BaseServer` with a timeout for
        ``get_request()``.  This should fix an issue where ``get_request()``
        may actually block and wait for input.

        As ``get_request()`` runs, other client connections will not be
        accepted.  This is a known issue when calling ``socket.accept()`` on
        SSL sockets, which may block and wait for a client handshake
        indefinetely (PySSL_SSLdo_handshake).
        """
        # TODO: We really only support TCPServer implementations, so the
        # timeout is placed here. We may want to move it to:
        #  - BofhdServerImplementation, so it applies to all servers
        #  - _SSLServer, so it only applies to ssl servers.
        start = time.time()
        try:
            with _SigAlrmTimeout(self.get_request_timeout):
                request, client_address = self.get_request()
            logger.info('connection from %r', client_address)
        except _SigAlrmTimeout.Timeout as e:
            logger.warn('connection timed out after %.02fs',
                        time.time() - start)
            return
        except socket.error as e:
            logger.warn('connection failed: %s', e)
            return
        except Exception:
            logger.error('connection failed', exc_info=True)
            return

        if self.verify_request(request, client_address):
            try:
                self.process_request(request, client_address)
            except:
                self.handle_error(request, client_address)
                self.shutdown_request(request)
        else:
            self.shutdown_request(request)


class _ThreadingMixIn(SocketServer.ThreadingMixIn, object):
    """SocketServer.ThreadingMixIn as a new-style class."""

    def process_request_thread(self, request, client_address):
        logger.debug("thread started for client %r", client_address)
        super(_ThreadingMixIn, self).process_request_thread(request,
                                                            client_address)


class BofhdServer(BofhdServerImplementation, _TCPServer):
    """Plain non-encrypted Bofhd server.

    Constructor accepts the following arguments:

      server_address        -- (ipAddr, portNumber) tuple
      RequestHandlerClass   -- class for handling XML-RPC requests
      logRequests           -- boolean
      bofhd_config          -- BofhdConfig object

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
      bofhd_config          -- BofhdConfig object

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
      bofhd_config          -- BofhdConfig object
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
      bofhd_config          -- BofhdConfig object
      ssl_context           -- SSL.Context object

    """
    pass
