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


from django.core.management.base import BaseCommand
from idgo_admin.ckan_module import CkanHandler
from idgo_admin.ckan_module import CkanUserHandler
from idgo_admin.models import Profile
from idgo_admin.models import Resource
import json


def get_all_users_for_organisations(list_id):
    return [
        profile.user.username
        for profile in Profile.objects.filter(
            organisation__in=list_id, organisation__is_active=True)]


class Command(BaseCommand):

    help = """Synchronisation des droits des utilisateur
              sur les ressources par organisations."""

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

    def handle(self, *args, **options):
        for resource in Resource.objects.exclude(organisations_allowed=None):
            dataset = resource.dataset

            ckan_params = {
                'id': str(resource.ckan_id),
                'restricted': json.dumps({
                    'allowed_users': ','.join(
                        get_all_users_for_organisations(
                            [r.pk for r in resource.organisations_allowed.all()])),
                    'level': 'only_allowed_users'})}

            apikey = CkanHandler.get_user(dataset.editor.username)['apikey']
            with CkanUserHandler(apikey=apikey) as ckan:
                package = ckan.get_package(str(dataset.ckan_id))
                ckan.push_resource(package, **ckan_params)
