# A very crude script that sets account types based om data from FS
# Will be worked through very soon

import cerebrum_path
import cereconf
from Cerebrum import Utils
from Cerebrum.modules.no.hia import Constants


db = Utils.Factory.get("Database")()
person = Utils.Factory.get("Person")(db)
logger = Utils.Factory.get_logger("console")
account = Utils.Factory.get("Account")(db)
const = Utils.Factory.get("Constants")(db)
db.cl_init(change_program='account_type_FS')
for row in person.list_external_ids(const.system_fs,
                                    const.externalid_fodselsnr):
    accounts = account.list_accounts_by_owner_id(row["person_id"])
    if not accounts:
	logger.warn("Person |%s| has no accounts. Skipped.", row["person_id"])
	continue
    logger.debug5("Person %s has %d accounts.", row["person_id"], len(accounts))
    person.clear()
    person.find(row["person_id"])
    for r in person.get_affiliations():
	for account_row in accounts:
	    account_id = account_row["account_id"]
	    account.clear()
	    account.find(account_id)
	    account.set_account_type(r["ou_id"], r["affiliation"])
	    logger.debug5("Account type set for person: |%s|, ou: |%s|  and affiliation: |%s|",
			  row["person_id"], r["ou_id"], r["affiliation"])	    
	    account.write_db()
    
db.commit()
