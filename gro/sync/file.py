import os


# Need to handle exceptions better
class multihandler:
    def __init__(self, *handlers):
        self.handlers=handlers
    def close(self):
        for h in self.handlers: h.close()
    def add(self, obj):
        for h in self.handlers: h.add(obj)
    def delete(self, obj):
        for h in self.handlers: h.delete(obj)
    def update(self, obj):
        for h in self.handlers: h.update(obj)


class fileback:
    def __init__(self, filename, mode, inkr=False):
        if inkr: throw "foo"
        self.filename=file
        self.tmpname=file + ".tmp." + str(os.getpid())
        self.f=open(self.tmpfile, 'w')
        os.chmod(self.tmpfile, mode)
        self.format=formatpasswd
    def close(self):
        self.f.flush()
        os.fsync(self.f.fileno())
        self.f.close()
        os.rename(self.tmpname, self.filename)
    def add(self, obj):
        self.f.write(self.format(obj))
    def update(self, obj):
        self.records[obj.name]=self.format(obj)
    def delete(self, obj):
        del self.records[obj.name]

class clfileback(fileback):
    def readin(self, srcfile):
        self.records={}
        for l in readlines(open(srcfile)):
            key=l.split(":",1)[0]
            self.records[key]=l
    def writeout(self):
        for l in records.values():
            self.f.write(l)


# classic: name:crypt:uid:gid:gcos:dir:shell
# shadow:  name:crypt:lastchg:min:max:warn:inactive:expire
# bsd:     name:crypt:uid:gid:class:change:expire:gcos:dir:shell

class passwdfile(clfileback):
    filename="/etc/bdb/passwd"
    def format(self, account):
        return "%s:%s:%d:%d:%s:%s:%s\n" % (
            account.name, account.cryptpasswd, account.uid, account.gid,
            account.fullname, account.dir, account.shell )


class groupfile(clfileback):
    filename="/etc/bdb/group"
    def format(self, group):
        return "%s:*:%d:%s\n" % (
            group.name, group.gid, ",".join(group.members) )


class shadowfile(clfileback):
    filename="/etc/bdb/shadow"
    def format(self, account):
        return "%s:%s:::::::" % ( account.name, account.cryptpasswd )


class aliasfile(cflfileback):
    filename="/etc/bdb/aliases"
    def format(self, addr):
        if addr.primary:
            to=addr.user
            mod="<>"
        else:
            to=addr.primary
            mod=">>"
        return "%s: %s %s" % ( addr.name, mod, to)

# arch-tag: 15c0dab6-50e3-4093-ba64-5be1b5789d90
