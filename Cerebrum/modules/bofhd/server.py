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

Configuration
-------------

This module actively uses the cereconf variables:


History
-------

This class used to be a part of the bofhd server script itself. It was
moved to a separate module after:

    commit ff3e3f1392a951a059020d56044f8017116bb69c
    Merge: c57e8ee 61f02de
    Date:  Fri Mar 18 10:34:58 2016 +0100

"""

import sys
import time
import socket
import threading
import SocketServer

from Cerebrum import Utils
from Cerebrum import https
from Cerebrum.modules.bofhd.config import BofhdConfig
from Cerebrum.modules.bofhd.handler import BofhdRequestHandler
from Cerebrum.modules.bofhd.utils import BofhdUtils
from Cerebrum.modules.bofhd.help import Help

# TODO: Fix me
from Cerebrum.Utils import Factory
logger = Factory.get_logger("bofhd")

thread_name = lambda: threading.currentThread().getName()
""" Get thread name. """

format_addr = lambda addr: ':'.join([str(x) for x in addr or ['err', 'err']])
""" Get ip:port formatted string from address tuple. """


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
    def __init__(self, server_address=None,
                 RequestHandlerClass=BofhdRequestHandler,
                 bind_and_activate=True, **kws):
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
