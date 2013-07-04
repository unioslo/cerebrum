from mx.TextTools.Examples.HTML import *

def test():
    text = """<frame noresize>"""

    utext = upper(text)
    print "UPPER:", utext
    result, taglist, nextindex = tag(utext,htmltable)
    print_tags(text,taglist)

    print
    utext = lower(text)
    print "LOWER", utext
    result, taglist, nextindex = tag(utext,htmltable)
    print_tags(text,taglist)

test()
