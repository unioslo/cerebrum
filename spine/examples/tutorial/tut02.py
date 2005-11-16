import Spine
session = Spine.login()
tr = session.new_transaction()

# how to create new objects

try:
    # get the `command`-object
    cmd = tr.get_commands()

    # create a new group
    group = cmd.create_group('blapp')
    group.promote_posix()
    print new.get_name(), new.get_posix_gid()

    # cmd can be used to create _new_ objects who has not been given
    # a primary key yet.
    # create_group is more or less a wrapper for:
    # group = Factory.get('Group')(db)
    # group.populate(*args, **vargs)
    #
    # cmd also has other useful methods like
    # get_group_by_name, get_account_by_name
finally:
    tr.rollback() # we are only testing, so don't commit anything
