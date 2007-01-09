#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2002, 2003, 2004 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

import cerebrum_path
import cereconf

import re
import pickle
import sys
import getopt
import time
import string

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.xmlutils.system2parser import system2parser
from Cerebrum.modules.xmlutils.object2cerebrum import XML2Cerebrum
from Cerebrum.modules.xmlutils.xml2object import SkippingIterator


OU_class = Factory.get('OU')
db = Factory.get('Database')()
db.cl_init(change_program='import_OU')
co = Factory.get('Constants')(db)
logger = Factory.get_logger("cronjob")
# TBD: Do we *ever* need to supply the perspective explicitely, even if we
# always supply source_system?
source2perspective = {co.system_lt: co.perspective_lt,
                      co.system_sap: co.perspective_sap,
                      co.system_fs: co.perspective_fs,}





def format_sko(xmlou):
    sko = xmlou.get_id(xmlou.NO_SKO)
    if sko is None:
        return None
    # fi
    
    # Yes, we will fail if there is no sko
    return "%02d%02d%02d" % sko
# end format_sko


def format_parent_sko(xmlou):

    parent = xmlou.parent
    if parent:
        assert parent[0] == xmlou.NO_SKO
        return "%02d%02d%02d" % parent[1]
    else:
        return None
    # fi
# end format_parent_sko



def rec_make_ou(my_sko, ou, existing_ou_mappings, org_units,
                stedkode2ou, perspective):
    """Recursively create the ou_id -> parent_id mapping.

    Arguments:

    my_sko	stedkode for the OU from which we want to start constructing
                the OU-subtree.
    ou		Instance of Factory.get('OU').
    existing_ou_mappings	ou_id -> parent_ou_id mapping, representing
                                parent information in Cerebrum.
    org_units	sko -> XML-object mapping (for each 'OU' element in the file)
    stedkode2ou	sko -> ou_id mapping (for each 'OU' element in the file).
    """
    
    # This may happen *if* there is an error in the datafile, when OU1 has
    # OU2 as parent, but there are no records of OU2 on file. It could happen
    # when *parts* of the OU-hierarchy expire.
    if my_sko not in org_units:
        logger.warn("Error in dataset: trying to construct "
                    "OU-hierarchy from sko %s, but it does not "
                    "exist in the datafile", my_sko)
        return

    xmlou = org_units[my_sko]
    parent_sko = format_parent_sko(xmlou)

    if (not parent_sko) or (parent_sko not in stedkode2ou):
        logger.warn("Error in dataset:"
                    " %s references missing STEDKODE: %s, using None" %
                    (my_sko, parent_sko))
        parent_sko = None
        parent_ouid = None
    elif my_sko == parent_sko:
        logger.debug("%s has self as parent, using None" % my_sko)
        parent_sko = None
        parent_ouid = None
    else:
        parent_ouid = stedkode2ou[parent_sko]
    # fi

    my_ouid = stedkode2ou[my_sko]

    # if my_ouid ID already has a parent in Cerebrum, we may need to change the
    # info in Cerebrum...
    if my_ouid in existing_ou_mappings:
        logger.debug("Parent exists: in cerebrum ou_id=%s; on file ou_id=%s" %
                     (existing_ou_mappings[my_ouid], parent_ouid))
        # if parent info in Cerebrum is different from parent info on file,
        # change the info in Cerebrum ...
        if existing_ou_mappings[my_ouid] != parent_ouid:
            logger.debug("Parent for OU %s changed (from %s to %s)" %
                         (my_sko, existing_ou_mappings[my_ouid], parent_ouid))
            # Assert that parents are properly placed before placing ourselves
            rec_make_ou(parent_sko, ou, existing_ou_mappings, org_units,
                        stedkode2ou, perspective)

        # ... however, when parent info in cerebrum equals that on file, there
        # is nothing more to be done for *this* ou (my_sko)
        else:
            return

    # ... else if my_ouid does not exist in Cerebrum, we may still want to
    # updates its parents...
    elif (parent_ouid is not None
          and (my_sko != parent_sko)
          and (not existing_ou_mappings.has_key(parent_ouid))):
        rec_make_ou(parent_sko, ou, existing_ou_mappings, org_units,
                    stedkode2ou, perspective)
    # fi

    logger.debug("Placing %s under %s" % (my_sko, parent_sko))
    ou.clear()
    ou.find(my_ouid)
    ou.set_parent(perspective, parent_ouid)
    existing_ou_mappings[my_ouid] = parent_ouid
# end rec_make_ou



