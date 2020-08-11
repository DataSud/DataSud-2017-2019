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


from datetime import datetime
from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from django.db.models.signals import pre_save
from django.db import transaction
from django.dispatch import receiver
from django.urls import reverse
from django.utils.text import slugify
from functools import reduce
from idgo_admin.ckan_module import CkanBaseHandler
from idgo_admin.ckan_module import CkanHandler
from idgo_admin.csw_module import CswBaseHandler
from idgo_admin.dcat_module import DcatBaseHandler
from idgo_admin.dcat_module import DcatBaseError
from idgo_admin.exceptions import CkanBaseError
from idgo_admin.exceptions import CriticalError
from idgo_admin.exceptions import CswBaseError
from idgo_admin.geonet_module import GeonetUserHandler as geonet
from idgo_admin import logger
from idgo_admin.mra_client import MRAHandler
from idgo_admin.models.category import ISO_TOPIC_CHOICES
import inspect
from operator import iand
from operator import ior
from urllib.parse import urljoin
from urllib.parse import urlparse
import uuid


DEFAULT_USER_ID = settings.DEFAULT_USER_ID
DEFAULT_CONTACT_EMAIL = settings.DEFAULT_CONTACT_EMAIL
DEFAULT_PLATFORM_NAME = settings.DEFAULT_PLATFORM_NAME
ISOFORMAT_DATE = '%Y-%m-%d'
ISOFORMAT_DATETIME = '%Y-%m-%dT%H:%M:%S.%f'
OWS_URL_PATTERN = settings.OWS_URL_PATTERN


class OrganisationType(models.Model):

    class Meta(object):
        verbose_name = "Type d'organisation"
        verbose_name_plural = "Types d'organisations"
        ordering = ('name',)

    code = models.CharField(
        verbose_name="Code",
        max_length=100,
        primary_key=True,
        )

    name = models.TextField(
        verbose_name="Type d'organisation",
        )

    def __str__(self):
        return self.name


class Organisation(models.Model):

    class Meta(object):
        verbose_name = "Organisation"
        verbose_name_plural = "Organisations"
        ordering = ('slug',)

    legal_name = models.CharField(
        verbose_name="Dénomination sociale",
        max_length=100,
        unique=True,
        db_index=True,
        )

    organisation_type = models.ForeignKey(
        to='OrganisationType',
        verbose_name="Type d'organisation",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        )

    jurisdiction = models.ForeignKey(
        to='Jurisdiction',
        verbose_name="Territoire de compétence",
        blank=True,
        null=True,
        )

    slug = models.SlugField(
        verbose_name="Slug",
        max_length=100,
        unique=True,
        db_index=True,
        )

    ckan_id = models.UUIDField(
        verbose_name="Ckan UUID",
        default=uuid.uuid4,
        editable=False,
        )

    website = models.URLField(
        verbose_name="Site internet",
        blank=True,
        null=True,
        )

    email = models.EmailField(
        verbose_name="Adresse e-mail",
        blank=True,
        null=True,
        )

    description = models.TextField(
        verbose_name='Description',
        blank=True,
        null=True,
        )

    logo = models.ImageField(
        verbose_name="Logo",
        blank=True,
        null=True,
        upload_to='logos/',
        )

    address = models.TextField(
        verbose_name="Adresse",
        blank=True,
        null=True,
        )

    postcode = models.CharField(
        verbose_name="Code postal",
        max_length=100,
        blank=True,
        null=True,
        )

    city = models.CharField(
        verbose_name="Ville",
        max_length=100,
        blank=True,
        null=True,
        )

    phone = models.CharField(
        verbose_name="Téléphone",
        max_length=10,
        blank=True,
        null=True,
        )

    license = models.ForeignKey(
        to='License',
        verbose_name="Licence",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        )

    is_active = models.BooleanField(
        verbose_name="Organisation active",
        default=False,
        )

    is_crige_partner = models.BooleanField(
        verbose_name="Organisation partenaire du CRIGE",
        default=False,
        )

    geonet_id = models.TextField(
        verbose_name="UUID de la métadonnées",
        unique=True,
        db_index=True,
        blank=True,
        null=True,
        )

    def __str__(self):
        return self.legal_name

    @property
    def logo_url(self):
        try:
            return urljoin(settings.DOMAIN_NAME, self.logo.url)
        except (ValueError, Exception):
            return None

    @property
    def full_address(self):
        return "{} - {} {}".format(self.address, self.postcode, self.city)

    @property
    def ows_url(self):
        if MRAHandler.is_workspace_exists(self.slug):
            return OWS_URL_PATTERN.format(organisation=self.slug)

    @property
    def ows_settings(self):
        if MRAHandler.is_workspace_exists(self.slug):
            return MRAHandler.get_ows_settings('ows', self.slug)

    @property
    def api_location(self):
        kwargs = {'organisation_name': self.slug}
        return reverse('api:organisation_show', kwargs=kwargs)

    @property
    def members(self):
        Dataset = apps.get_model(app_label='idgo_admin', model_name='Dataset')
        Profile = apps.get_model(app_label='idgo_admin', model_name='Profile')
        LiaisonsContributeurs = apps.get_model(app_label='idgo_admin', model_name='LiaisonsContributeurs')
        LiaisonsReferents = apps.get_model(app_label='idgo_admin', model_name='LiaisonsReferents')

        filter = reduce(ior, [
            Q(organisation=self.pk),
            reduce(iand, [
                Q(liaisonscontributeurs__organisation=self.pk),
                Q(liaisonscontributeurs__validated_on__isnull=False)
                ]),
            reduce(iand, [
                Q(liaisonsreferents__organisation=self.pk),
                Q(liaisonsreferents__validated_on__isnull=False),
                ])
            ])

        profiles = Profile.objects.filter(filter).distinct().order_by('user__username')

        data = [{
            'username': member.user.username,
            'full_name': member.user.get_full_name(),
            'is_member': Profile.objects.filter(organisation=self.pk, id=member.id).exists(),
            'is_contributor': LiaisonsContributeurs.objects.filter(profile=member, organisation__id=self.pk, validated_on__isnull=False).exists(),
            'is_referent': LiaisonsReferents.objects.filter(profile=member, organisation__id=self.pk, validated_on__isnull=False).exists(),
            'crige_membership': member.crige_membership,
            'datasets_count': len(Dataset.objects.filter(organisation=self.pk, editor=member.user)),
            'profile_id': member.id
            } for member in profiles]

        return data

    def get_datasets(self, **kwargs):
        Dataset = apps.get_model(app_label='idgo_admin', model_name='Dataset')
        return Dataset.objects.filter(organisation=self, **kwargs)

    def get_crige_membership(self):
        Profile = apps.get_model(app_label='idgo_admin', model_name='Profile')
        qs = Profile.objects.filter(organisation=self, crige_membership=True)
        return [profile.user for profile in qs]

    def get_members(self):
        """Retourner la liste des utilisateurs membres de l'organisation."""
        Profile = apps.get_model(app_label='idgo_admin', model_name='Profile')
        profiles = Profile.objects.filter(organisation=self, membership=True, is_active=True)
        return [e.user for e in profiles]

    def get_contributors(self):
        """Retourner la liste des utilisateurs contributeurs de l'organisation."""
        Nexus = apps.get_model(app_label='idgo_admin', model_name='LiaisonsContributeurs')
        entries = Nexus.objects.filter(organisation=self, validated_on__isnull=False)
        return [e.profile.user for e in entries if e.profile.is_active]

    def get_referents(self):
        """Retourner la liste des utilisateurs référents de l'organisation."""
        Nexus = apps.get_model(app_label='idgo_admin', model_name='LiaisonsReferents')
        entries = Nexus.objects.filter(organisation=self, validated_on__isnull=False)
        return [e.profile.user for e in entries if e.profile.is_active]


