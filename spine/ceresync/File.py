import os

def writeFile(filename, lines):
    tmpname = '%s.new.%s' % (filename, os.getpid())
    # FIXME: umask? os.chmod is unsafe
    fd = open(tmpname, 'w')
    fd.writelines(lines)
    fd.flush()
    os.fsync(fd.fileno())
    fd.close()
    os.rename(tmpname, filename)

# arch-tag: 8f9de454-47f8-11da-91ca-0e38a15f3071
