
from Cerebrum.modules.bofhd.cmd_param import *
from Cerebrum.modules.no.uit.bofhd_uit_cmds import BofhdExtension

class BofhdUiTExtension(BofhdExtension):

    
    #
    # Uito special table for reserved usernames. Usernames that is reserved duo
    # to being used in legacy systems
    #
    all_commands = {}
    all_commands['misc_list_legacy_user'] = Command(
        ("misc", "legacy_user"), PersonId(),
        fs=FormatSuggestion("%-6s %11s %6s %4s ", ('user_name', 'ssn', 'source', 'type'),
                            hdr="%-6s %-11s %6s %4s" % ('UserID', 'Personnr', 'Source', 'Type')))
    def misc_list_legacy_user(self,operator,personid):
        self.logger.debug("Var personid:"+personid)
        db_row = self.db.query( """
        SELECT user_name,ssn,source,type,name,comment
        FROM [:table schema=cerebrum name=legacy_users]
        WHERE
        user_name=:uname OR
        ssn=:ssn""",{'uname': personid, 'ssn':personid})
        ret = []
        for element in db_row:
            ret.append({'user_name': element[0], 'ssn':element[1],
                        'source': element[2],'type':element[3],
                        'name': element[4], 'comment': element[5]})
        return ret
                                             
    all_commands['misc_uit_check_ad_password'] = Command(
        ("misc", "ad_auth"), AccountName(),AccountPassword())
    def misc_uit_check_ad_password(self,operator,username,password):
        return "Checking password in domain AD for '%s' with password '%s'" % (username, password)

    
    all_commands['misc_get_primary_account'] = Command(
        ("misc", "get_account"), PersonId(),
        fs=FormatSuggestion("%s",('user_name'), hdr="%s" % ('Person NR')))
        
    def misc_get_primary_account(self,operator,ssn):
        return "bto001"
        pass
        #ac = self.Factory("Account")(self.db)
        
# arch-tag: 85db404e-b4f2-11da-8c86-8173ccfa4bd5
