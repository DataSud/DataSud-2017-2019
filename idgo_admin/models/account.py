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
from django.db.models.signals import post_save
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from idgo_admin.ckan_module import CkanHandler
import requests
import uuid


FTP_SERVICE_URL = settings.FTP_SERVICE_URL

try:
    ADMIN_USERNAME = settings.ADMIN_USERNAME
except AttributeError:
    ADMIN_USERNAME = None


# ==============
# Classe PROFILE
# ==============


class Profile(models.Model):
    # TODO: Surcharger la classe User avec Profile

    class Meta(object):
        verbose_name = "Profil utilisateur"
        verbose_name_plural = "Profils des utilisateurs"

    user = models.OneToOneField(User, on_delete=models.CASCADE)

    organisation = models.ForeignKey(
        to='Organisation',
        verbose_name="Organisation d'appartenance",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        )

    referents = models.ManyToManyField(
        to='Organisation',
        through='LiaisonsReferents',
        related_name='profile_referents',
        verbose_name="Organisations dont l'utilisateur est réferent",
        )

    contributions = models.ManyToManyField(
        to='Organisation',
        through='LiaisonsContributeurs',
        related_name='profile_contributions',
        verbose_name="Organisations dont l'utilisateur est contributeur",
        )

    phone = models.CharField(
        verbose_name="Téléphone",
        max_length=10,
        blank=True,
        null=True,
        )

    is_active = models.BooleanField(
        verbose_name="Validation suite à confirmation mail par utilisateur",
        default=False,
        )

    membership = models.BooleanField(
        verbose_name="Utilisateur rattaché à une organisation",
        default=False,
        )

    crige_membership = models.BooleanField(
        verbose_name="Utilisateur affilié au CRIGE",
        default=False,
        )

    is_admin = models.BooleanField(
        verbose_name="Administrateur métier",
        default=False,
        )

    sftp_password = models.CharField(
        verbose_name="Mot de passe sFTP",
        max_length=10,
        blank=True,
        null=True,
        )

    def __str__(self):
        return "{} ({})".format(self.user.get_full_name(), self.user.username)

    # Propriétés
    # ==========

    @property
    def is_agree_with_terms(self):
        Gdpr = apps.get_model(app_label='idgo_admin', model_name='Gdpr')
        GdprUser = apps.get_model(app_label='idgo_admin', model_name='GdprUser')
        try:
            GdprUser.objects.get(user=self.user, gdpr=Gdpr.objects.latest('issue_date'))
        except GdprUser.DoesNotExist:
            return False
        else:
            return True

    @property
    def is_referent(self):
        kwargs = {'profile': self, 'validated_on__isnull': False}
        return LiaisonsReferents.objects.filter(**kwargs).exists()

    @property
    def referent_for(self):
        return LiaisonsReferents.get_subordinated_organisations(profile=self)

    @property
    def is_contributor(self):
        kwargs = {'profile': self, 'validated_on__isnull': False}
        return LiaisonsContributeurs.objects.filter(**kwargs).exists()

    @property
    def contribute_for(self):
        return LiaisonsContributeurs.get_contribs(profile=self)

    @property
    def is_crige_admin(self):
        return self.is_admin and self.crige_membership

    @property
    def is_ftp_account_exists(self):
        return self.sftp_password and True or False

    @property
    def api_location(self):
        kwargs = {'username': self.user.username}
        return reverse('api:user_show', kwargs=kwargs)

    # Méthodes de classe
    # ==================

    @classmethod
    def get_crige_membership(cls):
        return Profile.objects.filter(is_active=True, crige_membership=True)

    # Autres méthodes
    # ===============

    def get_roles(self, organisation=None, dataset=None):

        if organisation:
            is_referent = LiaisonsReferents.objects.filter(
                profile=self,
                organisation=organisation,
                validated_on__isnull=False).exists()
        else:
            is_referent = LiaisonsReferents.objects.filter(
                profile=self,
                validated_on__isnull=False).exists()

        return {'is_admin': self.is_admin,
                'is_referent': is_referent,
                'is_editor': (self.user == dataset.editor) if dataset else False}

    def is_referent_for(self, organisation):
        kwargs = {
            'organisation': organisation,
            'profile': self,
            'validated_on__isnull': False}
        return LiaisonsReferents.objects.filter(**kwargs).exists()

    @property
    def awaiting_member_status(self):
        try:
            action = AccountActions.objects.get(
                action='confirm_rattachement', profile=self, closed__isnull=True)
        except Exception:
            return
        return action.organisation

    @property
    def awaiting_contributor_status(self):
        return LiaisonsContributeurs.get_pending(profile=self)

    @property
    def awaiting_referent_statut(self):
        return LiaisonsReferents.get_pending(profile=self)

    # Actions sur le compte FTP

    def create_ftp_account(self):
        params = {'action': 'create', 'login': self.user.username}
        r = requests.get(FTP_SERVICE_URL, params=params)
        if r.status_code == 200:
            details = r.json()
            self.sftp_password = details.get('message')
            self.save()

    def delete_ftp_account(self):
        params = {'action': 'delete', 'login': self.user.username}
        r = requests.get(FTP_SERVICE_URL, params=params)
        if r.status_code == 200:
            self.sftp_password = None
            self.save()


