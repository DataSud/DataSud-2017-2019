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


from decimal import Decimal
from django.apps import apps
from django.conf import settings
from django.contrib.gis.db import models
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import IntegrityError
from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from functools import reduce
from idgo_admin.ckan_module import CkanHandler
from idgo_admin.ckan_module import CkanUserHandler
from idgo_admin.datagis import bounds_to_wkt
from idgo_admin.datagis import DataDecodingError
from idgo_admin.datagis import drop_table
from idgo_admin.datagis import gdalinfo
from idgo_admin.datagis import get_gdalogr_object
from idgo_admin.datagis import NotDataGISError
from idgo_admin.datagis import NotFoundSrsError
from idgo_admin.datagis import NotOGRError
from idgo_admin.datagis import NotSupportedSrsError
from idgo_admin.datagis import ogr2postgis
from idgo_admin.datagis import WrongDataError
from idgo_admin.exceptions import ExceedsMaximumLayerNumberFixedError
from idgo_admin.exceptions import SizeLimitExceededError
from idgo_admin import logger
from idgo_admin.managers import DefaultResourceManager
from idgo_admin.utils import download
from idgo_admin.utils import remove_file
from idgo_admin.utils import slugify
from idgo_admin.utils import three_suspension_points
import json
import os
from pathlib import Path
import re
import shutil
from urllib.parse import urljoin
import uuid


try:
    DOWNLOAD_SIZE_LIMIT = settings.DOWNLOAD_SIZE_LIMIT
except AttributeError:
    DOWNLOAD_SIZE_LIMIT = 104857600

if settings.STATIC_ROOT:
    locales_path = os.path.join(
        settings.STATIC_ROOT, 'mdedit/config/locales/fr/locales.json')
else:
    locales_path = os.path.join(
        settings.BASE_DIR,
        'idgo_admin/static/mdedit/config/locales/fr/locales.json')

try:
    with open(locales_path, 'r', encoding='utf-8') as f:
        MDEDIT_LOCALES = json.loads(f.read())
        AUTHORIZED_PROTOCOL = (
            (protocol['id'], protocol['value']) for protocol
            in MDEDIT_LOCALES['codelists']['MD_LinkageProtocolCode'])
except Exception:
    AUTHORIZED_PROTOCOL = None

CKAN_STORAGE_PATH = settings.CKAN_STORAGE_PATH
OWS_URL_PATTERN = settings.OWS_URL_PATTERN
CKAN_URL = settings.CKAN_URL


def get_all_users_for_organisations(list_id):
    Profile = apps.get_model(app_label='idgo_admin', model_name='Profile')
    return [
        profile.user.username
        for profile in Profile.objects.filter(
            organisation__in=list_id, organisation__is_active=True)]


# =======================
# Modèle RESOURCE FORMATS
# =======================


class ResourceFormats(models.Model):

    class Meta(object):
        verbose_name = "Format de ressource"
        verbose_name_plural = "Formats de ressource"

    slug = models.SlugField(
        verbose_name="Slug",
        max_length=100,
        unique=True,
        db_index=True,
        )

    description = models.TextField(
        verbose_name="Description",
        )

    extension = models.CharField(
        verbose_name="Extension du fichier",
        max_length=10,
        )

    mimetype = ArrayField(
        models.TextField(),
        verbose_name="Type MIME",
        blank=True,
        null=True,
        )

    PROTOCOL_CHOICES = AUTHORIZED_PROTOCOL

    protocol = models.CharField(
        verbose_name="Protocole",
        max_length=100,
        blank=True,
        null=True,
        choices=PROTOCOL_CHOICES,
        )

    ckan_format = models.CharField(
        verbose_name="Format CKAN",
        max_length=10,
        )

    CKAN_CHOICES = (
        (None, 'N/A'),
        ('text_view', 'text_view'),
        ('geo_view', 'geo_view'),
        ('recline_view', 'recline_view'),
        ('pdf_view', 'pdf_view'),
        )

    ckan_view = models.CharField(
        verbose_name="Vue CKAN",
        max_length=100,
        blank=True,
        null=True,
        choices=CKAN_CHOICES,
        )

    is_gis_format = models.BooleanField(
        verbose_name="Format de fichier SIG",
        blank=False,
        null=False,
        default=False,
        )

    def __str__(self):
        return self.description


