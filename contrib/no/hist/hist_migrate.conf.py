# -*- coding: iso-8859-1 -*-
# Configuration file for import_userdb_XML.py at HiST

from Cerebrum.Utils import Factory

db = Factory.get('Database')()
co = Factory.get('Constants')(db)

person_aff_mapping = {
    'ansatt' : [co.affiliation_ansatt, co.affiliation_status_ansatt_tekadm],
    'student' : [co.affiliation_student, co.affiliation_status_student_evu],
    }
# *unset* aff_status -> inherit from Person
user_aff_mapping = {
    'ansatt' : {'*unset*': [co.affiliation_ansatt, '*unset*']
           },
    'student' : {'*unset*': [co.affiliation_student, '*unset*']
           }
    }

default_ou = "000000"


shell2shellconst = {
    }

ureg_domtyp2catgs = {
    }

# arch-tag: b231ff53-0751-4d47-95eb-9dea490d2c61
