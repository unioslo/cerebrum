# -*- coding: utf-8 -*-
# Copyright 2005 University of Oslo, Norway
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

from __future__ import unicode_literals
import sys
import getopt

from Cerebrum.modules.abcenterprise.ABCUtils import ABCFactory


# TODO:
# * Map types to variables i <properties>. Check these variables against
#   allowed types defined in abcconf. Make assert_type()?
#
# * Pending sync with igorr's work.
#
# * Move more into ABCFactory. Make classes Mixin-friendly.
#
# * Abstraction layer between Analyzer and output modules actually
#   doing something.
#
# * Add a layer between ABCXmlWriter and the Analyzer.


####################################################################
# PreParser
####################################################################

class Settings:
    """Empty class for storing 'global' variables. Can be sub-classed
    when writing Mixins"""

    def __init__(self):
        self.variables = dict()

    def set(self, type, value):
        self.variables[type] = value

    def get(self, type):
        return self.variables[type]


class ABCPreParser:
    """Class for parsing opts"""

    # TBD: make a pool of arguments different classes commit
    # parameters to? ex: Let properties-module issue warnings instead
    # of errors on config/file mimatch on a given parameter.

    def __init__(self, argv, logger):
        self.short_args = 'hdf:'
        self.long_args = ['help', 'dru-run', 'file=']

        self.logger = logger

        filename = dryrun = None
        try:
            opts, args = getopt.getopt(argv,
                                       self.short_args,
                                       self.long_args)
        except getopt.GetoptError as e:
            self.logger.warning(e)
            self.usage(1)

        for opt, val in opts:
            if opt in ('-h', '--help'):
                self.usage()
            elif opt in ('-d', '--dry-run'):
                dryrun = True
            elif opt in ('-f', '--file='):
                filename = val
        if filename is None:
            # TBD: let config decide? Set a default?
            self.usage(1)
        self.settings = ABCFactory.get('Settings')()
        self.settings.set('filename', filename)
        self.settings.set('dryrun', dryrun)

    def usage(self, exit_code=0):
        print("""
        -h, --help         This message
        -d, --dry-run      Dry-run import
        -f, --file <file>  File to parse
        """)
        sys.exit(exit_code)

    def get_settings(self):
        return self.settings


####################################################################
# Analyser
####################################################################

class ABCAnalyzer(object):
    """Analyze the data from the XML-parser. Uses ElementTree
    http://effbot.org/zone/element-index.htm as parser. ElementTree
    can be replaced for cElementTree for speed.

    Calls PreParser from ABCFactory. Gets a GlobalVariables object
    in return. Use Mixins for more options."""

    def __init__(self, argv, logger):
        # Get argv into variables and make am object for all of it
        pp = ABCFactory.get('PreParser')(argv, logger)
        self.settings = pp.get_settings()
        self._populate_settings()
        self.logger = logger

        proc = ABCFactory.get('Processor')(self.settings, self.logger)
        # Make calls into the Processor. This is where magic happens...
        logger.debug("parse_settings()")
        proc.parse_settings()

        logger.debug("parse_orgs()")
        proc.parse_orgs(self.iter_orgs())

        logger.debug("parse_persons()")
        proc.parse_persons(self.iter_persons())

        logger.debug("parse_groups()")
        proc.parse_groups(self.iter_groups())

        logger.debug("parse_relations()")
        proc.parse_relations(self.iter_relations())

        logger.debug("close()")
        proc.close()

    def _populate_settings(self):
        setiter = self.iter_properties()
        (self.settings.variables['datasource'],
         self.settings.variables['target'],
         self.settings.variables['timestamp']) = setiter.next()

    def _get_iterator(self, element):
        return iter(ABCFactory.get('EntityIterator')(
            self.settings.variables['filename'],
            element))

    def iter_properties(self):
        return ABCFactory.get('PropertiesParser')(
            self._get_iterator("properties"))

    def iter_persons(self):
        return ABCFactory.get('PersonParser')(
            self._get_iterator("person"))

    def iter_orgs(self):
        return ABCFactory.get('OrgParser')(
            self._get_iterator("organization"))

    def iter_groups(self):
        return ABCFactory.get('GroupParser')(
            self._get_iterator("group"))

    def iter_relations(self):
        return ABCFactory.get('RelationParser')(
            self._get_iterator("relation"))