# ===============
# Modèle RESOURCE
# ===============


def _ftp_file_upload_to(instance, filename):
    return filename


def _up_file_upload_to(instance, filename):
    return slugify(filename, exclude_dot=False)


class Resource(models.Model):
    """Modèle de classe d'une ressource de données."""

    class Meta(object):
        verbose_name = 'Ressource'
        verbose_name_plural = 'Ressources'

    # Managers
    # ========

    objects = models.Manager()
    default = DefaultResourceManager()

    # Champs atributaires
    # ===================

    ckan_id = models.UUIDField(
        verbose_name='Ckan UUID',
        default=uuid.uuid4,
        editable=False,
        unique=True,
        )

    title = models.TextField(
        verbose_name='Title',
        )

    description = models.TextField(
        verbose_name='Description',
        blank=True,
        null=True,
        )

    ftp_file = models.FileField(
        verbose_name='Fichier déposé sur FTP',
        blank=True,
        null=True,
        upload_to=_ftp_file_upload_to,
        )

    referenced_url = models.URLField(
        verbose_name='Référencer une URL',
        max_length=2000,
        blank=True,
        null=True,
        )

    dl_url = models.URLField(
        verbose_name='Télécharger depuis une URL',
        max_length=2000,
        blank=True,
        null=True,
        )

    up_file = models.FileField(
        verbose_name='Téléverser un ou plusieurs fichiers',
        blank=True,
        null=True,
        upload_to=_up_file_upload_to,
        )

    LANG_CHOICES = (
        ('french', 'Français'),
        ('english', 'Anglais'),
        ('italian', 'Italien'),
        ('german', 'Allemand'),
        ('other', 'Autre'))

    lang = models.CharField(
        verbose_name='Langue',
        choices=LANG_CHOICES,
        default='french',
        max_length=10,
        )

    format_type = models.ForeignKey(
        to='ResourceFormats',
        verbose_name='Format',
        blank=False,
        null=True,
        )

    LEVEL_CHOICES = (
        ('public', 'Tous les utilisateurs'),
        ('registered', 'Utilisateurs authentifiés'),
        ('only_allowed_users', 'Utilisateurs authentifiés avec droits spécifiques'),
        ('same_organization', 'Utilisateurs de cette organisation uniquement'),
        ('any_organization', 'Organisations spécifiées'),
        )

    restricted_level = models.CharField(
        verbose_name="Restriction d'accès",
        choices=LEVEL_CHOICES,
        default='public',
        max_length=20,
        blank=True,
        null=True,
        )

    profiles_allowed = models.ManyToManyField(
        to='Profile',
        verbose_name='Utilisateurs autorisés',
        blank=True,
        )

    organisations_allowed = models.ManyToManyField(
        to='Organisation',
        verbose_name='Organisations autorisées',
        blank=True,
        )

    dataset = models.ForeignKey(
        to='Dataset',
        verbose_name='Jeu de données',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        )

    bbox = models.PolygonField(
        verbose_name='Rectangle englobant',
        blank=True,
        null=True,
        srid=4171,
        )

    geo_restriction = models.BooleanField(
        verbose_name='Restriction géographique',
        default=False,
        )

    extractable = models.BooleanField(
        verbose_name='Extractible',
        default=True,
        )

    ogc_services = models.BooleanField(
        verbose_name='Services OGC',
        default=True,
        )

    created_on = models.DateTimeField(
        verbose_name='Date de création de la resource',
        blank=True,
        null=True,
        default=timezone.now,
        )

    last_update = models.DateTimeField(
        verbose_name='Date de dernière modification de la resource',
        blank=True,
        null=True,
        )

    TYPE_CHOICES = (
        ('raw', 'Données brutes'),
        ('annexe', 'Documentation associée'),
        ('service', 'Service'),
        )

    data_type = models.CharField(
        verbose_name='Type de la ressource',
        choices=TYPE_CHOICES,
        max_length=10,
        default='raw',
        )

    synchronisation = models.BooleanField(
        verbose_name='Synchronisation de données distante',
        default=False,
        )

    EXTRA_FREQUENCY_CHOICES = (
        ('5mn', 'Toutes les 5 minutes'),
        ('15mn', 'Toutes les 15 minutes'),
        ('20mn', 'Toutes les 20 minutes'),
        ('30mn', 'Toutes les 30 minutes'),
        )

    FREQUENCY_CHOICES = (
        ('1hour', 'Toutes les heures'),
        ('3hours', 'Toutes les trois heures'),
        ('6hours', 'Toutes les six heures'),
        ('daily', 'Quotidienne (tous les jours à minuit)'),
        ('weekly', 'Hebdomadaire (tous les lundi)'),
        ('bimonthly', 'Bimensuelle (1er et 15 de chaque mois)'),
        ('monthly', 'Mensuelle (1er de chaque mois)'),
        ('quarterly', 'Trimestrielle (1er des mois de janvier, avril, juillet, octobre)'),
        ('biannual', 'Semestrielle (1er janvier et 1er juillet)'),
        ('annual', 'Annuelle (1er janvier)'),
        ('never', 'Jamais'),
        )

    sync_frequency = models.CharField(
        verbose_name='Fréquence de synchronisation',
        max_length=20,
        blank=True,
        null=True,
        choices=FREQUENCY_CHOICES + EXTRA_FREQUENCY_CHOICES,
        default='never',
        )

    crs = models.ForeignKey(
        to='SupportedCrs',
        verbose_name='CRS',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        )

    def __str__(self):
        return self.title

    # Propriétés
    # ==========

    _encoding = 'utf-8'

    @property
    def encoding(self):
        return self._encoding

    @encoding.setter
    def encoding(self, value):
        if value:
            self._encoding = value

    @property
    def filename(self):
        if self.ftp_file:
            return self.ftp_file.name
        if self.up_file:
            return self.up_file.name
        return '{}.{}'.format(slugify(self.title), self.format.lower())

    @property
    def ckan_url(self):
        return urljoin(settings.CKAN_URL, 'dataset/{}/resource/{}/'.format(
            self.dataset.slug, self.ckan_id))

    @property
    def api_location(self):
        kwargs = {'dataset_name': self.dataset.slug, 'resource_id': self.ckan_id}
        return reverse('api:resource_show', kwargs=kwargs)

    @property
    def title_overflow(self):
        return three_suspension_points(self.title)

    @property
    def anonymous_access(self):
        return self.restricted_level == 'public'

    @property
    def is_datagis(self):
        return self.get_layers() and True or False

    # Méthodes héritées
    # =================

    def save(self, *args, current_user=None, synchronize=False,
             file_extras=None, skip_download=False, **kwargs):

        if 'update_fields' in kwargs:
            return super().save(*args, **kwargs)

        # Version précédante de la ressource (avant modification)
        previous, created = self.pk \
            and (Resource.objects.get(pk=self.pk), False) or (None, True)

        if previous:
            # crs est immuable sauf si le jeu de données change (Cf. plus bas)
            self.crs = previous.crs

        # Quelques valeur par défaut à la création de l'instance
        if created or not (
                # Ou si l'éditeur n'est pas partenaire du CRIGE
                current_user and current_user.profile.crige_membership):

            # Mais seulement s'il s'agit de données SIG, sauf
            # qu'on ne le sait pas encore...
            self.geo_restriction = False
            self.ogc_services = True
            self.extractable = True

        # La restriction au territoire de compétence désactive toujours les services OGC
        if self.geo_restriction:
            self.ogc_services = False

        self.last_update = timezone.now()

        if created:
            super().save(*args, **kwargs)
            kwargs['force_insert'] = False

        # Quelques contrôles sur les fichiers de données téléversée ou à télécharger
        filename = False
        content_type = None
        file_must_be_deleted = False  # permet d'indiquer si les fichiers doivent être supprimés à la fin de la chaine de traitement
        publish_raw_resource = True  # permet d'indiquer si les ressources brutes sont publiées dans CKAN

        if self.ftp_file and not skip_download:
            filename = self.ftp_file.file.name
            # Si la taille de fichier dépasse la limite autorisée,
            # on traite les données en fonction du type détecté
            if self.ftp_file.size > DOWNLOAD_SIZE_LIMIT:
                extension = self.format_type.extension.lower()
                if self.format_type.is_gis_format:
                    try:
                        gdalogr_obj = get_gdalogr_object(filename, extension)
                    except NotDataGISError:
                        # On essaye de traiter le jeux de données normalement, même si ça peut être long.
                        pass
                    else:
                        if gdalogr_obj.__class__.__name__ == 'GdalOpener':
                            s0 = str(self.ckan_id)
                            s1, s2, s3 = s0[:3], s0[3:6], s0[6:]
                            dir = os.path.join(CKAN_STORAGE_PATH, s1, s2)
                            os.makedirs(dir, mode=0o777, exist_ok=True)
                            shutil.copyfile(filename, os.path.join(dir, s3))

                            src = os.path.join(dir, s3)
                            dst = os.path.join(dir, filename.split('/')[-1])
                            try:
                                os.symlink(src, dst)
                            except FileNotFoundError as e:
                                logger.error(e)
                            else:
                                logger.debug('Created a symbolic link {dst} pointing to {src}.'.format(dst=dst, src=src))

                        # if gdalogr_obj.__class__.__name__ == 'OgrOpener':
                        # On ne publie que le service OGC dans CKAN
                        publish_raw_resource = False

        elif (self.up_file and file_extras):
            # GDAL/OGR ne semble pas prendre de fichier en mémoire..
            # ..à vérifier mais si c'est possible comment indiquer le vsi en préfixe du filename ?
            filename = self.up_file.path
            self.save(update_fields=('up_file',))
            file_must_be_deleted = True

        elif self.dl_url and not skip_download:
            try:
                directory, filename, content_type = download(
                    self.dl_url, settings.MEDIA_ROOT, max_size=DOWNLOAD_SIZE_LIMIT)
            except SizeLimitExceededError as e:
                l = len(str(e.max_size))
                if l > 6:
                    m = '{0} mo'.format(Decimal(int(e.max_size) / 1024 / 1024))
                elif l > 3:
                    m = '{0} ko'.format(Decimal(int(e.max_size) / 1024))
                else:
                    m = '{0} octets'.format(int(e.max_size))
                raise ValidationError((
                    'La taille du fichier dépasse '
                    'la limite autorisée : {0}.').format(m), code='dl_url')
            except Exception as e:
                if e.__class__.__name__ == 'HTTPError':
                    if e.response.status_code == 404:
                        msg = ('La ressource distante ne semble pas exister. '
                               "Assurez-vous que l'URL soit correcte.")
                    if e.response.status_code == 403:
                        msg = ("Vous n'avez pas l'autorisation pour "
                               'accéder à la ressource.')
                    if e.response.status_code == 401:
                        msg = ('Une authentification est nécessaire '
                               'pour accéder à la ressource.')
                else:
                    msg = 'Le téléchargement du fichier a échoué.'
                raise ValidationError(msg, code='dl_url')
            file_must_be_deleted = True

        # Synchronisation avec CKAN
        # =========================

        # La synchronisation doit s'effectuer avant la publication des
        # éventuelles couches de données SIG car dans le cas des données
        # de type « raster », nous utilisons le filestore de CKAN.
        if synchronize and publish_raw_resource:
            self.synchronize(
                content_type=content_type, file_extras=file_extras,
                filename=filename, with_user=current_user)
        elif synchronize and not publish_raw_resource:
            url = reduce(urljoin, [
                settings.CKAN_URL,
                'dataset/', str(self.dataset.ckan_id) + '/',
                'resource/', str(self.ckan_id) + '/',
                'download/', Path(self.ftp_file.name).name])
            self.synchronize(url=url, with_user=current_user)

        # Détection des données SIG
        # =========================
        if filename:
            # On vérifie s'il s'agit de données SIG, uniquement pour
            # les extensions de fichier autorisées..
            extension = self.format_type.extension.lower()
            if self.format_type.is_gis_format:
                # Si c'est le cas, on monte les données dans la base PostGIS dédiée
                # et on déclare la couche au service OGC:WxS de l'organisation.

                # Mais d'abord, on vérifie si la ressource contient
                # déjà des « Layers », auquel cas il faudra vérifier si
                # la table de données a changée.
                existing_layers = {}
                if not created:
                    existing_layers = dict((
                        re.sub('^(\w+)_[a-z0-9]{7}$', '\g<1>', layer.name),
                        layer.name) for layer in self.get_layers())

                try:

                    # C'est carrément moche mais c'est pour aller vite.
                    # Il faudrait factoriser tout ce bazar et créer
                    # un décorateur pour gérer le rool-back sur CKAN.

                    try:
                        gdalogr_obj = get_gdalogr_object(filename, extension)
                    except NotDataGISError:
                        tables = []
                        pass
                    else:

                        try:
                            self.format_type = ResourceFormats.objects.get(
                                extension=extension, ckan_format=gdalogr_obj.format)
                        # except ResourceFormats.MultipleObjectsReturned:
                        #     pass
                        except Exception:
                            pass

                        # ==========================
                        # Jeu de données vectorielle
                        # ==========================

                        if gdalogr_obj.__class__.__name__ == 'OgrOpener':

                            # On convertit les données vers PostGIS

                            try:
                                tables = ogr2postgis(
                                    gdalogr_obj, update=existing_layers,
                                    epsg=self.crs and self.crs.auth_code or None,
                                    encoding=self.encoding)

                            except NotOGRError as e:
                                logger.warning(e)
                                file_must_be_deleted and remove_file(filename)
                                msg = (
                                    "Le fichier reçu n'est pas reconnu "
                                    'comme étant un jeu de données SIG correct.')
                                raise ValidationError(msg, code='__all__')

                            except DataDecodingError as e:
                                logger.warning(e)
                                file_must_be_deleted and remove_file(filename)
                                msg = (
                                    'Impossible de décoder correctement les '
                                    "données. Merci d'indiquer l'encodage "
                                    'ci-dessous.')
                                raise ValidationError(msg, code='encoding')

                            except WrongDataError as e:
                                logger.warning(e)
                                file_must_be_deleted and remove_file(filename)
                                msg = (
                                    'Votre ressource contient des données SIG que '
                                    'nous ne parvenons pas à lire correctement. '
                                    'Un ou plusieurs objets sont erronés.')
                                raise ValidationError(msg)

                            except NotFoundSrsError as e:
                                logger.warning(e)
                                file_must_be_deleted and remove_file(filename)
                                msg = (
                                    'Votre ressource semble contenir des données SIG '
                                    'mais nous ne parvenons pas à détecter le système '
                                    'de coordonnées. Merci de sélectionner le code du '
                                    'CRS dans la liste ci-dessous.')
                                raise ValidationError(msg, code='crs')

                            except NotSupportedSrsError as e:
                                logger.warning(e)
                                file_must_be_deleted and remove_file(filename)
                                msg = (
                                    'Votre ressource semble contenir des données SIG '
                                    'mais le système de coordonnées de celles-ci '
                                    "n'est pas supporté par l'application.")
                                raise ValidationError(msg, code='__all__')

                            except ExceedsMaximumLayerNumberFixedError as e:
                                logger.warning(e)
                                file_must_be_deleted and remove_file(filename)
                                raise ValidationError(e.__str__(), code='__all__')

                            else:
                                # Ensuite, pour tous les jeux de données SIG trouvés,
                                # on crée le service ows à travers la création de `Layer`
                                try:
                                    Layer = apps.get_model(app_label='idgo_admin', model_name='Layer')
                                    for table in tables:
                                        try:
                                            Layer.objects.get(
                                                name=table['id'], resource=self)
                                        except Layer.DoesNotExist:
                                            save_opts = {'synchronize': synchronize}
                                            Layer.vector.create(
                                                bbox=table['bbox'],
                                                name=table['id'],
                                                resource=self,
                                                save_opts=save_opts)
                                except Exception as e:
                                    logger.error(e)
                                    file_must_be_deleted and remove_file(filename)
                                    for table in tables:
                                        drop_table(table['id'])
                                    raise e

                        # ==========================
                        # Jeu de données matricielle
                        # ==========================

                        if gdalogr_obj.__class__.__name__ == 'GdalOpener':

                            coverage = gdalogr_obj.get_coverage()

                            try:
                                tables = [gdalinfo(
                                    coverage, update=existing_layers,
                                    epsg=self.crs and self.crs.auth_code or None)]

                            except NotFoundSrsError as e:
                                logger.warning(e)
                                file_must_be_deleted and remove_file(filename)
                                msg = (
                                    'Votre ressource semble contenir des données SIG '
                                    'mais nous ne parvenons pas à détecter le système '
                                    'de coordonnées. Merci de sélectionner le code du '
                                    'CRS dans la liste ci-dessous.')
                                raise ValidationError(msg, code='crs')

                            except NotSupportedSrsError as e:
                                logger.warning(e)
                                file_must_be_deleted and remove_file(filename)
                                msg = (
                                    'Votre ressource semble contenir des données SIG '
                                    'mais le système de coordonnées de celles-ci '
                                    "n'est pas supporté par l'application.")
                                raise ValidationError(msg, code='__all__')

                            # Super Crado Code
                            s0 = str(self.ckan_id)
                            s1, s2, s3 = s0[:3], s0[3:6], s0[6:]
                            dir = os.path.join(CKAN_STORAGE_PATH, s1, s2)
                            src = os.path.join(dir, s3)
                            dst = os.path.join(dir, filename.split('/')[-1])
                            try:
                                os.symlink(src, dst)
                            except FileExistsError as e:
                                logger.warning(e)
                            except FileNotFoundError as e:
                                logger.error(e)
                            else:
                                logger.debug('Created a symbolic link {dst} pointing to {src}.'.format(dst=dst, src=src))

                            try:
                                Layer = apps.get_model(app_label='idgo_admin', model_name='Layer')
                                for table in tables:
                                    try:
                                        Layer.objects.get(
                                            name=table['id'], resource=self)
                                    except Layer.DoesNotExist:
                                        Layer.raster.create(
                                            bbox=table['bbox'],
                                            name=table['id'],
                                            resource=self)
                            except Exception as e:
                                logger.error(e)
                                file_must_be_deleted and remove_file(filename)
                                raise e

                except Exception as e:
                    if created:
                        if current_user:
                            username = current_user.username
                            apikey = CkanHandler.get_user(username)['apikey']
                            with CkanUserHandler(apikey) as ckan:
                                ckan.delete_resource(str(self.ckan_id))
                        else:
                            CkanHandler.delete_resource(str(self.ckan_id))
                        for layer in self.get_layers():
                            layer.delete(current_user=current_user)
                    # Puis on « raise » l'erreur
                    raise e

                # On met à jour les champs de la ressource
                SupportedCrs = apps.get_model(app_label='idgo_admin', model_name='SupportedCrs')
                crs = [
                    SupportedCrs.objects.get(
                        auth_name='EPSG', auth_code=table['epsg'])
                    for table in tables]
                # On prend la première valeur (c'est moche)
                self.crs = crs and crs[0] or None

                # Si les données changent..
                if existing_layers and \
                        set(previous.get_layers()) != set(self.get_layers()):
                    # on supprime les anciens `layers`..
                    for layer in previous.get_layers():
                        layer.delete()
        ####
        if self.get_layers():
            extent = self.get_layers().aggregate(models.Extent('bbox')).get('bbox__extent')
            if extent:
                xmin, ymin = extent[0], extent[1]
                xmax, ymax = extent[2], extent[3]
                setattr(self, 'bbox', bounds_to_wkt(xmin, ymin, xmax, ymax))
        else:
            # Si la ressource n'est pas de type SIG, on passe les trois arguments
            # qui concernent exclusivement ces dernières à « False ».
            self.geo_restriction = False
            self.ogc_services = False
            self.extractable = False

        super().save(*args, **kwargs)

        # Puis dans tous les cas..
        # on met à jour le statut des couches du service cartographique..
        if not created:
            self.update_enable_layers_status()

        # on supprime les données téléversées ou téléchargées..
        if file_must_be_deleted:
            remove_file(filename)

        # [Crado] on met à jour la ressource CKAN
        if synchronize:
            CkanHandler.update_resource(
                str(self.ckan_id), extracting_service=str(self.extractable))

        for layer in self.get_layers():
            layer.save(synchronize=synchronize)

        self.dataset.date_modification = timezone.now().date()
        self.dataset.save(current_user=None,
                          synchronize=True,
                          update_fields=['date_modification'])

    def delete(self, *args, current_user=None, **kwargs):
        with_user = current_user

        for layer in self.get_layers():
            layer.delete(current_user=current_user)

        # On supprime la ressource CKAN
        ckan_id = str(self.ckan_id)
        if with_user:
            username = with_user.username

            apikey = CkanHandler.get_user(username)['apikey']
            with CkanUserHandler(apikey=apikey) as ckan_user:
                ckan_user.delete_resource(ckan_id)
        else:
            CkanHandler.delete_resource(ckan_id)

        # On supprime l'instance
        super().delete(*args, **kwargs)

        self.dataset.date_modification = timezone.now().date()
        self.dataset.save(current_user=current_user,
                          synchronize=True,
                          update_fields=['date_modification'])

    # Autres méthodes
    # ===============

    def synchronize(self, url=None, filename=None, content_type=None,
                    file_extras=None, with_user=None):
        """Synchronizer le jeu de données avec l'instance de CKAN."""
        # Identifiant de la resource CKAN :
        id = str(self.ckan_id)

        # Définition des propriétés du « package » :
        data = {
            'crs': self.crs and self.crs.description or '',
            'name': self.title,
            'description': self.description,
            'data_type': self.data_type,
            'extracting_service': 'False',  # I <3 CKAN
            'format': self.format_type and self.format_type.ckan_format,
            'view_type': self.format_type and self.format_type.ckan_view,
            'id': id,
            'lang': self.lang,
            'restricted_by_jurisdiction': str(self.geo_restriction),
            'url': url and url or '',
            'api': '{}'}

        # TODO: Factoriser

        # (0) Aucune restriction
        if self.restricted_level == 'public':
            restricted = json.dumps({'level': 'public'})
        # (1) Uniquement pour un utilisateur connecté
        elif self.restricted_level == 'registered':
            restricted = json.dumps({'level': 'registered'})
        # (2) Seulement les utilisateurs indiquées
        elif self.restricted_level == 'only_allowed_users':
            restricted = json.dumps({
                'allowed_users': ','.join(
                    self.profiles_allowed.exists() and [
                        p.user.username for p
                        in self.profiles_allowed.all()] or []),
                'level': 'only_allowed_users'})
        # (3) Les utilisateurs de cette organisation
        elif self.restricted_level == 'same_organization':
            restricted = json.dumps({
                'allowed_users': ','.join(
                    get_all_users_for_organisations(
                        self.organisations_allowed.all())),
                'level': 'only_allowed_users'})
        # (3) Les utilisateurs des organisations indiquées
        elif self.restricted_level == 'any_organization':
            restricted = json.dumps({
                'allowed_users': ','.join(
                    get_all_users_for_organisations(
                        self.organisations_allowed.all())),
                'level': 'only_allowed_users'})

        data['restricted'] = restricted

        if self.referenced_url:
            data['url'] = self.referenced_url

        if self.dl_url and filename:
            downloaded_file = File(open(filename, 'rb'))
            data['upload'] = downloaded_file
            data['size'] = downloaded_file.size
            data['mimetype'] = content_type

        if self.up_file and file_extras:
            data['upload'] = self.up_file.file
            data['size'] = file_extras.get('size')
            data['mimetype'] = file_extras.get('mimetype')

        if self.ftp_file:
            if not url:
                data['upload'] = self.ftp_file.file
            data['size'] = self.ftp_file.size
            if self.format_type and len(self.format_type.mimetype):
                data['mimetype'] = self.format_type.mimetype[0]
            else:
                data['mimetype'] = 'text/plain'
            # Passe dans un validateur pour forcer en base : url_type='upload'
            data['force_url_type'] = 'upload'

        if self.data_type == 'raw':
            if self.ftp_file or self.dl_url or self.up_file:
                data['resource_type'] = 'file.upload'
            elif self.referenced_url:
                data['resource_type'] = 'file'
        if self.data_type == 'annexe':
            data['resource_type'] = 'documentation'
        if self.data_type == 'service':
            data['resource_type'] = 'api'

        ckan_package = CkanHandler.get_package(str(self.dataset.ckan_id))

        if with_user:
            username = with_user.username

            apikey = CkanHandler.get_user(username)['apikey']
            with CkanUserHandler(apikey=apikey) as ckan:
                ckan.publish_resource(ckan_package, **data)
        else:
            return CkanHandler.publish_resource(ckan_package, **data)

    def get_layers(self, **kwargs):
        Layer = apps.get_model(app_label='idgo_admin', model_name='Layer')
        return Layer.objects.filter(resource=self, **kwargs)

    def update_enable_layers_status(self):
        for layer in self.get_layers():
            layer.handle_enable_ows_status()

    def is_profile_authorized(self, user):
        Profile = apps.get_model(app_label='idgo_admin', model_name='Profile')
        if not user.pk:
            raise IntegrityError('User does not exists')
        if self.restricted_level == 'only_allowed_users' and self.profiles_allowed.exists():
            return user in [
                p.user for p in self.profiles_allowed.all()]
        elif self.restricted_level in ('same_organization', 'any_organization') and self.organisations_allowed.exists():
            return user in [p.user for p in Profile.objects.filter(
                organisation__in=self.organisations_allowed.all(),
                organisation__is_active=True)]
        return True


# Signaux
# =======


@receiver(post_save, sender=Resource)
def logging_after_save(sender, instance, **kwargs):
    action = kwargs.get('created', False) and 'created' or 'updated'
    logger.info('Resource "{pk}" has been {action}'.format(pk=instance.pk, action=action))


@receiver(post_delete, sender=Resource)
def logging_after_delete(sender, instance, **kwargs):
    logger.info('Resource "{pk}" has been deleted'.format(pk=instance.pk))