def import_org_units(sources, cer_ou_tab):
    """Scan the sources and import all the OUs into Cerebrum.

    Each entry in sources is a pair (system_name, filename).

    cer_ou_tab contains the OU list present in Cerebrum at the start of this
    script.
    """

    ou = OU_class(db)
    # These are used to help build OU structure information
    stedkode2ou = dict()
    org_units = dict()
    existing_ou_mappings = dict()

    for system, filename in sources:
        logger.debug("Processing %s data from %s", system, filename)
        source_system = getattr(co, system)
        db_writer = XML2Cerebrum(db, source_system, def_kat_merke)
        perspective = source2perspective[source_system]

        # iter_ou provides an iterator over objects inheriting from
        # xml2object.DataOU
        it = system2parser(system)(filename, False).iter_ou()
        for xmlou in SkippingIterator(it, logger):
            formatted_sko = format_sko(xmlou)
            if not formatted_sko:
                logger.error("Missing sko for OU %s (names: %s). Skipped!" %
                             (list(xmlou.iterids()), list(xmlou.iternames())))
                continue
            
            org_units[formatted_sko] = xmlou
            if verbose:
                logger.debug("Processing %s '%s'" %
                             (formatted_sko,
                              xmlou.get_name_with_lang(xmlou.NAME_SHORT,
                                                       "no", "en")))

            args = (xmlou, None)
            if clean_obsolete_ous:
                args = (xmlou, cer_ou_tab)
            
            status, ou_id = db_writer.store_ou(*args)

            if verbose:
                logger.debug("**** %s ****", status)

            # Not sure why this casting to int is required for PostgreSQL
            stedkode2ou[formatted_sko] = int(ou_id)
            db.commit()
        # od

        # Build and register parent information
        for node in ou.get_structure_mappings(perspective):
            existing_ou_mappings[int(node.fields.ou_id)] = node.fields.parent_id
        # od

        # Now populate ou_structure
        logger.info("Populate ou_structure")
        for stedkode in org_units.keys():
            rec_make_ou(stedkode, ou, existing_ou_mappings, org_units,
                        stedkode2ou, perspective)
        # od
        db.commit()
    # od
# end import_org_units



def get_cere_ou_table():
    """Collect sko available in Cerebrum now.

    This information is used to detect stale entries in Cerebrum.
    """
    
    stedkode = OU_class(db)
    sted_tab = {}
    for entry in stedkode.get_stedkoder():
	value = "%02d%02d%02d" % (entry['fakultet'], entry['institutt'],
                                  entry['avdeling'])
	key = int(entry['ou_id'])
	sted_tab[key] = value
    # od
    
    return sted_tab
# end get_cere_ou_table



def set_quaran(cer_ou_tab):
    """Set quarantine on OUs that are no longer in the data source.
    
    All the OUs that were in Cerebrum before an import is run are compared
    with the data files. Those OUs that are no longer present in the data
    source are marked as invalid.

    FIXME: How does it work with multiple data sources?
    """
    
    ous = OU_class(db)
    now = db.DateFromTicks(time.time())
    acc = Factory.get("Account")(db)
    acc.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    for k in cer_ou_tab.keys():
	ous.clear()
	ous.find(k)
	if (ous.get_entity_quarantine(type=co.quarantine_ou_notvalid) == []):
		ous.add_entity_quarantine(co.quarantine_ou_notvalid,
                                          acc.entity_id,
                                          description='import_OU',
                                          start = now) 
    db.commit()
# end set_quaran



