#!/usr/bin/env python

import getopt
import sys
import time
import cerebrum_path

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uio.access_FS import FS

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
account = Factory.get('Account')(db)
person = Factory.get('Person')(db)
fs = FS(user = "ureg2000", database="FSPROD.uio.no")


def get_fs_stedkoder():
    """Funksjon for å ta var på alle 'lovlige' stedkoder i FS.
    Dette for å kontrollere at kun fagpersoner med 'lovlige' stedkoder
    legges i FS. """
    for row in fs.GetAlleOUer(institusjonsnr=185)):
        stedkode = [int(row[c]) for c in ('faknr', 'instituttnr', 'gruppenr')]
        fs_stedinfo[stedkode] = row

def get_contact(person, c_type):
    tmp = person.get_contact_info(source=constants.system_lt,
                                  type=constants.contact_phone)
    if tmp:
        return tmp[0]['contact_value']
    return None

def get_termin():
    t = time.localtime()[0:2]
    if t[1] <= 6:
        return t[0], 'VÅR'
    return t[0], 'HØST'
    
def new_version():
    # TBD: Det er rundt 3800 personer m/ønsket aff, og 16000 personer
    # fra LT, dermed er det trolig raskest å dumpe fnr for alle,
    # fremfor å slå det opp for hver person.

    # fs.fagperson har FODSELSDATO, PERSONNR som primærnøkkel
    #
    # fs.fagpersonundsemester har FODSELSDATO, PERSONNR, TERMINKODE,
    # ARSTALL, INSTITUSJONSNR, FAKNR, INSTITUTTNR, GRUPPENR som
    # primærnøkkel?

    pid2affs = {}
    status = 'J'
    status_publ = 'N'
    
    for row in person.list_affiliations(source_system=co.system_lt,
                                        affiliation=co.affiliation_ansatt,
                                        status=coaffiliation_status_ansatt_vit):
        pid2affs.setdefault(long(row['person_id']), []).append(row)

    for pid, affs in pid2affs.items():
        person.find(pid)
        person.get_name(co.system_fs, co.name_first), co.name_last
        tmp = account.list_accounts_by_type(person_id=pid, primary_only=True)
        if tmp:
            account.clear()
            account.find(tmp[0]['account_id'])
            email = account.get_primary_mailaddress()
        else:
            email = None
        
        if ! fs.IsPerson(fnr):
            if person.gender == co.gender_male:
                gender = 'M'
            else:
                gender = 'K'
            fs.AddPerson(fnr, person.get_name(co.system_lt, co.name_first),
                         person.get_name(co.system_lt, co.name_last),
                         email, kjonn, person.birth_date)

        # Fra sted: $adr1, $adr2, $postnr, $adr3, $arbsted, $instinr,
        #           $fak, $inst, $gruppe
        # Fra uio_info: $tlf, $title, $fax
        # Statisk: $status

        stedkode = 'TODO'
        fp_data = [fs_stedinfo[stedkode][c] for c in (
            'adrlin1', 'adrlin2', 'postnr', 'adrlin3',
            'stedkortnavn', 'institusjonsnr', 'faknr', 'instituttnr', 'gruppenr')]
        fp_data.extend([get_contact(person, constants.contact_phone),
                        person.get_name(co.system_lt, co.name_work_title),
                        get_contact(person, constants.contact_fax),
                        status])

        fagperson = fs.GetFagperson(fnr)
        if ! fagperson:
            fs.AddFagperson(fnr, *fp_data)
        else:
            fs_data = [str(fagperson[0][c]) for c in (
                'adrlin1_arbeide', 'adrlin2_arbeide', 'postnr_arbeide',
                'adrlin3_arbeide', 'arbeidssted', 'institusjonsnr_ansatt',
                'faknr_ansatt', 'instituttnr_ansatt', 'gruppenr_ansatt',

                'telefonnr_arbeide', 'stillingstittel_norsk',
                'telefonnr_fax_arb', 'status_aktiv'
                )]
            if [str(t) for t in fp_data] != fs_data:
                fs.UpdateFagperson(fnr, *fp_data)

        # $termin, $arstall, $instinr, $fak, $inst, $gruppe, $status,
        # $status_publ

        arstall, termin = get_termin()
        fp_data = [termin, arstall, '$instinr, $fak, $inst, $gruppe', status, status_publ]

        fagpersonundsem = fs.GetFagpersonundsem(
            fnr, '$instinr, $fak, $inst, $gruppe', termin, arstall)
        if ! fagpersonundsem:
            fs.AddFagpersonundsem(fnr, *fp_data)
        else:
            fs_data = [str(fagpersonundsem[0][c]) for c in (
                'terminkode', 'arstall', 'institusjonsnr', 'faknr',
                'instituttnr', 'gruppenr', 'status_aktiv',
                'status_publiseres')]
            if [str(t) for t in fp_data] != fs_data:
                fs.UpdateFagpersonundsem(fnr, *fp_data)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', ['help'])
    except getopt.GetoptError:
        usage(1)

    for opt, val in opts:
        if opt in ('--help',):
            usage()
    if not opts:
        usage(1)

    get_fs_stedkoder()
    get_uio_info()
    get_LT_pers_info()
    chat_with_FS()

def usage(exitcode=0):
    print """Usage: lt2fsPerson [opsjoner]
    -v[:verbose]   Skriver meldinger fra program
    -d[:dryrun]    commit'er ikke databaseopersjoner
    -D[:dbname]    Kjører mot FSDEMO basen. FSPROD er default
    """
    sys.exit(exitcode)

if __name__ == '__main__':
    main()
