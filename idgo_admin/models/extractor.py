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


from django.apps import apps
from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.contrib.postgres.fields import JSONField
from django.db.models.signals import pre_init
from django.dispatch import receiver
from django.utils import timezone
from idgo_admin.models.mail import send_extraction_failure_mail
from idgo_admin.models.mail import send_extraction_successfully_mail
import requests
import uuid


class ExtractorSupportedFormat(models.Model):

    class Meta(object):
        verbose_name = "Format pris en charge par le service d'extraction"
        verbose_name_plural = "Formats pris en charge par le service d'extraction"

    name = models.SlugField(
        verbose_name="Nom",
        editable=False,
        primary_key=True,
        )

    description = models.TextField(
        verbose_name="Description",
        unique=True,
        )

    details = JSONField(
        verbose_name="Détails",
        )

    TYPE_CHOICES = (
        ('raster', 'raster'),
        ('vector', 'vector'),
        )

    type = models.CharField(
        verbose_name="Type",
        max_length=6,
        null=True,
        blank=True,
        choices=TYPE_CHOICES,
        )

    def __str__(self):
        return self.description


class AsyncExtractorTask(models.Model):

    class Meta(object):
        verbose_name = "Tâche exécutée par l'extracteur de données"
        verbose_name_plural = "Tâches exécutées par l'extracteur de données"

    uuid = models.UUIDField(
        editable=False,
        primary_key=True,
        default=uuid.uuid4,
        )

    user = models.ForeignKey(
        to=User,
        )

    foreign_value = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        )

    foreign_field = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        )

    model = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        )

    success = models.NullBooleanField(
        )

    submission_datetime = models.DateTimeField(
        null=True,
        blank=True,
        )

    start_datetime = models.DateTimeField(
        null=True,
        blank=True,
        )

    stop_datetime = models.DateTimeField(
        null=True,
        blank=True,
        )

    query = JSONField(
        null=True,
        blank=True,
        )

    details = JSONField(
        null=True,
        blank=True,
        )

    def __str__(self):
        return self.target_object.__str__()

    @property
    def status(self):
        if self.success is True:
            return 'Succès'
        elif self.success is False:
            return 'Échec'
        elif self.success is None and not self.start_datetime:
            return 'En attente'
        elif self.success is None and self.start_datetime:
            return 'En cours'
        else:
            return 'Inconnu'

    @property
    def elapsed_time(self):
        if self.stop_datetime and self.success in (True, False):
            return self.stop_datetime - self.submission_datetime
        else:
            return timezone.now() - self.submission_datetime

    @property
    def target_object(self):
        Model = apps.get_model(app_label='idgo_admin', model_name=self.model)
        return Model.objects.get(**{self.foreign_field: self.foreign_value})


@receiver(pre_init, sender=AsyncExtractorTask)
def synchronize_extractor_task(sender, *args, **kwargs):
    pre_init.disconnect(synchronize_extractor_task, sender=sender)

    doc = sender.__dict__.get('__doc__')
    if doc.startswith(sender.__name__):
        keys = doc[len(sender.__name__) + 1:-1].split(', ')
        values = kwargs.get('args')

        if len(keys) == len(values):
            kvp = dict((k, values[i]) for i, k in enumerate(keys))

            try:
                instance = AsyncExtractorTask.objects.get(uuid=kvp['uuid'])
            except AsyncExtractorTask.DoesNotExist:
                pass
            else:
                if instance.success is None:
                    url = instance.details['possible_requests']['status']['url']
                    r = requests.get(url)

                    if r.status_code == 200:
                        details = instance.details
                        details.update(r.json())

                        instance.success = {
                            'SUCCESS': True,
                            'FAILURE': False,
                            }.get(details['status'], None)

                        instance.details = details
                        if instance.success is False:
                            instance.stop_datetime = timezone.now()
                        else:
                            instance.stop_datetime = details.get('end_datetime')

                        instance.start_datetime = \
                            details.get('start_datetime') or instance.stop_datetime

                        instance.save()

                        if instance.success is True:
                            send_extraction_successfully_mail(instance.user, instance)
                        elif instance.success is False:
                            send_extraction_failure_mail(instance.user, instance)

    pre_init.connect(synchronize_extractor_task, sender=sender)