# Triggers


@receiver(pre_save, sender=Organisation)
def pre_save_organisation(sender, instance, **kwargs):
    instance.slug = slugify(instance.legal_name)


@receiver(post_save, sender=Organisation)
def post_save_organisation(sender, instance, **kwargs):
    # Mettre à jour en cascade les profiles (utilisateurs)
    Profile = apps.get_model(app_label='idgo_admin', model_name='Profile')
    for profile in Profile.objects.filter(organisation=instance):
        profile.crige_membership = instance.is_crige_partner
        profile.save()

    # Synchroniser avec l'organisation CKAN
    if CkanHandler.is_organisation_exists(str(instance.ckan_id)):
        CkanHandler.update_organisation(instance)


# @receiver(post_delete, sender=Organisation)
# def delete_attached_md(sender, instance, **kwargs):
#     if instance.geonet_id:
#         geonet.delete_record(instance.geonet_id)


@receiver(post_delete, sender=Organisation)
def post_delete_organisation(sender, instance, **kwargs):
    if CkanHandler.is_organisation_exists(str(instance.ckan_id)):
        CkanHandler.purge_organisation(str(instance.ckan_id))


# ================================================
# MODÈLE DE SYNCHRONISATION AVEC UN CATALOGUE CKAN
# ================================================


