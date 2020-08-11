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


class TaskTracking(models.Model):

    class Meta(object):
        # db_table = 'celery_task_tracking'
        verbose_name = "Suivi"
        verbose_name_plural = "Suivi des tâches"

    uuid = models.UUIDField(
        verbose_name="UUID",
        unique=True,
        )

    task = models.TextField(
        verbose_name="Tâche",
        blank=True,
        null=True,
        )

    detail = JSONField(
        verbose_name="Détail",
        blank=True,
        null=True,
        )

    STATE_CHOICES = (
        ('running', "Tâche en cours de traitement"),
        ('succesful', "Tâche terminée avec succés"),
        ('failed', "Échec de la tâche"),
        ('unknown', "Tâche perdue"),
        )

    state = models.CharField(
        verbose_name="État",
        max_length=10,
        choices=STATE_CHOICES,
        default='running',
        )

    start = models.DateTimeField(
        verbose_name="Début",
        auto_now_add=True,
        )

    end = models.DateTimeField(
        verbose_name="Fin",
        blank=True,
        null=True,
        )
