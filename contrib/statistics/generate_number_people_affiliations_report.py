import argparse
import codecs

import Cerebrum.utils.csvutils as _csvutils
from Cerebrum.Errors import NotFoundError
from Cerebrum.modules.orgreg.constants import OrgregConstants
from Cerebrum.modules.no.Stedkode import OuCache
from Cerebrum.Utils import Factory

def generate_amounts_affiliations(db, affiliation_type):
    pe = Factory.get('Person')(db)
    ou = Factory.get('OU')(db)
    co = Factory.get('Constants')(db)
    amount_dict = {}
    affiliations = pe.list_affiliations(affiliation=affiliation_type)
    if affiliation_type == co.affiliation_tilknyttet:
         affiliations.extend(pe.list_affiliations(affiliation = co.affiliation_manuell))
    for affiliation in affiliations:
        try:
            pe.find(affiliation['person_id'])
            if len(pe.get_accounts()) > 0:
                if amount_dict.get(affiliation['ou_id']) is None:
                    amount_dict[affiliation['ou_id']] = [affiliation['person_id']]
                else:
                    amount_dict[affiliation['ou_id']].append(affiliation['person_id'])
            pe.clear()
        except:
            pass
    return condense_dict(amount_dict, ou, co)

def condense_dict(dict, ou, co):
    amount_dict = dict
    run = True
    while run:
        run = False
        for place in list(amount_dict):
            valid = True
            ou.find(place)
            quarantines = ou.get_entity_quarantine()
            for quarantine in quarantines:
                if quarantine[0] == co.quarantine_ou_notvalid:
                    amount_dict.pop(place)
                    valid = False
            if valid:
                try:
                    parent = ou.get_parent(OrgregConstants.perspective_orgreg)
                except NotFoundError:
                    parent = None
                if parent is not None and parent != 677:
                    run = True
                    if amount_dict.get(parent) is None:
                        amount_dict[parent] = amount_dict.pop(place)
                    else:
                        amount_dict[parent].extend(amount_dict.pop(place))
            ou.clear()
    for place in list(amount_dict):
        amount_dict[place] = len(set(amount_dict[place]))
    return amount_dict

def combine_numbers(db, ansatt_dict, student_dict, tilknyttet_dict):
    ou_cache = OuCache(db)

    print_info = []
    for place in list(ansatt_dict):
        ansatte = ansatt_dict.pop(place)
        try:
            studenter = student_dict.pop(place)
        except KeyError:
            studenter = 0
        try:
            tilknyttede = tilknyttet_dict.pop(place)
        except KeyError:
            tilknyttede = 0
        print_info.append({
        'ou_id': place,
        'seksjon': ou_cache.get_name(place),
        'antall ansattbrukere': ansatte,
        'antall studentbrukere': studenter,
        'antall tilknyttetbrukere': tilknyttede,
        })
    for place in list(student_dict):
        ansatte = 0
        studenter = student_dict.pop(place)
        try:
            tilknyttede = tilknyttet_dict.pop(place)
        except KeyError:
            tilknyttede = 0
        print_info.append({
        'ou_id': place,
        'seksjon': ou_cache.get_name(place),
        'antall ansattbrukere': ansatte,
        'antall studentbrukere': studenter,
        'antall tilknyttetbrukere': tilknyttede,
        })
    for place in list(tilknyttet_dict):
        ansatte = 0
        studenter = 0
        tilknyttede = tilknyttet_dict.pop(place)
        print_info.append({
        'ou_id': place,
        'seksjon': ou_cache.get_name(place),
        'antall ansattbrukere': ansatte,
        'antall studentbrukere': studenter,
        'antall tilknyttetbrukere': tilknyttede,
        })

    return print_info

def main():
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    parser = argparse.ArgumentParser()
    parser.add_argument('filename', type = str, help = 'Filename for output-file')
    args = parser.parse_args()
    ansatt = generate_amounts_affiliations(db, co.affiliation_ansatt)
    student = generate_amounts_affiliations(db, co.affiliation_student)
    tilknyttet = generate_amounts_affiliations(db, co.affiliation_tilknyttet)
    print_info = combine_numbers(db, ansatt, student, tilknyttet)
    fields = ['ou_id', 'seksjon', 'antall ansattbrukere',
              'antall studentbrukere', 'antall tilknyttetbrukere']
    codec = codecs.lookup('utf-8')
    output_file = open(args.filename, 'w')
    output = codec.streamwriter(output_file)
    writer = _csvutils.UnicodeDictWriter(output, fields)
    writer.writeheader()
    writer.writerows(print_info)
    output_file.close()


if __name__ == '__main__':
    main()
