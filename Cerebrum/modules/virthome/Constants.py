#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""Constants for the VirtHome project.
"""

import cerebrum_path
import cereconf

from Cerebrum.Constants import (Constants, CLConstants)
from Cerebrum.Constants import _SpreadCode as SpreadCode
from Cerebrum.Constants import _QuarantineCode as QuarantineCode
from Cerebrum.modules.EntityTrait import _EntityTraitCode as EntityTrait


class VirtHomeCLConstants(CLConstants):
    #
    # Bofhd requests
    #####
    va_pending_create = Constants._ChangeTypeCode(
        'e_account',
        'pending_create',
        'waiting for creation confirmation on %(subject)s')

    va_email_change = Constants._ChangeTypeCode(
        'e_account',
        'pending_email',
        'waiting for e-mail change confirmation on %(subject)s')

    va_group_invitation = Constants._ChangeTypeCode(
        'e_group',
        'pending_invitation',
        'issued invitation to join group')

    va_group_owner_swap = Constants._ChangeTypeCode(
        'e_group',
        'pending_owner_change',
        'waiting for a group owner change')

    va_group_moderator_add = Constants._ChangeTypeCode(
        'e_group',
        'pending_moderator_add',
        'waiting for a new group moderator')

    va_password_recover = Constants._ChangeTypeCode(
        'e_account',
        'password_recover',
        'a pending password recovery request')

    va_reset_expire_date = Constants._ChangeTypeCode(
        'e_account',
        'reset_expire_date',
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

