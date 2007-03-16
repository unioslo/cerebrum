#!/local/bin/python
# IVR 2007-03-16 FIXME: httpd runs as nobody, and nobody has the wrong 
# python in the PATH.
# -*- coding: iso-8859-1 -*-
#
# Copyright 2005-2007 University of Oslo, Norway
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

import logging
import cerebrum_path
import cereconf
from Cerebrum.modules.no.Indigo.Cweb import Controller

def make_logger(): # TBD: use cgi.py's logger?
    logger = logging.getLogger('myapp')
    hdlr = logging.FileHandler(cereconf.CWEB_LOG_FILE)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr) 
    logger.setLevel(logging.DEBUG)
    return logger

if __name__ == '__main__':
    c = Controller.Controller(make_logger(), cereconf.CWEB_AVAILABLE_COMMANDS)
    c.process_request()

# arch-tag: d2ac908e-7155-11da-96f0-bb5b91364575
