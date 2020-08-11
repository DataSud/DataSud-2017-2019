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
from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils.text import slugify
from django.utils import timezone
from idgo_admin.ckan_module import CkanHandler
from idgo_admin.ckan_module import CkanUserHandler
from idgo_admin.datagis import bounds_to_wkt
from idgo_admin import logger
from idgo_admin.geonet_module import GeonetUserHandler as geonet
from idgo_admin.managers import DefaultDatasetManager
from idgo_admin.managers import HarvestedCkanDatasetManager
from idgo_admin.managers import HarvestedCswDatasetManager
from idgo_admin.managers import HarvestedDcatDatasetManager
from idgo_admin.utils import three_suspension_points
from taggit.admin import Tag
from taggit.managers import TaggableManager
from urllib.parse import urljoin
from uuid import UUID


CKAN_URL = settings.CKAN_URL
GEONETWORK_URL = settings.GEONETWORK_URL
OWS_URL_PATTERN = settings.OWS_URL_PATTERN
DEFAULT_CONTACT_EMAIL = settings.DEFAULT_CONTACT_EMAIL
DEFAULT_PLATFORM_NAME = settings.DEFAULT_PLATFORM_NAME


try:
    BOUNDS = settings.DEFAULTS_VALUES['BOUNDS']
except AttributeError:
    xmin, ymin = -180, -90
    xmax, ymax = 180, 90
else:
    xmin, ymin = BOUNDS[0][1], BOUNDS[0][0]
    xmax, ymax = BOUNDS[1][1], BOUNDS[1][0]
finally:
    DEFAULT_BBOX = bounds_to_wkt(xmin, ymin, xmax, ymax)


# ==============
# Modèle DATASET
# ==============


