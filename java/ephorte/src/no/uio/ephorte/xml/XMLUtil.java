package no.uio.ephorte.xml;

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
        return a == b || (a != null && a.equals(b));
    }
}
