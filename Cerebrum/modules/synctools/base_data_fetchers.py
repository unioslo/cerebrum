# -*- coding: utf-8 -*-
import collections
from Cerebrum import Utils, Errors
from Cerebrum import QuarantineHandler


def build_row_dict(row, keys=None):
    """
    Builds a dict from a Cerebrum db-row. Will only use the keys (and
    values) if a list of keys are passed, otherwise the entire row will
    be used.
    @param row: Cerebrum db-row
    @param keys: list
    @return: dict
    """
    if keys is not None:
        row_dict = {}
        for key in keys:
            row_dict.update({key: row[key]})
        return row_dict
    else:
        return row.dict()


def build_dict_from_row_list(rows, key_attr, keys=None):
    """
    Builds a dict from a list of Cerebrum db-rows, using row[key_attr]
    as keys, and setting the specified keys (and corresponding values)
    from each row as values.
    If no keys are specified, all the keys/values in the row are used.
    @param rows: list
    @param key_attr: any valid dict-key value
    @param keys: a list of row-keys to use as values.
    @return: dict
    """
    rows_dict = {}
    for row in rows:
        row_dict = build_row_dict(row, keys)
        rows_dict[row[key_attr]] = row_dict
    return rows_dict


def build_concatenated_dict_from_row_list(row_list, key_attr, keys=None):
    concat_dict = dict()
    for row in row_list:
        if keys is None:
            values = row
        else:
            values = {key: row[key] for key in keys}
        if row[key_attr] not in concat_dict:
            concat_dict[row[key_attr]] = [values]
        else:
            concat_dict[row[key_attr]].append(values)
    return concat_dict


def build_dict_list_from_row_list(row_list, key_attr, keys):
    """
    Builds a dict with lists as values from a list of Cerebrum db-rows,
    using row[key_attr] as keys, and keys as values.
    @param row_list: iterable
    @param key_attr: any valid dict-key value
    @param keys: a list of row-keys to use as values
    @return: dict of lists
    """
    r = collections.defaultdict(list)
    for row in row_list:
        r[row[key_attr]].extend([row[attr] for attr in keys])
    return r


def get_all_account_rows(db, key_attr='account_id',
                         keys=None, spread=None):
    """Builds a dict account[key_attr]: account, filtering on a given
    spread if it is passed."""
    ac = Utils.Factory.get('Account')(db)
    account_rows = list(ac.search(spread=spread))
    return build_dict_from_row_list(account_rows, key_attr, keys)


def get_all_groups_data(db, key_attr='group_id', keys=None, spread=None):
    """Builds a dict group[key_attr]: group, filtering on a given
    spread if it is passed."""
    gr = Utils.Factory.get('Group')(db)
    group_rows = list(gr.search(spread=spread))
    return build_dict_from_row_list(group_rows, key_attr, keys)


def get_all_group_members(db,
                          key_attr='group_id',
                          keys=None,
                          spread=None,
                          member_spread=None):
    gr = Utils.Factory.get('Group')(db)
    return build_concatenated_dict_from_row_list(
        row_list=gr.search_members(spread=spread,
                                   member_spread=member_spread,
                                   include_member_entity_name=True),
        key_attr=key_attr,
        keys=keys)


def get_all_persons_accounts(db,
                             key_attr='person_id',
                             keys=None,
                             account_spread=None,
                             primary_only=False):
    ac = Utils.Factory.get('Account')(db)
    return build_dict_from_row_list(
        rows=ac.list_accounts_by_type(primary_only=primary_only,
                                      account_spread=account_spread),
        key_attr=key_attr,
        keys=keys)


def get_all_posix_group_gids(db, key_attr='group_id', keys=None):
    pg = Utils.Factory.get('PosixGroup')(db)
    return build_dict_from_row_list(pg.list_posix_groups(), key_attr, keys)


def get_all_posix_groups(db, spread=None, key_attr='group_id', keys=None):
    pg = Utils.Factory.get('PosixGroup')(db)
    return build_dict_from_row_list(pg.search(spread=spread),
                                    key_attr=key_attr, keys=keys)


def get_all_posix_accounts_rows(db, spread=None,
                                key_attr='account_id', keys=None):
    pu = Utils.Factory.get('PosixUser')(db)
    posix_users_rows = pu.list_posix_users(spread=spread,
                                           filter_expired=True)
    return build_dict_from_row_list(posix_users_rows, key_attr, keys)


def get_all_host_rows(db, key_attr='host_id', keys=None):
    ho = Utils.Factory.get('Host')(db)
    hosts_rows = ho.search()
    return build_dict_from_row_list(hosts_rows, key_attr, keys)


def get_account_id_by_username(db, username):
    """Get the entity_id of an account by username."""
    ac = Utils.Factory.get('Account')(db)
    try:
        ac.find_by_name(username)
    except Errors.NotFoundError:
        return None
    return int(ac.entity_id)


def get_group_id_by_name(db, group_name):
    """Get the entity_id of a group by name."""
    gr = Utils.Factory.get('Group')(db)
    try:
        gr.find_by_name(group_name)
    except Errors.NotFoundError:
        return None
    return int(gr.entity_id)


def get_email_addr(db, account_id):
    """Get the primary email address of an account."""
    ac = Utils.Factory.get('Account')(db)
    try:
        ac.find(account_id)
        mail_addr = ac.get_primary_mailaddress()
        return mail_addr
    except Errors.NotFoundError:
        return None


def get_accounts_quarantine_data(db,
                                 account_ids=None,
                                 only_active=True):
    """
    Builds a dict: account_id -> quarantine_action, filtering on
    account IDs in account_ids if it is passed.
    @param db: Cerebrum db-object
    @param account_ids: list of account_ids
    @param only_active: boolean
    @return: dict
    """
    ac = Utils.Factory.get('Account')(db)
    all_quarantines = list(ac.list_entity_quarantines(
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
        qh = QuarantineHandler.QuarantineHandler(db, quarantines)
        if qh.should_skip():
            quarantine_data[acc_id] = 'skip'
        elif qh.is_locked():
            quarantine_data[acc_id] = 'lock'
        else:
            quarantine_data[acc_id] = 'none'
    return quarantine_data
