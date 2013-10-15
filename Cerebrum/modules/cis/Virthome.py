from Cerebrum.Errors import NotFoundError, CerebrumRPCException, CerebrumError
from Cerebrum.modules.cis.Utils import CisModule, commit_handler
from Cerebrum.modules.virthome.base import VirthomeBase, VirthomeUtils
from Cerebrum.Utils import Factory

class Virthome(CisModule):
    """ This is the cis interface with Cerebrum for all virthome-related
    functionality.

    Attributes:
        dryrun: If bool(dryrun) is True, nothing gets commited unless
                self.commit is explicitly called.
    """
    dryrun = False

    # FIXME: We don't authenticate pr. user, no operator_id
    def __init__(self, operator_id=None, dryrun=None):
        """Constructor. Since we are using access control, we need the
        authenticated entity's ID as a parameter.
        """
        super(Virthome, self).__init__('cis_virthome')

        self.virthome = VirthomeBase(self.db)
        self.vhutils = VirthomeUtils(self.db)
        self.operator_id = operator_id

        if dryrun is not None:
            self.dryrun = dryrun


    @commit_handler(dryrun=dryrun)
    def fedaccount_assert(self, account_name, email, expire_date=None,
            human_first_name=None, human_last_name=None):
        """ This should be called whenever a FEDAccount logs in in external
        applications. It ensures that the fedaccount also exists in WebID, so
        that we have an entity ID to bind events to.

        This is the equivalent to bofhd_virthome_cmds/user_fedaccount_login
        NOTE: This method does no authentication check, WE NEED TO BE CERTAIN
        THAT THE CALLER HAS AUTHENTICATED THE USER AND USER DATA.

        @type account_name: str
        @param account_name: Desired FEDAccount name. If unavailable, we'll
                             encounter an error.

        @type email: str
        @param email: The FEDAccount owner's e-mail address.

        @type expire_date: mx.DateTime.DateTime 
        @param expire_date: Expiration date for the FEDAccount we are about to
                            create.

        @type human_first_name: str
        @param human_first_name: The first name(s) of the account owner

        @type human_last_name: str
        @param human_last_name: The last name(s) of the account owner

        @rtype: bool
        @return: True if the account already existed, False if the account just
                 got created
        """
        # TODO: This method should be moved to modules/virthome/base.py
        if not self.vhutils.account_exists(account_name):
            self.vhutils.create_fedaccount(account_name, email, expire_date,
                    human_first_name, human_last_name)
            self.log.info("FEDAccount %s created" % account_name)
            return False

        ac = Factory.get('Account')(self.db)
        co = Factory.get('Constants')(self.db)
        try:
            ac.find_by_name(account_name)
        except NotFoundError:
            raise CerebrumRPCException(
                    "Could not find account (%s), should exist!" % account_name)

        # Account exists, check if email / name has changed
        if email and ac.get_email_address() != email:
            ac.set_email_address(email)
        if human_first_name and ac.get_owner_name(co.human_first_name) != human_first_name:
            ac.set_owner_name(co.human_first_name, human_first_name)
        if human_last_name and ac.get_owner_name(co.human_last_name) != human_last_name:
            ac.set_owner_name(co.human_last_name, human_last_name)

        ac.extend_expire_date()
        ac.write_db()

        return True
    

    @commit_handler(dryrun=dryrun)
    def group_create(self, group_name, description, owner_name, url=None, forward=None):
        """ This is a wrapper for the method of the same name in
        VirthomeBase. This method looks up the C{owner_name} and handles
        commit/rollback.

        See L{Cerebrum.modules.virthome.base.VirthomeBase} for more.
        """
        creator = self.virthome.account_class(self.db)
        owner = self.virthome.account_class(self.db)

        # Normally, we might want to use owner_name to set the actuall group
        # owner. However, we log the name to the twisted logger, and use the
        # creator, as there's no guarantee that the owner_name exist.
        #
        # For now, that's accepted behaviour. If this module is ever used for
        # something other than personreg, we might want to change this
        # behaviour.
        #
        
        if self.vhutils.group_exists(group_name):
            raise CerebrumRPCException("Group name '%s' already exists" % group_name)

        # FIXME: Move to config?
        creator_name = 'webapp'

        try:
            creator.find_by_name(creator_name)
        except NotFoundError:
            raise CerebrumRPCException(
                "Could not find creator account (%s)" % creator_name)

        owner = creator
        #try:
            #owner.find_by_name(creator_name)
        #except NotFoundError:
            #raise CerebrumRPCException(
                #"Could not find account with name (%s)" % owner_name)
        try:
            new_group = self.virthome.group_create(group_name, description,
                                                   creator, owner, url,
                                                   forward)
        except CerebrumError, e:
            raise CerebrumRPCException(
                "Could not create group '%s' - %s" % (group_name, str(e)))

        self.log.info('Group (%s) created by (%s)' % (group_name, owner_name))
        return {'group_id': new_group.entity_id, 
                'group_name': new_group.group_name}


    @commit_handler(dryrun=dryrun)
    def group_invite_user(self, group_name, inviter_name, email, timeout=3):
        """ This is a wrapper for the method of the same name in
        VirthomeBase. This method looks up the C{group_name} and handles
        commit/rollback.

        See L{Cerebrum.modules.virthome.base.VirthomeBase} for more.
        """
        inviter = self.virthome.account_class(self.db)
        try:
            inviter.find_by_name(inviter_name)
        except NotFoundError:
            raise CerebrumRPCException("Could not find account (%s)" % inviter_name)

        group = self.virthome.group_class(self.db)
        try:
            group.find_by_name(group_name)
        except NotFoundError:
            raise CerebrumRPCException("Could not find group (%s)" % group_name)
        
        return self.virthome.group_invite_user(inviter, group, email, timeout)


    @commit_handler(dryrun=dryrun)
    def group_disable(self, group_name):
        """ This is a wrapper for the method of the same name in
        VirthomeBase. This method looks up the C{group_name} and handles
        commit/rollback.

        See L{Cerebrum.modules.virthome.base.VirthomeBase} for more.
        """
        group = self.virthome.group_class(self.db)
        
        try:
            group.find_by_name(group_name)
        except NotFoundError:
            raise CerebrumRPCException("Could not find group (%s)" % group_name)

        return self.virthome.group_disable(group)


    def list_group_members(self, group_name):
        """ This is a wrapper for the method of the same name in
        VirthomeUtils. This method looks up the C{group_name}.

        See L{Cerebrum.modules.virthome.base.VirthomeUtils} for more.
        """
        group = self.virthome.group_class(self.db)
        
        try:
            group.find_by_name(group_name)
        except NotFoundError:
            raise CerebrumRPCException("Could not find group (%s)" % group_name)

        return self.vhutils.list_group_members(group)


    def list_group_memberships(self, account_name):
        """ This is a wrapper for the method of the same name in
        VirthomeUtils. This method looks up the C{account_name}

        See L{Cerebrum.modules.virthome.base.VirthomeUtils} for more.
        """
        account = self.virthome.account_class(self.db)
        
        try:
            account.find_by_name(account_name)
        except NotFoundError:
            raise CerebrumRPCException("Could not find account (%s)" % account_name)

        return self.vhutils.list_group_memberships(account)

