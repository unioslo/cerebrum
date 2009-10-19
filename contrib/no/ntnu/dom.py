################################################################################
# Copyright (C) 1997, 1998 by the Regents of the University
# of California.   Anyone may reproduce the software in this file,
# in whole or in part, provided that:
# 
# (1)  Any copy or redistribution of this code must show the
#         Regents of the University of California, through its
#         Lawrence Berkeley National Laboratory, as the source, and must
#         include this notice;
# 
# (2)  Any use of this software must state that the software
#         copyright is held by the Regents of the University of
#         California, and that the software is used by their permission.
# 
# It is acknowledged that the U.S. Government has rights
# in this code under Contract DE-AC03-765F00098 between the U.S.
# Department of Energy and the University of California.
# 
# This code is provided as a professional academic contribution
# for joint exchange.  Thus it is experimental, is provided ``as is'',
# with no warranties of any kind  whatsoever,
# no support, promise of updates, or printed documentation.
# The Regents of the University of California shall have no
# liability with respect to the infringement of copyrights by
# this code, or any part thereof.
#  
# Joshua R. Boverhof, LBNL
###########################################################################
from cStringIO import StringIO
from string import join, strip, split

from xml.dom import Node
from Ft.Xml.Domlette import NonvalidatingReaderBase, NonvalidatingReader
import Ft.Xml.Domlette
from Ft.Xml import XPath

from ZSI.wstools.c14n import Canonicalize
from ZSI.wstools.Namespaces import SCHEMA, SOAP, XMLNS, DSIG
from ZSI.wstools.Utility import DOMException, SplitQName
from ZSI.wstools.Utility import NamespaceError, MessageInterface, ElementProxy


class DomletteReader(NonvalidatingReaderBase):
    '''Used with ZSI.parse.ParsedSoap
    '''
    fromString = NonvalidatingReaderBase.parseString
    fromStream = NonvalidatingReaderBase.parseStream


