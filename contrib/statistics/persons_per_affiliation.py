import sys

import Cerebrum.utils.csvutils as _csvutils
from Cerebrum.Errors import NotFoundError
from Cerebrum.modules.orgreg.constants import OrgregConstants
from Cerebrum.modules.no.Stedkode import OuCache
from Cerebrum.Utils import Factory

def generate_amounts_affiliations(db):
    pe = Factory.get('Person')(db)
    ou = Factory.get('OU')(db)
    ou_cache = OuCache(db)

    amount_dict = {}
    affiliations = pe.list_affiliations()

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
    print_info = []
    for place in amount_dict:
        print_info.append({
        'ou_id': place,
        'seksjon': ou_cache.get_name(place),
        'antall brukere': amount_dict[place],
        })

    fields = ['ou_id', 'seksjon', 'antall brukere']
    writer = _csvutils.UnicodeDictWriter(sys.stdout, fields)
    writer.writeheader()
    writer.writerows(print_info)

def main():
    db = Factory.get('Database')()
    generate_amounts_affiliations(db)

if __name__ == '__main__':
    main()
