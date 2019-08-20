# -*- coding: utf-8 -*-
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

# TBD: Provide defaults for all settings like cereconf?
# from Cerebrum.default_config import *

# Classes to fetch in ABCFactory
CLASS_SETTINGS = ['Cerebrum.modules.abcenterprise.ABCEnterprise/Settings']

CLASS_PREPARSER = ['Cerebrum.modules.abcenterprise.ABCEnterprise/ABCPreParser']

CLASS_ANALYZER=['Cerebrum.modules.abcenterprise.ABCEnterprise/ABCAnalyzer']

CLASS_XMLPARSER='cElementTree'

CLASS_ENTITYITERATOR=['Cerebrum.modules.abcenterprise.ABCXmlParsers/XMLEntityIterator']

CLASS_PROPERTIESPARSER=['Cerebrum.modules.abcenterprise.ABCXmlParsers/XMLPropertiesParser']
CLASS_PERSONPARSER=['Cerebrum.modules.abcenterprise.ABCXmlParsers/XMLPerson2Object']
CLASS_ORGPARSER=['Cerebrum.modules.abcenterprise.ABCXmlParsers/XMLOrg2Object']
CLASS_OUPARSER=['Cerebrum.modules.abcenterprise.ABCXmlParsers/XMLOU2Object']
CLASS_GROUPPARSER=['Cerebrum.modules.abcenterprise.ABCXmlParsers/XMLGroup2Object']
CLASS_RELATIONPARSER=['Cerebrum.modules.abcenterprise.ABCXmlParsers/XMLRelation2Object']
CLASS_PROCESSOR=['Cerebrum.modules.abcenterprise.ABCObj2Cerebrum/ABCObj2Cerebrum']
CLASS_OBJ2CEREBRUM=['Cerebrum.modules.abcenterprise.Object2Cerebrum/Object2Cerebrum']


# Types used in ABCEnterprise. Last argument in list is a coded type.
TYPES={'addresstype'  : (("organization", "Postal", "ADDR_ORG_POSTAL"),
                         ("person", "Home", "ADDR_PERS_HOME"),),
       'contacttype'  : (("organization", "Contactphone", "CONT_ORG_CONTPHONE"),
                         ("person", "Homephone", "CONT_PERS_HOMEPHONE"),
                         ("person", "Officephone", "CONT_PERS_OFFICEPHONE"),
                         ("person", "Mobile", "CONT_PERS_MOBIL"),),
       'tagtype'      : (("ou", "visibility", "ADD_SPREAD"),),
       'orgidtype'    : (("Orgnr", "ORG_ID_ORGID"),),
       'orgnametype'  : (("Akronym", "ORG_NAME_ACRONYM"),
                         ("Navn", "ORG_NAME_NAME"),),
       'ouidtype'     : (("Orgnr", "OU_ID_ORGID"),
                         ("OUID", "OU_ID_OUID"),),
       'ounametype'   : (("ID", "OU_NAME_ID"),
                         ("Navn", "OU_NAME_NAME"),),
       'personidtype' : (("fnr", "PERS_ID_FNR"),),
       'groupidtype'  : (("grpid", "GRP_ID_GRPID"),),
       'relationtype' : (("ou", "person", "Employee", "REL_OU_PERS_EMPLOYEE"),
                         ("ou", "person", "Pupil", "REL_OU_PERS_PUPIL"),
                         ("group", "person", "Responsible", "REL_GRP_PERS_RESPONSIBLE"),
                         ("group", "person", "Pupil", "REL_GRP_PERS_PUPIL"),)
        }

# People's names has to be converted into "type" : "value". This dict is a mapping
# for just that. 'partname' is covered in TYPES.
NAMETYPES={'fn'       : "NAME_FULL",
           'sort'     : "NAME_SORT",
           'nickname' : "NAME_NICKNAME",
           'family'   : "NAME_FAMILY",
           'given'    : "NAME_GIVEN",
           'other'    : "NAME_OTHER",
           'prefix'   : "NAME_PREFIX",
           'suffix'   : "NAME_SUFFIX"
           }