class RemoteCkan(models.Model):

    class Meta(object):
        verbose_name = "Catalogue CKAN distant"
        verbose_name_plural = "Catalogues CKAN distants"

    organisation = models.OneToOneField(
        to='Organisation',
        on_delete=models.CASCADE,
        )

    url = models.URLField(
        verbose_name="URL",
        blank=True,
        )

    sync_with = ArrayField(
        models.SlugField(max_length=100),
        verbose_name="Organisations synchronisées",
        blank=True,
        null=True,
        )

    FREQUENCY_CHOICES = (
        ('never', "Jamais"),
        ('daily', "Quotidienne (tous les jours à minuit)"),
        ('weekly', "Hebdomadaire (tous les lundi)"),
        ('bimonthly', "Bimensuelle (1er et 15 de chaque mois)"),
        ('monthly', "Mensuelle (1er de chaque mois)"),
        ('quarterly', "Trimestrielle (1er des mois de janvier, avril, juillet, octobre)"),
        ('biannual', "Semestrielle (1er janvier et 1er juillet)"),
        ('annual', "Annuelle (1er janvier)"),
        )

    sync_frequency = models.CharField(
        verbose_name="Fréquence de synchronisation",
        max_length=20,
        blank=True,
        null=True,
        choices=FREQUENCY_CHOICES,
        default='never',
        )

    def __str__(self):
        return self.url

    def save(self, *args, **kwargs):
        Category = apps.get_model(app_label='idgo_admin', model_name='Category')
        Dataset = apps.get_model(app_label='idgo_admin', model_name='Dataset')
        License = apps.get_model(app_label='idgo_admin', model_name='License')
        Resource = apps.get_model(app_label='idgo_admin', model_name='Resource')
        ResourceFormats = apps.get_model(app_label='idgo_admin', model_name='ResourceFormats')

        # (1) Supprimer les jeux de données qui ne sont plus synchronisés
        previous = self.pk and RemoteCkan.objects.get(pk=self.pk)

        if previous:
            remote_organisation__in = [
                x for x in (previous.sync_with or [])
                if x not in (self.sync_with or [])]
            filter = {
                'remote_instance': previous,
                'remote_organisation__in': remote_organisation__in,
                }

            # TODO: 'Dataset.harvested_ckan.filter(**filter).delete()' ne fonctionne pas
            for dataset in Dataset.harvested_ckan.filter(**filter):
                dataset.delete()
        else:
            # Dans le cas d'une création, on vérifie si l'URL CKAN est valide
            try:
                with CkanBaseHandler(self.url):
                    pass
            except CkanBaseError as e:
                raise ValidationError(e.__str__(), code='url')

        # (2) Sauver l'instance
        super().save(*args, **kwargs)

        # (3) Créer/Mettre à jour les jeux de données synchronisés

        # On récupère dans le `stack` l'utilisateur effectuant l'opération
        editor = User.objects.get(pk=DEFAULT_USER_ID)
        for entry in inspect.stack():
            try:
                editor = entry[0].f_locals['request'].user._wrapped
            except (KeyError, AttributeError):
                continue
            break

        # Puis on moissonne le catalogue
        if self.sync_with:
            try:
                ckan_ids = []
                with transaction.atomic():

                    # TODO: Factoriser
                    for value in self.sync_with:
                        with CkanBaseHandler(self.url) as ckan:
                            ckan_organisation = ckan.get_organisation(
                                value, include_datasets=True,
                                include_groups=True, include_tags=True)

                        if not ckan_organisation.get('package_count', 0):
                            continue
                        for package in ckan_organisation.get('packages'):
                            if not package['state'] == 'active' \
                                    or not package['type'] == 'dataset':
                                continue
                            with CkanBaseHandler(self.url) as ckan:
                                package = ckan.get_package(package['id'])

                            ckan_id = uuid.UUID(package['id'])

                            update_frequency = dict(Dataset.FREQUENCY_CHOICES).get(
                                package.get('frequency'), 'unknown')
                            update_frequency = package.get('frequency')
                            if not(update_frequency and update_frequency
                                    in dict(Dataset.FREQUENCY_CHOICES).keys()):
                                update_frequency = 'unknown'
                            metadata_created = package.get('metadata_created', None)
                            if metadata_created:
                                metadata_created = datetime.strptime(metadata_created, ISOFORMAT_DATETIME)
                            metadata_modified = package.get('metadata_modified', None)
                            if metadata_modified:
                                metadata_modified = datetime.strptime(metadata_modified, ISOFORMAT_DATETIME)

                            try:
                                mapping_licence = MappingLicence.objects.get(
                                    remote_ckan=self, slug=package.get('license_id'))
                            except MappingLicence.DoesNotExist:
                                try:
                                    license = License.objects.get(slug='other-at')
                                except MappingLicence.DoesNotExist:
                                    license = None
                            else:
                                logger.warning("'{}' non trouvé".format(package.get('license_id')))
                                license = mapping_licence.licence

                            slug = 'sync{}-{}'.format(str(uuid.uuid4())[:7].lower(), package.get('name'))[:100]
                            kvp = {
                                'slug': slug,
                                'title': package.get('title'),
                                'description': package.get('notes'),
                                'date_creation': metadata_created and metadata_created.date(),
                                'date_modification': metadata_modified and metadata_modified.date(),
                                # date_publication
                                'editor': editor,
                                'license': license,
                                'owner_email': self.organisation.email or DEFAULT_CONTACT_EMAIL,
                                'owner_name': self.organisation.legal_name or DEFAULT_PLATFORM_NAME,
                                'organisation': self.organisation,
                                'published': not package.get('private'),
                                'remote_instance': self,
                                'remote_dataset': ckan_id,
                                'remote_organisation': value,
                                'update_frequency': update_frequency,
                                # bbox
                                # broadcaster_email
                                # broadcaster_name
                                # data_type
                                # geocover
                                # geonet_id
                                # granularity
                                # thumbnail
                                # support
                                }

                            dataset, created = Dataset.harvested_ckan.update_or_create(**kvp)

                            mapping_categories = MappingCategory.objects.filter(
                                remote_ckan=self, slug__in=[m['name'] for m in package.get('groups', [])])
                            if mapping_categories:
                                dataset.categories = set(mc.category for mc in mapping_categories)

                            if not created:
                                dataset.keywords.clear()
                            keywords = [tag['display_name'] for tag in package.get('tags')]
                            dataset.keywords.add(*keywords)
                            dataset.save(current_user=None, synchronize=True, activate=False)

                            ckan_ids.append(dataset.ckan_id)

                            for resource in package.get('resources', []):
                                try:
                                    ckan_id = uuid.UUID(resource['id'])
                                except ValueError as e:
                                    logger.exception(e)
                                    logger.error("I can't crash here, so I do not pay any attention to this error.")
                                    continue

                                try:
                                    ckan_format = resource['format'].upper()
                                    format_type = ResourceFormats.objects.get(ckan_format=ckan_format)
                                except (ResourceFormats.MultipleObjectsReturned, ResourceFormats.DoesNotExist, TypeError) as e:
                                    logger.exception(e)
                                    logger.error("I can't crash here, so I do not pay any attention to this error.")
                                    format_type = None

                                kvp = {
                                    'ckan_id': ckan_id,
                                    'dataset': dataset,
                                    'format_type': format_type,
                                    'title': resource['name'],
                                    'referenced_url': resource['url'],
                                    }

                                try:
                                    resource = Resource.objects.get(ckan_id=ckan_id)
                                except Resource.DoesNotExist:
                                    resource = Resource.default.create(
                                        save_opts={'current_user': None, 'synchronize': True}, **kvp)
                                else:
                                    for k, v in kvp.items():
                                        setattr(resource, k, v)
                                resource.save(current_user=None, synchronize=True)

            except Exception as e:
                for id in ckan_ids:
                    CkanHandler.purge_dataset(str(id))
                logger.error(e)
                raise CriticalError()
            else:
                for id in ckan_ids:
                    CkanHandler.publish_dataset(id=str(id), state='active')

    def delete(self, *args, **kwargs):
        Dataset = apps.get_model(app_label='idgo_admin', model_name='Dataset')
        for dataset in Dataset.harvested_ckan.filter(remote_instance=self):
            dataset.delete()
        return super().delete(*args, **kwargs)


