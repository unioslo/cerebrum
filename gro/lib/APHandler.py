# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

import omniORB

from Cerebrum.gro.Cerebrum_core import Errors
from Cerebrum.gro import Transaction
from Cerebrum.gro import Account, Builder, CorbaBuilder, Attribute, Method

def create_ap_get_method(attribute):
    def get(self):
        # TODO: hooks til transaksjon/låsing må fikses her

        value = attribute.get(self.gro_object)

        ap_object = APHandler.convert(value, attribute.data_type, self.ap_handler)
        if ap_object is value:
            print 'returning:', [value]
            return value
        else:
            print 'returning:', [ap_object]
            return self.ap_handler.com.get_corba_representation(ap_object)
    return get

def create_ap_set_method(attribute):
    def set(self, corbaValue):
        # hooks til transaksjon/låsing må fikses her
        
        # så må value konverteres....
        
        value = corbaValue
        
        attribute.set(self.gro_object, value)
    return set

class APClass:
    """ Creator of Access point proxy object.

    An APClass object contains the APHandler and an object from the GRO API. 
    It acts as a proxy for the object.
    This is to give us a sort of automatic session handling that will solve two problems:
    1 - The client does not have to deal with a session id
    2 - GRO can perform locking on objects requested by a client,
        using the APHandler to identify it.
    """

    def __init__(self, gro_object, ap_handler):
        self.gro_object = gro_object
        self.ap_handler = ap_handler

    def create_ap_class(cls, gro_class, idl_class):
        name = gro_class.__name__
        ap_class_name = 'AP' + name
        
        exec 'class %s(cls, idl_class):\n\tpass\nap_class = %s' % (
             ap_class_name, ap_class_name)

        for attribute in gro_class.slots:
            get = create_ap_get_method(attribute)
            setattr(ap_class, 'get_' + attribute.name, get)

            if attribute.writable:
                set = create_ap_set_method(attribute)
                setattr(ap_class, 'set_' + attribute.name, set)

        ap_class.gro_class = gro_class

        # TODO: legge til support for gro_class.method_slots

        return ap_class

    create_ap_class = classmethod(create_ap_class)

def create_ap_handler_get_method(name):
    def get(self, *args, **vargs):
        print args, vargs, name, self
        obj = APHandler.gro_classes[name](*args, **vargs)
        return self.com.get_corba_representation(APHandler.classes[name](obj, self))
    return get

class APHandler(CorbaBuilder):
    """Access point handler.

    Each client has his own access point, wich will be used to identify the client
    so we can lock down objects to the client and check if the client has access to
    make the changes he tries to do. The client has to provide GRO a username
    and password before he gets the APHandler. This information will be stored in
    this object.
    """

    classes = {} # Access Point classes
    gro_classes = {} # GRO API classes to be used
    slots = []
    method_slots = [Method('begin','void'), Method('rollback', 'void'), Method('commit', 'void')]

    def convert(cls, value, data_type, ap_handler):
        # TODO: skummel bruk av navnekonvesjon, burde legge til flags i Attribute i stedet
        if data_type.endswith('Seq'):
            return [cls.convert(i) for i in value]
        elif data_type[0].isupper():
            ap_class = cls.classes[data_type]
            return ap_class(value, ap_handler)
        else:
            return value

    convert = classmethod(convert)

    def __init__(self, com, username, password):
        # Login raises exception if it fails, or returns entity_id if not.
        self.entity_id = self.login(username, password)
        self.username = username
        self.com = com
        self.transaction = None

    def login(self, username, password):
        """Login the user with the username and password.
        """
        # Check username
        for char in ['*','?']:
            if char in username:
                raise Errors.LoginError('Username contains invalid characters.')

        search = Account.create_search_class()()
        search.set_name(username)
        unames = search.search()
        if len(unames) != 1:
            raise Errors.LoginError('Wrong username or password.')
        account = unames[0]

        # Check password
        if not account.authenticate(password):
            raise Errors.LoginError('Wrong username or password.')

        # Check quarantines
        if account.is_quarantined():
            raise Errors.LoginError('Account has active quarantine, access denied.')

        # Log successfull login..
        
        return account.get_entity_id()
    
    def get_username(self):
        """Returns the username of the client.
        """
        return self.username

    def begin(self):
        """Starts a new transaction. If this APHandler already got a transaction
        running, an error will be raised.
        """
        if self.transaction is None:
            self.transaction = Transaction.Transaction(self)
        else:
            raise Errors.TransactionError("Transaction already created.")

    def rollback(self):
        """Rollback changes done in the transaction.
        """
        self.transaction.rollback()
        self.transaction = None
        
    def commit(self):
        """Commit changes to the database.

        Tries first to commit all nodes, then unlocks them.
        """
        self.transaction.commit()

    def register_gro_class(cls, gro_class):
        name = gro_class.__name__

        method_name = 'get_%s' % name.lower()
        method_impl = create_ap_handler_get_method(name)
        method = Method(method_name, name, gro_class.primary)

        cls.method_slots.append(method)
        cls.gro_classes[name] = gro_class
        setattr(cls, method_name, method_impl)

    register_gro_class = classmethod(register_gro_class)

    def create_idl(cls):
        txt = ''

        defined = []
        for gro_class in cls.gro_classes.values():
            txt += gro_class.create_idl_header(defined)
            
        for gro_class in cls.gro_classes.values():
            txt += gro_class.create_idl_interface()

        tmp = cls.create_idl_interface()
        txt += tmp
        
        return 'module %s {\n\t%s\n};' % ('generated', txt)

    create_idl = classmethod(create_idl)

    def build_classes(cls):
        idl_string = cls.create_idl()
        omniORB.importIDLString(idl_string)
        import generated__POA
        for name, gro_class in cls.gro_classes.items():
            idl_class = getattr(generated__POA, name)
            ap_class = APClass.create_ap_class(gro_class, idl_class)
            cls.classes[name] = ap_class

    build_classes = classmethod(build_classes)

    def create_ap_handler_impl(cls):
        import generated__POA
        class APHandlerImpl(cls, generated__POA.APHandler):
            pass
        return APHandlerImpl

    create_ap_handler_impl = classmethod(create_ap_handler_impl)
