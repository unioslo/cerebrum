#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

import cerebrum_path
import cereconf

import re
import pickle
import sys
import getopt

import xml.sax

from Cerebrum import Errors
from Cerebrum.Utils import Factory

OU_class = Factory.get('OU')
db = Factory.get('Database')()
db.cl_init(change_program='import_OU')
co = Factory.get('Constants')(db)


# <data>
#   <sted fakultetnr="ff" instituttnr="ii" gruppenr="gg"
#         forkstednavn="foo" stednavn="foo bar" akronym="fb"
#         stedkortnavn_bokmal="fooen" stedkortnavn_nynorsk="fooa"
#         stedkortnavn_engelsk="thefoo"
#         stedlangnavn_bokmal="foo baren" stedlangnavn_nynorsk="foo bara"
#         stedlangnavn_engelsk="the foo bar"
#         fakultetnr_for_org_sted="FF" instituttnr_for_org_sted="II"
#         gruppenr_for_org_sted="GG"
#         opprettetmerke_for_oppf_i_kat="X"
#         telefonnr="22851234" innvalgnr="228" linjenr="51234"
#         stedpostboks="1023"
#         adrtypekode_besok_adr="INT" adresselinje1_besok_adr="adr1_besok"
#         adresselinje2_besok_adr="adr2_besok"
#         poststednr_besok_adr="postnr_besok"
#         poststednavn_besok_adr="postnavn_besok" landnavn_besok_adr="ITALIA"
#         adrtypekode_intern_adr="INT" adresselinje1_intern_adr="adr1_int"
#         adresselinje2_intern_adr="adr2_int"
#         poststednr_intern_adr="postnr_int"
#         poststednavn_intern_adr="postnavn_int" landnavn_intern_adr="ITALIA"
#         adrtypekode_alternativ_adr="INT"
#         adresselinje1_alternativ_adr="adr1_alt"
#         adresselinje2_alternativ_adr="adr2_alt"
#         poststednr_alternativ_adr="postnr_alt"
#         poststednavn_alternativ_adr="postnavn_alt"
#         landnavn_alternativ_adr="ITALIA">
#     <komm kommtypekode=("EKSTRA TLF" | "FAX" | "FAXUTLAND" | "JOBBTLFUTL" |
#                         "EPOST")
#           telefonnr="foo" kommnrverdi="bar">
#     </komm>
#   </sted>
# </data>

class OUData(xml.sax.ContentHandler):
    def __init__(self, filename):
        self.tp = TrivialParser()
        xml.sax.parse(filename, self.tp)

    def __iter__(self):
        return self

    def next(self):
        try:
            return self.tp.org_units.pop(0)
        except IndexError:
            raise StopIteration, "End of file"

class TrivialParser(xml.sax.ContentHandler):
    def __init__(self):
        self.org_units = []

    def startElement(self, name, attrs):
        tmp = {}
        for k in attrs.keys():
            tmp[k.encode('iso8859-1')] = attrs[k].encode('iso8859-1')
        if name == 'data':
            pass
        elif name == "sted":
            self.org_units.append(tmp)
        elif name == "komm":
            self.org_units[-1].setdefault("komm", []).append(tmp)
        else:
            raise ValueError, "Unknown XML element %s" % name

    def endElement(self, name):
        pass

def get_stedkode_str(row, suffix=""):
    elems = []
    for key in ('fakultetnr', 'instituttnr', 'gruppenr'):
        elems.append("%02d" % int(row[key+suffix]))
    return "-".join(elems)

def rec_make_ou(stedkode, ou, existing_ou_mappings, org_units,
                stedkode2ou, co):
    """Recursively create the ou_id -> parent_id mapping"""
    ou_data = org_units[stedkode]
    org_stedkode = get_stedkode_str(ou_data, suffix='_for_org_sted')
    if not stedkode2ou.has_key(org_stedkode):
        print "Error in dataset:"\
              " %s references missing STEDKODE: %s, using None" % (
            stedkode, org_stedkode)
        org_stedkode = None
        org_stedkode_ou = None
    elif stedkode == org_stedkode:
        print "Warning: %s has self as parent, using None" % stedkode
        org_stedkode = None
        org_stedkode_ou = None
    else:
        org_stedkode_ou = stedkode2ou[org_stedkode]

    if existing_ou_mappings.has_key(stedkode2ou[stedkode]):
        if existing_ou_mappings[stedkode2ou[stedkode]] != org_stedkode_ou:
            # TODO: Update ou_structure
            print "Mapping for %s changed (%s != %s)" % (
                stedkode, existing_ou_mappings[stedkode2ou[stedkode]],
                org_stedkode_ou)
        return

    if (org_stedkode_ou is not None
        and (stedkode != org_stedkode)
        and (not existing_ou_mappings.has_key(org_stedkode_ou))):
        rec_make_ou(org_stedkode, ou, existing_ou_mappings, org_units,
                          stedkode2ou, co)

    ou.clear()
    ou.find(stedkode2ou[stedkode])
    if stedkode2ou.has_key(org_stedkode):
        ou.set_parent(perspective, stedkode2ou[org_stedkode])
    else:
        ou.set_parent(perspective, None)
    existing_ou_mappings[stedkode2ou[stedkode]] = org_stedkode_ou

