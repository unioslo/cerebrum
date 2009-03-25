#! /usr/bin/env python
# -*- encoding: iso-8859-1 -*-
import sys
import getopt
import mx

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum import Errors


affiliations = {
                93 : 'tilkyttet',
                94 : 'ansatt',
                95 : 'alumni',
                96 : 'student',
                }
lastName = 8
firstName = 11

valueDomainAccount = 4
 
outFileName = '/tmp/cerebrum_to_kjernen.sdv'
fileMode = 'w'
bufferSize = 16384
               
class Export2Kjernen(object):
    
    def __init__(self):
        self.db = Factory.get('Database')()
        self.co = Factory.get('Constants')(self.db)
        self._person = Factory.get('Person')(self.db)
        self._ou = Factory.get('OU')(self.db)
        self._account = Factory.get('Account')(self.db)
        self._iso_format = '%Y-%m-%d'
        self._norw_format = '%d%m%y'

    def get_stedkoder(self):
        koder = {}
        for row in self._ou.get_stedkoder():
            koder[row['ou_id']] = '%03d%02d%02d%02d' %(row['institusjon'], row['fakultet'], row['institutt'], row['avdeling'])
        return koder

    def get_birthdates(self):
        bdates = {}
        for row in self._person.list_persons():
            bdates[row['person_id']] = row['birth_date'].strftime(self._iso_format)
        return bdates

    def get_nins(self):
        nins = {}
        ## for row in self._person.list_external_ids(self.co.system_kjernen, self.co.externalid_fodselsnr):
        for row in self._person.list_external_ids(id_type=self.co.externalid_fodselsnr):
            nins[row["entity_id"]]=row["external_id"]
        return nins

    def get_emails(self):
        emails = {}
        ## for row in self._person.list_contact_info(self.co.system_kjernen, self.co.contact_email):
        for row in self._person.list_contact_info(contact_type=self.co.contact_email):
            emails[row["entity_id"]]=row["contact_value"]
        return emails
     
    def get_lastnames(self):
        lastnames = {}
        for row in self._person.list_persons_name(name_type=lastName):
            lastnames[row['person_id']] = row['name']
        return lastnames

    def get_firstnames(self):
        firstnames = {}
        for row in self._person.list_persons_name(name_type=firstName):
            firstnames[row['person_id']] = row['name']
        return firstnames

    def get_entities(self):
        entities = {}
        for row in self._account.list_names(valueDomainAccount):
            entities[row['entity_id']] = row['entity_name']
        return entities

    def get_accounts(self, entities):
        accounts = {}
        for row in self._account.list():
            accounts[row['owner_id']] = entities[row.get('account_id', '')]
        return accounts

    def get_affiliations(self):
        affs = {}
        ous = {}
        ## for row in self._person.list_affiliations(source_system=self.co.system_kjernen):
        for row in self._person.list_affiliations():
            affs[row['person_id']] = row['affiliation']
            ous[row['person_id']] = row['ou_id']
        return (affs, ous)
        
    def export_persons(self):
        print ''
        print 'Fetching stedkoder...'
        stedkoder = self.get_stedkoder()

        print 'Fetching birthdates...'
        birthdates = self.get_birthdates()

        print 'fetching nins...'
        nins = self.get_nins()
         
        print 'Fetching emails...'
        emails = self.get_emails()

        print 'Fetching affiliations...'
        (affs, ous) = self.get_affiliations()

        print 'Fetching lastnames...'
        lastnames = self.get_lastnames()

        print 'Fetching firstnames...'
        firstnames = self.get_firstnames()
    
        print 'fetching accounts...'
        accounts = self.get_accounts(self.get_entities())

        i = 0
        f = open(outFileName, fileMode, bufferSize)
        for k in nins.keys():
            out_line = '%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;\n' % \
                    (k,
                    nins[k][:6],
                    nins[k][6:],
                    birthdates.get(k, ''),
                    firstnames.get(k,''),
                    lastnames.get(k, ''),
                    emails.get(k, ''),
                    affiliations.get(affs.get(k, ''),''),
                    stedkoder.get(ous.get(k, ''), ''),
                    accounts.get(k, ''))
            
            f.write(out_line)
            i += 1
            ## if (i % 100) == 0:
            ##     print 'Persons written',i

        print ''
        print '--------------------------------------------------------------------------------'
        print 'Total persons written:',i
        print '================================================================================'
        print ''

        f.flush()
        f.close()

def main(*args):
    export_kj = Export2Kjernen()
    export_kj.export_persons()
    

if __name__ == '__main__':
    main(sys.argv[1:])