def dump_perspective(sources):
    """Displays the OU hierarchy in a fairly readable way.

    For information about sources, see import_org_units.
    """

    logger.info("OU tree for %s", sources)
    
    class Node(object):
        def __init__(self, name, parent):
            self.name = name
            self.parent = parent
            self.children = []
        # end __init__
    # end class


    ou = Factory.get("OU")(db)
    person = Factory.get("Person")(db)
    def make_prefix(key, level):
        """Make a pretty prefix for each output line."""

        xmlou = org_units.get(key)
        if xmlou is not None and getattr(xmlou, "publishable", False):
            katalogmerke = 'T'
        else:
            katalogmerke = ' '
        # fi

        # And now we find out if there are people with affiliations to this
        # place
        people_mark = " "
        if key is not None and xmlou is not None:
            try:
                fakultet, institutt, avdeling = xmlou.get_id(xmlou.NO_SKO)
                ou.clear()
                ou.find_stedkode(int(fakultet), int(institutt), int(avdeling),
                                 cereconf.DEFAULT_INSTITUSJONSNR)
                if person.list_affiliations(ou_id = ou.entity_id):
                    people_mark = "*"
                # fi
            except Errors.NotFoundError:
                pass
            # yrt
        # fi
            
        return "%s%s %s" % (katalogmerke, people_mark, level)
    # end make_prefix
    

    def dump_part(parent, level):
        """dump part of the OU tree rooted at parent."""
        lang_pri = ("no", "en")
        xmlou = org_units.get(parent)
        if xmlou:
            name = xmlou.get_name_with_lang(xmlou.NAME_LONG, *lang_pri)
            values = { "akronym" : xmlou.get_name_with_lang(xmlou.NAME_ACRONYM,
                                                          *lang_pri) or "N/A",
                       "stednavn" : name or "N/A" }
        else:
            values = { "akronym" : "N/A",
                       "stednavn" : "N/A", }
        # fi

        print "%s%s %s %s (%s)" % (make_prefix(parent, level),
                                   " " * (level * 4),
                                   str(parent),
                                   values["akronym"], values["stednavn"])
        children = list()
        for t in tree_info.keys():
            if tree_info[t].parent == parent:
                if t == parent:
                    print "WARNING: circular for %s" % t
                else:
                    children.append(t)
                # fi
            # fi
        # od

        children.sort()
        for t in children:
            dump_part(t, level + 1)
        # od
    # end dump_part

    
    for system, filename in sources:
        source_system = getattr(co, system)
        perspective = source2perspective[source_system]

        # These are used to help build OU structure information
        tree_info = dict()
        org_units = dict()

        # Slurp in data
        it = system2parser(system)(filename, False).iter_ou()
        for xmlou in SkippingIterator(it, logger):
            sko = format_sko(xmlou)
            if sko is None:
                print ("Missing sko for OU %s (names: %s). Skipped!" %
                           (list(xmlou.iterids()), list(xmlou.iternames())))
                continue
            # fi
            org_units[sko] = xmlou
        # od
            
        # Fill tree_info with parent/child relationships
        for k in org_units.keys():
            parent_sko = format_parent_sko(org_units[k])
            if parent_sko is None:
                print "%s has no parent" % k
            # fi

            if parent_sko not in tree_info:
                if parent_sko not in org_units or parent_sko is None:
                    parent2x = None
                else:
                    parent2x = format_parent_sko(org_units[parent_sko])
                # fi

                tree_info[parent_sko] = Node(parent_sko, parent2x)
            # fi

            tree_info[k] = Node(k, parent_sko)
            tree_info[parent_sko].children.append(k)
        # od

        # Display structure
        # dump_part(None, 0)
        top_keys = tree_info.keys(); top_keys.sort()
        for t in top_keys:
            if tree_info[t].parent == tree_info[t].name:
                dump_part(t, 0)
            # fi
        # od
    # od
# end dump_perspective



def usage(exitcode=0):
    print """Usage: [options] [file ...]
Imports OU data from systems that use 'stedkoder', primarily used to
import from UoOs LT system.

    -v | --verbose              increase verbosity
    -c | --clean		quarantine invalid OUs
    -s | --source-spec SPEC     colon-separated (source-system, filename) pair
    -l | --ldap-visibility
    --dump-perspective          view the hierarchy of the ou-file
    """
    sys.exit(exitcode)

def main():
    global verbose, clean_obsolete_ous, def_kat_merke

    opts, args = getopt.getopt(sys.argv[1:], 'vcs:l',
                               ['verbose',
                                'clean',
                                'source-spec=',
                                'dump-perspective',
                                'ldap-visibility',])
    

    verbose = 0
    sources = []
    clean_obsolete_ous = False
    def_kat_merke = False
    cer_ou_tab = dict()
    for opt, val in opts:
        if opt in ('-v', '--verbose'):
            verbose += 1
	elif opt in ('-c','--clean'):
	    clean_obsolete_ous = True
        elif opt in ('-s', '--source-spec'):
            sysname, filename = val.split(":")
            sources.append((sysname, filename))
	elif opt in ('-l', '--ldap-visibility',):
	    def_kat_merke = True
        elif opt in ('--dump-perspective',):
            dump_perspective(sources)
            sys.exit(0)
    if clean_obsolete_ous:
	cer_ou_tab = get_cere_ou_table()
        logger.debug("Collected %d ou_id->sko mappings from Cerebrum",
                     len(cer_ou_tab))
    if sources:
        import_org_units(sources, cer_ou_tab)
    else:
        usage(4)
    set_quaran(cer_ou_tab)

if __name__ == '__main__':
    main()

# arch-tag: 859f1333-238e-43e6-89ee-d9ce39b11e6f
