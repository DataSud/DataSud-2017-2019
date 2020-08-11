# Copyright (c) 2017-2019 Neogeo-Technologies.
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


from django.utils.text import slugify
from functools import wraps
from idgo_admin.datagis import bounds_to_wkt
from idgo_admin.datagis import transform
from idgo_admin.exceptions import CswBaseError
from idgo_admin import logger
import inspect
import os
from owslib.csw import CatalogueServiceWeb
import re
import timeout_decorator


CSW_TIMEOUT = 36000


def timeout(fun):
    t = CSW_TIMEOUT  # in seconds

    @timeout_decorator.timeout(t, use_signals=False)
    def return_with_timeout(fun, args=tuple(), kwargs=dict()):
        return fun(*args, **kwargs)

    @wraps(fun)
    def wrapper(*args, **kwargs):
        return return_with_timeout(fun, args=args, kwargs=kwargs)

    return wrapper


class CswReadError(CswBaseError):
    message = "L'url ne semble pas indiquer un service CSW."


class CswTimeoutError(CswBaseError):
    message = "Le service CSW met du temps à répondre, celui-ci est peut-être temporairement inaccessible."


class CswError(CswBaseError):
    message = "Une erreur est survenue."


class CswExceptionsHandler(object):

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
                    raise CswTimeoutError
                if self.is_ignored(e):
                    return f(*args, **kwargs)
                raise CswError("Une erreur critique est survenue lors de l'appel au CSW distant.")
        return wrapper

    def is_ignored(self, exception):
        return type(exception) in self.ignore


class CswBaseHandler(object):

    def __init__(self, url, username=None, password=None):
        self.url = url
        self.username = username
        self.password = password
        try:
            self.remote = CatalogueServiceWeb(
                self.url, timeout=3600, lang='fr-FR', version='2.0.2',
                skip_caps=True, username=self.username, password=self.password)
        except Exception:
            raise CswReadError()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def close(self):
        # Fake
        logger.info('Close CSW connection')

    @CswExceptionsHandler()
    def get_packages(self, *args, **kwargs):
        self.remote.getrecords2(**kwargs)
        records = self.remote.records.copy()
        res = []
        for k in list(records.keys()):
            try:
                package = self.get_package(k)
            except CswBaseError as e:
                logger.warning(e)
            else:
                res.append(package)
        return res

    @CswExceptionsHandler()
    def get_package(self, id, *args, **kwargs):

        self.remote.getrecordbyid(
            [id], outputschema='http://www.isotc211.org/2005/gmd')

        records = self.remote.records.copy()

        rec = records[id]

        xml = rec.xml
        if not rec.__class__.__name__ == 'MD_Metadata':
            raise CswBaseError('outputschema error')
        # if not (rec.stdname == 'ISO 19115:2003/19139' and rec.stdver == '1.0'):
        #     raise CswBaseError('outputschema error: stdname:{} stdver:{}'.format(rec.stdname, rec.stdver))
        if rec.hierarchy and not rec.hierarchy == 'dataset':  # 7218
            raise CswBaseError('MD {id} is not a Dataset'.format(rec.identifier))

        # _encoding = rec.charset

        id = rec.identifier
        title = rec.identification.title
        name = slugify(title)
        notes = description = rec.identification.abstract
        thumbnail = None

        keywords, themes = [], []
        for item in rec.identification.keywords2:
            if not item.__class__.__name__ == 'MD_Keywords':
                continue
            if item.type == 'theme':
                themes += item.keywords
            keywords += item.keywords

        tags = []
        for keyword in keywords:
            if not keyword:
                continue
            keyword_match = re.compile('[\w\s\-.]*$', re.UNICODE)
            if keyword_match.match(keyword):
                tags.append({'display_name': keyword})

        groups = [
            {'name': name} for name in rec.identification.topiccategory]
        if themes:
            groups += [{'name': name} for name in themes]

        dataset_creation_date = None
        dataset_modification_date = None
        dataset_publication_date = None
        if rec.identification.date:
            for item in rec.identification.date:
                if not item.__class__.__name__ == 'CI_Date':
                    continue
                if item.type == 'creation':
                    dataset_creation_date = item.date
                elif item.type == 'publication':
                    dataset_publication_date = item.date
                elif item.type in ('modification', 'revision'):
                    dataset_modification_date = item.date

        frequency = None
        geocover = None
        granularity = None
        organisation = {
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

        license_titles = rec.identification.uselimitation or []

        support = None
        data_type = None
        author = None
        author_email = None
        maintainer = None
        maintainer_email = None

        spatial = None
        bbox = None
        if rec.identification.bbox:
            xmin = rec.identification.bbox.minx
            ymin = rec.identification.bbox.miny
            xmax = rec.identification.bbox.maxx
            ymax = rec.identification.bbox.maxy

            bbox = transform(bounds_to_wkt(xmin, ymin, xmax, ymax), '4326')
            spatial = {
                'type': 'Polygon',
                'coordinates': [[
                    [xmin, ymin],
                    [xmax, ymin],
                    [xmax, ymax],
                    [xmin, ymax],
                    [xmin, ymin]
                    ]]
                }

        resources = []
        for item in rec.distribution.online:
            name = hasattr(item, 'name') and item.name or ''
            description = hasattr(item, 'description') and item.description or ''
            protocol = hasattr(item, 'protocol') and item.protocol or ''
            mimetype = hasattr(item, 'mimetype') and item.mimetype or ''
            url = hasattr(item, 'url') and item.url or ''
            resource = {
                'name': name,
                'description': description,
                'protocol': protocol,
                'mimetype': mimetype,
                'url': url,
                }
            resources.append(resource)

        return {
            'state': 'active',
            'type': 'dataset',
            'id': id,
            'name': name,
            'title': title,
            'notes': notes,
            'thumbnail': thumbnail,
            'num_tags': len(tags),
            'tags': tags,
            'groups': groups,
            'metadata_created': dataset_creation_date,
            'metadata_modified': dataset_modification_date,
            'dataset_creation_date': dataset_creation_date,
            'dataset_modification_date': dataset_modification_date,
            'dataset_publication_date': dataset_publication_date,
            'frequency': frequency,
            'geocover': geocover,
            'granularity': granularity,
            'organization': organisation,
            'license_titles': license_titles,
            'support': support,
            'datatype': data_type,
            'author': author,
            'author_email': author_email,
            'maintainer': maintainer,
            'maintainer_email': maintainer_email,
            'num_resources': len(resources),
            'resources': resources,
            'spatial': spatial,
            'bbox': bbox,
            'xml': xml,
            }
