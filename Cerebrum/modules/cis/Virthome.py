from Cerebrum.Errors import NotFoundError, CerebrumRPCException
from Cerebrum.modules.cis.Utils import CisModule, commit_handler
from Cerebrum.modules.virthome.base import VirthomeBase, VirthomeUtils

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
        
        # FIXME: Move to config?
        creator_name = 'webapp'

        try:
            creator.find(creator_name)
        except NotFoundError:
            raise CerebrumRPCException(
                "Could not find creator account (%s)" % creator_name)

        owner = creator
        #try:
            #owner.find_by_name(creator_name)
        #except NotFoundError:
            #raise CerebrumRPCException(
                #"Could not find account with name (%s)" % owner_name)

        new_group = self.virthome.group_create(group_name, description, creator,
                                               owner, url, forward)
        self.log.info('Group (%s) created by (%s)' % (group_name, owner_name))
        return {'group_id': new_group.entity_id, 
                'group_name': new_group.group_name}


    @commit_handler(dryrun=dryrun)
    def group_invite_user(self, group_name, email, timeout=3):
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
        
        return self.virthome.group_invite_user(group, email, timeout)


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

