from Cerebrum.Constants import Constants, \
     _AuthoritativeSystemCode, _OUPerspectiveCode, _SpreadCode, \
     _QuarantineCode, _EntityExternalIdCode, _PersonAffiliationCode, \
     _PersonAffStatusCode, _AccountCode, _PersonNameCode, \
     _ContactInfoCode, _CountryCode
from Cerebrum.modules.PosixUser import _PosixShellCode

central_Constants = Constants

class Constants(central_Constants):

    externalid_studentnr = _EntityExternalIdCode('NO_STUDNO',
                                                 'Norwegian student number')

    
#    system_initial = ()
#    system_people_auth_source =()
    
    system_school_administration = _AuthoritativeSystemCode('SCHADM',
                                                            'School HR administration system')

# arch-tag: 54a01cba-72f6-4c18-9296-e0b88b6266a7
