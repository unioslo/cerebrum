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


__doc__ = """
This file contains generic configuration for the web-based password
change service. Most of these values will be overridden for a
particular site, and serve therefore best as examples.

Site-specific overrides will be in 'password_config.py', which is the
file the cgi-script imports to get its configuration. If not all
values are overridden in that file, it should in turn do a 'from
default_password_config import *' to get these default values.

"""

__version__ = "$Revision$"
# $Source$

# Directory with log file, CA certificate file, and warn-timestamp file
WORK_DIR = '/var/www/cerebrum'

# Where to log (both successful and failed) password changes
LOG_FILE = WORK_DIR + '/password.log'

# If this file exists, use it as the message to report downtime.
# If a file with the language as suffix exists, take text of
# message from that instead (e.g., down.html.no-nyn).
DOWNTIME_FLAGFILE = WORK_DIR + "/down.html"

# Bofh server.  MUST start with 'https:' to get an encrypted connection.
BOFH_URL = 'https://localhost:8000/'

# Where to find the CA certificate for bofhd.
# The file contains one or more certificates concatenated together.
CACERT_FILE = WORK_DIR + '/bofh-cacert.pem'

# Send internal error messages here
WWW_ADMIN = 'www@mydomain.com'

# Warn these if the bofh certificate is wrong - may be an attack
CERT_WARN = (WWW_ADMIN + ', admin@mydomain.com, cerebrum@mydomain.com')

# Wait at least this many seconds between warnings about wrong certificate
CERT_WARN_FREQUENCY = 24*3600

# Create this file to timestamp warnings about wrong certificate
CERT_WARNED_FILE = WORK_DIR + '/bofh-cacert.warned'

# Fetch template for web page from TEMPLATE_URL_PREFIX + language + '.html'
TEMPLATE_URL_PREFIX = 'http://www.usit.uio.no/it/ureg2000/.template_'

# Info in the web page:
# Editor name/address, address for users to send bug reports to.
EDITOR_NAME =    'Cerebrum'
EDITOR_EMAIL =   'cerebrum@mydomain.com'
BUGREPORT_ADDR = 'cerebrum@mydomain.com'

# Command which generates at least 32 bytes of random data.
# Used if /dev/random does not exist.
RANDOM_DATA_CMD = '/usr/bin/ssh-rand-helper'

# Command to send an e-mail message.
# Receives the message from standard input, including headers.
SENDMAIL_CMD = '/usr/lib/sendmail -oi -oem -odb -t'
