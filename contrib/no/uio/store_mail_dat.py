#!/usr/bin/env python
# encoding: utf-8

u"""
Konverteringsprogram.

Tar en dat-fil, produsert av cerebrum/contrib/no/uio/notify_change_password.py,
som eneste argument.

Filen inneholder et picklet objekt, en dict.
Nøklene i denne er account_id-er fra Cerebrum. Verdiene er
en ny dict, indeksert med 'first' (alle) og 'reminder' (noen).
Verdiene er et flyttall, som representerer en timestamp.

Resultatet skal være:
    Konti med 'reminder' satt skal ha en passord-trait med verdien 2,
    resten skal ha verdien 1.
    Verdien av 'first' skal lagres som dato på denne trait.
    I tillegg lagres begge datoer i strval-feltet, som en
    kommaseparert liste. Datoene konverteres til dato-strenger.
"""

import cerebrum_path
from Cerebrum.Utils import Factory
from Cerebrum.modules.PasswordNotifier import PasswordNotifier
import sys, cPickle, mx.DateTime as dt

import locale
locale.setlocale(locale.LC_ALL, "")

def usage(progname):
    print progname, " file"
    print __doc__.encode(locale.getpreferredencoding())
    sys.exit(1)

def main():
    import time
    try:
        progname, arg = sys.argv
    except ValueError:
        usage(sys.argv[0])

    logger = Factory.get_logger("console")
    try:
        fil = open(arg, "r")
        m = cPickle.loads(fil.read())
        fil.close()
    except:
        logger.exception("Could not read file")
        usage(progname)

    db = Factory.get("Database")()
    account = Factory.get("Account")(db)
    #account.find_by_name("bootstrap_account")
    db.cl_init(change_program="pw_migrate")
    pw = PasswordNotifier.get_notifier()
    trait = pw.config.trait
    for account_id, info in m.iteritems():
        account.clear()
        account.find(account_id)
        logger.info("Handling %s", account.account_name)
        times = [time.localtime(info['first'])[:3]]
        logger.info(" first = %4d-%2d-%2d", *times[0])
        if 'reminder' in info:
            times.append(time.localtime(info['reminder'])[:3])
            logger.info(" rem   = %4d-%2d-%2d", *times[0])
        strval = ", ".join([ dt.DateTime(*x).strftime("%Y-%m-%d") for x in times ])
        logger.info(" str   = %s", strval)
        t = {
            'code': trait,
            'date': db.Date(*times[0]),
            'numval': len(times),
            'strval': strval
            }
        account.populate_trait(**t)
        account.write_db()
    db.commit()

if __name__ == '__main__':
    import cereconf
    main()

