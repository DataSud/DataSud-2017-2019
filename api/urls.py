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


from api.views import DatasetList as APIDatasetList
from api.views import DatasetShow as APIDatasetShow
from api.views import DatasetMDShow as APIDatasetMDShow
from api.views import OrganisationList as APIOrganisationList
from api.views import OrganisationShow as APIOrganisationShow
from api.views import ResourceList as APIResourceList
from api.views import ResourceShow as APIResourceShow
from api.views import UserList as APIUserList
from api.views import UserShow as APIUserShow
from django.conf.urls import url


urlpatterns = [
    url('^user/?$', APIUserList.as_view(), name='user_list'),
    url('^user/(?P<username>[a-z0-9\\-]+)/?$', APIUserShow.as_view(), name='user_show'),
    url('^organisation/?$', APIOrganisationList.as_view(), name='organisation_list'),
    url('^organisation/(?P<organisation_name>[a-z0-9\\-]+)/?$', APIOrganisationShow.as_view(), name='organisation_show'),
    url('^dataset/?$', APIDatasetList.as_view(), name='dataset_list'),
    url('^dataset/(?P<dataset_name>[a-z0-9\\-]+)/?$', APIDatasetShow.as_view(), name='dataset_show'),
    url('^dataset/(?P<dataset_name>[a-z0-9\\-]+)/md/?$', APIDatasetMDShow.as_view(), name='dataset_md_show'),
    url('^dataset/(?P<dataset_name>[a-z0-9\\-]+)/resource/?$', APIResourceList.as_view(), name='resource_list'),
    url('^dataset/(?P<dataset_name>[a-z0-9\\-]+)/resource/(?P<resource_id>[a-z0-9\\-]+)/?$', APIResourceShow.as_view(), name='resource_show'),
    ]