def import_org_units(oufile):
    org_units = {}
    ou = OU_class(db)
    i = 1
    stedkode2ou = {}
    for k in OUData(oufile):
        i += 1
        org_units[get_stedkode_str(k)] = k
        if verbose:
            print "Processing %s '%s'" % (get_stedkode_str(k),
                                          k['forkstednavn']),
        ou.clear()
        try:
            ou.find_stedkode(k['fakultetnr'], k['instituttnr'], k['gruppenr'],
                             institusjon=k.get('institusjonsnr',
                                               cereconf.DEFAULT_INSTITUSJONSNR))
        except Errors.NotFoundError:
            pass
        kat_merke = 'F'
        if k.get('opprettetmerke_for_oppf_i_kat'):
            kat_merke = 'T'
        ou.populate(k['stednavn'], k['fakultetnr'],
                    k['instituttnr'], k['gruppenr'],
                    institusjon=k.get('institusjonsnr',
                                      cereconf.DEFAULT_INSTITUSJONSNR),
                    katalog_merke=kat_merke,
                    acronym=k.get('akronym', None),
                    short_name=k['forkstednavn'],
                    display_name=k['stednavn'],
                    sort_name=k['stednavn'])
        if k.has_key('adresselinje1_intern_adr'):
            p_o_box = k.get('stedpostboks', None)
            if p_o_box == '0':
                p_o_box = None
            adrlines = filter(None, (k.get('adresselinje1_intern_adr', None),
                                     k.get('adresselinje2_intern_adr', None) ))
            postal_number = k.get('poststednr_intern_adr', '')
            if postal_number:
                postal_number = "%04i" % int(postal_number)
            ou.populate_address(source_system, co.address_post,
                                address_text = "\n".join(adrlines),
                                p_o_box = p_o_box,
                                postal_number = postal_number,
                                city = k.get('poststednavn_intern_adr', ''))
        if k.has_key('adresselinje1_besok_adr'):
            adrlines = filter(None, (k.get('adresselinje1_besok_adr', None),
                                     k.get('adresselinje2_besok_adr', None) ))
            postal_number = k.get('poststednr_besok_adr', None)
            if postal_number:
                postal_number = "%04i" % int(postal_number)
            ou.populate_address(source_system, co.address_street,
                                address_text = "\n".join(adrlines),
                                postal_number = postal_number,
                                city = k.get('poststednavn_besok_adr', None))
        n = 0
        for t in k.get('komm', []):
            n += 1       # TODO: set contact_pref properly
            nrtypes = {'EKSTRA TLF': co.contact_phone,
                       'FAX': co.contact_fax,
                       'FAXUTLAND': co.contact_fax,
                       'JOBBTLFUTL': co.contact_phone}
            if nrtypes.has_key(t['kommtypekode']):
                nr = t.get('telefonnr', t.get('kommnrverdi', None))
                if nr is None:
                    print "Warning: unknown contact: %s" % str(t)
                    continue
                ou.populate_contact_info(source_system, nrtypes[t['kommtypekode']],
                                         nr, contact_pref=n)
            elif t['kommtypekode'] == 'EPOST':
                ou.populate_contact_info(source_system, co.contact_email,
                                         t['kommnrverdi'], contact_pref=n)
	n += 1
	if k.has_key('innvalgnr') and k.has_key('linjenr'):
	    phone_value = "%s%05i" % (k['innvalgnr'], int(k['linjenr']))
            ou.populate_contact_info(source_system, co.contact_phone,
					phone_value, contact_pref=n)
        op = ou.write_db()
        if verbose:
            if op is None:
                print "**** EQUAL ****"
            elif op:
                print "**** NEW ****"
            else:
                print "**** UPDATE ****"

        stedkode = get_stedkode_str(k)
        # Not sure why this casting to int is required for PostgreSQL
        stedkode2ou[stedkode] = int(ou.entity_id)
        db.commit()

    existing_ou_mappings = {}
    for node in ou.get_structure_mappings(perspective):
        existing_ou_mappings[int(node.ou_id)] = node.parent_id

    # Now populate ou_structure
    if verbose:
        print "Populate ou_structure"
    for stedkode in org_units.keys():
        rec_make_ou(stedkode, ou, existing_ou_mappings, org_units,
                    stedkode2ou, co)
    db.commit()

def usage(exitcode=0):
    print """Usage: [options]
    -v | --verbose: increase verbosity
    -o | --ou-file file: file to read stedinfo from
    --source-system name: name of source-system to use
    --perspective name: name of perspective to use

    Imports OU data from systems that use 'stedkoder', primarily used
    to import from UoOs LT system"""
    sys.exit(exitcode)
    
def main():
    global source_system, verbose, perspective
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'vo:p:',
                                   ['verbose', 'ou-file=', 'source-system=',
                                    'perspective='])
    except getopt.GetoptError:
        usage(1)
    verbose = 0
    oufile = None
    source_system = None
    for opt, val in opts:
        if opt in ('-v', '--verbose'):
            verbose += 1
        elif opt in ('-o', '--ou-file'):
            oufile = val
        elif opt in ('--source-system',):
            source_system = getattr(co, val)
        elif opt in ('--perspective',):
            perspective = getattr(co, val)
    if not (source_system is None
            or perspective is None
            or oufile is None):
        import_org_units(oufile)
    else:
        usage(2)

if __name__ == '__main__':
    main()
