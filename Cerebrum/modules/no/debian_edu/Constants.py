from Cerebrum.Constants import Constants, \
     _AuthoritativeSystemCode, _OUPerspectiveCode, _SpreadCode, \
     _QuarantineCode, _PersonExternalIdCode, _PersonAffiliationCode, \
     _PersonAffStatusCode, _AccountCode, _PersonNameCode, \
     _ContactInfoCode, _CountryCode
from Cerebrum.modules.PosixUser import _PosixShellCode

central_Constants = Constants

class Constants(central_Constants):

    externalid_studentnr = _PersonExternalIdCode('NO_STUDNO', 'Norwegian student number')