class DomletteElementProxy(ElementProxy):
    expression_dict = {}

    def __init__(self, sw, message=None):
        '''Initialize. 
           sw -- SoapWriter
        '''
        ElementProxy.__init__(self, sw, message)
        self._dom = DOM
        self._context = None

    def evaluate(self, expression, processorNss=None):
        '''expression -- XPath statement or compiled expression.
        '''
        if isinstance(expression, basestring):
            if not self.expression_dict.has_key(expression):
                self.expression_dict[expression] =  XPath.Compile(expression)
            expression = self.expression_dict[expression]

        context = self._context
        if context is None:
            context = XPath.Context.Context(self.node, processorNss=processorNss or self.processorNss)
        result = expression.evaluate(context)
        if type(result) in (list,tuple):
            #return map(lambda node: DomletteElementProxy(self.sw,node), result)
            l = []
            for node in result:
                item = node
                if node.nodeType == Node.ELEMENT_NODE:
                    item = DomletteElementProxy(self.sw,node)
                #elif node.nodeType == Node.TEXT_NODE:
                #   item = node.nodeValue
                # probably dont want to wrap other stuff...
                l.append(item)
            result = l
        else:
            if node.nodeType == Node.ELEMENT_NODE:
                result = DomletteElementProxy(self.sw,result)

        return result
        
    def isContextInitialized(self, processorNss=None):
        return self._context is not None
    def setContext(self, processorNss=None):
        self._context = XPath.Context.Context(self.node, processorNss=processorNss or self.processorNss)

    #############################################
    # Methods for checking/setting the
    # classes (namespaceURI,name) node. 
    #############################################
    def checkNode(self, namespaceURI=None, localName=None):
        '''
            namespaceURI -- namespace of element
            localName -- local name of element
        '''
        namespaceURI = namespaceURI or self.namespaceURI
        localName = localName or self.name
        check = False
        if localName and self.node:
            check = self._dom.isElement(self.node, localName, namespaceURI)
        if not check:
            raise NamespaceError, 'unexpected node type %s, expecting %s' %(self.node, localName)

    def setNode(self, node=None):
        if node:
            if isinstance(node, DomletteElementProxy):
                self.node = node._getNode()
            else:
                self.node = node
        elif self.node:
            node = self._dom.getElement(self.node, self.name, self.namespaceURI, default=None)
            if not node:
                raise NamespaceError, 'cant find element (%s,%s)' %(self.namespaceURI,self.name)
            self.node = node
        else:
            #self.node = self._dom.create(self.node, self.name, self.namespaceURI, default=None)
            self.createDocument(self.namespaceURI, localName=self.name, doctype=None)
        
        self.checkNode()

    #############################################
    # Wrapper Methods for direct DOM Element Node access
    #############################################
    def _getNode(self):
        return self.node

    def _getElements(self):
        return self._dom.getElements(self.node, name=None)

    def _getOwnerDocument(self):
        return self.node.ownerDocument or self.node

    def _getUniquePrefix(self):
        '''I guess we need to resolve all potential prefixes
        because when the current node is attached it copies the 
        namespaces into the parent node.
        '''
        while 1:
            self._indx += 1
            prefix = 'ns%d' %self._indx
            try:
                self._dom.findNamespaceURI(prefix, self._getNode())
            except (AttributeError, DOMException), ex:
                break
        return prefix

    def _getPrefix(self, node, nsuri):
        '''
        Keyword arguments:
            node -- DOM Element Node
            nsuri -- namespace of attribute value
        '''
        try:
            if node and (node.nodeType == node.ELEMENT_NODE) and \
                (nsuri == self._dom.findDefaultNS(node)):
                return None
        except DOMException, ex:
            pass
        if nsuri == XMLNS.XML:
            return self._xml_prefix
        if node.nodeType == Node.ELEMENT_NODE:
            for attr in node.attributes.values():
                if attr.namespaceURI == XMLNS.BASE \
                   and nsuri == attr.value:
                        return attr.localName
            else:
                if node.parentNode:
                    return self._getPrefix(node.parentNode, nsuri)
        raise NamespaceError, 'namespaceURI "%s" is not defined' %nsuri

    def _appendChild(self, node):
        '''
        Keyword arguments:
            node -- DOM Element Node
        '''
        if node is None:
            raise TypeError, 'node is None'
        self.node.appendChild(node)

    def _insertBefore(self, newChild, refChild):
        '''
        Keyword arguments:
            child -- DOM Element Node to insert
            refChild -- DOM Element Node 
        '''
        self.node.insertBefore(newChild, refChild)

    def _setAttributeNS(self, namespaceURI, qualifiedName, value):
        '''
        Keyword arguments:
            namespaceURI -- namespace of attribute
            qualifiedName -- qualified name of new attribute value
            value -- value of attribute
        '''
        self.node.setAttributeNS(namespaceURI, qualifiedName, value)

    #############################################
    #General Methods
    #############################################
    def isFault(self):
        '''check to see if this is a soap:fault message.
        '''
        return False

    def getPrefix(self, namespaceURI):
        try:
            prefix = self._getPrefix(node=self.node, nsuri=namespaceURI)
        except NamespaceError, ex:
            prefix = self._getUniquePrefix() 
            self.setNamespaceAttribute(prefix, namespaceURI)
        return prefix

    def getDocument(self):
        return self._getOwnerDocument()

    def setDocument(self, document):
        self.node = document

    def importFromString(self, xmlString):
        doc = self._dom.loadDocument(StringIO(xmlString))
        node = self._dom.getElement(doc, name=None)
        clone = self.importNode(node)
        self._appendChild(clone)

    def importNode(self, node):
        if isinstance(node, DomletteElementProxy):
            node = node._getNode()
        return self._dom.importNode(self._getOwnerDocument(), node, deep=1)

    def loadFromString(self, data):
        self.node = self._dom.loadDocument(StringIO(data))

    def canonicalize(self, algorithm=DSIG.C14N, unsuppressedPrefixes=[]):
        if algorithm == DSIG.C14N_EXCL:
            return Canonicalize(self.node, unsuppressedPrefixes=unsuppressedPrefixes)
        else:
            return Canonicalize(self.node)

    def toString(self):
        s = StringIO()
        FastPrint(self.node, output=s)
        return s.getvalue()

    def createDocument(self, namespaceURI, localName, doctype=None):
        prefix = self._soap_env_prefix
        if namespaceURI == self.reserved_ns[prefix]:
            qualifiedName = '%s:%s' %(prefix,localName)
        elif namespaceURI is localName is None:
            self.node = self._dom.createDocument(None,None,None)
            return
        else:
            raise KeyError, 'only support creation of document in %s' %self.reserved_ns[prefix]

        qualifiedName = '%s:%s' %(prefix,localName)
        document = self._dom.createDocument(nsuri=namespaceURI, qname=qualifiedName, doctype=doctype)
        self.node = document.childNodes[0]

        #set up reserved namespace attributes
        for prefix,nsuri in self.reserved_ns.items():
            self._setAttributeNS(namespaceURI=self._xmlns_nsuri, 
                qualifiedName='%s:%s' %(self._xmlns_prefix,prefix), 
                value=nsuri)

    #############################################
    #Methods for attributes
    #############################################
    def hasAttribute(self, namespaceURI, localName):
        return self._dom.hasAttr(self._getNode(), name=localName, nsuri=namespaceURI)

    def setAttributeType(self, namespaceURI, localName):
        '''set xsi:type
        Keyword arguments:
            namespaceURI -- namespace of attribute value
            localName -- name of new attribute value

        '''
        self.logger.debug('setAttributeType: (%s,%s)', namespaceURI, localName)
        value = localName
        if namespaceURI:
            value = '%s:%s' %(self.getPrefix(namespaceURI),localName)
        self._setAttributeNS(self._xsi_nsuri, '%s:type' %self._xsi_prefix, value)

    def createAttributeNS(self, namespace, name, value):
        document = self._getOwnerDocument()
        attrNode = document.createAttributeNS(namespace, name, value)

    def setAttributeNS(self, namespaceURI, localName, value):
        '''
        Keyword arguments:
            namespaceURI -- namespace of attribute to create, None is for
                attributes in no namespace.
            localName -- local name of new attribute
            value -- value of new attribute
        ''' 
        prefix = None
        if namespaceURI:
            try:
                prefix = self.getPrefix(namespaceURI)
            except KeyError, ex:
                prefix = 'ns2'
                self.setNamespaceAttribute(prefix, namespaceURI)
        qualifiedName = localName
        if prefix:
            qualifiedName = '%s:%s' %(prefix, localName)
        self._setAttributeNS(namespaceURI, qualifiedName, value)

    def setNamespaceAttribute(self, prefix, namespaceURI):
        '''
        Keyword arguments:
            prefix -- xmlns prefix
            namespaceURI -- value of prefix
        '''
        self._setAttributeNS(XMLNS.BASE, 'xmlns:%s' %prefix, namespaceURI)

    #############################################
    #Methods for elements
    #############################################
    def createElementNS(self, namespace, qname):
        '''
        Keyword arguments:
            namespace -- namespace of element to create
            qname -- qualified name of new element
        '''
        document = self._getOwnerDocument()
        node = document.createElementNS(namespace, qname)
        return DomletteElementProxy(self.sw, node)

    def createAppendSetElement(self, namespaceURI, localName, prefix=None):
        '''Create a new element (namespaceURI,name), append it
           to current node, then set it to be the current node.
        Keyword arguments:
            namespaceURI -- namespace of element to create
            localName -- local name of new element
            prefix -- if namespaceURI is not defined, declare prefix.  defaults
                to 'ns1' if left unspecified.
        '''
        node = self.createAppendElement(namespaceURI, localName, prefix=None)
        node=node._getNode()
        self._setNode(node._getNode())

    def createAppendElement(self, namespaceURI, localName, prefix=None):
        '''Create a new element (namespaceURI,name), append it
           to current node, and return the newly created node.
        Keyword arguments:
            namespaceURI -- namespace of element to create
            localName -- local name of new element
            prefix -- if namespaceURI is not defined, declare prefix.  defaults
                to 'ns1' if left unspecified.
        '''
        declare = False
        qualifiedName = localName
        if namespaceURI:
            try:
                prefix = self.getPrefix(namespaceURI)
            except:
                declare = True
                prefix = prefix or self._getUniquePrefix()
            if prefix: 
                qualifiedName = '%s:%s' %(prefix, localName)
        node = self.createElementNS(namespaceURI, qualifiedName)
        if declare:
            node._setAttributeNS(XMLNS.BASE, 'xmlns:%s' %prefix, namespaceURI)
        self._appendChild(node=node._getNode())
        return node

    def createInsertBefore(self, namespaceURI, localName, refChild):
        qualifiedName = localName
        prefix = self.getPrefix(namespaceURI)
        if prefix: 
            qualifiedName = '%s:%s' %(prefix, localName)
        node = self.createElementNS(namespaceURI, qualifiedName)
        self._insertBefore(newChild=node._getNode(), refChild=refChild._getNode())
        return node

    def getElement(self, namespaceURI, localName):
        '''
        Keyword arguments:
            namespaceURI -- namespace of element
            localName -- local name of element
        '''
        node = self._dom.getElement(self.node, localName, namespaceURI, default=None)
        if node:
            return DomletteElementProxy(self.sw, node)
        return None

    def getElements(self, namespaceURI=None, localName=None):
        '''
         Keyword arguments:
            namespaceURI -- namespace of element
            localName -- local name of element
        '''
        nodes = self._dom.getElements(self.node,localName, namespaceURI)
        nodesList = []
        if nodes:
            for node in nodes:
                nodesList.append(DomletteElementProxy(self.sw, node))

        return nodesList
                                 
    def getAttributeValue(self, namespaceURI, localName):
        '''
        Keyword arguments:
            namespaceURI -- namespace of attribute
            localName -- local name of attribute
        '''
        if self.hasAttribute(namespaceURI, localName):
            attr = self.node.getAttributeNodeNS(namespaceURI,localName)
            return attr.value
        return None

    def getValue(self):
        return self._dom.getElementText(self.node, preserve_ws=True)    

    #############################################
    #Methods for text nodes
    #############################################
    def createAppendTextNode(self, pyobj):
        node = self.createTextNode(pyobj)
        self._appendChild(node=node._getNode())
        return node

    def createTextNode(self, pyobj):
        document = self._getOwnerDocument()
        node = document.createTextNode(pyobj)
        return DomletteElementProxy(self.sw, node)

    #############################################
    #Methods for retrieving namespaceURI's
    #############################################
    def findNamespaceURI(self, qualifiedName):
        parts = SplitQName(qualifiedName)
        element = self._getNode()
        if len(parts) == 1:
            return (self._dom.findTargetNS(element), value)
        return self._dom.findNamespaceURI(parts[0], element)

    def resolvePrefix(self, prefix):
        element = self._getNode()
        return self._dom.findNamespaceURI(prefix, element)

    def getSOAPEnvURI(self):
        return self._soap_env_nsuri

    def isEmpty(self):
        return not self.node


