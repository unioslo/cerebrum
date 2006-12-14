#!/usr/bin/env python
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

import ConfigParser
import os

conf = ConfigParser.SafeConfigParser()
conf.read(('sync.conf.template', 'sync.conf'))
sync=conf # compat

def apply_quarantine(obj, typestr):
    """
    Apply rules set in the [OBJTYPE_quarantenes] section of the config
    file. For each quarantene the user may override one atttribute.
    If no rule exists for a given quarantene, the DEFAULT rule will be used.
    The format is:
    [account_quarantenes]
    nologin: shell="/bin/nologin"
    DEFAULT: passwd="*"
    """
    for q in obj.get_quarantines:
        try:
            a=sync.get('%s_quarantenes' % typestr, q.name)
        except ConfigParser.NoOptionError:
            try:
                a=sync.get('%s_quarantenes' % typestr, "DEFAULT")
            except ConfigParser.NoOptionError:
                return
        try:
            (var, val) = a.split('=')
            val=eval(val)  # ouch! but needed for strings/ints/etc
        except ValueError:
            logging.error("Bad quarantene action \"%s\"" % a)
        setattr(obj, var, val)

def apply_override(obj, typestr):
    """
    Apply rules set in the [OBJTYPE_override] section of the config file.
    These values will override any values supplied by the server.
    The format is:
    [account_override]
    homedir: /home/%(name)s
    """
    section='%s_override' % typestr
    attribs = dict([(x,y) for x, y in obj.__dict__.items()
                    if y not in ('', -1)])
    for a in sync.options(section):
        if attribs.has_key(a): del attribs[a]
    for a in sync.options(section):
        setattr(obj, a, sync.get(section, a, vars=attribs))

def apply_default(obj, typestr):
    """
    Apply rules set in the [OBJTYPE_default] section of the config file.
    These values will be used if no value is supplied by the server.
    The format is:
    [account_default]
    homedir: /home/%(name)s
    """
    section='%s_default' % typestr
    attribs = dict([(x,y) for x, y in obj.__dict__.items()
                    if y not in ('', -1)])
    for a in sync.options(section):
        # "" or -1 for nonexisting values is an spine-ism
        if (not obj.__dict__.has_key(a)) or getattr(obj, a) == "" or getattr(obj, a) == -1:
            setattr(obj, a, sync.get(section, a, vars=attribs))

