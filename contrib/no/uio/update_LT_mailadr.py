#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

import getopt
import re
import sys

import cereconf
from Cerebrum import Database
from Cerebrum.Utils import Factory
from Cerebrum.extlib import logging
from Cerebrum.modules.no.uio.access_LT import LT

def usage(exitcode=0):
    print """Usage: [options]
    Updates all e-mail adresses in LT that come from Cerebrum
    -v | --verbose
    -d | --dryrun
    --db-user name: connect with given database username
    --db-service name: connect to given database
    """
    sys.exit(exitcode)

def main():
    db_user = db_service = None
    verbose = dryrun = 0
    try:
        opts, args = getopt.getopt(sys.argv[1:], "dv",
                                   ["dryrun", "verbose", "db-user=",
                                    "db-service="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    for o, val in opts:
        if o in ('-v', '--verbose'):
            verbose += 1
        elif o in ('-d', '--dryrun'):
            dryrun = 1
        elif o in ('--db-user',):
            db_user = val
        elif o in ('--db-service',):
            db_service = val

    logging.fileConfig(cereconf.LOGGING_CONFIGFILE)
    logger = logging.getLogger("console")

    db = Database.connect(user=db_user, service=db_service,
                          DB_driver='Oracle')
    fs = LT(db)
    db = Factory.get('Database')()
    fnr2primary = {}  # TODO: Fill with mapping fnr -> [account_id, uname, email]

    LT_fnr2email = LT.GetAllPersonsUregEmail()
    LT_fnr2user = LT.GetAllPersonsUregUser()

    re_cerebrum_addr = re.compile('[@.]uio\.no$', re.IGNORECASE)
    # TODO: should either be in cereconf, or deduced from the email system

    for fnr in fnr2primary.keys():
        account_id, uname_cerebrum, email_cerebrum = fnr2primary[fnr]

        if LT_fnr2email.has_key(fnr):
	    # Fjern evt. mailadresser som ikke lenger er personens
	    # default-adresse.
            for email_lt in LT_fnr2email[fnr]:
                if email_lt == email_cerebrum or email_cerebrum is None:
                    continue
                logger.debug("%s: Sletter email %s" % (fnr, email_lt))
		LT.DeletePriMailAddr(fnr, email_lt)
                LT_fnr2email[fnr].remove(email_lt)

	    # Nå skal det enten være 0 eller 1 adresser igjen for
	    # denne personen; dersom det fortsatt er 1 adresse igjen,
	    # er den identisk med den nåværende default-adressen
	    # personen har i Ureg.
            if len(LT_fnr2email[fnr]) == 0 and email_cerebrum != '':
		# Personen finnes i LT, men har ikke (lenger) definert
		# noen 'ureg-mailadresse'.
                logger.debug("%s: Skriver email %s" % (fnr, email_cerebrum))
		LT.WritePriMailAddr(fnr, email_cerebrum)

	    # Trenger ikke å ha emailentryen i hashen lenger.
	    del(LT_fnr2email[fnr])

	if LT_fnr2user.has_key(fnr):
            for uname_lt in LT_fnr2user[fnr]:
                if uname_lt == uname_cerebrum:
                    continue
                logger.debug("%s: Sletter uname %s" % (fnr, uname_lt))
		LT.DeletePriUser(fnr, uname_lt)
                LT_fnr2user[fnr].remove(uname_lt)

	    if len(LT_fnr2user[fnr]) == 0:
		# Personen finnes i LT, men har ikke (lenger) definert
		# noen 'ureg-mailadresse'.
                logger.debug("%s: Skriver uname %s" % (fnr, uname_cerebrum))
		LT.WritePriUser(fnr, uname_cerebrum)

	    # Trenger ikke å ha emailentryen i hashen lenger.
	    del(LT_fnr2user[fnr])

    # Hvis det nå finnes entries i hashene fra LT _hvis verdier er
    # ikke-tomme lister_, betyr det at dette er gamle brukere som
    # tidligere har blitt registrert i LT med email-addresse og/eller
    # brukernavn, men ikke lenger finnes i Ureg.  Disse innslagene slettes
    # fra LT.
    for fnr in LT_fnr2email.keys():
        for email in LT_fnr2email[fnr]:
            logger.debug("%s: Sletter email %s" % (fnr, email))
            LT.DeletePriMailAddr(fnr, email)
        del(LT_fnr2email[fnr])

    for fnr in LT_fnr2user.keys():
        for uname in LT_fnr2user[fnr]:
            logger.debug("%s: Sletter uname %s" % (fnr, uname))
            LT.DeletePriUser(fnr, uname)
        del(LT_fnr2user[fnr])

    if dryrun:
        LT.db.rollback()
    else:
        LT.db.commit()

if __name__ == '__main__':
    main()
