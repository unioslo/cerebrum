#from Cerebrum import Utils
#from Cerebrum.OU import OU
#from Cerebrum.Entity import EntityName
import random
import sys
import re
import string
import crypt
import pprint


# UIT imports
import md5
import base64
import sha
import mx
import traceback
# UIT end
import cerebrum_path
import cereconf
from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum.modules.no import Stedkode
from Cerebrum import Utils
from Cerebrum.Utils import NotSet
from Cerebrum.modules import Email
from Cerebrum.modules.pwcheck.history import PasswordHistory
#from Cerebrum.modules import PasswordHistory
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.Utils import pgp_encrypt, Factory, prepare_string
from Cerebrum.modules.no.uit.Email import email_address
logger = Factory.get_logger(cereconf.DEFAULT_LOGGER_TARGET)
from pprint import pprint


from Cerebrum.modules.no import Stedkode

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
person = Factory.get('Person')(db)
account = Factory.get('Account')(db)    
#__version__ = "1.1"


class StedkodeMixin(Stedkode.Stedkode):
    
    def get_name(self,domain):
        self.EntityName.get_name(self,domain)

    def find_by_perspective_old(self, ou_id,perspective):
        """Associate the object with the OU whose identifier is OU_ID and perspective as given.

        If OU_ID isn't an existing OU identifier,
        NotFoundError is raised."""
        self.__super.find(ou_id)
        (self.ou_id, self.name, self.acronym, self.short_name,
         self.display_name) = self.query_1("""
        SELECT oi.ou_id, oi.name, oi.acronym, oi.short_name, oi.display_name
        FROM [:table schema=cerebrum name=ou_info] oi,
             [:table schema=cerebrum name=ou_structure] os
        WHERE oi.ou_id=:ou_id AND oi.ou_id = os.ou_id AND os.perspective=:perspective""", {'ou_id': ou_id,'perspective': perspective})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []


    def find_by_perspective(self, ou_id,perspective):
        name_variant = co.ou_name
        #perspective = co.perspective_fs
        self.__super.find(ou_id)
        (self.ou_id, self.name) = self.query_1("""SELECT os.ou_id, eln.name FROM [:table schema=cerebrum name=entity_language_name] eln, [:table schema=cerebrum name=ou_structure] os WHERE eln.name_variant=:name_variant_1 AND eln.entity_id = os.ou_id AND os.ou_id=:ou_id_1 AND os.perspective=:perspective_1""",{'name_variant_1' : name_variant,'ou_id_1' : ou_id, 'perspective_1' : perspective})

        try:
            name_variant = co.ou_name_acronym
            self.acronym = self.query_1("""SELECT eln.name FROM [:table schema=cerebrum name=entity_language_name] eln, [:table schema=cerebrum name=ou_structure] os WHERE eln.name_variant=:name_variant_1 AND eln.entity_id = os.ou_id AND os.ou_id=:ou_id_1 AND os.perspective=:perspective_1""",{'name_variant_1' : name_variant,'ou_id_1' : ou_id, 'perspective_1' : perspective})
        except Errors.NotFoundError:
            self.acronym=""
            #print "unable to find acronym for %s" % ou_id
        try:
            name_variant = co.ou_name_short
            self.short_name = self.query_1("""SELECT eln.name FROM [:table schema=cerebrum name=entity_language_name] eln, [:table schema=cerebrum name=ou_structure] os WHERE eln.name_variant=:name_variant_1 AND eln.entity_id = os.ou_id AND os.ou_id=:ou_id_1 AND os.perspective=:perspective_1""",{'name_variant_1' : name_variant,'ou_id_1' : ou_id, 'perspective_1' : perspective})
        except Errors.NotFoundError:
            self.short_name=""
            #print "unable to find short name for %s" % ou_id
        try:
            name_variant = co.ou_name_display
            self.display_name = self.query_1("""SELECT eln.name FROM [:table schema=cerebrum name=entity_language_name] eln, [:table schema=cerebrum name=ou_structure] os WHERE eln.name_variant=:name_variant_1 AND eln.entity_id = os.ou_id AND os.ou_id=:ou_id_1 AND os.perspective=:perspective_1""",{'name_variant_1' : name_variant,'ou_id_1' : ou_id, 'perspective_1' : perspective})
        except Errors.NotFoundError:
            self.display_name=""
            #print "unable to find display name for %s" % ou_id

        #print "having collected ou names:"
        #print "ou_name:%s" % self.name
        #print "ou_acronym:%s" % self.acronym
        #print "ou_short:%s" % self.short_name
        #print "ou_display:%s" % self.display_name
       

        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []
# 785 = name
# 784 = acronym
# 787 = short
# 783 = display
# ?   = sort
