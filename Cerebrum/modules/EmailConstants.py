# coding: utf-8
#
# Copyright 2018 University of Oslo, Norway
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
""" Constant types and common constants for the Email module. """

from Cerebrum import Constants


class _EmailTargetCode(Constants._CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=email_target_code]'


class _EmailDomainCategoryCode(Constants._CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=email_domain_cat_code]'


class _EmailServerTypeCode(Constants._CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=email_server_type_code]'


class _EmailTargetFilterCode(Constants._CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=email_target_filter_code]'


class _EmailSpamLevelCode(Constants._CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=email_spam_level_code]'

    def __init__(self, code, level=None, description=None):
        super(_EmailSpamLevelCode, self).__init__(code, description)
        self.level = level

    def insert(self):
        self._pre_insert_check()
        self.sql.execute("""
        INSERT INTO %(code_table)s
          (%(code_col)s, %(str_col)s, level, %(desc_col)s)
        VALUES
          (%(code_seq)s, :str, :level, :desc)""" % {
            'code_table': self._lookup_table,
            'code_col': self._lookup_code_column,
            'str_col': self._lookup_str_column,
            'desc_col': self._lookup_desc_column,
            'code_seq': self._code_sequence},
            {'str': self.str,
             'level': self.level,
             'desc': self._desc})

    def get_level(self):
        if self.level is None:
            self.level = int(self.sql.query_1("""
            SELECT level
            FROM %(code_table)s
            WHERE code=:code""" % {'code_table': self._lookup_table},
                                  {'code': int(self)}))
        return self.level


class _EmailSpamActionCode(Constants._CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=email_spam_action_code]'


class _EmailVirusFoundCode(Constants._CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=email_virus_found_code]'


class _EmailVirusRemovedCode(Constants._CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=email_virus_removed_code]'


class EmailConstants(Constants.Constants):
    # TODO: Clean up these constants! And do it in a way that lets
    # us import system specific constants
    EmailTarget = _EmailTargetCode
    EmailDomainCategory = _EmailDomainCategoryCode
    EmailServerType = _EmailServerTypeCode
    EmailSpamLevel = _EmailSpamLevelCode
    EmailSpamAction = _EmailSpamActionCode
    EmailTargetFilter = _EmailTargetFilterCode
    EmailVirusFound = _EmailVirusFoundCode
    EmailVirusRemoved = _EmailVirusRemovedCode

    entity_email_domain = Constants._EntityTypeCode(
        'email_domain',
        'Email domain - see table "cerebrum.email_domain" and friends.')

    entity_email_address = Constants._EntityTypeCode(
        'email_address',
        'Email address - see table "cerebrum.email_address" and friends.')

    entity_email_target = Constants._EntityTypeCode(
        'email_target',
        'Email target - see table "cerebrum.email_target" and friends.')

    email_domain_category_noexport = _EmailDomainCategoryCode(
        'noexport',
        'Addresses in these domains can be defined, but are not'
        ' exported to the mail system.  This is useful for'
        ' pre-defining addresses prior to taking over a new'
        ' maildomain.')

    email_domain_category_cnaddr = _EmailDomainCategoryCode(
        'cnaddr',
        "Primary user addresses in these domains will be based on the"
        " owner's full common name, and not just e.g. the username.")

    email_domain_category_uidaddr = _EmailDomainCategoryCode(
        'uidaddr',
        'Primary user addresses in these domains will be in the format'
        'username@domain.')

    email_domain_category_include_all_uids = _EmailDomainCategoryCode(
        'all_uids',
        'All account email targets should get a valid address in this domain,'
        ' on the form <accountname@domain>.')

    email_target_account = _EmailTargetCode(
        'account',
        "Target is the local delivery defined for the PosixUser whose"
        " account_id == email_target.using_uid.")

    # exchange-related-jazz
    email_target_dl_group = _EmailTargetCode(
        'group',
        "Target is the Exchange - local delivery defined for"
        " the DistributionGroup with"
        " group_id == email_target.using_uid.")

    email_target_deleted = _EmailTargetCode(
        'deleted',
        "Target type for addresses that are no longer working, but"
        " for which it is useful to include a short custom text in"
        " the error message returned to the sender.  The text"
        " is taken from email_target.alias_value")

    email_target_forward = _EmailTargetCode(
        'forward',
        "Target is a pure forwarding mechanism; local deliveries will"
        " only occur as indirect deliveries to the addresses forwarded"
        " to.  Both email_target.target_entity_id, email_target.using_uid and"
        " email_target.alias_value should be NULL, as they are ignored."
        "  The email address(es) to forward to is taken from table"
        " email_forward.")

    email_target_file = _EmailTargetCode(
        'file',
        "Target is a file.  The absolute path of the file is gathered"
        " from email_target.alias_value.  Iff email_target.using_uid"
        " is set, deliveries to this target will be run as that"
        " PosixUser.")

    email_target_pipe = _EmailTargetCode(
        'pipe',
        "Target is a shell pipe.  The command (and args) to pipe mail"
        " into is gathered from email_target.alias_value.  Iff"
        " email_target.using_uid is set, deliveries to this target"
        " will be run as that PosixUser.")

    email_target_RT = _EmailTargetCode(
        'RT',
        "Target is a RT queue.  The command (and args) to pipe mail"
        " into is gathered from email_target.alias_value.  Iff"
        " email_target.using_uid is set, deliveries to this target"
        " will be run as that PosixUser.")

    email_target_Sympa = _EmailTargetCode(
        'Sympa',
        "Target is a Sympa mailing list.  The command (and args) to"
        " pipe mail into is gathered from email_target.alias_value."
        "  Iff email_target.using_uid is set, deliveries to this target"
        " will be run as that PosixUser.")

    email_target_multi = _EmailTargetCode(
        'multi',
        "Target is the set of `account`-type targets corresponding to"
        " the Accounts that are first-level members of the Group that"
        " has group_id == email_target.target_entity_id.")

    email_server_type_nfsmbox = _EmailServerTypeCode(
        'nfsmbox',
        "Server delivers mail as mbox-style mailboxes over NFS.")

    email_server_type_cyrus = _EmailServerTypeCode(
        'cyrus_IMAP',
        "Server is a Cyrus IMAP server, which keeps mailboxes in a "
        "Cyrus-specific format.")

    email_server_type_sympa = _EmailServerTypeCode(
        'sympa',
        "Server is a Sympa mailing list server.")

    email_server_type_exchange = _EmailServerTypeCode(
        'exchange',
        "Exchange server.")

    email_target_filter_greylist = _EmailTargetFilterCode(
        'greylist',
        "Delay messages from unknown servers")

    email_target_filter_uioonly = _EmailTargetFilterCode(
        'uioonly',
        "Only accept the use of an UiO address as sender address"
        " on the UiO network, or when using authenticated SMTP")

    email_target_filter_internalonly = _EmailTargetFilterCode(
        'internalonly',
        "Only route internal mail. External mail is rejected")


