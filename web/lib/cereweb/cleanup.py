from mod_python import apache
from time import strftime

def cleanuphandler(req):
    log = open("/tmp/cleanup", "a")
    log.write("Cleanup started at %s\n" %  strftime("%Y-%m-%d %H:%M:%S"))
    log.close()
    try:
        sess = req.session
    except:
        pass
    else:
        sess.save()
        sess.unlock()
        del sess
        del req.session        
    return apache.OK       

# arch-tag: 9890c009-9dab-4207-aeec-604d91ee1e7d
