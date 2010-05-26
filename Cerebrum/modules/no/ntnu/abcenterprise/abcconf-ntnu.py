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
CLASS_SETTINGS = ['Cerebrum.modules.abcenterprise.ABCEnterprise/Settings']

CLASS_PREPARSER = ['Cerebrum.modules.abcenterprise.ABCEnterprise/ABCPreParser']

CLASS_ANALYZER=['Cerebrum.modules.abcenterprise.ABCEnterprise/ABCAnalyzer']

CLASS_XMLPARSER='cElementTree'

CLASS_ENTITYITERATOR=['Cerebrum.modules.abcenterprise.ABCXmlParsers/XMLEntityIterator']

CLASS_PROPERTIESPARSER=['Cerebrum.modules.no.ntnu.abcenterprise.ABCXmlParsers/XMLPropertiesParserExt']
CLASS_PERSONPARSER=['Cerebrum.modules.no.ntnu.abcenterprise.ABCXmlParsers/XMLPerson2ObjectExt']
CLASS_ORGPARSER=['Cerebrum.modules.no.ntnu.abcenterprise.ABCXmlParsers/XMLOrg2ObjectExt']
CLASS_OUPARSER=['Cerebrum.modules.no.ntnu.abcenterprise.ABCXmlParsers/XMLOU2ObjectExt']
CLASS_GROUPPARSER=['Cerebrum.modules.abcenterprise.ABCXmlParsers/XMLGroup2Object']
CLASS_RELATIONPARSER=['Cerebrum.modules.abcenterprise.ABCXmlParsers/XMLRelation2Object']
CLASS_PROCESSOR=['Cerebrum.modules.no.ntnu.abcenterprise.ABCObj2Cerebrum/ABCObj2Cerebrum']
CLASS_OBJ2CEREBRUM=['Cerebrum.modules.no.ntnu.abcenterprise.Object2Cerebrum/Object2CerebrumExt']


