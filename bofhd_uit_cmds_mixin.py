import cerebrum_path
import cereconf
from Cerebrum import Utils
from Cerebrum import Errors
from Cerebrum.modules.no.fodselsnr import personnr_ok, InvalidFnrError
from Cerebrum.modules.bofhd.cmd_param import *
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.no.uit.bofhd_uit_cmds import BofhdExtension

class BofhdUiTExtension(BofhdExtension):


    def _uit_list_legacy_user(self,personid):
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

    
    #
    # Uito special table for reserved usernames. Usernames that is reserved due
    # to being used in legacy systems
    #
    all_commands = {}
    all_commands['misc_list_legacy_user'] = Command(
        ("misc", "legacy_user"), PersonId(),
        fs=FormatSuggestion("%-6s %11s %6s %4s ", ('user_name', 'ssn', 'source', 'type'),
                            hdr="%-6s %-11s %6s %4s" % ('UserID', 'Personnr', 'Source', 'Type')))
    def misc_list_legacy_user(self,operator,personid):
        return self._uit_list_legacy_user(personid)

