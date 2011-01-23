#!/usr/bin/env python
#coding:utf-8
# Author:  mozman --<mozman@gmx.at>
# Purpose: ODF Document class
# Created: 27.12.2010
# Copyright (C) 2010, Manfred Moitzi
# License: GPLv3

import zipfile
import os

from .const import MIMETYPES, MIMETYPE_BODYTAG_MAP, FILE_EXT_FOR_MIMETYPE
from .xmlns import subelement, CN, etree, wrap, ALL_NSMAP
from .filemanager import FileManager
from .meta import OfficeDocumentMeta
from .styles import OfficeDocumentStyles
from .content import OfficeDocumentContent
#from .observer import Observer

from . import body # register body classes

class InvalidFiletypeError(TypeError):
    pass

def opendoc(filename):
    if zipfile.is_zipfile(filename):
        fm = FileManager(filename)
        mimetype = fm.get_text('mimetype')
        return PackagedDocument(filemanager=fm, mimetype=mimetype)
    else:
        try:
            xmlnode = etree.parse(filename)
            return FlatXMLDocument(filename=filename, xmlnode=xmlnode)
        except etree.ParseError:
            raise IOError("File '%s' is neither a zip-package nor a flat XML OpenDocumentFormat file." % filename)


def newdoc(doctype="odt", filename="", template=None):
    if template is None:
        mimetype = MIMETYPES[doctype]
        document = PackagedDocument(None, mimetype)
        document.docname = filename
    else:
        document = _new_doc_from_template(filename, template)
    return document

def _new_doc_from_template(filename, templatename):
    #TODO: only works with zip packaged documents
    if zipfile.is_zipfile(templatename):
        fm = FileManager(templatename)
        mimetype = fm.get_text('mimetype')
        if mimetype.endswith('-template'):
            mimetype = mimetype[:-9]
        try:
            document = PackagedDocument(filemanager=fm, mimetype=mimetype)
            document.docname = filename
            return document
        except KeyError:
            raise InvalidFiletypeError("Unsupported mimetype: %s".format(mimetype))
    else:
        raise IOError('File does not exist or it is not a zipfile: %s' % templatename)


class _BaseDocument:
    """
    Broadcasting Events:
        broadcast(event='save', msg=self): send before saving the document
    """
    def __init__(self):
        self.backup = True
        # self.observer = Observer()

    def saveas(self, filename):
        self.docname = filename
        self.save()

    def save(self):
        if self.docname is None:
            raise IOError('No filename specified!')
        # inform save listener about saving event
        # self.observer.broadcast(event='save', msg=self)

        # set modification date to now
        self.meta.touch()
        self.meta.inc_editing_cycles()

    @property
    def application_body_tag(self):
        return CN(MIMETYPE_BODYTAG_MAP[self.mimetype])


class FlatXMLDocument(_BaseDocument):
    """ OpenDocument contained in a single XML file. """
    TAG = CN('office:document')

    def __init__(self, filetype='odt', filename=None, xmlnode=None):
        super(FlatXMLDocument, self).__init__()
        self.docname=filename
        self.mimetype = MIMETYPES[filetype]
        self.doctype = filetype

        if xmlnode is None: # new document
            self.xmlnode = etree.Element(self.TAG, nsmap=ALL_NSMAP)
        elif xmlnode.tag == self.TAG:
            self.xmlnode = xmlnode
            self.mimetype = xmlnode.get(CN('office:mimetype')) # required
        else:
            raise ValueError("Unexpected root tag: %s" % self.xmlnode.tag)

        if self.mimetype not in frozenset(MIMETYPES.values()):
            raise TypeError("Unsupported mimetype: %s" % self.mimetype)

        self._setup()

    def _setup(self):
        self.meta = OfficeDocumentMeta(subelement(self.xmlnode, CN('office:document-meta')))
        self.styles = wrap(subelement(self.xmlnode, CN('office:settings')))
        self.scripts = wrap(subelement(self.xmlnode, CN('office:scripts')))
        self.fonts = wrap(subelement(self.xmlnode, CN('office:font-face-decls')))
        self.styles = wrap(subelement(self.xmlnode, CN('office:styles')))
        self.automatic_styles = wrap(subelement(self.xmlnode, CN('office:automatic-styles')))
        self.master_styles = wrap(subelement(self.xmlnode, CN('office:master-styles')))
        self.body = self.get_application_body(self.application_body_tag)

    def get_application_body(self, bodytag):
        # The office:body element is just frame element for the real document content:
        # office:text, office:spreadsheet, office:presentation, office:drawing
        office_body = subelement(self.xmlnode, CN('office:body'))
        application_body = subelement(office_body, bodytag)
        return wrap(application_body)

    def save(self):
        super(FlatXMLDocument, self).save()
        if os.path.exists(self.docname) and self.backup:
            self._backupfile(self.docname)
        self._writefile(self.docname)

    def _backupfile(self, filename):
        bakfilename = filename+'.bak'
        # remove existing backupfile
        if os.path.exists(bakfilename):
            os.remove(bakfilename)
        os.rename(filename, bakfilename)

    def _writefile(self, filename):
        with open(filename, 'wb') as fp:
            fp.write(etree.tostring(self.xmlnode,
                                    xml_declaration=True,
                                    encoding='UTF-8'))

class PackagedDocument(_BaseDocument):
    """ OpenDocument as package in a zipfile.
    """
    def __init__(self, filemanager, mimetype):
        super(PackagedDocument, self).__init__()
        self.filemanager = fm = FileManager() if filemanager is None else filemanager
        self.docname = fm.zipname

        # add doctype to manifest
        self.filemanager.manifest.add('/', mimetype)

        self.mimetype = mimetype
        self.doctype = FILE_EXT_FOR_MIMETYPE[mimetype]
        fm.register('mimetype', self.mimetype)

        self.meta = OfficeDocumentMeta(fm.get_xml_element('meta.xml'))
        fm.register('meta.xml', self.meta, 'text/xml')

        self.styles = OfficeDocumentStyles(fm.get_xml_element('styles.xml'))
        fm.register('styles.xml', self.styles, 'text/xml')

        self.content = OfficeDocumentContent(mimetype, fm.get_xml_element('content.xml'))
        fm.register('content.xml', self.content, 'text/xml')

        self.body = self.content.get_application_body(self.application_body_tag)

    def save(self):
        super(PackagedDocument, self).save()
        self.filemanager.save(self.docname, backup=self.backup)
