#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

import pickle
import re
import time
import xmlrpclib
from mx import DateTime
# from Cerebrum.modules.bofhd.xmlutils import xmlrpc_to_native, native_to_xmlrpc

def xmlrpc_to_native(obj):
    """Translate XML-RPC-usable structures back to Python objects"""
    #  We could have used marshal.{loads,dumps} here,
    # but then the Java client would have trouble
    # encoding/decoding requests/responses.
    if isinstance(obj, (str, unicode)):
        if isinstance(obj, (unicode,)):
            obj = obj.encode('iso8859-1')
        if obj == ':None':
            return None
        elif obj.startswith(":"):
            return obj[1:]
        return obj
    elif isinstance(obj, (tuple, list)):
        obj_type = type(obj)
        return obj_type([xmlrpc_to_native(x) for x in obj])
    elif isinstance(obj, dict):
        return dict([(xmlrpc_to_native(x), xmlrpc_to_native(obj[x]))
                              for x in obj])
    elif isinstance(obj, (int, long, float)):
        return obj
    elif isinstance(obj, xmlrpclib.DateTime):
        t = DateTime.ISO.ParseDateTime(obj.value)
        return t.strftime('%Y-%m-%d')
#    elif isinstance(obj, xmlrpclib.Binary):
#        return str(obj)
    else:
        # unknown type, no need to recurse (probably DateTime =) ) 
        return obj

class CerebrumProxy(object):
    LIVE_MODE = 1
    PLAYBACK_MODE = 2
    
    def __init__(self, logger, url=None, recfile=None):
        self._logger = logger
        self._sessionid= None
        if recfile is not None:
            self.data = pickle.load(open(recfile))
            self.mode = self.PLAYBACK_MODE
        else:
            if url.startswith("https"):
                from M2Crypto.m2xmlrpclib import Server, SSL_Transport
                self.conn = Server(url,
                                 SSL_Transport(), encoding='iso8859-1')
            else:
                self.conn = xmlrpclib.Server(url, encoding='iso8859-1')
            self.mode = self.LIVE_MODE

    def run_command(self, cmd, *args):
        if self.mode == self.PLAYBACK_MODE:
            if self.data.has_key((cmd, args)):
                return self.data[(cmd, args)]
            for k, v in self.data.items():
                self._logger.debug("Check: %s -> %s" % (k[0], cmd))
                if k[0] == cmd:
                    return v
            self._logger.debug("run_command returned None")
            return None
        else:
            self._logger.debug("run_command: %s" % repr(
                (self._session_id, cmd, args)))
            r = self.conn.run_command(self._session_id, cmd, *args)
            self._logger.debug(" <- %s" % repr(r))
            return xmlrpc_to_native(r)

    def convert(self, dta): # TODO: a better name
        r = dta.copy()
        for k, v in r.items():
            if v is None:
                r[k] = '<Not set>'
        return r

    def clear_passwords(self):
        return self.run_command('misc_clear_passwords')
    
    def set_session_id(self, sessid):
        self._session_id = sessid

    def login(self, uname, password):
        if self.mode == self.PLAYBACK_MODE:
            return time.time()
        r = self.conn.login(uname, password)
        self._logger.debug("login(%s) -> %s" % (uname, r))
        return r
        
    def logout(self):
        if self.mode == self.LIVE_MODE:
            return self.conn.logout(self._session_id)

    def get_auth_level(self):
        return self.run_command('get_auth_level')

    def get_default_email(self, entity_id):
        return self.run_command('get_default_email', 'id:%s' % entity_id)

    def user_get_pwd(self, id):
        return self.run_command('user_get_pwd', id)
    
    def get_entity_spreads(self, entity_id):
        return self.run_command('get_entity_spreads', entity_id)

    def group_create(self, name, description):
        return self.run_command('group_create', name, description)

    def list_active(self):
        return self.run_command('list_active')

    def find_school(self, ou_name):
        return self.run_command('find_school', ou_name)

    def group_user(self, entity_id=None, uname=None):
        ret = []
        search = self._get_search_str(
            etype='user', entity_id=entity_id, name=uname)
        for r in self.run_command('group_user', search):
            tmp = []
            for s in r['spreads'].split(","):
                tmp.append(s)
            r['spreads'] = tmp
            ret.append(r)
        return ret

    def group_search(self, search_type=None, search_value=None):
        r = self.run_command('group_search', '%s:%s' % (
            search_type, search_value))
        for t in r:
            t['entity_id'] = t['id']
        return r

    def group_list(self, entity_id=None, uname=None):
        search = self._get_search_str(
            etype='group', entity_id=entity_id, name=uname)
        r = self.run_command('group_list', search)
        for t in r:
            t['entity_id'] = t['id']
        return r

    def group_info(self, entity_id=None, name=None):
        search = self._get_search_str(
            etype='group', entity_id=entity_id, name=name)
        ret = {}
        for r in self.run_command('group_info', search):
            ret.update(r)
        for k in ('c_account_u', 'c_group_u'):
            if not ret.has_key(k):
                ret[k] = 0
        return ret

    def group_add_entity(self, member_id, group_id, member_op='union'):
        return self.run_command('group_add_entity', member_id, group_id, member_op)

    def group_remove_entity(self, member_id, group_id, member_op='union'):
        return self.run_command('group_remove_entity', member_id, group_id, member_op)

    def _get_search_str(self, etype=None, entity_id=None, name=None):
        if entity_id:
            if etype in ('user', 'group'):
                return 'id:%s' % entity_id
            else:
                return 'entity_id:%s' % entity_id                
        else:
            return name

    def list_passwords(self):
        return self.run_command('misc_list_passwords', 'skjerm')

    def list_defined_spreads(self):
        return self.run_command('list_defined_spreads')

    def person_list_user_priorities(self, entity_id=None, name=None):
        search = self._get_search_str(
            etype='person', entity_id=entity_id, name=name)
        ret = self.run_command('person_list_user_priorities', search)
        for r in ret:
            tmp = self._parse_aff(r['affiliation'])
            self._logger.debug("%s -> %s" % (r['affiliation'], tmp))
            if tmp:
                r.update(tmp)
        return ret

    def user_create(self, uname, owner_id):
        return self.run_command('user_create', uname, owner_id)

    def user_info(self, entity_id=None, uname=None):
        search = self._get_search_str(
            etype='user', entity_id=entity_id, name=uname)
        new_user = self.run_command('user_info', search)
        new_affs = []
