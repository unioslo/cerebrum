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


"""Module for all exceptions in Spine which should be sent to clients.

Contains SpineException, which should be the baseclass for all exceptions
which should be sent to users.

Implement exceptions localy, in the modules where they fit the most.
Exceptions which is not so clear to where they should be placed, can be
implemented here.
"""

class SpineException(Exception):
    """Base-class for all exceptions in spine."""
  
    def __init__(self, *args, **vargs):
        """Allows an explanation-string as argument.

        The explanation will be copied into the wrapper-object in
        the corba-layer.
        """
        if 'explanation' in vargs.keys():
            self.explanation = vargs.pop('explanation')
        elif len(args) > 0 and type(args[0]) is str:
            self.explanation = args[0]
            args = args[1:]

        Exception.__init__(self, *args, **vargs)

