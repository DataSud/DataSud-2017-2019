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


class DataType(models.Model):

    class Meta(object):
        verbose_name = "Type de donnée"
        verbose_name_plural = "Types de données"

    slug = models.SlugField(
        verbose_name="Slug",
        max_length=100,
        unique=True,
        blank=True,
        db_index=True,
        )

    name = models.CharField(
        verbose_name="Nom",
        max_length=100,
        )

    description = models.CharField(
        verbose_name='Description',
        max_length=1024,
        )

    def __str__(self):
        return self.name