# ==================
# Classes de liaison
# ==================


class LiaisonsReferents(models.Model):

    class Meta(object):
        verbose_name = "Statut de référent"
        verbose_name_plural = "Statuts de référent"
        unique_together = (
            ('profile', 'organisation'),
            )

    profile = models.ForeignKey(
        to='Profile',
        verbose_name='Profil utilisateur',
        on_delete=models.CASCADE,
        )

    organisation = models.ForeignKey(
        to='Organisation',
        verbose_name='Organisation',
        on_delete=models.CASCADE,
        )

    created_on = models.DateField(
        verbose_name="Date de la demande de statut de référent",
        auto_now_add=True,
        )

    validated_on = models.DateField(
        verbose_name="Date de la confirmation par un administrateur",
        blank=True,
        null=True,
        default=timezone.now,
        )

    def __str__(self):
        return '{full_name} ({username})--{organisation}'.format(
            full_name=self.profile.user.get_full_name(),
            username=self.profile.user.username,
            organisation=self.organisation.legal_name,
            )

    # Méthodes de classe
    # ==================

    @classmethod
    def get_subordinated_organisations(cls, profile):

        # TODO: Sortir le rôle 'admin' (Attention à l'impact que cela peut avoir sur le code)
        if profile.is_admin:
            Organisation = apps.get_model(app_label='idgo_admin', model_name='Organisation')
            return Organisation.objects.filter(is_active=True)

        kwargs = {'profile': profile, 'validated_on__isnull': False}
        return [e.organisation for e in LiaisonsReferents.objects.filter(**kwargs)]

    @classmethod
    def get_pending(cls, profile):
        kwargs = {'profile': profile, 'validated_on': None}
        return [e.organisation for e in LiaisonsReferents.objects.filter(**kwargs)]


class LiaisonsContributeurs(models.Model):

    class Meta(object):
        verbose_name = "Statut de contributeur"
        verbose_name_plural = "Statuts de contributeur"
        unique_together = (
            ('profile', 'organisation'),
            )

    profile = models.ForeignKey(
        to='Profile',
        verbose_name="Profil utilisateur",
        on_delete=models.CASCADE,
        )

    organisation = models.ForeignKey(
        to='Organisation',
        verbose_name="Organisation",
        on_delete=models.CASCADE,
        )

    created_on = models.DateField(
        verbose_name="Date de la demande de statut de contributeur",
        auto_now_add=True,
        )

    validated_on = models.DateField(
        verbose_name="Date de la confirmation par un administrateur",
        blank=True,
        null=True,
        )

    def __str__(self):
        return '{full_name} ({username})--{organisation}'.format(
            full_name=self.profile.user.get_full_name(),
            username=self.profile.user.username,
            organisation=self.organisation.legal_name,
            )

    # Méthodes de classe
    # ==================

    @classmethod
    def get_contribs(cls, profile):
        kwargs = {'profile': profile, 'validated_on__isnull': False}
        return [e.organisation for e in LiaisonsContributeurs.objects.filter(**kwargs)]

    @classmethod
    def get_contributors(cls, organisation):
        kwargs = {'organisation': organisation, 'validated_on__isnull': False}
        return [e.profile for e in LiaisonsContributeurs.objects.filter(**kwargs)]

    @classmethod
    def get_pending(cls, profile):
        kwargs = {'profile': profile, 'validated_on': None}
        return [e.organisation for e in LiaisonsContributeurs.objects.filter(**kwargs)]


