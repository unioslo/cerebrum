import os


# Need to handle exceptions better?
class multihandler:
    def __init__(self, *handlers):
        self.handlers=handlers
	self.active=False
	self.bad=False
    def begin(self):
	if self.bad or self.active: raise "notready"
	try:
            for h in self.handlers: h.begin()
	    self.active=True
	except:
	    self.bad=True
	    raise
    def close(self):
	if self.bad or not self.active: raise "notready"
	try:
           for h in self.handlers: h.close()
	   self.active=False
        except:
	   self.bad=True
	   raise
    def add(self, obj):
	if self.bad or not self.active: raise "notready"
	try:
            for h in self.handlers: h.add(obj)
	except:
	    self.bad=True
	    raise
    def delete(self, obj):
	if self.bad or not self.active: raise "notready"
	try:
            for h in self.handlers: h.delete(obj)
	except:
	    self.bad=True
	    raise
    def update(self, obj):
	if self.bad or not self.active: raise "notready"
	try:
            for h in self.handlers: h.update(obj)
	except:
	    self.bad=True
	    raise
    def abort(self):
	for h in self.handlers:
	    try:
		h.abort()
	    except:
		pass #This is abort, so it's ok.
	self.active=False
	self.bad=False


class fileback:
    def __init__(self, filename=None, mode=0644):
	if filename: self.filename=filename
	self.mode=mode
    def begin(inkr=False)
	self.inkr=inkr
	if self.inkr: self.readin(self.filename)
        self.tmpname=self.filename + ".tmp." + str(os.getpid())
        self.f=open(self.tmpfile, 'w')
        os.chmod(self.tmpfile, mode)
    def close(self):
	if self.inkr: self.writeout()
        self.f.flush()
        os.fsync(self.f.fileno())
        self.f.close()
        os.rename(self.tmpname, self.filename)
    def abort(self):
	self.f.close()
	os.unlink(self.tmpname)
    def add(self, obj):
	if self.inkr:
            self.records[obj.name]=self.format(obj)
	else:
	    self.f.write(self.format(obj))
    def update(self, obj):
	if not self.inkr: raise "not supported in this mode of operation"
        self.records[obj.name]=self.format(obj)
    def delete(self, obj):
	if not self.inkr: raise "not supported in this mode of operation"
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


class aliasfile(clfileback):
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
