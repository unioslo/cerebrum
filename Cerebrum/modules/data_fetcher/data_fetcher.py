from Cerebrum import Utils, Errors
from Cerebrum import QuarantineHandler


class CerebrumDataFetcher(object):
    def __init__(self, **kwargs):
        self.db = kwargs.get('db', Utils.Factory.get('Database')())
        self.ac = kwargs.get('ac', Utils.Factory.get('Account')(self.db))
        self.pe = kwargs.get('pe', Utils.Factory.get('Person')(self.db))
        self.gr = kwargs.get('pe', Utils.Factory.get('Group')(self.db))
        self.co = kwargs.get('co', Utils.Factory.get('Constants')(self.db))
        self.pg = kwargs.get('pg', Utils.Factory.get('PosixGroup')(self.db))
        self.pu = kwargs.get('pu', Utils.Factory.get('PosixUser')(self.db))
        self.di = kwargs.get('di', Utils.Factory.get('Disk')(self.db))
        self.ho = kwargs.get('ho', Utils.Factory.get('Host')(self.db))

    def get_all_accounts_data(self, spread=None):
        """Builds a dict account_id: {owner_id, username} for accounts with
        the specified spread."""
        return {acc['account_id']: {'owner_id': acc['owner_id'],
                                    'username': acc['name'],
                                    'entity_id': acc['account_id'],
                                    'entity_type': 'account'}
                for acc in list(self.ac.search(spread=spread))}

    def get_all_groups_data(self, spread=None, postfix=''):
        grp_dict = {}
        spread_res = list(self.gr.search(spread=int(self.co.Spread(spread))))
        for row in spread_res:
            gname = unicode(row["name"],'ISO-8859-1') + postfix
            grp_dict[gname] = {
                'description' : unicode(row["description"], 'ISO-8859-1'),
                'grp_id' : row["group_id"],
                'displayName' : gname,
                'displayNamePrintable' : gname,
            }

        return {[''.join(unicode(row["name"],'ISO-8859-1'), postfix)]: {
                'description': unicode(row["description"], 'ISO-8859-1'),
                'grp_id': grp['group_id'],
                'displayName': ''.join(unicode(row["name"],'ISO-8859-1'), postfix),
                'displayNamePrintable': ''.join(unicode(row["name"],'ISO-8859-1'),
                                                postfix)
                }
                for grp in list(self.gr.search(spread=int(self.co.Spread(spread))))
        }

    def get_quarantine_data(self, account_ids):
        """Takes a list of account ids, and returns a dict
        account_id -> quarantine_action."""
        all_quarantines = list(self.ac.list_entity_quarantines(
            only_active=True,
            entity_ids=account_ids
        ))

        # Gather up all quarantines for each account
        quarantined_accounts = {}
        for q in all_quarantines:
            quarantined_accounts.setdefault(q['entity_id'], [])
            quarantined_accounts[q['entity_id']].append(q['quarantine_type'])

        quarantine_data = {}
        for acc_id, quarantines in quarantined_accounts.items():
            qh = QuarantineHandler.QuarantineHandler(self.db, quarantines)
            if qh.should_skip():
                quarantine_data[acc_id] = 'skip'
            elif qh.is_locked():
                quarantine_data[acc_id] = 'lock'
            else:
                quarantine_data[acc_id] = 'none'
        return quarantine_data

    def get_all_persons_names(self):
        """Returns a dict person_id -> first_name & last_name using
        system_cached as source_system."""
        names = {}
        for row in self.pe.search_person_names(
                name_variant=[self.co.name_first,
                              self.co.name_last],
                source_system=self.co.system_cached):
            names.setdefault(int(row['person_id']), {})
            if int(self.co.name_first) == int(row['name_variant']):
                names[int(row['person_id'])]['first_name'] = row['name']
            elif int(self.co.name_last) == int(row['name_variant']):
                names[int(row['person_id'])]['last_name'] = row['name']
        return names

    def get_all_posix_group_gids(self):
        return {group['group_id']: group['posix_gid']
                for group in self.pg.list_posix_groups()}

    def get_all_posix_accounts_data(self, spread=None):
        return {acc['account_id']: {'posix_uid': acc['posix_uid'],
                                    'posix_group_id': acc['gid'],
                                    'gecos': acc['gecos']}
                for acc in self.pu.list_posix_users(spread=spread,
                                                    filter_expired=True)}

    def get_all_ad_group_names(self, spread=None):
        return {group['group_id']: group['name']
                for group in self.pg.search(spread=spread)}

    def get_all_email_addrs(self):
        """Returns a dict of uname -> primary email mappings."""
        return self.ac.getdict_uname2mailaddr(filter_expired=True,
                                              primary_only=True)

    def get_all_hosts(self):
        return {host['host_id']: host['name']
                for host in self.ho.search()}

    def get_all_posix_data(self, spread=None):
        account_data = self.get_all_posix_accounts_data(spread)
        grp_gids = self.get_all_posix_group_gids()
        grp_names = self.get_all_ad_group_names(spread)
        posix_data = {}
        for acc_id, acc_data in account_data.items():
            posix_data[acc_id] = dict(acc_data)
            posix_data[acc_id].update(
                {'posix_gid': grp_gids.get(acc_data['posix_group_id']),
                 'posix_group_name': grp_names.get(acc_data['posix_group_id'])}
            )
        return posix_data

    def get_all_accounts_homedir_data(self, spread=None):
        host_data = self.get_all_hosts()
        return {
            home['account_id']: {'home_host': host_data[home['host_id']],
                                 'home_path': home['path']}
            for home in self.ac.list_account_home(
            account_spread=spread
        )
            if home['host_id'] and home['host_id'] in host_data
        }

    def get_account_basic_info(self, account_id):
        self.ac.clear()
        try:
            self.ac.find(account_id)
        except Errors.NotFoundError:
            return None
        if not self.ac.has_spread(self.account_spread):
            return None
        return {'owner_id': self.ac.owner_id,
                'entity_id': account_id,
                'entity_type': 'account',
                'username': self.ac.account_name}

    def get_account_id_by_username(self, username):
        self.ac.clear()
        try:
            self.ac.find_by_name(username)
        except Errors.NotFoundError:
            return None
        return int(self.ac.entity_id)

    def get_person_names(self, person_id):
        self.pe.clear()
        try:
            self.pe.find(person_id)
        except Errors.NotFoundError:
            return None
        return {'first_name': self.pe.get_name(self.co.system_cached,
                                               self.co.name_first),
                'last_name': self.pe.get_name(self.co.system_cached,
                                              self.co.name_last)}

    def get_posix_data(self, account_id):
        self.pu.clear()
        self.pg.clear()
        try:
            self.pu.find(account_id)
            self.pg.find(self.pu.gid_id)
            return {'posix_uid': self.pu.posix_uid,
                    'gecos': self.pu.gecos,
                    'posix_gid': self.pg.posix_gid,
                    'posix_group_name': self.pg.group_name}
        except Errors.NotFoundError:
            return None

    def get_homedir_data(self, account_id):
        self.ac.clear()
        try:
            self.ac.find(account_id)
        except Errors.NotFoundError:
            return None
        homes = self.ac.get_homes()
        if not homes:
            return None
        home = None
        for h in homes:
            if h['disk_id']:
                home = h
                break
        if home is None:
            return None
        self.di.clear()
        self.di.find(home['disk_id'])
        self.ho.clear()
        self.ho.find(self.di.host_id)
        return {'home_path': self.ac.get_homepath(home['spread']),
                'host_name': self.ho.name}

    def get_email_addr(self, account_id):
        """Get the primary email address of an account."""
        try:
            self.ac.clear()
            self.ac.find(account_id)
            mail_addr = self.ac.get_primary_mailaddress()
            return mail_addr
        except Errors.NotFoundError:
            return None