#        for a in new_user['affiliations'].split(",\n"):
#            tmp = self._parse_aff(a)
#            if tmp:
#                new_affs.append(tmp)
        new_user['affiliations'] = new_affs
        if "username" not in new_user:
            new_user["username"] = uname
        if "entity_id" not in new_user:
            new_user["entity_id"] = entity_id
        return new_user

    def user_password(self, entity_id, password=None):
        if password:
            return self.run_command('user_password', 'id:%s' % entity_id, password)
        else:
            return self.run_command('user_password', 'id:%s' % entity_id)

    def user_suggest_uname(self, owner_id):
        return self.run_command('user_suggest_uname', owner_id)

    def quarantine_show(self, entity_id=None, uname=None):
        search = self._get_search_str(
            etype='user', entity_id=entity_id, name=uname)
        return self.run_command('quarantine_show', 'account', search)

    def email_info(self, entity_id=None, uname=None):
        search = self._get_search_str(
            etype='user', entity_id=entity_id, name=uname)
        tmp = self.run_command('email_info', search)
        ret = {}
        for r in tmp:
            for k, v in r.items():
                if k == 'valid_addr_1':
                    ret['valid_addr'] = [v]
                elif k == 'valid_addr':
                    ret['valid_addr'].append(r['valid_addr'])
                else:
                    ret[k] = v
        return ret

    def misc_history(self, days):
        tmp = self.run_command('misc_history', days)
        map_desc = {'e_account:password': 'Ny bruker',
                    'person:create': 'Ny person'}
        ret = []
        for r in tmp:
            if r['change_type'] == 'e_account:create':
                continue # also has a password, use that
            r['change_type'] = map_desc.get(r['change_type'],  r['change_type'])
            ret.append(r)
        return ret

    def user_find(self, search_type=None, search_value=None):
        if search_type == 'owner':
            ret = self.run_command('person_accounts',
                                   'entity_id:%s' % search_value)
        elif search_type == 'uname':
            ret = self.run_command('user_find', search_type, search_value)
        else:
            raise ("Ukjent søkekriterium: finn bruker ved (%s, %s)" %
                   (search_type, search_value))

        for r in ret:
            r['username'] = r['name']
            r['entity_id'] = r['account_id']
        return ret
    # end user_find

    def person_find(self, search_type=None, search_value=None):
        return self.run_command('person_find', search_type, search_value)

    def person_info(self, entity_id=None):
        new_person = {'affiliations': [],
                      'fnrs': []}
        for p in self.run_command('person_info', 'entity_id:%s' % entity_id):
            if p.has_key('affiliation'):
                new_person['affiliations'].append(p)
            elif p.has_key('fnr'):
                new_person['fnrs'].append(p)
            else:
                for k, v in p.items():
                    if k.endswith('_1'):
                        new_person['affiliations'] = [{
                            'affiliation': p['affiliation_1'],
                            'source_system': p['source_system_1']
                            }]
                    else:
                        new_person[k] = v
        new_affs = []
        for a in new_person['affiliations']:
            tmp = self._parse_aff(a['affiliation'])
            if tmp:
                a.update(tmp)
                new_affs.append(a)
        new_person['affiliations'] = new_affs
        return new_person

    def spread_add(self, entity_type, id, spread):
        return self.run_command('spread_add', entity_type, id, spread)

    def _parse_aff(self, aff_str):
        # ANSATT/tekadm@331520 (Grunntjenester)
        aff_re = re.compile(r'^([^/]+)/?([^@]+)?@(\S+)[^[]+\(([^)]+)')
        m = aff_re.match(aff_str)
        if not m:
            return {}
        ret = { 'aff_type': m.group(1).lower(),
                'aff_status': m.group(2),
                'aff_stedkode': m.group(3),
                'aff_sted_desc': m.group(4)}
        return ret
                   
# arch-tag: ccc8df24-7155-11da-90e8-d1d0823776a7
