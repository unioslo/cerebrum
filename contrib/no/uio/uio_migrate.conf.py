# -*- coding: iso-8859-1 -*-
# Configuration file for import_userdb_XML.py at UiO

# Copyright 2003 University of Oslo, Norway
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
    'A' : {'*unset*': [co.affiliation_ansatt, '*unset*'],
           '*fallback*': [co.affiliation_manuell,
                          co.affiliation_manuell_inaktiv_ansatt],
           },
    'S' : {'*unset*': [co.affiliation_student, '*unset*'],
           '*fallback*': [co.affiliation_manuell,
                          co.affiliation_manuell_inaktiv_student],
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
           't' : [co.affiliation_ansatt, '*unset*'],
           'u' : [co.affiliation_manuell, co.affiliation_manuell_gjest],
           # TODO: z = frischsenteret.  Hva er rett affiliation?
           'z' : [co.affiliation_manuell, co.affiliation_manuell_ekst_person],
           # TODO: noen har blank.  Hva er rett affiliation?
           '*unset*' : [co.affiliation_manuell, co.affiliation_manuell_ekst_person],
           },
    'a' : {'*unset*': [co.affiliation_ansatt, '*unset*'],
           '*fallback*': [co.affiliation_manuell,
                          co.affiliation_manuell_inaktiv_ansatt],
           },
    's' : {'*unset*': [co.affiliation_student, '*unset*'],
           '*fallback*': [co.affiliation_manuell,
                          co.affiliation_manuell_inaktiv_student],
           }
    }

default_ou = "900199"



shell2shellconst = {
    'bash': co.posix_shell_bash,
    'csh': co.posix_shell_csh,
    'false': co.posix_shell_false,
    'nologin': co.posix_shell_nologin,
    'nologin.autostud': co.posix_shell_nologin_autostud,  # TODO: more shells, (and their path)
    'nologin.brk': co.posix_shell_nologin_brk,
    'nologin.chpwd': co.posix_shell_nologin_chpwd,
    'nologin.ftpuser': co.posix_shell_nologin_ftpuser,
    'nologin.nystudent': co.posix_shell_nologin_nystudent,
    'nologin.pwd': co.posix_shell_nologin_pwd,
    'nologin.sh': co.posix_shell_nologin_sh,
    'nologin.sluttet': co.posix_shell_nologin_sluttet,
    'nologin.stengt': co.posix_shell_nologin_stengt,
    'nologin.teppe': co.posix_shell_nologin_teppe,
    'puberos': co.posix_shell_puberos,
    'sftp-server': co.posix_shell_sftp_server,
    'sh': co.posix_shell_sh,
    'tcsh': co.posix_shell_tcsh,
    'zsh': co.posix_shell_zsh,
    }

ureg_domtyp2catgs = {
    'u': (co.email_domain_category_uidaddr,),
    'U': (co.email_domain_category_uidaddr,
          co.email_domain_category_include_all_uids),
    'p': (co.email_domain_category_cnaddr,),
    'P': (co.email_domain_category_cnaddr,
          co.email_domain_category_include_all_uids),
    'N': ()
    }

spamlvl2const = {'0': co.email_spam_level_none,
                 '1': co.email_spam_level_standard,
                 '2': co.email_spam_level_heightened,
                 '3': co.email_spam_level_aggressive,
                 '*default*': co.email_spam_level_none
                 }
spamact2const = {'0': co.email_spam_action_none,
                 '1': co.email_spam_action_folder,
                 '2': co.email_spam_action_delete,
                 '*default*': co.email_spam_action_none
                 }
