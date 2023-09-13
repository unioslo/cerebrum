# -*- coding: utf-8 -*-
#
# Copyright 2006-2023 University of Oslo, Norway
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

"""Module with functions for cerebrum export to Active Directory at UiO

Extends the functionality provided in the general AD-export module
ADutilMixIn.py to work with the AD setup at the University of Oslo.
"""
import copy
from collections import defaultdict

import six

import cereconf
from Cerebrum import QuarantineHandler
from Cerebrum import Utils
from Cerebrum.modules import CLHandler
from Cerebrum.modules.Email import EmailTarget
from Cerebrum.modules.no.uio import ADutils
from Cerebrum.utils import json


def is_blacklisted(name):
    """ Check if the given name is blacklisted.

    Add a name to the blacklist by putting a substring of the name in
    `cereconf.AD_DO_NOT_TOUCH`.
    """
    return any(sub.upper() in name.upper()
               for sub in getattr(cereconf, 'AD_DO_NOT_TOUCH', ()))


class ADFullUserSync(ADutils.ADuserUtil):

    def __init__(self, *args, **kwargs):
        super(ADFullUserSync, self).__init__(*args, **kwargs)
        self.pg = Utils.Factory.get('PosixGroup')(self.db)
        self.pu = Utils.Factory.get('PosixUser')(self.db)

    def _filter_quarantines(self, user_dict):
        """Filter quarantined accounts

        Removes all accounts that are quarantined from export to AD

        @param user_dict: account_id -> account info mapping
        @type user_dict: dict
        """
        def apply_quarantines(entity_id, quarantines):
            q_types = []
            for q in quarantines:
                q_types.append(q['quarantine_type'])
            if entity_id not in user_dict:
                return
            qh = QuarantineHandler.QuarantineHandler(self.db, q_types)
            if qh.should_skip():
                del user_dict[entity_id]
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

    def _update_mail_info(self, user_dict):
        """
        Fetch primary email address for users in user_dict.

        @param user_dict: account_id -> account information
        @type user_dict: dict
        """
        targets = EmailTarget(self.db).list_email_target_addresses
        co = Utils.Factory.get('Constants')(self.db)
        for row in targets(target_type=co.email_target_account,
                           domain='uio.no', uname_local=True):
            mail = "@".join((row['local_part'], row['domain']))
            try:
                user_dict[row['entity_name']]['mail'] = mail
            except KeyError:
                pass

    def _update_home_drive_info(self, user_dict, spread):
        """ Update user_dict with home directory.

        Fetch host server for users homedrive and build homeDirectory
        attribute.

        @param user_dict: account_id -> account information
        @type user_dict: dict
        """
        # Build dict of all valid hosts: host id -> host name
        ho = Utils.Factory.get('Host')(self.db)
        hid2hostname = {}
        for ho_row in ho.search():
            hid2hostname[ho_row["host_id"]] = ho_row["name"]

        # Getting all homedrives for user with spread.
        uname2disk = dict((r['entity_name'], r) for r in
                          self.ac.list_account_home(
                                    account_spread=self.co.Spread(spread))
                          if r['host_id'] and r['host_id'] in hid2hostname)

        # Assigning homeDirectory to users
        users_wo_homedir = defaultdict(int)
        for k, v in user_dict.iteritems():
            if k in uname2disk:
                home_srv = hid2hostname[uname2disk[k]['host_id']]
                # The new disks requires a somewhat longer path:
                if home_srv in getattr(cereconf, 'AD_HOMEDIR_HITACHI_DISKS',
                                       ()):
                    path = uname2disk[k]['path'].split('/')[-1]
                    v['homeDirectory'] = r"\\%s\%s\%s" % (home_srv, path, k)
                else:
                    v['homeDirectory'] = r"\\%s\%s" % (home_srv, k)
            else:
                users_wo_homedir[k.partition('-')[2]] += 1
                v['homeDirectory'] = ""
        self.logger.debug("Number of users without homeDirectory: %d (%r)",
                          sum(users_wo_homedir.values()),
                          dict(users_wo_homedir))

    def get_default_ou(self):
        """
        Return default OU for users.
        """
        return "%s" % (cereconf.AD_USER_OU)

    def fetch_cerebrum_data(self, spread):
        """
        Fetch relevant cerebrum data for users with the given spread.

        @param spread: ad account spread for a domain
        @type spread: _SpreadCode
        @rtype: dict
        @return: a dict {uname: {'adAttrib': 'value'}} for all users
        of relevant spread. Typical attributes::

          # canonicalName er et 'constructed attribute' (fra dn)
          'displayName': String,          # Fullt navn
          'givenName': String,            # fornavn
          'sn': String,                   # etternavn
          'userPrincipalName' : String    # brukernavn@domene
          'mail' : String                 # epostadresse
          'homeDrive': String             # Monteringspunkt for hjemmedisk
          'homeDirectory' : String        # Full path til hjemmedisk
          'userAccountControl' : Bitmap   # bruker settinger i AD
          'ACCOUNTDISABLE'                # Flag, used by ADutilMixIn
        """

        self.person = Utils.Factory.get('Person')(self.db)

        #
        # Find all users with relevant spread
        #
        tmp_ret = {}
        spread_res = list(self.ac.search(spread=spread))
        for row in spread_res:
            tmp_ret[int(row['account_id'])] = {
                'TEMPownerId': row['owner_id'],
                'TEMPuname': row['name'],
                'ACCOUNTDISABLE': False,
            }
        self.logger.debug("Fetched %i accounts with spread %r",
                          len(tmp_ret), spread)

        #
        # Remove/mark quarantined users
        #
        self._filter_quarantines(tmp_ret)
        self.logger.debug("%i accounts with spread %r after quarantine filter",
                          len(tmp_ret), spread)
        a = 0
        for u in tmp_ret.itervalues():
            if u['ACCOUNTDISABLE']:
                a += 1
        self.logger.debug("Number of disabled accounts: %i", a)

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
                firstName = names.get(int(self.co.name_first), '')
                lastName = names.get(int(self.co.name_last), '')
                v['givenName'] = firstName.strip()
                v['sn'] = lastName.strip()
                v['displayName'] = "%s %s" % (firstName, lastName)

        #
        # Posix attributes
        #
        # This requires that the domain is first set up with the UNIX
        # attributes schema (msSFU30).
        groupid2gid = dict((row['group_id'], row['posix_gid'])
                           for row in self.pg.list_posix_groups())
        posixusers = dict((row['account_id'], row)
                          for row in self.pu.list_posix_users(
                              spread=self.co.Spread(spread),
                              filter_expired=True))
        groupspread = self.co.Spread(cereconf.AD_GROUP_SPREAD)
        groupid2name = dict((row['group_id'],
                             ''.join((row['name'], cereconf.AD_GROUP_POSTFIX)))
                            for row in self.pg.search(spread=groupspread))
        i = 0
        for k, v in tmp_ret.iteritems():
            if k in posixusers:
                v['uidNumber'] = posixusers[k]['posix_uid'] or ''
                v['gidNumber'] = groupid2gid[posixusers[k]['gid']] or ''
                v['gecos'] = posixusers[k]['gecos'] or ''
                v['uid'] = [v['TEMPuname']]  # UID is a list/array in AD
                v['mssfu30name'] = v['TEMPuname']
                v['msSFU30NisDomain'] = 'uio'
                v['primaryGroup_groupname'] = groupid2name.get(
                    posixusers[k]['gid']) or ''
                i += 1
        self.logger.debug("Number of users with posix-data: %d", i)

        # Getting some posix statistics, could be removed later:

        # Sort by users' DFG:
        bydfg = dict()
        for k, v in tmp_ret.iteritems():
            gname = v.get('primaryGroup_groupname')
            bydfg.setdefault(gname, set()).add(v['TEMPuname'])
        self.logger.debug("Users spread around %d DFGs", len(bydfg))
        # Print out largest DFG groups:
        max = 10
        for k in sorted(bydfg, key=lambda x: len(bydfg[x]), reverse=True):
            self.logger.debug("DFG: %20s : %6d", k, len(bydfg[k]))
            max -= 1
            if max < 1:
                break
        self.logger.debug("Number of users without DFG: %d (%r)",
                          len(bydfg.get(None, ())),
                          bydfg.get(None, ()))
        # Find the number of users with a personal dfg:
        personal_dfg = 0
        for k, v in tmp_ret.iteritems():
            gname = '%s-gruppe' % v['TEMPuname']
            if gname == v.get('primaryGroup_groupname'):
                personal_dfg += 1
        self.logger.debug("Users with personal dfg: %d", personal_dfg)
        # statistics done, the code above could be removed

        #
        # Indexing user dict on username instead of entity id
        #
        userdict_ret = {}
        for k, v in tmp_ret.iteritems():
            userdict_ret[v['TEMPuname']] = v
            del v['TEMPuname']
            del v['TEMPownerId']

        #
        # Set mail info
        #
        self._update_mail_info(userdict_ret)

        #
        # Set home drive info
        #
        self._update_home_drive_info(userdict_ret, spread)

        #
        # Assign derived attributes
        #
        for k, v in userdict_ret.iteritems():
            # TODO: derive domain part from LDAP DC components
            v['userPrincipalName'] = k + "@uio.no"
            v['homeDrive'] = "M:"

        return userdict_ret

    def fetch_ad_data(self, search_ou):
        """
        Returns full LDAP path to AD objects of type 'user' in search_ou and
        child ous of this ou.

        @param search_ou: LDAP path to base ou for search
        @type search_ou: String
        """
        # Find a list of all groups' SID, to be used when populating the posix
        # attribute for primary group for the user, as it reuquires the last
        # part of the SID.
        self.logger.debug("Fetching group SIDs for posix, from OU: %r",
                          self.ad_ldap)
        self.groupsids = self.server.getObjectID(True, False, self.ad_ldap,
                                                 'group')
        # groupsids is a dict, with groupname as key, and each value is a dict
        # with values. We are interested in the value 'Sid', but other values
        # might be useful too.
        if not self.groupsids:
            self.logger.warn("No group SIDs returned from AD")
        self.logger.debug("Fetched %d SIDs from AD", len(self.groupsids))

        # Setting the userattributes to be fetched.
        self.logger.debug("Fetching AD users from: %r", search_ou)
        self.server.setUserAttributes(cereconf.AD_ATTRIBUTES,
                                      cereconf.AD_ACCOUNT_CONTROL)
        return self.server.listObjects('user', True, search_ou)

    def write_sid(self, objtype, name, sid, dry_run):
        """Store AD object SID to cerebrum database for given user

        @param objtype: type of AD object
        @type objtype: String
        @param name: user name
        @type name: String
        @param sid: SID from AD
        @type sid: String
        """
        # husk aa definere AD som kildesystem
        # TBD: Check if we create a new object for a entity that already
        # have a externalid_accountsid defined in the db and delete old?
        self.logger.debug("Writing SID for %r %r to database", objtype, name)
        if objtype == 'account' and not dry_run:
            self.ac.clear()
            self.ac.find_by_name(name)
            self.ac.affect_external_id(self.co.system_ad,
                                       self.co.externalid_accountsid)
            self.ac.populate_external_id(self.co.system_ad,
                                         self.co.externalid_accountsid, sid)
            self.ac.write_db()

    def perform_changes(self, changelist, dry_run, store_sid):
        """
        Binds to AD object and perform changes such as
        updates to attributes or move and/or disabling.

        @param changelist: user name -> changes mapping
        @type changelist: array of dict
        @param dry_run: Flag
        @param store_sid: Flag
        """
        for chg in changelist:
            self.logger.debug("Process change: %s", repr(chg))
            if chg['type'] == 'create_object':
                self.create_object(chg, dry_run, store_sid)
            else:
                ret = self.run_cmd('bindObject', dry_run,
                                   chg['distinguishedName'])
                if not ret[0]:
                    self.logger.warning("bindObject on %r failed: %r",
                                        chg['distinguishedName'], ret)
                else:
                    exec('self.' + chg['type'] + '(chg, dry_run)')

    def create_object(self, chg, dry_run, store_sid):
        """
        Creates AD account object and populates given attributes

        @param chg: account_id -> account info mapping
        @type chg: dict
        @param dry_run:
            Flag to decide if changes are commited to AD and Cerebrum
        """
        ou = chg.get("OU", self.get_default_ou())
        ret = self.run_cmd('createObject', dry_run, 'User', ou,
                           chg['sAMAccountName'])
        if not ret[0]:
            self.logger.warning("create user %r failed: %r",
                                chg['sAMAccountName'], ret)
        else:
            if not dry_run:
                self.logger.info("created user %r", ret)
            if store_sid:
                self.write_sid('account', chg['sAMAccountName'], ret[2],
                               dry_run)
            pw = self.get_password(chg['sAMAccountName'])
            ret = self.run_cmd('setPassword', dry_run, pw)
            if not ret[0]:
                self.logger.warning("Setting random password on %r failed: %r",
                                    chg['sAMAccountName'], ret)
            else:
                # Important not to enable a new account if setPassword
                # fail, it will have a blank password.
                uname = ""
                del chg['type']
                if 'distinguishedName' in chg:
                    del chg['distinguishedName']
                if 'sAMAccountName' in chg:
                    uname = chg['sAMAccountName']
                    del chg['sAMAccountName']
                if 'primaryGroup_groupname' in chg:
                    del chg['primaryGroup_groupname']
                # Setting default for undefined AD_ACCOUNT_CONTROL values.
                for acc, value in cereconf.AD_ACCOUNT_CONTROL.items():
                    if acc not in chg:
                        chg[acc] = value
                ret = self.run_cmd('putProperties', dry_run, chg)
                if not ret[0]:
                    self.logger.warning("putproperties on %r failed: %r",
                                        uname, ret)
                ret = self.run_cmd('setObject', dry_run)
                if not ret[0]:
                    self.logger.warning("setObject on %r failed: %r",
                                        uname, ret)

    def get_password(self, uname):
        """
        Returns password for a new user to be created in AD. First tries to
        get the password from the database, and if unsuccessful it will return
        a random secure password.

        @param uname: Username of new user
        @type uname: string
        @rtype: string
        @return: password
        """
        # TODO: move passwords to auth-table and fetch from there
        self.ac.clear()
        # need the account_id which is not passed to create_object
        self.ac.find_by_name(uname)
        # get the last pwd-change entry from change_log for this account
        # and user it to populate AD.
        # And if there isn't a pwd in changelog, generate one
        tmp = self.db.get_log_events(types=(self.ac.clconst.account_password,),
                                     subject_entity=self.ac.entity_id,
                                     return_last_only=True)
        try:
            row = tmp.next()
            params = json.loads(row["change_params"])
            passwd = params["password"]
        except (StopIteration, AttributeError, KeyError, TypeError):
            passwd = self.ac.make_passwd(uname)
        return passwd

    def compare(self, delete_users, cerebrumusrs, adusrs):
        """
        Check if any values for account need be updated in AD

        @param cerebrumusers: account_id -> account info mapping
        @type cerebrumusers: dict
        @param adusers: account_id -> account info mapping
        @type adusers: dict
        @param delete_users: Delete or move unwanted users
        @type delete_users: Flag
        @rtype: list
        @return: a list over dicts with changes to AD objects
        """
        # Keys in dict from cerebrum must match fields to be populated in AD.
        changelist = []

        for usr, dta in adusrs.iteritems():

            if is_blacklisted(adusrs[usr]['distinguishedName']):
                # User is blacklisted. We do not care if it exists in Cerebrum,
                # we do not touch it!
                if usr in cerebrumusrs:
                    # Remove it from the cerebrum data so it doesn't get a
                    # 'create_object' change.
                    del cerebrumusrs[usr]
                continue

            changes = {}
            if usr in cerebrumusrs:
                # User is both places, we want to check correct data.
                # Checking for correct OU.
                ou = cerebrumusrs.get("OU", self.get_default_ou())
                if adusrs[usr]['distinguishedName'] != 'CN=%s,%s' % (usr, ou):
                    changes['type'] = 'move_object'
                    changes['OU'] = ou
                    changes['distinguishedName'] = \
                        adusrs[usr]['distinguishedName']
                    # Submit list and clean.
                    changelist.append(changes)
                    changes = {}

                for attr in cereconf.AD_ATTRIBUTES:
                    # Check against home drive.
                    if attr == 'homeDrive':
                        home_drive = self.get_home_drive(cerebrumusrs[usr])
                        if 'homeDrive' in adusrs[usr]:
                            if adusrs[usr]['homeDrive'] != home_drive:
                                changes['homeDrive'] = home_drive
                        continue

                    if attr == 'primaryGroupID':
                        # PrimaryGroupID must contain the last part of the SID,
                        # which we had to retrieve from AD on beforehand. The
                        # primaryGroup_groupname contains the AD name of the
                        # group that is the dfg, and all the group SIDs are
                        # located in self.groupsids. Do the mapping.
                        sid = self.groupsids.get(
                            cerebrumusrs[usr].get('primaryGroup_groupname'))
                        # We should not set the primaryGroup to None, so we're
                        # only updating it if we have something proper to set:
                        if sid:
                            sid = sid['Sid'].split('-')[-1]
                            if int(adusrs[usr]['primaryGroupID']) != int(sid):
                                self.logger.debug(
                                    "changing primaryGroupID from %r to %r",
                                    adusrs[usr]['primaryGroupID'],
                                    sid)
                                changes['primaryGroupID'] = sid
                        if 'primaryGroup_groupname' in cerebrumusrs[usr]:
                            del cerebrumusrs[usr]['primaryGroup_groupname']
                        continue

                    # attr exists both places
                    if attr in cerebrumusrs[usr] and attr in adusrs[usr]:
                        if isinstance(cerebrumusrs[usr][attr], (list)):
                            # Multivalued, it is assumed that a
                            # multivalue in cerebrumusrs always is
                            # represented as a list.
                            Mchange = False

                            if (isinstance(adusrs[usr][attr], six.string_types)
                                    or isinstance(adusrs[usr][attr],
                                                  six.integer_types)):
                                # Transform single-value to a list for comp
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
                        continue

                    # attr only in cerebrum, update if not empty
                    if attr in cerebrumusrs[usr]:
                        if cerebrumusrs[usr][attr] != "":
                            changes[attr] = cerebrumusrs[usr][attr]
                        continue

                    # attr only in ad, so clear it
                    if attr in adusrs[usr]:
                        changes[attr] = ''
                        continue

                for acc, value in cereconf.AD_ACCOUNT_CONTROL.items():
                    if acc in cerebrumusrs[usr]:
                        if (acc in adusrs[usr] and
                                adusrs[usr][acc] == cerebrumusrs[usr][acc]):
                            pass
                        else:
                            changes[acc] = cerebrumusrs[usr][acc]
                    else:
                        if acc in adusrs[usr] and adusrs[usr][acc] == value:
                            pass
                        else:
                            changes[acc] = value

                # Submit if any changes.
                if changes:
                    changes['distinguishedName'] = 'CN=%s,%s' % (usr, ou)
                    changes['type'] = 'alter_object'
                # after processing we delete from array.
                del cerebrumusrs[usr]

            else:
                # ac.is_deleted() or ac.is_expired() pluss a small rest of
                # accounts created in AD, but that do not have AD_spread.
                if delete_users:
                    changes['type'] = 'delete_object'
                    changes['distinguishedName'] = (adusrs[usr]
                                                    ['distinguishedName'])
                else:
                    # Disable account.
                    if not adusrs[usr]['ACCOUNTDISABLE']:
                        changes['distinguishedName'] = (
                            adusrs[usr]['distinguishedName'])
                        changes['type'] = 'alter_object'
                        changes['ACCOUNTDISABLE'] = True
                        # commit changes
                        changelist.append(changes)
                        changes = {}
                    # Moving account.
                    if (adusrs[usr]['distinguishedName'] != "CN=%s,%s" %
                            (usr, cereconf.AD_LOST_AND_FOUND)):
                        changes['type'] = 'move_object'
                        changes['distinguishedName'] = (
                            adusrs[usr]['distinguishedName'])
                        changes['OU'] = (
                            "%s" % (cereconf.AD_LOST_AND_FOUND))

            # Finished processing user, register changes if any.
            if changes:
                changelist.append(changes)

        # The remaining items in cerebrumusrs is not in AD, create user.
        for cusr, cdta in cerebrumusrs.items():
            changes = {}
            # New user, create.
            changes = cdta
            changes['type'] = 'create_object'
            changes['sAMAccountName'] = cusr
            changelist.append(changes)

        return changelist

    def get_pwds_from_cl(self, adusrs, dry_run, spread, commit_changes=False):
        cl = CLHandler.CLHandler(self.db)

        # We reverse the set of events, so that if the same account
        # has multiple password changes, only the last will be updated.
        # If we didn't reverse, and if the first password update fails,
        # then this would be retried in the next run, and the next password
        # update(s) will not be rerun afterwards, leaving the user with
        # an older password than the last.
        answer = reversed(cl.get_events('ad', (self.co.account_password,)))
        handled = set()
        for ans in answer:
            confirm = True
            if (ans['change_type_id'] == self.co.account_password
                    and ans['subject_entity'] not in handled):
                handled.add(ans['subject_entity'])
                self.ac.clear()
                self.ac.find(ans['subject_entity'])
                # if usr exists in ad change pwd, else password set when
                # created
                if self.ac.account_name in adusrs:
                    pw = json.loads(ans['change_params'])['password']
                    confirm = self.change_pwd(self.ac.account_name,
                                              pw, dry_run)
                # but for now we dont get the password when user is created so
                # we also check if user is a user with AD-spread and assume
                # these are just created
                elif self.ac.has_spread(self.co.Spread(spread)):
                    pw = json.loads(ans['change_params'])['password']
                    confirm = self.change_pwd(self.ac.account_name,
                                              pw, dry_run)
            else:
                self.logger.debug("unknown change_type_id %i or user already"
                                  " updated", ans['change_type_id'])
            if confirm:
                cl.confirm_event(ans)
        if commit_changes:
            cl.commit_confirmations()
            self.logger.info("Commited changes, updated c_l_handler.")

    def change_pwd(self, uname, pw, dry_run):
        """Change password in AD, return True on success, False on fail"""
        dn = self.server.findObject(uname)
        ret = self.run_cmd('bindObject', dry_run, dn)
        self.logger.debug("Binding %r", ret[0])
        ret = self.run_cmd('setPassword', dry_run, pw)
        if ret[0]:
            self.logger.info('Changed password for %r in domain %r',
                             uname, self.ad_ldap)
            return True
        else:
            # Something went wrong.
            self.logger.error('Failed change password for %r in domain %r',
                              uname, self.ad_ldap)
            return False

    def full_sync(self, delete=False, spread=None, dry_run=True,
                  store_sid=False, pwd_sync=False):

        self.logger.info("Starting user-sync(spread=%r,delete=%r, "
                         "dry_run=%r, store_sid=%r password_sync=%r)",
                         spread, delete, dry_run, store_sid, pwd_sync)

        # Fetch cerebrum data.
        self.logger.info("Fetching cerebrum data...")
        cerebrumdump = self.fetch_cerebrum_data(spread)
        self.logger.info("Fetched %i cerebrum users", len(cerebrumdump))

        # Fetch AD-data.
        self.logger.info("Fetching AD data...")
        addump = self.fetch_ad_data(self.ad_ldap)
        self.logger.info("Fetched %i ad-users", len(addump))

        # compare cerebrum and ad-data.
        self.logger.info("Comparing Cerebrum and AD data...")
        changelist = self.compare(delete, cerebrumdump, addump)
        self.logger.info("Found %i number of user changes", len(changelist))

        # Perform changes.
        self.perform_changes(changelist, dry_run, store_sid)

        # Set passwords from changelog if option enabled
        if pwd_sync:
            self.logger.info("Starting password sync.")
            self.get_pwds_from_cl(addump, dry_run, spread, True)

        # Cleaning up.
        addump = None
        cerebrumdump = None

        # Commiting changes to DB (SID external ID) or not.
        if dry_run:
            self.db.rollback()
        else:
            self.db.commit()

        self.logger.info("Finished user-sync")


