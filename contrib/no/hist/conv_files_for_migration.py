#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# Converts files for use with import_userdb_XML.py

import getopt
import sys
from Cerebrum.modules.no import fodselsnr

fake_fnr = 1
known_users = {}

## cerebrum=# select o.ou_id, acronym, institusjon, fakultet, institutt, avdeling from stedkode s, ou_info o where o.ou_id=s.ou_id and o.acronym in ('AØA', 'AHS', 'AFT', 'ALT', 'HA', 'AiTEL');
##  ou_id | acronym | institusjon | fakultet | institutt | avdeling 
## -------+---------+-------------+----------+-----------+----------
##   6506 | HA      |         185 |        1 |         0 |        0
##   6512 | AFT     |         185 |        2 |         0 |        0
##   6524 | AHS     |         185 |        3 |         0 |        0
##   6542 | ALT     |         185 |        4 |         0 |        0
##   6568 | AA      |         185 |        5 |         0 |        0
## (5 rows)

ou_mapping = {'AØA': "050000", 'AHS': "030000", 'AFT': "020000",
              'ALT': "040000", 'HA': "010000",
              # MERK: Ukjent stedkode for disse:
              'AiTEL': "000000", 'AOA': "000000"}

def read_person_file(fname, persons, ftype):
    global fake_fnr
    f = open(fname)
    for line in f.readlines():
        tmp = line.rstrip().split(":")
        if known_users.has_key(tmp[0]):
            print "WARNING: skipping duplicate user %s" % tmp
            continue
        known_users[tmp[0]] = 1
        tmp.append(ftype)
        tmp[2] = ou_mapping[tmp[2]]
        if not tmp[1]:
            tmp[1] = fake_fnr
            fake_fnr += 1
        persons.setdefault(tmp[1], []).append(tmp)

def gen_file(ansatt_file, reservert_file, student_file, out_file):
    persons = {}
    read_person_file(ansatt_file, persons, 'ansatt')
    read_person_file(student_file, persons, 'student')
    out = open(out_file, 'w')
    out.write('<?xml version="1.0" encoding="ISO-8859-1"?>\n<data>\n  <persons>\n')
    for k in persons.keys():
        p = persons[k][0]
        uname, fnr, ou, lname, fname, ftype = p
        bdate = ''
        if fnr:
            try:
                bdate = ' bdate="%s"' % "-".join(["%i" % x for x in fodselsnr.fodt_dato(fnr)])
            except fodselsnr.InvalidFnrError:
                fnr = ''
        tmp =  '    <person%s>\n' % bdate
        tmp += '      <uio psko="%s" pinst="184">\n' % ou
        tmp += '        <ptype val="%s"/>\n' % ftype
        tmp += '      </uio>\n'
        if fnr:
            tmp += '      <extid type="fnr" val="%s"/>\n' % fnr
        tmp += '      <name type="fname" val="%s"/>\n' % fname
        tmp += '      <name type="lname" val="%s"/>\n' % lname
        for i in range(len(persons[k])):
            uname, fnr, ou, lname, fname, ftype = persons[k][i]
            tmp += '      <user uname="%s">\n' % uname
            tmp += '        <uio utype="%s" usko="%s"/>\n' % (ftype, ou)
            tmp += '      </user>\n'
        tmp += '    </person>\n'
        out.write(tmp)
    tmp = '  </persons>\n  <nonpersons>\n    <group_owned name="bootstrap_group">\n'
    f = open(reservert_file)
    for line in f.readlines():
        line = line.rstrip()
        if known_users.has_key(line):
            print "WARNING: skipping duplicate user %s" % line
            continue
        known_users[line] = 1
        tmp += '      <user uname="%s"/>\n' % line
    tmp += '    </group_owned>\n  </nonpersons>\n</data>\n'
    out.write(tmp)
    out.close()

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'a:r:s:o:',
                                   ['ansatte=', 'reserverte=', 'studenter=', 'out='])
    except getopt.GetoptError:
        print ("Example: convfiles.py -a ansatte-20030801.txt -r reserverte-passord.txt "+
               "-s studenter-20030730.txt -o file.xml")
        sys.exit(1)

    for opt, val in opts:
        if opt in ('-a', '--ansatte'):
            ans = val
        elif opt in('-r', '--reserverte'):
            res = val
        elif opt in('-s', '--studenter'):
            stud = val
        elif opt in('-o', '--out'):
            out = val
    gen_file(ans, res, stud, out)

if __name__ == '__main__':
    main()
