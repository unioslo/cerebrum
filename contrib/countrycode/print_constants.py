#!/usr/bin/env python
# -*- coding: utf-8 -*-

import csv

#CSV column indexes:
#   1: Phone prefix
#   2: Entity name (English)
#   7: ISO3166-1-Alpha-2 (two-letter country code)


def main():
	comprehensive = 'country-codes-comprehensive.csv'
	norwegian = 'iso3166-nb.txt'

	read_country_files(comprehensive, norwegian)

def read_country_files(comprehensive, norwegian):
    countries = get_comprehensive_country_data(comprehensive)
    no = get_norwegian_country_names(norwegian)

    for c in countries:
        code_str = c[7]
        country = c[2]
        # skip long phone prefixes, db column is CHAR VARYING(8)
        phone_prefix = c[1] if len(c[1]) < 8 else ""
        description = no.get(code_str, None)
        
        if description is not None:
            description = description.decode('iso-8859-1').encode('utf-8')
        else:
            print 'Missing translation for ' + code_str

        print "country_%s = _CountryCode(\"%s\", \"%s\", \"%s\", \"%s\")" % (
            code_str.lower(), code_str, country, phone_prefix, description)

def get_norwegian_country_names(fname):
    countries = {}
    f = file(fname, "r")
    for line in f.readlines():
        if line[0] == '#':
            continue
        if not line.strip():
            continue
        dta = [x.strip() for x in line.split("\t")]
        countries.setdefault(dta[0], dta[1])
    return countries

def get_comprehensive_country_data(fname):
    reader = csv.reader(open(fname, "rb"))
    reader.next()
    return [line for line in reader]

if __name__ == '__main__':
    main()
