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
    acc_dict = {}
    for x in account.list_accounts_by_type(person_id=row['person_id']):
	str1 = str(x['ou_id']) + ':' + str(x['affiliation'])
	if acc_dict.has_key(int(x['account_id'])):
	    acc_dict[int(x['account_id'])].append(str1)
	else:
	    acc_dict[int(x['account_id'])] = [str1,]
    for r in person.get_affiliations():
	for account_row in accounts:
	    if acc_dict.has_key(int(account_row['account_id'])) \
			and (str(r["ou_id"]) + ':' + str(r['affiliation'])) \
			in acc_dict[int(account_row['account_id'])]:
		#logger.debug5("Propper account_type already exist")
		continue
	    account_id = account_row["account_id"]
	    account.clear()
	    account.find(account_id)
	    account.set_account_type(r["ou_id"], r["affiliation"])
	    logger.debug5("Account type set for person: |%s|, ou: |%s|  and affiliation: |%s|",
			  row["person_id"], r["ou_id"], r["affiliation"])	    
	    account.write_db()
    
db.commit()

# arch-tag: 0e2a514f-f354-4279-b603-73ac3577447c
