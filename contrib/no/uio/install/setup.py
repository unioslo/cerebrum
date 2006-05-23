#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2006 University of Oslo, Norway
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
# Set-up program for Cerebrum
#

import getopt
import logging
import sys

from Framework import *

__doc__ = """Cerebrum installation program.

Usage: setup.py [options]

    Options:

    -h, --help           Prints this message.
    -l, --logfile FILE   Logfile that detailed info will be written to.
    -c, --config FILE    Configuration file holding 'new' default values for installation.
    -o, --output FILE    Will dump all configuration values to given file at end of installation.
    -b, --batch          Batch install. No user interaction. Use defaults for all values.

"""

__version__ = "$Revision$"
# $Source$


# Defaults for options
options = {"logfile": "/tmp/cerebrum-install.log",
           "config": None,
           "output": None,
           "modules": ["CoreInstall:Core"],
           }


def init_logging():
    """Initializes logging to commandline and to logfile"""
    logger= logging.getLogger()
    logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(options["logfile"], 'w')
    dateformat='%Y-%m-%d %H:%M:%S'
    file_format = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s', dateformat)
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)
    
    # Let console pick up on stuff >= warnings
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_format = logging.Formatter('\n%(levelname)s: %(message)s')
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    inform_user("Detailed log in '%s'" % options["logfile"])


def usage(message=None):
    """Gives user info on how to use the program and its options."""

    if message is not None:
        print "\n%s\n" % message

    print __doc__


def main(argv=None):
    """Main installation activities."""
    if argv is None:
        argv = sys.argv
    
    try:
        opts, args = getopt.getopt(argv[1:],
                                   "bc:hl:o:",
                                   ["batch", "config=", "help", "logfile=", "output="])
    except getopt.GetoptError, option_error:
        usage(message="ERROR: %s" % option_error)
        return 1

    installation_data = CerebrumInstallationData()

    for opt, val in opts:
        if opt in ('-h', '--help',):
            usage()
            return 0
        elif opt in ('-l', '--logfile',):
            options["logfile"] = val
        elif opt in ('-c', '--config',):
            options["config"] = val
        elif opt in ('-b', '--batch',):
            installation_data["batch"] = True
        elif opt in ('-o', '--output',):
            options["output"] = val

    if os.getuid() != 0:
        usage(message="ERROR: Setup must be run as root-user")
        return 3
    
    init_logging()
    logging.info("Options read and accepted")

    data = CerebrumInstallationData()
    
    if options["config"] is not None:
        # Read option file and load "default" data
        try:
            installenv_file = open(options["config"])
        except IOError, error:
            usage(message="ERROR: %s" % error)
            return 4
            
        for line in installenv_file.read().splitlines():
            components = line.split("=")
            installation_data[components[0]] = components[1]
        installenv_file.close()

    data["SRCDIR"] = os.path.dirname(sys.path[0])  # Parent directory of script
    
    try:
        queue_control = InstallationQueueController(options['modules'])

        while queue_control.queue_is_not_empty():
            current_module = queue_control.get_next_module()
            inform_user("\nStarting to install '%s'" % current_module)
            if current_module.install():
                queue_control.commit(current_module)
            else:
                raise CerebrumInstallationError("Unable to install module '%s' for some reason"
                                                % current_module)
            
    except CerebrumInstallationError, error:
        sys.stdout.flush()  # To dump anything waiting before reporting errors
        logging.error(error)
        logging.critical("Aborting installation")
        return 2
    
    logging.info("Cerebrum installation completed")

    if options["output"] is not None:
        # Dump variables to output-file
        try:
            installenv_file = open(options["output"], "w")
            for element in installation_data:
                if element.startswith("CERE"):
                    installenv_file.write("%s=%s" % (element, installation_data[element]))
        except IOError, error:
            print("Unable to write to file '%s': %s" % (options["output"], error))
                
        installenv_file.close()

    print "\nSUCCESS!\n"


if __name__ == "__main__":
    print sys.path[0]
    sys.exit(main())

