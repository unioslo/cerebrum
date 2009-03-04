



def parsefiles(groupfile, passwdfile):
    memb={}
    gid2name={}
    for line in open(groupfile):
        name, pw, gid, members = line.rstrip('\n').split(':')
        memb.setdefault(name, set()).update(members.split(","))
        gid2name[gid]=name
    for line in open(passwdfile):
        name, pw, uid, gid, gecos, dir, shell = line.rstrip('\n').split(':')
        group=gid2name.get(gid, gid)
        memb.setdefault(group, set()).add(name)
    return memb


def diff(members1, members2):
    only1={}
    only2={}
    
    groups1=set(members1.keys())
    groups2=set(members2.keys())

    empty=set()
    for g in groups1 | groups2:
        memb1 = members1.get(g, empty) - members2.get(g, empty)
        memb2 = members2.get(g, empty) - members1.get(g, empty)
        if memb1:
            only1[g]=memb1
        if memb2:
            only2[g]=memb2

    return (only1, only2)

def inv(members):
    r={}
    for k in members.keys():
        for m in members[k]:
            r.setdefault(m, set()).add(k)
    return r

def main():
    import sys
    groupfile1=sys.argv[1]
    passwdfile1=sys.argv[2]
    groupfile2=sys.argv[3]
    passwdfile2=sys.argv[4]
    
    members1=parsefiles(groupfile1, passwdfile1)
    members2=parsefiles(groupfile2, passwdfile2)

    only1, only2 = diff(members1, members2)
    onlygroups1 = inv(only1)
    onlygroups2 = inv(only2)
    
    for a in onlygroups1:
        print '-'+a+":"+",".join(onlygroups1[a])

    for a in onlygroups2:
        print '+'+a+":"+",".join(onlygroups2[a])


if __name__ == '__main__':
    main()
