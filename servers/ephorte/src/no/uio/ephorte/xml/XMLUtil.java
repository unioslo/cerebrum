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
        if(data == null) data = "";
        xmlData.append("<" + element + ">" + xmlify(data) + "</" + element + ">\n");
    }

    public String toString() {
        return xmlData.toString() /* .replaceAll("\n", "") */;
    }

    protected String xmlify(String data) {
	// Not very clever, but this class is kind of silly anyway.
	// We need to escape certain characters in xml data.
	data = data.replaceAll("&", "&amp;");
	data = data.replaceAll("<", "&lt;");
	data = data.replaceAll(">", "&gt;");
	data = data.replaceAll("\"", "&quot;");
	data = data.replaceAll("'", "&#39;");
	return data;
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
