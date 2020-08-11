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
from django.contrib.gis.db import models
from django.contrib.gis.db.models import Union
from django.contrib.gis.geos import MultiPolygon
import json


class Jurisdiction(models.Model):

    class Meta(object):
        verbose_name = "Territoire de compétence"
        verbose_name_plural = "Territoires de compétence"

    objects = models.GeoManager()

    code = models.CharField(
        verbose_name="Code INSEE",
        max_length=10,
        primary_key=True,
        )

    name = models.CharField(
        verbose_name="Nom",
        max_length=100,
        )

    communes = models.ManyToManyField(
        to='Commune',
        through='JurisdictionCommune',
        related_name='jurisdiction_communes',
        verbose_name="Communes",
        )

    geom = models.MultiPolygonField(
        verbose_name="Géometrie",
        null=True,
        blank=True,
        srid=4171,
        )

    def __str__(self):
        return self.name

    @property
    def organisations(self):
        Organisation = apps.get_model(app_label='idgo_admin', model_name='Organisation')
        return Organisation.objects.filter(jurisdiction=self)

    def save(self, *args, **kwargs):
        old = kwargs.pop('old', None)
        super().save(*args, **kwargs)

        if old and old != self.code:
            instance_to_del = Jurisdiction.objects.get(code=old)
            JurisdictionCommune.objects.filter(jurisdiction=instance_to_del).delete()
            Organisation = apps.get_model(app_label='idgo_admin', model_name='Organisation')
            Organisation.objects.filter(jurisdiction=instance_to_del).update(jurisdiction=self)
            instance_to_del.delete()

    def set_geom(self):
        if self.communes.count() == 1:
            commune = self.communes.all()[0]
            if commune.geom.__class__.__name__ == 'MultiPolygon':
                self.geom = commune.geom
            elif commune.geom.__class__.__name__ == 'Polygon':
                # Bien que normalement, on ne devrait pas avoir de type Polygon
                self.geom = MultiPolygon(commune.geom)
        elif self.communes.count() > 1:
            geom__union = self.communes.aggregate(Union('geom'))['geom__union']
            if geom__union:
                try:
                    self.geom = geom__union
                except TypeError:
                    self.geom = MultiPolygon(geom__union)
        super().save(update_fields=('geom',))

    def get_bounds(self):
        extent = self.communes.envelope().aggregate(models.Extent('geom')).get('geom__extent')
        if extent:
            return ((extent[1], extent[0]), (extent[3], extent[2]))

    def get_communes_as_feature_collection_geojson(self):
        features = []
        for instance in JurisdictionCommune.objects.filter(jurisdiction=self):
            geojson = {
                'type': 'Feature',
                'geometry': json.loads(instance.commune.geom.geojson),
                'properties': {
                    'code': instance.commune.code,
                    'name': instance.commune.name,
                    }
                }
            features.append(geojson)

        feature_collection = {
            'type': 'FeatureCollection',
            'features': features,
            }

        return json.dumps(feature_collection)


class Commune(models.Model):

    class Meta(object):
        verbose_name = "Commune"
        verbose_name_plural = "Communes"
        ordering = ('code',)

    objects = models.GeoManager()

    code = models.CharField(
        verbose_name="Code INSEE",
        max_length=5,
        primary_key=True,
        )

    name = models.CharField(
        verbose_name="Nom",
        max_length=100,
        )

    geom = models.MultiPolygonField(
        verbose_name="Géometrie",
        null=True,
        blank=True,
        srid=4171,
        )

    def __str__(self):
        return '{} ({})'.format(self.name, self.code)


class JurisdictionCommune(models.Model):

    class Meta(object):
        verbose_name = "Territoire de compétence / Commune"
        verbose_name_plural = "Territoires de compétence / Communes"

    jurisdiction = models.ForeignKey(
        to='Jurisdiction',
        to_field='code',
        verbose_name="Territoire de compétence",
        on_delete=models.CASCADE,
        )

    commune = models.ForeignKey(
        to='Commune',
        to_field='code',
        verbose_name="Commune",
        on_delete=models.CASCADE,
        )

    created_on = models.DateField(
        verbose_name="Créé le",
        auto_now_add=True,
        )

    created_by = models.ForeignKey(
        to='Profile',
        related_name='creates_jurisdiction',
        verbose_name="Créé par",
        null=True,
        on_delete=models.SET_NULL,
        )

    def __str__(self):
        return '{}: {}'.format(self.jurisdiction, self.commune)
