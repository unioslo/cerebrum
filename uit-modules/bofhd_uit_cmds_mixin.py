# encoding: utf-8
from Cerebrum.modules.bofhd.cmd_param import Command
from Cerebrum.modules.bofhd.cmd_param import FormatSuggestion
from Cerebrum.modules.bofhd.cmd_param import PersonId
from Cerebrum.modules.legacy_users import LegacyUsers
from Cerebrum.modules.no.uit.bofhd_uit_cmds import BofhdExtension


def list_legacy_users(db, search_term):
    lu = LegacyUsers(db)
    results = dict()
    for row in lu.search(username=search_term):
        results[row['user_name']] = dict(row)
    for row in lu.search(ssn=search_term):
        results[row['user_name']] = dict(row)
    return list(results.values())


class BofhdUiTExtension(BofhdExtension):

    all_commands = {}

    #
    # UiT special table for reserved usernames. Usernames that is reserved due
    # to being used in legacy systems
    #
    all_commands['misc_list_legacy_user'] = Command(
        ("misc", "legacy_user"),
        PersonId(),
        fs=FormatSuggestion(
            "%-6s %11s %6s %4s ", ('user_name', 'ssn', 'source', 'type'),
            hdr="%-6s %-11s %6s %4s" % ('UserID', 'Personnr', 'Source', 'Type')
        )
    )

    def misc_list_legacy_user(self, operator, personid):
        # TODO: This method leaks personal information
        return list_legacy_users(self.db, personid)
