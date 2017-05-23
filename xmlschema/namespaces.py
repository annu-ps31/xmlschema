# -*- coding: utf-8 -*-
#
# Copyright (c), 2016, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module contains functions and classes for managing namespaces XSD declarations.
"""
import logging as _logging

from .qnames import *
from .exceptions import XMLSchemaTypeError, XMLSchemaLookupError, XMLSchemaParseError
from .utils import get_namespace, camel_case_split, URIDict
from .qnames import (
    local_name, XSD_ATTRIBUTE_TAG, XSD_COMPLEX_TYPE_TAG, XSD_ELEMENT_TAG,
    XSD_SIMPLE_TYPE_TAG, XSD_ATTRIBUTE_GROUP_TAG, XSD_GROUP_TAG
)
from .xsdbase import get_xsd_attribute, XsdBase

_logger = _logging.getLogger(__name__)


#
# Defines the iterfind functions for XML Schema declarations
def create_iterfind_by_tag(tag):
    """
    Defines a generator that produce all subelements that have a specific tag.
    """
    tag = str(tag)

    def iterfind_function(elements, path=None, namespaces=None):
        if isinstance(elements, list):
            for _elem in elements:
                for elem in _elem.iterfind(path or tag, namespaces or {}):
                    if elem.tag == tag:
                        yield _elem
        else:
            for elem in elements.iterfind(path or tag, namespaces or {}):
                if elem.tag == tag:
                    yield elem
    iterfind_function.__name__ = 'iterfind_xsd_%ss' % '_'.join(camel_case_split(split_qname(tag)[1])).lower()

    return iterfind_function

iterfind_xsd_import = create_iterfind_by_tag(XSD_IMPORT_TAG)
iterfind_xsd_include = create_iterfind_by_tag(XSD_INCLUDE_TAG)
iterfind_xsd_redefine = create_iterfind_by_tag(XSD_REDEFINE_TAG)
iterfind_xsd_simple_types = create_iterfind_by_tag(XSD_SIMPLE_TYPE_TAG)
iterfind_xsd_complex_types = create_iterfind_by_tag(XSD_COMPLEX_TYPE_TAG)
iterfind_xsd_attributes = create_iterfind_by_tag(XSD_ATTRIBUTE_TAG)
iterfind_xsd_attribute_groups = create_iterfind_by_tag(XSD_ATTRIBUTE_GROUP_TAG)
iterfind_xsd_elements = create_iterfind_by_tag(XSD_ELEMENT_TAG)
iterfind_xsd_groups = create_iterfind_by_tag(XSD_GROUP_TAG)


#
# Defines the update functions for XML Schema structures
def create_load_function(filter_function):

    def load_xsd_globals(xsd_globals, schemas):
        redefinitions = []
        for schema in schemas:
            if schema.built:
                continue

            target_namespace = schema.target_namespace
            for elem in iterfind_xsd_redefine(schema.root):
                for child in filter_function(elem):
                    qname = get_qname(target_namespace, get_xsd_attribute(child, 'name'))
                    redefinitions.append((qname, (child, schema)))

            for elem in filter_function(schema.root):
                qname = get_qname(target_namespace, get_xsd_attribute(elem, 'name'))
                try:
                    xsd_globals[qname].append((elem, schema))
                except KeyError:
                    xsd_globals[qname] = (elem, schema)
                except AttributeError:
                    xsd_globals[qname] = [xsd_globals[qname], (elem, schema)]

        for qname, obj in redefinitions:
            if qname not in xsd_globals:
                raise XMLSchemaParseError("not a redefinition!", obj[0])
            try:
                xsd_globals[qname].append(obj)
            except KeyError:
                xsd_globals[qname] = obj
            except AttributeError:
                xsd_globals[qname] = [xsd_globals[qname], obj]

    return load_xsd_globals

load_xsd_simple_types = create_load_function(iterfind_xsd_simple_types)
load_xsd_attributes = create_load_function(iterfind_xsd_attributes)
load_xsd_attribute_groups = create_load_function(iterfind_xsd_attribute_groups)
load_xsd_complex_types = create_load_function(iterfind_xsd_complex_types)
load_xsd_elements = create_load_function(iterfind_xsd_elements)
load_xsd_groups = create_load_function(iterfind_xsd_groups)


#
# Defines the builder functions for XML Schema structures
def create_builder_function(factory_key):

    def build_xsd_map(xsd_globals, tag, **kwargs):
        global_names = set(xsd_globals.keys())
        factory_function = kwargs.get(factory_key)
        errors_counter = 0
        i = 0
        while True:
            i += 1
            missing = []
            errors = []
            for qname in global_names:
                obj = xsd_globals[qname]
                try:
                    if isinstance(obj, XsdBase):
                        elem, schema = obj.elem, obj.schema
                        if elem is None or elem.tag != tag or schema.built:
                            continue
                        res_qname, xsd_instance = factory_function(
                            elem, schema, obj, is_global=True, **kwargs
                        )
                    elif isinstance(obj, tuple):
                        elem, schema = obj
                        if elem.tag != tag:
                            continue
                        res_qname, xsd_instance = factory_function(
                            elem, schema, is_global=True, **kwargs
                        )
                    elif isinstance(obj, list):
                        start = int(isinstance(obj[0], XsdBase))
                        xsd_instance = obj[0] if start else None
                        for k in range(start, len(obj)):
                            elem, schema = obj[k]
                            if elem.tag != tag:
                                break
                            res_qname, xsd_instance = factory_function(
                                elem, schema, xsd_instance, is_global=True, **kwargs
                            )
                            obj[0] = xsd_instance
                    else:
                        raise XMLSchemaTypeError("unexpected type %r for XSD global %r" % (type(obj), qname))

                except (XMLSchemaTypeError, XMLSchemaLookupError) as err:
                    _logger.debug("XSD reference %s not yet defined: elem.attrib=%r", err, elem.attrib)
                    missing.append(qname)
                    if isinstance(err, XMLSchemaLookupError):
                        errors.append(err)
                    if len(missing) == errors_counter:
                        raise errors[0] if errors else XMLSchemaParseError(message=str(err), elem=elem)
                else:
                    if elem.tag != tag:
                        continue
                    if res_qname != qname:
                        raise XMLSchemaParseError("wrong result name: %r != %r" % (res_qname, qname))
                    _logger.debug("Update XSD reference: target[%r] = %r", res_qname, xsd_instance)
                    xsd_globals[qname] = xsd_instance

            if not missing:
                break
            errors_counter = len(missing)
            global_names = missing

    return build_xsd_map

build_xsd_simple_types = create_builder_function('simple_type_factory')
build_xsd_attributes = create_builder_function('attribute_factory')
build_xsd_attribute_groups = create_builder_function('attribute_group_factory')
build_xsd_complex_types = create_builder_function('complex_type_factory')
build_xsd_elements = create_builder_function('element_factory')
build_xsd_groups = create_builder_function('group_factory')


class XsdGlobals(object):
    """
    Mediator class for related XML schema instances. It stores the global 
    declarations defined in the registered schemas. Register a schema to 
    add it's declarations to the global maps.

    :param validator: the XMLSchema class that have to be used for initializing \
    the object.
    """

    def __init__(self, validator):
        self.validator = validator
        self.namespaces = URIDict()  # Registered schemas by namespace URI
        self.resources = URIDict()  # Registered schemas by resource URI

        self.types = {}  # Global types
        self.attributes = {}  # Global attributes
        self.attribute_groups = {}  # Attribute groups
        self.groups = {}  # Model groups
        self.elements = {}  # Global elements
        self.base_elements = {}  # Global elements + global groups expansion
        self._view_cache = {}  # Cache for namespace views

        self.types.update(validator.BUILTIN_TYPES)

    def copy(self):
        """Makes a copy of the object."""
        obj = XsdGlobals(self.validator)
        obj.namespaces.update(self.namespaces)
        obj.resources.update(self.resources)
        obj.types.update(self.types)
        obj.attributes.update(self.attributes)
        obj.attribute_groups.update(self.attribute_groups)
        obj.groups.update(self.groups)
        obj.elements.update(self.elements)
        obj.base_elements.update(self.base_elements)
        return obj

    __copy__ = copy

    def register(self, schema):
        """
        Registers an XMLSchema instance.         
        """
        if schema.uri:
            if schema.uri not in self.resources:
                self.resources[schema.uri] = schema
            elif self.resources[schema.uri] != schema:
                return

        try:
            ns_schemas = self.namespaces[schema.target_namespace]
        except KeyError:
            self.namespaces[schema.target_namespace] = [schema]
        else:
            if schema in ns_schemas:
                return
            if not any([schema.uri == obj.uri for obj in ns_schemas]):
                ns_schemas.append(schema)

    def get_globals(self, map_name, namespace, fqn_keys=True):
        """
        Get a global map for a namespace. The map is cached by the instance.

        :param map_name: can be the name of one of the XSD global maps \
        (``'attributes'``, ``'attribute_groups'``, ``'elements'``, \
        ``'groups'``, ``'elements'``).
        :param namespace: is an optional mapping from namespace prefix \
        to full qualified name. 
        :param fqn_keys: if ``True`` the returned map's keys are fully \
        qualified names, if ``False`` the returned map's keys are local names.
        :return: a dictionary.
        """
        try:
            return self._view_cache[(map_name, namespace, fqn_keys)]
        except KeyError:
            if fqn_keys:
                view = self._view_cache[(map_name, namespace, fqn_keys)] = {
                    k: v for k, v in getattr(self, map_name).items()
                    if namespace == get_namespace(k)
                }
            else:
                view = self._view_cache[(map_name, namespace, fqn_keys)] = {
                    local_name(k): v for k, v in getattr(self, map_name).items()
                    if namespace == get_namespace(k)
                }
            return view

    def iter_schemas(self):
        """Creates an iterator for the schemas registered in the instance."""
        for ns_schemas in self.namespaces.values():
            for schema in ns_schemas:
                yield schema

    def clear(self, remove_schemas=False):
        """
        Clears the instance maps, removing also all the registered schemas 
        and cleaning the cache.
        """
        self.types.clear()
        self.attributes.clear()
        self.attribute_groups.clear()
        self.groups.clear()
        self.elements.clear()
        self.base_elements.clear()
        self._view_cache.clear()

        self.types.update(self.validator.BUILTIN_TYPES)
        for schema in self.iter_schemas():
            schema.built = False

        if remove_schemas:
            self.namespaces = URIDict()
            self.resources = URIDict()

    def build(self):
        """
        Builds the schemas registered in the instance, excluding
        those that are already built.
        """
        kwargs = self.validator.OPTIONS.copy()

        # Load and build global declarations
        load_xsd_simple_types(self.types, self.iter_schemas())
        build_xsd_simple_types(self.types, XSD_SIMPLE_TYPE_TAG, **kwargs)
        load_xsd_attributes(self.attributes, self.iter_schemas())
        build_xsd_attributes(self.attributes, XSD_ATTRIBUTE_TAG, **kwargs)
        load_xsd_attribute_groups(self.attribute_groups, self.iter_schemas())
        build_xsd_attribute_groups(self.attribute_groups, XSD_ATTRIBUTE_GROUP_TAG, **kwargs)
        load_xsd_complex_types(self.types, self.iter_schemas())
        build_xsd_complex_types(self.types, XSD_COMPLEX_TYPE_TAG, **kwargs)
        load_xsd_elements(self.elements, self.iter_schemas())
        build_xsd_elements(self.elements, XSD_ELEMENT_TAG, **kwargs)
        load_xsd_groups(self.groups, self.iter_schemas())
        build_xsd_groups(self.groups, XSD_GROUP_TAG, **kwargs)

        # Build all local declarations
        build_xsd_groups(self.groups, XSD_GROUP_TAG, parse_local_groups=True, **kwargs)
        build_xsd_complex_types(self.types, XSD_COMPLEX_TYPE_TAG, parse_local_groups=True, **kwargs)
        build_xsd_elements(self.elements, XSD_ELEMENT_TAG, parse_local_groups=True, **kwargs)

        # Update base_elements
        self.base_elements.update(self.elements)
        for group in self.groups.values():
            self.base_elements.update({e.name: e for e in group.iter_elements()})

        for schema in self.iter_schemas():
            schema.built = True
