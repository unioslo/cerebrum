#! /usr/bin/env python
# -*- encoding: iso-8859-1 -*-
import os
import sys
import time
import getopt
import mx

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum import Errors

fileMode = 'w'
bufferSize = 16384
               
class Export2Kjernen(object):
    
    def __init__(self, outfile, verbose, doTiming):
        self.db = Factory.get('Database')()
        self.co = Factory.get('Constants')(self.db)
        self._person = Factory.get('Person')(self.db)
        self._ou = Factory.get('OU')(self.db)
        self._account = Factory.get('Account')(self.db)
        self._iso_format = '%Y.%m.%d'
        self.outfile = outfile
        self.verbose = verbose
        self.doTiming = doTiming
        self.affiliations = {
            self.co.affiliation_tilknyttet :    'tilknyttet',
            self.co.affiliation_ansatt:         'ansatt',
            self.co.affiliation_alumni:         'alumni',
            self.co.affiliation_student:        'student'
        }
        ## not used at the moment, maybe later...
        self.affiliations_status = {
            self.co.affiliation_status_tilknyttet_bilag:        'bilag',
            self.co.affiliation_status_ansatt_ansatt:           'ansatt',
            self.co.affiliation_status_student_student:         'student',
            self.co.affiliation_status_student_bachelor:        'bachelor',
            self.co.affiliation_status_tilknyttet_annen:        'annen',
            self.co.affiliation_status_student_aktiv:           'master',
            self.co.affiliation_status_tilknyttet_gjest:        'gjest',
            self.co.affiliation_status_tilknyttet_fagperson:    'fagperson',
            self.co.affiliation_status_ansatt_vit:              'vitenskaplig',
            self.co.affiliation_status_alumni_aktiv:            'alumni',
            self.co.affiliation_status_student_drgrad:          'drgrad',
            self.co.affiliation_status_ansatt_tekadm:           'tekadm'
        }

    def get_stedkoder(self):
        if self.verbose:
            print 'Fetching stedkoder...'
        koder = {}
        for row in self._ou.get_stedkoder():
            koder[row['ou_id']] = '%03d%02d%02d%02d' %(row['institusjon'], row['fakultet'], row['institutt'], row['avdeling'])
        return koder

    def get_birthdates(self):
        if self.verbose:
            print 'Fetching birthdates...'
        bdates = {}
        for row in self._person.list_persons():
            bdates[row['person_id']] = row['birth_date'].strftime(self._iso_format)
        return bdates

    def get_nins(self):
        if self.verbose:
            print 'Fetching nins...'
        nins = {}
        for row in self._person.list_external_ids(id_type=self.co.externalid_fodselsnr):
            nins[row["entity_id"]]=row["external_id"]
        return nins

    def get_emails(self):
        if self.verbose:
            print 'Fetching emailaddreses...'
        emails = {}
        for row in self._person.list_contact_info(contact_type=self.co.contact_email):
            emails[row["entity_id"]]=row["contact_value"]
        return emails
     
    def get_lastnames(self):
        if self.verbose:
            print 'Fetching lastnames...'
        lastnames = {}
        for row in self._person.list_persons_name(name_type=self.co.name_last):
            lastnames[row['person_id']] = row['name']
        return lastnames

    def get_firstnames(self):
        if self.verbose:
            print 'Fetching firstnames...'
        firstnames = {}
        for row in self._person.list_persons_name(name_type=self.co.name_first):
            firstnames[row['person_id']] = row['name']
        return firstnames

    def get_entities(self):
        if self.verbose:
            print 'Fetching entities...'
        entities = {}
        for row in self._account.list_names(self.co.account_namespace):
            entities[row['entity_id']] = row['entity_name']
        return entities

    def get_accounts(self, entities):
        if self.verbose:
            print 'Fetching accounts...'
        accounts = {}
        for row in self._account.list():
            accounts[row['owner_id']] = entities[row.get('account_id', '')]
        return accounts

    def get_affiliations(self):
        if self.verbose:
            print 'Fetching affiliations...'
        affs = {}
        affs_status = {}
        ous = {}
        aff_created = {}
        for row in self._person.list_affiliations():
            affs[row['person_id']] = row['affiliation']
            ## affiliation status is not used at the moment, maybe later...
            ## affs_status[row['person_id']] = row['status']
            ous[row['person_id']] = row['ou_id']
            aff_created[row['person_id']] = row['create_date'].strftime(self._iso_format)
            
        ## affiliation status is not used at the moment, maybe later...
        ## return (affs, ous, affs_status, aff_created)
        return (affs, ous, aff_created)
 
    def write_file(self):
        if self.verbose:
            print 'Writing persons to', self.outfile
        i = 0
        f = open(self.outfile, fileMode, bufferSize)
        for k in self.nins.keys():
            ## affiliation status is not used at the moment, maybe later...
            ## out_line = '%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;\n' % \
            out_line = '%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;\n' % \
                    (k,
                    self.nins[k][:6],
                    self.nins[k][6:],
                    self.birthdates.get(k, ''),
                    self.firstnames.get(k,''),
                    self.lastnames.get(k, ''),
                    self.emails.get(k, ''),
                    self.affiliations.get(self.affs.get(k, ''), ''),
                    ## self.affiliations_status.get(self.affs_status.get(k, ''),''),
                    self.stedkoder.get(self.ous.get(k, ''), ''),
                    self.accounts.get(k, ''),
                    self.created.get(k, ''))

            f.write(out_line)
            i += 1

        f.flush()
        f.close()
        if self.verbose:
            print '--------------------------------------------------------------------------------'
            print 'Total persons written:',i
            print '================================================================================'

    def print_time(self, before):
        print 'Time = %.2f secs' % (time.time() - before)

    def export_persons(self):
        totalBefore = 0
        before = 0
        if self.doTiming:
            totalBefore = time.time()
            before = totalBefore
        self.stedkoder = self.get_stedkoder()
        if self.doTiming and self.verbose:
            self.print_time(before)
            before = time.time()
        self.birthdates = self.get_birthdates()
        if self.doTiming and self.verbose:
            self.print_time(before)
            before = time.time()
        self.nins = self.get_nins()
        if self.doTiming and self.verbose:
            self.print_time(before)
            before = time.time()
        self.emails = self.get_emails()
        if self.doTiming and self.verbose:
            self.print_time(before)
            before = time.time()
        ## affiliation status is not used at the moment, maybe later...
        ## (self.affs, self.ous, self.affs_status, self.created) = self.get_affiliations()
        (self.affs, self.ous, self.created) = self.get_affiliations()
        if self.doTiming and self.verbose:
            self.print_time(before)
            before = time.time()
        self.lastnames = self.get_lastnames()
        if self.doTiming and self.verbose:
            self.print_time(before)
            before = time.time()
        self.firstnames = self.get_firstnames()
        if self.doTiming and self.verbose:
            self.print_time(before)
            before = time.time()
        self.accounts = self.get_accounts(self.get_entities())
        if self.doTiming and self.verbose:
            self.print_time(before)
            before = time.time()
        self.write_file()
        if self.doTiming and self.verbose:
            self.print_time(before)
        if self.doTiming:
            print 'Total time = %.2f secs' % (time.time() - totalBefore)

