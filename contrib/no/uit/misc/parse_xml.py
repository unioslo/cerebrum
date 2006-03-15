
import mx

import xml.sax

class LTDataParser(xml.sax.ContentHandler):
    """This class is used to iterate over all users in LT. """

    def __init__(self, filename, call_back_function):
        self.call_back_function = call_back_function        
        xml.sax.parse(filename, self)

    def startElement(self, name, attrs):
        if name == 'data':
            pass
        elif name in ("arbtlf", "komm", "tils", "bilag",
                      "gjest", "rolle", "res", "permisjon"):
            tmp = {}
            for k in attrs.keys():
                tmp[k] = attrs[k].encode('iso8859-1')
            self.p_data[name] = self.p_data.get(name, []) + [tmp]
        elif name == "person":
            self.p_data = {}
            for k in attrs.keys():
                self.p_data[k] = attrs[k].encode('iso8859-1')
        else:
            logger.warn("WARNING: unknown element: %s" % name)

    def endElement(self, name):
        if name == "person":
            self.call_back_function(self.p_data)


def process_employee(person):
    fnr =("%02d%02d%02d%05d" % (int(person['fodtdag']), int(person['fodtmnd']),
                              int(person['fodtar']), int(person['personnr'])))
    print "fnr = %s" % fnr
def main():
    file = '/cerebrum/var/dumps/employees/uit_persons_20060314.xml'
    LTDataParser(file,process_employee)



if __name__ =='__main__':
    main()
    
