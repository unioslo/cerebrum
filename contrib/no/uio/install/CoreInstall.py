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


__doc__ = """ """

__version__ = "$Revision$"
# $Source$

from Framework import *

class Init(CerebrumInstallationModule):

    """Responsible for setting up the bare minimum for starting the
    installation.

    E.g. checking that the database exists, the designated
    cerebrum-user exists, and so forth."""
    
    def __init__(self, installation_queue_controller):
        CerebrumInstallationModule.__init__(self, installation_queue_controller)
        # This module has no prereqs; use super's empty list


    def __str__(self):
        """String representation of this module's 'qualified' name,
        i.e. 'module:class'

        """
        return "CoreInstall:Init"


    def postgres_tests(self):
        """Runs through basic connectivity and functionality tests for
        Postgres DB.

        """
        work_start("Checking that we can connect to database")
        import psycopg
        conn_info = "host=localhost dbname=cerebrum user=cerebrum password=cerebrum"
        try:
            connection = psycopg.connect(conn_info)
        except psycopg.OperationalError, error:
            sys.stdout.flush()  # To dump anything waiting before reporting errors
            logging.error(error)
            raise CerebrumInstallationError("Unable to connect to database with given parameters: '%s'"
                                            % conn_info)
        work_end()
        
        work_start("Checking that we can do stuff in database")

        cursor = connection.cursor()
        logging.debug("===> CREATE TABLE")
        cursor.execute("""CREATE TABLE installtest (
                          col1   CHAR VARYING(16)  PRIMARY KEY,
                          col2   CHAR VARYING(512) NOT NULL);""")
        connection.commit()

        logging.debug("===> INSERT")
        cursor.execute("INSERT INTO installtest VALUES ('Testing', 'testing')")
        connection.commit()

        logging.debug("===> UPDATE")
        cursor.execute("UPDATE installtest SET col2 = 'more testing' " +
                       "WHERE col1 LIKE 'Testing'")
        connection.commit()

        logging.debug("===> DELETE")
        cursor.execute("DELETE FROM installtest WHERE col1 LIKE 'Testing'")
        connection.commit()

        logging.debug("===> DROP TABLE")
        cursor.execute("DROP TABLE installtest")
        connection.commit()

        work_end()


    def install(self):
        """Does the actual installation for this module."""
        data = CerebrumInstallationData()
        
        work_start("Checking Python version")
        check_python_version(atleast=(2,3), atmost=(2,3))  # Need to change later
        work_end()

        work_start("Checking basic Python modules needed")
        for module_to_check in ["ldap", "psycopg", "M2Crypto", "mx"]:
            check_python_library(module=module_to_check)
        work_end()

        cere_user = ask_user(info="Cerebrum usually operates as a non-root user.",
                             question="Which user should this be?",
                             default = "cerebrum",
                             env = "CEREINSTALL_USER")
        cere_group = ask_user(question="Which group is this user part of?",
                              default = "cerebrum",
                              env = "CEREINSTALL_GROUP")
        
        work_start("Verifying user and group")
        check_cerebrum_user(user=cere_user, group=cere_group)
        data["CEREINSTALL_USER"] = cere_user
        data["CEREINSTALL_GROUP"] = cere_group
        work_end()

        syspath = sys.path
        syspath.reverse()
        cerepath_suggestion = syspath[0]
        for directory in syspath:
            if directory.find("site-packages") > 0:
                cerepath_suggestion = directory
                break            
        
        cerepath_dir = ask_user(info="Cerebrum needs to place a file within PYTHONPATH that will " +
                                "be used to define/determine where the other parts of the " +
                                "installation are. The suggested directory seems to be a suitable " +
                                "one; if you select a different one, you must ensure yourself that " +
                                "it is found in PYTHONPATH.",
                                question="Where should cerebrum_path.py be placed?",
                                default=cerepath_suggestion,
                                env="CEREBRUM_PATH_DIR")
        data["CEREBRUM_PATH_DIR"] = cerepath_dir

        work_start("Setting up cerebrum_path.py")
        copy_files(source=data["SRCDIR"] + "/cerebrum_path.py.in", destination=cerepath_dir,
                   owner=None, group=None, rename="cerebrum_path.py")
        # Need to expand with adding directory overviews to cerebrum_path.py
        work_end()

        self.postgres_tests()

        return True


class Core(CerebrumInstallationModule):

    """Installs the things need for a basic Cerebrum installation."""

    def __init__(self, installation_queue_controller):
        CerebrumInstallationModule.__init__(self, installation_queue_controller)
        self.prerequisite_modules = ["CoreInstall:Init"]

        
    def __str__(self):
        """String representation of this module's 'qualified' name, i.e. 'module:class'"""
        return "CoreInstall:Core"


    def install(self):
        """Does the actual installation for this module."""
        
        return True
