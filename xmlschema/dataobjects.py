#
# Copyright (c), 2016-2021, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from abc import ABCMeta
from collections import namedtuple
from collections.abc import MutableSequence

from .exceptions import XMLSchemaValueError


ElementData = namedtuple('ElementData', ['tag', 'text', 'content', 'attributes'])
"""
Namedtuple for Element data interchange between decoders and converters.
The field *tag* is a string containing the Element's tag, *text* can be `None`
or a string representing the Element's text, *content* can be `None`, a list
containing the Element's children or a dictionary containing element name to
list of element contents for the Element's children (used for unordered input
data), *attributes* can be `None` or a dictionary containing the Element's
attributes.
"""


class DataElement(MutableSequence):
    """
    Data Element, an Element like object with decoded data and schema bindings.
    """
    value = None
    tail = None

    def __init__(self, tag, value=None, attrib=None, nsmap=None, xsd_element=None, xsd_type=None):
        super(DataElement, self).__init__()
        self._children = []
        self.tag = tag
        self.attrib = {}
        self.nsmap = {}

        if value is not None:
            self.value = value
        if attrib:
            self.attrib.update(attrib)
        if nsmap:
            self.nsmap.update(nsmap)

        self.xsd_element = xsd_element
        self._xsd_type = xsd_type

    def __getitem__(self, i):
        return self._children[i]

    def __setitem__(self, i, child):
        self._children[i] = child

    def __delitem__(self, i):
        del self._children[i]

    def __len__(self):
        return len(self._children)

    def insert(self, i, child):
        self._children.insert(i, child)

    def __repr__(self):
        return '%s(tag=%r)' % (self.__class__.__name__, self.tag)

    def __iter__(self):
        yield from self._children

    @property
    def text(self):
        if self.value is None:
            return
        elif self.value is True:
            return 'true'
        elif self.value is False:
            return 'false'
        else:
            return str(self.value)

    @property
    def xsd_type(self):
        if self._xsd_type is not None:
            return self._xsd_type
        elif self.xsd_element is not None:
            return self.xsd_element.type

    @xsd_type.setter
    def xsd_type(self, xsd_type):
        self._xsd_type = xsd_type

    def encode(self, **kwargs):
        if self.xsd_element is not None:
            return self.xsd_element.encode(self, **kwargs)
        raise XMLSchemaValueError("{!r} has no schema bindings".format(self))
        # TODO: handle _xsd_type is not xml_element.type

    to_etree = encode

    def iter(self, tag=None):
        if tag is None:
            tag = '*'
        if tag == '*' or tag == self.tag:
            yield self
        for child in self._children:
            yield from child.iter(tag)


class DataElementMeta(ABCMeta):
    """
    TODO: A metaclass for defining derived data element classes.
     The underlining idea is to develop schema API for XSD elements
     that can be generated by option and stored in a registry if
     necessary.
    """
