import mx.BeeBase.BeeDict

def test():
    d = mx.BeeBase.BeeDict.BeeDict('testjohn.dat')
    d['Marc9']='Sveta'
    d.commit()
    d.close()

    d = mx.BeeBase.BeeDict.BeeDict('testjohn.dat')
    print 'original',d['Marc9']
    d['Marc9']='betty1'
    d.commit()
    print 'dict change\t',d.changed(),d['Marc9']

    del(d['Marc9'])
    d.commit()
    d['Marc9']='betty2'
    print 'del dict change\t',d.changed(),d['Marc9']
    d.close()


test()
