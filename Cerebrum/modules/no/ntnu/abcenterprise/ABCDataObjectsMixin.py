import sys
import time
from mx.DateTime import Date

import abcconf

from Cerebrum.modules.abcenterprise.ABCDataObjects import DataOU

class DataOUMixin(DataOU):
    def __init__(self):
        super(DataOUMixin, self).__init__()
        self.replacedby = None

    def __str__(self):
        result = ("%sDataOUMixin: \n"
            "\treplacedby: %s \n" % (super(DataOUMixin, self).__str__(),
                                      self.replacedby))
        return result