class DOM:
    """The DOM singleton defines a number of XML related constants and
       provides a number of utility methods for DOM related tasks. It
       also provides some basic abstractions so that the rest of the
       package need not care about actual DOM implementation in use."""

    # Namespace stuff related to the SOAP specification.

    NS_SOAP_ENV_1_1 = 'http://schemas.xmlsoap.org/soap/envelope/'
    NS_SOAP_ENC_1_1 = 'http://schemas.xmlsoap.org/soap/encoding/'

    NS_SOAP_ENV_1_2 = 'http://www.w3.org/2001/06/soap-envelope'
    NS_SOAP_ENC_1_2 = 'http://www.w3.org/2001/06/soap-encoding'

    NS_SOAP_ENV_ALL = (NS_SOAP_ENV_1_1, NS_SOAP_ENV_1_2)
    NS_SOAP_ENC_ALL = (NS_SOAP_ENC_1_1, NS_SOAP_ENC_1_2)

    NS_SOAP_ENV = NS_SOAP_ENV_1_1
    NS_SOAP_ENC = NS_SOAP_ENC_1_1

    _soap_uri_mapping = {
        NS_SOAP_ENV_1_1 : '1.1',
        NS_SOAP_ENV_1_2 : '1.2',
    }

    SOAP_ACTOR_NEXT_1_1 = 'http://schemas.xmlsoap.org/soap/actor/next'
    SOAP_ACTOR_NEXT_1_2 = 'http://www.w3.org/2001/06/soap-envelope/actor/next'
    SOAP_ACTOR_NEXT_ALL = (SOAP_ACTOR_NEXT_1_1, SOAP_ACTOR_NEXT_1_2)
    
    def SOAPUriToVersion(self, uri):
        """Return the SOAP version related to an envelope uri."""
        value = self._soap_uri_mapping.get(uri)
        if value is not None:
            return value
        raise ValueError(
            'Unsupported SOAP envelope uri: %s' % uri
            )

    def GetSOAPEnvUri(self, version):
        """Return the appropriate SOAP envelope uri for a given
           human-friendly SOAP version string (e.g. '1.1')."""
        attrname = 'NS_SOAP_ENV_%s' % join(split(version, '.'), '_')
        value = getattr(self, attrname, None)
        if value is not None:
            return value
        raise ValueError(
            'Unsupported SOAP version: %s' % version
            )

    def GetSOAPEncUri(self, version):
        """Return the appropriate SOAP encoding uri for a given
           human-friendly SOAP version string (e.g. '1.1')."""
        attrname = 'NS_SOAP_ENC_%s' % join(split(version, '.'), '_')
        value = getattr(self, attrname, None)
        if value is not None:
            return value
        raise ValueError(
            'Unsupported SOAP version: %s' % version
            )

    def GetSOAPActorNextUri(self, version):
        """Return the right special next-actor uri for a given
           human-friendly SOAP version string (e.g. '1.1')."""
        attrname = 'SOAP_ACTOR_NEXT_%s' % join(split(version, '.'), '_')
        value = getattr(self, attrname, None)
        if value is not None:
            return value
        raise ValueError(
            'Unsupported SOAP version: %s' % version
            )


    # Namespace stuff related to XML Schema.

    NS_XSD_99 = 'http://www.w3.org/1999/XMLSchema'
    NS_XSI_99 = 'http://www.w3.org/1999/XMLSchema-instance'    

    NS_XSD_00 = 'http://www.w3.org/2000/10/XMLSchema'
    NS_XSI_00 = 'http://www.w3.org/2000/10/XMLSchema-instance'    

    NS_XSD_01 = 'http://www.w3.org/2001/XMLSchema'
    NS_XSI_01 = 'http://www.w3.org/2001/XMLSchema-instance'

    NS_XSD_ALL = (NS_XSD_99, NS_XSD_00, NS_XSD_01)
    NS_XSI_ALL = (NS_XSI_99, NS_XSI_00, NS_XSI_01)

    NS_XSD = NS_XSD_01
    NS_XSI = NS_XSI_01

    _xsd_uri_mapping = {
        NS_XSD_99 : NS_XSI_99,
        NS_XSD_00 : NS_XSI_00,
        NS_XSD_01 : NS_XSI_01,
    }

    for key, value in _xsd_uri_mapping.items():
        _xsd_uri_mapping[value] = key


    def InstanceUriForSchemaUri(self, uri):
        """Return the appropriate matching XML Schema instance uri for
           the given XML Schema namespace uri."""
        return self._xsd_uri_mapping.get(uri)

    def SchemaUriForInstanceUri(self, uri):
        """Return the appropriate matching XML Schema namespace uri for
           the given XML Schema instance namespace uri."""
        return self._xsd_uri_mapping.get(uri)


    # Namespace stuff related to WSDL.

    NS_WSDL_1_1 = 'http://schemas.xmlsoap.org/wsdl/'
    NS_WSDL_ALL = (NS_WSDL_1_1,)
    NS_WSDL = NS_WSDL_1_1

    NS_SOAP_BINDING_1_1 = 'http://schemas.xmlsoap.org/wsdl/soap/'
    NS_HTTP_BINDING_1_1 = 'http://schemas.xmlsoap.org/wsdl/http/'
    NS_MIME_BINDING_1_1 = 'http://schemas.xmlsoap.org/wsdl/mime/'

    NS_SOAP_BINDING_ALL = (NS_SOAP_BINDING_1_1,)
    NS_HTTP_BINDING_ALL = (NS_HTTP_BINDING_1_1,)
    NS_MIME_BINDING_ALL = (NS_MIME_BINDING_1_1,)

    NS_SOAP_BINDING = NS_SOAP_BINDING_1_1
    NS_HTTP_BINDING = NS_HTTP_BINDING_1_1
    NS_MIME_BINDING = NS_MIME_BINDING_1_1

    NS_SOAP_HTTP_1_1 = 'http://schemas.xmlsoap.org/soap/http'
    NS_SOAP_HTTP_ALL = (NS_SOAP_HTTP_1_1,)
    NS_SOAP_HTTP = NS_SOAP_HTTP_1_1
    

    _wsdl_uri_mapping = {
        NS_WSDL_1_1 : '1.1',
    }
    
    def WSDLUriToVersion(self, uri):
        """Return the WSDL version related to a WSDL namespace uri."""
        value = self._wsdl_uri_mapping.get(uri)
        if value is not None:
            return value
        raise ValueError(
            'Unsupported SOAP envelope uri: %s' % uri
            )

    def GetWSDLUri(self, version):
        attr = 'NS_WSDL_%s' % join(split(version, '.'), '_')
        value = getattr(self, attr, None)
        if value is not None:
            return value
        raise ValueError(
            'Unsupported WSDL version: %s' % version
            )

    def GetWSDLSoapBindingUri(self, version):
        attr = 'NS_SOAP_BINDING_%s' % join(split(version, '.'), '_')
        value = getattr(self, attr, None)
        if value is not None:
            return value
        raise ValueError(
            'Unsupported WSDL version: %s' % version
            )

    def GetWSDLHttpBindingUri(self, version):
        attr = 'NS_HTTP_BINDING_%s' % join(split(version, '.'), '_')
        value = getattr(self, attr, None)
        if value is not None:
            return value
        raise ValueError(
            'Unsupported WSDL version: %s' % version
            )

    def GetWSDLMimeBindingUri(self, version):
        attr = 'NS_MIME_BINDING_%s' % join(split(version, '.'), '_')
        value = getattr(self, attr, None)
        if value is not None:
            return value
        raise ValueError(
            'Unsupported WSDL version: %s' % version
            )

    def GetWSDLHttpTransportUri(self, version):
        attr = 'NS_SOAP_HTTP_%s' % join(split(version, '.'), '_')
        value = getattr(self, attr, None)
        if value is not None:
            return value
        raise ValueError(
            'Unsupported WSDL version: %s' % version
            )


    # Other xml namespace constants.
    NS_XMLNS     = 'http://www.w3.org/2000/xmlns/'



    def isElement(self, node, name, nsuri=None):
        """Return true if the given node is an element with the given
           name and optional namespace uri."""
        if node.nodeType != node.ELEMENT_NODE:
            return 0
        return node.localName == name and \
               (nsuri is None or self.nsUriMatch(node.namespaceURI, nsuri))

    def getElement(self, node, name, nsuri=None, default=join):
        """Return the first child of node with a matching name and
           namespace uri, or the default if one is provided."""
        nsmatch = self.nsUriMatch
        ELEMENT_NODE = node.ELEMENT_NODE
        for child in node.childNodes:
            if child.nodeType == ELEMENT_NODE:
                if ((child.localName == name or name is None) and
                    (nsuri is None or nsmatch(child.namespaceURI, nsuri))
                    ):
                    return child
        if default is not join:
            return default
        raise KeyError, name

    def getElementById(self, node, id, default=join):
        """Return the first child of node matching an id reference."""
        attrget = self.getAttr
        ELEMENT_NODE = node.ELEMENT_NODE
        for child in node.childNodes:
            if child.nodeType == ELEMENT_NODE:
                if attrget(child, 'id') == id:
                    return child
        if default is not join:
            return default
        raise KeyError, name

    def getMappingById(self, document, depth=None, element=None,
                       mapping=None, level=1):
        """Create an id -> element mapping of those elements within a
           document that define an id attribute. The depth of the search
           may be controlled by using the (1-based) depth argument."""
        if document is not None:
            element = document.documentElement
            mapping = {}
        attr = element._attrs.get('id', None)
        if attr is not None:
            mapping[attr.value] = element
        if depth is None or depth > level:
            level = level + 1
            ELEMENT_NODE = element.ELEMENT_NODE
            for child in element.childNodes:
                if child.nodeType == ELEMENT_NODE:
                    self.getMappingById(None, depth, child, mapping, level)
        return mapping        

    def getElements(self, node, name, nsuri=None):
        """Return a sequence of the child elements of the given node that
           match the given name and optional namespace uri."""
        nsmatch = self.nsUriMatch
        result = []
        ELEMENT_NODE = node.ELEMENT_NODE
        for child in node.childNodes:
            if child.nodeType == ELEMENT_NODE:
                if ((child.localName == name or name is None) and (
                    (nsuri is None) or nsmatch(child.namespaceURI, nsuri))):
                    result.append(child)
        return result

    def hasAttr(self, node, name, nsuri=None):
        """Return true if element has attribute with the given name and
           optional nsuri. If nsuri is not specified, returns true if an
           attribute exists with the given name with any namespace."""
        return node.hasAttributeNS(nsuri, name)

    def getAttr(self, node, name, nsuri=None, default=join):
        """Return the value of the attribute named 'name' with the
           optional nsuri, or the default if one is specified. If
           nsuri is not specified, an attribute that matches the
           given name will be returned regardless of namespace."""
        result = node.getAttributeNS(nsuri,name)
        if result is not None and result != '':
            return result
        if default is not join:
            return default
        return ''

    def getAttrs(self, node):
        """Return a Collection of all attributes 
        """
        attrs = {}
        for k,v in node._attrs.items():
            attrs[k] = v.value
        return attrs

    def getElementText(self, node, preserve_ws=None):
        """Return the text value of an xml element node. Leading and trailing
           whitespace is stripped from the value unless the preserve_ws flag
           is passed with a true value."""
        result = []
        for child in node.childNodes:
            nodetype = child.nodeType
            if nodetype == child.TEXT_NODE or \
               nodetype == child.CDATA_SECTION_NODE:
                result.append(child.nodeValue)
        value = join(result, '')
        if preserve_ws is None:
            value = strip(value)
        return value

    def findNamespaceURI(self, prefix, node):
        """Find a namespace uri given a prefix and a context node."""
        attrkey = (self.NS_XMLNS, prefix)
        DOCUMENT_NODE = node.DOCUMENT_NODE
        ELEMENT_NODE = node.ELEMENT_NODE
        while 1:
            if node.nodeType != ELEMENT_NODE:
                node = node.parentNode
                continue
            #result = node._attrsNS.get(attrkey, None)
            #if result is not None:
            #    return result.value
            result = node.getAttributeNS(*attrkey)
            if result != '':
                return result

            if hasattr(node, '__imported__'):
                raise DOMException('Value for prefix %s not found.' % prefix)
            node = node.parentNode
            if node.nodeType == DOCUMENT_NODE:
                raise DOMException('Value for prefix %s not found.' % prefix)

    def findDefaultNS(self, node):
        """Return the current default namespace uri for the given node."""
        attrkey = (self.NS_XMLNS, 'xmlns')
        DOCUMENT_NODE = node.DOCUMENT_NODE
        ELEMENT_NODE = node.ELEMENT_NODE
        while 1:
            if node.nodeType != ELEMENT_NODE:
                node = node.parentNode
                continue
            #result = node._attrsNS.get(attrkey, None)
            #if result is not None:
            #    return result.value
            result = node.getAttributeNS(*attrkey)
            if result != '':
                return result

            if hasattr(node, '__imported__'):
                raise DOMException('Cannot determine default namespace.')
            node = node.parentNode
            if node.nodeType == DOCUMENT_NODE:
                raise DOMException('Cannot determine default namespace.')

    def findTargetNS(self, node):
        """Return the defined target namespace uri for the given node."""
        attrget = self.getAttr
        attrkey = (self.NS_XMLNS, 'xmlns')
        DOCUMENT_NODE = node.DOCUMENT_NODE
        ELEMENT_NODE = node.ELEMENT_NODE
        while 1:
            if node.nodeType != ELEMENT_NODE:
                node = node.parentNode
                continue
            result = attrget(node, 'targetNamespace', default=None)
            if result is not None:
                return result
            node = node.parentNode
            if node.nodeType == DOCUMENT_NODE:
                raise DOMException('Cannot determine target namespace.')

    def getTypeRef(self, element):
        """Return (namespaceURI, name) for a type attribue of the given
           element, or None if the element does not have a type attribute."""
        typeattr = self.getAttr(element, 'type', default=None)
        if typeattr is None:
            return None
        parts = typeattr.split(':', 1)
        if len(parts) == 2:
            nsuri = self.findNamespaceURI(parts[0], element)
        else:
            nsuri = self.findDefaultNS(element)
        return (nsuri, parts[1])

    def importNode(self, document, node, deep=0):
        """Implements (well enough for our purposes) DOM node import."""
        nodetype = node.nodeType
        if nodetype in (node.DOCUMENT_NODE, node.DOCUMENT_TYPE_NODE):
            raise DOMException('Illegal node type for importNode')
        if nodetype == node.ENTITY_REFERENCE_NODE:
            deep = 0
        clone = node.cloneNode(deep)
        self._setOwnerDoc(document, clone)
        clone.__imported__ = 1
        return clone

    def _setOwnerDoc(self, document, node):
        node.ownerDocument = document
        for child in node.childNodes:
            self._setOwnerDoc(document, child)

    def nsUriMatch(self, value, wanted, strict=0, tt=type(())):
        """Return a true value if two namespace uri values match."""
        if value == wanted or (type(wanted) is tt) and value in wanted:
            return 1
        if not strict:
            wanted = type(wanted) is tt and wanted or (wanted,)
            value = value[-1:] != '/' and value or value[:-1]
            for item in wanted:
                if item == value or item[:-1] == value:
                    return 1
        return 0

    def createDocument(self, nsuri, qname, doctype=None):
        """Create a new writable DOM document object."""
        #impl = xml.dom.minidom.getDOMImplementation()
        impl = Ft.Xml.Domlette.implementation
        return impl.createDocument(nsuri, qname, doctype)

    def loadDocument(self, data):
        """Load an xml file from a file-like object and return a DOM
           document instance."""
        #return xml.dom.minidom.parse(data)
        return NonvalidatingReader.parseStream(data)

    def loadFromURL(self, url):
        """Load an xml file from a URL and return a DOM document."""
        file = urlopen(url)
        try:     result = self.loadDocument(file)
        finally: file.close()
        return result

    def unlink(self, document):
        """When you are finished with a DOM, you should clean it up. 
        This is necessary because some versions of Python do not support 
        garbage collection of objects that refer to each other in a cycle. 
        Until this restriction is removed from all versions of Python, it 
        is safest to write your code as if cycles would not be cleaned up."""
        #if hasattr(document, 'unlink'):
        #    document.unlink()
        return