class CLConstants(Constants.CLConstants):
    # ChangeTypes used by the email module
    # TODO: Put these in it's own file? Put that file and this file into
    # Cerebrum/modules/email/?

    # email domain
    email_dom_add = Constants._ChangeTypeCode(
        'email_domain', 'add', 'add email domain %(subject)s',
        'name=%(string:new_domain_name)')
    email_dom_rem = Constants._ChangeTypeCode(
        'email_domain', 'remove', 'remove email domain %(subject)s',
        'name=%(string:del_domain')
    # either domain name or domain description has been changed
    email_dom_mod = Constants._ChangeTypeCode(
        'email_domain', 'modify', 'modify email domain %(subject)s',
        ('name=%(string:new_domain_name)',
         'desc=%(string:new_domain_desc'))
    email_dom_addcat = Constants._ChangeTypeCode(
        'email_domain_cat', 'add', 'add category in email domain'
        ' %(subject)s',
        'cat=%(int:cat)')
    email_dom_remcat = Constants._ChangeTypeCode(
        'email_domain_cat', 'remove', 'remove category in email domain'
        ' %(subject)s',
        'cat=%(int:cat)')

    # email target
    email_target_add = Constants._ChangeTypeCode(
        'email_target', 'add', 'add email target %(subject)s', )
    email_target_rem = Constants._ChangeTypeCode(
        'email_target', 'remove',  'remove email target %(subject)s')
    email_target_mod = Constants._ChangeTypeCode(
        'email_target', 'modify', 'modify email target %(subject)s',
        ('type=id:%(int:target_type)s',
         'server=id:%(int:server_id)s', ))
    email_address_add = Constants._ChangeTypeCode(
        'email_address', 'add', 'add email address %(subject)s',
        ('lp=%(string:lp)s',
         'domain=%(int:dom_id)s'))
    email_address_rem = Constants._ChangeTypeCode(
        'email_address', 'remove', 'remove email address %(subject)s',
        ('lp=%(string:lp)s',
         'domain=%(int:dom_id)s'))

    # email entity domain affiliation
    email_entity_dom_add = Constants._ChangeTypeCode(
        'email_entity_domain', 'add', 'add domain aff for %(subject)s',
        'affiliation=%(int:aff)')
    email_entity_dom_rem = Constants._ChangeTypeCode(
        'email_entity_domain', 'remove', 'remove domain aff for %(subject)s')
    email_entity_dom_mod = Constants._ChangeTypeCode(
        'email_entity_domain', 'modify', 'modify domain aff for %(subject)s',
        'affiliation=%(int:aff)')

    # email quota (subject here is an email_target)
    email_quota_add = Constants._ChangeTypeCode(
        'email_quota', 'add', 'add quota for %(subject)s',
        ('soft=%(int:soft)',
         'hard=%(int:hard)'))
    email_quota_rem = Constants._ChangeTypeCode(
        'email_quota', 'remove', 'remove quota for %(subject)s')
    email_quota_mod = Constants._ChangeTypeCode(
        'email_quota', 'modify', 'modify quota for %(subject)s',
        ('soft=%(int:soft)',
         'hard=%(int:hard)'))

    # email target filter
    email_tfilter_add = Constants._ChangeTypeCode(
        'email_tfilter', 'add', 'add tfilter for %(subject)s',
        'filter=%(int:filter)')
    email_tfilter_rem = Constants._ChangeTypeCode(
        'email_tfilter', 'remove', 'remove tfilter for %(subject)s',
        'filter=%(int:filter)')

    # email spam_filter
    email_sfilter_add = Constants._ChangeTypeCode(
        'email_sfilter', 'add', 'add sfilter for %(subject)s',
        ('level=%(int:level)',
         'action=%(int:action)'))
    email_sfilter_mod = Constants._ChangeTypeCode(
        'email_sfilter', 'modify', 'modify sfilter for %(subject)s',
        ('level=%(int:level)',
         'action=%(int:action)'))

    # email virus scan
    email_scan_add = Constants._ChangeTypeCode(
        'email_scan', 'add', 'add scan for %(subject)s',
        ('found=%(int:found)',
         'removed=%(int:removed)',
         'enable=%(int:enable)'))
    email_scan_mod = Constants._ChangeTypeCode(
        'email_scan', 'modify', 'modify scan for %(subject)s')

    # email forward (subject here is an email_target)
    email_forward_add = Constants._ChangeTypeCode(
        'email_forward', 'add',
        'add forward for %(subject)s',
        ('forward=%(string:forward)s',
         'enable=%(bool:enable)s'))
    email_forward_rem = Constants._ChangeTypeCode(
        'email_forward', 'remove',
        'remove forward for %(subject)s',
        ('forward=%(string:forward)s', ))
    email_forward_enable = Constants._ChangeTypeCode(
        'email_forward', 'enable',
        'enable forward for %(subject)s',
        ('forward=%(string:forward)s',
         'cat=%(int:cat)s'))
    email_forward_disable = Constants._ChangeTypeCode(
        'email_forward', 'disable',
        'disable forward for %(subject)s',
        ('forward=%(string:forward)s',
         'cat=%(int:cat)s'))

    # Local delivery of email forwards
    email_local_delivery = Constants._ChangeTypeCode(
        'email_forward_local_delivery', 'set',
        'modify local delivery for subject %(subject)s',
        ('enabled=%(string:enabled)s', ))

    # email vacation (subject here is an email_target)
    # TBD: should we bother to log this? I don't think so, vacation
    # msg will be moved to exchange
    email_vacation_add = Constants._ChangeTypeCode(
        'email_vacation', 'add', 'add vacation for %(subject)s')
    email_vacation_rem = Constants._ChangeTypeCode(
        'email_vacation', 'remove', 'remove vacation for %(subject)s')
    email_vacation_enable = Constants._ChangeTypeCode(
        'email_vacation', 'enable', 'enable vacation msg for %(subject)s')
    email_vacation_disable = Constants._ChangeTypeCode(
        'email_vacation', 'disable',
        'disable vacation msg for %(subject)s')

    # email primary address target (subject here is an email_target)
    email_primary_address_add = Constants._ChangeTypeCode(
        'email_primary_address', 'add',
        'add primary address for %(subject)s', 'primary=%(int:addr_id)')
    email_primary_address_rem = Constants._ChangeTypeCode(
        'email_primary_address', 'remove',
        'remove primary address for %(subject)s', 'primary=%(int:addr_id)')
    email_primary_address_mod = Constants._ChangeTypeCode(
        'email_primary_address', 'modify',
        'modify primary address for %(subject)s', 'primary=%(int:addr_id)')
    # email server (subject here is an e-mail server)
    email_server_add = Constants._ChangeTypeCode(
        'email_server', 'add', 'add email server %(subject)s',
        'type=%(int:server_type)')
    email_server_rem = Constants._ChangeTypeCode(
        'email_server', 'remove', 'remove email server %(subject)s',
        'type=%(int:server_type)')
    email_server_mod = Constants._ChangeTypeCode(
        'email_server', 'modify', 'modify email server %(subject)s',
        'type=%(int:server_type)')
