# -*- coding: iso-8859-1 -*-
# Configuration file for import_userdb_XML.py at UiO

from Cerebrum.Utils import Factory

db = Factory.get('Database')()
co = Factory.get('Constants')(db)

person_aff_mapping = {
    'A' : [co.affiliation_ansatt, co.affiliation_status_ansatt_tekadm],
    'M' : [co.affiliation_ansatt, co.affiliation_status_ansatt_tekadm],
    'V' : [co.affiliation_ansatt, co.affiliation_status_ansatt_vit],
    'F' : [co.affiliation_tilknyttet, co.affiliation_tilknyttet_fagperson],
    'E' : [co.affiliation_student, co.affiliation_status_student_evu],
    'S' : [co.affiliation_student, co.affiliation_status_student_aktiv],
    'G' : [co.affiliation_tilknyttet, co.affiliation_tilknyttet_emeritus]
    }
# *unset* aff_status -> inherit from Person
user_aff_mapping = {
    'A' : {'*unset*': [co.affiliation_ansatt, '*unset*']
           },
    'S' : {'*unset*': [co.affiliation_student, '*unset*']
           },
    'X' : {'C': [co.affiliation_manuell, co.affiliation_manuell_cicero],
           'D' : [co.affiliation_upersonlig, co.affiliation_upersonlig_felles],
           'E' : [co.affiliation_manuell, co.affiliation_manuell_ekst_person],
           'F' : '*special*',
           'G' : [co.affiliation_manuell, co.affiliation_manuell_gjest],
           'J' : [co.affiliation_manuell, co.affiliation_manuell_spes_avt],
           'K' : [co.affiliation_upersonlig, co.affiliation_upersonlig_kurs],
           'L' : [co.affiliation_upersonlig, co.affiliation_upersonlig_pvare],
           'N' : [co.affiliation_manuell, co.affiliation_manuell_biotech],
           'O' : [co.affiliation_manuell, co.affiliation_manuell_sio],
           'P' : [co.affiliation_upersonlig, co.affiliation_upersonlig_term_maskin],
           'R' : [co.affiliation_manuell, co.affiliation_manuell_radium],
           'T' : [co.affiliation_manuell, co.affiliation_manuell_notur],
           'W' : [co.affiliation_manuell, co.affiliation_manuell_gjesteforsker],
           'Z' : [co.affiliation_manuell, co.affiliation_manuell_sivilarb],
           'c' : [co.affiliation_upersonlig, co.affiliation_upersonlig_bib_felles],
           'e' : [co.affiliation_tilknyttet, co.affiliation_tilknyttet_emeritus],
           'f' : [co.affiliation_upersonlig, co.affiliation_upersonlig_uio_forening],
           # TODO: h = sommerskole.  Hva er rett affiliation?
           'h' : [co.affiliation_student, co.affiliation_status_student_aktiv],
           'j' : [co.affiliation_manuell, co.affiliation_manuell_kaja_kontrakt],
           'k' : [co.affiliation_manuell, co.affiliation_manuell_konsulent],
           'n' : [co.affiliation_manuell, co.affiliation_manuell_notam2],
           'p' : [co.affiliation_tilknyttet, co.affiliation_tilknyttet_ekst_stip],
           'r' : [co.affiliation_manuell, co.affiliation_manuell_radium],
           'u' : [co.affiliation_manuell, co.affiliation_manuell_gjest],
           # TODO: z = frischsenteret.  Hva er rett affiliation?
           'z' : [co.affiliation_manuell, co.affiliation_manuell_ekst_person],
           # TODO: noen har blank.  Hva er rett affiliation?
           '*unset*' : [co.affiliation_manuell, co.affiliation_manuell_ekst_person],
           },
    'a' : {'*unset*': [co.affiliation_ansatt, '*unset*']
           },
    's' : {'*unset*': [co.affiliation_student, '*unset*']
           }
    }

default_ou = "900199"
