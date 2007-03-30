# -*- coding: iso-8859-1 -*-

# Copyright 2006, 2007 University of Oslo, Norway
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

from Cerebrum.modules import ADutilMixIn
from Cerebrum.Utils import Factory
import pickle

class ADFullUserSync(ADutilMixIn.ADuserUtil):
    def _filter_quarantines(self, user_dict):
        def apply_quarantines(entity_id, quarantines):
            if not user_dict.has_key(entity_id):
                return
            qh = QuarantineHandler.QuarantineHandler(self.db, quarantines)
            if qh.should_skip():
                del(user_dict[entity_id])
            if qh.is_locked():
                user_dict[entity_id]['ACCOUNTDISABLE'] = True

        prev_user = None
        user_rows = []
        for row in self.ac.list_entity_quarantines(only_active=True):
            if prev_user != row['account_id'] and prev_user is not None:
                apply_quarantines(prev_user, user_rows)
                user_rows = [row]
            else:
                user_rows.append(row)
            prev_user = row['account_id']
        else:
            if user_rows:
                apply_quarantines(prev_user, user_rows)

    def _fetch_primary_mail_addresses(self, user_dict):
        from Cerebrum.modules.Email import EmailDomain, EmailTarget
        etarget = EmailTarget(self.db)
        rewrite = EmailDomain(self.db).rewrite_special_domains

        for row in etarget.list_email_target_primary_addresses(
                target_type = self.co.email_target_account):
            v = user_dict.get(int(row['entity_id']))
            if not v:
                continue
            try:
                v['mail'] = "@".join(
                    (row['local_part'], rewrite(row['domain'])))
            except TypeError:
                pass  # Silently ignore

    def fetch_cerebrum_data(self, spread):
        """Return a dict {uname: {'adAttrib': 'value'}} for all users
        of relevant spread.  Typical attributes::
        
          # canonicalName er et 'constructed attribute' (fra dn)
          'displayName': '',   # Fullt navn
          'givenName': '',     # fornavn
          'sn': '',            # etternavn
          'mail': '',          # e-post adresse
          'homeDrive': '',     # X:
          'homeDirectory': '', # \\domain\server\uname
          'profilePath': '',   # \\domain\server\uname\profile
          'OU': '',            # Container-OU, used by ADutilMixIn
          'ACCOUNTDISABLE'     # Flag, used by ADutilMixIn
        """
        disk_spread = spread
        db = self.db
        const = self.co
        self.person = Factory.get('Person')(db)

        #
        # Find all users with relevant spread
        #
        tmp_ret = {}
        disk = Factory.get('Disk')(db)
        diskid2path = {}
        for d in disk.list():
            diskid2path[int(d['disk_id'])] = d['path']
        self.logger.debug("Found info about %d disks" % len(diskid2path.keys()))
        
        # We use list_account_home even if we don't get home from
        # here, but since it's the only list-method that returns
        # owner_id and antity_name
        for row in self.ac.list_account_home(
            home_spread=disk_spread, account_spread=spread, filter_expired=True, include_nohome=True):
            tmp_ret[int(row['account_id'])] = {
                'homeDrive': 'N:',
                'TEMPownerId': row['owner_id'],
                'TEMPuname': row['entity_name'],
                'ACCOUNTDISABLE': False   # if ADutilMixIn used get we could remove this
                }
        self.logger.debug("Found info about %d accounts" % len(tmp_ret.keys()))

        #
        # Remove/mark quarantined users
        #
        self._filter_quarantines(tmp_ret)
        
        #
        # Set person names
        #
        pid2names = {}
        for row in self.person.list_persons_name(
                source_system = const.system_cached,
                name_type     = [const.name_first,
                                 const.name_last]):
            pid2names.setdefault(int(row['person_id']), {})[
                int(row['name_variant'])] = row['name']
        for v in tmp_ret.values():
            names = v.get(v['TEMPownerId'])
            if names:
                firstName = names.get(const.name_first, '')
                lastName = names.get(const.name_last, '')
                v['givenName'] = firstName
                v['sn'] = lastName
                v['displayName'] = "%s, %s" % (lastName, firstName)

        #
        # Set data from traits
        #
        for row in self.ac.list_traits(self.co.trait_ad_profile_path):
            v = tmp_ret.get(int(row['entity_id']))
            if v:
                try:
                    tmp = pickle.loads(row['strval'])[int(spread)]
                    v['profilePath'] = tmp
                except Exception, e:
                    self.logger.warn("Error getting profilepath for %i: %s" % (row['entity_id'], e))
        for row in self.ac.list_traits(self.co.trait_ad_account_ou):
            v = tmp_ret.get(int(row['entity_id']))
            if v:
                try:
                    tmp = pickle.loads(row['strval'])[int(spread)]
                    v['OU'] = tmp + "," + self.ad_ldap
                except Exception, e:
                    self.logger.warn("Error getting OU for %i: %s" % (row['entity_id'], e))
        for row in self.ac.list_traits(self.co.trait_ad_homedir):
            v = tmp_ret.get(int(row['entity_id']))
            if v:
                try:
                    tmp = pickle.loads(row['strval'])[int(spread)]
                    v['homeDirectory'] = tmp
                except Exception, e:
                    self.logger.warn("Error getting homedir for %i: %s" % (row['entity_id'], e))

        #
        # Set mail adresses
        #
        self._fetch_primary_mail_addresses(tmp_ret)

        ret = {}
        for k, v in tmp_ret.items():
            ret[v['TEMPuname']] = v
            del(v['TEMPuname'])
            del(v['TEMPownerId'])

        # Create any missing container-OUs for our users
        required_ous = {}
        for v in ret.values():
            ou = v.get('OU')
            if ou:
                required_ous[ou] = True
        self._make_ou_if_missing(required_ous.keys())
        return ret

    def _make_ou_if_missing(self, required_ous, object_list=None, dryrun=False):
        if object_list is None:
            object_list = self.server.listObjects('organizationalUnit')
            object_list.append(self.ad_ldap)
            self.logger.debug("OU-list: %s" % repr(object_list))
        for ou in required_ous:
            if ou not in object_list:
                self.logger.debug("Creating missing OU: "+ou)
                name, parent_ou = ou.split(",", 1)
                if not parent_ou in object_list:
                    # Recursively create parent
                    self._make_ou_if_missing([parent_ou], object_list=object_list, dryrun=dryrun)
                name = name[name.find("=")+1:]
                self.run_cmd('createObject', dryrun, "organizationalUnit", parent_ou, name)
                object_list.append(ou)

class ADFullGroupSync(ADutilMixIn.ADgroupUtil):
    #Groupsync Mixin
    
    def get_default_ou(self, change = None):
        #Returns default OU in AD.
        return "OU=grupper,%s" % cereconf.AD_LDAP

