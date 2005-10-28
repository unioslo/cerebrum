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
