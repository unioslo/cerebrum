#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
import config
import sys
from Cerebrum.modules.no import fodselsnr
import util
import getopt
import cx_Oracle
import logging
import time
import os

# Set the client encoding for the Oracle client libraries
os.environ['NLS_LANG'] = config.conf.get('bdb', 'encoding')
cnt_missing_nin = 0

class BDB:
    def __init__(self):
        dsn = cx_Oracle.makedsn(config.conf.get('bdb', 'host'), int(config.conf.get('bdb', 'port')),
                config.conf.get('bdb', 'sid'))
        try:
            self.db = cx_Oracle.connect(dsn=dsn, user=config.conf.get('bdb', 'user'),
                password=config.conf.get('bdb', 'password'))
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
        cursor.execute("select m.id,m.navn,m.system,s.navn as spread_name from \
                        mail_domain m, system s \
                        where m.system = s.id and \
                        s.user_domain=1 and \
                        s.operational=1")
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
            if dom[3]:
                d['spread_name'] = dom[3]
            domains.append(d)
        cursor.close()
        return domains

    def get_email_addresses(self):
        cursor = self.db.cursor()
        cursor.execute("select p.id,p.epost_adr,p.forward,p.mail,m.id as mail_domain_id, \
                        m.navn as domain_name, b.brukernavn \
                        from person p, mail_domain m, bruker b \
                        where p.mail_domain = m.id and \
                        p.id = b.person and \
                        b.user_domain = 1 \
                        ")
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
                        FROM konto k, bruker b, gruppe g, bdb.system s \
                        WHERE k.bruker = b.id AND \
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

    def get_persons(self):
        cursor = self.db.cursor()
        cursor.execute("SELECT DISTINCT p.id, to_char(p.fodselsdato,'YYYY-MM-DD'), p.personnr, p.personnavn,\
                        p.fornavn, p.etternavn, p.sperret, p.forward FROM person p,bruker b \
                        WHERE b.person = p.id and b.user_domain=1 AND \
                        p.personnr IS NOT NULL")
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
                    p['full_name'] = bp[4] + ' ' + bp[5]
            if bp[4]:
                p['first_name'] = bp[4]
            if bp[5]:
                p['last_name'] = bp[5]
            if bp[6]:
                p['sperret'] = bp[6]
            if bp[7]:
                b['mail_forward'] = bp[7]
            persons.append(p)
        cursor.close()
        return persons

    def get_accounts(self):
        cursor = self.db.cursor()
        cursor.execute("SELECT b.passord_type, b.gruppe, b.person, b.brukernavn, b.siden, b.utloper \
                        ,b.unix_uid, b.skall, b.standard_passord, b.id, b.status, g.unix_gid \
                        FROM bruker b,person p, gruppe g \
                        WHERE b.user_domain=1 AND \
                              b.person = p.id AND \
                              b.gruppe =  g.id AND \
                              p.personnr is not null") 
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
        cursor.execute('SELECT UNIQUE f.id, f.navn, f.fork, f.postadresse, f.postnummer, f.poststed FROM fakultet f WHERE f.org_enhet=%s' % config.conf.get('bdb-sync', 'bdb_ntnu_ou'))
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
