
import cereconf
from Cerebrum.modules import Email
from Cerebrum.Utils import Factory
from Cerebrum import Errors

logger = Factory.get_logger("console")

class Builder(object):
    def __init__(self, db, creator_id):
        self.db = db
        self.account = Factory.get("Account")(db)
        self.posixuser = Factory.get("PosixUser")(db)
        self.person = Factory.get("Person")(db)
        self.group = Factory.get("Group")(db)
        self.emailtarget = Email.EmailTarget(db)
        self.emailprimaryaddr = Email.EmailPrimaryAddressTarget(db)
        self.emailaddr = Email.EmailAddress(db)
        self.emailserver = Email.EmailServer(db)
        self.emaildomain = Email.EmailDomain(db)
        self.creator_id = creator_id
        self._make_ou_cache(db)
        self.const = self.account.const

    def build_from_owner(self, owner_id):
        owner = self._get_owner(owner_id)

        accounts = self.account.search(owner_id=owner_id)
        if accounts:
            for a in accounts:
                self._build_account(a['account_id'], owner)
        else:
            account_id = self._create_account(owner)
            self._build_account(account_id, owner)
    
    def rebuild_account(self, account_id):
        self._build_account(account_id)
            
    def rebuild_all_accounts(self):
        for a in self.account.list():
            if not a['np_type']:
                self._build_account(a['account_id'])

    def _build_account(self, account_id, owner=None):
        # Add new personaffiliations to account!
        self.account.clear()
        self.account.find(account_id)
        
        if not owner:
            owner = self._get_owner(self.account.owner_id)

        self._build_account_affiliations(owner)

        accountprio = list(self.account.get_account_types())
        accountprio.sort(key=lambda ap: ap['priority'])
        if not accountprio:
            return

        primarygroup_id = self._build_group_membership(accountprio)
        if not primarygroup_id:
            logger.warn("Cannot find a primary group for account %s.",
                        self.account.account_name)
            return

        self._build_posix(primarygroup_id)
        self._build_spreads(accountprio)
        self._build_email(owner, accountprio)

    def _build_account_affiliations(self, owner):
        uninheritedaffs = owner['personaffs'] - owner['allaccountaffs']
        self._add_account_affiliations(uninheritedaffs)

    def _build_group_membership(self, accountprio):
        """Add group memberships requested by accountprio/config.
        Return suggestion for default group.
        The last entries of accountprio are the first priorites. 
        """
        primary_group_id = None
        primary_group_name = None
        new_groups = set()
        for ap in reversed(accountprio):
            aff_groups = self.map_affiliation_to_groups(
                ap['ou_id'], ap['affiliation'])
            new_groups.update(aff_groups)
            if aff_groups:
                primary_group_name = aff_groups[0]
        old_groups = set()
        for g in self.group.search_members(member_id=self.account.entity_id):
            old_groups.add(g['group_name'])
            if g['group_name'] == primary_group_name:
                primary_group_id = g['group_id']
                              
        
        for group_name in new_groups - old_groups:
            self.group.clear()
            self.group.find_by_name(group_name)
            logger.info("Adding %s to group %s",
                        self.account.account_name,
                        self.group.group_name)
            self.group.add_member(self.account.entity_id)
            if group_name == primary_group_name:
                primary_group_id = self.group.entity_id
        return primary_group_id

    def _build_posix(self, primarygroup_id):
        self.posixuser.clear()
        try:
            self.posixuser.find(self.account.entity_id)
        except Errors.NotFoundError:
            posix_uid = self.posixuser.get_free_uid()
            logger.info("Promoting %s to posix, uid %d, group %d",
                        self.account.account_name,
                        posix_uid, primarygroup_id)
            self.posixuser.populate(posix_uid=posix_uid,
                                    gid_id=primarygroup_id,
                                    gecos=None,
                                    shell=self.const.posix_shell_bash,
                                    parent=self.account.entity_id)
            self.posixuser.write_db()
        
    def _build_spreads(self, accountprio):
        """Add spreads requested by config for accountprio"""
        new_spreads = set()
        for ap in accountprio:
            s = self.map_affiliation_to_spread(ap['ou_id'], ap['affiliation'])
            new_spreads |= set(map(self.const.Spread, s))
        
        old_spreads = set([s['spread'] for s in self.account.get_spread()])
        add_spreads = new_spreads - old_spreads
        if add_spreads:
            logger.info("Adding spreads for %s: %s",
                        self.account.account_name,
                        ", ".join([str(s) for s in add_spreads]))
            for s in add_spreads:
                self.account.add_spread(s)
            self.account.write_db()
        # XXX Delete/expire some managed spreads later?

    def _build_email(self, owner, accountprio):
        """Build email for user."""
        primaryaff = accountprio[0]

        emailconf = self.map_affiliation_to_email(
            primaryaff['ou_id'], primaryaff['affiliation'])
        if not emailconf:
            logger.debug("No email for account %s",
                         self.account.account_name)
            return

        (emailserver, emaildomain, addrtype) = emailconf

        # Find or make an emailtarget.
        # XXX Should handle multiple emailtargets per account.
        self.emailtarget.clear()
        try:
            self.emailtarget.find_by_target_entity(self.account.entity_id)
            logger.debug("Using existing emailtarget for account %s",
                         self.account.account_name);
        except Errors.NotFoundError:
            logger.info("Adding emailtarget for %s on server %s",
                        self.account.account_name,
                        emailserver)
            self.emailserver.clear()
            self.emailserver.find_by_name(emailserver)
            self.emailtarget.populate(
                type=self.const.email_target_account,
                target_entity_id=self.account.entity_id,
                target_entity_type=self.account.entity_type,
                server_id=self.emailserver.entity_id)
            self.emailtarget.write_db()

        # Find or make an email address on the requested domain.
        for addr in self.emailtarget.get_addresses():
            if addr['domain'] == emaildomain:
                logger.debug("Account %s already has address %s@%s",
                             self.account.account_name,
                             addr['local_part'], emaildomain)
                self.emailaddr.clear()
                self.emailaddr.find(addr['address_id'])
                break
        else:
            if addrtype == "uname":
                local_parts = [self.account.account_name]
            elif addrtype == "fullname":
                fname = owner['fname']
                lname = owner['lname']
                local_parts = self.generate_email_addresses(fname, lname)
            self.emaildomain.clear()
            self.emaildomain.find_by_domain(emaildomain)
            for local_part in local_parts:
                try:
                    self.emailaddr.clear()
                    self.emailaddr.find_by_local_part_and_domain(
                        local_part, self.emaildomain.entity_id)
                except Errors.NotFoundError:
                    logger.info("Creating email address for %s: %s@%s",
                                self.account.account_name,
                                local_part,
                                self.emaildomain.email_domain_name)
                    self.emailaddr.populate(
                        local_part=local_part,
                        domain_id=self.emaildomain.entity_id,
                        target_id=self.emailtarget.entity_id)
                    self.emailaddr.write_db()
                    break
                else:
                    logger.warn("Could not create email for %s: "+
                                "local_part suggestions exhausted",
                                self.account.account_name);
                    return

        self.emailprimaryaddr.clear()
        # Set primary address of target if required
        try:
            self.emailprimaryaddr.find(self.emailtarget.entity_id)
            logger.debug("Account %s already has primary email address, "+
                         "leaving untouched",
                         self.account.account_name)
        except Errors.NotFoundError:
            logger.info("Setting primary address for %s to %s",
                        self.account.account_name,
                        self.emailaddr.get_address())
            self.emailprimaryaddr.populate(
                self.emailaddr.entity_id,
                self.emailtarget.entity_id)
            self.emailprimaryaddr.write_db()
                
    def _add_account_affiliations(self, affs):
        if affs:
            logger.info("Adding affiliations for %s: %s",
                        self.account.account_name,
                        ", ".join(["%s:%s" % (
                            self.const.PersonAffiliation(aff),
                            self.ou_acronym.get(ou_id, ou_id))
                                   for aff, ou_id in affs]))
            for aff, ou_id in affs:
                self.account.set_account_type(ou_id, aff)
            self.account.write_db()

    def _make_ou_cache(self, db):
        ou = Factory.get("OU")(db)

        ou_by_id = {}
        ou_acros = set()
        self.ou_acronym = {}
        for o in ou.list_all():
            acronym = o['acronym']
            id = o['ou_id']
            ou_by_id[id] = o
            if acronym:
                self.ou_acronym[id] = acronym
                assert acronym not in ou_acros
                ou_acros.add(acronym)
            else:
                self.ou_acronym[id] = str(id)
                

        parents = {}
        for m in ou.get_structure_mappings(ou.const.perspective_kjernen):
            parents[m['ou_id']] = m['parent_id']
        
        self.ou_recursive_cache = {}
        for o in ou_by_id.values():
            id = o['ou_id']
            
            self.ou_recursive_cache[id] = []
            if o['acronym']:
                self.ou_recursive_cache[id].append(o['acronym'])
            p = parents.get(id)
            while p:
                if ou_by_id[p]['acronym']:
                    self.ou_recursive_cache[id].append(ou_by_id[p]['acronym'])
                p = parents.get(p)
            
    def _parse_config_map(self, confmap, ou_id, affiliation):
        acronyms = self.ou_recursive_cache[ou_id]
        affiliation = self.const.PersonAffiliation(affiliation).str
        logger.debug("Checking rules for %s %s", "/".join(acronyms), affiliation)
        for acronym in acronyms:
            if (affiliation, acronym) in confmap:
                yield confmap[affiliation, acronym]
        if (affiliation, None) in confmap:
            yield confmap[affiliation, None]
        for acronym in acronyms:
            if (None, acronym) in confmap:
                yield confmap[None, acronym]
        if (None, None) in confmap:
            yield confmap[None, None]

    def _get_person_affiliations(self, owner_id):
        self.person.clear()
        self.person.find(owner_id)

        person_affs = set()
        for aff in self.person.get_affiliations():
            person_affs.add((aff['affiliation'], aff['ou_id']))
        return person_affs
    
    def _get_all_account_affiliations(self, owner_id):
        account_affs = set()
        for aff in self.account.get_account_types(
              all_persons_types=True,
              owner_id=owner_id):
            account_affs.add((aff['affiliation'], aff['ou_id']))
        return account_affs

    def _remove_account_affiliations(self, affs):
        const = self.account.const
        for aff in self.account.get_account_types():
            if (aff['affiliation'], aff['ou_id']) not in affs:
                logger.info("Removing affiliation for %s: %s:%s",
                            self.account.account_name,
                            const.PersonAffiliation(aff),
                            self.ou_acronym.get(ou_id, ou_id))
                self.account.del_account_type(aff['ou_id'], aff['affiliation'])
                
        

    def _create_account(self, owner):
        uname = self.account.suggest_unames(
            self.const.account_namespace,
            owner['fname'], owner['lname'], maxlen=8)[0]
        logger.info("Creating account %s", uname)
            
        self.account.clear()
        self.account.populate(name=uname, 
                              owner_type=owner['type'],
                              owner_id=owner['id'],
                              np_type=None,
                              creator_id=self.creator_id,
                              expire_date=None)
        self.account.write_db()
        return self.account.entity_id

    def map_affiliation_to_groups(self, ou_id, affiliation):
        try:
            return self._parse_config_map(cereconf.BUILD_GROUP,
                                          ou_id, affiliation).next()
        except StopIteration:
            return ()

    def map_affiliation_to_spread(self, ou_id, affiliation):
        try:
            return self._parse_config_map(cereconf.BUILD_SPREAD,
                                          ou_id, affiliation).next()
        except StopIteration:
            return ()

    def map_affiliation_to_email(self, ou_id, affiliation):
        try:
            return self._parse_config_map(cereconf.BUILD_EMAIL,
                                          ou_id, affiliation).next()
        except StopIteration:
            return None

    def generate_email_addresses(self, fname, lname):
        lname = self.account.simplify_name(lname, alt=0)
        lnames = lname.split(" ")

        fname = self.account.simplify_name(fname, alt=0)
        fnames = fname.split(" ")
        fname = fnames[0]
        mnames = fnames[1:]
        initials = [i[0] for i in mnames]

        for i in range(len(mnames)+1):
            yield ".".join([fname] + mnames[:i] +
                           initials[i:] + lnames)

        yield ".".join([fname]+lnames)
        i=2
        while True:
            yield ".".join([fname]+[str(i)]+lnames)
            i+=1

    def _get_owner(self, owner_id):
        self.person.clear()
        self.person.find(owner_id)

        fname = self.person.get_name(self.const.system_cached,
                                     self.const.name_first)
        lname = self.person.get_name(self.const.system_cached,
                                     self.const.name_last)
        personaffs = self._get_person_affiliations(owner_id)
        allaccountaffs = self._get_all_account_affiliations(owner_id)

        return {
            'id': owner_id,
            'type': self.person.entity_type,
            'fname': fname,
            'lname': lname,
            'personaffs': personaffs,
            'allaccountaffs': allaccountaffs,
        }
