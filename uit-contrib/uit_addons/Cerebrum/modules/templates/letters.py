# -*- coding: utf-8 -*-
#
# Copyright 2003-2019 University of Oslo, Norway
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
"""
Legacy password letters module for Cerebrum

History
-------
This module was removed, and LaTeX templating replaced with HTML/CSS templates
(the current Cerebrum.modules.templates). It has temporarily been restored in
order to merge UiT code with the Cerebrum repository.
"""
import os
import re
import string

import cereconf

from Cerebrum import Utils


class TemplateHandler(object):
    """
    Handling of templates for letters.

    Templates are stored in directories like this:
       no/new_password.tex
       no/new_password_body.tex
       en/new_password.tex
       en/new_password_body.tex

    ...where no/en is the language, and new_password is the main template
    file. When reading the template, the contents of the file named _body
    will be replace the string <BODY> in the main template.  If no <BODY>
    tag is present, hdr and footer will be empty.

    Example:
      def make_letter():
          (hdr, body, footer) = read_templates('no', 'new_password')
          print hdr
          for u in users:
              print apply_template(body, {'username': u.user, ...})
          print footer

    """
    def __init__(self, lang=None, tplname=None, type=None):
        if lang is not None:
            self._type = type
            (self._hdr,
             self._body,
             self._footer) = self.read_templates(lang, tplname)

    def read_templates(self, lang, tplname):
        filename_hdr = os.path.join(
            cereconf.TEMPLATE_DIR, lang,
            "{template}.{ext}".format(tplname, self._type))
        filename_body = os.path.join(
            cereconf.TEMPLATE_DIR, lang,
            "{template}_body.{ext}".format(tplname, self._type))

        with open(filename_hdr, 'rb') as f:
            hdr = body = footer = ''
            for t in f.readlines():
                if t.startswith("<BODY>"):
                    with open(filename_body, 'rb') as f2:
                        for t2 in f2.readlines():
                            body += t2
                else:
                    if not body:
                        hdr += t
                    else:
                        footer += t
            if not body:
                return (None, hdr, None)
            return (hdr, body, footer)

    def apply_template(self, template, mapping, no_quote=()):
        """applies mapping to hdr, body or footer template and returns
        the resulting string.  Mapping is a dict, where strings named
        <key> are replaced with mapping[key].  The special key
        template_dir may be used to refer to cereconf.TEMPLATE_DIR"""

        if template == 'hdr':
            template = self._hdr
        elif template == 'body':
            template = self._body
        elif template == 'footer':
            template = self._footer
        mapping['template_dir'] = cereconf.TEMPLATE_DIR
        no_quote += ('template_dir', )
        for k in mapping.keys():
            if mapping[k] is None:
                v = ""
            else:
                v = str(mapping[k])
            if k in no_quote:
                pass
            elif self._type == 'ps':  # Quote postscript
                v = v.replace('\\', '\\\\')
                v = v.replace(')', '\\)')
                v = v.replace('(', '\\(')
            elif self._type == 'tex':
                if not v:
                    v = '\\ '
                else:
                    for c in '\\#$%&~_^{}':
                        v = v.replace(c, '\\' + c)
                    v = v.replace('-', '{-}')
            template = template.replace("<%s>" % k, v)
        return template

    def make_barcode(self, account_id, filename):
        ret = os.system("%s -e EAN -E -n -b %012i > %s" % (
            cereconf.PRINT_BARCODE, account_id, filename))
        if ret:
            raise IOError("Bardode returned %s" % ret)

    # TODO: Remove use of spool_job, and get rid of:
    def _tail(self, fname, num=-1):
        with open(fname) as f:
            ret = f.readlines()[-num]
            return "".join(ret).rstrip()

    def spool_job(self, filename, type, printer, skip_lpr=False, logfile=None,
                  lpr_user='unknown', def_lpr_cmd=None):
        """
        Spools the job.

        The spool command is executed in the directory where filename
        resides.
        """
        if logfile is None:
            logfile = Utils.make_temp_file(only_name=True)
        self.logfile = logfile
        old_dir = os.getcwd()
        if os.path.dirname(filename):
            os.chdir(os.path.dirname(filename))
        base_filename = filename[:filename.rindex('.')]
        try:
            if cereconf.PRINT_DVIPS_CMD:
                format_sys_cmd = "%s -f < %s.dvi > %s.ps 2>> %s" % (
                    cereconf.PRINT_DVIPS_CMD,
                    base_filename,
                    base_filename,
                    logfile,
                )
                base_filename += ".ps"
            elif cereconf.PRINT_DVIPDF_CMD:
                format_sys_cmd = "%s %s.dvi %s.pdf 2>> %s" % (
                    cereconf.PRINT_DVIPDF_CMD,
                    base_filename,
                    base_filename,
                    logfile,
                )
                base_filename += ".pdf"
            else:
                raise IOError("Error spooling job, see %s for details" %
                              (logfile, ))
            if type == 'tex':
                tex_cmd = "%s --interaction nonstopmode %s >> %s 2>&1" % (
                    cereconf.PRINT_LATEX_CMD,
                    filename,
                    logfile,
                )
                status = os.system(tex_cmd) or os.system(format_sys_cmd)
                if status:
                    raise IOError("Error spooling job, see %s for details" %
                                  (logfile, ))
            if not skip_lpr:
                if printer is not None and re.search(r'[^a-z0-9\-_]', printer):
                    raise IOError("Bad printer name")

                if def_lpr_cmd:
                    lpr_cmd = string.Template(def_lpr_cmd)
                else:
                    lpr_cmd = string.Template(cereconf.PRINT_LPR_CMD)

                # Assemble parameters that might be of use for further
                # handling of the job. Contents of def_lpr_cmd/
                # cereconf.PRINT_LPR_CMD determine what is actually used and
                # for what purpose
                lpr_params = {
                    'filename': base_filename,
                    'uname': lpr_user,
                    'printer': printer,
                    'hostname': os.uname()[1],
                }

                status = os.system("%s >> %s 2>&1" % (
                    lpr_cmd.substitute(lpr_params),
                    logfile,
                ))
                if status:
                    raise IOError(
                        "Error spooling job, see %s for details (tail: %s)"
                        % (logfile, self._tail(logfile, num=1)))
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