DOM = DOM()


"""
Some code from c14n modified to not do sorting.  
~30% faster than c14n.Canonicalize
~12% faster than Ft.Xml.Domlette.Print

    --Ft.Xml.Domlette.Print(self.node, stream=s)
    This function produces XML with a different canonical form
    from the source.
"""
_attrs = lambda E: (E.attributes and E.attributes.values()) or []
_children = lambda E: E.childNodes or []
_IN_XML_NS = lambda n: n.namespaceURI == XMLNS.XML
_LesserElement, _Element, _GreaterElement = range(3)

def _utilized(n, node, other_attrs, unsuppressedPrefixes):
    '''_utilized(n, node, other_attrs, unsuppressedPrefixes) -> boolean
    Return true if that nodespace is utilized within the node'''

    if n.startswith('xmlns:'):
        n = n[6:]
    elif n.startswith('xmlns'):
        n = n[5:]
    if n == node.prefix or n in unsuppressedPrefixes: return 1
    for attr in other_attrs:
        if n == attr.prefix: return 1
    return 0

_in_subset = lambda subset, node: not subset or node in subset

class _implementation:
    '''Implementation class for C14N. This accompanies a node during it's
    processing and includes the parameters and processing state.'''

    # Handler for each node type; populated during module instantiation.
    handlers = {}

    def __init__(self, node, write, **kw):
        '''Create and run the implementation.'''

        self.write = write
        self.subset = kw.get('subset')
        if self.subset:
            self.comments = kw.get('comments', 1)
        else:
            self.comments = kw.get('comments', 0)
        self.unsuppressedPrefixes = kw.get('unsuppressedPrefixes')
        nsdict = kw.get('nsdict', { 'xml': XMLNS.XML, 'xmlns': XMLNS.BASE })

        # Processing state.
        self.state = (nsdict, ['xml'], [])

        #ATTRIBUTE_NODE
        #CDATA_SECTION_NODE
        #COMMENT_NODE
        #DOCUMENT_FRAGMENT_NODE
        #DOCUMENT_NODE
        #DOCUMENT_TYPE_NODE
        #ELEMENT_NODE
        #ENTITY_NODE
        #ENTITY_REFERENCE_NODE
        #NOTATION_NODE
        #PROCESSING_INSTRUCTION_NODE
        #TEXT_NODE
        #TREE_POSITION_SAME_NODE
        if node.nodeType == Node.DOCUMENT_NODE:
            self._do_document(node)
        elif node.nodeType == Node.ELEMENT_NODE:
            self.documentOrder = _Element        # At document element
            if self.unsuppressedPrefixes is not None:
                self._do_element(node)
            else:
                inherited = self._inherit_context(node)
                self._do_element(node, inherited)
        elif node.nodeType == Node.DOCUMENT_TYPE_NODE:
            pass
        else:
            raise TypeError, str(node)


    def _inherit_context(self, node):
        '''_inherit_context(self, node) -> list
        Scan ancestors of attribute and namespace context.  Used only
        for single element node canonicalization, not for subset
        canonicalization.'''

        # Collect the initial list of xml:foo attributes.
        xmlattrs = filter(_IN_XML_NS, _attrs(node))

        # Walk up and get all xml:XXX attributes we inherit.
        inherited, parent = [], node.parentNode
        while parent and parent.nodeType == Node.ELEMENT_NODE:
            for a in filter(_IN_XML_NS, _attrs(parent)):
                n = a.localName
                if n not in xmlattrs:
                    xmlattrs.append(n)
                    inherited.append(a)
            parent = parent.parentNode
        return inherited


    def _do_document(self, node):
        '''_do_document(self, node) -> None
        Process a document node. documentOrder holds whether the document
        element has been encountered such that PIs/comments can be written
        as specified.'''

        self.documentOrder = _LesserElement
        for child in node.childNodes:
            if child.nodeType == Node.ELEMENT_NODE:
                self.documentOrder = _Element        # At document element
                self._do_element(child)
                self.documentOrder = _GreaterElement # After document element
            elif child.nodeType == Node.PROCESSING_INSTRUCTION_NODE:
                self._do_pi(child)
            elif child.nodeType == Node.COMMENT_NODE:
                self._do_comment(child)
            elif child.nodeType == Node.DOCUMENT_TYPE_NODE:
                pass
            else:
                raise TypeError, str(child)
    handlers[Node.DOCUMENT_NODE] = _do_document


    def _do_text(self, node):
        '''_do_text(self, node) -> None
        Process a text or CDATA node.  Render various special characters
        as their C14N entity representations.'''
        if not _in_subset(self.subset, node): return
        s = node.data \
                .replace("&", "&amp;") \
                .replace("<", "&lt;") \
                .replace(">", "&gt;") \
                .replace("\015", "&#xD;")
        if s: self.write(s)
    handlers[Node.TEXT_NODE] = _do_text
    handlers[Node.CDATA_SECTION_NODE] = _do_text


    def _do_pi(self, node):
        '''_do_pi(self, node) -> None
        Process a PI node. Render a leading or trailing #xA if the
        document order of the PI is greater or lesser (respectively)
        than the document element.
        '''
        if not _in_subset(self.subset, node): return
        W = self.write
        if self.documentOrder == _GreaterElement: W('\n')
        W('<?')
        W(node.nodeName)
        s = node.data
        if s:
            W(' ')
            W(s)
        W('?>')
        if self.documentOrder == _LesserElement: W('\n')
    handlers[Node.PROCESSING_INSTRUCTION_NODE] = _do_pi


    def _do_comment(self, node):
        '''_do_comment(self, node) -> None
        Process a comment node. Render a leading or trailing #xA if the
        document order of the comment is greater or lesser (respectively)
        than the document element.
        '''
        if not _in_subset(self.subset, node): return
        if self.comments:
            W = self.write
            if self.documentOrder == _GreaterElement: W('\n')
            W('<!--')
            W(node.data)
            W('-->')
            if self.documentOrder == _LesserElement: W('\n')
    handlers[Node.COMMENT_NODE] = _do_comment


    def _do_attr(self, n, value):
        ''''_do_attr(self, node) -> None
        Process an attribute.'''

        W = self.write
        W(' ')
        W(n)
        W('="')
        s = value \
            .replace("&", "&amp;") \
            .replace("<", "&lt;") \
            .replace('"', '&quot;') \
            .replace('\011', '&#x9') \
            .replace('\012', '&#xA') \
            .replace('\015', '&#xD')
        s = s.encode("utf-8")
        W(s)
        W('"')

    def _do_element(self, node, initial_other_attrs = []):
        '''_do_element(self, node, initial_other_attrs = []) -> None
        Process an element (and its children).'''

        # Get state (from the stack) make local copies.
        #       ns_parent -- NS declarations in parent
        #       ns_rendered -- NS nodes rendered by ancestors
        #       xml_attrs -- Attributes in XML namespace from parent
        #       ns_local -- NS declarations relevant to this element
        ns_parent, ns_rendered, xml_attrs = \
                self.state[0], self.state[1][:], self.state[2][:]
        ns_local = ns_parent.copy()

        # Divide attributes into NS, XML, and others.
        other_attrs = initial_other_attrs[:]
        in_subset = _in_subset(self.subset, node)
        for a in _attrs(node):
            if a.namespaceURI == XMLNS.BASE:
                n = a.nodeName
                if n == "xmlns:": n = "xmlns"        # DOM bug workaround
                ns_local[n] = a.nodeValue
            elif a.namespaceURI == XMLNS.XML:
                if self.unsuppressedPrefixes is None or in_subset:
                    xml_attrs.append(a)
            else:
                other_attrs.append(a)

        # Render the node
        W, name = self.write, None
        if in_subset:
            name = node.nodeName
            W('<')
            W(name)

            # Create list of NS attributes to render.
            ns_to_render = []
            for n,v in ns_local.items():
                pval = ns_parent.get(n)

                # If default namespace is XMLNS.BASE or empty, skip
                if n == "xmlns" \
                and v in [ XMLNS.BASE, '' ] and pval in [ XMLNS.BASE, '' ]:
                    continue

                # "omit namespace node with local name xml, which defines
                # the xml prefix, if its string value is
                # http://www.w3.org/XML/1998/namespace."
                if n == "xmlns:xml" \
                and v in [ 'http://www.w3.org/XML/1998/namespace' ]:
                    continue

                # If different from parent, or parent didn't render
                # and if not exclusive, or this prefix is needed or
                # not suppressed
                if (v != pval or n not in ns_rendered) \
                  and (self.unsuppressedPrefixes is None or \
                  _utilized(n, node, other_attrs, self.unsuppressedPrefixes)):
                    ns_to_render.append((n, v))

            # Sort and render the ns, marking what was rendered.
            #ns_to_render.sort(_sorter_ns)
            for n,v in ns_to_render:
                self._do_attr(n, v)
                ns_rendered.append(n)

            # Add in the XML attributes (don't pass to children, since
            # we're rendering them), sort, and render.
            other_attrs.extend(xml_attrs)
            xml_attrs = []
            #other_attrs.sort(_sorter)
            for a in other_attrs:
                self._do_attr(a.nodeName, a.value)
            W('>')

        # Push state, recurse, pop state.
        state, self.state = self.state, (ns_local, ns_rendered, xml_attrs)
        for c in _children(node):
            _implementation.handlers[c.nodeType](self, c)
        self.state = state

        if name: W('</%s>' % name)
    handlers[Node.ELEMENT_NODE] = _do_element


def FastPrint(node, output=None, **kw):
    """FastPrint(node, output=None, **kw) -> UTF-8
    
    Output a DOM document/element node and all descendents.
    Return the text; if output is specified then output.write will
    be called to output the text and None will be returned
    Keyword parameters:
        comments: keep comments if non-zero (default is 0)
        
    """
    if output:
        _implementation(node, output.write, **kw)
    else:
        s = StringIO.StringIO()
        _implementation(node, s.write, **kw)
        return s.getvalue()


if __name__ == '__main__': print _copyright
