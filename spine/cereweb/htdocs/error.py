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
from gettext import gettext as _
from lib.utils import queue_message, redirect
import config

def report(title, message, name="", path="",
           referer="", traceback="", explanation=""):
    """Saves an error report to disk."""

    if config.conf.getboolean('error', 'allow_reporting'):
        path = config.conf.get('error', 'report_dir')
        filename = 'cereweb_er_%s' % title[:15]
        filename = os.path.join(path, filename)
        args = ('Title: '+title, 'Message: '+message, 'Name: '+name,
                'Path: '+path, 'Referer: '+referer,
                'Explanation: '+explanation, 'Traceback: '+traceback, '--')
        
        fd = file(filename, 'a')
        fd.write("\n".join(args))
        fd.close()
        
        queue_message(_('Error successfully reported.'))
    else:
        queue_message(_('Reporting of errors are not allowed at this moment.'), error=True)
    
    redirect('index')
report.exposed = True

# arch-tag: dc1e0ce4-2c4d-11da-948d-0ae10e01ecdf
