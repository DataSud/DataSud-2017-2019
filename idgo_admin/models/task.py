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
from django.contrib.postgres.fields import JSONField


class Task(models.Model):

    class Meta(object):
        verbose_name = "Tâche de synchronisation"
        verbose_name_plural = "Tâches de synchronisation"

    uuid = models.UUIDField(
        verbose_name="Id",
        null=True,
        blank=True,
        editable=False,
        unique=True,
        db_index=True,
        )

    action = models.TextField(
        verbose_name="Action",
        blank=True,
        null=True,
        )

    extras = JSONField(
        verbose_name="Extras",
        blank=True,
        null=True,
        )

    STATE_CHOICES = (
        ('succesful', "Tâche terminée avec succés"),
        ('failed', "Echec de la tâche"),
        ('running', "Tâche en cours de traitement"),
        )

    state = models.CharField(
        verbose_name="État",
        max_length=20,
        choices=STATE_CHOICES,
        default='running',
        )

    starting = models.DateTimeField(
        verbose_name="Début du traitement",
        auto_now_add=True,
        )

    end = models.DateTimeField(
        verbose_name="Fin du traitement",
        blank=True,
        null=True,
        )