class Dataset(models.Model):
    """Modèle de classe d'un jeu de données."""

    class Meta(object):
        verbose_name = "Jeu de données"
        verbose_name_plural = "Jeux de données"

    # Managers
    # ========

    objects = models.Manager()
    default = DefaultDatasetManager()
    harvested_ckan = HarvestedCkanDatasetManager()
    harvested_csw = HarvestedCswDatasetManager()
    harvested_dcat = HarvestedDcatDatasetManager()

    # Champs atributaires
    # ===================

    editor = models.ForeignKey(
        User,
        verbose_name="Producteur (propriétaire)",
        )

    title = models.TextField(
        verbose_name="Titre",
        )

    slug = models.SlugField(
        verbose_name="Slug",
        error_messages={
            'invalid': (
                "Le label court ne peut contenir ni majuscule, "
                "ni caractères spéciaux à l'exception le tiret.")},
        max_length=100,
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        )

    ckan_id = models.UUIDField(
        verbose_name="Identifiant CKAN",
        null=True,
        blank=True,
        editable=False,
        unique=True,
        db_index=True,
        )

    description = models.TextField(
        verbose_name="Description",
        blank=True,
        null=True,
        )

    thumbnail = models.ImageField(
        verbose_name="Illustration",
        null=True,
        blank=True,
        upload_to='thumbnails/',
        )

    keywords = TaggableManager(
        verbose_name="Liste de mots-clés",
        blank=True,
        )

    categories = models.ManyToManyField(
        to='Category',
        verbose_name="Catégories",
        blank=True,
        )

    date_creation = models.DateField(
        verbose_name="Date de création",
        null=True,
        blank=True,
        )

    date_modification = models.DateField(
        verbose_name="Date de dernière modification",
        null=True,
        blank=True,
        )

    date_publication = models.DateField(
        verbose_name="Date de publication",
        null=True,
        blank=True,
        )

    FREQUENCY_CHOICES = (
        ('asneeded', "Lorsque nécessaire"),
        ('never', "Non planifiée"),
        ('intermittently', "Irrégulière"),
        ('continuously', "Continue"),
        ('realtime', "Temps réel"),
        ('daily', "Journalière"),
        ('weekly', "Hebdomadaire"),
        ('fortnightly', "Bi-mensuelle"),
        ('monthly', "Mensuelle"),
        ('quarterly', "Trimestrielle"),
        ('semiannual', "Bi-annuelle"),
        ('annual', "Annuelle"),
        ('unknown', "Inconnue"),
        )

    update_frequency = models.CharField(
        verbose_name="Fréquence de mise à jour",
        max_length=30,
        choices=FREQUENCY_CHOICES,
        default='never',
        )

    GEOCOVER_CHOICES = (
        (None, "Indéfinie"),
        ('regionale', "Régionale"),
        ('jurisdiction', "Territoire de compétence"),
        )

    geocover = models.CharField(
        verbose_name="Couverture géographique",
        max_length=30,
        null=True,
        blank=True,
        choices=GEOCOVER_CHOICES,
        default=None,
        )

    granularity = models.ForeignKey(
        to='Granularity',
        verbose_name="Granularité de la couverture territoriale",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        )

    organisation = models.ForeignKey(
        to='Organisation',
        verbose_name="Organisation",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        )

    license = models.ForeignKey(
        to='License',
        verbose_name="Licence",
        null=True,
        blank=True,
        )

    support = models.ForeignKey(
        to='Support',
        verbose_name="Support technique",
        null=True,
        blank=True,
        )

    data_type = models.ManyToManyField(
        to='DataType',
        verbose_name="Type de données",
        blank=True,
        )

    owner_name = models.CharField(
        verbose_name="Nom du producteur",
        max_length=100,
        null=True,
        blank=True,
        )

    owner_email = models.EmailField(
        verbose_name="Adresse e-mail du producteur",
        null=True,
        blank=True,
        )

    broadcaster_name = models.CharField(
        verbose_name="Nom du diffuseur",
        max_length=100,
        blank=True,
        null=True,
        )

    broadcaster_email = models.EmailField(
        verbose_name="Adresse e-mail du diffuseur",
        null=True,
        blank=True,
        )

    published = models.BooleanField(
        verbose_name="Publier le jeu de données",
        default=False,
        )

    geonet_id = models.TextField(
        verbose_name="Identifiant de la fiche de métadonnées",
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        )

    bbox = models.PolygonField(
        verbose_name="Rectangle englobant",
        null=True,
        blank=True,
        srid=4171,
        )

    def __str__(self):
        return self.title

    # Propriétés
    # ==========

    @property
    def name(self):
        return not self.slug

    @property
    def title_overflow(self):
        return three_suspension_points(self.title)

    @property
    def private(self):
        return not self.published

    @property
    def ckan_url(self):
        return urljoin(CKAN_URL, 'dataset/', self.slug)

    @property
    def api_location(self):
        kwargs = {'dataset_name': self.slug}
        return reverse('api:dataset_show', kwargs=kwargs)

    @property
    def geonet_url(self):
        if self.geonet_id:
            return urljoin(GEONETWORK_URL, 'srv/fre/catalog.search#/metadata/{id}'.format(id=self.geonet_id))

    @property
    def bounds(self):
        if self.bbox:
            minx, miny, maxx, maxy = self.bbox.extent
            return [[miny, minx], [maxy, maxx]]

    @property
    def remote_ckan_dataset(self):
        Model = apps.get_model(app_label='idgo_admin', model_name='RemoteCkanDataset')
        try:
            return Model.objects.get(dataset=self)
        except Model.DoesNotExist:
            return None

    @property
    def remote_csw_dataset(self):
        Model = apps.get_model(app_label='idgo_admin', model_name='RemoteCswDataset')
        try:
            return Model.objects.get(dataset=self)
        except Model.DoesNotExist:
            return None

    @property
    def remote_dcat_dataset(self):
        Model = apps.get_model(app_label='idgo_admin', model_name='RemoteDcatDataset')
        try:
            return Model.objects.get(dataset=self)
        except Model.DoesNotExist:
            return None

    # Méthodes héritées
    # =================

    def save(self, *args, current_user=None, synchronize=True, activate=None, **kwargs):

        # Version précédante du jeu de données (avant modification)
        previous, created = self.pk \
            and (Dataset.objects.get(pk=self.pk), False) or (None, True)
        if created:
            activate = True

        # Quelques valeurs par défaut
        # ===========================
        today = timezone.now().date()
        if not self.date_creation:      # La date de création
            self.date_creation = today
        if not self.date_modification:  # La date de modification
            self.date_modification = today
        if not self.date_publication:   # La date de publication
            self.date_publication = today

        if not self.owner_name:         # Le propriétaire du jeu de données
            self.owner_name = self.editor.get_full_name()
        if not self.owner_email:        # et son e-mail
            self.owner_email = self.editor.email

        # Le rectangle englobant du jeu de données :
        #     Il est calculé en fonction des ressources géographiques et/ou de la couverture
        #     et/ou de la couverture géographique définie
        layers = self.get_layers()
        if layers:
            # On calcule la BBOX de l'ensemble des Layers rattachés au Dataset
            extent = layers.aggregate(models.Extent('bbox')).get('bbox__extent')
            if extent:
                xmin, ymin = extent[0], extent[1]
                xmax, ymax = extent[2], extent[3]
                setattr(self, 'bbox', bounds_to_wkt(xmin, ymin, xmax, ymax))
        else:
            # Sinon, on regarde la valeur de `geocover` renseignée
            if self.geocover == 'jurisdiction':
                # Prend l'étendue du territoire de compétence
                if self.organisation:
                    jurisdiction = self.organisation.jurisdiction
                    if jurisdiction and jurisdiction.communes:
                        bounds = jurisdiction.get_bounds()
                        if bounds:
                            xmin, ymin = bounds[0][1], bounds[0][0]
                            xmax, ymax = bounds[1][1], bounds[1][0]
                            setattr(self, 'bbox', bounds_to_wkt(xmin, ymin, xmax, ymax))
            elif self.geocover == 'regionale':
                # Prend l'étendue par défaut définie en settings
                setattr(self, 'bbox', DEFAULT_BBOX)
            else:
                setattr(self, 'bbox', self.bbox or None)  # ATTENTION AUX EFFETS DE BORD !

        # On sauvegarde le jeu de données
        super().save(*args, **kwargs)

        # Puis...
        if not created:
            # Une organisation CKAN ne contenant plus
            # de jeu de données doit être désactivée.
            if previous.organisation:
                CkanHandler.deactivate_ckan_organisation_if_empty(str(previous.organisation.ckan_id))

            # On vérifie si l'organisation du jeu de données change.
            # Si c'est le cas, il est nécessaire de sauvegarder tous
            # les `Layers` rattachés au jeu de données afin de forcer
            # la modification du `Workspace` (c'est-à-dire du Mapfile)
            if previous.organisation != self.organisation:
                for resource in previous.get_resources():
                    for layer in resource.get_layers():
                        layer.save()
                        url = '{0}#{1}'.format(
                            OWS_URL_PATTERN.format(organisation=self.organisation.slug),
                            layer.name)
                        CkanHandler.update_resource(layer.name, url=url)

        # Enfin...
        if synchronize:
            ckan_dataset = self.synchronize(with_user=current_user, activate=activate)
            # puis on met à jour `ckan_id`
            self.ckan_id = UUID(ckan_dataset['id'])
            super().save(update_fields=['ckan_id'])

    def delete(self, *args, current_user=None, **kwargs):
        with_user = current_user

        # On supprime toutes les ressources attachées au jeu de données
        Resource = apps.get_model(app_label='idgo_admin', model_name='Resource')
        for resource in Resource.objects.filter(dataset=self):
            resource.delete(current_user=current_user)

        # On supprime le package CKAN
        ckan_id = str(self.ckan_id)
        if with_user:
            username = with_user.username
            apikey = CkanHandler.get_user(username)['apikey']
            with CkanUserHandler(apikey=apikey) as ckan_user:
                ckan_user.delete_dataset(ckan_id)
        else:
            CkanHandler.delete_dataset(ckan_id)

        CkanHandler.purge_dataset(ckan_id)

        # On supprime l'instance
        super().delete(*args, **kwargs)

    # Autres méthodes
    # ===============

    def clean(self):

        # Vérifie la disponibilité du « slug » dans CKAN
        slug = self.slug or slugify(self.title)[:100]
        ckan_dataset = CkanHandler.get_package(slug)
        if ckan_dataset:
            if UUID(ckan_dataset['id']) != self.ckan_id and ckan_dataset['name'] == slug:
                raise ValidationError("L'URL du jeu de données est réservé.")

    def synchronize(self, with_user=None, activate=None):
        """Synchronizer le jeu de données avec l'instance de CKAN."""

        # Identifiant du package CKAN :
        id = self.ckan_id and str(self.ckan_id) or None
        # Si la valeur est `None`, alors il s'agit d'une création.

        # Définition des propriétés du « paquet »
        # =======================================

        datatype = [item.slug for item in self.data_type.all()]

        date_creation = self.date_creation and str(self.date_creation) or ''
        date_modification = self.date_modification and str(self.date_modification) or ''
        date_publication = self.date_publication and str(self.date_publication) or ''

        broadcaster_name = self.broadcaster_name or \
            self.support and self.support.name or DEFAULT_PLATFORM_NAME
        broadcaster_email = self.broadcaster_email or \
            self.support and self.support.email or DEFAULT_CONTACT_EMAIL

        geocover = self.geocover or ''

        granularity = self.granularity and self.granularity.slug or ''

        licenses = [license['id'] for license in CkanHandler.get_licenses()]
        if self.license and self.license.ckan_id in licenses:
            license_id = self.license.ckan_id
        else:
            license_id = ''

        ows = False
        Resource = apps.get_model(app_label='idgo_admin', model_name='Resource')
        for resource in Resource.objects.filter(dataset=self):
            ows = resource.ogc_services

        # On regarde si le jeu de données est moissonnées
        # ===============================================
        remote_url = None
        # Soit CKAN :
        RemoteCkanDataset = apps.get_model(
            app_label='idgo_admin', model_name='RemoteCkanDataset')
        try:
            remote_dataset = RemoteCkanDataset.objects.get(dataset=self)
        except RemoteCkanDataset.DoesNotExist:
            pass
        else:
            remote_url = remote_dataset.url
        # Soit CSW :
        RemoteCswDataset = apps.get_model(
            app_label='idgo_admin', model_name='RemoteCswDataset')
        try:
            remote_dataset = RemoteCswDataset.objects.get(dataset=self)
        except RemoteCswDataset.DoesNotExist:
            pass
        else:
            remote_url = remote_dataset.url
        # mais pas les deux.

        spatial = self.bbox and self.bbox.geojson or ''
        support = self.support and self.support.slug or ''
        tags = [{'name': keyword.name} for keyword in self.keywords.all()]
        try:
            thumbnail = urljoin(settings.DOMAIN_NAME, self.thumbnail.url)
        except ValueError:
            thumbnail = ''

        data = {
            'author': self.owner_name,
            'author_email': self.owner_email,
            'datatype': datatype,
            'dataset_creation_date': date_creation,
            'dataset_modification_date': date_modification,
            'dataset_publication_date': date_publication,
            'frequency': self.update_frequency or 'unknown',
            'geocover': geocover,
            'granularity': granularity,
            'groups': [],
            'inspire_url': self.geonet_url,
            'license_id': license_id,
            'maintainer': broadcaster_name,
            'maintainer_email': broadcaster_email,
            'name': self.slug,
            'notes': self.description,
            'owner_org': str(self.organisation.ckan_id),
            'ows': str(ows),  # IMPORTANT
            'private': self.private,
            'remote_url': remote_url or '',
            'spatial': spatial,
            'support': support,
            'tags': tags,
            'title': self.title,
            'thumbnail': thumbnail,
            'url': '',  # IMPORTANT
            }

        if activate is not None:
            data['state'] = activate and 'active' or 'deleted'

        # Synchronisation des catégories :
        for category in self.categories.all():
            data['groups'].append({'name': category.slug})

        organisation_id = str(self.organisation.ckan_id)

        # Synchronisation de l'organisation ; si l'organisation
        # n'existe pas il faut la créer
        ckan_organisation = CkanHandler.get_organisation(organisation_id)
        if not ckan_organisation:
            CkanHandler.add_organisation(self.organisation)
        # et si l'organisation est désactiver il faut l'activer
        elif ckan_organisation.get('state') == 'deleted':
            CkanHandler.activate_organisation(organisation_id)

        if with_user:
            username = with_user.username

            # TODO: C'est très lourd de faire cela systématiquement -> voir pour améliorer cela
            CkanHandler.add_user_to_organisation(username, organisation_id)
            for category in self.categories.all():
                category_id = str(category.ckan_id)
                CkanHandler.add_user_to_group(username, category_id)
            #

            apikey = CkanHandler.get_user(username)['apikey']
            with CkanUserHandler(apikey=apikey) as ckan_user:
                return ckan_user.publish_dataset(id=id, **data)
        else:
            return CkanHandler.publish_dataset(id=id, **data)

    def get_resources(self, **kwargs):
        Model = apps.get_model(app_label='idgo_admin', model_name='Resource')
        return Model.objects.filter(dataset=self, **kwargs)

    def get_layers(self):
        if self.pk:
            Model = apps.get_model(app_label='idgo_admin', model_name='Layer')
            return Model.objects.filter(resource__dataset__pk=self.pk)

    def is_contributor(self, profile):
        Model = apps.get_model(app_label='idgo_admin', model_name='LiaisonsContributeurs')
        kvp = {
            'profile': profile,
            'organisation': self.organisation,
            'validated_on__isnull': False,
            }
        return Model.objects.filter(**kvp).exists()

    def is_referent(self, profile):
        Model = apps.get_model(app_label='idgo_admin', model_name='LiaisonsReferents')
        kvp = {
            'profile': profile,
            'organisation': self.organisation,
            'validated_on__isnull': False,
            }
        return Model.objects.filter(**kvp).exists()