def usage(p):
    print '\nUsage: %s [OPTIONS]\n\n    OPTIONS\n\t-h, --help\t\tshow this help and exit.\n\t-o FILE, --output=FILE\twrite report to FILE.\n\t-t  --time\t\tcombination with verbose will show seconds\n\t\t\t\tper. operation and total; otherwise just\n\t\t\t\ttotal time.\n\t-v, --verbose\t\tshow status-messages to stdout.\n' % p


def main(argv):
    opts = None
    args = None
    prog = os.path.basename(argv[0])
    try:
        opts, args = getopt.getopt(argv[1:], 'ho:tv', ['help', 'output=', 'time', 'verbose'])
    except getopt.GetoptError, err:
        print str(err)
        usage(prog)
        sys.exit(1)
    output = None
    verbose = False
    doTiming = False
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            usage(prog)
            sys.exit(0)
        elif opt in ('-v', '--verbose'):
            verbose = True
        elif opt in ('-o', '--output'):
            output = arg
        elif opt in ('-t', '--time'):
            doTiming = True
        else:
            assert False, "unhandled option"
            sys.exit(2)
    if not output:
        usage(prog)
        sys.exit(3)
    export_kj = Export2Kjernen(output, verbose, doTiming)
    export_kj.export_persons()
    

if __name__ == '__main__':
    main(sys.argv)

