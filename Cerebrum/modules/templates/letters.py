#!/usr/bin/env python2.2

import os
import cereconf
from Cerebrum import Utils

class TemplateHandler(object):
    """Handling of templates for letters.

Templates are stored in directories like this:
   no/new_password.tex
   no/new_password_body.tex
   en/new_password.tex
   en/new_password_body.tex

Where no/en is the language, and new_password is the main template
file.  When reading the template, the contents of the file named _body
will be replace the string <BODY> in the main template.  If no <BODY>
tag is present, hdr and footer will be empty.

    def make_letter():
        (hdr, body, footer) = read_templates('no', 'new_password')
        print hdr
        for u in users:
            print apply_template(body, {'username': u.user, ...})
        print footer
        """
    def __init__(self, lang=None, tplname=None, type=None):
        if lang is not None:
            self._type=type
            (self._hdr, self._body, self._footer) = self.read_templates(lang, tplname)

    def read_templates(self, lang, tplname):
        pathinfo = (cereconf.TEMPLATE_DIR,lang, tplname, self._type)
        f = open("%s/%s/%s.%s" % pathinfo, 'rb')
        hdr = body = footer = ''
        for t in f.readlines():
            if t.startswith("<BODY>"):
                f2 = open("%s/%s/%s_body.%s" %  pathinfo, 'rb')
                for t2 in f2.readlines():
                    body += t2
            else:
                if len(body) == 0:
                    hdr += t
                else:
                    footer += t
        if len(body) == 0:
            return (None, hdr, None)
        return (hdr, body, footer)

    def apply_template(self, template, mapping):
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
        for k in mapping.keys():
            if mapping[k] is None:
                v = ""
            else:
                v = str(mapping[k])
            if self._type == 'ps':  # Quote postscript
                v.replace('\\', '\\\\')
                v.replace(')', '\\)')
                v.replace('(', '\\(')
            elif self._type == 'tex':
                if len(v) == 0:
                    v = '\ '
                else:
                    for c in '#$%&~_^\{}':
                        v = v.replace(c, '\%s' % c)
                    v = v.replace('-', '{-}')
            template = template.replace("<%s>" % k, v)
        return template

    def spool_job(self, filename, type, printer, skip_lpr=False):
        logfile = Utils.make_temp_file(only_name=1)
        self.logfile = logfile
        base_filename = filename[:filename.rindex('.')]
        if type == 'tex':
            status = (os.system("%s --interaction nonstopmode %s >> %s 2>&1" % (
                cereconf.PRINT_LATEX_CMD, filename, logfile)) or
                      os.system("%s -f < %s.dvi > %s.ps 2>> %s" % (
                cereconf.PRINT_DVIPS_CMD, base_filename, base_filename, logfile)))
            if status:
                raise IOError("Error spooling job, see %s for details" % logfile)
        if not skip_lpr:
            lpr_cmd = cereconf.PRINT_LPR_CMD.replace("<printer>", printer)
            status = os.system("%s %s.ps >> %s.zz 2>&1" % (
                lpr_cmd, base_filename, logfile))
            if status:
                raise IOError("Error spooling job, see %s for details" % logfile)
