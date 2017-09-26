import uuid

import cereconf
import ldap

from Cerebrum import Utils
from Cerebrum.config.configuration import Configuration, ConfigDescriptor
from Cerebrum.config.loader import read
from Cerebrum.config.settings import String
from Cerebrum.modules.event_publisher.amqp_publisher import AMQP091Publisher
from Cerebrum.modules.event_publisher.config import load_publisher_config
from Cerebrum.modules.event_publisher.scim import ScimFormatter
from Cerebrum.modules.synctools.data_fetcher import CerebrumDataFetcher


class ADLDAPConfig(Configuration):
    """Configuration for AD-LDAP connections."""

    ldap_proto = ConfigDescriptor(
        String,
        default=u'ldap',
        doc=u'The protocol to use when connecting to the LDAP-server.'
    )

    ldap_server = ConfigDescriptor(
        String,
        default=u'localhost:389',
        doc=u'The hostname (and port) to connect to.'
    )

    ldap_user = ConfigDescriptor(
        String,
        default=u'cereauth',
        doc=u'The username of the user to bind with.'
    )

    bind_dn_template = ConfigDescriptor(
        String,
        default=u'cn=cereauth,ou=users,dc=ad-example,dc=com',
        doc=u'The DN to use when binding the LDAP connection.'
    )

    users_dn = ConfigDescriptor(
        String,
        default=u'ou=users,dc=ad-example,dc=com',
        doc=u'The DN where to look up users.'
    )

    groups_dn = ConfigDescriptor(
        String,
        default=u'ou=groups,dc=ad-example,dc=com',
        doc=u'The DN where to look up groups.'
    )


def load_ad_ldap_config():
    config = ADLDAPConfig()
    read(config, 'ad_ldap')
    config.validate()
    return config


def build_ad_account_data(account_basic_info,
                          name_data,
                          quarantine_action,
                          posix_data,
                          email,
                          home_dir_data):
    ad_account_data = {'disabled': False}
    ad_account_data.update(account_basic_info)
    if posix_data:
        ad_account_data.update(posix_data)
    if name_data:
        ad_account_data.update(name_data)
    if quarantine_action:
        if quarantine_action == 'lock':
            ad_account_data.update({'disabled': True})
        elif quarantine_action == 'skip':
            ad_account_data.update({'skip': True})
    if home_dir_data:
        ad_account_data.update(home_dir_data)
    if email:
        ad_account_data.update({'email': email})
    return ad_account_data


def get_ad_account_data(account_id, df, spread):
    account_basic_info = df.get_account_data(account_id, spread)
    return build_ad_account_data(
        account_basic_info=account_basic_info,
        name_data=df.get_person_basic_info(account_basic_info['owner_id']),
        quarantine_action=df.get_quarantine_data([account_id]),
        posix_data=df.get_posix_data(account_id),
        email=df.get_email_addr(account_id),
        home_dir_data=df.get_homedir_data(account_id)
    )


def build_ad_account_obj(account_data, path_req_disks, group_postfix):
    first_name = unicode(account_data.get('first_name') or '', 'ISO-8859-1')
    last_name = unicode(account_data.get('last_name') or '', 'ISO-8859-1')

    def build_homedir(acc_data):
        home_host = acc_data.get('home_host')
        if not home_host:
            return ''
        if home_host in path_req_disks:
            path = acc_data['home_path'].split('/')[-1]
            return '\\\\{0}\\{1}\\{2}'.format(home_host,
                                              path,
                                              acc_data['username'])
        return '\\\\{0}\\{1}'.format(home_host, acc_data['username'])

    def build_mail(acc_data):
        email = acc_data.get('email')
        if email:
            return {'mail': [email]}
        return {}

    def build_group_name(acc_data):
        grp_name = acc_data.get('posix_group_name')
        if grp_name:
            return ''.join([grp_name, group_postfix])
        return ''

    ad_repr = {
        'entity_type': account_data['entity_type'],
        'entity_id': account_data['entity_id'],
        'username': account_data['username'],
        'disabled': account_data['disabled'],
        'givenName': [first_name.strip()],
        'sn': [last_name.strip()],
        'displayName': [' '.join([first_name, last_name])],
        'uidNumber': [str(account_data.get('posix_uid')) or ''],
        'gidNumber': [str(account_data.get('posix_gid')) or ''],
        'gecos': [unicode(account_data.get('gecos') or '', 'ISO-8859-1')],
        'primaryGroup_groupname': build_group_name(account_data),
        'uid': [account_data['username']],
        'msSFU30Name': [account_data['username']],
        'msSFU30NisDomain': ['uio'],
        'homeDirectory': [build_homedir(account_data)],
        'userPrincipalName': [''.join([account_data['username'], '@uio.no'])],
        'homeDrive': ['M:']
    }
    ad_repr.update(build_mail(account_data))
    return ad_repr


