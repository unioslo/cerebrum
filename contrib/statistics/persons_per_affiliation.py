import sys
import codecs

import Cerebrum.utils.csvutils as _csvutils
from Cerebrum.Errors import NotFoundError
from Cerebrum.modules.orgreg.constants import OrgregConstants
from Cerebrum.modules.no.Stedkode import OuCache
from Cerebrum.Utils import Factory

def generate_amounts_affiliations(db, affiliation_type):
    pe = Factory.get('Person')(db)
    ou = Factory.get('OU')(db)

    amount_dict = {}
    affiliations = pe.list_affiliations(affiliation=affiliation_type)

    for affiliation in affiliations:
        if amount_dict.get(affiliation['ou_id']) is None:
            amount_dict[affiliation['ou_id']] = 1
        else:
            amount_dict[affiliation['ou_id']] = amount_dict[affiliation[1]] + 1

    run = 1
    while run > 0:
        run = 0
        for place in list(amount_dict):
            ou.find(place)
	    try:
	        parent = ou.get_parent(OrgregConstants.perspective_orgreg)
            except NotFoundError:
                parent = None
            if parent is not None and parent != 677:
                run = 1
                if(amount_dict.get(parent) == None):
                    amount_dict[parent] = amount_dict.pop(place)
                else:
                    amount_dict[parent] = amount_dict[parent]+amount_dict.pop(place)
            ou.clear()
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
        'antall ansatt brukere': ansatte,
        'antall student brukere': studenter,
        'antall tilknyttet brukere': tilknyttede,
        })
    if len(student_dict) != 0:
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
            'antall ansatt brukere': ansatte,
            'antall student brukere': studenter,
            'antall tilknyttet brukere': tilknyttede,
            })
    if len(tilknyttet_dict) != 0:
        for place in list(tilknyttet_dict):
            ansatte = 0
            studenter = 0
            tilknyttede = tilknyttet_dict.pop(place)
            print_info.append({
            'ou_id': place,
            'seksjon': ou_cache.get_name(place),
            'antall ansatt brukere': ansatte,
            'antall student brukere': studenter,
            'antall tilknyttet brukere': tilknyttede,
            })

    return print_info

def main():
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    ansatt = generate_amounts_affiliations(db, co.affiliation_ansatt)
    student = generate_amounts_affiliations(db, co.affiliation_student)
    tilknyttet = generate_amounts_affiliations(db, co.affiliation_tilknyttet)
    print_info = combine_numbers(db, ansatt, student, tilknyttet)
    fields = ['ou_id', 'seksjon', 'antall ansatt brukere', 'antall student brukere', 'antall tilknyttet brukere']
    codec = codecs.lookup('utf-8')
    output_file = open('output.txt', 'w')
    output = codec.streamwriter(output_file)
    writer = _csvutils.UnicodeDictWriter(output, fields)
    writer.writeheader()
    writer.writerows(print_info)
    output_file.close()


if __name__ == '__main__':
    main()
