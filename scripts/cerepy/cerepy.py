#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Original author unknown (but it's someone in Cerebrum)
#

# Generelt oppsett
import rlcompleter
import readline
import code

from mx import DateTime

# Cerebrumoppsett
import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.modules import CLHandler

readline.parse_and_bind('tab:complete')

# Skriv ut litt info om hva som skjer
print """\033[92mCurrent config:\033[37m
\033[94mimport cerebrum_path, cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.modules import CLHandler
db = Factory.get('Database')()
cl = CLHandler.CLHandler(db)
db.cl_init(change_program='cereutvsh')\033[37m"""

# Hent db og init cl
db = Factory.get('Database')()
cl = CLHandler.CLHandler(db)
db.cl_init(change_program='cereutvsh')

# Definererer variabelnavn og klasser.
# Dette kan potensielt sett brukes til å
# autopuppulere variable, som en del av en
# auto-test-config-miljø-sak
attrs = {'en': 'Entity',
         'pe': 'Person',
         'di': 'Disk',
         'co': 'Constants',
         'ac': 'Account',
         'ou': 'OU',
         'gr': 'Group',
         'pu': 'PosixUser',
         'pg': 'PosixGroup'}
inited = {}
for x in attrs:
    try:
        inited[x] = Factory.get(attrs[x])(db)
    except ValueError, e:
        print "\033[1;31m%s\033[0;37m" % e
    except ImportError, e:
        print "\033[1;31m%s\033[0;37m" % e
    finally:
        print "\033[1;94m%s = Factory.get('%s')(db)\033[0;37m" % (x, attrs[x])
locals().update(inited)
del inited
del attrs

# Disse linjene kan gi deg fine farger på promt.
# Her er det verdt å merke seg at kontrollkarakterene for å
# sette farger på promptet er lagt inn mellom \001 og \002.
# \001 og \002 angir at karakterene mellom disse to karakterene
# ikke skal telles av readline. Uten disse blir ikke readline
# mindre hyggelig å bruke.
code.sys.ps1 = '\001\033[1;95m\002>>>\001\033[0;37m\002 '
code.sys.ps2 = '\001\033[1;93m\002...\001\033[0;37m\002 '

# Start den interaktive sesjonen
code.interact(local=locals())

