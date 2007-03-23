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

    def get_persons(self):
        cursor = self.db.cursor()
        cursor.execute("SELECT id, to_char(fodselsdato,'YYYY-MM-DD'), personnr, personnavn, fornavn, \
        etternavn, sperret FROM person" )
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
            # FIXME:
            # We don't want to run a select N times that returns each persons 
            # different phonenumbers. Dropping phone-numbers for now. 
            """
            cursor.execute('SELECT p.phone_number, c.name FROM phone p, phone_categories c WHERE p.person=%s AND p.categorie=c.id' % p['id'])
            numbers = cursor.fetchall()
            for n in numbers:
                p[n[1]] = n[0]
            """
            persons.append(p)
        cursor.close()
        return persons

    def get_accounts(self):
        cursor = self.db.cursor()
        cursor.execute("SELECT passord_type, gruppe, person, brukernavn, siden, utloper, unix_uid, skall, standard_passord, id FROM bruker WHERE user_domain=1") # user_domain=1 is NTNU
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
