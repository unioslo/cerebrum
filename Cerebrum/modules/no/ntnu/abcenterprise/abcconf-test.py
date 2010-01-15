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

# TBD: Provide defaults for all settings like cereconf?
# from Cerebrum.default_config import *

# Classes to fetch in ABCFactory
CLASS_SETTINGS = ['Cerebrum.modules.no.ntnu.abcenterprise.ABCEnterprise/Settings']

CLASS_PREPARSER = ['Cerebrum.modules.no.ntnu.abcenterprise.ABCEnterprise/ABCPreParser']

CLASS_ANALYZER=['Cerebrum.modules.no.ntnu.abcenterprise.ABCEnterprise/ABCAnalyzer']

CLASS_XMLPARSER='cElementTree'

CLASS_ENTITYITERATOR=['Cerebrum.modules.no.ntnu.abcenterprise.ABCXmlParsers/XMLEntityIterator']

CLASS_PROPERTIESPARSER=['Cerebrum.modules.no.ntnu.abcenterprise.ABCXmlParsers/XMLPropertiesParser']
CLASS_PERSONPARSER=['Cerebrum.modules.no.ntnu.abcenterprise.ABCXmlParsers/XMLPerson2Object']
CLASS_ORGPARSER=['Cerebrum.modules.no.ntnu.abcenterprise.ABCXmlParsers/XMLOrg2Object']
CLASS_OUPARSER=['Cerebrum.modules.no.ntnu.abcenterprise.ABCXmlParsers/XMLOU2Object']
CLASS_GROUPPARSER=['Cerebrum.modules.no.ntnu.abcenterprise.ABCXmlParsers/XMLGroup2Object']
CLASS_RELATIONPARSER=['Cerebrum.modules.no.ntnu.abcenterprise.ABCXmlParsers/XMLRelation2Object']
CLASS_PROCESSOR=['Cerebrum.modules.abcenterprise.ABCObj2Cerebrum/ABCObj2Cerebrum']
CLASS_OBJ2CEREBRUM=['Cerebrum.modules.no.ntnu.abcenterprise.Object2Cerebrum/Object2Cerebrum']


