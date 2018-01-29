# -*- coding: utf-8 -*-

# Copyright 2006-2009 University of Oslo, Norway
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
import time
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
                target_type=self.co.email_target_account):
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
                'ACCOUNTDISABLE':
                False   # if ADutilMixIn used get we could remove this
            }
        #
        # Remove/mark quarantined users
        #
        self._filter_quarantines(tmp_ret)
        #
        # Set person names
        #
        pid2names = {}
        for row in self.person.search_person_names(
                source_system=self.co.system_cached,
                name_variant=[self.co.name_first,
                              self.co.name_last]):
            pid2names.setdefault(int(row['person_id']), {})[
                int(row['name_variant'])] = row['name']
        for v in tmp_ret.values():
            names = pid2names.get(v['TEMPownerId'])
            if names:
                firstName = unicode(
                    names.get(int(self.co.name_first), ''), 'ISO-8859-1')
                lastName = unicode(
                    names.get(int(self.co.name_last), ''), 'ISO-8859-1')
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

    def _make_ou_if_missing(
            self, required_ous, object_list=None, dryrun=False):
        """
        If an accounts OU doesn't exist in AD, create it (and if
        neccessary the parent OUs) before syncing the account.
        """
        if object_list is None:
            object_list = self.server.listObjects('organizationalUnit')
            if not object_list:
                self.logger.warn(
                    "Problems getting OUs from server.listObjects")
            object_list.append(self.ad_ldap)
        for ou in required_ous:
            if ou not in object_list:
                name, parent_ou = ou.split(",", 1)
                if not parent_ou in object_list:
                    # Recursively create parent
                    self._make_ou_if_missing([parent_ou],
                                             object_list=object_list,
                                             dryrun=dryrun)
                name = name[name.find("=") + 1:]
                self.logger.debug("Creating missing OU: %s" % ou)
                self.create_ou(parent_ou, name, dryrun)
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
        return "%s,%s" % (cereconf.AD_DEFAULT_OU, self.ad_ldap)

    def perform_changes(self, changelist, dry_run):
        """
        Handle changes for accounts synced to AD. If change is OK run
        the proper change command on AD domain server.

        @param changelist: list of changes (dicts)
        @type  changelist: list
        """
        for chg in changelist:
            # RH: There's a bug somewhere. How can that be, this code
            # being som nice and all? So we'll check if change has a
            # type before proceeding.
            if 'type' not in chg:
                self.logger.warn("This shouldn't happen. chg = %s" % str(chg))
                continue
            if ('OU' in chg and chg['OU'] == '' and
                    chg['type'] in ('create_object', 'move_object', 'alter_object')):
                try:
                    user = chg.get('distinguishedName').split(
                        ',')[0].split('=')[1]
                except:
                    user = ''
                msg = "No OU was calculated for %s. Not syncing %s operation" % (
                    user, chg.get('type', ''))
                self.logger.warn(msg)
                continue
            self.logger.debug("Process change: %s" % repr(chg))
            if chg['type'] == 'create_object':
                self.create_object(chg, dry_run)
            else:
                ret = self.run_cmd('bindObject', dry_run,
                                   chg['distinguishedName'])
                if not ret[0]:
                    self.logger.warning("bindObject on %s failed: %r" %
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
            self.logger.warn("No OU for %s. Not creating object." %
                             chg.get('sAMAccountName', chg))
            return
        ret = self.run_cmd('createObject', dry_run,
                           'User', ou, chg['sAMAccountName'])
        if not ret[0]:
            self.logger.error(
                "create user %s failed: %r",
                chg['sAMAccountName'],
                ret)
        else:
            if not dry_run:
                self.logger.info("created user %s", ret)

            pw = self.ac.make_passwd(chg['sAMAccountName'])
            ret = self.run_cmd('setPassword', dry_run, pw)
            if not ret[0]:
                self.logger.warning(
                    "setPassword on %s failed: %s",
                    chg['sAMAccountName'],
                    ret)
            else:
                # Important not to enable a new account if setPassword
                # fail, it will have a blank password.
                uname = ""
                del chg['type']
                # OU is not needed anymore. Delete from chg before sending dict
                if chg.has_key('OU'):
                    del chg['OU']
                if chg.has_key('distinguishedName'):
                    del chg['distinguishedName']
                if chg.has_key('sAMAccountName'):
                    uname = chg['sAMAccountName']
                    del chg['sAMAccountName']
                # Setting default for undefined AD_ACCOUNT_CONTROL values.
                for acc, value in cereconf.AD_ACCOUNT_CONTROL.items():
                    if not chg.has_key(acc):
                        chg[acc] = value
                ret = self.run_cmd('putProperties', dry_run, chg)
                if not ret[0]:
                    self.logger.warning(
                        "putproperties on %s failed: %r",
                        uname,
                        ret)
                ret = self.run_cmd('setObject', dry_run)
                if not ret[0]:
                    self.logger.warning(
                        "setObject on %s failed: %r",
                        uname,
                        ret)
                    return
                if ret[0]:
                    # Wait a few seconds before creating the homedir
                    # for a a new account. AD needs to rest now and then...
                    time.sleep(5)
                    ret = self.run_cmd('createDir', dry_run, 'homeDirectory')
                    if not ret[0]:
                        self.logger.error(
                            'createDir on %s failed: %r',
                            uname,
                            ret)
                    ret = self.run_cmd('createDir', dry_run, 'profilePath')
                    if not ret[0]:
                        self.logger.error(
                            "createDir on %s failed: %r",
                            uname,
                            ret)

    # Had to import this incredibly ugly method from ADutilMixin,
    # because of one small change.
    # FIXME: Rewrite this mess. This is just ... ugly :(
    def compare(self, delete_users, cerebrumusrs, adusrs):
        # Keys in dict from cerebrum must match fields to be populated in AD.

        changelist = []

        for usr, dta in adusrs.items():
            changes = {}
            if cerebrumusrs.has_key(usr):
                # User is both places, we want to check correct data.

                # Checking for correct OU.
                if cerebrumusrs[usr].has_key('OU'):
                    ou = cerebrumusrs[usr]['OU']
                else:
                    self.logger.debug("No OU in cerebrum for user %s" % usr)
                    # This is ugly
                    ou = ''
                if adusrs[usr]['distinguishedName'] != 'CN=%s,%s' % (usr, ou):
                    changes['type'] = 'move_object'
                    changes['OU'] = ou
                    changes['distinguishedName'] = \
                        adusrs[usr]['distinguishedName']
                    # Submit list and clean.
                    changelist.append(changes)
                    changes = {}

                for attr in cereconf.AD_ATTRIBUTES:
                    # Catching special cases.
                    # Check against home drive.
                    if attr == 'homeDrive':
                        home_drive = self.get_home_drive(cerebrumusrs[usr])
                        if adusrs[usr].has_key('homeDrive'):
                            if adusrs[usr]['homeDrive'] != home_drive:
                                changes['homeDrive'] = home_drive

                    # Treating general cases
                    else:
                        if cerebrumusrs[usr].has_key(attr) and \
                                adusrs[usr].has_key(attr):
                            if isinstance(cerebrumusrs[usr][attr], (list)):
                                # Multivalued, it is assumed that a
                                # multivalue in cerebrumusrs always is
                                # represented as a list.
                                Mchange = False

                                if isinstance(adusrs[usr][attr], (str, int, long, unicode)):
                                    # Transform single-value to a list for
                                    # comparison.
                                    val2list = []
                                    val2list.append(adusrs[usr][attr])
                                    adusrs[usr][attr] = val2list

                                for val in cerebrumusrs[usr][attr]:
                                    if val not in adusrs[usr][attr]:
                                        Mchange = True

                                if Mchange:
                                    changes[attr] = cerebrumusrs[usr][attr]
                            else:
                                if adusrs[usr][attr] != cerebrumusrs[usr][attr]:
                                    changes[attr] = cerebrumusrs[usr][attr]
                        else:
                            if cerebrumusrs[usr].has_key(attr):
                                # A blank value in cerebrum and <not
                                # set> in AD -> do nothing.
                                if cerebrumusrs[usr][attr] != "":
                                    changes[attr] = cerebrumusrs[usr][attr]
                            elif adusrs[usr].has_key(attr):
                                # Delete value
                                changes[attr] = ''

                for acc, value in cereconf.AD_ACCOUNT_CONTROL.items():
                    if cerebrumusrs[usr].has_key(acc):
                        if adusrs[usr].has_key(acc) and \
                                adusrs[usr][acc] == cerebrumusrs[usr][acc]:
                            pass
                        else:
                            changes[acc] = cerebrumusrs[usr][acc]

                    else:
                        if adusrs[usr].has_key(acc) and adusrs[usr][acc] == \
                                value:
                            pass
                        else:
                            changes[acc] = value

                # Submit if any changes.
                if len(changes) and ou:
                    changes['distinguishedName'] = 'CN=%s,%s' % (usr, ou)
                    changes['type'] = 'alter_object'

                # after processing we delete from array.
                del cerebrumusrs[usr]

            else:
                # Account not in Cerebrum, but in AD.
                if [s for s in cereconf.AD_DO_NOT_TOUCH if
                        adusrs[usr]['distinguishedName'].find(s) >= 0]:
                    pass
                elif adusrs[usr]['distinguishedName'].find(cereconf.AD_PW_EXCEPTION_OU) >= 0:
                    # Account do not have AD_spread, but is in AD to
                    # register password changes, do nothing.
                    pass
                else:
                    # ac.is_deleted() or ac.is_expired() pluss a small rest of
                    # accounts created in AD, but that do not have AD_spread.
                    if bool(delete_users):
                        changes['type'] = 'delete_object'
                        changes[
                            'distinguishedName'] = adusrs[
                                usr][
                                    'distinguishedName']
                    else:
                        # Disable account.
                        if not bool(adusrs[usr]['ACCOUNTDISABLE']):
                            changes[
                                'distinguishedName'] = adusrs[
                                    usr][
                                        'distinguishedName']
                            changes['type'] = 'alter_object'
                            changes['ACCOUNTDISABLE'] = True
                            # commit changes
                            changelist.append(changes)
                            changes = {}
                        # Moving account.
                        if adusrs[usr]['distinguishedName'] != "CN=%s,OU=%s,%s" % \
                                (usr, cereconf.AD_LOST_AND_FOUND, self.ad_ldap):
                            changes['type'] = 'move_object'
                            changes[
                                'distinguishedName'] = adusrs[
                                    usr][
                                        'distinguishedName']
                            changes['OU'] = "OU=%s,%s" % \
                                (cereconf.AD_LOST_AND_FOUND, self.ad_ldap)

            # Finished processing user, register changes if any.
            if len(changes):
                changelist.append(changes)

        # The remaining items in cerebrumusrs is not in AD, create user.
        for cusr, cdta in cerebrumusrs.items():
            changes = {}
            # TBD: Should quarantined users be created?
            if cerebrumusrs[cusr]['ACCOUNTDISABLE']:
                # Quarantined, do not create.
                pass
            else:
                # New user, create.
                changes = cdta
                changes['type'] = 'create_object'
                changes['sAMAccountName'] = cusr
                changelist.append(changes)
                changes['homeDrive'] = self.get_home_drive(cdta)

        return changelist


class ADFullGroupSync(ADutilMixIn.ADgroupUtil):

    """
    Hiof specific AD group sync mixin.
    """

    def get_default_ou(self, change=None):
        """
        Return default OU for hiof.no.
        """
        # Returns default OU in AD.
        return "OU=Grupper,%s" % self.ad_ldap

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
