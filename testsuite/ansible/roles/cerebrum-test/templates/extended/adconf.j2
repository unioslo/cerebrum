# -*- coding: utf-8 -*-
"""The configuration for the AD sync."""
 
from Cerebrum.Utils import Factory
 
# Provide defaults for all settings.
from Cerebrum.config.adconf import *
from Cerebrum.config.adconf import ConfigUtils as cu
 
 
co = Factory.get('Constants')(Factory.get('Database')())
 
host_uio = 'ceresynk02.uio.no'

SYNCS['AD_account'] = {
        'sync_classes': ('Cerebrum.modules.ad2.ADSync/UserSync',),
        'object_classes': (
            'Cerebrum.modules.ad2.CerebrumData/CerebrumUser',
            ),
        'domain': 'uio.no',
        # Connection settings:
        # The hostname of the Member server we should connect to:
        'server': host_uio,
        # The user we should authenticate to the server with:
        'auth_user': 'cereauth',
        # The user we can administrate the AD domain with:
        'domain_admin': 'uio.no\\ceresynk02_service',

        'target_ou': 'OU=users,OU=cerebrum,DC=uio,DC=no',
        # TODO: should we add the DC-parts automatically through the 'domain'
        #       definition? Could be set for all OU definitions.
        'search_ou': 'OU=cerebrum,DC=uio,DC=no',
        # OUs to ignore. TODO: what to do with objects outside of search_ou?
        # What to do with objects unknown in Cerebrum (includes those without
        # AD-spread), and those who are known and have the correct spread, but
        # is considered not active (inactive, disabled):
        # Possible options:
        # - ignore: do nothing. The OUs will not be cleaned up in.
        # - disable: Mark the object as disabled. Note that this only works for
        #            accounts.
        # - move: deactivate and move the object to a given OU
        # - delete: delete the object. Note that this might not be undone!
        'handle_unknown_objects': ('disable', None),
        'handle_deactivated_objects': ('disable', None),

        'create_ous': True,
        # If objects that are not in the correct OU should be moved:
        'move_objects': True,

        # The different languages to use, ordered by priority:
        # Used for instance for the Title attribute.
        'language': ('nb', 'nn', 'en'),

        # If SID should be stored in Cerebrum. Default: False.
        #'store_sid': False,

        # What change types the quicksync should treat:
        # TODO: note that if new change types are added, all such events would
        # be processed, even those created before the previous quicksync run.
        'change_types': (#('account', 'create'),
                         #('account', 'delete'),
                         #('account', 'modify'),
                         ('account_password', 'set'),
                         ('quarantine', 'add'), 
                         ('quarantine', 'modify'),
                         ('quarantine', 'remove'),
                         ('quarantine', 'refresh'), 
                         ('ad_attr', 'add'),
                         ('ad_attr', 'remove')),

        'attributes': {'SamAccountName': None,
                #'Name': None, # TODO: how should we update Name - can't be
                #updated in the normal way, but through a rename-command.
                       'UserPrincipalName': None,
                       'GivenName': None,
                       'DisplayName': None,
                       # Note that Surname, sn and Sn marks the same attribute,
                       # but Surname is not possible to write - use Sn or sn.
                       'Surname': None,
                       # Titles need some config:
                       'Title': ('PERSONALTITLE', 'WORKTITLE'), # what titles to use, in priority
                       # TODO: others

                       #'mail': None,
                       # TODO: these are for subclasses
                       #'HomeDrive': None,
                       #'HomeDirectory': None,
                       ## TODO: 
                       ##
                       ## TODO: Not tested yet:
                       #'Mail': None,
                       #'ProfilePath': None,
                       },
    }

# AD sync for Office365 attributes
SYNCS['consent'] = {
    'sync_classes': ('Cerebrum.modules.ad2.froupsync/ConsentGroupSync',
                     'Cerebrum.modules.ad2.froupsync/AffGroupSync',),
    'object_classes': (
        'Cerebrum.modules.ad2.CerebrumData/CerebrumGroup', ),

    'domain': 'uio.no',
    # Connection settings:
    # The hostname of the Member server we should connect to:
    'server': host_uio,
    # The user we should authenticate to the server with:
    'auth_user': 'cereauth',
    # The user we can administrate the AD domain with:
    'domain_admin': 'uio.no\\ceresynk02_service',
    # 'encrypted': True,
    # 'ca': os.path.join(cereconf.DB_AUTH_DIR, 'ad.pem'),

    'target_ou': 'OU=Groups,OU=ad_only,DC=uio,DC=no',
    'search_ou': 'OU=Groups,OU=ad_only,DC=uio,DC=no',
    'create_ous': False,
    'move_objects': False,

    'target_type': 'account',
    'target_spread': 'AD_account',

    'attributes': {
        'SamAccountName': ConfigUtils.AttrConfig(default='%(ad_id)s'),
        'DisplayName': ConfigUtils.AttrConfig(default='%(ad_id)s'),
        'DisplayNamePrintable': ConfigUtils.AttrConfig(default='%(ad_id)s'),
        'Description': ConfigUtils.CallbackAttr(
            lambda e: getattr(e, 'description', 'N/A').strip()),
        'Member': ConfigUtils.CallbackAttr(
            default=[],
            callback=lambda g: ['CN=%s,OU=users,OU=cerebrum,DC=uio,DC=no' % m
                                for m in getattr(g, 'members', [])]), },

    'script': {},

    'change_types': (
        ('consent', 'approve'),
        ('consent', 'decline'),
        ('consent', 'delete'),
        ('person_aff', 'add'),
        ('person_aff', 'modify'),
        ('person_aff', 'remove'), ),

    'handle_unknown_objects': ('delete', None),
    'handle_deactivated_objects': ('disable', None),

    'affiliation_groups': {
        'uioOffice365staff': [('SAP', 'ANSATT'), ],
        'uioOffice365student': [('FS', 'STUDENT'), ], },

    'consent_groups': {
        'uioOffice365consent': ['office365'], },
}

