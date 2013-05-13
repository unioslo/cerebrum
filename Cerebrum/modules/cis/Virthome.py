from Cerebrum.Errors import NotFoundError, CerebrumRPCException
from Cerebrum.modules.cis.Utils import CisModule, commit_handler
from Cerebrum.modules.virthome.base import VirthomeBase

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
        self.operator_id = operator_id

        if dryrun is not None:
            self.dryrun = dryrun
    
    @commit_handler(dryrun=dryrun)
    def group_create(self, group_name, description, owner_name, url=None, forward=None):
        """ This is a wrapper for the method of the same name in
        Cerebrum.modules.virthome.Utils.VirthomeApi. It looks up the
        L{owner_name} and C{creator_id}, which are neccessary to populate a new
        group, and set up access control.

        See L{Cerebrum.modules.virthome.Utils.VirthomeApi.group_create} for more.
        """
        creator = self.virthome.account_class(self.db)
        owner = self.virthome.account_class(self.db)

        # TODO: What should the creator/owner be? operator_id will disappear.
        creator_id = self.operator_id
        try:
            creator.find(creator_id)
        except NotFoundError:
            raise CerebrumRPCException(
                "Could not find creator account (id %d)" % creator_id)

        try:
            owner.find_by_name(owner_name)
        except NotFoundError:
            raise CerebrumRPCException(
                "Could not find account with name (%s)" % owner_name)

        new_group = self.virthome.group_create(group_name, description, creator,
                                               owner, url, forward)
        return {'group_id': new_group.entity_id, 
                'group_name': new_group.group_name}


    @commit_handler(dryrun=dryrun)
    def group_invite_user(self, group_name, email, timeout=3):
        """ This is a wrapper for the method of the same name in
        Cerebrum.modules.virthome.Utils.VirthomeApi. It looks up the
        C{group_name}.

        See L{Cerebrum.modules.virthome.Utils.VirthomeApi.group_invite_user} for more.
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
        Cerebrum.modules.virthome.Utils.VirthomeApi. It looks up the
        C{group_name}

        See L{Cerebrum.modules.virthome.Utils.VirthomeApi.group_disable} for more.
        """
        group = self.virthome.group_class(self.db)
        
        try:
            group.find_by_name(group_name)
        except NotFoundError:
            raise CerebrumRPCException("Could not find group (%s)" % group_name)

        return self.virthome.group_disable(group)

    def list_group_members(self, group_name):
        """ This is a wrapper for the method of the same name in
        Cerebrum.modules.virthome.Utils.VirthomeApi. It looks up the
        C{group_name}

        See L{Cerebrum.modules.virthome.Utils.VirthomeApi.group_disable} for more.
        """
        group = self.virthome.group_class(self.db)
        
        try:
            group.find_by_name(group_name)
        except NotFoundError:
            raise CerebrumRPCException("Could not find group (%s)" % group_name)

        return self.vhutils.list_group_members(group)

    def list_group_memberships(self, username):
        """ This is a wrapper for the method of the same name in
        Cerebrum.modules.virthome.Utils.VirthomeApi. It looks up the
        C{group_name}

        See L{Cerebrum.modules.virthome.Utils.VirthomeApi.group_disable} for more.
        """
        account = self.virthome.account_class(self.db)
        
        try:
            account.find_by_name(username)
        except NotFoundError:
            raise CerebrumRPCException("Could not find account (%s)" % username)

        return self.vhutils.list_group_memberships(account)

