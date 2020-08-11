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


class SupportedCrs(models.Model):

    class Meta(object):
        verbose_name = "CRS supporté par l'application"
        verbose_name_plural = "CRS supportés par l'application"

    # TODO: pk

    auth_name = models.CharField(
        verbose_name="Authority Name",
        max_length=100,
        db_index=True,
        default='EPSG',
        )

    auth_code = models.CharField(
        verbose_name="Authority Code",
        max_length=100,
        db_index=True,
        )

    description = models.TextField(
        verbose_name="Description",
        blank=True,
        null=True,
        )

    regex = models.TextField(
        verbose_name="Expression régulière",
        blank=True,
        null=True,
        )

    @property
    def authority(self):
        return '{}:{}'.format(self.auth_name, self.auth_code)

    def __str__(self):
        return '{}:{} ({})'.format(
            self.auth_name, self.auth_code, self.description)
