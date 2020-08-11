import inspect
import json
import os
import requests
import rdflib.parser
import timeout_decorator
from functools import wraps
import re
import xml.etree.ElementTree as ET

from geomet import wkt
from rdflib import URIRef, BNode, Literal
from rdflib.namespace import Namespace, RDF, SKOS, RDFS

from idgo_admin.exceptions import DcatBaseError
from idgo_admin import logger


DCT = Namespace("http://purl.org/dc/terms/")
DCAT = Namespace("http://www.w3.org/ns/dcat#")
ADMS = Namespace("http://www.w3.org/ns/adms#")
VCARD = Namespace("http://www.w3.org/2006/vcard/ns#")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
LOCN = Namespace('http://www.w3.org/ns/locn#')
GSP = Namespace('http://www.opengis.net/ont/geosparql#')
OWL = Namespace('http://www.w3.org/2002/07/owl#')

namespaces = {
    'dct': DCT,
    'dcat': DCAT,
    'adms': ADMS,
    'vcard': VCARD,
    'foaf': FOAF,
    'skos': SKOS,
    'locn': LOCN,
    'gsp': GSP,
    'owl': OWL,
    'rdfs': RDFS,
    'rdf': RDF
}

GEOJSON_IMT = 'https://www.iana.org/assignments/media-types/application/vnd.geo+json'

profiles=['euro_dcat_ap']


DCAT_TIMEOUT = 36000


class DcatTimeoutError(Exception):
    message = "Le service DCAT met du temps à répondre, celui-ci est peut-être temporairement inaccessible."


class DcatError(DcatBaseError):
    pass


def timeout(fun):
    t = DCAT_TIMEOUT  # in seconds

    @timeout_decorator.timeout(t, use_signals=False)
    def return_with_timeout(fun, args=tuple(), kwargs=dict()):
        return fun(*args, **kwargs)

    @wraps(fun)
    def wrapper(*args, **kwargs):
        return return_with_timeout(fun, args=args, kwargs=kwargs)

    return wrapper


class DcatExceptionsHandler(object):

    def __init__(self, ignore=None):
        self.ignore = ignore or []

    def __call__(self, f):
        @wraps(f)
        def wrapper(*args, **kwargs):

            root_dir = os.path.dirname(os.path.abspath(__file__))
            info = inspect.getframeinfo(inspect.stack()[1][0])
            logger.debug(
                'Run {} (called by file "{}", line {}, in {})'.format(
                    f.__qualname__,
                    info.filename.replace(root_dir, '.'),
                    info.lineno,
                    info.function))

            try:
                return f(*args, **kwargs)
            except Exception as e:
                logger.exception(e)
                if isinstance(e, timeout_decorator.TimeoutError):
                    raise DcatTimeoutError
                if self.is_ignored(e):
                    return f(*args, **kwargs)
                raise DcatError("Une erreur critique est survenue lors de l'appel au DCAT distant.")
        return wrapper

    def is_ignored(self, exception):
        return type(exception) in self.ignore


