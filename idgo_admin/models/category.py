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
from django.contrib.gis.db import models
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.utils.text import slugify
from idgo_admin.ckan_module import CkanHandler
import json
import os
import uuid


MDEDIT_HTML_PATH = 'mdedit/html/'
MDEDIT_CONFIG_PATH = 'mdedit/config/'
MDEDIT_LOCALES_PATH = os.path.join(MDEDIT_CONFIG_PATH, 'locales/fr/locales.json')
MDEDIT_DATASET_MODEL = 'models/model-dataset-empty.json'
MDEDIT_SERVICE_MODEL = 'models/model-service-empty.json'

locales_path = os.path.join(settings.BASE_DIR, 'idgo_admin/static/', MDEDIT_LOCALES_PATH)
try:
    with open(locales_path, 'r', encoding='utf-8') as f:
        MDEDIT_LOCALES = json.loads(f.read())
        iso_topics = MDEDIT_LOCALES['codelists']['MD_TopicCategoryCode']
        ISO_TOPIC_CHOICES = ((m['id'], m['value']) for m in iso_topics)
except Exception:
    MDEDIT_LOCALES = None
    ISO_TOPIC_CHOICES = None


class Category(models.Model):

    class Meta(object):
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"

    slug = models.SlugField(
        verbose_name="Slug",
        max_length=100,
        blank=True,
        unique=True,
        db_index=True,
        )

    ckan_id = models.UUIDField(
        verbose_name="Identifiant CKAN",
        editable=False,
        db_index=True,
        default=uuid.uuid4,
        )

    name = models.CharField(  # TODO title->TextField
        verbose_name="Nom",
        max_length=100,
        )

    alternate_titles = ArrayField(
        models.TextField(),
        verbose_name="Autres titres",
        blank=True,
        null=True,
        size=None,
        )

    description = models.CharField(
        verbose_name="Description",
        max_length=1024,
        )

    iso_topic = models.CharField(
        verbose_name="Thème ISO",
        max_length=100,
        null=True,
        blank=True,
        choices=ISO_TOPIC_CHOICES,
        )

    picto = models.ImageField(
        verbose_name="Pictogramme",
        upload_to='logos/',
        null=True,
        blank=True,
        )

    def __str__(self):
        return self.name

    def sync_ckan(self):
        if self.pk:
            CkanHandler.update_group(self)
        else:
            CkanHandler.add_group(self)

    def clean(self):
        self.slug = slugify(self.name)
        try:
            self.sync_ckan()
        except Exception as e:
            raise ValidationError(e.__str__())


@receiver(pre_delete, sender=Category)
def pre_delete_category(sender, instance, **kwargs):
    if CkanHandler.is_group_exists(str(instance.ckan_id)):
        CkanHandler.del_group(str(instance.ckan_id))
