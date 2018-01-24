# -*- coding: utf-8 -*-
#
# Copyright 2013 University of Oslo, Norway
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
"""Help text for bofhd in the TSD project."""

from Cerebrum.modules.bofhd.bofhd_core_help import group_help
from Cerebrum.modules.bofhd.bofhd_core_help import command_help
from Cerebrum.modules.bofhd.bofhd_core_help import arg_help
import cereconf

# Add instance specific help text:

group_help['project'] = 'Project related commands'

# The texts in command_help are automatically line-wrapped, and should
# not contain \n
command_help['user'].update({
    'user_approve':
        'Activate a user in the systems, after checking',
    'user_generate_otpkey':
        'Regenerate a One Time Password (OTP) key for an account',
    'user_password':
        "Set password for a person's users",
})

command_help['group'].update({
    'group_add_member':
        'Add a member to a group',
    'group_remove_member':
        'Remove a member from a group',
})

command_help.setdefault('subnet', {}).update({
    'subnet_list':
        'List all subnets',
    'subnet_search':
        'Wildcard search for subnets',
})

command_help.setdefault('host', {}).update({
    'host_list_projects':
        'List all projects associated with a host',
})

command_help['project'] = {
    'project_approve':
        'Approve a project with the given name',
    'project_reject':
        'Reject a project with the given name',
    'project_create':
        'Create a new project manually',
    'project_freeze':
        'Add a BofhdRequest for freezing a project',
    'project_unfreeze':
        'Thaw a project',
    'project_info':
        'Show information about a given project',
    'project_list':
        'List all projects according to given filter',
    'project_affiliate_entity':
        'Affiliate an entity with a project, e.g. groups and hosts',
    'project_set_enddate':
        'Reset the end date for a project',
    'project_set_projectname':
        'Reset the project name',
    'project_set_longname':
        "Reset a project's full name",
    'project_set_shortname':
        "Reset a project's short name",
    'project_setup':
        "Rerun an existing project's setup procedure to use new settings.",
    'project_set_vm_type':
        "Change the project's vm_type, and re-run setup of project.",
    'project_terminate':
        'Terminate a project by removing all data',
    'project_unapproved':
        'List all projects that has not been approved or rejected yet',
    'project_list_hosts':
        'List all hosts associated with a project',
}

arg_help.update({
    'project_id':
        ['projectID', 'Project ID',
         ('The project ID, normally on the form pXX, '
          'where XX goes from 01 to 32678')],
    'project_name':
        ['projectname', 'Project name',
         'Short, unique name of the project, around 6 digits'],
    'project_longname':
        ['longname', "Project's full name",
         'The full, long name of the project'],
    'project_shortname':
        ['shortname', "Project's short name",
         'The short, descriptive name of the project'],
    'project_start_date':
        ['startdate', "Project's start date",
         'The day the project should be activated'],
    'project_end_date':
        ['enddate', "Project's end date",
         'The day the project should be ended and frozen'],
    'project_statusfilter':
        ['filter', 'Filter on project status',
                   'Not implemented yet'],
    'project_price':
        ['price', "Project's price", "Price, e.g. UIO, UH or OTHER"],
    'project_institution':
        ['institution', "Project's institution",
         "Institution, e.g. UIO, HSØ, HIOA, UIT, NTNU or OTHER"],
    'project_hpc':
        ['hpc', "Project's HPC flag",
         'If project uses HPC'],
    'project_metadata':
        ['metadata', "User defined metadata field",
         'User defined meta data field for project'],
    'vlan':
        ['vlan', 'VLAN number',
         'A number between 0-4094, or a blank value, which defaults to the '
         'first available VLAN'],
    'entity_type':
        ['entity_type', 'Entity type',
         'Possible values:\n - group\n - account\n - project\n - host'],
    'person_search_type':
        ['search_type', 'Enter person search type',
         """Possible values:
  - 'fnr'
  - 'name'
  - 'date' of birth, on format YYYY-MM-DD
  - 'stedkode' - Use project-ID"""],
    'subnet_search_type':
        ['search_type', 'Enter subnet search type',
        """Possible values:
  - 'subnet'
  - 'vlan'
  - 'project'
  - 'description'"""],
    'fnmatch_pattern':
        ['pattern', 'Enter wildcard pattern',
        """Case-sensitive. Use Unix shell-style wildcards:
  - *      matches everything
  - ?      matches any single character
  - [seq]  matches any character in seq
  - [!seq] matches any character not in seq"""],
    'otp_type':
        ['otp_type', 'OTP type',
         'The OTP type, e.g. totp, hotp or smartphone_yes'],
    'vm_type':
        ["vm_type", "VM type",
         "The type of OS for the project's hosts.\nPossible values are:\n" +
         "".join([" - %s\n" % x for x in cereconf.TSD_VM_TYPES])]
})
