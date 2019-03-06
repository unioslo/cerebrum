# -*- coding: utf-8 -*-
# Copyright 2009 University of Oslo, Norway
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

"""The VirtAccount module presents an API to the information about the account
types available in VirtHome -- VAccount and FEDAccount. This module mimicks
some of the functionality from Cerebrum/Account.py and relies on
Cerebrum/Entity.py plus a number of tables from design/mod_virthome.sql.
"""

import mx.DateTime
import string

import cereconf

from Cerebrum import Utils
from Cerebrum.Entity import EntityName
from Cerebrum.Entity import EntityQuarantine
from Cerebrum.Entity import EntityContactInfo
from Cerebrum.Entity import EntitySpread
from Cerebrum.Entity import Entity
from Cerebrum.Account import Account
from Cerebrum.modules.EntityTrait import EntityTrait
from Cerebrum import Errors


class BaseVirtHomeAccount(Account,
                          EntityTrait):
    """Common functionality for VirtHome accounts.
    """

    #
    # By default FA/VA persist in VH for 1 year until expiration kicks in.
    #
    DEFAULT_ACCOUNT_LIFETIME = mx.DateTime.DateTimeDelta(365)

    # IVR 2009-04-11 FIXME: This uglyness is due to the fact that Account
    # inherits from AccountType and AccountHome. In VirtHome we need neither
    # (but we do need all the other nifty things in Account).
    # Hack to offset Account using AccountType 
    def get_account_types(self, *rest, **kw): raise NotImplementedError("N/A")
    def set_account_type(self, *rest, **kw): raise NotImplementedError("N/A")
    def del_account_type(self, *rest, **kw): raise NotImplementedError("N/A")
    def list_accounts_by_type(self, *rest, **kw): raise NotImplementedError("N/A")

    # Hack to offset Account using AccountHome
    def resolve_homedir(self, *rest, **kw): raise NotImplementedError("N/A")
    def clear_home(self, *rest, **kw): raise NotImplementedError("N/A")
    def set_homedir(self, *rest, **kw): raise NotImplementedError("N/A")
    def get_homedir(self, *rest, **kw): raise NotImplementedError("N/A")
    def get_homepath(self, *rest, **kw): raise NotImplementedError("N/A")
    def set_home(self, *rest, **kw):  raise NotImplementedError("N/A")
    def get_home(self, *rest, **kw):  raise NotImplementedError("N/A")
    def get_homes(self, *rest, **kw):  raise NotImplementedError("N/A")
    def list_account_home(self, *rest, **kw): raise NotImplementedError("N/A")

    def __eq__(self, other):
        raise NotImplementedError("TBD")

    def new(self, *rest):
        raise NotImplementedError("TBD")

    def __init__(self, *rest, **kw):
        self.__super.__init__(*rest, **kw)

        # VirtAccounts are owner by the system, rather than people/groups. We
        # need these ids later. Easier to fetch them right now and forget
        # about it.  
        initial_group = Utils.Factory.get("Group")(self._db)
        initial_group.find_by_name(cereconf.INITIAL_GROUPNAME)
        self.initial_group = initial_group.entity_id

        initial_account = EntityName(self._db)
        initial_account.find_by_name(cereconf.INITIAL_ACCOUNTNAME,
                                     self.const.account_namespace)
        self.initial_account = initial_account.entity_id
        self.legal_chars = set(string.letters + string.digits + " .@")
    # end __init__


    def populate(self, email, account_name,
                 human_first_name, human_last_name, expire_date=None):
        """Populate data for a new VirtAccount.

        The caller is responsible for populating VirtAccount owner's human
        name elsewhere, if the name at all exists.
        
        @type email: basestring
        @param email:
          E-mail address associated with this VirtAccount. This is the only
          communication channel with whoever/whatever really owns a
          VirtAccount.

        @type account_name: basestring
        @param account_name:
          Account name for this VirtAccount structured as <name>@<realm>. The
          <realm> is fixed -- cereconf.VIRTACCOUNT_REALM. <name> cannot
          contain '@' and it cannot be empty. Account names are obviously
          unique (within the virthome realm). This can be used as an id. 

        @type expire_date: mx.DateTime.DateTime
        @param expire_date:
          Expiration date for the account (an expired account is no longer
          considered available for any external services). If nothing is
          specified a default of now (creation date) + 1 year is used.
        """

        # IVR 2009-04-11 FIXME: We need to check that at the very least the
        # email is in a valid format.
        assert email and email.strip(), "VirtHome e-mail addresses cannot be empty"

        # Double check that the username is available
        assert self.uname_is_available(account_name), "Username already taken"

        Account.populate(self,
                         account_name,
                         # VA is owned by the system
                         self.const.entity_group,
                         self.initial_group,
                         self.account_type,
                         # VA is created by the system
                         self.initial_account,
                         expire_date)
        self.extend_expire_date(expire_date)
        
        self.populate_contact_info(self.const.system_virthome)
        self.populate_contact_info(self.const.system_virthome,      
                                   self.const.virthome_contact_email,
                                   email)
        # Push the names in. NB! Don't store the full name -- we'll derive it
        # later as needed.
        self.populate_contact_info(self.const.system_virthome,
                                   self.const.human_first_name,
                                   human_first_name)
        self.populate_contact_info(self.const.system_virthome,
                                   self.const.human_last_name,
                                   human_last_name)
    # end populate


    def validate_new_uname(self, domain, uname):
        """Check that the requested username is legal and free"""

        # Wrong domain
        if domain != self.const.account_namespace:
            return False

        # Illegal name
        if self.illegal_name(uname):
            return False

        if not self.uname_is_available(uname, domain):
            return False

        return self.__super.validate_new_uname(domain, uname)
    # end validate_new_uname

    def uname_is_available(self, uname, domain=None):
        """Checks that a username can be used. Note that we can not have
        several usernames which all converts to the same lowercased name, e.g.
        'User' and 'uSeR'. This is to prevent LDAP from crashing."""
        if domain is None:
            domain = int(self.const.account_namespace)
        return 0 == len(self.query("""
            SELECT entity_id
            FROM [:table schema=cerebrum name=entity_name]
            WHERE value_domain=:domain AND LOWER(entity_name) = :name""", 
                                            {'domain': int(domain),
                                             'name': uname.lower()}))
    # end uname_is_available

    def illegal_name(self, uname):
        """Check whether username is compliant with webid guidelines.

        This method implements checks common for *all* accounts in webid.
        """

        if not uname.strip():
            return "Account name is empty"
        
        if (uname.startswith(" ") or uname.endswith(" ")):
            return "Username cannot start/end with space"

        if any(x not in self.legal_chars
               for x in uname):
            return "Illegal character in uname"
        
        if uname.count("@") != 1:
            return "Account name misses a realm"

        return super(BaseVirtHomeAccount, self).illegal_name(uname)



    def update_contact_value(self, source_system, contact_type, value):
        """Alter an existing contact value in the db.

        If the value does not exist, add a new value with default priority.

        If multiple values exist with different contact priorities -- change
        them all.

        FIXME: This should be generalised.
        FIXME: If there are multiple preferences for the same ss/ct pair, we
        overwrite them all. This works for VH, but it NOT a general solution.
        """

        if not self.get_contact_info(source_system, contact_type):
            # This method makes an INSERT INTO.
            self.add_contact_info(source_system, contact_type, value)
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=entity_contact_info]
            SET contact_value = :value
            WHERE entity_id = :e_id AND
            source_system = :source AND
            contact_type = :contact_type
            """, {"e_id": self.entity_id,
                  "source": int(self.const.AuthoritativeSystem(source_system)),
                  "contact_type": int(self.const.ContactInfo(contact_type)),
                  "value": value})
    # end update_contact_value


    def __get_contact_info(self, contact_type):
        rows = self.get_contact_info(self.const.system_virthome, contact_type)
        if len(rows) > 1:
            raise ValueError("Too many %s registered for account %s" %
                             (self.const.ContactType(contact_type),
                              self.account_name))
        elif len(rows) == 1:
            row = rows[0]
            return row["contact_value"]
        else:
            return None
    # end __get_contact_info
        

    def set_email_address(self, mail):
        self.update_contact_value(self.const.system_virthome,
                                 self.const.virthome_contact_email,
                                 mail)
    # end set_email_address


    def get_email_address(self):
        return self.__get_contact_info(self.const.virthome_contact_email)


    def set_owner_name(self, name_type, name):
        """Add a non-unique name.

        The only non-unique name we allow to add is that of the account's
        human owner. These names originate from a specific domain.
        """

        assert name_type in (self.const.human_first_name,
                             self.const.human_last_name)
        self.update_contact_value(self.const.system_virthome,
                                  name_type, name)
    # end set_owner_name


    def get_owner_name(self, name_type):
        """Fetch a specific name for this account's human owner.

        This method is the only interface to retrieving name information from
        Cerebrum. For the specific situation where name_type is the owner's
        full name, we fetch first and last names and join them. Full name is
        not stored in Cerebrum as such.
        """

        if name_type == self.const.human_full_name:
            first = self.__get_contact_info(self.const.human_first_name)
            last =  self.__get_contact_info(self.const.human_last_name)
            if first is None and last is None:
                return None
            first = first or ""
            last = last or ""
            return " ".join((first, last))

        return self.__get_contact_info(name_type)
    # end get_owner_name


    def extend_expire_date(self, date=None):
        """Move account's expire date.

        If no expire date is specified, set expire date to
        DEFAULT_ACCOUNT_LIFETIME days from today.
        """

        if date is None:
            self.expire_date = mx.DateTime.now() + self.DEFAULT_ACCOUNT_LIFETIME
        else:
            self.expire_date = date
    # end extend_expire_date
# end BaseVirtHomeAccount
    


class VirtAccount(BaseVirtHomeAccount):
    """A class to adapt Cerebrum's Account to VirtHome requirements.

    A VirtAccount class represents non-federated accounts in VirtHome.

    These are the accounts that we have the least amount of control over.
    Every VirtAccount has en e-mail (EntityContactInfo), an account_name, a
    created_at and an expire_date. Optionally, a human-like name may be
    specified to help identify the human owner of the account.
    """

    def __init__(self, *rest, **kw):
        self.__super.__init__(*rest, **kw)
        self.account_type = self.const.virtaccount_type
    # end __init__


    def write_db(self):
        """Sync proxy content to the database."""

        # We don't store anything in VirtAccount, just the superclasses
        self.__super.write_db()
    # end write_db


    def clear(self):
        """Erase the changes from the VirtAccount proxy.

        Whether the changes have been written to the db or not, they have to
        be explicitely clear()ed, in order to populate()/find() another
        VirtAccount. This method does just that. Check mark_update.__doc__ for
        details.
        """
        # See write_db()
        self.__super.clear()
    # end clear


    def illegal_name(self, uname):
        if self.__super.illegal_name(uname):
            return self.__super.illegal_name(uname)
            
        # Present, but erroneous realm
        if uname.split("@")[1] != cereconf.VIRTHOME_REALM:
            return "Wrong realm <%s> for VirtAccount" % (uname.split("@")[1],)

        if len(uname.split("@")[0]) < 4:
            return "Account name %s is too short" % (uname,)

        return False

    # IVR 2009-04-11 TBD: Do we want to override some of the is_*()-methods?
    # A VirtAccount is not active, until VACCOUNT_UNCONFIRMED trait has been
    # removed.
# end VirtAccount



class FEDAccount(BaseVirtHomeAccount):
    """A class to adapt Cerebrum's Account to VirtHome requirements.

    A FEDAccount class represents federated accounts in VirtHome.

    These are the accounts that we come from federated institutions and
    therefore the information contained therein is (at least somewhat)
    trustworthy. Every FEDAccount has an e-mail, an account name, a create
    date and an expire_date. Optionally, a human-like name may be specified to
    help identify the human owner of the account.
    """

    def __init__(self, *rest, **kw):
        self.__super.__init__(*rest, **kw)

        self.account_type = self.const.fedaccount_type
    # end __init__


    def write_db(self):
        """Sync proxy content to the database."""

        # We don't store anything in VirtAccount, just the superclasses
        self.__super.write_db()
    # end write_db


    def clear(self):
        """Erase the changes from the VirtAccount proxy.

        Whether the changes have been written to the db or not, they have to
        be explicitely clear()ed, in order to populate()/find() another
        VirtAccount. This method does just that. Check mark_update.__doc__ for
        details.
        """
        # See write_db()
        self.__super.clear()
    # end clear


    def illegal_name(self, uname):
        if self.__super.illegal_name(uname):
            return self.__super.illegal_name(uname)

        # Present, but erroneous realm. How do we check this, exactly?
        return False
    # end illegal_name


    # FIXME: All the auth/password methods below would not have been
    # necessary, had that functionality been split out into an authentication
    # plugin. 
    def affect_auth_types(self, *authtypes):
        raise NotImplementedError("FEDAccount does not support authentication "
                                  "via Cerebrum")

    def populate_authentication_type(self, *rest, **kw):
        raise NotImplementedError("FEDAccount does not support authentication "
                                  "via Cerebrum")
    # end populate_authentication_type

    def wants_auth_type(self, method):
        raise NotImplementedError("FEDAccount does not support authentication "
                                  "via Cerebrum")
    # end wants_auth_type

    def set_password(self, plaintext):
        raise NotImplementedError("FEDAccount does not support authentication "
                                  "via Cerebrum")
    # end set_password

    def encrypt_password(self, *rest, **kw):
        raise NotImplementedError("FEDAccount does not support authentication "
                                  "via Cerebrum")

    def decrypt_password(self, *rest, **kw):
        raise NotImplementedError("FEDAccount does not support authentication "
                                  "via Cerebrum")

    def verify_password(self, *rest, **kw):
        raise NotImplementedError("FEDAccount does not support authentication "
                                  "via Cerebrum")

    def verify_auth(self, *rest, **kw):
        raise NotImplementedError("FEDAccount does not support authentication "
                                  "via Cerebrum")

    def make_passwd(self, uname):
        raise NotImplementedError("FEDAccount does not support authentication "
                                  "via Cerebrum")

    # IVR 2009-04-11 TBD: Do we want to override some of the is_*()-methods?
    # A FEDAccount is not active, until VACCOUNT_UNCONFIRMED trait has been
    # removed.
# end FEDAccount
