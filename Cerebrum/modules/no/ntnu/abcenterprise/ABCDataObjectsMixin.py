import sys
import time
from mx.DateTime import Date

import abcconf

from Cerebrum.modules.abcenterprise.ABCDataObjects import DataOU
from Cerebrum.modules.abcenterprise.ABCDataObjects import DataPerson

class DataOUMixin(DataOU):
    def __init__(self):
        super(DataOUMixin, self).__init__()
        self.replacedby = None
        self.stedkodes = []

    def __str__(self):
        kodes = None
        for kode in self.stedkodes:
            if not kodes:
                kodes = kode
            else:
                kodes += ", " + kode
        result = ("%sDataOUMixin: \n"
            "\treplacedby: %s Stedkoder: %s\n" % (super(DataOUMixin, self).__str__(),
                                      self.replacedby, kodes))
       return result

class DataPersonMixin(DataPerson):
    def __init__(self):
        super(DataPersonMixin, self).__init__()
        self.fnr_old = []
        self.privacy = None

    def __str__(self):
        old_fnr = None
        for old in self.fnr_old:
            if not old_fnr:
                old_fnr = old
            else:
                old_fnr += ", " + old
        result = ("%sDataPersonMixin: \n"
                "privacy: %s Old fnr: %s" % (super(DataPersonMixin, self).__str__(),
                                    self.privacy, old_fnr))
        return result
