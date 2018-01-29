# -*- coding: utf-8 -*-

# Copyright 2003-2005 University of Oslo, Norway
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
"""Help text for NIH's bofhd."""

from Cerebrum.modules.bofhd.bofhd_core_help import group_help
from Cerebrum.modules.bofhd.bofhd_core_help import command_help
from Cerebrum.modules.bofhd.bofhd_core_help import arg_help

# Overrides of the default help text follows:

command_help['misc']['misc_checkpassw'] = "Test the quality of a given password"
command_help['misc']['misc_user_passwd'] = "Check whether an account has a given password"
command_help['user']['user_create'] = 'Create a user account'
# No need to modify group_help, we use UiO's without modifications.

command_help['email']['email_set_primary_address'] = ("Changes the primary "
        "address for the e-mail target to the specified value")
