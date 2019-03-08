# -*- coding: utf-8 -*-

# Copyright 2018 University of Oslo, Norway
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

from Cerebrum import Constants as CereConst
from Cerebrum.modules.bofhd.bofhd_constants import _AuthRoleOpCode


class Constants(CereConst.Constants):
    auth_pquota_list_history = _AuthRoleOpCode(
        'pq_list_hist', 'List printer quota history')
    auth_pquota_list_extended_history = _AuthRoleOpCode(
        'pq_list_ext_hist', 'List printer quota history')
    auth_pquota_off = _AuthRoleOpCode(
        'pq_off', 'Turn off printerquota')
    auth_pquota_undo = _AuthRoleOpCode(
        'pq_undo', 'Undo printjob < 72 hours')
    auth_pquota_undo_old = _AuthRoleOpCode(
        'pq_undo_old', 'Undo printjob of any age')
    auth_pquota_job_info = _AuthRoleOpCode(
        'pq_job_info', 'Job_info printjob < 72 hours')
    auth_pquota_job_info_old = _AuthRoleOpCode(
        'pq_job_info_old', 'Job_info printjob of any age')
    auth_pquota_update = _AuthRoleOpCode(
        'pq_update', 'Update printerquota')
