package no.uio.ephorte.connection;

import java.net.MalformedURLException;
import java.rmi.RemoteException;
import java.util.Hashtable;
import java.util.Properties;
import java.util.Vector;

import javax.xml.rpc.ServiceException;

import no.gecko.www.ephorte.webservices.GetDataSetResponseGetDataSetResult;
import no.gecko.www.ephorte.webservices.ServicesLocator;
import no.gecko.www.ephorte.webservices.ServicesSoap;

import org.apache.axis.message.MessageElement;
import org.apache.commons.logging.Log;
import org.apache.commons.logging.LogFactory;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

public class EphorteConnectionImpl extends EphorteConnection {
    String sessionID;
    ServicesSoap service;
    private Log log = LogFactory.getLog(EphorteConnectionImpl.class);
    private Properties props;

    public EphorteConnectionImpl(Properties props) {
        this.props = props;
        connect(props.getProperty("url"), props.getProperty("uname"),
                props.getProperty("password"), props.getProperty("database"));
    }

    protected void connect(String url, String userName, String passWord, String dataBase) {
        ServicesLocator locator = new ServicesLocator();
	log.info("Using web-service at url: " + url);
	log.info("Using database: " + dataBase + ", user: " + userName);
        try {
            if (url == null) {
                service = locator.getServicesSoap();
            } else {
                service = locator.getServicesSoap(new java.net.URL(url));
            }
            sessionID = service.login(userName, passWord, "", dataBase, null);
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
     * @throws RemoteException, TooManyRecordsException
     */
    public Vector<Hashtable<String, String>> getDataSet(String criteriaCollectionString,
							String tagName) 
	throws RemoteException, TooManyRecordsException 
    {
        Vector<Hashtable<String, String>> ret = new Vector<Hashtable<String, String>>();
        GetDataSetResponseGetDataSetResult res = service.getDataSet(sessionID,
                criteriaCollectionString+";MaxRecords=30000");  
        /* 
	 * IMPORTANT! Don't set MaxRecords any lower than 30000, until
	 * the code can handle partial results from the web service.
         */
        for (MessageElement me : res.get_any()) {
	    /* TODO: This hack should not run in a production system.
	     *       For now MaxRecords and AbsoluteMaxRecords will be
	     *       set to values large enough to avoid this
	     *       situation, but this code must handle partial
	     *       results sooner or later..
	     */
            NodeList nl = me.getElementsByTagName("PartialResult");
            for (int i = 0; i < nl.getLength(); i++) {
                Node node = nl.item(i);		
                if ("true".equals(node.getFirstChild().getNodeValue())) {
		    throw new TooManyRecordsException("WebService returned partial result. Giving up! ("+nl.getLength()+" records)");
                }
            }
            nl = me.getElementsByTagName(tagName);
            Hashtable<String, String> entry = new Hashtable<String, String>();
            for (int i = 0; i < nl.getLength(); i++) {
                Node node = nl.item(i);
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
        log.info("getDataSet("+criteriaCollectionString+") found " + 
		 ret.size() + " entries (using WebService)");
        return ret;
    }

}
