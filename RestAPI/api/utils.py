from flask.ext.restful import abort
from api import db

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email


from Cerebrum.modules.bofhd.auth import (BofhdAuthOpSet,
                                         BofhdAuthOpTarget,
                                         BofhdAuthRole)


co = Factory.get('Constants')(db.connection)


class EntityLookupError(Exception):
    """Raised when an entity lookup failed for whatever reason.
    This message is passed on to the user when abort()ing."""
    pass


def get_account(identifier, idtype=None, actype='Account'):
    """Fetch an account by name, ID or POSIX UID.

    :param str identifier: The identifier for the account to be retrived
    :param str idtype: The identifier type. Can be 'name', 'entity_id' or 'posix_uid'
    :param str actype: The wanted account subclass
    :rtype: Account or PosixUser
    :return: The account object associated with the specified identifier, or an exception.
    """
    if actype == 'Account':
        account = Factory.get('Account')(db.connection)
    elif actype == 'PosixUser':
        account = Factory.get('PosixUser')(db.connection)

    try:
        if idtype == 'name':
            account.find_by_name(identifier, co.account_namespace)
        elif idtype == 'entity_id':
            if isinstance(identifier, str) and not identifier.isdigit():
                raise EntityLookupError(u"entity_id must be a number")
            account.find(identifier)
        elif idtype == 'posix_uid':
            if isinstance(identifier, str) and not identifier.isdigit():
                raise EntityLookupError(u"posix_uid must be a number")
            if actype != 'PosixUser':
                account = Factory.get('PosixUser')(db.connection)
                account.clear()
            account.find_by_uid(identifier)
        else:
            raise EntityLookupError(u"Invalid identifier type {}".format(idtype))
    except Errors.NotFoundError:
        raise EntityLookupError(u"No such {} with {}={}".format(actype, idtype, identifier))

    return account


def get_group(identifier, idtype=None, grtype='Group'):
    """Fetch a group by name, ID or POSIX GID.

    :param str identifier: The identifier for the group to be retrived
    :param str idtype: The identifier type. Can be 'name', 'entity_id' or 'posix_gid'
    :param str actype: The wanted group subclass
    :rtype: Group or PosixGroup
    :return: The group object associated with the specified identifier, or an exception.
    """
    group = None
    if grtype == 'Group':
        group = Factory.get('Group')(db.connection)
    elif grtype == 'PosixGroup':
        group = Factory.get('PosixGroup')(db.connection)
    elif grtype == 'DistributionGroup':
        group = Factory.get('DistributionGroup')(db.connection)
    else:
        raise EntityLookupError(u"Invalid group type {}".format(grtype))

    try:
        if idtype == "name":
            group.find_by_name(identifier)
        elif idtype == "entity_id":
            group.find(identifier)
        elif idtype == "posix_gid" and grtype == 'PosixGroup':
            group.find_by_gid(identifier)
        else:
            raise EntityLookupError(u"Invalid identifier type '{}'".format(idtype))
    except Errors.NotFoundError:
        raise EntityLookupError(u"Could not find a {} with {}={}".format(
            grtype, idtype, identifier))

    return group


def get_entity(identifier=None, entype=None, idtype=None):
    """Fetches an entity.

    :param str identifier: The identifier for the entity to be retrived
    :param str/None entype: The entity type. If None, 'identifier' is assumed to be numeric,
                            and the subclassed object is returned.
    :param str idtype: The identifier type

    :rtype: Entity or one of its subclasses
    :return: The entity object
    """
    if identifier is None:
        raise EntityLookupError(u"Missing identifier")
    if entype == 'account':
        return get_account(idtype=idtype, identifier=identifier)
    # if entype == 'person':
    #     return self._get_person(*self._map_person_id(identifier))
    # if entype == 'group':
    #     return self._get_group(identifier)
    # if entype == 'stedkode':
    #     return self._get_ou(stedkode=identifier)
    # if entype == 'host':
    #     return self._get_host(identifier)
    if entype is None:
        try:
            int(identifier)
        except ValueError:
            raise EntityLookupError(u"Expected numeric identifier")
        en = Factory.get('Entity')(db.connection)
        return en.get_subclassed_object(identifier)
    raise EntityLookupError(u"Invalid entity type {}".format(entype))


def get_entity_name(entity):
    """Looks up the name of an entity object. If 'entity' is numeric, the object is retrived
    from the database.

    :param Entity/int/long entity: The entity object or its ID
    :rtype: str
    :return: The name of the entity
    """
    if isinstance(entity, (int, long)):
        entity_obj = Factory.get('Entity')(db.connection)
        try:
            entity_obj.find(entity)
            entity = entity_obj.get_subclassed_object()
        except Errors.NotFoundError:
            return None
    name = None
    if entity.entity_type == co.entity_account:
        name = entity.account_name
    elif entity.entity_type == co.entity_group:
        name = entity.group_name
    return name


# Used to find auth role owners. Should probably be moved somewhere else.
# For example (entity_id=group_id, target_type='group') will find group moderators.
def get_auth_owners(entity, target_type):
    aot = BofhdAuthOpTarget(db.connection)
    ar = BofhdAuthRole(db.connection)
    aos = BofhdAuthOpSet(db.connection)
    targets = []
    for row in aot.list(target_type=target_type, entity_id=entity.entity_id):
        targets.append(int(row['op_target_id']))

    data = []
    for row in ar.list_owners(targets):
        print dict(row)
        aos.clear()
        aos.find(row['op_set_id'])
        entity_id = int(row['entity_id'])
        en = get_entity(identifier=entity_id)
        if en.entity_type == co.entity_account:
            owner_id = en.account_name
        elif en.entity_type == co.entity_group:
            owner_id = en.group_name
        else:
            owner_id = entity_id
        data.append({
            'type': en.entity_type,
            'owner_id': owner_id,
            'operation_name': aos.name
        })
