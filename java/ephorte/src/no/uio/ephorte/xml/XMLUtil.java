package no.uio.ephorte.xml;

import java.util.Date;

import no.uio.ephorte.data.Person;

/**
 * Helper methods for writing properly escaped xml data.
 * 
 * @author runefro
 * 
 */
public class XMLUtil {
    StringBuffer xmlData;

    public XMLUtil() {
        xmlData = new StringBuffer("<?xml version=\"1.0\" standalone=\"yes\"?>\n");
    }

    public void startTag(String string) {
        xmlData.append("<" + string + ">\n");
    }

    public void endTag(String string) {
        xmlData.append("</" + string + ">\n");
    }

    public void writeElement(String element, String data) {
        xmlData.append("<" + element + ">" + data + "</" + element + ">\n");
    }

    public String toString() {
        return xmlData.toString() /* .replaceAll("\n", "") */;
    }

    public static boolean equals(Object a, Object b) {
        // this method does not belong in a class named xml
        if (a instanceof Date && b instanceof Date) {
            Date dA = (Date) a;
            Date dB = (Date) b;
            return Person.dayFormat.format(dA).equals(Person.dayFormat.format(dB));
        }
        return a == b || (a != null && a.equals(b));
    }
}
