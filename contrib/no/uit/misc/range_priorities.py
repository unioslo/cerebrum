import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum import Errors

db = Factory.get("Database")()
db.cl_init(change_program='range_priorities')
person = Factory.get("Person")(db)
account = Factory.get("Account")(db)
const = Factory.get("Constants")(db)
logger = Factory.get_logger("console")
all_accounts = {}

old_account_types = {}
new_account_types = {}

logger.info("Getting all accounts")
all_accounts = account.list(filter_expired=True)

#all_accounts = account.list_accounts_by_type(affiliation=188)

logger.info("Done getting all accounts")

for ac in all_accounts:
    account.clear()
    account.find(int(ac['account_id']))
    logger.info("*******************START***********************************")
    logger.info("Found account |%s| for |%s|" % (account.account_name,
    						 account.owner_id))

    logger.info("Getting account types")
    old_account_types = account.get_account_types()
    logger.info("Rearanging priorities for |%s|.",account.account_name)
    for a in old_account_types:
	logger.info("Setting new priority for affiliation |%d| and ou |%d|, old is |%d|" % 
		    (int(a['affiliation']),int(a['ou_id']),int(a['priority'])))
	try:
	    account.set_account_type(int(a['ou_id']),int(a['affiliation']))
	    account.write_db()
	except Exception,msg:
	    logger.info("Manual intervention required for this user\nReason:%s" % msg)
	continue
    new_account_types = account.get_account_types()
    for n in new_account_types:
	logger.info("New priority %d for affiliation %d to ou %d" % (int(n['priority']),
								     int(n['affiliation']),
								     int(n['ou_id'])))
    logger.info("*******************END*************************************")
db.commit()

