LDAP_BASE = 'dc=uio,dc=no'
BASE_OBJECTCLASS = ('top','organization','norOrganization','labeledURIObject')
BASE_BUSINESSCATEGORY = ('University','Universitet','Education','Utdanning')
#BASE_DESCRIPTION = 'Universitetet i Oslo har 8 fakultet: Teologisk, Juridisk, Medisinsk, Historisk-filosofisk, Matematisk-naturvitenskapelig, 
#Odontologisk, Samfunnsvitenskapelig og Utdanningsvitenskapelig.'	
BASE_CITY = 'Oslo' 		#Mutiple values allowed
BASE_ALTERNATIVE_NAME = ('University of Oslo','Universitetet i Oslo','UoO','Universitas Osloensis','UiO','Oslo University','Oslo Universitet')




ORGANIZATION = 'Enable' #Boer vurdere FALSE/TRUE eller 0/1
ORGANIZATION_DN = 'ou=organization'
ORG_ATTR = 'ou'
ORG_OBJECTCLASS = ('top','organizationalUnit','norOrganizationalUnit')
ORG_ROOT = '645' # Finn et felt i "ou_structure" eller "ou_info" som virker fornuftig 

PERSON = 'Enable'
PERSON_DN = 'ou=people'
PERSON_ATTR = 'uid' # 'uid' or 'cn'
PERSON_OBJECTCLASS = ('top','person','organizationalPerson','inetOrgPerson','eduPerson','norPerson')

USER = 'Enable'
USER_DN = 'ou=users'
USER_ATTR = 'uid'
USER_OBJECTCLASS = ('top','account','posixAccount')

ALIAS = 'Enable'
ALIAS_ATTR = 'uid'
ALIAS_OBJECTCLASS = ('top','alias','extensibleObject')

GROUP = 'Enable'
GROUP_DN = 'ou=filegroups'
GROUP_ATTR = 'cn'
GROUP_OBJECTCLASS = ('top','posixGroup')
GROUP_SPREAD = 'NIS_fg@uio'

NETGROUP = 'Enable'
NETGROUP_DN = 'ou=netgroups'
NETGROUP_ATTR = 'cn'
NETGROUP_OBJECTCLASS = ('top','nisNetGroup')




