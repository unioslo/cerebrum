#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

import cereconf
import sys
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.ntnu import util
from Cerebrum.Utils import read_password
import getopt
import cx_Oracle
import logging
import time
import os

# Set the client encoding for the Oracle client libraries
os.environ['NLS_LANG'] = cereconf.BDB_ENCODING
cnt_missing_nin = 0

class BDB:
    def __init__(self):
        dsn = cx_Oracle.makedsn(cereconf.BDB_HOST, cereconf.BDB_PORT,
                                cereconf.BDB_SID)
        try:
            self.db = cx_Oracle.connect(dsn=dsn, user=cereconf.BDB_USER,
                password = read_password(cereconf.BDB_USER, "BDB"))
        except Exception,e:
            print "Error connecting to remote Oracle RDBMS. Reason: %s" % str(e)
            sys.exit()

    def get_spreads(self):
        cursor = self.db.cursor()
        cursor.execute("select id,domene,navn,skall,client_version, \
                        beskrivelse from bdb.system \
                        where operational=1 and user_domain=1")
        spreads = []
        bdb_spreads = cursor.fetchall()
        for sp in bdb_spreads:
            s = {}
            if sp[0]:
                s['id'] = sp[0]
            if sp[1]:
                s['domain'] = sp[1]
            if sp[2]:
                s['spread_name'] = sp[2]
            if sp[3]:
                s['shell'] = sp[3]
            if sp[4]:
                s['client_version'] = sp[4]
            if sp[5]:
                s['description'] = sp[5]
            spreads.append(s)
        cursor.close()
        return spreads

    def get_email_domains(self):
        cursor = self.db.cursor()
        cursor.execute("SELECT id,navn,system FROM mail_domain WHERE system IS NOT NULL")
        domains = []
        bdb_domains = cursor.fetchall()
        for dom in bdb_domains:
            d = {}
            if dom[0]:
                d['id'] = dom[0]
            if dom[1]:
                d['email_domain'] = dom[1]
            if dom[2]:
                d['spread_id'] = dom[2]
            domains.append(d)
        cursor.close()
        return domains

    def get_email_addresses(self, all_addresses=False):
        cursor = self.db.cursor()
        sql = """
        SELECT p.id,p.epost_adr,p.forward,p.mail,m.id as mail_domain_id,
               m.navn as domain_name, b.brukernavn
        FROM person p, mail_domain m, bruker b
        WHERE m.system IS NOT NULL AND
              p.id = b.person AND
              p.personnr IS NOT NULL AND
              b.user_domain = 1
        """
        if not all_addresses:
            sql += "AND m.system IS NOT NULL\n"
        cursor.execute(sql)
        addresses = []
        bdb_addresses = cursor.fetchall()
        for adr in bdb_addresses:
            a = {}
            if adr[0]:
                a['id'] = adr[0]
            if adr[1]:
                a['email_address'] = adr[1]
            if adr[2]:
                a['forward'] = adr[2]
            if adr[3]:
                a['email'] = adr[3]
            if adr[4]:
                a['email_domain_id'] = adr[4]
            if adr[5]:
                a['email_domain_name'] = adr[5]
            if adr[6]:
                a['username'] = adr[6]
            addresses.append(a)
        return addresses

    def get_account_spreads(self):
        cursor = self.db.cursor()
        cursor.execute("SELECT k.id, g.unix_gid, g.navn as gruppenavn, \
                        k.system, b.brukernavn , s.navn as spread_name, \
                        s.domene, s.skall as require_shell\
                        FROM person p,konto k, bruker b, gruppe g, bdb.system s \
                        WHERE p.id = b.person AND \
                              p.personnr IS NOT NULL AND \
                              k.bruker = b.id AND \
                              k.gruppe = g.id AND \
                              k.system = s.id AND \
                              s.user_domain = 1 \
                       ")
        bdb_spreads = cursor.fetchall()
        spreads = []
        for sp in bdb_spreads:
            s = {}
            if sp[0]:
                s['id'] = sp[0]
            if sp[1]:
                s['unix_gid'] = sp[1]
            if sp[2]:
                s['groupname'] = sp[2].lower()
            if sp[3]:
                s['system'] = sp[3]
            if sp[4]:
                s['username'] = sp[4]
            if sp[5]:
                s['spread_name'] = sp[5]
            if sp[6]:
                s['domain'] = sp[6]
            if sp[7]:
                s['require_shell'] = sp[7]
            spreads.append(s)
        cursor.close()
        return spreads

    def get_vacations(self):
        cursor = self.db.cursor()
        cursor.execute("SELECT v.id,v.person,v.subject,v.message,to_char(p.fodselsdato,'YYYY-MM-DD'), \
                               p.personnr, p.fornavn, p.etternavn \
                        FROM vacation v, person p, bruker b \
                        WHERE v.person = p.id AND \
                              p.id = b.person AND \
                              p.personnr IS NOT NULL \
                              b.user_domain = 1 ")
        bdb_vacations = cursor.fetchall()
        vacations = []
        for vac in bdb_vacations:
            v = {}
            if vac[0]:
                v['id'] = vac[0]
            if vac[1]:
                v['subject'] = vac[1]
            if vac[2]:
                v['message'] = vac[2]
            if vac[3]:
                v['birth_date'] = vac[3]
            if vac[4]:
                v['person_number'] = vac[4]
            if vac[5]:
                v['givenname'] = vac[5]
            if vac[6]:
                v['surname'] = vac[6]
            vacations.append(v)
        cursor.close()
        return vacations

    def get_persons(self,fdato=None,pnr=None,bdbid=None):
        cursor = self.db.cursor()
        if not fdato and not pnr and not bdbid:
            cursor.execute("SELECT DISTINCT p.id, to_char(p.fodselsdato,'YYYY-MM-DD'), p.personnr, p.personnavn,\
                        p.fornavn, p.etternavn, p.sperret, p.forward FROM person p,bruker b \
                        WHERE b.person = p.id and b.user_domain=1 AND \
                        p.personnr IS NOT NULL")
        elif bdbid:
            cursor.execute("SELECT DISTINCT p.id, to_char(p.fodselsdato,'YYYY-MM-DD'), \
                        p.personnr, p.personnavn, p.fornavn, p.etternavn, p.sperret, p.forward \
                        FROM person p WHERE p.id = %s " % (bdbid))
        else:
            cursor.execute("SELECT DISTINCT p.id, to_char(p.fodselsdato,'YYYY-MM-DD'), \
                        p.personnr, p.personnavn, p.fornavn, p.etternavn, p.sperret, p.forward \
                        FROM person p WHERE \
                        p.personnr = %s AND to_char(p.fodselsdato,'DDMMYY') = %s" % (pnr,fdato))
        bdb_persons = cursor.fetchall()
        persons = []
        # Convert to a dict
        for bp in bdb_persons:
            p = {}
            if bp[0]:
                p['id'] = bp[0]
            if bp[1]:
                p['birth_date'] = bp[1]
            if bp[2]:
                p['person_number'] = bp[2]
            #if bp[3]:
            #    p['full_name'] = bp[3]
            if bp[4] and bp[5]:
                    p['full_name'] = bp[4].strip().replace("`","'") + ' ' + bp[5].strip().replace("`","'")
            if bp[4]:
                p['first_name'] = bp[4].strip().replace("`","'")
            if bp[5]:
                p['last_name'] = bp[5].strip().replace("`","'")
            if bp[6]:
                p['sperret'] = bp[6]
            if bp[7]:
                p['mail_forward'] = bp[7].strip()
            persons.append(p)
        cursor.close()
        return persons

    def get_accounts(self,username=None,last=None):
        cursor = self.db.cursor()
        if username:
            cursor.execute("SELECT b.passord_type, b.gruppe, b.person, \
                              b.brukernavn, to_char(b.siden,'YYYY-MM-DD'), \
                              to_char(b.utloper,'YYYY-MM-DD'), \
                              b.unix_uid, b.skall, b.standard_passord, \
                              b.id, b.status, g.unix_gid, b.nt_passord \
                            FROM bruker b,person p, gruppe g \
                            WHERE b.user_domain=1 AND \
                              b.person = p.id AND \
                              b.gruppe =  g.id AND \
                              b.brukernavn='%s'" % username)
        elif last:
            cursor.execute("""
                            select distinct b.passord_type, b.gruppe, b.person,
                            b.brukernavn, to_char(b.siden,'YYYY-MM-DD'),
                            to_char(b.utloper,'YYYY-MM-DD'),
                            b.unix_uid, b.skall, b.standard_passord,
                            b.id, b.status, g.unix_gid, b.nt_passord
                            FROM bruker b,person p, gruppe g, har_hatt_pw h
                            WHERE b.user_domain=1 AND
                            h.byttet > sysdate - interval '%s' minute AND
                            h.bruker = b.id AND
                            h.konto IS NULL AND
                            b.person = p.id AND
                            b.gruppe =  g.id 
                           """ % int(last))
                              
        else:
            cursor.execute("SELECT b.passord_type, b.gruppe, b.person, \
                              b.brukernavn, to_char(b.siden,'YYYY-MM-DD'), \
                              to_char(b.utloper,'YYYY-MM-DD'),  \
                              b.unix_uid, b.skall, b.standard_passord, \
                              b.id, b.status, g.unix_gid, b.nt_passord \
                            FROM bruker b,person p, gruppe g \
                            WHERE b.user_domain=1 AND \
                              b.person = p.id AND \
                              b.gruppe =  g.id ") 
        # user_domain=1 is NTNU
        bdb_accounts = cursor.fetchall()
        accounts = []
        for ba in bdb_accounts:
            if not ba:
                break
            a = {}
            if ba[0]:
                a["password_type"] = ba[0]
            if ba[1]:
                a["group"] = ba[1]
            if ba[2]:
                a["person"] = ba[2]
            if ba[3]:
                a["name"] = ba[3]
            if ba[4]:
                a["creation_date"] = ba[4]
            if ba[5]:
                a["expire_date"] = ba[5]
            else:
                a['expire_date'] = None
            if ba[6]:
                a["unix_uid"] = ba[6]
            if ba[7]:
                a["shell"] = ba[7]
            if ba[8]:
                a["password"] = ba[8]
            if ba[9]:
                a["id"] = ba[9]
            if ba[10]:
                a["status"] = ba[10]
            if ba[11]:
                a["unix_gid"] = ba[11]
            if ba[12]:
                a["password2"] = ba[12]

            accounts.append(a)
        cursor.close()
        return accounts

    def get_groups(self):
        cursor = self.db.cursor()
        cursor.execute("SELECT id, navn, beskrivelse, unix_gid FROM gruppe")
        bdb_groups = cursor.fetchall()
        groups = []
        for bg in bdb_groups:
            g = {}
            g['id'] = bg[0]
            if bg[1]:
                g['name'] = bg[1]
            if bg[2]:
                g['description'] = bg[2]
            if bg[3]:
                g['gid'] = bg[3]
            groups.append(g)
        cursor.close()
        return groups

    def get_affiliations(self):
        cursor = self.db.cursor()
        cursor.execute("""SELECT t.id, t.person, to_char(t.siden,'YYYY-MM-DD'),t.org_enhet, \
                        t.fakultet, t.institutt, \
                        t.tilkn_form, t.familie, f.navn, f.alltidsluttdato, k.kode \
                        FROM tilknyttet t, person p, bruker b, tilkn_former f, ksted k\
                        WHERE t.person = p.id AND \
                              b.person = p.id AND \
                              p.personnr IS NOT NULL AND \
                              b.user_domain = 1 AND \
                              t.tilkn_form = f.id AND \
                              t.fakultet = k.fakultet AND \
                              t.institutt = k.institutt \
                      """)
        bdb_affs = cursor.fetchall()
        affiliations = []
        for af in bdb_affs:
            aff = {}
            aff['id'] = af[0]
            aff['person'] = af[1]
            aff['since'] = af[2]
            aff['org'] = af[3]
            aff['faknr'] = af[4]
            aff['institutt'] = af[5]
            aff['aff_type'] = af[6]
            aff['family'] = af[7]
            aff['aff_name'] = af[8]
            aff['has_end_date'] = af[9]
            aff['ou_code'] = af[10]
            affiliations.append(aff)
        cursor.close()
        return affiliations

    def _get_ous(self, query, type):
        cursor = self.db.cursor()
        cursor.execute(query)
        bdb_ous = cursor.fetchall()
        ous = []
        for bo in bdb_ous:
            ou = {}
            ou['id'] = bo[0]
            ou['name'] = bo[1]
            ou['acronym'] = bo[2]
            ou['postal_address'] = bo[3]
            ou['postal_code'] = bo[4]
            ou['postal_city'] = bo[5]
            ou['stedkode'] = '194' + str(bo[6])
            if type == 'f':
                ou['stedkode'] = ou['stedkode'][:5] + '0000'
            elif type == 'i':
                ou['stedkode'] = ou['stedkode'][:7] + '00'
            ous.append(ou)
        cursor.close()
        return ous

    def get_ous(self):
        cursor = self.db.cursor()
        cursor.execute('SELECT UNIQUE f.id, f.navn, f.fork, f.postadresse, f.postnummer, f.poststed FROM fakultet f WHERE f.org_enhet=%s' % cereconf.BDB_NTNU_OU)
        bdb_ous = cursor.fetchall()
        ous = []
        for bdb_fak in bdb_ous:
            fak = {}
            fak['id'] = bdb_fak[0]
            fak['name'] = bdb_fak[1]
            fak['acronym'] = bdb_fak[2]
            fak['postal_address'] = bdb_fak[3]
            fak['postal_code'] = bdb_fak[4]
            fak['postal_city'] = bdb_fak[5]
            cursor.execute('SELECT UNIQUE k.kode FROM ksted k WHERE k.fakultet=%s' % fak['id'])
            try:
                stedkode = cursor.fetchall()[0][0]
                fak['stedkode'] = '194' + str(stedkode)[:2] + '0000'
            except IndexError:
                pass

            # Fetch all institutes
            cursor.execute('SELECT UNIQUE i.id, i.navn, i.fork, i.postadresse, i.postnummer, i.poststed FROM institutt i, fakultet f WHERE i.fakultet=%s' % fak['id'])
            bdb_insts = cursor.fetchall()
            insts = []
            for bdb_inst in bdb_insts:
                inst = {}
                inst['id'] = bdb_inst[0]
                inst['name'] = bdb_inst[1]
                inst['acronym'] = bdb_inst[2]
                inst['postal_address'] = bdb_inst[3]
                inst['postal_code'] = bdb_inst[4]
                inst['postal_city'] = bdb_inst[5]
                cursor.execute('SELECT UNIQUE k.kode FROM ksted k WHERE k.institutt=%s AND k.fakultet=%s' % (inst['id'], fak['id']))
                try:
                    stedkode = cursor.fetchall()[0][0]
                    inst['stedkode'] = '194' + str(stedkode)[:4] + '00'
                except IndexError:
                    pass

                insts.append(inst)
            fak['institutes'] = insts
            ous.append(fak)
        cursor.close()
        return ous