##################################################


class ADFullGroupSync(ADutils.ADgroupUtil):

    def __init__(self, *args, **kwargs):
        super(ADFullGroupSync, self).__init__(*args, **kwargs)
        self.ac = Utils.Factory.get('Account')(self.db)
        self.pg = Utils.Factory.get('PosixGroup')(self.db)
        self.pu = Utils.Factory.get('PosixUser')(self.db)

    def fetch_cerebrum_data(self, spread):
        """
        Fetch relevant cerebrum data for groups of the three
        group types that shall be exported to AD. They are
        assigned OU according to group type.

        @rtype: dict
        @return: a dict {grpname: {'adAttrib': 'value'}} for all groups
        of relevant spread. Typical attributes::

        'displayName': String,          # gruppenavn
        'displayNamePrintable' : String # gruppenavn
        'description' : String          # beskrivelse
        """
        #
        # Get groups with spread
        #
        grp_dict = {}
        spread_res = list(
            self.group.search(spread=int(self.co.Spread(spread))))
        for row in spread_res:
            gname = row["name"] + cereconf.AD_GROUP_POSTFIX
            grp_dict[gname] = {
                'description': row["description"],
                'grp_id': row["group_id"],
                'displayName': gname,
                'displayNamePrintable': gname,
            }

        #
        # Posix attributes
        #
        groupid2gid = dict((row['group_id'], row['posix_gid'])
                           for row in self.pg.list_posix_groups())
        groupid2uids = dict()
        for row in self.pu.list_posix_users(filter_expired=True):
            groupid2uids.setdefault(row['gid'], []).append(
                str(row['posix_uid']))
        i = 0
        for gname, gdata in grp_dict.iteritems():
            if gdata['grp_id'] in groupid2gid:
                gdata['gidNumber'] = groupid2gid[gdata['grp_id']]
                gdata['msSFU30Name'] = gname
                gdata['msSFU30NisDomain'] = 'uio'
                gdata['memberUID'] = groupid2uids.get(gdata['grp_id'], ())
                i += 1
        self.logger.debug("Number of groups with posix GID: %d", i)

        i = 0
        for gdata in grp_dict.itervalues():
            if 'gidNumber' not in gdata:
                i += 1
        self.logger.debug("Number of groups without posix GID: %d", i)

        return grp_dict

    def fetch_ad_data(self):
        """Get list of groups with  attributes from AD

        Dict with data from AD with sAMAccountName as index:
        'displayName': String,          # gruppenavn
        'displayNamePrintable' : String # gruppenavn
        'description' : String          # beskrivelse
        'distinguishedName' : String    # AD-LDAP path to object

        @returm ad_dict : group name -> group info mapping
        @type ad_dict : dict
        """

        self.server.setGroupAttributes(cereconf.AD_GRP_ATTRIBUTES)
        search_ou = self.ad_ldap
        self.logger.debug("Search OU %r for groups, fetch: %r",
                          search_ou, cereconf.AD_GRP_ATTRIBUTES)
        ad_dict = self.server.listObjects('group', True, search_ou)
        if ad_dict:
            for grp in ad_dict:
                part = ad_dict[grp]['distinguishedName'].split(",", 1)
                if part[1] and part[0].find("CN=") > -1:
                    ad_dict[grp]['OU'] = part[1]
                else:
                    ad_dict[grp]['OU'] = self.get_default_ou()

                # descritpion is list from AD.
                # Only want to check first string with ours
                if 'description' in ad_dict[grp]:
                    if isinstance(ad_dict[grp]['description'], (list)):
                        ad_dict[grp]['description'] = \
                            ad_dict[grp]['description'][0]
        else:
            ad_dict = {}
        return ad_dict

    def delete_and_filter(self,
                          ad_dict, cerebrum_dict, dry_run, delete_groups):
        """Filter out groups in AD that shall not be synced from Cerebrum.

        Goes through the dict of the groups in AD, and checks if it is
        a group that shall be synced from cerebrum. If it is not we remove
        it from the dict so we will pay no attention to the group when we sync,
        but only after checking if it is in our OU. If it is we delete it.

        :param dict ad_dict: account_id -> account info mapping
        :param dict cerebrum_dict: account_id -> account info mapping
        :param Flag delete_users: Delete or not unwanted groups
        :param Falg dry_run: Dry run, don't actually delete.
        """

        for grp_name, v in ad_dict.items():
            if grp_name not in cerebrum_dict:
                if self.ad_ldap in ad_dict[grp_name]['OU']:
                    if is_blacklisted(ad_dict[grp_name]['distinguishedName']):
                        self.logger.debug(
                            "%r (dn=%r) in AD_DO_NOT_TOUCH, skipping",
                            grp_name,
                            ad_dict[grp_name]['distinguishedName'])
                    # an unknown group in OUs under our control
                    # and not i DO_NOT_TOUCH -> delete
                    elif not delete_groups:
                        self.logger.debug("delete is False. Don't delete"
                                          " group: %r", grp_name)
                    else:
                        self.logger.info(
                            "delete_groups=%r, deleting group %r",
                            delete_groups, grp_name)
                        self.run_cmd(
                            'bindObject', dry_run,
                            ad_dict[grp_name]['distinguishedName'])
                        ret = self.run_cmd('deleteObject', dry_run)
                        if not ret[0]:
                            self.logger.warning(
                                "Delete on %r failed: %r",
                                ad_dict[grp_name]['distinguishedName'],
                                ret)
                # does not concern us (anymore), delete from dict.
                del ad_dict[grp_name]

    def get_default_ou(self):
        """
        Return default OU for groups.
        """
        return "%s" % (cereconf.AD_GROUP_OU)

    def sync_group_info(self, ad_dict, cerebrum_dict, dry_run):
        """ Sync group info with AD

        Check if any values about groups other than group members
        should be updated in AD

        @param ad_dict : account_id -> account info mapping
        @type ad_dict : dict
        @param cerebrum_dict : account_id -> account info mapping
        @type cerebrum_dict : dict
        @param dry_run: Flag
        """
        # Keys in dict from cerebrum must match fields to be populated in AD.
        # Already removed groups from ad_dict not i cerebrum_dict
        changelist = []

        for grp in cerebrum_dict:
            changes = {}
            if grp in ad_dict:
                # group in both places, we want to check correct data

                # Checking for correct OU.
                ou = self.get_default_ou()
                if ad_dict[grp]['OU'] != ou:
                    changes['type'] = 'move_object'
                    changes['OU'] = ou
                    changes['distinguishedName'] = \
                        ad_dict[grp]['distinguishedName']
                    # Submit list and clean.
                    changelist.append(changes)
                    changes = {}

                # Comparing group info
                for attr in cereconf.AD_GRP_ATTRIBUTES:
                    cere_attr = cerebrum_dict[grp].get(attr, None)
                    ad_attr = ad_dict[grp].get(attr, None)

                    if attr == 'memberUID':
                        # Ignore updating when Cerebrum has an empty list and
                        # AD has None.
                        # TODO: Find out if this could be used for all
                        # attributes.
                        if (not cere_attr and not ad_attr):
                            continue
                        if cere_attr != ad_attr:
                            self.logger.debug("Compare memberUID c=%r, ad=%r",
                                              cere_attr, ad_attr)
                    if attr == 'member':
                        pass
                    elif attr in cerebrum_dict[grp] and attr in ad_dict[grp]:
                        if isinstance(cerebrum_dict[grp][attr], (list)):
                            # Multivalued, it is assumed that a
                            # multivalue in cerebrumusrs always is
                            # represented as a list.
                            Mchange = False

                            if (isinstance(ad_dict[grp][attr],
                                           six.string_types)
                                    or isinstance(ad_dict[grp][attr],
                                                  six.integer_types)):
                                # Transform single-value to a list for comp.
                                val2list = []
                                val2list.append(ad_dict[grp][attr])
                                ad_dict[grp][attr] = val2list

                            for val in cerebrum_dict[grp][attr]:
                                if val not in ad_dict[grp][attr]:
                                    Mchange = True

                            if Mchange:
                                changes[attr] = cerebrum_dict[grp][attr]
                        else:
                            if ad_dict[grp][attr] != cerebrum_dict[grp][attr]:
                                changes[attr] = cerebrum_dict[grp][attr]
                    else:
                        if attr in cerebrum_dict[grp]:
                            # A blank value in cerebrum and <not
                            # set> in AD -> do nothing.
                            if cerebrum_dict[grp][attr] != "":
                                changes[attr] = cerebrum_dict[grp][attr]
                        elif attr in ad_dict[grp]:
                            # Delete value
                            changes[attr] = ''

                # Submit if any changes.
                if len(changes):
                    changes['distinguishedName'] = 'CN=%s,%s' % (grp, ou)
                    changes['type'] = 'alter_object'
                    changelist.append(changes)
                    changes = {}
            else:
                # The remaining items in cerebrum_dict is not in AD, create
                # group
                changes = {}
                changes = copy.copy(cerebrum_dict[grp])
                changes['type'] = 'create_object'
                changes['sAMAccountName'] = grp
                changelist.append(changes)

        return changelist

    def write_sid(self, objtype, crbname, sid, dry_run):
        """
        Store AD object SID to cerebrum database for given group

        @param objtype: type of AD object
        @type objtype: String
        @param name: group name
        @type name: String
        @param sid: SID from AD
        @type sid: String
        """
        # TBD: Check if we create a new object for a entity that already
        # have an externalid_groupsid defined in the db and delete old?
        self.logger.info("Writing SID for %r %r to database",
                         objtype, crbname)
        if objtype == 'group' and not dry_run:
            self.group.clear()
            self.group.find_by_name(crbname)
            self.group.affect_external_id(self.co.system_ad,
                                          self.co.externalid_groupsid)
            self.group.populate_external_id(self.co.system_ad,
                                            self.co.externalid_groupsid, sid)
            self.group.write_db()

    def perform_changes(self, changelist, dry_run, store_sid):
        """
        Binds to AD object and perform changes such as
        updates to attributes or move or deleting.

        @param changelist: group name -> changes mapping
        @type changelist: array of dict
        @param dry_run: Flag
        @param store_sid: Flag
        """
        for chg in changelist:
            self.logger.debug("Process change: %s", repr(chg))
            if chg['type'] == 'create_object':
                self.create_object(chg, dry_run, store_sid)
            else:
                ret = self.run_cmd('bindObject', dry_run,
                                   chg['distinguishedName'])
                if not ret[0]:
                    self.logger.warning("bindObject on %r failed: %r",
                                        chg['distinguishedName'], ret)
                else:
                    exec('self.' + chg['type'] + '(chg, dry_run)')

    def create_object(self, chg, dry_run, store_sid):
        """
        Creates AD group object and populates given attributes

        @param chg: group_name -> group info mapping
        @type chg: dict
        @param dry_run: Flag
        @param store_sid: Flag
        """
        # RH 2011-02-02: groupType should just be set for new groups
        chg['groupType'] = cereconf.AD_GROUP_TYPE
        ou = chg.get("OU", self.get_default_ou())
        self.logger.info('Create group %r', chg)
        ret = self.run_cmd('createObject', dry_run, 'Group', ou,
                           chg['sAMAccountName'])
        if not ret[0]:
            self.logger.warning("create group %r failed: %r",
                                chg['sAMAccountName'], ret[1])
        elif not dry_run:
            if store_sid:
                self.write_sid('group', chg['crb_gname'], ret[2], dry_run)
            del chg['type']
            gname = ''
            if 'distinguishedName' in chg:
                del chg['distinguishedName']
            if 'sAMAccountName' in chg:
                gname = chg['sAMAccountName']
                del chg['sAMAccountName']
            ret = self.server.putGroupProperties(chg)
            if not ret[0]:
                self.logger.warning("putproperties on %r failed: %r",
                                    gname, ret)
            else:
                ret = self.run_cmd('setObject', dry_run)
                if not ret[0]:
                    self.logger.warning("setObject on %r failed: %r",
                                        gname, ret)

    def alter_object(self, chg, dry_run):
        """
        Binds to AD group objects and updates given attributes

        @param chg: group_name -> group info mapping
        @type chg: dict
        @param dry_run: Flag
        """
        distName = chg['distinguishedName']
        # Already binded
        del chg['type']
        del chg['distinguishedName']

        # ret = self.run_cmd('putGroupProperties', dry_run, chg)
        # run_cmd in ADutilMixIn.py not written for group updates
        if not dry_run:
            ret = self.server.putGroupProperties(chg)
        else:
            ret = (True, 'putGroupProperties')
        if not ret[0]:
            self.logger.warning("putGroupProperties on %r failed: %r",
                                distName, ret)
        else:
            ret = self.run_cmd('setObject', dry_run)
            if not ret[0]:
                self.logger.warning("setObject on %r failed: %r",
                                    distName, ret)

    def compare_members(self, cerebrum_dict, ad_dict, group_spread,
                        user_spread, dry_run, sendDN_boost):
        """
        Update group memberships in AD by comparing memberlists for groups
        in AD and Cerebrum.

        @param cerebrum_dict : group_name -> group info mapping
        @type cerebrum_dict : dict
        @param ad_dict : group_name -> group info mapping
        @type ad_dict : dict
        @param spread: ad group spread for a domain
        @type spread: _SpreadCode
        @param user_spread: ad account spread for a domain
        @type user_spread: _SpreadCode
        @param dry_run: Flag
        @param sendDN_boost: Flag to determine if we should use fully qualified
                             domain named for users and groups
        """
        def get_medlemmer(gruppe_id, add_users):
            """ Help function to gather group members. Groups without AD-spread
            that are member, either directly or in-directly will have their
            members with ad-spread added as members (so-called flattening).
            """
            if add_users:
                for usr in (self.group.search_members(
                        group_id=gruppe_id, member_type=self.co.entity_account,
                        member_spread=int(self.co.Spread(user_spread)))):
                    user_members.add(usr["member_id"])
                # persons doesn't have AD-spread, so we have to search for them
                # explicitly:
                for usr in self.group.search_members(
                        group_id=gruppe_id,
                        member_type=self.co.entity_person):
                    primary = pe2primary.get(usr['member_id'], None)
                    if primary:
                        user_members.add(primary)
                    else:
                        self.logger.debug("Person %r has no primary account",
                                          usr['member_id'])

            for gruppe in (self.group.search_members(
                    group_id=gruppe_id,
                    member_type=self.co.entity_group)):
                # to avoid loops where groups are members of each-other
                if gruppe["member_id"] in group_members:
                    continue
                if gruppe["member_id"] in groups_with_ad_spread:
                    if add_users:
                        group_members.add(gruppe["member_id"])
                    get_medlemmer(gruppe["member_id"], False)
                else:
                    get_medlemmer(gruppe["member_id"], True)

        entity2name = dict([(x["entity_id"], x["entity_name"])
                            for x in self.group.list_names(
                                    self.co.account_namespace)])
        entity2name.update([(x["entity_id"], x["entity_name"])
                            for x in self.group.list_names(
                                    self.co.group_namespace)])
        pe2primary = dict((r['person_id'], r['account_id'])
                          for r in self.ac.list_accounts_by_type(
                                  primary_only=True,
                                  account_spread=self.co.Spread(user_spread)))
        # TBD: Note that if a person's primary account does not have the
        # user_spread, the first account with the user_spread is returned. This
        # means that it's not necessarily the primary account that is used, but
        # the account with the most priority and a user_spread. Is this correct
        # behaviour?

        groups_with_ad_spread = set(
            int(x['group_id']) for x in self.group.search(
                spread=int(self.co.Spread(group_spread))))

        for grp in cerebrum_dict:
            if 'grp_id' in cerebrum_dict[grp]:
                grp_id = cerebrum_dict[grp]['grp_id']

                user_members = set()
                group_members = set()
                members = list()

                # get members and flatten groups without ad-spread recurseivly
                get_medlemmer(grp_id, True)

                for user_id in user_members:
                    if user_id not in entity2name:
                        self.logger.debug("Missing name for account id=%r",
                                          user_id)
                        continue
                    if sendDN_boost:
                        members.append(("CN=%s,%s" % (entity2name[user_id],
                                                      cereconf.AD_USER_OU)))
                    else:
                        members.append(entity2name[user_id])

                for group_id in group_members:
                    if group_id not in entity2name:
                        self.logger.debug("Missing name for group id=%r",
                                          group_id)
                        continue
                    if sendDN_boost:
                        members.append(
                            ("CN=%s%s,%s" % (entity2name[group_id],
                                             cereconf.AD_GROUP_POSTFIX,
                                             cereconf.AD_GROUP_OU)))
                    else:
                        members.append("%s%s" % (entity2name[group_id],
                                                 cereconf.AD_GROUP_POSTFIX))

                if sendDN_boost:
                    members_in_ad = ad_dict.get(grp, {}).get("member", [])
                else:
                    # To extract the username/groupname from the FQDN
                    # (CN=username,OU=...etc)
                    members_in_ad = [x.split(",")[0].split("=")[1] for x in
                                     ad_dict.get(grp, {}).get("member", [])]

                # If number of members returned from AD is zero and the group
                # has members in cerebrum we do a full sync on this group. It
                # is either an empty group that gets members or it is a group
                # with more members than the 1500 maxValRange limit in AD (thus
                # AD returns no members at all)
                if not members_in_ad and members:
                    dn = self.server.findObject(grp)
                    if not dn:
                        self.logger.warning(
                            "Not able to bind to group %r in AD", grp)
                    elif dry_run:
                        self.logger.debug("Dryrun: don't sync members: Would "
                                          "have done fullsync of group.")
                    else:
                        self.server.bindObject(dn)
                        self.logger.info("Too many members(%i) or empty AD "
                                         " group. Doing fullsync of"
                                         " memberships for group %r",
                                         len(members), grp)
                        res = self.server.syncMembers(members,
                                                      bool(sendDN_boost),
                                                      False)
                        if not res[0]:
                            self.logger.warning("syncMembers %r failed for:%r",
                                                dn, res[1:])
                    continue

                # Comparing members in cerebrum and ad
                members_add = [userdn for userdn in members
                               if userdn not in members_in_ad]
                members_remove = [userdn for userdn in members_in_ad
                                  if userdn not in members]

                if members_add or members_remove:
                    dn = self.server.findObject(grp)
                    if not dn:
                        self.logger.warning(
                            "Not able to bind to group %r in AD", grp)
                    elif dry_run:
                        self.logger.debug("Dryrun: don't sync members for %r",
                                          grp)
                    else:
                        self.server.bindObject(dn)
                        if members_add:
                            self.logger.info("Add %d members to group %r: %r…",
                                             len(members_add), grp,
                                             members_add[:50])
                            res = self.server.addMembers(members_add,
                                                         sendDN_boost)
                            if not res[0]:
                                self.logger.warning(
                                    "Adding members for group %r failed: %r",
                                    dn, res[1])
                        if members_remove:
                            self.logger.info(
                                "Removing members from group %r (%r)",
                                grp, members_remove)
                            res = self.server.removeMembers(
                                members_remove, sendDN_boost)
                            if not res[0]:
                                self.logger.warning(
                                    "Removing members for group %r failed: %r",
                                    dn, res[1])
            else:
                self.logger.warning(
                    "Group %r has no group_id. Not syncing members.", grp)

    def get_group_members(self, entity2name, group_spread, user_spread,
                          sendDN_boost, grp_id):
        members = list()
        account_type = self.co.entity_account
        group_type = self.co.entity_group

        for member in self.group.search_members(
                group_id=grp_id,
                member_spread=(int(self.co.Spread(user_spread)),
                               int(self.co.Spread(group_spread)))):
            member_id = member["member_id"]

            if member['member_type'] == account_type:
                try:
                    if sendDN_boost:
                        members.append(("CN={},{}".format(
                            entity2name[member_id],
                            cereconf.AD_USER_OU)))
                    else:
                        members.append(entity2name[member_id])
                    self.logger.debug(
                        "Try to sync member account id=%r, name=%r",
                        member_id, entity2name[member_id])
                except KeyError:
                    self.logger.debug("Missing name for account id=%r",
                                      member_id)
                    continue

            elif member['member_type'] == group_type:
                try:
                    if sendDN_boost:
                        members.append(("CN={}{},{}".format(
                                entity2name[member_id],
                                cereconf.AD_GROUP_POSTFIX,
                                cereconf.AD_GROUP_OU)))
                    else:
                        members.append('{}{}'.format(
                            entity2name[member_id],
                            cereconf.AD_GROUP_POSTFIX))
                    self.logger.debug(
                        "Try to sync member group id=%r, name=%r",
                        member_id, entity2name[member_id])
                except KeyError:
                    self.logger.debug("Missing name for group id=%r",
                                      member_id)
                    continue
        return members

    def sync_group_members(self, cerebrum_dict, group_spread, user_spread,
                           dry_run, sendDN_boost):
        """
        Update group memberships in AD using an alternative method to the
        compare_memebers function. Here we do not read status in AD and
        instead gives AD a full current list of members for all groups.
        This method can be used if the --full_membersync option is enabled.

        @param cerebrum_dict : group_name -> group info mapping
        @type cerebrum_dict : dict
        @param spread: ad group spread for a domain
        @type spread: _SpreadCode
        @param user_spread: ad account spread for a domain
        @type user_spread: _SpreadCode
        @param dry_run: Flag
        """
        # To reduce traffic, we send current list of groupmembers to AD, and
        # the server ensures that each group have correct members.

        entity2name = dict([(x["entity_id"], x["entity_name"]) for x in
                           self.group.list_names(self.co.account_namespace)])
        entity2name.update([(x["entity_id"], x["entity_name"]) for x in
                           self.group.list_names(self.co.group_namespace)])

        for grp in cerebrum_dict:
            if 'grp_id' in cerebrum_dict[grp]:
                grp_name = grp.replace(cereconf.AD_GROUP_POSTFIX, "")
                grp_id = cerebrum_dict[grp]['grp_id']

                # TODO: How to treat quarantined users???, some exist in AD,
                # others do not. They generate errors when not in AD. We still
                # want to update group membership if in AD.
                members = self.get_group_members(entity2name, group_spread,
                                                 user_spread, sendDN_boost,
                                                 grp_id)

                dn = self.server.findObject(
                    '%s%s' % (grp_name, cereconf.AD_GROUP_POSTFIX))
                if not dn:
                    self.logger.debug("unknown group: %s%s",
                                      grp_name, cereconf.AD_GROUP_POSTFIX)
                elif dry_run:
                    self.logger.debug("Dryrun: don't sync members")
                else:
                    self.server.bindObject(dn)
                    if sendDN_boost:
                        res = self.server.syncMembers(members, True, False)
                    else:
                        res = self.server.syncMembers(members, False, False)
                    if not res[0]:
                        self.logger.warning("syncMembers %r failed for:%r",
                                            dn, res[1:])
            else:
                self.logger.warning(
                    "Group %r has no group_id. Not syncing members.", grp)

    def full_sync(self, delete=False, dry_run=True, store_sid=False,
                  user_spread=None, group_spread=None, sendDN_boost=False,
                  full_membersync=False):

        self.logger.info("Starting group-sync(group_spread=%r, "
                         "user_spread=%r, delete=%r, dry_run=%r, "
                         "store_sid=%r, sendDN_boost=%r, "
                         "full_membersync=%r)",
                         group_spread, user_spread, delete, dry_run, store_sid,
                         sendDN_boost, full_membersync)

        # Fetch cerebrum data.
        self.logger.debug("Fetching cerebrum data...")
        cerebrumdump = self.fetch_cerebrum_data(group_spread)
        self.logger.debug("Fetched %i groups with spread %r",
                          len(cerebrumdump), group_spread)

        # Fetch AD data
        self.logger.debug("Fetching AD data...")
        addump = self.fetch_ad_data()
        self.logger.debug("Fetched %i ad-groups", len(addump))

        # Filter AD-list
        self.delete_and_filter(addump, cerebrumdump, dry_run, delete)
        self.logger.debug("Comparing %i ad-groups after filtering",
                          len(addump))

        # Compare groups and attributes (not members)
        changelist = self.sync_group_info(addump, cerebrumdump, dry_run)
        self.logger.debug("Found %i number of group changes", len(changelist))

        # Perform changes
        self.perform_changes(changelist, dry_run, store_sid)

        # Syncing group members
        if full_membersync:
            self.logger.info(
                "Starting sync of group members using full member sync")
            self.sync_group_members(cerebrumdump, group_spread, user_spread,
                                    dry_run, sendDN_boost)
        else:
            self.logger.info("Starting sync of group members using"
                             " differential member sync")
            self.compare_members(cerebrumdump, addump, group_spread,
                                 user_spread, dry_run, sendDN_boost)

        # Cleaning up.
        addump = None
        cerebrumdump = None

        # Commiting changes to DB (SID external ID) or not.
        if dry_run:
            self.db.rollback()
        else:
            self.db.commit()

        self.logger.info("Finished group-sync")
