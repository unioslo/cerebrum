# Windows/ActiveDirectory-only
import sys
import os
if (os.uname()[0] != 'Windows'):
    print "Not on windows.. exiting"
    sys.exit(255)
else:
    import win32com

class AdsiBack:
    """
    Generalized class representing common data for working with adsi objects.
    In general, working with Active Directory, you can either use WinNT:// or
    LDAP:// to search,add,modify,delete objects.
    """
    def __init__(self):
        pass

    def begin(incr=False):
        ''' Initialize objects and authenticate as needed. '''
        pass

    def close():
        ''' Close all authenticated objects and commit changes if nececerry.'''
        pass

    def abort():
        ''' Abort any ongoing operations. '''
        pass

    def add(self):
        pass

    def update(self):
        pass

    def delete(self):
        pass

class ADUser(AdsiBack):
    """
    Reference: 
    # http://www.microsoft.com/windows2000/techinfo/howitworks/activedirectory/adsilinks.asp
    # http://search.microsoft.com/search/results.aspx?qu=adsi&View=msdn&st=b&c=4&s=1&swc=4
    Example usage:
    try:
        nt = ADUser(account)
        nt.set(NewPassword)
        return 1
    except pythoncom.com_error, (hr,msg,exc,arg):
        scode = exc[5]
        # Codes:
        # 0x8007005 => account locked out
        # 0x80070056 => invalid OLD NT Password
        # 0x800708ad => account does not exist
        # 0x800708c5 => password cannot be the same as any previous password and
        #               must satisfy the domain's password-uniqueness policies
        # So, handle errors any way you want
        pass
    else:
        return "ADSI Error - %x: %s, %x\n" % (hr,msg,scode)
    return 0
    """
    def __init__(self,userid):
        self.adsiNS = win32com.client.Dispatch('ADsNameSpaces')
        #ADSI can work with 2 different Userpaths -> WinNT:// and LDAP://
        Userpath = "WinNT://DOMAIN/" + userid + ",user"
        self.adsiNTUser = self.adsiNS.GetObject("",Userpath)

    ###
    # Example function:
    #def set(self,NewPassword):
    #    self.adsiNTUser.SetPassword(NewPassword)

    def add(self,obj):
        pass

class ADGroup(AdsiBack):
    """
    Handle groups in AD/NT
    """

    def __init__(self,obj):
        pass

class ADAlias(AdsiBack):
    """
    Handles mail-aliases (distribution lists) within Exchange/AD
    """
    def __init__(self,obj):
        pass

# arch-tag: e76356d7-873f-4cb6-95a5-b852638f5524
