# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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

import os
import ConfigParser

path = '/home/local/kandal/install/etc/cerebrum' or '.'


def read_conf(conf, name):
	tmpl = os.path.join(path, "%s.template" % name)
	print "Using config %s" % tmpl
	conf.read(tmpl)
	file = os.path.join(path, name)
	print "Using config %s" % file
	conf.read(file)
	return file, tmpl

conf = ConfigParser.ConfigParser()
cereweb_config, cereweb_template = read_conf(conf, 'cereweb.conf')

cherrypy_template = os.path.join(path, 'cherrypy.conf.template')
cherrypy = os.path.join(path, 'cherrypy.conf')

default_options = ConfigParser.ConfigParser()
option_config, option_template = read_conf(default_options, 'options.conf')
