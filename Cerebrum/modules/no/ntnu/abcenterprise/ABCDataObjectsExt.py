import sys
import time
from mx.DateTime import Date

import abcconf

from Cerebrum.modules.abcenterprise.ABCDataObjects import DataOU
from Cerebrum.modules.abcenterprise.ABCDataObjects import DataPerson

class DataOUExt(DataOU):
    def __init__(self):
        super(DataOUExt, self).__init__()
        self.replacedby = None
        self.stedkodes = []

    def __str__(self):
        kodes = None
        for kode in self.stedkodes:
            if not kodes:
                kodes = kode
            else:
                kodes += ", " + kode
        result = "%s DataOUExt: \n\treplacedby: %s\n\tStedkoder: %s\n" % (super(DataOUExt, self).__str__(), self.replacedby, kodes)
        return result

class DataPersonExt(DataPerson):
    def __init__(self):
        super(DataPersonExt, self).__init__()
        self.fnr_closed = []
        self.reserv_publish = None

    def __str__(self):
        old_fnr = None
        for old in self.fnr_old:
            if not old_fnr:
                old_fnr = old
            else:
                old_fnr += ", " + old
        result = ("%sDataPersonExt: \n" +
                    "\tprivacy: %s Old fnr: %s" %
                    (super(DataPersonExt, self).__str__(),
                    self.reserv_publish, old_fnr))
        return result
