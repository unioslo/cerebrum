#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""Constants for the VirtHome project.
"""

import cereconf

from Cerebrum.Constants import (Constants, CLConstants, _ChangeTypeCode)
from Cerebrum.Constants import _SpreadCode as SpreadCode
from Cerebrum.Constants import _QuarantineCode as QuarantineCode
from Cerebrum.modules.EntityTraitConstants import _EntityTraitCode as EntityTrait


class BofhdVirtHomeAuthConstants(Constants):
    pass
# end BofhdVirtHomeAuthConstants


class VirtHomeCLConstants(CLConstants):
    """
    ChangeTypeCodes related to VirtHome

    VirtHome change log events are used more as indicators of requests than as
    regular change log events.

    For instance, a typical use case would be to run the bofh command
    user_virtaccount_create which would create an event in pending_changelog
    with a confirmation key. Running the bofh command user_confirm_request
    with that confirmation key would then create the user, and delete the
    change log event, without logging the deletion of the request. This means
    that there are no change_log events that confirm the deletion of the
    "requests", only change_log events of pending requests.

    """
    #
    # Bofhd requests
    #####
    va_pending_create = _ChangeTypeCode(
        'virthome_account_create',
        'request',
        'waiting for creation confirmation on %(subject)s')

    va_email_change = _ChangeTypeCode(
        'virthome_account_email',
        'request',
        'waiting for e-mail change confirmation on %(subject)s')

    va_group_invitation = _ChangeTypeCode(
        'virthome_group_member',
        'request',
        'issued invitation to join group')

    va_group_admin_swap = _ChangeTypeCode(
        'virthome_group_admin_change',
        'request',
        'waiting for a group admin change')

    va_group_moderator_add = _ChangeTypeCode(
        'virthome_group_moderator_add',
        'request',
        'waiting for a new group moderator')

    va_password_recover = _ChangeTypeCode(
        'virthome_account_pwd_recover',
        'request',
        'a pending password recovery request')

    va_reset_expire_date = _ChangeTypeCode(
        'virthome_account_reset_exp_date',
        'request',
        "push VA/FA's expire date into the future")


class VirtHomeMiscConstants(Constants):
    """Miscellaneous VH constants.
    """

    virtaccount_type = Constants.Account("virtaccount",
                                         "Non-federated account in VirtHome")
    
    fedaccount_type = Constants.Account("fedaccount",   
                                        "Federated account in VirtHome")

    system_virthome = Constants.AuthoritativeSystem('VH', "VirtHome")

    virthome_contact_email = Constants.ContactInfo(
                               "VH-MAIL",
                               "VirtHome accounts' e-mail address")

    human_first_name = Constants.ContactInfo("HUMANFIRST",
                                             "VA/FA's human owner's first name")
    human_last_name = Constants.ContactInfo("HUMANLAST",
                                            "VA/FA's human owner's last name")
    human_full_name = Constants.ContactInfo("HUMANFULL",
                                            "VA/FA's human owner's full name")
    
    virthome_group_url = Constants.ContactInfo(
                               "VH-GROUP-URL",
                               "Group resource url in VirtHome")

    #
    # Various spreads ...
    spread_ldap_group = SpreadCode(
        'group@ldap', Constants.entity_group,
        'Group is exported to LDAP')

    spread_ldap_account = SpreadCode(
        'account@ldap', Constants.entity_account,
        'Account is exported to LDAP')


    #
    # Various quarantines ...
    quarantine_autopassword = QuarantineCode("autopassword", "Password is too old")
    quarantine_nologin = QuarantineCode("nologin", "Login not allowed")
    quarantine_pending = QuarantineCode("pending", "Account is pending confirmation")
    quarantine_disabled = QuarantineCode("disabled", "Account is disabled")


    trait_user_eula = EntityTrait("user_eula",
                                  Constants.entity_account,
                                  "Account acknowledged user EULA")

    trait_group_eula = EntityTrait("group_eula",
                                   Constants.entity_account,
                                   "Account acknowledged group EULA")

    trait_user_invited = EntityTrait("user_invited",
                                     Constants.entity_account,
                                     "Account has been explicitly invited to join a group")

    trait_group_forward = EntityTrait("group_forward",
                                     Constants.entity_group,
                                     "Redirect URL to use when a new member joins a group.")

    trait_user_retained = EntityTrait("user_retained",
                                      Constants.entity_account,
                                      "Account have been retained from LDAP export.")

    trait_user_notified = EntityTrait("user_notified",
                                      Constants.entity_account,
                                      """Account owner have been emailed (about
                                      LDAP export) """)
# end VirtHomeMiscConstants

