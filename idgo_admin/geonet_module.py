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


from django.conf import settings
from idgo_admin.utils import Singleton
from owslib.csw import CatalogueServiceWeb
import requests
from urllib.parse import urljoin


GEONET_URL = settings.GEONETWORK_URL
GEONET_USERNAME = settings.GEONETWORK_LOGIN
GEONET_PASSWORD = settings.GEONETWORK_PASSWORD
try:
    GEONET_TIMEOUT = settings.GEONET_TIMEOUT
except AttributeError:
    GEONET_TIMEOUT = 3600


class GeonetUserHandler(metaclass=Singleton):

    def __init__(self):
        self.username = GEONET_USERNAME
        self.password = GEONET_PASSWORD
        self.remote = CatalogueServiceWeb(
            urljoin(GEONET_URL, 'srv/fre/csw-publication'),
            timeout=GEONET_TIMEOUT, lang='fr-FR',
            version='2.0.2', skip_caps=True,
            username=self.username, password=self.password)

    def _get(self, url, params):
        r = requests.get(
            url, params=params, auth=(self.username, self.password))
        r.raise_for_status()
        return r

    def _q(self, identifier):
        r = self._get(urljoin(GEONET_URL, 'srv/fre/q'),
                      {'uuid': identifier, '_content_type': 'json'})
        metadata = r.json().get('metadata')
        if metadata \
                and len(metadata) == 1 \
                and metadata[0]['uuid'] == identifier:
            return metadata[0]['id']
        # Sinon error ?

    def _md_publish(self, identifier):
        return self._get(
            urljoin(GEONET_URL, 'srv/fre/md.publish'), {'ids': identifier})

    def _transaction(self, ttype, identifier, record):
        params = {
            'identifier': identifier,
            'record': record,
            'ttype': ttype,
            'typename': 'gmd:MD_Metadata'}
        return self.remote.transaction(**params)

    def is_record_exists(self, id):
        return self.get_record(id) and True or False

    def get_record(self, id):
        try:
            self.remote.getrecordbyid(
                id=[id], outputschema='http://www.isotc211.org/2005/gmd')
        except requests.exceptions.HTTPError as e:
            if (e.response.status_code == 404):
                return None
            raise e
        else:
            return self.remote.records.get(id)

    def create_record(self, id, record):
        return self._transaction('insert', id, record)

    def update_record(self, id, record):
        return self._transaction('update', id, record)

    # def delete_record(self, id):
    #     return self.remote.transaction('delete', id)

    def publish(self, id):
        return self._md_publish(self._q(id))


GeonetUserHandler = GeonetUserHandler()
