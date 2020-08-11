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


from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.utils import timezone
from markdown import markdown


class Gdpr(models.Model):

    class Meta(object):
        verbose_name = "Modalités et conditions d'utilisation (RGPD)"

    title = models.TextField(
        verbose_name="Title",
        )

    description = models.TextField(
        verbose_name="Description",
        )

    issue_date = models.DateTimeField(
        verbose_name="Date d'émission",
        blank=False,
        null=False,
        default=timezone.now,
        )

    @property
    def description_as_html(self):
        return markdown(self.description)


class GdprUser(models.Model):

    class Meta(object):
        verbose_name = "RGPD / Utilisateur"
        unique_together = ('user', 'gdpr',)

    user = models.ForeignKey(
        to=User,
        verbose_name="Utilisateur",
        on_delete=models.CASCADE,
        )

    gdpr = models.ForeignKey(
        to='Gdpr',
        verbose_name="RGPD",
        on_delete=models.CASCADE,
        )

    validated_on = models.DateTimeField(
        verbose_name="Date de validation",
        blank=True,
        null=True,
        default=timezone.now,
        )