class RemoteCkanDataset(models.Model):

    class Meta(object):
        verbose_name = "Jeu de données moissonné"
        verbose_name_plural = "Jeux de données moissonnés"
        unique_together = ('remote_instance', 'dataset')

    remote_instance = models.ForeignKey(
        to='RemoteCkan',
        on_delete=models.CASCADE,
        to_field='id',
        )

    dataset = models.ForeignKey(
        to='Dataset',
        on_delete=models.CASCADE,
        to_field='id',
        )

    remote_dataset = models.UUIDField(
        verbose_name="Ckan UUID",
        editable=False,
        null=True,
        blank=True,
        unique=True,
        )

    remote_organisation = models.SlugField(
        verbose_name="Organisation distante",
        max_length=100,
        blank=True,
        null=True,
        )

    created_by = models.ForeignKey(
        User,
        related_name='creates_dataset_from_remote_ckan',
        verbose_name="Utilisateur",
        null=True,
        on_delete=models.SET_NULL,
        )

    created_on = models.DateTimeField(
        verbose_name="Créé le",
        auto_now_add=True,
        )

    updated_on = models.DateTimeField(
        verbose_name="Mis-à-jour le",
        auto_now_add=True,
        )

    def __str__(self):
        return '{0} - {1}'.format(self.remote_instance, self.dataset)

    @property
    def url(self):
        base_url = self.remote_instance.url
        if not base_url.endswith('/'):
            base_url += '/'
        return reduce(urljoin, [base_url, 'dataset/', str(self.remote_dataset)])


class MappingLicence(models.Model):

    class Meta(object):
        verbose_name = "Mapping license"
        verbose_name_plural = "Mapping licenses"

    remote_ckan = models.ForeignKey('RemoteCkan', on_delete=models.CASCADE)

    licence = models.ForeignKey('License', on_delete=models.CASCADE)

    slug = models.SlugField('Slug', null=True)


class MappingCategory(models.Model):

    class Meta(object):
        verbose_name = "Mapping categorie"
        verbose_name_plural = "Mapping categories"

    remote_ckan = models.ForeignKey('RemoteCkan', on_delete=models.CASCADE)

    category = models.ForeignKey('Category', on_delete=models.CASCADE)

    slug = models.SlugField('Slug', null=True)


# ===============================================
# MODÈLE DE SYNCHRONISATION AVEC UN CATALOGUE CWS
# ===============================================


