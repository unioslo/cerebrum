package no.uio.ephorte.connection;

import java.net.MalformedURLException;
import java.rmi.RemoteException;
import java.util.Hashtable;
import java.util.Vector;

import javax.xml.rpc.ServiceException;

import no.gecko.www.ephorte.webservices.GetDataSetResponseGetDataSetResult;
import no.gecko.www.ephorte.webservices.ServicesLocator;
import no.gecko.www.ephorte.webservices.ServicesSoap;

import org.apache.axis.message.MessageElement;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

public class EphorteConnectionImpl extends EphorteConnection {
    String sessionID;
    ServicesSoap service;
    String url;

    public EphorteConnectionImpl(String url) {
        this.url = url;
    }

    protected void connect() {
        ServicesLocator locator = new ServicesLocator();
        try {
            if(url == null) {
                service = locator.getServicesSoap();
            } else {
                service = locator.getServicesSoap(new java.net.URL(url));
            }
            sessionID = service.login("ephsys", "ephsys", "", "UioTest", null);
        } catch (ServiceException e) {
            e.printStackTrace();
            System.exit(1);
        } catch (RemoteException e) {
            e.printStackTrace();
            System.exit(1);
        } catch (MalformedURLException e) {
            e.printStackTrace();
            System.exit(1);
        }
    }

    protected int updatePersonByXML(String xml) throws RemoteException {
        return service.updatePersonByXML(sessionID, xml, "");
    }

    /**
     * Fetches data from the specified ePhorte table, and returns database rows
     * as a Vector of Hashtables
     * 
     * @param criteriaCollectionString
     * @param tagName
     * @return
     * @throws RemoteException
     */
    protected Vector<Hashtable<String, String>> getDataSet(String criteriaCollectionString,
            String tagName) throws RemoteException {
        Vector<Hashtable<String, String>> ret = new Vector<Hashtable<String, String>>();
        GetDataSetResponseGetDataSetResult res = service.getDataSet(sessionID,
                criteriaCollectionString);
        // System.out.println("RES: "+res.toString());
        for (MessageElement me : res.get_any()) {
            // System.out.println("M: "+me.getAsString());
            NodeList nl = me.getElementsByTagName(tagName);
            Hashtable<String, String> entry = new Hashtable<String, String>();
            for (int i = 0; i < nl.getLength(); i++) {
                Node node = nl.item(i);
                // System.out.println("Node "+i+": "+node.toString());
                NodeList c = node.getChildNodes();
                for (int j = 0; j < c.getLength(); j++) {
                    Node n2 = c.item(j);
                    entry.put(n2.getLocalName(), n2.getFirstChild().getNodeValue());
                    // System.out.println(n2.getLocalName() +" -> "+
                    // n2.getFirstChild().getNodeValue());
                }
                if (!entry.isEmpty())
                    ret.add(entry);
                entry = new Hashtable<String, String>();
            }
        }
        return ret;
    }

}