# Under is ABCObj2Cerebrum stuff. We import Cerebrum modules here, but
# leave the above "untouched".

# Provide Constants:
import cereconf
from Cerebrum.Utils import Factory
co = Factory.get('Constants')(Factory.get('Database')())

SOURCE={'datasource'   : "Example SAS",
        'target'       : "Example BAS",
        'source_system': co.system_some_system_defined_in_a_constant
        }

# Mock up
CONSTANTS={'ADDR_ORG_POSTAL'         : co.address_post,
           'ADDR_PERS_HOME'          : co.address_post_private,
           'CONT_ORG_CONTPHONE'      : co.contact_phone,
           'CONT_PERS_HOMEPHONE'     : co.contact_phone_private,
           'CONT_PERS_OFFICEPHOONE'  : co.contact_phone,
           'CONT_PERS_MOBILE'        : co.contact_mobile,   
           'ORG_ID_ORGID'            : co.externalid_orgnr,
           'ORG_NAME_ACRONYM'        : "OU_NAME_ACRONYM",
           'ORG_NAME_NAME'           : "OU_NAME_NAME",
           'OU_ID_ORGID'             : co.externalid_orgnr,
           'OU_ID_OUID'              : co.externalid_ouid,
           'OU_NAME_ID'              : "OU_NAME_ID",
           'OU_NAME_NAME'            : "OU_NAME_NAME",
           'PERS_ID_FNR'             : co.externalid_fodselsnr,
           'GRP_ID_GRPID'            : co.external_id_groupid,
           'REL_OU_PERS_EMPLOYEE'    : None,
           'REL_OU_PERS_PUPIL'       : None,
           'REL_GRP_PERS_RESPONSIBLE': None,
           'REL_GRP_PERS_PUPIL'      : None,
           'NAME_FULL'               : co.name_full,
           'NAME_FAMILY'             : co.name_last,
           'NAME_GIVEN'              : co.name_first
           }

# OU names are special. 'name' is required, the rest is optional.
OU_NAMES={'name'        : "OU_NAME_NAME",
          'acronym'     : "OU_NAME_ACRONYM",
          'short_name'  : "OU_NAME_ID",
          'display_name': None,
          'sort_name'   : None
          }

OU_PERSPECTIVE=co.perspective_same_source_system

# In ABC Enterprise a group's name is the same as an ID. Therefore
# we map one ID to become the groups name.
GROUP_NAMES=(co.external_id_groupid,)

# Rewrite rule for group names
# OPTIONAL! Remove if you don't need rewriting.
GROUP_REWRITE = lambda x: "import_abc_%s" % x

# Mapping of what should be done in relations
RELATIONS={'ou' : {'person' : {'Employee' : ('affiliation',
                                             co.affiliation_ansatt),
                               'Pupil' : ('affiliation',
                                          co.affiliation_elev),
                               },
                    },
           'group' : {'person' : {'Responsible' : ('memberof',),
                                  'Pupil' : ('memberof',),
                                  }
                      }
           }
# Person affiliations have a status. Map this here.
AFF_STATUS={ co.affiliation_elev : co.affiliation_status_elev_ektiv,
             co.affiliation_ansatt : co.affiliation_status_ansatt_tekadm
             }

# When inspecting the content of a 'tag' element, the following
# rewrite rule shold be followed. Remove TAG_REWRITE from the config
# fileif you don't want the functionality.
TAG_REWRITE={ 'AD' : co.spread_ad_ou,
              'Feide' : co.spread_ou_publishable,
              'Fronter' : co.spread_lms_ou,
              'OID' : co.spread_oid_ou
            }


# Example XML for this config:
 