class RemoteCsw(models.Model):

    class Meta(object):
        verbose_name = "Catalogue CSW distant"
        verbose_name_plural = "Catalogues CSW distants"

    organisation = models.OneToOneField(
        to='Organisation',
        on_delete=models.CASCADE,
        )

    url = models.URLField(
        verbose_name="URL",
        blank=True,
        )

    getrecords = models.TextField(
        verbose_name="GetRecords",
        blank=True,
        null=True,
        )

    FREQUENCY_CHOICES = (
        ('never', "Jamais"),
        ('daily', "Quotidienne (tous les jours à minuit)"),
        ('weekly', "Hebdomadaire (tous les lundi)"),
        ('bimonthly', "Bimensuelle (1er et 15 de chaque mois)"),
        ('monthly', "Mensuelle (1er de chaque mois)"),
        ('quarterly', "Trimestrielle (1er des mois de janvier, avril, juillet, octobre)"),
        ('biannual', "Semestrielle (1er janvier et 1er juillet)"),
        ('annual', "Annuelle (1er janvier)"),
        )

    sync_frequency = models.CharField(
        verbose_name="Fréquence de synchronisation",
        max_length=20,
        blank=True,
        null=True,
        choices=FREQUENCY_CHOICES,
        default='never',
        )

    def __str__(self):
        return self.url

    def save(self, *args, harvest=True, **kwargs):
        Category = apps.get_model(app_label='idgo_admin', model_name='Category')
        Dataset = apps.get_model(app_label='idgo_admin', model_name='Dataset')
        License = apps.get_model(app_label='idgo_admin', model_name='License')
        Resource = apps.get_model(app_label='idgo_admin', model_name='Resource')
        ResourceFormats = apps.get_model(app_label='idgo_admin', model_name='ResourceFormats')

        # (1) Supprimer les jeux de données qui ne sont plus synchronisés
        previous = self.pk and RemoteCsw.objects.get(pk=self.pk)
        if previous:
            for dataset in Dataset.harvested_csw.filter(remote_instance=previous):
                dataset.delete()
        else:
            # Dans le cas d'une création, on vérifie si l'URL CSW est valide
            try:
                with CswBaseHandler(self.url):
                    pass
            except CswBaseError as e:
                raise ValidationError(e.__str__(), code='url')

        # (2) Sauver l'instance
        super().save(*args, **kwargs)

        # (3) Créer/Mettre à jour les jeux de données synchronisés

        # On récupère dans le `stack` l'utilisateur effectuant l'opération
        editor = None
        for entry in inspect.stack():
            try:
                editor = entry[0].f_locals['request'].user._wrapped
            except (KeyError, AttributeError):
                continue
            break

        if not previous:
            return

        if harvest:
            # Puis on moissonne le catalogue
            try:
                ckan_ids = []
                geonet_ids = []
                with transaction.atomic():

                    with CswBaseHandler(self.url) as csw:
                        packages = csw.get_packages(xml=self.getrecords or None)

                    for package in packages:
                        if not package['type'] == 'dataset':
                            continue

                        geonet_id = package['id']
                        update_frequency = dict(Dataset.FREQUENCY_CHOICES).get(
                            package.get('frequency'), 'unknown')
                        update_frequency = package.get('frequency')
                        if not(update_frequency and update_frequency
                                in dict(Dataset.FREQUENCY_CHOICES).keys()):
                            update_frequency = 'unknown'

                        date_creation = package.get('dataset_creation_date', None)
                        if date_creation:
                            try:
                                date_creation = datetime.strptime(date_creation, ISOFORMAT_DATE)
                            except ValueError as e:
                                logger.warning(e)
                                date_creation = None

                        date_modification = package.get('dataset_modification_date', None)
                        if date_modification:
                            try:
                                date_modification = datetime.strptime(date_modification, ISOFORMAT_DATE)
                            except ValueError as e:
                                logger.warning(e)
                                date_modification = None

                        date_publication = package.get('dataset_publication_date', None)
                        if date_publication:
                            try:
                                date_publication = datetime.strptime(date_publication, ISOFORMAT_DATE)
                            except ValueError as e:
                                logger.warning(e)
                                date_publication = None

                        # Licence
                        license_titles = package.get('license_titles')
                        filters = [
                            Q(slug__in=license_titles),
                            Q(title__in=license_titles),
                            Q(alternate_titles__overlap=license_titles),
                            ]
                        license = License.objects.filter(reduce(ior, filters)).distinct().first()
                        if not license:
                            try:
                                license = License.objects.get(slug=settings.DEFAULTS_VALUES.get('LICENSE'))
                            except License.DoesNotExist:
                                license = License.objects.first()

                        # On pousse la fiche de MD dans Geonet
                        if not geonet.get_record(geonet_id):
                            try:
                                geonet.create_record(geonet_id, package['xml'])
                            except Exception as e:
                                logger.warning('La création de la fiche de métadonnées a échoué.')
                                logger.error(e)
                            else:
                                geonet_ids.append(geonet_id)
                                geonet.publish(geonet_id)  # Toujours publier la fiche
                        else:
                            try:
                                geonet.update_record(geonet_id, package['xml'])
                            except Exception as e:
                                logger.warning('La mise à jour de la fiche de métadonnées a échoué.')
                                logger.error(e)

                        slug = 'sync{}-{}'.format(str(uuid.uuid4())[:7].lower(), slugify(geonet_id))[:100]
                        kvp = {
                            'slug': slug,
                            'title': package.get('title'),
                            'description': package.get('notes'),
                            'date_creation': date_creation and date_creation.date(),
                            'date_modification': date_modification and date_modification.date(),
                            'date_publication': date_publication and date_publication.date(),
                            'editor': editor,
                            'license': license,
                            'owner_email': self.organisation.email or DEFAULT_CONTACT_EMAIL,
                            'owner_name': self.organisation.legal_name or DEFAULT_PLATFORM_NAME,
                            'organisation': self.organisation,
                            'published': not package.get('private'),
                            'remote_instance': self,
                            'remote_dataset': geonet_id,
                            'update_frequency': update_frequency,
                            'bbox': package.get('bbox'),
                            # broadcaster_email
                            # broadcaster_name
                            # data_type
                            # geocover
                            'geonet_id': geonet_id,
                            # granularity
                            # thumbnail
                            # support
                            }

                        dataset, created = Dataset.harvested_csw.update_or_create(**kvp)
                        if created:
                            ckan_ids.append(dataset.ckan_id)

                        categories_name = [m['name'] for m in package.get('groups', [])]
                        iso_topic_reverse = dict((v, k) for k, v in Category._meta.fields[5].choices)

                        filters = [
                            Q(slug__in=categories_name),
                            Q(name__in=categories_name),
                            Q(iso_topic__in=[m['name'] for m in package.get('groups', [])]),
                            Q(iso_topic__in=[iso_topic_reverse.get(name) for name in categories_name]),
                            Q(alternate_titles__overlap=categories_name),
                            ]

                        categories = Category.objects.filter(reduce(ior, filters)).distinct()
                        if categories:
                            dataset.categories.set(categories, clear=True)

                        if not created:
                            dataset.keywords.clear()
                        keywords = [tag['display_name'] for tag in package.get('tags')]
                        dataset.keywords.add(*keywords)

                        dataset.save(current_user=None, synchronize=True, activate=False)

                        for resource in package.get('resources', []):
                            try:
                                ckan_id = uuid.uuid4()
                            except ValueError as e:
                                logger.exception(e)
                                logger.error("I can't crash here, so I do not pay any attention to this error.")
                                continue

                            filters = []
                            protocol = resource.get('protocol')
                            protocol and filters.append(Q(protocol=protocol))
                            mimetype = resource.get('mimetype')
                            mimetype and filters.append(Q(mimetype__overlap=[mimetype]))
                            try:
                                format_type = ResourceFormats.objects.get(reduce(iand, filters))
                            except (ResourceFormats.MultipleObjectsReturned, ResourceFormats.DoesNotExist, TypeError):
                                format_type = None

                            kvp = {
                                'ckan_id': ckan_id,
                                'dataset': dataset,
                                'format_type': format_type,
                                'title': resource['name'] or resource['url'],
                                'referenced_url': resource['url'],
                                }

                            try:
                                resource = Resource.objects.get(ckan_id=ckan_id)
                            except Resource.DoesNotExist:
                                resource = Resource.default.create(
                                    save_opts={'current_user': editor, 'synchronize': True}, **kvp)
                            else:
                                for k, v in kvp.items():
                                    setattr(resource, k, v)
                            resource.save(current_user=editor, synchronize=True)

            except Exception as e:
                for id in ckan_ids:
                    logger.warning('Delete CKAN package : {id}.'.format(id=str(id)))
                    CkanHandler.purge_dataset(str(id))
                for id in geonet_ids:
                    logger.warning('Delete MD : {id}.'.format(id=str(id)))
                    geonet.delete_record(id)
                logger.error(e)
                raise CriticalError()
            else:
                for id in ckan_ids:
                    CkanHandler.publish_dataset(id=str(id), state='active')

    def delete(self, *args, **kwargs):
        Dataset = apps.get_model(app_label='idgo_admin', model_name='Dataset')
        for dataset in Dataset.harvested_csw.filter(remote_instance=self):
            dataset.delete()
        return super().delete(*args, **kwargs)


