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

# $Id$
""" Server used by clients that wants to access the cerebrum database.

Work in progress, current implementation, expect big changes


Configuration
-------------

BOFHD_SUPERUSER_GROUP
    A group of bofh superusers. Members of this group will have access to all
    bofhd commands. The value should contain the name of the group.

DB_AUTH_DIR
    General cerebrum setting. Contains the path to a folder with protected
    data.  Bofhd expects to find certain files in this directory:

    TODO: Server certificate
    TODO: Database connection -- general file, but also needed by bofhd

"""
import cereconf

import operator
import os
import thread
import threading

from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum import https

import Cerebrum.modules.bofhd.server as bofhd_server
import Cerebrum.modules.bofhd.session as bofhd_session
import Cerebrum.modules.bofhd.config as bofhd_config

# An installation *may* have many instances of bofhd running in parallel. If
# this is the case, make sure that all of the instances get their own
# logger. Otherwise, depending on the logger used, the physical entity
# representing the log (typically a file) may not cope with multiple processes
# writing to it simultaneously.
logger = Utils.Factory.get_logger("bofhd")


def thread_name():
    """ Get current thread name. """
    # FIXME: Used in log messages, fix log format to get this automatically
    return threading.currentThread().getName()

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

    :param BofhdConfig config: The bofhd configuration.
    :param string target: The help texts test

    """
    db = Utils.Factory.get('Database')()
    server = bofhd_server.BofhdServerImplementation(logger=logger,
                                                    bofhd_config=config)

    def error(reason):
        return SystemExit("Cannot list help texts: {0}".format(reason))

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
        print server.cmdhelp.get_general_help(commands)
    elif target == 'check':
        server.help.check_consistency(commands)
    elif target.find(":") >= 0:
        print server.cmdhelp.get_cmd_help(commands, *target.split(":"))
    else:
        print server.cmdhelp.get_group_help(commands, target)


def auth_dir(filename):
    return os.path.join(getattr(cereconf, 'DB_AUTH_DIR', '.'), filename)


if __name__ == '__main__':
    import argparse

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
                      help='Run multi-threaded')
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
    argp.add_argument('--ssl-version',
                      default=list(https.SSL_VERSION.values())[-1],
                      dest='ssl_version',
                      metavar='<version>',
                      choices=list(https.SSL_VERSION.keys()),
                      help='SSL protocol version (default: %(default)s, '
                           'available: %(choices)s)')

    args = argp.parse_args()

    # Read early to fail early
    config = bofhd_config.BofhdConfig(args.conffile)

    if args.test_help is not None:
        test_help(config, args.test_help)
        raise SystemExit()

    logger.info("Server (%s) starting at %s:%d",
                "multi-threaded" if args.multi_threaded else "single-threaded",
                args.host, args.port)

    # All BofhdServerImplementations share these arguments
    server_args = {
        'server_address': (args.host, args.port),
        'bofhd_config': config,
        'logger': logger,
    }

    if args.use_encryption:
        ssl_config = https.SSLConfig(ca_certs=args.ca_file,
                                     certfile=args.cert_file)
        ssl_config.set_ca_validate(ssl_config.OPTIONAL)
        ssl_config.set_ssl_version(args.ssl_version)
        server_args['ssl_config'] = ssl_config
        logger.info("Server using encryption (%s)", args.ssl_version)

        if args.multi_threaded:
            cls = bofhd_server.ThreadingSSLBofhdServer
        else:
            cls = bofhd_server.SSLBofhdServer
    else:
        logger.warning("Server *NOT* using encryption")

        if args.multi_threaded:
            cls = bofhd_server.ThreadingBofhdServer
        else:
            cls = bofhd_server.BofhdServer

    # Check and cache constants
    # Note: This will cause a single persistent connection to the database,
    #       which is caused by the caching of constants in
    #       Cerebrum.Constants._CerebrumCode. The persisten connection will be
    #       set up sooner or later anyway.
    #       This *should* be OK, but we need to re-consider the design of this
    #       cache
    logger.debug("Caching constants...")
    constants = Utils.Factory.get('Constants')()
    constants.cache_constants()
    del constants
    logger.debug("Done caching constants")

    # Log short timeout values
    bofhd_session.BofhdSession._log_short_timeouts(logger)

    server = cls(**server_args)
    server.serve_forever()
