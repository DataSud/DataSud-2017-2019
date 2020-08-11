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


from django.contrib.gis.db import models
from django.contrib.postgres.fields import ArrayField


class License(models.Model):

    class Meta(object):
        verbose_name = "Licence"
        verbose_name_plural = "Licences"

    slug = models.SlugField(
        verbose_name="Slug",
        max_length=100,
        blank=True,
        unique=True,
        db_index=True,
        primary_key=True,
        )

    title = models.TextField(
        verbose_name="Titre",
        )

    alternate_titles = ArrayField(
        models.TextField(),
        verbose_name="Autres titres",
        blank=True,
        null=True,
        size=None,
        )

    url = models.URLField(
        verbose_name="URL",
        blank=True,
        null=True,
        )

    alternate_urls = ArrayField(
        models.URLField(),
        verbose_name="Autres URLs",
        null=True,
        blank=True,
        size=None,
        )

    domain_content = models.BooleanField(
        verbose_name="Domain Content",
        default=False,
        )

    domain_data = models.BooleanField(
        default=False,
        verbose_name="Domain Data",
        )

    domain_software = models.BooleanField(
        default=False,
        verbose_name="Domain Software",
        )

    STATUS_CHOICES = (
        ('active', 'Active'),
        ('deleted', 'Deleted'),
        )

    status = models.CharField(
        verbose_name="Status",
        max_length=7,
        choices=STATUS_CHOICES,
        default='active',
        )

    maintainer = models.TextField(
        verbose_name="Maintainer",
        null=True,
        blank=True,
        )

    CONFORMANCE_CHOICES = (
        ('approved', 'Approved'),
        ('not reviewed', 'Not reviewed'),
        ('rejected', 'Rejected'),
        )

    od_conformance = models.CharField(
        verbose_name="Open Definition Conformance",
        max_length=30,
        choices=CONFORMANCE_CHOICES,
        default='not reviewed',
        )

    osd_conformance = models.CharField(
        verbose_name="Open Source Definition Conformance",
        max_length=30,
        choices=CONFORMANCE_CHOICES,
        default='not reviewed',
        )

    def __str__(self):
        return self.title

    @property
    def ckan_id(self):
        return self.slug
