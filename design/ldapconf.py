# -*- coding: iso-8859-1 -*-

# Copyright 2003, 2004 University of Oslo, Norway
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

# Note: The 'LDAP_*_DN' variables have changed semantics;
# they should now contain the entire DN.

LDAP_BASE       = 'dc=example,dc=com'
LDAP_BASE_ATTRS = {
    # Attributes of base object; will be added to as needed
    'objectClass': ('top', 'organization', 'dcObject', 'labeledURIObject'),
    'o': ('Example','Example INC','EX INC'),
    'businessCategory': ('Manufacturing','Education',),
    'description': ('Example INC Company, Middle Of Nowhere', 'Test'),
    'l': ('Place of Example',),
    'labeledURI': ('http://www.example.com/',) }

LDAP_BASE_DOMAIN = 'example.com'
LDAP_DUMP_DIR = '/home/cerebrum/dump'

# Common attributes of 'container' objects such as 'ou=people,...'
LDAP_CONTAINER_ATTRS = { 'objectClass': ('top', 'organizationalUnit') }

LDAP_ORG_DN    = 'ou=organization,' + LDAP_BASE
LDAP_ORG_ATTRS = {
    'ou': ('organization', 'Example organization'),
    'description': ('Organization level',) }

LDAP_ORG_ROOT_AUTO = 'Enable' 
LDAP_ORG_ROOT = None  
LDAP_ORG_FILE = 'organization.ldif'

LDAP_POSIX_FILE  = 'posix.ldif'
# Root object for the posix file, if that is to be written
#LDAP_POSIX_DN    = None
#LDAP_POSIX_ATTRS = {}

LDAP_PRINT_NONE_ROOT = 'Enable'
LDAP_NON_ROOT_ATTR = '--'
LDAP_NON_ROOT_ATTRS = {
    'description': ('Other organizational units',) }

LDAP_ORG_ADD_LDIF_FILE = 'manuell.ldif' # renamed from LDAP_MAN_LDIF_ADD_FILE

LDAP_PERSON = 'Enable'
LDAP_PERSON_DN    = 'ou=people,' + LDAP_BASE
LDAP_PERSON_ATTRS = {
    'ou': ('people', 'Persons'),
    'description': ('All persons in Example INC Company',) }
LDAP_PERSON_FILE = 'person.ldif'
LDAP_PERSON_FILTER = 'Disable' 	
# Filters. _LIST_AFFI list is a filter on which entry should be exported based on 
# the person affiliation. _PH_ADDR_AFFI will export contact info of persons with 
# the affiliation listed. 
LDAP_PERSON_LIST_AFFI = ('affiliation_status_employee_staff','affiliation_status_employee_sales',
			'affiliation_status_external_consultant','affiliation_status_contract_hired')
LDAP_PERSON_PH_ADDR_AFFI = ('affiliation_status_employee_sales',)
# OPENLDAPaci-filters: Only support one filter to add on a person-entry.
# This example has default not open public search, and the aci will open the entry
# for open public search.   
# _AFF_ACI will give default aci to any person with this affiliation.
# Both 
# _NOT_PUBLIC_GR will remove aci from persons which is included by AFF_ACI.
# _PUBLIC_GR
LDAP_PERSON_AFF_ACI = ('affiliation_status_employee_staff','affiliation_status_employee_sales')   
PERSON_NOT_PUBLIC_GR = 'group_of_not_public_internal'
PERSON_PUBLIC_GR = 'group_of_public_external'
LDAP_PERSON_ACI = 'OpenLDAPaci: 1.1#entry#grant;c,r,s,x;[all],[entry]#public#'


LDAP_USER = 'Enable'
LDAP_USER_DN    = 'ou=users,' + LDAP_BASE
LDAP_USER_ATTRS = {
    'ou': ('users', 'Users in Example','Accounts'),
    'description': ('Users in Example INC.',) }
LDAP_USER_FILE = 'posixuser.ldif'
LDAP_USER_SPREAD = ('spread_nis_user',)

LDAP_ALIAS = 'Enable'
LDAP_ALIAS_FILE = 'alias.ldif'

LDAP_GROUP = 'Enable'
LDAP_GROUP_DN    = 'ou=filegroups,' + LDAP_BASE
LDAP_GROUP_ATTRS = {
    'ou': ('filegroups', 'Filegroups in Example'),
    'description': ('All filegroups in Example INC.',) }
LDAP_GROUP_SPREAD = ('spread_nis_fg',)
LDAP_GROUP_FILE = 'posixgroup.ldif'

LDAP_NETGROUP = 'Enable'
LDAP_NETGROUP_DN    = 'ou=netgroups,' + LDAP_BASE
LDAP_NETGROUP_ATTRS = {
    'ou': ('netgroups', 'Netgroup in Example INC'),
    'description': ('All acccess groups in Example INC',) }
LDAP_NETGROUP_SPREAD = ('spread_nis_ng',)
LDAP_NETGROUP_FILE = 'posixnetgroup.ldif'


#### Obsolete variables, retained temporarily for backwards compatibility ####

LDAP_BASE_BUSINESSCATEGORY = ('Manufacturing','Education')
LDAP_BASE_DESCRIPTION = ('Example INC Company, Middle Of Nowhere','Test')	
LDAP_BASE_CITY = 'City of Example' 		
LDAP_BASE_ALTERNATIVE_NAME = ('Example','Example INC','EX INC')
LDAP_BASE_URL = 'http://www.example.com'

LDAP_ORG_GROUPS = ('ORG','PERSON','USER','GROUP','NETGROUP')

LDAP_ORG_ALTERNATIVE_NAME = ('organization','Example organization')
LDAP_ORG_ATTR = 'ou'
LDAP_ORG_OBJECTCLASS = ('organizationalUnit',)
LDAP_ORG_DESCRIPTION = ('Organization level',)

LDAP_MAN_LDIF_ADD_FILE = 'manuell.ldif' # renamed to LDAP_ORG_ADD_LDIF_FILE

LDAP_PERSON_ALTERNATIVE_NAME = ('people','Persons')
LDAP_PERSON_DESCRIPTION = 'All persons in Example INC Company'

LDAP_USER_ALTERNATIVE_NAME = ('users','Users in Example','Accounts')
LDAP_USER_DESCRIPTION = 'Users in Example INC.'

LDAP_GROUP_ALTERNATIVE_NAME = ('filegroups','Filegroups in Example')
LDAP_GROUP_DESCRIPTION = 'All filegroups in Example INC.'

LDAP_NETGROUP_ALTERNATIVE_NAME = ('netgroups','Netgroup in Example INC')
LDAP_NETGROUP_DESCRIPTION = 'All acccess groups in Example INC'

# arch-tag: d60574a0-a8f4-4fe9-9084-c3c2a159ff72