class RDFProfile(object):
    '''Base class with helper methods for implementing RDF parsing profiles

       This class should not be used directly, but rather extended to create
       custom profiles
    '''

    def __init__(self, graph):
        '''Class constructor
        Graph is an rdflib.Graph instance.
        '''

        self.g = graph

    def _datasets(self):
        '''
        Generator that returns all DCAT datasets on the graph

        Yields rdflib.term.URIRef objects that can be used on graph lookups
        and queries
        '''
        for dataset in self.g.subjects(RDF.type, DCAT.Dataset):
            yield dataset

    def _distributions(self, dataset):
        '''
        Generator that returns all DCAT distributions on a particular dataset

        Yields rdflib.term.URIRef objects that can be used on graph lookups
        and queries
        '''
        for distribution in self.g.objects(dataset, DCAT.distribution):
            yield distribution

    def _keywords(self, dataset_ref):
        '''
        Returns all DCAT keywords on a particular dataset
        '''
        keywords = self._object_value_list(dataset_ref, DCAT.keyword) or []
        # Split keywords with commas
        keywords_with_commas = [k for k in keywords if ',' in k]
        for keyword in keywords_with_commas:
            keywords.remove(keyword)
            keywords.extend([k.strip() for k in keyword.split(',')])
        return keywords

    def _object(self, subject, predicate):
        '''
        Helper for returning the first object for this subject and predicate

        Both subject and predicate must be rdflib URIRef or BNode objects

        Returns an rdflib reference (URIRef or BNode) or None if not found
        '''
        for _object in self.g.objects(subject, predicate):
            return _object
        return None

    def _object_value(self, subject, predicate):
        '''
        Given a subject and a predicate, returns the value of the object

        Both subject and predicate must be rdflib URIRef or BNode objects

        If found, the str representation is returned, else an empty string
        '''
        default_lang = 'en'
        fallback = ''
        for o in self.g.objects(subject, predicate):
            if isinstance(o, Literal):
                if o.language and o.language == default_lang:
                    return str(o)
                # Use first object as fallback if no object with the default language is available
                elif fallback == '':
                    fallback = str(o)
            else:
                return str(o)
        return fallback

    def _object_value_int(self, subject, predicate):
        '''
        Given a subject and a predicate, returns the value of the object as an
        integer

        Both subject and predicate must be rdflib URIRef or BNode objects

        If the value can not be parsed as intger, returns None
        '''
        object_value = self._object_value(subject, predicate)
        if object_value:
            try:
                return int(float(object_value))
            except ValueError:
                pass
        return None

    def _object_value_list(self, subject, predicate):
        '''
        Given a subject and a predicate, returns a list with all the values of
        the objects

        Both subject and predicate must be rdflib URIRef or BNode  objects

        If no values found, returns an empty string
        '''
        return [str(o) for o in self.g.objects(subject, predicate)]

    def _contact_details(self, subject, predicate):
        '''
        Returns a dict with details about a vcard expression

        Both subject and predicate must be rdflib URIRef or BNode objects

        Returns keys for uri, name and email with the values set to
        an empty string if they could not be found
        '''

        contact = {}

        for agent in self.g.objects(subject, predicate):

            contact['author'] = self._object_value(agent, VCARD.fn)

            contact['author_email'] = self._object_value(agent, VCARD.hasEmail)

        return contact

    def _spatial(self, subject, predicate):
        '''
        Returns a dict with details about the spatial location

        Both subject and predicate must be rdflib URIRef or BNode objects

        Returns keys for uri, text or geom with the values set to
        None if they could not be found.

        Geometries are always returned in GeoJSON. If only WKT is provided,
        it will be transformed to GeoJSON.

        Check the notes on the README for the supported formats:

        https://github.com/ckan/ckanext-dcat/#rdf-dcat-to-ckan-dataset-mapping
        '''

        uri = None
        text = None
        geom = None

        for spatial in self.g.objects(subject, predicate):

            if isinstance(spatial, URIRef):
                uri = str(spatial)

            if isinstance(spatial, Literal):
                text = str(spatial)

            if (spatial, RDF.type, DCT.Location) in self.g:
                for geometry in self.g.objects(spatial, LOCN.geometry):
                    if (geometry.datatype == URIRef(GEOJSON_IMT) or
                            not geometry.datatype):
                        try:
                            json.loads(str(geometry))
                            geom = str(geometry)
                        except (ValueError, TypeError):
                            pass
                    if not geom and geometry.datatype == GSP.wktLiteral:
                        try:
                            geom = json.dumps(wkt.loads(str(geometry)))
                        except (ValueError, TypeError):
                            pass
                for label in self.g.objects(spatial, SKOS.prefLabel):
                    text = str(label)
                for label in self.g.objects(spatial, RDFS.label):
                    text = str(label)

        return {
            'uri': uri,
            'text': text,
            'geom': geom,
        }

    def _distribution_format(self, distribution):
        '''
        Returns the Internet Media Type for a distribution

        Given a reference (URIRef or BNode) to a dcat:Distribution, it will
        try to extract the media type (previously knowm as MIME type), eg
        `text/csv`

        Values for the media type will be checked in the following order:

        1. literal value of dcat:mediaType
        2. literal value of dct:format if it contains a '/' character
        3. value of dct:format if it is an instance of dct:IMT, eg:

            <dct:format>
                <dct:IMT rdf:value="text/html" rdfs:label="HTML"/>
            </dct:format>
        4. value of dct:format if it is an URIRef and appears to be an IANA type

        Return the media type, set to None if
        it couldn't be found.
        '''

        imt = self._object_value(distribution, DCAT.mediaType)

        _format = self._object(distribution, DCT['format'])
        if isinstance(_format, Literal):
            if not imt and '/' in _format:
                imt = str(_format)

        elif isinstance(_format, (BNode, URIRef)):
            if self._object(_format, RDF.type) == DCT.IMT:
                if not imt:
                    imt = str(self.g.value(_format, default=None))
            elif isinstance(_format, URIRef):
                # If the URIRef does not reference a BNode, it could reference an IANA type.
                format_uri = str(_format)
                if 'iana.org/assignments/media-types' in format_uri and not imt:
                    imt = format_uri

        return imt

    # Public methods for profiles to implement

    def parse_dataset(self, dataset_dict, dataset_ref):
        '''
        Creates a dataset dict from the RDF graph

        The `dataset_dict` is passed to all the loaded profiles before being
        yielded, so it can be further modified by each one of them.
        `dataset_ref` is an rdflib URIRef object
        that can be used to reference the dataset when querying the graph.

        Returns a dataset dict that can be passed to eg `package_create`
        or `package_update`
        '''
        return dataset_dict