class RemoteCswDataset(models.Model):

    class Meta(object):
        verbose_name = "Jeu de données moissonné"
        verbose_name_plural = "Jeux de données moissonnés"
        unique_together = ('remote_instance', 'dataset')

    remote_instance = models.ForeignKey(
        to='RemoteCsw',
        on_delete=models.CASCADE,
        to_field='id',
        )

    dataset = models.ForeignKey(
        to='Dataset',
        on_delete=models.CASCADE,
        to_field='id',
        )

    remote_dataset = models.CharField(
        verbose_name="Jeu de données distant",
        max_length=100,
        editable=False,
        null=True,
        blank=True,
        unique=True,
        )

    created_by = models.ForeignKey(
        User,
        related_name='creates_dataset_from_remote_csw',
        verbose_name="Utilisateur",
        null=True,
        on_delete=models.SET_NULL,
        )

    created_on = models.DateTimeField(
        verbose_name="Créé le",
        auto_now_add=True,
        )

    updated_on = models.DateTimeField(
        verbose_name="Mis-à-jour le",
        auto_now_add=True,
        )

    def __str__(self):
        return '{0} - {1}'.format(self.remote_instance, self.dataset)

    @property
    def url(self):
        parsed = urlparse(self.remote_instance.url)
        return '{scheme}://{netloc}/'.format(scheme=parsed.scheme, netloc=parsed.netloc)


# ================================================
# MODÈLE DE SYNCHRONISATION AVEC UN CATALOGUE DCAT
# ================================================


