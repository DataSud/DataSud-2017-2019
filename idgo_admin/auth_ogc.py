#!/idgo_venv/bin/python3
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


import logging
import os
import sys
from urllib.parse import parse_qs
from urllib.parse import urlparse
python_home = "/idgo_venv/"
activate_this = python_home + '/bin/activate_this.py'
exec(open(activate_this).read())
sys.path.append(python_home)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django  # noqa: E402
django.setup()
from django.contrib.auth.models import User  # noqa: E402
from django.db.models import Q  # noqa: E402
from functools import reduce  # noqa: E402
from idgo_admin.models import Dataset  # noqa: E402
from idgo_admin.models import Organisation   # noqa: E402
from idgo_admin.models import Resource  # noqa: E402
from operator import ior  # noqa: E402


logger = logging.getLogger('auth_ogc')
stream_handler = logging.StreamHandler()
# stream_handler.setLevel(logging.DEBUG)
logger.addHandler(stream_handler)
# logger.setLevel(logging.DEBUG)

AUTHORIZED_PREFIX = ['/maps/', '/wfs/', '/wms/', '/wxs/']
# used for parsing address when basic auth is provided
PRIVATE_AUTHORIZED_PREFIX = ["/private{prefix}".format(prefix=p)
                             for p in AUTHORIZED_PREFIX]


def retrieve_resources_through_ows_url(url):
    parsed_url = urlparse(url.lower())
    qs = parse_qs(parsed_url.query)
    if 'layers' in qs:
        layers = qs.get('layers')[-1]
    elif 'typename' in qs:
        layers = qs.get('typename')[-1]
    elif 'typenames' in qs:
        layers = qs.get('typenames')[-1]
    else:
        layers = None
    if not layers:
        return None
    layers = set(layers.replace(' ', '').split(','))
    layers = [layer.split(':')[-1] for layer in layers]
    datasets_filters = [
        Q(slug__in=layers),
        Q(organisation__in=Organisation.objects.filter(slug__in=layers).distinct()),
        ]
    datasets = Dataset.objects.filter(reduce(ior, datasets_filters)).distinct()
    resources_filters = [
        Q(dataset__in=datasets),
        Q(layer__name__in=layers),
        ]
    resources = Resource.objects.filter(reduce(ior, resources_filters)).distinct()
    return resources


def check_password(environ, user, password):

    url = environ['REQUEST_URI']

    logger.debug('Checking user %s rights to url %s', user, url)

    # check path is authorized

    is_path_authorized = False
    for prefix in AUTHORIZED_PREFIX + PRIVATE_AUTHORIZED_PREFIX:
        if url.startswith(prefix):
            is_path_authorized = True

    if not is_path_authorized:
        logger.error("path '%s' is unauthorized", url)
        return False

    # Get Capabilities and metadata are always athorized
    qs = parse_qs(urlparse(url.lower()).query)

    request = qs.get('request')
    logger.debug(qs)
    public_requests = [
        "getcapabilities",
        "getmetadata",
        "getlegendgraphic",
        "describefeaturetype",
        "describelayer",
        "getstyles",
        ]

    if request[-1] in public_requests:
        logger.debug("URL request is public")
        return True

    try:
        user = User.objects.get(username=user, is_active=True)
    except User.DoesNotExist:
        logger.debug("User %s does not exist (or is not active)" % user)
    else:
        if not user.check_password(password):
            logger.error("User %s provided bad password", user)
            return False

    resources = retrieve_resources_through_ows_url(url)
    if not resources:
        logger.error("Unable to get resources")
        return False
    # Refuse query if one of the resources is not available/authorized
    for resource in resources:
        if resource.anonymous_access:
            continue
        if not resource.is_profile_authorized(user):
            logger.error(
                "Resource '{resource}' is not authorized to user '{user}'.".format(
                    resource=resource.pk, user=user.username))
            return False
    return True


if __name__ == '__main__':
    while True:
        try:
            line = sys.stdin.readline().strip()
            logger.debug("REMAP ogc auth: %s" % line)
            headers = {"REQUEST_URI": line}
            # Remove querystring (handled by apache)
            path = line.split("?")[0]

            # if ressource is accessible by anonymous => public,
            # otherwise check password (=> private)
            if check_password(headers, "", ""):
                response = "http://localhost/public{uri}".format(uri=path)
            else:
                response = "http://localhost/private{uri}".format(uri=path)

            logger.debug("response : %s" % response)
            sys.stdout.write(response + '\n')
            sys.stdout.flush()
        except Exception as e:
            logger.error(e)
            sys.stdout.write('NULL\n')
            sys.stdout.flush()