class EuropeanDCATAPProfile(RDFProfile):
    '''
    An RDF profile based on the DCAT-AP for data portals in Europe

    More information and specification:

    https://joinup.ec.europa.eu/asset/dcat_application_profile

    '''

    def parse_dataset(self, dataset_dict, dataset_ref):

        dataset_dict['resources'] = []

        # Basic fields
        for key, predicate in (
                ('title', DCT.title),
                ('notes', DCT.description),
                ('url', DCAT.landingPage),
                ('version', OWL.versionInfo),
                ):
            value = self._object_value(dataset_ref, predicate)
            if value:
                dataset_dict[key] = value

        if not dataset_dict.get('version'):
            # adms:version was supported on the first version of the DCAT-AP
            value = self._object_value(dataset_ref, ADMS.version)
            if value:
                dataset_dict['version'] = value

        # Tags
        tags_val = [tag for tag in self._keywords(dataset_ref)]

        tags = []
        for tag in tags_val:
            if not tag:
                continue
            keyword_match = re.compile('[\w\s\-.]*$', re.UNICODE)
            if keyword_match.match(tag):
                tags.append({'display_name': tag})

        dataset_dict['tags'] = tags
        dataset_dict['num_tags'] = len(tags)

        #  Simple values
        for key, predicate in (
                ('metadata_created', DCT.issued),
                ('dataset_creation_date', DCT.issued),
                ('dataset_publication_date', DCT.issued),
                ('metadata_modified', DCT.modified),
                ('dataset_modification_date', DCT.modified),
                ('id', DCT.identifier),
                ('frequency', DCT.accrualPeriodicity),
                ('type', DCT.type),
                ('datatype', DCT.type),
                ):
            value = self._object_value(dataset_ref, predicate)
            if value:
                dataset_dict[key] = value

        # Contact details
        contact = self._contact_details(dataset_ref, DCAT.contactPoint)

        if contact:
            for key in ('author', 'author_email'):
                if contact.get(key):
                    dataset_dict[key] = contact.get(key)
            dataset_dict["maintainer"] = dataset_dict['author']
            dataset_dict["maintainer_email"] = dataset_dict['author_email']

        # Spatial
        spatial = self._spatial(dataset_ref, DCT.spatial)
        for key in ('spatial'):
            if spatial.get(key):
                dataset_dict[key] = spatial.get(key)

        dataset_dict['license_titles'] = []
        # Resources
        for distribution in self._distributions(dataset_ref):

            resource_dict = {
                'name': '',
                'description': '',
                'protocol': ''}

            #  Simple values
            license = self._object_value(distribution, DCT.license)

            resource_dict['url'] = (self._object_value(distribution,
                                                       DCAT.downloadURL) or
                                    self._object_value(distribution,
                                                       DCAT.accessURL))

            imt = self._distribution_format(distribution)

            if imt:
                resource_dict['mimetype'] = imt

            dataset_dict['resources'].append(resource_dict)
            if license is not None:
                dataset_dict['license_titles'].append(license)

        dataset_dict['license_titles'] = list(dict.fromkeys(dataset_dict['license_titles']))
        dataset_dict['num_resources'] = len(dataset_dict['resources'])
        dataset_dict['organization'] = {
            'id': None,
            'name': None,
            'title': None,
            'description': None,
            'created': None,
            'is_organization': True,
            'state': 'active',
            'image_url': None,
            'type': 'organization',
            'approval_status': 'approved',
            }

        return dataset_dict


class DcatBaseHandler(object):

    def __init__(self, url):
        self.url = url
        self.graph = rdflib.Graph()
        self.graph.parse(self.url)
        self.profile = EuropeanDCATAPProfile(self.graph)
        self.xml_dict = self._get_xml_dict()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def close(self):
        self.xml_dict = None
        self.profile = None
        self.graph = None
        self.url = None

    def _get_xml_dict(self):
        xml_data = requests.get(self.url, verify=False)
        xml_object = ET.fromstring(xml_data.content)

        for key, value in namespaces.items():
            ET.register_namespace(key, value)
        xml_dict = {}
        for root in xml_object[0].findall('dcat:dataset', namespaces):
            xml_dict[root[0].find('dct:identifier', namespaces).text] = ET.tostring(root)
        return xml_dict

    @DcatExceptionsHandler()
    def get_packages(self):
        for dataset_ref in self.graph.subjects(RDF.type, DCAT.Dataset):
            dataset_dict = {'state': 'active',
                            'type': 'dataset',
                            'id': None,
                            'name':  None,
                            'title': None,
                            'notes': None,
                            'thumbnail': None,
                            'num_tags': 0,
                            'tags': [],
                            'groups': [],
                            'metadata_created': None,
                            'metadata_modified': None,
                            'dataset_creation_date': None,
                            'dataset_modification_date': None,
                            'dataset_publication_date': None,
                            'frequency': None,
                            'geocover': None,
                            'granularity': None,
                            'organization': {},
                            'license_titles': [],
                            'support': None,
                            'datatype': None,
                            'author': None,
                            'author_email': None,
                            'maintainer': None,
                            'maintainer_email': None,
                            'num_resources': 0,
                            'resources': None,
                            'spatial': None,
                            'bbox': None,
                            'xml': None,
                            }
            dataset_dict = self.profile.parse_dataset(dataset_dict, dataset_ref)
            dataset_dict['xml'] = self.xml_dict.pop(dataset_dict['id'])
            yield dataset_dict
