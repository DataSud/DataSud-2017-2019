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
from django.conf import settings
from django.contrib.gis.db import models
from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from django.dispatch import receiver
from idgo_admin.ckan_module import CkanHandler
from idgo_admin.ckan_module import CkanUserHandler
from idgo_admin.datagis import drop_table
from idgo_admin import logger
from idgo_admin.managers import RasterLayerManager
from idgo_admin.managers import VectorLayerManager
from idgo_admin.mra_client import MraBaseError
from idgo_admin.mra_client import MRAHandler
import itertools
import json
import os
import re


MRA = settings.MRA
OWS_URL_PATTERN = settings.OWS_URL_PATTERN
CKAN_STORAGE_PATH = settings.CKAN_STORAGE_PATH
MAPSERV_STORAGE_PATH = settings.MAPSERV_STORAGE_PATH


def get_all_users_for_organisations(list_id):
    Profile = apps.get_model(app_label='idgo_admin', model_name='Profile')
    return [
        profile.user.username
        for profile in Profile.objects.filter(
            organisation__in=list_id, organisation__is_active=True)]


class Layer(models.Model):

    class Meta(object):
        verbose_name = "Couche de données"
        verbose_name_plural = "Couches de données"

    # Managers
    # ========

    objects = models.Manager()
    vector = VectorLayerManager()
    raster = RasterLayerManager()

    # Champs atributaires
    # ===================

    name = models.SlugField(
        verbose_name="Nom de la couche",
        max_length=100,
        editable=False,
        primary_key=True,
        )

    resource = models.ForeignKey(
        to='Resource',
        verbose_name="Ressource",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
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

    bbox = models.PolygonField(
        verbose_name="Rectangle englobant",
        null=True,
        blank=True,
        srid=4171,
        )

    def __str__(self):
        return self.resource.__str__()

    # Propriétés
    # ==========

    @property
    def layername(self):
        return self.mra_info['name']

    @property
    def geometry_type(self):
        return {
            'POLYGON': 'Polygone',
            'POINT': 'Point',
            'LINESTRING': 'Ligne',
            'RASTER': 'Raster',
            }.get(self.mra_info['type'], None)

    @property
    def is_enabled(self):
        return self.mra_info['enabled']

    @property
    def title(self):
        return self.mra_info['title']

    @property
    def abstract(self):
        return self.mra_info['abstract']

    @property
    def styles(self):
        return self.mra_info['styles']['styles']

    @property
    def default_style(self):
        return self.mra_info['styles']['styles'][0]

    @property
    def id(self):
        return self.name

    @property
    def filename(self):
        if self.type == 'vector':
            # Peut-être quelque chose à retourner ici ?
            return None
        if self.type == 'raster':
            x = str(self.resource.ckan_id)
            _filename = os.path.join(
                CKAN_STORAGE_PATH, x[:3], x[3:6],
                self.resource.filename.split('/')[-1])
            if os.path.isfile(_filename):
                filename = os.path.join(
                    MAPSERV_STORAGE_PATH, x[:3], x[3:6],
                    self.resource.filename.split('/')[-1])
            else:
                filename = os.path.join(
                    MAPSERV_STORAGE_PATH, x[:3], x[3:6], x[6:])
            return filename

    # Méthodes héritées
    # =================

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        organisation = self.resource.dataset.organisation
        ws_name = organisation.slug

        self.mra_info = {
            'name': None,
            'title': None,
            'type': None,
            'enabled': None,
            'abstract': None,
            'bbox': None,
            'attributes': None,
            'styles': {'default': None, 'styles': None}}

        try:
            l = MRAHandler.get_layer(self.name)
        except MraBaseError as e:
            logger.error(e)
            return

        # Récupération des informations de couche vecteur
        # ===============================================

        if self.type == 'vector':
            try:
                ft = MRAHandler.get_featuretype(ws_name, 'public', self.name)
            except MraBaseError:
                return
            if not l or not ft:
                return

            ll = ft['featureType']['latLonBoundingBox']
            bbox = [[ll['miny'], ll['minx']], [ll['maxy'], ll['maxx']]]
            attributes = [item['name'] for item in ft['featureType']['attributes']]

            default_style_name = None
            styles = []
            if 'defaultStyle' in l:
                default_style_name = l['defaultStyle']['name']
                try:
                    sld = MRAHandler.get_style(l['defaultStyle']['name'])
                except MraBaseError as e:
                    logger.error(e)
                    styles = {}
                else:
                    styles = [{
                        'name': 'default',
                        'text': 'Style par défaut',
                        'url': l['defaultStyle']['href'].replace('json', 'sld'),
                        'sld': sld,
                        }]

            if l.get('styles'):
                for style in l.get('styles')['style']:
                    styles.append({
                        'name': style['name'],
                        'text': style['name'],
                        'url': style['href'].replace('json', 'sld'),
                        'sld': MRAHandler.get_style(style['name']),
                        })

        # Récupération des informations de couche raster
        # ==============================================

        elif self.type == 'raster':
            try:
                c = MRAHandler.get_coverage(ws_name, self.name, self.name)
            except MraBaseError:
                return
            if not l or not c:
                return

            ll = c['coverage']['latLonBoundingBox']
            bbox = [[ll['miny'], ll['minx']], [ll['maxy'], ll['maxx']]]
            attributes = []
            default_style_name = None
            styles = []

        # Puis..
        self.mra_info = {
            'name': l['name'],
            'title': l['title'],
            'type': l['type'],
            'enabled': l['enabled'],
            'abstract': l['abstract'],
            'bbox': bbox,
            'attributes': attributes,
            'styles': {
                'default': default_style_name,
                'styles': styles}}

    def save(self, *args, synchronize=False, **kwargs):
        # Synchronisation avec le service OGC en fonction du type de données
        if self.type == 'vector':
            self.save_vector_layer()
        elif self.type == 'raster':
            self.save_raster_layer()

        # Puis sauvegarde
        super().save(*args, **kwargs)
        self.handle_enable_ows_status()
        self.handle_layergroup()

        if synchronize:
            self.synchronize()

    def delete(self, *args, current_user=None, **kwargs):
        with_user = current_user

        # On supprime la ressource CKAN
        if with_user:
            username = with_user.username
            apikey = CkanHandler.get_user(username)['apikey']
            with CkanUserHandler(apikey=apikey) as ckan_user:
                ckan_user.delete_resource(self.name)
        else:
            CkanHandler.delete_resource(self.name)

        # On supprime les ressources MRA
        try:
            MRAHandler.del_layer(self.name)
            ws_name = self.resource.dataset.organisation.slug
            if self.type == 'vector':
                MRAHandler.del_featuretype(ws_name, 'public', self.name)
            if self.type == 'raster':
                MRAHandler.del_coverage(ws_name, self.name, self.name)
                # MRAHandler.del_coveragestore(ws_name, self.name)
        except Exception as e:
            logger.error(e)
            pass

        # On supprime la table de données PostGIS
        try:
            drop_table(self.name)
        except Exception as e:
            logger.error(e)
            pass

        # Puis on supprime l'instance
        super().delete(*args, **kwargs)

    # Autres méthodes
    # ===============

    def save_raster_layer(self, *args, **kwargs):
        """Synchronizer la couche de données matricielle avec le service OGC via MRA."""
        organisation = self.resource.dataset.organisation
        ws_name = organisation.slug
        cs_name = self.name

        if self.pk:
            try:
                Layer.objects.get(pk=self.pk)
            except Layer.DoesNotExist:
                pass
            else:
                # On vérifie si l'organisation du jeu de données a changée,
                # auquel cas il est nécessaire de supprimer les objets MRA
                # afin de les recréer dans le bon workspace (c-à-d Mapfile).
                previous_layer = MRAHandler.get_layer(self.name)
                regex = '/workspaces/(?P<ws_name>[a-z_\-]+)/coveragestores/'

                matched = re.search(regex, previous_layer['resource']['href'])
                if matched:
                    previous_ws_name = matched.group('ws_name')
                    if not ws_name == previous_ws_name:
                        MRAHandler.del_layer(self.name)
                        MRAHandler.del_coverage(
                            previous_ws_name, cs_name, self.name)

        MRAHandler.get_or_create_workspace(organisation)
        MRAHandler.get_or_create_coveragestore(ws_name, cs_name, filename=self.filename)
        MRAHandler.get_or_create_coverage(
            ws_name, cs_name, self.name, enabled=True,
            title=self.resource.title, abstract=self.resource.description)

    def save_vector_layer(self, *args, **kwargs):
        """Synchronizer la couche de données vectorielle avec le service OGC via MRA."""
        organisation = self.resource.dataset.organisation
        ws_name = organisation.slug
        ds_name = 'public'

        if self.pk:
            try:
                Layer.objects.get(pk=self.pk)
            except Layer.DoesNotExist:
                pass
            else:
                # On vérifie si l'organisation du jeu de données a changée,
                # auquel cas il est nécessaire de supprimer les objets MRA
                # afin de les recréer dans le bon workspace (c-à-d Mapfile).
                previous_layer = MRAHandler.get_layer(self.name)
                regex = '/workspaces/(?P<ws_name>[a-z_\-]+)/datastores/'

                matched = re.search(regex, previous_layer['resource']['href'])
                if matched:
                    previous_ws_name = matched.group('ws_name')
                    if not ws_name == previous_ws_name:
                        MRAHandler.del_layer(self.name)
                        MRAHandler.del_featuretype(
                            previous_ws_name, ds_name, self.name)

        MRAHandler.get_or_create_workspace(organisation)
        MRAHandler.get_or_create_datastore(ws_name, ds_name)
        MRAHandler.get_or_create_featuretype(
            ws_name, ds_name, self.name, enabled=True,
            title=self.resource.title, abstract=self.resource.description)

    def synchronize(self, with_user=None):
        """Synchronizer le jeu de données avec l'instance de CKAN."""
        # 'with_user' n'est pas utiliser dans ce contexte

        # Définition des propriétés de la « ressource »
        # =============================================

        id = self.name
        name = 'Aperçu cartographique'.format(name=self.resource.title)
        description = self.resource.description
        organisation = self.resource.dataset.organisation

        base_url = OWS_URL_PATTERN.format(organisation=organisation.slug).replace('?', '')

        getlegendgraphic = (
            '{base_url}?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetLegendGraphic'
            '&LAYER={layer}&FORMAT=image/png'
            ).format(base_url=base_url, layer=id)

        api = {
            'url': base_url,
            'typename': id,
            'getlegendgraphic': getlegendgraphic}

        try:
            DEFAULT_SRID = settings.DEFAULTS_VALUES['SRID']
        except Exception:
            DEFAULT_SRID = 4326
        else:
            SupportedCrs = apps.get_model(app_label='idgo_admin', model_name='SupportedCrs')
            try:
                SupportedCrs.objects.get(auth_name='EPSG', auth_code=DEFAULT_SRID)
            except SupportedCrs.DoesNotExist:
                DEFAULT_SRID = 4326

        if self.type == 'vector':
            outputformat = None
            if self.resource.format_type.extension.lower() in ('json', 'geojson'):
                outputformat = 'shapezip'  # Il faudrait être sûr que le format existe avec le même nom !
            elif self.resource.format_type.extension.lower() in ('zip', 'tar'):
                outputformat = 'geojson'   # Il faudrait être sûr que le format existe avec le même nom !
            if outputformat:
                api[outputformat] = (
                    '{base_url}?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature'
                    '&TYPENAME={typename}&OUTPUTFORMAT={outputformat}&CRSNAME=EPSG:{srid}'
                    ).format(
                        base_url=base_url, typename=id,
                        outputformat=outputformat, srid=str(DEFAULT_SRID))

        CkanHandler.update_resource(str(self.resource.ckan_id), api=json.dumps(api))
        CkanHandler.push_resource_view(
            title=name, description=description,
            resource_id=str(self.resource.ckan_id), view_type='geo_view')

    def handle_enable_ows_status(self):
        """Gérer le statut d'activation de la couche de données SIG."""
        ws_name = self.resource.dataset.organisation.slug
        if self.resource.ogc_services:
            MRAHandler.enable_layer(ws_name, self.name)
            # TODO: Comment on gère les ressources CKAN service ???
        else:
            MRAHandler.disable_layer(ws_name, self.name)
            # TODO: Comment on gère les ressources CKAN service ???

    def handle_layergroup(self):
        dataset = self.resource.dataset
        layers = list(itertools.chain.from_iterable([
            qs for qs in [
                resource.get_layers() for resource
                in dataset.get_resources()]]))
        # TODO remplacer par `layers = dataset.get_layers()`

        MRAHandler.create_or_update_layergroup(
            dataset.organisation.slug, {
                'name': dataset.slug,
                'title': dataset.title,
                'abstract': dataset.description,
                'layers': [layer.name for layer in layers]})


# Signaux
# =======


@receiver(post_save, sender=Layer)
def logging_after_save(sender, instance, **kwargs):
    action = kwargs.get('created', False) and 'created' or 'updated'
    logger.info('Layer "{pk}" has been {action}'.format(pk=instance.pk, action=action))


@receiver(post_delete, sender=Layer)
def logging_after_delete(sender, instance, **kwargs):
    logger.info('Layer "{pk}" has been deleted'.format(pk=instance.pk))
