#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

import getopt
import pickle
import sys
import cerebrum_path
from Cerebrum import Errors
from Cerebrum.Utils import Factory, XMLHelper, SimilarSizeWriter
from Cerebrum.modules import CLHandler
from Cerebrum.modules.no.Stedkode import Stedkode
from Cerebrum.modules.no.uio.Ephorte import EphorteRole

progname = __file__.split("/")[-1]
__doc__ = """
This script populates ...

Usage: %s [options]
  -f fname : output filename

""" % progname

db = Factory.get('Database')()
db.cl_init(change_program="populate_ephorte")

co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)
pe = Factory.get('Person')(db)
group = Factory.get('Group')(db)
ephorte_role = EphorteRole(db)
ou = Stedkode(db)
cl = CLHandler.CLHandler(db)

logger = Factory.get_logger("cronjob")

class SimpleRole(object):
    def __init__(self, role_type, adm_enhet, arkivdel, journalenhet):
        self.role_type = role_type
        self.adm_enhet = adm_enhet
        self.arkivdel = arkivdel
        self.journalenhet = journalenhet

    def cmp(self, b):
        return (self.role_type == b.role_type and self.adm_enhet == b.adm_enhet and
                self.arkivdel == b.arkivdel and self.journalenhet == b.journalenhet)

    def __str__(self):
        return "role_type=%s, adm_enhet=%s, arkivdel=%s, journalenhet=%s" % (
            self.role_type, self.adm_enhet, self.arkivdel,
            self.journalenhet)