# ===========================================
# Classe des actions de profile d'utilisateur
# ===========================================


class AccountActions(models.Model):

    key = models.UUIDField(
        verbose_name="Clé",
        editable=False,
        default=uuid.uuid4,
        )

    ACTION_CHOICES = (
        (
            'confirm_mail',
            "Confirmation de l'e-mail par l'utilisateur"
            ),
        (
            'confirm_new_organisation',
            "Confirmation par un administrateur de la création d'une organisation par l'utilisateur"
            ),
        (
            'confirm_rattachement',
            "Rattachement d'un utilisateur à une organisation par un administrateur"
            ),
        (
            'confirm_referent',
            "Confirmation du rôle de réferent d'une organisation pour un utilisateur par un administrateur"
            ),
        (
            'confirm_contribution',
            "Confirmation du rôle de contributeur d'une organisation pour un utilisateur par un administrateur"
            ),
        (
            'reset_password',
            "Réinitialisation du mot de passe"
            ),
        (
            'set_password_admin',
            "Initialisation du mot de passe suite à une inscription par un administrateur"
            ),
        (
            'created_organisation_through_api',
            "Création d'une organisation depuis l'API"
            ),
        )

    action = models.CharField(
        verbose_name="Action de gestion de profile",
        max_length=250,
        blank=True,
        null=True,
        choices=ACTION_CHOICES,
        default='confirm_mail',
        )

    created_on = models.DateTimeField(
        verbose_name="Date de création",
        blank=True,
        null=True,
        auto_now_add=True,
        )

    closed = models.DateTimeField(
        verbose_name="Date de validation",
        blank=True,
        null=True,
        )

    profile = models.ForeignKey(
        to='Profile',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        )

    # Pour pouvoir reutiliser AccountActions pour demandes post-inscription
    organisation = models.ForeignKey(
        to='Organisation',
        verbose_name="Organisation",
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        )

    def orga_name(self):
        return self.organisation and str(self.organisation.legal_name) or 'N/A'

    orga_name.short_description = "Nom de l'organisation concernée"

    def get_path(self):
        action = {
            'confirm_mail': (
                'confirmation_mail', {'key': self.key},
                ),
            'confirm_new_organisation': (
                'confirm_new_orga', {'key': self.key},
                ),
            'confirm_rattachement': (
                'confirm_rattachement', {'key': self.key},
                ),
            'confirm_referent': (
                'confirm_referent', {'key': self.key},
                ),
            'confirm_contribution': (
                'confirm_contribution', {'key': self.key},
                ),
            'reset_password': (
                'password_manager', {'key': self.key, 'process': 'reset'},
                ),
            'set_password_admin': (
                'password_manager', {'key': self.key, 'process': 'initiate'},
                ),
            }
        return reverse(
            'idgo_admin:{action}'.format(action=action[self.action][0]),
            kwargs=action[self.action][1])

    get_path.short_description = "Adresse de validation"


# Signaux
# =======


@receiver(pre_delete, sender=User)
def delete_ckan_user(sender, instance, **kwargs):
    CkanHandler.del_user(instance.username)


@receiver(post_save, sender=Profile)
def handle_crige_partner(sender, instance, **kwargs):
    groupname = 'crige-partner'

    username = instance.user.username
    if CkanHandler.is_user_exists(username):
        if instance.crige_membership:
            CkanHandler.add_user_to_partner_group(username, groupname)
        else:
            CkanHandler.del_user_from_partner_group(username, groupname)