def build_acc_quarantine_data(df, account_ids=None):
    quarantine_data = df.get_quarantine_data(account_ids=account_ids)
    return quarantine_data


def build_all_ad_objects(df, path_req_disks, group_postfix, spread):
    """Creates a list of AD-objects for all Cerebrum accounts that should
    be present in AD."""
    accounts = df.get_all_account_rows(spread=spread)
    quarantine_data = build_acc_quarantine_data(df, account_ids=accounts.keys())
    person_names = df.get_all_persons_names()
    email_data = df.get_all_email_addrs()
    posix_data = df.get_all_posix_accounts_data()
    accounts_homedir_data = df.get_all_accounts_homedir_data(spread)

    account_data_list = [
        build_ad_account_data(
            account_basic_info=acc_data,
            name_data=person_names.get(acc_data['owner_id']),
            quarantine_action=quarantine_data.get(acc_id),
            posix_data=posix_data.get(acc_id),
            email=email_data.get(acc_data['username']),
            home_dir_data=accounts_homedir_data.get(acc_id)
        )
        for acc_id, acc_data in accounts.items()
    ]
    return [build_ad_account_obj(account_data, path_req_disks, group_postfix)
            for account_data in account_data_list]


def get_ad_account_data_list(account_ids, df, spread):
    return [get_ad_account_data(account_id, df, spread)
            for account_id in account_ids]


def get_ad_objects_list(account_ids, df,  path_req_disks, group_postfix, spread):
    account_data_list = get_ad_account_data_list(account_ids, df, spread)
    return [build_ad_account_obj(account_data, path_req_disks, group_postfix)
            for account_data in account_data_list]


def build_scim_account_msg(data):
    formatter = ScimFormatter()
    entity_route = formatter.get_entity_type_route(data['entity_type'])
    payload = {
        'eventUris': [formatter.get_uri('add')],
        'sub': formatter.build_url(entity_route, data['entity_id']),
        'iss': formatter.config.issuer,
        'jti': str(uuid.uuid4()),
        'iat': formatter.make_timestamp(),
        'resourceType': entity_route
    }
    return payload


def build_account_scim_list(account_list):
    return [build_scim_account_msg(account) for account in account_list]


def account_in_sync(crb_data, ad_data):
    attrs = ['sn', 'givenName', 'displayName', 'mail',
             'userPrincipalName', 'homeDrive', 'homeDirectory',
             'uidNumber', 'gidNumber', 'gecos',
             'uid', 'msSFU30Name', 'msSFU30NisDomain']

    if crb_data['disabled'] != ad_data['disabled']:
        return False
    for attr in attrs:
        if attr not in ad_data:
            if crb_data[attr] != ['']:
                return False
            continue
        decoded_ad_attr = [a.decode('utf-8') for a in ad_data[attr]]
        if crb_data[attr] != decoded_ad_attr:
            return False
    return True


def parse_ad_acc_data(ad_acc_data):
    uac = int(ad_acc_data['userAccountControl'][0])
    ad_acc_data.update({'disabled': hex(uac)[-1] == '2'})
    return ad_acc_data


def get_ldap_connection(config):
    password = Utils.read_password(config.ldap_user, 'ceretestad01.uio.no')
    con = ldap.initialize('{0}://{1}'.format(config.ldap_proto,
                                             config.ldap_server))
    con.bind_s(config.bind_dn_template.format(config.ldap_user),
               password)
    return con


def get_all_ad_values(ldap_con):
    ctrltype = ldap.controls.SimplePagedResultsControl.controlType
    lc = ldap.controls.SimplePagedResultsControl(True, 1000, '')
    pages = 0
    msg_id = ldap_con.search_ext(ldap_config.users_dn,
                                 ldap.SCOPE_SUBTREE,
                                 '(objectClass=user)',
                                 serverctrls=[lc])
    ldap_res = {}
    while True:
        pages += 1
        print('Getting page {}'.format(pages))
        rtype, data, rmsgid, serverctrls = ldap_con.result3(msg_id)
        for dn, attrs in data:
            ldap_res.update({attrs['cn'][0]: attrs})
        pctrls = [c for c in serverctrls
                  if c.controlType == ctrltype]
        if pctrls:
            cookie = pctrls[0].cookie
            if cookie:
                lc.cookie = cookie
                msg_id = ldap_con.search_ext(ldap_config.users_dn,
                                             ldap.SCOPE_SUBTREE,
                                             '(objectClass=user)',
                                             serverctrls=[lc])
            else:
                break
    return ldap_res