class PopulateEphorte(object):
    def __init__(self, ephorte_sko_file):
        # Pre-fetch some information about OUs in ePhorte and Cerebrum

        logger.info("Fetching OU info...")
        sko2ou_id = {}
        self.ouid_2roleinfo = {}
        self.ouid2sko = {}
        for row in ou.get_stedkoder():
            sko = "%02i%02i%02i" % tuple([
                int(row[x]) for x in ('fakultet', 'institutt', 'avdeling')])
            ou_id = int(row['ou_id'])
            self.ouid2sko[ou_id] = sko
            sko2ou_id[sko] = ou_id
            if sko.startswith("3905") or sko == "332520":
                self.ouid_2roleinfo[ou_id] = (
                    int(co.ephorte_arkivdel_sak_so), int(co.ephorte_journenhet_so))
            elif sko == '390920':
                self.ouid_2roleinfo[ou_id] = (
                    int(co.ephorte_arkivdel_sak_nikk), int(co.ephorte_journenhet_nikk))
            else:
                self.ouid_2roleinfo[ou_id] = (
                    int(co.ephorte_arkivdel_sak_uio), int(co.ephorte_journenhet_uio))

        self._superuser_role = SimpleRole(
            int(co.ephorte_role_sy), sko2ou_id["900199"], int(co.ephorte_arkivdel_sak_uio),
            int(co.ephorte_journenhet_uio))

        # ./run_import.sh -d admindel -t AdminDel -p eph-conn.props
        lines = file(ephorte_sko_file).readlines()
        tmp = lines.pop(0).split(';')
        posname2num = dict((tmp[n], n) for n in range(len(tmp)))
        self.known_ephorte_ou = []
        for line in lines:
            ephorte_sko = line.split(";")[posname2num['AI_FORKDN']]
            if ephorte_sko == 'UIO':
                pass  # TODO: skal vi gjøre noe med root-noden?
            ou_id = sko2ou_id.get(ephorte_sko)
            if ou_id is None:
                logger.info("Ukjent ePhorte sted: '%s'" % ephorte_sko)
                continue
            self.known_ephorte_ou.append(ou_id)
        #logger.debug("Known ephorte sko: %s" % ", ".join(
        #    [self.ouid2sko[x] for x in self.known_ephorte_ou]))
        
        self.ou_id2parent = {}
        for row in ou.get_structure_mappings(co.perspective_lt):
            i = row['parent_id'] and int(row['parent_id']) or None
            self.ou_id2parent[int(row['ou_id'])] = i

    def map_ou2role(self, ou_id):
        arkiv, journal = self.ouid_2roleinfo[ou_id]
        return SimpleRole(int(co.ephorte_role_sb), ou_id, arkiv, journal)
    
    def run(self):
        """Automatically add roles and spreads for employees according to
        rules in ephorte-sync-spec.rst """

        logger.info("Lising affiliations")
        person2ou = {}
        for row in pe.list_affiliations(source_system=co.system_sap,
                                        affiliation=co.affiliation_ansatt):
            ou_id = int(row['ou_id'])
            while ou_id is not None and ou_id not in self.known_ephorte_ou:
                #logger.debug("Try parent: %s -> %s" % (
                #    self.ouid2sko[ou_id], self.ouid2sko.get(self.ou_id2parent.get(ou_id))))
                ou_id = self.ou_id2parent.get(ou_id)
            if ou_id is None:
                # Her kunne vi valgt å plasere personen på root-noden
                # (900199), men det ønsker vi ikke(?)
                logger.info("Failed mapping '%s' to known ePhorte sko" % self.ouid2sko[int(row['ou_id'])])
                continue
            person2ou.setdefault(int(row['person_id']), {})[ou_id] = 1

        person2roles = {}
        for row in ephorte_role.list_roles():
            person2roles.setdefault(int(row['person_id']), []).append(
                SimpleRole(int(row['role_type']), int(row['adm_enhet']), row['arkivdel'], row['journalenhet']))

        has_ephorte_spread = {}
        for row in pe.list_all_with_spread(co.spread_ephorte_person):
            has_ephorte_spread[int(row['entity_id'])] = True

        # Ideally, the group should have persons as members, but bofh
        # doesn't have much support for that, so we map user->owner_id
        # instead
        superusers = []
        group.find_by_name("ephorte-admins")
        for account_id in group.get_members():
            ac.clear()
            ac.find(account_id)
            superusers.append(int(ac.owner_id))

        logger.info("Starting comparison...")
        # Done fetching data, start comparison
        for person_id, ous in person2ou.items():
            auto_roles = []
            existing_roles = person2roles.get(person_id, [])
            # logger.debug("Process pid=%i, ous=%s, old=%s" % (person_id, repr(ous), existing_roles))
            for t in ous:
                auto_roles.append(self.map_ou2role(t))
            if person_id in superusers:
                auto_roles.append(self._superuser_role)
            if not has_ephorte_spread.get(person_id):
                pe.clear()
                pe.find(person_id)
                pe.add_spread(co.spread_ephorte_person)

            n = 0
            for ar in auto_roles:
                idx = [n for n in range(len(existing_roles))
                       if ar.cmp(existing_roles[n])]
                if not idx:
                    logger.debug("Adding role (pid=%i): %s" % (person_id, ar))
                    ephorte_role.add_role(person_id, ar.role_type, ar.adm_enhet, ar.arkivdel, ar.journalenhet)
                else:
                    del existing_roles[idx[0]]
            for er in existing_roles:
                if er.role_type == int(co.ephorte_role_sb):
                    logger.debug("Removing role (pid=%i): %s" % (person_id, er))
                    ephorte_role.remove_role(person_id, er.role_type, er.adm_enhet, er.arkivdel, er.journalenhet)

        # Superuser group
        logger.info("All done")
        db.commit()

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'p', ['help'])
    except getopt.GetoptError:
        usage(1)

    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('-p',):
            pop = PopulateEphorte("/local2/home/runefro/usit/cerebrum/sf/cerebrum/java/ephorte/ephorte-steder.dat")
            pop.run()
    if not opts:
        usage(1)

def usage(exitcode=0):
    print __doc__
    sys.exit(exitcode)

if __name__ == '__main__':
    main()
