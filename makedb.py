#!/usr/bin/env python

import sys
import re

from Cerebrum import Database
from Cerebrum import cereconf

def main():
    Cerebrum = Database.connect(user=cereconf.CEREBRUM_DATABASE_USER)
    makedbs(Cerebrum)


def makedbs(Cerebrum):
    for f in ('drop_core_tables.sql', 'core_tables.sql', 'core_data.sql', 'pop.sql', 'mod_stedkode.sql'):
        runfile("design/%s" % f, Cerebrum)

def runfile(fname, Cerebrum):
    print "Reading file: <%s>" % fname
    f = file(fname)
    text = "".join(f.readlines())
    long_comment = re.compile(r"/\*.*?\*/", re.DOTALL)
    text = re.sub(long_comment, "", text)
    line_comment = re.compile(r"--.*")
    text = re.sub(line_comment, "", text)
    text = re.sub(r"\s+", " ", text)
    for ddl in text.split(";"):
        ddl = ddl.strip()
        if not ddl:
            continue
        try:
            res = Cerebrum.execute(ddl)
        except:
            print "CMD: [%s] -> " % ddl
            print "  database error:", sys.exc_info()[1]
        else:
            print "ret: "+str(res)
    Cerebrum.commit()

if __name__ == '__main__':
    main()
