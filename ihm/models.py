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


from django.db import models


class IHMSettings(models.Model):

    class Meta(object):
        verbose_name = "Configuration particulière des IHM"
        verbose_name_plural = "Configurations particulières des IHM"
        ordering = ('name', )

    name = models.SlugField(
        verbose_name="Identifiant de l'objet",
        unique=True,
        db_index=True,
        max_length=100,
        )

    contents = models.TextField(verbose_name='Contenu')

    TARGET_CHOICES = (
        ('ckan', "Ckan"),
        ('admin', "Admin"),
        )

    target = models.CharField(
        verbose_name='Cible',
        max_length=100,
        blank=True,
        null=True,
        choices=TARGET_CHOICES,
        default='ckan',
        )

    activate = models.BooleanField(
        verbose_name="Activer",
        default=False,
        )

    def __str__(self):
        return str(self.name)
