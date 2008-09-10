import cerebrum_path
from Cerebrum import Errors
from Cerebrum.Utils import Factory

db=Factory.get("Database")()
co=Factory.get("Constants")(db)
a=Factory.get("Account")(db)
g=Factory.get("Group")(db)
g2=Factory.get("Group")(db)
pu=Factory.get("PosixUser")(db)
pg=Factory.get("PosixGroup")(db)
pg2=Factory.get("PosixGroup")(db)
db.cl_init(change_program="rename_groups")

def rename(group, name):
    # Only if the name is not taken...
    try:
        a.clear()
        a.find_by_name(name)
    except Errors.NotFoundError:
        group.delete_entity_name(co.group_namespace)
        group.add_entity_name(co.group_namespace, name)
        group.write_db()
    else:
        pass


def fixgrp(i):
    g.clear()
    g.find(i)
    name=g.get_name(co.group_namespace)
    if name[:2] == "g_":
        g2.clear()
        try:
            g2.find_by_name(name[2:])
        except Errors.NotFoundError:
            rename(g, name[2:])
        else:
            pg.clear()
            is_posix=False
            try:
                pg.find(g.entity_id)
            except Errors.NotFoundError:
                pass
            else:
                is_posix=True
                move_posix(pg, g2)
            move_members(g, g2)
            if is_posix:
                pg.delete_posix()
            g.delete()

def move_posix(pg, g2):
    # move all stuff from g to g2...
    # make g2 posix if g1 is.
    pg2.clear()
    try:
        pg2.find(g2.entity_id)
    except Errors.NotFoundError:
        gid = g.posix_gid
        tmpgid = gid + 100000
        found_free = False
        while not found_free:
            pg2.clear()
            try:
                pg2.find_by_gid(tmpgid)
            except Errors.NotFoundError:
                found_free = True
            else:
                tmpgid += 1
            pg.posix_gid=tmpgid
            pg.write_db()
            pg2.populate(gid=gid, parent=g2.entity_id)
            pg2.write_db()


def move_members(g, g2):
    """Move members from g to g2."""

    gmemb2 = set(x["member_id"] for x in
                 g2.search_members(group_id=g2.entity_id,
                                   filter_expired=False))
    for member in g.search_members(group_id=g.entity_id, filter_expired=False):
        entity_type = int(member["member_type"])
        entity_id = int(member["member_id"])

        # Add to new group
        if not entity_id in gmemb2:
            g2.add_member(entity_id)
            g2.write_db()

        # Change primary
        if entity_type == co.entity_account:
            pu.clear()
            try:
                pu.find(entity_id)
            except Errors.NotFoundError:
                pass
            else:
                if pu.gid_id == g.entity_id:
                    pu.gid_id = g2.entity_id
                    pu.write_db()

        # Remove from old group
        g.remove_member(entity_id)
# end move_members
    

for i in g.search(filter_expired=False):
    try:
        fixgrp(i["group_id"])
    except db.IntegrityError:
        db.rollback()
    else:
        db.commit()