def get_all_crb_group_data(df, group_postfix):
    groups_data = df.get_all_groups_data(spread=ad_grp_spread,
                                         key_attr='name')
    pf_groups_data = add_group_postfix(groups_data, group_postfix)
    posix_group_data = df.get_all_posix_group_data()
    groupid2uids = {}
    for gid, acc in df.get_all_posix_accounts_rows(
            spread=ad_acc_spread,
            key_attr='gid').items():
        groupid2uids.setdefault(gid, []).append(str(acc['posix_uid']))
    return pf_groups_data


def add_group_postfix(groups_data, postfix):
    pf_groups_data = {}
    for group_name, group_data in groups_data.items():
        grp_name = ''.join([group_name, postfix])
        pf_groups_data[grp_name] = dict(group_data)
        pf_groups_data[grp_name].update({
            'displayName': grp_name,
            'displayNamePrintable': grp_name
        })
    return pf_groups_data


if __name__ == '__main__':
    group_postfix = getattr(cereconf, 'AD_GROUP_POSTFIX', '')
    path_req_disks = getattr(cereconf, 'AD_HOMEDIR_HITACHI_DISKS', ())
    df = CerebrumDataFetcher()
    db = Utils.Factory.get('Database')()
    co = Utils.Factory.get('Constants')(db)
    ad_acc_spread = co.Spread(cereconf.AD_ACCOUNT_SPREAD)
    ad_grp_spread = co.Spread(cereconf.AD_GROUP_SPREAD)

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--account_ids', nargs="*", type=int, help="""A list of entity_ids to sync""")
    parser.add_argument('--usernames', nargs="*", type=str, help="""A list of usernames to sync""")
    parser.add_argument('--fullsync', help="""Do a complete sync for all
                         accounts/groups""", action='store_true')
    parser.add_argument('--groups', help="""Do a complete sync for all
                         accounts/groups""", action='store_true')
    parser.add_argument('--send', help="""send messages""", action='store_true')
    args = parser.parse_args()

    ldap_config = load_ad_ldap_config()
    ldap_con = get_ldap_connection(ldap_config)

    desynced_entities = []
    not_in_ad = []
    not_in_crb = []

    if not args.usernames and not args.account_ids and not args.fullsync and not args.groups:
        raise SystemExit(
            'Error: No sync method specified. See --help.'
        )
    if (args.usernames or args.account_ids) and args.fullsync:
        raise SystemExit(
            'Error: --fullsync cannot be used with --account_ids or --usernames'
        )

    if args.fullsync:
        crb_acc_vals = build_all_ad_objects(df,
                                            path_req_disks,
                                            group_postfix,
                                            ad_acc_spread)
        ad_values = get_all_ad_values(ldap_con)

        for crb_acc in crb_acc_vals:
            if crb_acc.get('quarantine_action') == 'skip':
                continue
            try:
                ad_acc = ad_values.pop(crb_acc['username'])
                if not account_in_sync(crb_acc, parse_ad_acc_data(ad_acc)):
                    desynced_entities.append(crb_acc)
            except KeyError:
                not_in_ad.append(crb_acc)
        print('# of accounts present in AD, but not Cerebrum: {}'.format(
            len(ad_values)
        ))

    accounts = []
    if args.account_ids is not None:
        accounts = args.account_ids

    if args.usernames:
        for username in args.usernames:
            account_id = df.get_account_id_by_username(username)
            if account_id:
                accounts.append(account_id)

    if accounts:
        res = get_ad_objects_list(accounts,
                                  df,
                                  path_req_disks,
                                  group_postfix,
                                  ad_acc_spread)
        for crb_acc in res:
            if crb_acc.get('quarantine_action') == 'skip':
                continue
            ad_data = ldap_con.search_s(ldap_config.users_dn,
                                        ldap.SCOPE_SUBTREE,
                                        '(cn={})'.format(crb_acc['username']))
            if not ad_data:
                not_in_ad.append(crb_acc)
                continue
            ad_values = parse_ad_acc_data(ad_data[0][1])
            if not account_in_sync(crb_acc, ad_values):
                desynced_entities.append(ad_values)

    if args.groups:
        from pprint import pprint
        lol = df.get_all_account_rows(key_attr='account_id',
                                      keys=['account_id', 'owner_id'],
                                      spread=ad_acc_spread)
        pprint(lol.popitem())

    print('# of accounts that are desynced: '.format(len(desynced_entities)))
    print('# of accounts present in Cerebrum, but not in AD:'.format(
        len(not_in_ad)
    ))

    if args.send:
        omglol = build_account_scim_list(desynced_entities)
        pub_config = load_publisher_config()
        c = AMQP091Publisher(pub_config)
        c.open()
        for msg in omglol:
            c.publish('omglol', msg)
        c.close()