class RemoteDcat(models.Model):

    class Meta(object):
        verbose_name = "Catalogue DCAT distant"
        verbose_name_plural = "Catalogues DCAT distants"

    organisation = models.OneToOneField(
        to='Organisation',
        on_delete=models.CASCADE,
        )

    url = models.URLField(
        verbose_name="URL",
        blank=True,
        )

    FREQUENCY_CHOICES = (
        ('never', "Jamais"),
        ('daily', "Quotidienne (tous les jours à minuit)"),
        ('weekly', "Hebdomadaire (tous les lundi)"),
        ('bimonthly', "Bimensuelle (1er et 15 de chaque mois)"),
        ('monthly', "Mensuelle (1er de chaque mois)"),
        ('quarterly', "Trimestrielle (1er des mois de janvier, avril, juillet, octobre)"),
        ('biannual', "Semestrielle (1er janvier et 1er juillet)"),
        ('annual', "Annuelle (1er janvier)"),
        )

    sync_frequency = models.CharField(
        verbose_name="Fréquence de synchronisation",
        max_length=20,
        blank=True,
        null=True,
        choices=FREQUENCY_CHOICES,
        default='never',
        )

    def __str__(self):
        return self.url

    def save(self, *args, harvest=True, **kwargs):
        Category = apps.get_model(app_label='idgo_admin', model_name='Category')
        Dataset = apps.get_model(app_label='idgo_admin', model_name='Dataset')
        License = apps.get_model(app_label='idgo_admin', model_name='License')
        Resource = apps.get_model(app_label='idgo_admin', model_name='Resource')
        ResourceFormats = apps.get_model(app_label='idgo_admin', model_name='ResourceFormats')

        # (1) Supprimer les jeux de données qui ne sont plus synchronisés
        previous = self.pk and RemoteDcat.objects.get(pk=self.pk)
        if previous:
            for dataset in Dataset.harvested_dcat.filter(remote_instance=previous):
                dataset.delete()
        else:
            # Dans le cas d'une création, on vérifie si l'URL CSW est valide
            try:
                with DcatBaseHandler(self.url) as dcat:
                    pass
            except DcatBaseError as e:
                raise ValidationError(e.__str__(), code='url')

        # (2) Sauver l'instance
        super().save(*args, **kwargs)

        # (3) Créer/Mettre à jour les jeux de données synchronisés

        # On récupère dans le `stack` l'utilisateur effectuant l'opération
        editor = None
        for entry in inspect.stack():
            try:
                editor = entry[0].f_locals['request'].user._wrapped
            except (KeyError, AttributeError):
                continue
            break

        if not previous:
            return

        if harvest:
            # Puis on moissonne le catalogue
            try:
                ckan_ids = []
                geonet_ids = []
                with transaction.atomic():
                    with DcatBaseHandler(self.url) as dcat:
                        for package in dcat.get_packages():
                            geonet_id = str(uuid.uuid4())
                            update_frequency = dict(Dataset.FREQUENCY_CHOICES).get(
                                package.get('frequency'), 'unknown')
                            update_frequency = package.get('frequency')
                            if not(update_frequency and update_frequency
                                    in dict(Dataset.FREQUENCY_CHOICES).keys()):
                                update_frequency = 'unknown'

                            date_creation = package.get('dataset_creation_date', None)
                            if date_creation:
                                try:
                                    date_creation = datetime.strptime(date_creation, ISOFORMAT_DATE)
                                except ValueError as e:
                                    logger.warning(e)
                                    date_creation = None

                            date_modification = package.get('dataset_modification_date', None)
                            if date_modification:
                                try:
                                    date_modification = datetime.strptime(date_modification, ISOFORMAT_DATE)
                                except ValueError as e:
                                    logger.warning(e)
                                    date_modification = None

                            date_publication = package.get('dataset_publication_date', None)
                            if date_publication:
                                try:
                                    date_publication = datetime.strptime(date_publication, ISOFORMAT_DATE)
                                except ValueError as e:
                                    logger.warning(e)
                                    date_publication = None

                            # Licence
                            license_titles = package.get('license_titles')
                            filters = [
                                Q(slug__in=license_titles),
                                Q(title__in=license_titles),
                                Q(alternate_titles__overlap=license_titles),
                                ]
                            license = License.objects.filter(reduce(ior, filters)).distinct().first()
                            if not license:
                                try:
                                    license = License.objects.get(slug=settings.DEFAULTS_VALUES.get('LICENSE'))
                                except License.DoesNotExist:
                                    license = License.objects.first()

                            # On pousse la fiche de MD dans Geonet
                            # ====================================
                            if not geonet.get_record(geonet_id):
                                try:
                                    geonet.create_record(geonet_id, package['xml'])
                                except Exception as e:
                                    logger.warning('La création de la fiche de métadonnées a échoué.')
                                    logger.error(e)
                                else:
                                    geonet_ids.append(geonet_id)
                                    geonet.publish(geonet_id)  # Toujours publier la fiche
                            else:
                                try:
                                    geonet.update_record(geonet_id, package['xml'])
                                except Exception as e:
                                    logger.warning('La mise à jour de la fiche de métadonnées a échoué.')
                                    logger.error(e)

                            slug = 'sync{}-{}'.format(str(uuid.uuid4())[:7].lower(), slugify(geonet_id))[:100]
                            kvp = {
                                'slug': slug,
                                'title': package.get('title'),
                                'description': package.get('notes'),
                                'date_creation': date_creation and date_creation.date(),
                                'date_modification': date_modification and date_modification.date(),
                                'date_publication': date_publication and date_publication.date(),
                                'editor': editor,
                                'license': license,
                                'owner_email': self.organisation.email or DEFAULT_CONTACT_EMAIL,
                                'owner_name': self.organisation.legal_name or DEFAULT_PLATFORM_NAME,
                                'organisation': self.organisation,
                                'published': not package.get('private'),
                                'remote_instance': self,
                                'remote_dataset': geonet_id,
                                'update_frequency': update_frequency,
                                'bbox': package.get('bbox'),
                                # broadcaster_email
                                # broadcaster_name
                                # data_type
                                # geocover
                                'geonet_id': geonet_id,
                                # granularity
                                # thumbnail
                                # support
                                }

                            dataset, created = Dataset.harvested_dcat.update_or_create(**kvp)
                            if created:
                                ckan_ids.append(dataset.ckan_id)

                            categories_name = [m['name'] for m in package.get('groups', [])]
                            iso_topic_reverse = dict((v, k) for k, v in Category._meta.fields[5].choices)

                            filters = [
                                Q(slug__in=categories_name),
                                Q(name__in=categories_name),
                                Q(iso_topic__in=[m['name'] for m in package.get('groups', [])]),
                                Q(iso_topic__in=[iso_topic_reverse.get(name) for name in categories_name]),
                                Q(alternate_titles__overlap=categories_name),
                                ]

                            categories = Category.objects.filter(reduce(ior, filters)).distinct()
                            if categories:
                                dataset.categories.set(categories, clear=True)

                            if not created:
                                dataset.keywords.clear()
                            keywords = [tag['display_name'] for tag in package.get('tags')]
                            dataset.keywords.add(*keywords)

                            dataset.save(current_user=None, synchronize=True, activate=False)

                            for resource in package.get('resources', []):
                                try:
                                    ckan_id = uuid.uuid4()
                                except ValueError as e:
                                    logger.exception(e)
                                    logger.error("I can't crash here, so I do not pay any attention to this error.")
                                    continue

                                filters = []
                                protocol = resource.get('protocol')
                                protocol and filters.append(Q(protocol=protocol))
                                mimetype = resource.get('mimetype')
                                mimetype and filters.append(Q(mimetype__overlap=[mimetype]))
                                try:
                                    format_type = ResourceFormats.objects.get(reduce(iand, filters))
                                except (ResourceFormats.MultipleObjectsReturned, ResourceFormats.DoesNotExist, TypeError):
                                    format_type = None

                                kvp = {
                                    'ckan_id': ckan_id,
                                    'dataset': dataset,
                                    'format_type': format_type,
                                    'title': resource['name'] or resource['url'],
                                    'referenced_url': resource['url'],
                                    }

                                try:
                                    resource = Resource.objects.get(ckan_id=ckan_id)
                                except Resource.DoesNotExist:
                                    resource = Resource.default.create(
                                        save_opts={'current_user': editor, 'synchronize': True}, **kvp)
                                else:
                                    for k, v in kvp.items():
                                        setattr(resource, k, v)
                                resource.save(current_user=editor, synchronize=True)

            except Exception as e:
                for id in ckan_ids:
                    logger.warning('Delete CKAN package : {id}.'.format(id=str(id)))
                    CkanHandler.purge_dataset(str(id))
                for id in geonet_ids:
                    logger.warning('Delete MD : {id}.'.format(id=str(id)))
                    geonet.delete_record(id)
                logger.error(e)
                raise CriticalError()
            else:
                for id in ckan_ids:
                    CkanHandler.publish_dataset(id=str(id), state='active')

    def delete(self, *args, **kwargs):
        Dataset = apps.get_model(app_label='idgo_admin', model_name='Dataset')
        for dataset in Dataset.harvested_dcat.filter(remote_instance=self):
            dataset.delete()
        return super().delete(*args, **kwargs)


