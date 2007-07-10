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

def fixgrp(i):
    g.clear()
    g.find(i)
    name=g.get_name(co.group_namespace)
    if name[:2] == "g_":
        g2.clear()
        try:
            g2.find_by_name(name[2:])
        except Errors.NotFoundError:
            # rename g
            try:
                a.clear()
                a.find_by_name(name[2:])
            except Errors.NotFoundError:
                g.delete_entity_name(co.group_namespace)
                g.add_entity_name(co.group_namespace, name[2:])
                g.write_db()
            else:
                pass
        else:
            # move all stuff from g to g2...
            # make g2 posix if g1 is.
            pg.clear()
            pg2.clear()
            try:
                pg.find(g.entity_id)
            except Errors.NotFoundError:
                pass # Neither is
            else:
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
            
            # move members ...
            gmemb = g.list_members(filter_expired=False)
            gmemb2 = g2.list_members(filter_expired=False)
            for i,op in ((0, co.group_memberop_union),
                         (1, co.group_memberop_intersection),
                         (2, co.group_memberop_difference)):
                for m in gmemb[i]:
                    # Add to new group
                    entity_type=m[0]
                    entity_id=m[1]
                    if not m in gmemb2[i]:
                        g2.add_member(entity_id, entity_type, op)
                        g2.write_db()
                    
                    # change primary
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
                    g.remove_member(entity_id, op)
            pg.delete()


for i in g.list_all_grp():
    try:
        fixgrp(i[0])
    except db.IntegrityError:
        db.rollback()
    else:
        db.commit()

