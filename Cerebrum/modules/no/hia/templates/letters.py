# -*- coding: utf-8 -*-
#
# Copyright 2014 University of Oslo, Norway
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
import re
import cereconf
from Cerebrum import Utils

from Cerebrum.modules.templates import letters

class TemplateHandler(letters.TemplateHandler):
    """Subclass providing UiA-specific job spooling"""
    def spool_job(self, filename, type, printer, skip_lpr=False, logfile=None,
                  lpr_user='unknown', def_lpr_cmd=None):
        """Spools the job.  The spool command is executed in the
        directory where filename resides."""
        # local change, will be removed soon
        printer = "tilfalk"
        if logfile is None:
            logfile = Utils.make_temp_file(only_name=True)
        self.logfile = logfile
        old_dir = os.getcwd()
        if os.path.dirname(filename):
            os.chdir(os.path.dirname(filename))
        base_filename = filename[:filename.rindex('.')] 
        try:
            if cereconf.PRINT_DVIPS_CMD:
                format_sys_cmd = "%s -f < %s.dvi > %s.ps 2>> %s" % (cereconf.PRINT_DVIPS_CMD,
                                                                    base_filename, base_filename,
                                                                    logfile)
            elif cereconf.PRINT_DVIPDF_CMD:
                format_sys_cmd = "%s %s.dvi %s.pdf 2>> %s" % (cereconf.PRINT_DVIPDF_CMD,
                                                              base_filename, base_filename,
                                                              logfile)
            else:
                raise IOError("Error spooling job, see %s for details" % logfile)
            if type == 'tex':
                status = (os.system("%s --interaction nonstopmode %s >> %s 2>&1" % (
                    cereconf.PRINT_LATEX_CMD, filename, logfile)) or
                          os.system("%s" % (format_sys_cmd)))
                if status:
                    raise IOError("Error spooling job, see %s for details" % logfile)
            if not skip_lpr:
                if re.search(r'[^a-z0-9\-_]', printer):
                    raise IOError("Bad printer name")
        finally:
            os.chdir(old_dir)

if __name__ == '__main__':
    th = TemplateHandler('no_NO/printer', 'breg', 'ps')
    f = file("t.ps", "w")
    if th._hdr:
        f.write(th._hdr)
    f.write(th.apply_template('body', {}))
    if th._footer:
        f.write(th._footer)
    f.close()
    th.spool_job("t.ps", th._type, 'nosuchprinter', skip_lpr=False)

