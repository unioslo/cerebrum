"""Access to Cerebrum code values.

"""

from Cerebrum import Constants
from Cerebrum.Constants import _AuthoritativeSystemCode
from Cerebrum.Constants import _PersonExternalIdCode

class Constants(Constants.Constants):
    system_sats = _AuthoritativeSystemCode('SATS', 'SATS')

    externalid_personoid = _PersonExternalIdCode('SATS_PERSONOID',
                                                 'PK in SATS')
