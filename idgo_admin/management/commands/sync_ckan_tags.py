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
from idgo_admin.ckan_module import CkanManagerHandler
from idgo_admin.models import DataType
from idgo_admin.models import Support


class Command(BaseCommand):

    help = 'Synchroniser les tags IDGO avec CKAN.'

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.ckan = CkanManagerHandler()

    def sync_tags(self, data, vocabulary_name):
        vocabulary = self.ckan.get_vocabulary(vocabulary_name)
        if not vocabulary:
            self.ckan.add_vocabulary(vocabulary, [entry.slug for entry in data])
            self.stdout.write("New vocabulary '{0}' created".format(entry.slug))
        else:
            for entry in data:
                if self.ckan.is_tag_exists(
                        entry.name, vocabulary_id=vocabulary['id']):
                    self.stdout.write("'{0}' already sync".format(entry.name))
                    continue
                self.ckan.add_tag(
                    entry.name, vocabulary_id=vocabulary['id'])
                self.stdout.write("'{0}' added".format(entry.name))

    def sync_group(self, queryset, group_type=None):
        for entry in queryset:
            if self.ckan.is_group_exists(entry.slug):
                self.stdout.write("'{0}' already exists".format(entry.slug))
                continue
            self.ckan.add_group(entry, type=group_type)
            self.stdout.write("'{0}' is created".format(entry.slug))

    def handle(self, *args, **options):
        self.sync_group(DataType.objects.all(), group_type='data_type')
        self.sync_group(Support.objects.all(), group_type='support')

        # self.sync_tags(DataType.objects.all(), 'data_type')
        # self.sync_tags(Support.objects.all(), 'support')

        self.stdout.write('Done!')
