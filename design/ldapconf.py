LDAP_BASE = 'dc=example,dc=com'
LDAP_BASE_BUSINESSCATEGORY = ('Manufacturing','Education')
LDAP_BASE_DESCRIPTION = ('Example INC Company, Middle Of Nowhere','Test')	
LDAP_BASE_CITY = 'City of Example' 		
LDAP_BASE_ALTERNATIVE_NAME = ('Example','Example INC','EX INC')
LDAP_BASE_URL = 'http://www.example.com'
LDAP_BASE_DOMAIN = 'example.com'
LDAP_DUMP_DIR = '/home/cerebrum/dump'

LDAP_ORG_GROUPS = ('ORG','PERSON','USER','GROUP','NETGROUP')
LDAP_ORG_DN = 'organization' #Objectclass "top" is included
LDAP_ORG_ALTERNATIVE_NAME = ('organization','Example organization')
LDAP_ORG_ATTR = 'ou'
LDAP_ORG_OBJECTCLASS = ('organizationalUnit',)
LDAP_ORG_DESCRIPTION = ('Organization level',)
LDAP_ORG_ROOT_AUTO = 'Enable' 
LDAP_ORG_ROOT = None  
LDAP_ORG_FILE = 'organization.ldif'
LDAP_PRINT_NONE_ROOT = 'Enable'
LDAP_NON_ROOT_ATTR = '--'
LDAP_MAN_LDIF_ADD_FILE = 'manuell.ldif'

LDAP_PERSON = 'Enable'
LDAP_PERSON_DN = 'people'
LDAP_PERSON_ALTERNATIVE_NAME = ('people','Persons')
LDAP_PERSON_DESCRIPTION = 'All persons in Example INC Company'
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
LDAP_USER_DN = 'users'
LDAP_USER_ALTERNATIVE_NAME = ('users','Users in Example','Accounts')
LDAP_USER_DESCRIPTION = 'Users in Example INC.'
LDAP_USER_FILE = 'posixuser.ldif'
LDAP_USER_SPREAD = ('spread_nis_user',)


LDAP_ALIAS = 'Enable'
LDA_ALIAS_FILE = 'alias.ldif'


LDAP_GROUP = 'Enable'
LDAP_GROUP_DN = 'filegroups'
LDAP_GROUP_ALTERNATIVE_NAME = ('filegroups','Filegroups in Example')
LDAP_GROUP_DESCRIPTION = 'All filegroups in Example INC.'
LDAP_GROUP_SPREAD = ('spread_nis_fg',)
LDAP_GROUP_FILE = 'posixgroup.ldif'

LDAP_NETGROUP = 'Enable'
LDAP_NETGROUP_DN = 'netgroups'
LDAP_NETGROUP_ALTERNATIVE_NAME = ('netgroups','Netgroup in Example INC')
LDAP_NETGROUP_DESCRIPTION = 'All acccess groups in Example INC'
LDAP_NETGROUP_SPREAD = ('spread_nis_ng',)
LDAP_NETGROUP_FILE = 'posixnetgroup.ldif'

