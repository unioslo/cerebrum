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

    @staticmethod
    def build_row_dict(row, keys=None):
        """
        Builds a dict from a Cerebrum db-row. Will only use the keys (and
        values) if a list of keys are passed, otherwise the entire row will
        be used.
        @param row: Cerebrum db-row
        @param keys: list
        @return: dict
        """
        row_dict = {}
        if keys is not None:
            for key in keys:
                row_dict.update({key: row[key]})
        else:
            for key in row.keys():
                row_dict.update({key: row[key]})
        return row_dict

    def build_dict_from_row_list(self, row_list, key_attr, keys=None):
        """
        Builds a dict from a list of Cerebrum db-rows, using row[key_attr]
        as keys, and setting the specified keys (and corresponding values)
        from each row as values.
        If no keys are specified, all the keys/values in the row are used.
        @param row_list: list
        @param key_attr: any valid dict-key value
        @param keys: a list of row-keys to use as values.
        @return: dict
        """
        rows_dict = {}
        for row in row_list:
            row_dict = self.build_row_dict(row, keys)
            rows_dict[row[key_attr]] = row_dict
        return rows_dict

    def get_all_account_rows(self, key_attr='account_id',
                             keys=None, spread=None):
        """Builds a dict account[key_attr]: account, filtering on a given
        spread if it is passed."""
        account_rows = list(self.ac.search(spread=spread))
        return self.build_dict_from_row_list(account_rows, key_attr, keys)

    def get_all_groups_data(self, key_attr='group_id', keys=None, spread=None):
        """Builds a dict group[key_attr]: group, filtering on a given
        spread if it is passed."""
        group_rows = list(self.gr.search(spread=spread))
        return self.build_dict_from_row_list(group_rows, key_attr, keys)

    def get_accounts_quarantine_data(self,
                                     account_ids=None,
                                     only_active=True):
        """
        Builds a dict: account_id -> quarantine_action, filtering on
        account IDs in account_ids if it is passed.
        @param account_ids: list of account_ids
        @param only_active: boolean
        @return: dict
        """
        all_quarantines = list(self.ac.list_entity_quarantines(
            only_active=only_active,
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

    def get_all_posix_group_data(self, key_attr='group_id', keys=None):
        posix_group_rows = self.pg.list_posix_groups()
        return self.build_dict_from_row_list(posix_group_rows, key_attr, keys)

    def get_all_posix_accounts_rows(self, spread=None,
                                    key_attr='account_id', keys=None):
        posix_users_rows = self.pu.list_posix_users(spread=spread,
                                                    filter_expired=True)
        return self.build_dict_from_row_list(posix_users_rows, key_attr, keys)

    def get_all_posix_group_rows(self, spread=None, key_attr='group_id', keys=None):
        pg_rows = self.pg.search(spread=spread)
        return self.build_dict_from_row_list(pg_rows, key_attr, keys)

    def get_all_email_addrs(self):
        """Returns a dict of uname -> primary email mappings."""
        return self.ac.getdict_uname2mailaddr(filter_expired=True,
                                              primary_only=True)

    def get_all_host_rows(self, key_attr='host_id', keys=None):
        hosts_rows = self.ho.search()
        return self.build_dict_from_row_list(hosts_rows, key_attr, keys)

    def get_account_id_by_username(self, username):
        """Get the entity_id of an account by username."""
        self.ac.clear()
        try:
            self.ac.find_by_name(username)
        except Errors.NotFoundError:
            return None
        return int(self.ac.entity_id)

    def get_email_addr(self, account_id):
        """Get the primary email address of an account."""
        try:
            self.ac.clear()
            self.ac.find(account_id)
            mail_addr = self.ac.get_primary_mailaddress()
            return mail_addr
        except Errors.NotFoundError:
            return None
