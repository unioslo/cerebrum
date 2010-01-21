# -*- coding: iso-8859-1 -*-
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

import cerebrum_path
import cereconf
import abcconf

from Cerebrum.Utils import dyn_import
from Cerebrum.extlib.doc_exception import DocstringException
from Cerebrum.extlib.doc_exception import ProgrammingError
from Cerebrum.modules.abcenterprise.ABCUtils import ABCConfigError
from Cerebrum.modules.abcenterprise.ABCUtils import ABCTypesError
from Cerebrum.modules.abcenterprise.ABCUtils import ABCDataError
from Cerebrum.modules.abcenterprise.ABCUtils import ABCNotSupportedError
from Cerebrum.modules.abcenterprise.ABCUtils import ABCFactory
from Cerebrum.modules.abcenterprise.ABCUtils import ABCTypes


class ABCTypesExt(ABCTypes):
    def get_type(type, args):
        if not isinstance(args, tuple):
            raise ProgrammingError, "'args' is not a tuple."
        lenght = len(args)
        for t, vals in (("addresstype", 2), ("contacttype", 2),
                        ("orgidtype", 1), ("orgnametype", 1),
                        ("ouidtype", 1), ("ounametype", 1),
                        ("personidtype", 1), ("groupidtype", 1),
                        ("relationtype", 3), ("tagtype", 2),
                        ("printplacetype",1), ("keycardtype", 1)):
            if type == t:
                if not vals == lenght:
                    raise ABCTypesError, "wrong length on list: '%s':'%d' should be '%d' - %s" % (t, lenght, vals, args)
                lists = abcconf.TYPES[type]
                for lst in lists:
                    if lst[:vals] == args:
                        if not len(lst[vals:]) == 1:
                            raise ABCConfigError
                        return lst[vals:][0]
        raise ABCTypesError, "type '%s' not found: '%s'" % (type, args)
    get_type = staticmethod(get_type)


# arch-tag: fc851628-6995-11da-98cb-38262c77ee84
