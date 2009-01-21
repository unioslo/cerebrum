# -*- coding: iso-8859-1 -*-

# Copyright 2006-2008 University of Oslo, Norway
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

import sys
import cereconf
from Cerebrum import QuarantineHandler
from Cerebrum.modules import ADutilMixIn
from Cerebrum.Utils import Factory
import cPickle

class ADFullUserSync(ADutilMixIn.ADuserUtil):
    """
    Hiof specific AD user sync mixin.
    """

    def _filter_quarantines(self, user_dict):
        """
        Filter quarantined accounts

        @param user_dict: account_id -> account info mapping
        @type user_dict: dict
        """
        def apply_quarantines(entity_id, quarantines):
            q_types = []
            for q in quarantines:
                q_types.append(q['quarantine_type'])
            if not user_dict.has_key(entity_id):
                return
            qh = QuarantineHandler.QuarantineHandler(self.db, q_types)
            if qh.should_skip():
                del(user_dict[entity_id])
            if qh.is_locked():
                user_dict[entity_id]['ACCOUNTDISABLE'] = True

        prev_user = None
        user_rows = []
        for row in self.ac.list_entity_quarantines(only_active=True):
            if prev_user != row['entity_id'] and prev_user is not None:
                apply_quarantines(prev_user, user_rows)
                user_rows = [row]
            else:
                user_rows.append(row)
            prev_user = row['entity_id']
        else:
            if user_rows:
                apply_quarantines(prev_user, user_rows)


    def _fetch_primary_mail_addresses(self, user_dict):
        """
        Fetch primary email addresses for users in user_dict.
        Add key, value pair 'mail', <primary address> if found.

        @param user_dict: account_id -> account info mapping
        @type user_dict: dict
        """
        from Cerebrum.modules.Email import EmailDomain, EmailTarget
        etarget = EmailTarget(self.db)
        rewrite = EmailDomain(self.db).rewrite_special_domains

        for row in etarget.list_email_target_primary_addresses(
                target_type = self.co.email_target_account):
            v = user_dict.get(int(row['target_entity_id']))
            if not v:
                continue
            try:
                v['mail'] = "@".join(
                    (row['local_part'], rewrite(row['domain'])))
            except TypeError:
                pass  # Silently ignore


    def fetch_cerebrum_data(self, spread):
        """
        Fetch relevant cerebrum data for users with the given spread.

        @param spread: ad account spread for a domain
        @type spread: _SpreadCode
        @rtype: dict

        @return: a dict {uname: {'adAttrib': 'value'}} for all users
        of relevant spread. Typical attributes::
        
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
        self.person = Factory.get('Person')(self.db)
        #
        # Find all users with relevant spread
        #
        tmp_ret = {}
        for row in self.ac.search(spread=spread):
            tmp_ret[int(row['account_id'])] = {
                'homeDrive': 'N:',
                'TEMPownerId': row['owner_id'],
                'TEMPuname': row['name'],
                'ACCOUNTDISABLE': False   # if ADutilMixIn used get we could remove this
                }
        #
        # Remove/mark quarantined users
        #
        self._filter_quarantines(tmp_ret)
        #
        # Set person names
        #
        pid2names = {}
        for row in self.person.list_persons_name(
                source_system = self.co.system_cached,
                name_type     = [self.co.name_first,
                                 self.co.name_last]):
            pid2names.setdefault(int(row['person_id']), {})[
                int(row['name_variant'])] = row['name']
        for v in tmp_ret.values():
            names = pid2names.get(v['TEMPownerId'])
            if names:
                firstName = unicode(names.get(int(self.co.name_first), ''), 'ISO-8859-1')
                lastName = unicode(names.get(int(self.co.name_last), ''), 'ISO-8859-1')
                v['givenName'] = firstName
                v['sn'] = lastName
                v['displayName'] = "%s %s" % (firstName, lastName)

        #
        # Set data from traits
        #
        for ad_trait, key in ((self.co.trait_ad_profile_path, 'profilePath'),
                              (self.co.trait_ad_account_ou, 'OU'),
                              (self.co.trait_ad_homedir, 'homeDirectory')):
            # Use EntityTrait API instead og hiofs Account for
            # efficiency reasons
            for row in self.ac.list_traits(ad_trait):
                v = tmp_ret.get(int(row['entity_id']))
                if v:
                    try:
                        tmp = cPickle.loads(row['strval'])
                        if int(spread) in tmp:
                            v[key] = unicode(tmp[int(spread)], 'ISO-8859-1')
                            if key == 'OU':                            
                                v[key] += "," + self.ad_ldap                        
                    except KeyError:
                        self.logger.warn("No %s -> %s mapping for user %i" % (
                            spread, key, row['entity_id']))
                    except Exception, e:
                        self.logger.warn("Error getting %s for %i: %s" % (
                            key, row['entity_id'], e))

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
        """
        If an accounts OU doesn't exist in AD, create it (and if
        neccessary the parent OUs) before syncing the account.
        """
        if object_list is None:
            object_list = self.server.listObjects('organizationalUnit')
            if not object_list:
                self.logger.warn("Problems getting OUs from server.listObjects")
            object_list.append(self.ad_ldap)
        for ou in required_ous:
            if ou not in object_list:
                name, parent_ou = ou.split(",", 1)
                if not parent_ou in object_list:
                    # Recursively create parent
                    self._make_ou_if_missing([parent_ou],
                                             object_list=object_list,
                                             dryrun=dryrun)
                name = name[name.find("=")+1:]
                self.create_ou(parent_ou, name, dryrun)
                self.logger.debug("Creating missing OU: %s" % ou)
                object_list.append(ou)


    def create_ou(self, ou, name, dryrun):
        ret = self.run_cmd('createObject', dryrun,
                           "organizationalUnit", ou, name)
        if not ret[0]:
            self.logger.warn(ret[1])
        

    def get_default_ou(self, change=None):
        """
        Return default OU for hiof.no
        """
        return "OU=BOFH brukere,%s" % self.ad_ldap


    def perform_changes(self, changelist, dry_run):
        """
        Handle changes for accounts synced to AD. If change is OK run
        the proper change command on AD domain server.

        @param changelist: list of changes (dicts)
        @type  changelist: list
        """
        for chg in changelist:
            if ('OU' in chg and chg['OU'] == self.get_default_ou() and 
                chg['type'] in ('create_object', 'move_object', 'alter_object')):
                msg = "No OU was calculated for %s. Not syncing %s operation" % (
                    chg.get('distinguishedName', ''), chg.get('type', ''))
                self.logger.warn(msg)
                continue
            self.logger.debug("Process change: %s" % repr(chg))
            if chg['type'] == 'create_object':
                self.create_object(chg, dry_run)
            else:
                ret = self.run_cmd('bindObject', dry_run,
                                   chg['distinguishedName'])
                if not ret[0]:
                    self.logger.warning("bindObject on %s failed: %r" % \
                                   (chg['distinguishedName'], ret))
                else:
                    exec('self.' + chg['type'] + '(chg, dry_run)')


    def create_object(self, chg, dry_run):
        """
        Create account, it's properties, homedir and profile path in
        AD. ADutilMixIn.create_object is overwritten because we don't
        want to sync users without proper OU.

        @param chg: changes to be synced for an account
        @type  chg: dict
        """
        if chg.has_key('OU'):
            ou = chg['OU']
        else:
            self.logger.error("No OU for %s" % chg.get('sAMAccountName', chg))
            return
        ret = self.run_cmd('createObject', dry_run,
                           'User', ou, chg['sAMAccountName'])
        if not ret[0]:
            self.logger.error("create user %s failed: %r", chg['sAMAccountName'], ret)
        else:
            if not dry_run:
                self.logger.info("created user %s", ret)

            pw = unicode(self.ac.make_passwd(chg['sAMAccountName']),
                         'iso-8859-1')
            ret = self.run_cmd('setPassword', dry_run, pw)
            if not ret[0]:
                self.logger.warning("setPassword on %s failed: %s", chg['sAMAccountName'], ret)
            else:
                #Important not to enable a new account if setPassword
                #fail, it will have a blank password.
                uname = ""
                del chg['type']
                if chg.has_key('distinguishedName'):
                    del chg['distinguishedName']
                if chg.has_key('sAMAccountName'):
                    uname = chg['sAMAccountName']
                    del chg['sAMAccountName']
                #Setting default for undefined AD_ACCOUNT_CONTROL values.
                for acc, value in cereconf.AD_ACCOUNT_CONTROL.items():
                    if not chg.has_key(acc):
                        chg[acc] = value
                ret = self.run_cmd('putProperties', dry_run, chg)
                if not ret[0]:
                    self.logger.warning("putproperties on %s failed: %r", uname, ret)
                ret = self.run_cmd('setObject', dry_run)
                if not ret[0]:
                    self.logger.warning("setObject on %s failed: %r", uname, ret)
                    return
                if ret[0]:
                    ret = self.run_cmd('createDir', dry_run, 'homeDirectory')
                    if not ret[0]:
                        self.logger.error('createDir on %s failed: %r', uname, ret)
                    ret = self.run_cmd('createDir', dry_run, 'profilePath')
                    if not ret[0]:
                        self.logger.error("createDir on %s failed: %r", uname, ret)
                     
class ADFullGroupSync(ADutilMixIn.ADgroupUtil):
    """
    Hiof specific AD group sync mixin.
    """

    def get_default_ou(self, change=None):
        """
        Return default OU for hiof.no.
        """
        #Returns default OU in AD.
        return "OU=Grupper,%s" %  self.ad_ldap
    
    def fetch_ad_data(self):
        """
        Fetch relevant data from AD

        @rtype: dict 
        @return: dict of ad user data. 
        """
        ret = self.server.listObjects('group', True, self.get_default_ou())
        if ret is False:
            self.logger.error("Couldn't fetch data from AD service. Quitting!")
            # TODO: raise an exception, don't quit.
            sys.exit(1)
        return ret