class RemoteDcatDataset(models.Model):

    class Meta(object):
        verbose_name = "Jeu de données moissonné"
        verbose_name_plural = "Jeux de données moissonnés"
        unique_together = ('remote_instance', 'dataset')

    remote_instance = models.ForeignKey(
        to='RemoteDcat',
        on_delete=models.CASCADE,
        to_field='id',
        )

    dataset = models.ForeignKey(
        to='Dataset',
        on_delete=models.CASCADE,
        to_field='id',
        )

    remote_dataset = models.CharField(
        verbose_name="Jeu de données distant",
        max_length=100,
        editable=False,
        null=True,
        blank=True,
        unique=True,
        )

    created_by = models.ForeignKey(
        User,
        related_name='creates_dataset_from_remote_dcat',
        verbose_name="Utilisateur",
        null=True,
        on_delete=models.SET_NULL,
        )

    created_on = models.DateTimeField(
        verbose_name="Créé le",
        auto_now_add=True,
        )

    updated_on = models.DateTimeField(
        verbose_name="Mis-à-jour le",
        auto_now_add=True,
        )

    def __str__(self):
        return '{0} - {1}'.format(self.remote_instance, self.dataset)

    @property
    def url(self):
        parsed = urlparse(self.remote_instance.url)
        return '{scheme}://{netloc}/'.format(scheme=parsed.scheme, netloc=parsed.netloc)