# <?xml version="1.0" encoding="UTF-8"?>
# <document>
#   <properties>
#     <datasource>Example SAS</datasource>
#     <target>Example BAS</target>
#     <timestamp>2005-08-23T09:30:47-02:00</timestamp>
#     <types>
#       <addresstype subject="organization">Postal</addresstype>
#       <addresstype subject="person">Home</addresstype>
#       <contacttype subject="organization">Contactphone</contacttype>
#       <contacttype subject="person">Homephone</contacttype>
#       <contacttype subject="person">Officephone</contacttype>
#       <contacttype subject="person">Mobile</contacttype>
#       <orgidtype>Orgnr</orgidtype>
#       <orgnametype>Akronym</orgnametype>
#       <ouidtype>Orgnr</ouidtype>
#       <ouidtype>OUID</ouidtype>
#       <ounametype>ID</ounametype>
#       <ounametype>Navn</ounametype>
#       <personidtype>fnr</personidtype>
#       <groupidtype>grpid</groupidtype>
#       <relationtype subject="ou" object="person">Employee</relationtype>
#       <relationtype subject="ou" object="person">Pupil</relationtype>
#       <relationtype subject="group" object="person">Responsible</relationtype>
#       <relationtype subject="group" object="person">Pupil</relationtype>
#     </types>
#   </properties>

#   <organization>
#     <orgid orgidtype="Orgnr">1</orgid>
#     <orgname lang="no" orgnametype="Navn">Foo State</orgname>
#     <orgname lang="no" orgnametype="Akronym">FooS</orgname>
#     <realm>foo.edu</realm>
#     <ou>
#       <ouid ouidtype="Orgnr">2</ouid>
#       <ouid ouidtype="OUID">FOO</ouid>
#       <ouname lang="NO" ounametype="ID">Foo</ouname>
#       <ouname lang="NO" ounametype="Navn">Foo university</ouname>
#     </ou>
#   </organization>

#   <person>
#     <personid personidtype="fnr">11223312345</personid>
#     <name>
#       <fn>John Smith</fn>
#       <n>
#         <family>Smith</family>
#         <given>John</given>
#       </n>
#     </name>
#     <birthdate>1970-12-24</birthdate>
#     <gender>male</gender>
#     <address addresstype="Home">
#       <street>upper westside</street>
#       <postcode>3030</postcode>
#       <city>Atlantis</city>
#     </address>
#     <contactinfo contacttype="Homephone">32323232</contactinfo>
#     <contactinfo contacttype="Mobile">91919191</contactinfo>
#     <contactinfo contacttype="Officephone">32322323</contactinfo>
#   </person>

#   <person>
#     <personid personidtype="fnr">22334412345</personid>
#     <name>
#       <fn>Ola Elev</fn>
#       <n>
#         <family>Elev</family>
#         <given>Ola</given>
#       </n>
#     </name>
#     <birthdate>1989-02-02</birthdate>
#     <gender>male</gender>
#   </person>
  
#   <group>
#     <groupid groupidtype="grpid">grp1</groupid>
#     <description>Group 1</description>
#   </group>
#   <group>
#     <groupid groupidtype="grpid">grp2</groupid>
#     <description>Group 2</description>
#   </group>
#   <group>
#     <groupid groupidtype="grpid">grp3</groupid>
#     <description>Group 3</description>
#   </group>
  
#   <relation relationtype="Employee">
#     <subject>
#       <org>
#         <orgid orgidtype="Orgnr">1</orgid>
#         <ouid ouidtype="OUID">FOO</ouid>
#       </org>
#     </subject>
#     <object>
#       <personid personidtype="fnr">11223312345</personid>
#     </object>
#   </relation>
#   <relation relationtype="Pupil">
#     <subject>
#       <org>
#         <orgid orgidtype="Orgnr">1</orgid>
#         <ouid ouidtype="OUID">FOO</ouid>
#       </org>
#     </subject>
#     <object>
#       <personid personidtype="fnr">22334412345</personid>
#     </object>
#   </relation>
#   <relation relationtype="Responsible">
#     <subject>
#       <groupid groupidtype="grpid">grp1</groupid>
#     </subject>
#     <object>
#       <personid personidtype="fnr">11223312345</personid>
#     </object>
#   </relation>
#   <relation relationtype="Pupil">
#     <subject>
#       <groupid groupidtype="grpid">grp2</groupid>
#     </subject>
#     <object>
#       <personid personidtype="fnr">11223312345</personid>
#       <personid personidtype="fnr">22334412345</personid>
#     </object>
#   </relation>
# </document>

