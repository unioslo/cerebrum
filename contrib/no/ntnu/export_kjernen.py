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
    
    def get_stedkoder(self):
        if self.verbose:
            print 'Fetching stedkoder...'
        koder = {}
        ## only ous with stedkode
        for row in self._ou.get_stedkoder():
            koder[row['ou_id']] = '%03d%02d%02d%02d' %(row['institusjon'], row['fakultet'], row['institutt'], row['avdeling'])
        return koder

    def get_birthdates(self):
        """Fetch all birthdates as YYYY.mm.dd."""
        if self.verbose:
            print 'Fetching birthdates...'
        bdates = {}
        for row in self._person.list_persons():
            bdates[row['person_id']] = row['birth_date'].strftime(self._iso_format)
        return bdates

    def get_nins(self):
        """Link person til her/his norwegian national identity numbers."""
        if self.verbose:
            print 'Fetching nins...'
        nins = {}
        for row in self._person.list_external_ids(id_type=self.co.externalid_fodselsnr):
            nins[row["entity_id"]]=row["external_id"]
        return nins

    def get_emails(self):
        """Link person til her/his email-address."""
        if self.verbose:
            print 'Fetching emailaddreses...'
        emails = {}
        for row in self._person.list_contact_info(contact_type=self.co.contact_email):
            emails[row["entity_id"]]=row["contact_value"]
        return emails
     
    def get_lastnames(self):
        """Link person til her/his surname."""
        if self.verbose:
            print 'Fetching lastnames...'
        lastnames = {}
        for row in self._person.list_persons_name(name_type=self.co.name_last):
            lastnames[row['person_id']] = row['name']
        return lastnames

    def get_firstnames(self):
        """Link person til her/his givenname(s)."""
        if self.verbose:
            print 'Fetching firstnames...'
        firstnames = {}
        for row in self._person.list_persons_name(name_type=self.co.name_first):
            firstnames[row['person_id']] = row['name']
        return firstnames

    def get_entities(self):
        """Fetch all usernames."""
        if self.verbose:
            print 'Fetching entities...'
        entities = {}
        for row in self._account.list_names(self.co.account_namespace):
            entities[row['entity_id']] = row['entity_name']
        return entities
    
    def get_traits(self):
        """Fetch all usernames that are defined as a primary username."""
        if self.verbose:
            print 'Fetching traits...'
        traits = {}
        for row in self._account.list_traits(code=self.co.trait_primary_account):
            traits[row['entity_id']] = row['target_id']
        return traits

    def get_accounts(self):
        """Link person and username."""
        if self.verbose:
            print 'Fetching accounts...'
        
        entities = self.get_entities()
        traits = self.get_traits()
        
        accounts = {}
        for row in self._account.list():
            ## fetch only usernames.
            if entities.get(traits.get(row['owner_id'], ''), ''):
                accounts[row['owner_id']] = \
                    entities.get(traits.get(row['owner_id'], ''), '')
        return accounts


    def get_affiliations(self):
        """Connect person to her/his affilations.
            
            Affiliations are returned as:
            res = {
                personid: [('aff', 'ouid', 'aff_status', 'created'), ...],
                personid1 : [(),],
             }
        """
        if self.verbose:
            print 'Fetching affiliations...'
        
        personid_to_afflist = {}
        
        for row in self._person.list_affiliations():
            aff = self._person.const.PersonAffiliation(row['affiliation']).str.lower()
            aff_status = self._person.const.PersonAffStatus(row['status']).str.lower()
            ouid = row['ou_id']
            created = row['create_date'].strftime(self._iso_format)
            
            personid_to_afflist.setdefault(row['person_id'], []).append((aff, ouid, aff_status, created))
            
        return personid_to_afflist
    
    def exclusively_alumni(self, affiliations):
        """ Persons with alumni as the only affiliation should be
        excluded from the export. We don't care whether the person might have
        alumni as a secondary affiliation """
        return (len(affiliations) == 1 and affiliations[0][0] == "alumni")
    
    def contains_gjest(self, affiliations):
        """ Persons having 'gjest' affiliations should be treated differently
        than others."""
        for affiliation in affiliations:
            if affiliation[0] == "tilknyttet" and affiliation[2] == "gjest":
                return True
        return False 
    
    def get_one_line(self, personid, account, stedkoder, birthdates, nins, emails,
                   affiliations, lastnames, firstnames, accounts, affs_for_person):
        for affiliation in affs_for_person:
            if affiliation[0] != "alumni":
                out_line = '%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;\n' % \
                    (personid,
                    nins[personid][:6],
                    nins[personid][6:],
                    birthdates.get(personid, ''),
                    firstnames.get(personid,''),
                    lastnames.get(personid, ''),
                    emails.get(personid, ''),
                    affiliation[0],
                    affiliation[2],
                    stedkoder.get(affiliation[1], ''),
                    account,
                    affiliation[3])
                return out_line
                    
    def write_file(self, stedkoder, birthdates, nins, emails,
                   affiliations, lastnames, firstnames, accounts):
        if self.verbose:
            print 'Writing persons to', self.outfile
        i = 0
        no_account_counter = 0
        alumni_counter = 0
        f = open(self.outfile, fileMode, bufferSize)
        
        for personid in nins.keys():
            # person should have account(s)
            if accounts.has_key(personid):
                account = accounts[personid]

                # person should have affiliation(s)
                if affiliations.has_key(personid):
                    affs_for_person = affiliations[personid]
                    
                    if not self.exclusively_alumni(affs_for_person):
                        if self.contains_gjest(affs_for_person):
                            for affiliation in affs_for_person:
                                # only export tilknyttet/gjest
                                if affiliation[0] == "tilknyttet" and affiliation[2] == "gjest":
                                    out_line = '%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;\n' % \
                                        (personid,
                                        nins[personid][:6],
                                        nins[personid][6:],
                                        birthdates.get(personid, ''),
                                        firstnames.get(personid,''),
                                        lastnames.get(personid, ''),
                                        emails.get(personid, ''),
                                        affiliation[0],
                                        affiliation[2],
                                        stedkoder.get(affiliation[1], ''),
                                        account,
                                        affiliation[3])
            
                                    f.write(out_line)
                                    i += 1
                        else:
                            # doesn't contain 'gjest'
                            out_line = self.get_one_line(personid, account, stedkoder, birthdates, nins, emails,
                                                         affiliations, lastnames, firstnames, accounts, affs_for_person)
                            f.write(out_line)
                            i += 1
                            
                    else:
                        alumni_counter += 1
            else:
                no_account_counter += 1

        f.flush()
        f.close()
        if self.verbose:
            print '--------------------------------------------------------------------------------'
            print 'Total lines written:',i
            print 'Total alumnis excluded from the list: ', alumni_counter
            print 'Persons with no account:',no_account_counter
            print '================================================================================'

    def print_time(self, before):
        print 'Time = %.2f secs' % (time.time() - before)

    def export_persons(self):
        totalBefore = 0
        before = 0
        # retrieve stedkoder
        if self.doTiming:
            totalBefore = time.time()
            before = totalBefore
        stedkoder = self.get_stedkoder()
        
        # retrieve birthdates
        if self.doTiming and self.verbose:
            self.print_time(before)
            before = time.time()
        birthdates = self.get_birthdates()
        
        # retrieve NINs
        if self.doTiming and self.verbose:
            self.print_time(before)
            before = time.time()
        nins = self.get_nins()
        
        # retrieve emails
        if self.doTiming and self.verbose:
            self.print_time(before)
            before = time.time()
        emails = self.get_emails()
        
        # retrieve affiliations
        if self.doTiming and self.verbose:
            self.print_time(before)
            before = time.time()
        affiliations = self.get_affiliations()
        
        # retrieve lastnames
        if self.doTiming and self.verbose:
            self.print_time(before)
            before = time.time()
        lastnames = self.get_lastnames()
        
        # retrieve firstnames
        if self.doTiming and self.verbose:
            self.print_time(before)
            before = time.time()
        firstnames = self.get_firstnames()

        # retrieve accounts
        if self.doTiming and self.verbose:
            self.print_time(before)
            before = time.time()
        accounts = self.get_accounts()

        # write output
        if self.doTiming and self.verbose:
            self.print_time(before)
            before = time.time()
        self.write_file(stedkoder, birthdates, nins, emails,
                        affiliations, lastnames, firstnames, accounts)
        
        if self.doTiming and self.verbose:
            self.print_time(before)
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