# Types used in ABCEnterprise. Last argument in list is a coded type.
TYPES={'addresstype'  : (("organization", "Postal", "ADDR_ORG_POSTAL"),
                         ("organization", "postal", "ADDR_ORG_POSTAL"),
                         ("organization", "visitor","ADDR_ORG_VISITOR"),
                         ("ou", "visitor", "ADDR_OU_VISITOR"),
                         ("person", "Home", "ADDR_PERS_HOME"),
                         ("person", "office", "ADDR_PERS_OFFICE"),),
       'contacttype'  : (("organization", "Contactphone", "CONT_ORG_CONTPHONE"),
                         ("organization", "e-mail", "CONT_ORG_EMAIL"),
                         ("organization", "url", "CONT_ORG_URL"),
                         ("organization", "switchboard", "CONT_ORG_SWITCHBOARD"),
                         ("ou", "e-mail", "CONT_OU_EMAIL"),
                         ("ou", "url", "CONT_OU_URL"),
                         ("ou", "switchboard", "CONT_OU_SWITCHBOARD"),
                         ("person", "Homephone", "CONT_PERS_HOMEPHONE"),
                         ("person", "Officephone", "CONT_PERS_OFFICEPHONE"),
                         ("person", "officephone", "CONT_PERS_OFFICEPHONE"),
                         ("person", "Mobile", "CONT_PERS_MOBILE"),
                         ("person", "mobile", "CONT_PERS_MOBILE"),),
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
                         ("stedkode", "OU_ID_STEDKODE"),
                         ("studieprogram", "STUDPROG_KODE"),),
       'ounametype'   : (("ID", "OU_NAME_ID"),
                         ("Navn", "OU_NAME_NAME"),
                         ("acronym", "OU_NAME_ACRONYM"),
                         ("name", "OU_NAME_NAME"),),
       'personidtype' : (("fnr", "PERS_ID_FNR"),
                         ("fnr_closed", "PERS_ID_FNR_CLOSED"),
                         ("kjerneid", "PERS_ID_KJERNEID"),
                         ("studentnr", "PERS_ID_STUD_NR"),),
       'keycardtype': (("student", "KEYCARDID_STUDENT"),
                          ("employee", "KEYCARDID_EMPLOYEE"),),
       'printplacetype': (("kjerneid", "PRINTPLACE_ID_KJERNEID"),),
       'groupidtype'  : (("grpid", "GRP_ID_GRPID"),),
       'relationtype' : (("ou", "person", "Employee", "REL_OU_PERS_EMPLOYEE"),
                         ("ou", "person", "Pupil", "REL_OU_PERS_PUPIL"),
                         ("ou", "person", "ansatt", "REL_OU_PERS_EMPLOYEE"),
                         ("org", "person", "ansatt", "REL_OU_PERS_EMPLOYEE"),
                         ("ou", "person", "vitenskaplig", "REL_OU_PERS_EMPLOYEE_RESEARCHER"),
                         ("org", "person", "vitenskaplig", "REL_OU_PERS_EMPLOYEE_RESEARCHER"),
                         ("ou", "person", "tekadm", "REL_OU_PERS_EMPLOYEE_STAFF"),
                         ("org", "person", "tekadm", "REL_OU_PERS_EMPLOYEE_STAFF"),
                         ("ou", "person", "student", "REL_OU_PERS_STUD"),
                         ("org", "person", "student", "REL_OU_PERS_STUD"),
                         ("ou", "person", "bachelor", "REL_OU_PERS_STUD_BACHELOR"),
                         ("org", "person", "bachelor", "REL_OU_PERS_STUD_BACHELOR"),
                         ("ou", "person", "master", "REL_OU_PERS_STUD_MASTER"),
                         ("org", "person", "master", "REL_OU_PERS_STUD_MASTER"),
                         ("ou", "person", "drgrad", "REL_OU_PERS_STUD_PHD"),
                         ("org", "person", "drgrad", "REL_OU_PERS_STUD_PHD"),
                         ("ou", "person", "fagperson", "REL_OU_PERS_EMPLOYEE_TEACHER"),
                         ("org", "person", "fagperson", "REL_OU_PERS_EMPLOYEE_TEACHER"),
                         ("ou", "person", "bilag", "REL_OU_PERS_EMPLOYEE_PARTTIME"),
                         ("org", "person", "bilag", "REL_OU_PERS_EMPLOYEE_PARTTIME"),
                         ("ou", "person", "gjest", "REL_OU_PERS_GUEST"),
                         ("org", "person", "gjest", "REL_OU_PERS_GUEST"),
                         ("ou", "person", "annen", "REL_OU_PERS_OTHER"),
                         ("org", "person", "annen", "REL_OU_PERS_OTHER"),
                         ("ou", "person", "alumni", "REL_OU_PERS_ALUMNI"),
                         ("org", "person", "alumni", "REL_OU_PERS_ALUMNI"),
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

import sys
# Provide Constants:
import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
co = Factory.get('Constants')(Factory.get('Database')())

SOURCE={'datasource'   : "kjernen",
        'target'       : "cerebrum",
        'source_system': co.system_kjernen,
        }


# Mock up
CONSTANTS={'ADDR_ORG_POSTAL'              : co.address_post,
           'ADDR_ORG_VISITOR'             : co.address_street,
           'ADDR_OU_VISITOR'              : co.address_street,
           'ADDR_PERS_HOME'               : co.address_post_private,
           'ADDR_PERS_OFFICE'             : co.address_street,
           'CONT_ORG_CONTPHONE'           : co.contact_phone,
           'CONT_ORG_EMAIL'               : co.contact_email,
           'CONT_ORG_URL'                 : co.contact_url,
           'CONT_ORG_SWITCHBOARD'         : co.contact_phone,
           'CONT_OU_EMAIL'                : co.contact_email,
           'CONT_OU_URL'                  : co.contact_url,
           'CONT_OU_SWITCHBOARD'          : co.contact_phone,
           'CONT_PERS_HOMEPHONE'          : co.contact_phone_private,
           'CONT_PERS_OFFICEPHONE'        : co.contact_phone,
           'CONT_PERS_MOBILE'             : co.contact_mobile_phone,   
           'ORG_ID_KJERNEID'              : co.externalid_kjerneid_ou,
           'ORG_ID_ORGID'                 : co.externalid_business_reg_num,
           'ORG_ID_STEDKODE'              : co.externalid_stedkode,
           'ORG_NAME_ACRONYM'             : "OU_NAME_ACRONYM",
           'ORG_NAME_NAME'                : "OU_NAME_NAME",
           'OU_ID_ORGID'                  : co.externalid_business_reg_num,
           'OU_ID_OUID'                   : None,
           'OU_ID_KJERNEID'               : co.externalid_kjerneid_ou,
           'OU_ID_STEDKODE'               : co.externalid_stedkode,
           'OU_NAME_ID'                   : "OU_NAME_ID",
           'OU_NAME_NAME'                 : "OU_NAME_NAME",
           'OU_NAME_ACRONYM'              : "OU_NAME_ACRONYM",
           'STUDPROG_KODE'                : co.externalid_studieprogram,
           'PERS_ID_FNR'                  : co.externalid_fodselsnr,
           'PERS_ID_KJERNEID'             : co.externalid_kjerneid_person,
           'PERS_ID_STUD_NR'              : None,
           'PERS_ID_FNR_CLOSED'           : None,
           'GRP_ID_GRPID'                 : None,
           'KEYCARDID_EMPLOYEE'           : co.externalid_keycardid_employee,
           'KEYCARDID_STUDENT'            : co.externalid_keycardid_student,
           'PRINTPLACE_ID_KJERNEID'       : None,
           'REL_OU_PERS_EMPLOYEE'         : co.affiliation_status_ansatt_ansatt,
           'REL_OU_PERS_EMPLOYEE_RESEARCHER' : co.affiliation_status_ansatt_vit,
           'REL_OU_PERS_EMPLOYEE_STAFF'   : co.affiliation_status_ansatt_tekadm,
           'REL_OU_PERS_STUD'             : co.affiliation_status_student_student,
           'REL_OU_PERS_STUD_BACHELOR'    : co.affiliation_status_student_bachelor,
           'REL_OU_PERS_STUD_MASTER'      : co.affiliation_status_student_aktiv,
           'REL_OU_PERS_STUD_PHD'         : co.affiliation_status_student_drgrad,
           'REL_OU_PERS_EMPLOYEE_TEACHER' : co.affiliation_status_tilknyttet_fagperson,
           'REL_OU_PERS_EMPLOYEE_PARTTIME' : co.affiliation_status_tilknyttet_bilag,
           'REL_OU_PERS_GUEST'            : co.affiliation_status_tilknyttet_bilag,
           'REL_OU_PERS_OTHER'            : co.affiliation_status_tilknyttet_annen,
           'REL_OU_PERS_ALUMNI'           : co.affiliation_status_alumni_aktiv,
           'NAME_FULL'                    : co.name_full,
           'NAME_FAMILY'                  : co.name_last,
           'NAME_GIVEN'                   : co.name_first,
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
##

##
## check python-code for abc-import.
## we use relations to find affilation from affiliation-status.
## origionally it was intended to do it the opposite way
## (check the lines above).
##
RELATIONS={'ou' : {'person' : { 'tekadm' : ('affiliation',
                                             co.affiliation_status_ansatt_tekadm),
                                'bilag': ('affiliation',
                                            co.affiliation_status_tilknyttet_bilag),
                                'ansatt': ('affiliation',
                                            co.affiliation_status_ansatt_ansatt),
                             'vitenskaplig': ('affiliation',
                                             co.affiliation_status_ansatt_vit),
                             'fagperson' : ('affiliation',
                                             co.affiliation_status_tilknyttet_fagperson),
                             'alumni' : ('affiliation',
                                             co.affiliation_status_alumni_aktiv),
                             'student' : ('affiliation',
                                             co.affiliation_status_student_student),
                             'bachelor' : ('affiliation',
                                             co.affiliation_status_student_bachelor),
                             'master' : ('affiliation',
                                             co.affiliation_status_student_aktiv),
                             'drgrad' : ('affiliation',
                                             co.affiliation_status_student_drgrad),
                             'gjest' : ('affiliation',
                                            co.affiliation_status_tilknyttet_gjest),
                             }
                 },
            'org' : {'person' : { 'tekadm' : ('affiliation',
                                             co.affiliation_status_ansatt_tekadm),
                                'bilag': ('affiliation',
                                            co.affiliation_status_tilknyttet_bilag),
                                'ansatt': ('affiliation',
                                            co.affiliation_status_ansatt_ansatt),
                             'vitenskaplig': ('affiliation',
                                             co.affiliation_status_ansatt_vit),
                             'fagperson' : ('affiliation',
                                             co.affiliation_status_tilknyttet_fagperson),
                             'alumni' : ('affiliation',
                                             co.affiliation_status_alumni_aktiv),
                             'student' : ('affiliation',
                                             co.affiliation_status_student_student),
                             'bachelor' : ('affiliation',
                                             co.affiliation_status_student_bachelor),
                             'master' : ('affiliation',
                                             co.affiliation_status_student_aktiv),
                             'drgrad' : ('affiliation',
                                             co.affiliation_status_student_drgrad),
                            'gjest' : ('affiliation',
                                            co.affiliation_status_tilknyttet_gjest),
                             }
                 }
         }

# arch-tag: fe6dc034-6995-11da-8b95-70cd30d8e9fc
