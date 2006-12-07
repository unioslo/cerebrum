# -*- coding: iso-8859-1 -*-

from Cerebrum.modules.no.hiof import ADutilMixIn
from Cerebrum.Utils import Factory

class ADFullUserSync(ADutilMixIn.ADuserUtil):
    def _filter_quarantines(self, user_dict):
        def apply_quarantines(entity_id, quarantines):
            if not user_dict.has_key(entity_id):
                return
            qh = QuarantineHandler.QuarantineHandler(db, quarantines)
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
        #ac = Factory.get('Account')(db)
        tmp_ret = {}
        for row in self.ac.list_account_home(
            home_spread=disk_spread, account_spread=spread, filter_expired=True, include_nohome=True):
            
            tmp_ret[int(row['account_id'])] = {
                'homeDrive': 'N:',
                'homeDirectory': row['home'],
                'TEMPownerId': row['owner_id'],  # TODO: API leser den ikke
                'TEMPuname': row['entity_name'],
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
                source_system = const.system_cached,
                name_type     = [const.name_first,
                                 const.name_last]):
            pid2names.setdefault(int(row['person_id']), {})[
                int(row['name_variant'])] = row['name,']
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
                v['profilePath'] = row['strval']
        for row in self.ac.list_traits(self.co.trait_ad_account_ou):
            v = tmp_ret.get(int(row['entity_id']))
            if v:
                v['OU'] = row['strval']

        #
        # Set mail adresses
        #
        self._fetch_primary_mail_addresses(tmp_ret)

        ret = {}
        for k, v in tmp_ret.items():
            ret[v['TEMPuname']] = v
            del(v['TEMPuname'])
            del(v['TEMPownerId'])
        return ret