class Keywords(Tag):
    # On se sert de ce modèle mandataire comme entrée dans l'Admin Django.
    class Meta(object):
        verbose_name = "Mot-clé"
        verbose_name_plural = "Mots-clés"
        proxy = True


# Signaux
# =======


@receiver(pre_save, sender=Dataset)
def pre_save_dataset(sender, instance, **kwargs):
    if not instance.slug:
        instance.slug = slugify(instance.title)[:100]


# @receiver(post_delete, sender=Dataset)
# def delete_attached_md(sender, instance, **kwargs):
#     if instance.geonet_id:
#         geonet.delete_record(instance.geonet_id)


@receiver(post_delete, sender=Dataset)
def post_delete_dataset(sender, instance, **kwargs):
    CkanHandler.deactivate_ckan_organisation_if_empty(str(instance.organisation.ckan_id))


@receiver(post_save, sender=Dataset)
def logging_after_save(sender, instance, **kwargs):
    action = kwargs.get('created', False) and 'created' or 'updated'
    logger.info('Dataset "{pk}" has been {action}'.format(pk=instance.pk, action=action))


@receiver(post_delete, sender=Dataset)
def logging_after_delete(sender, instance, **kwargs):
    logger.info('Dataset "{pk}" has been deleted'.format(pk=instance.pk))