# Types used in ABCEnterprise. Last argument in list is a coded type.
TYPES={'addresstype'  : (("organization", "Postal", "ADDR_ORG_POSTAL"),
                         ("organization", "postal", "ADDR_ORG_POSTAL"),
                         ("person", "Home", "ADDR_PERS_HOME"),),
       'contacttype'  : (("organization", "Contactphone", "CONT_ORG_CONTPHONE"),
                         ("organization", "e-mail", "CONT_ORG_EMAIL"),
                         ("organization", "url", "CONT_ORG_URL"),
                         ("organization", "switchboard", "CONT_ORG_SWITCHBOARD"),
                         ("ou", "e-mail", "CONT_ORG_EMAIL"),
                         ("ou", "url", "CONT_ORG_URL"),
                         ("ou", "switchboard", "CONT_ORG_SWITCHBOARD"),
                         ("person", "Homephone", "CONT_PERS_HOMEPHONE"),
                         ("person", "Officephone", "CONT_PERS_OFFICEPHONE"),
                         ("person", "Mobile", "CONT_PERS_MOBIL"),),
       'orgidtype'    : (("Orgnr", "ORG_ID_ORGID"),
                         ("kjerneid", "ORG_ID_KJERNEID"),
                         ("stedkode", "ORG_ID_STEDKODE"),),
       'orgnametype'  : (("Akronym", "ORG_NAME_ACRONYM"),
                         ("Navn", "ORG_NAME_NAME"),
                         ("acronym", "ORG_NAME_ACRONYM"),
                         ("name", "ORG_NAME_NAME"),),
       'ouidtype'     : (("Orgnr", "OU_ID_ORGID"),
                         ("OUID", "OU_ID_OUID"),
                         ("kjerneid", "OU_ID_KJERNEID"),
                         ("stedkode", "OU_ID_STEDKODE"),),
       'ounametype'   : (("ID", "OU_NAME_ID"),
                         ("Navn", "OU_NAME_NAME"),
                         ("acronym", "OU_NAME_ACRONYM"),
                         ("name", "OU_NAME_NAME"),),
       'personidtype' : (("fnr", "PERS_ID_FNR"),
                         ("kjerneid", "PERS_ID_KJERNEID"),),
       'groupidtype'  : (("grpid", "GRP_ID_GRPID"),),
       'relationtype' : (("ou", "person", "Employee", "REL_OU_PERS_EMPLOYEE"),
                         ("ou", "person", "Pupil", "REL_OU_PERS_PUPIL"),
                         ("group", "person", "Responsible", "REL_GRP_PERS_RESPONSIBLE"),
                         ("group", "person", "Pupil", "REL_GRP_PERS_PUPIL"),),
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
import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
co = Factory.get('Constants')(Factory.get('Database')())

## SOURCE={'datasource'   : "Example SAS",
##         'target'       : "Example BAS",
##         'source_system': "Kjernen",
##         }
SOURCE={'datasource'   : "kjernen",
        'target'       : "cerebrum",
        'source_system': co.system_kjernen,
        }


# Mock up
CONSTANTS={'ADDR_ORG_POSTAL'         : co.address_post,
           'ADDR_PERS_HOME'          : co.address_post_private,
           'CONT_ORG_CONTPHONE'      : co.contact_phone,
           'CONT_ORG_EMAIL'          : co.contact_email,
           'CONT_ORG_URL'            : co.contact_url,
           'CONT_ORG_SWITCHBOARD'    : co.contact_phone,
           'CONT_PERS_HOMEPHONE'     : co.contact_phone_private,
           'CONT_PERS_OFFICEPHOONE'  : co.contact_phone,
           'CONT_PERS_MOBILE'        : co.contact_mobile_phone,   
           ## 'ORG_ID_ORGID'            : co.externalid_orgnr,
           'ORG_ID_ORGID'            : None,
           'ORG_ID_KJERNEID'         : co.externalid_kjerneid_ou,
           ##'ORG_ID_STEDKODE'         : "ORG_ID_STEDKODE",
           'ORG_NAME_ACRONYM'        : "OU_NAME_ACRONYM",
           'ORG_NAME_NAME'           : "OU_NAME_NAME",
           ## 'OU_ID_ORGID'             : co.externalid_orgnr,
           'OU_ID_ORGID'             : None,
           ## 'OU_ID_OUID'              : co.externalid_ouid,
           'OU_ID_OUID'              : None,
           'OU_ID_KJERNEID'          :  co.externalid_kjerneid_ou,
           ## 'OU_ID_STEDKODE'            : "OU_ID_STEDKODE",
           'OU_ID_STEDKODE'          : None,
           'OU_NAME_ID'              : "OU_NAME_ID",
           'OU_NAME_NAME'            : "OU_NAME_NAME",
           'OU_NAME_ACRONYM'         : "OU_NAME_ACRONYM",
           'PERS_ID_FNR'             : co.externalid_fodselsnr,
           'PERS_ID_KJERNEID'        : co.externalid_kjerneid_person,
           ## 'GRP_ID_GRPID'            : co.external_id_groupid,
           'GRP_ID_GRPID'            : None,
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

## OU_PERSPECTIVE=co.perspective_same_source_system
OU_PERSPECTIVE=co.perspective_kjernen

# In ABC Enterprise a group's name is the same as an ID. Therefore
# we map one ID to become the groups name.
## GROUP_NAMES=(co.external_id_groupid,)

# Rewrite rule for group names
# OPTIONAL! Remove if you don't need rewriting.
## GROUP_REWRITE = lambda x: "import_abc_%s" % x

# Mapping of what should be done in relations
## RELATIONS={'ou' : {'person' : {'Employee' : ('affiliation',
##                                              co.affiliation_ansatt),
##                                'Pupil' : ('affiliation',
##                                           co.affiliation_elev),
##                                },
##                     },
##            'group' : {'person' : {'Responsible' : ('memberof',),
##                                   'Pupil' : ('memberof',),
##                                   }
##                       }
##            }
## 
## AFF_STATUS={ co.affiliation_elev : co.affiliation_status_elev_aktiv,
##              co.affiliation_ansatt : co.affiliation_status_ansatt_tekadm
##              }


# arch-tag: fe6dc034-6995-11da-8b95-70cd30d8e9fc
