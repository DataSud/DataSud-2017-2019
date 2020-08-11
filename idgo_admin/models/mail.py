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
from django.core.mail import get_connection
from django.core.mail.message import EmailMultiAlternatives
from idgo_admin.exceptions import GenericException
from idgo_admin import logger
from idgo_admin.utils import PartialFormatter
from smtplib import SMTPDataError
from urllib.parse import urljoin


EXTRACTOR_URL = settings.EXTRACTOR_URL
DEFAULT_FROM_EMAIL = settings.DEFAULT_FROM_EMAIL


class MailError(GenericException):
    message = "Un problème est survenu lors de l'envoi des e-mails."


class Mail(models.Model):

    class Meta(object):
        verbose_name = "E-mail"
        verbose_name_plural = "E-mails"

    template_name = models.CharField(
        verbose_name="Identifiant",
        max_length=100,
        primary_key=True,
        )

    subject = models.CharField(
        verbose_name="Objet",
        max_length=255,
        null=True,
        blank=True,
        )

    message = models.TextField(
        verbose_name="Corps du message",
        null=True,
        blank=True,
        )

    def __str__(self):
        return self.template_name


def get_admins_mails(crige=False):
    kwargs = {'is_active': True, 'is_admin': True}
    if crige:
        kwargs['crige_membership'] = True
    Model = apps.get_model(app_label='idgo_admin', model_name='Profile')
    profiles = Model.objects.filter(**kwargs)
    return [profile.user.email for profile in profiles if profile.is_active]


def get_referents_mails(organisation):
    Model = apps.get_model(app_label='idgo_admin', model_name='LiaisonsReferents')
    l_profiles = Model.objects.filter(organisation=organisation, validated_on__isnull=False)
    return [l_profile.profile.user.email for l_profile in l_profiles if l_profile.profile.is_active]


def get_template_mail(template_name):
    try:
        return Mail.objects.get(template_name=template_name)
    except Mail.DoesNotExist as e:
        logger.error(e)
        return


def sender(template_mail, to=None, cc=None, bcc=None, attach_files=[], **kvp):

    if to and cc:
        for v in to:
            try:
                cc.remove(v)
            except ValueError:
                continue

    if to and bcc:
        for v in to:
            try:
                bcc.remove(v)
            except ValueError:
                continue

    subject = template_mail.subject.format(**kvp)
    body = PartialFormatter().format(template_mail.message, **kvp)
    from_email = DEFAULT_FROM_EMAIL
    connection = get_connection(fail_silently=False)

    mail = EmailMultiAlternatives(
        subject=subject, body=body,
        from_email=from_email, to=to,
        cc=cc, bcc=bcc, connection=connection)

    for attach_file in attach_files:
        mail.attach_file(attach_file)

    try:
        mail.send()
    except SMTPDataError as e:
        logger.error(e)
        return MailError()


# Pour informer l'utilisateur de la création de son compte par un administrateur
def send_account_creation_mail(user, url):
    return sender(
        get_template_mail('account_creation_by_admin'),
        full_name=user.get_full_name(),
        to=[user.email],
        url=url,
        username=user.username)


# Pour confirmer une demande de création de compte
def send_account_creation_confirmation_mail(user, url):
    return sender(
        get_template_mail('confirm_account_creation'),
        full_name=user.get_full_name(),
        to=[user.email],
        url=url,
        username=user.username)


# Pour informer de la création du compte
def send_successful_account_creation_mail(user):
    return sender(
        get_template_mail('account_activated'),
        full_name=user.get_full_name(),
        to=[user.email],
        username=user.username)


# Pour réinitialiser le mot de passe d'un compte
def send_reset_password_link_to_user(user, url):
    return sender(
        get_template_mail('reset_password'),
        full_name=user.get_full_name(),
        to=[user.email],
        url=url,
        username=user.username)


# Pour informer l'utilisateur de la suppression de son compte
def send_account_deletion_mail(email, full_name, username):
    return sender(
        get_template_mail('account_deleted'),
        full_name=full_name,
        to=[email],
        username=username)


# Pour confirmer une demande de statut de membre
def send_membership_confirmation_mail(user, organisation, url):
    return sender(
        get_template_mail('account_deleted'),
        bcc=list(set(get_admins_mails() + get_referents_mails(organisation))),
        email=user.email,
        full_name=user.get_full_name(),
        organisation=organisation.legal_name,
        url=url,
        username=user.username,
        website=organisation.website or '- adresse url manquante -')


# Pour informer l'utilisateur de son statut de membre
def send_confirmed_membership_mail(user, organisation):
    return sender(
        get_template_mail('membership_status_confirmed'),
        full_name=user.get_full_name(),
        organisation=organisation.legal_name,
        to=[user.email],
        username=user.username)


# Pour confirmer le statut de contributeur d'un utilisateur
def send_contributor_confirmation_mail(user, organisation, url):
    return sender(
        get_template_mail('confirm_contributor_status'),
        bcc=list(set(get_admins_mails() + get_referents_mails(organisation))),
        email=user.email,
        full_name=user.get_full_name(),
        organisation=organisation.legal_name,
        url=url,
        username=user.username,
        website=organisation.website or '- adresse url manquante -')


# Pour informer l'utilisateur de son statut de contributeur
def send_confirmed_contribution_mail(user, organisation):
    return sender(
        get_template_mail('contributor_status_confirmed'),
        full_name=user.get_full_name(),
        organisation=organisation.legal_name,
        to=[user.email],
        username=user.username)


# Pour confirmer le statut de référent d'un utilisateur
def send_referent_confirmation_mail(user, organisation, url):
    return sender(
        get_template_mail('confirm_referent_status'),
        bcc=list(set(get_admins_mails() + get_referents_mails(organisation))),
        email=user.email,
        full_name=user.get_full_name(),
        organisation=organisation.legal_name,
        url=url,
        username=user.username,
        website=organisation.website or '- adresse url manquante -')


# Pour informer l'utilisateur de son statut de référent
def send_confirmed_referent_mail(user, organisation):
    return sender(
        get_template_mail('referent_status_confirmed'),
        full_name=user.get_full_name(),
        organisation=organisation.legal_name,
        to=[user.email],
        username=user.username)


# Pour confirmer une demande de création d'organisation
def send_organisation_creation_confirmation_mail(user, organisation, url):
    return sender(
        get_template_mail('confirm_organisation_creation'),
        bcc=get_admins_mails(),
        email=user.email,
        full_name=user.get_full_name(),
        organisation=organisation.legal_name,
        url=url,
        username=user.username,
        website=organisation.website or '- adresse url manquante -')


# Pour informer de la création d'un jeu de données
def send_dataset_creation_mail(user, dataset):
    return sender(
        get_template_mail('dataset_created'),
        bcc=list(set(get_admins_mails() + get_referents_mails(dataset.organisation))),
        ckan_url=dataset.ckan_url,
        dataset=dataset.title,
        id=dataset.slug,
        full_name=user.get_full_name(),
        to=[user.email],
        username=user.username)


# Pour informer de la modification d'un jeu de données
def send_dataset_update_mail(user, dataset):
    return sender(
        get_template_mail('dataset_updated'),
        bcc=list(set(get_admins_mails() + get_referents_mails(dataset.organisation))),
        ckan_url=dataset.ckan_url,
        dataset=dataset.title,
        full_name=user.get_full_name(),
        id=dataset.slug,
        to=[user.email],
        username=user.username)


# Pour informer de la suppression d'un jeu de données
def send_dataset_delete_mail(user, dataset):
    return sender(
        get_template_mail('dataset_deleted'),
        bcc=list(set(get_admins_mails() + get_referents_mails(dataset.organisation))),
        dataset=dataset.title,
        full_name=user.get_full_name(),
        id=dataset.slug,
        to=[user.email],
        username=user.username)


# Pour informer de la création d'une ressource
def send_resource_creation_mail(user, resource):
    return sender(
        get_template_mail('resource_created'),
        bcc=list(set(get_admins_mails() + get_referents_mails(resource.dataset.organisation))),
        ckan_url=resource.ckan_url,
        dataset=resource.dataset.title,
        full_name=user.get_full_name(),
        id=resource.ckan_id,
        resource=resource.title,
        to=[user.email],
        username=user.username)


# Pour informer de la modification d'une ressource
def send_resource_update_mail(user, resource):
    return sender(
        get_template_mail('resource_updated'),
        bcc=list(set(get_admins_mails() + get_referents_mails(resource.dataset.organisation))),
        ckan_url=resource.ckan_url,
        dataset=resource.dataset.title,
        full_name=user.get_full_name(),
        id=resource.ckan_id,
        resource=resource.title,
        to=[user.email],
        username=user.username)


# Pour informer de la suppression d'une ressource
def send_resource_delete_mail(user, resource):
    return sender(
        get_template_mail('resource_deleted'),
        bcc=list(set(get_admins_mails() + get_referents_mails(resource.dataset.organisation))),
        dataset=resource.dataset.title,
        full_name=user.get_full_name(),
        id=resource.ckan_id,
        resource=resource.title,
        to=[user.email],
        username=user.username)


# Pour demander le rattachement à un territoire de compétence existant
def send_mail_asking_for_jurisdiction_attachment(user, jurisdiction, organisation):
    return sender(
        get_template_mail('ask_for_jurisdiction_attachment'),
        # bcc=[user.email],
        full_name=user.get_full_name(),
        user_email=user.email,
        jurisdiction=jurisdiction.name,
        jurisdiction_pk=jurisdiction.code,
        organisation=organisation.legal_name,
        organisation_pk=organisation.pk,
        to=get_admins_mails(crige=True),
        username=user.username)


# Pour demander la création d'un territoire de compétence
def send_mail_asking_for_jurisdiction_creation(user, jurisdiction, organisation, url):
    JurisdictionCommune = apps.get_model(
        app_label='idgo_admin', model_name='JurisdictionCommune')
    communes = [
        instance.commune for instance
        in JurisdictionCommune.objects.filter(jurisdiction=jurisdiction)]
    return sender(
        get_template_mail('ask_for_jurisdiction_creation'),
        # bcc=[user.email],
        full_name=user.get_full_name(),
        name=jurisdiction.name,
        code=jurisdiction.code,
        communes=','.join([commune.code for commune in communes]),
        user_email=user.email,
        url=url,
        organisation=organisation.legal_name,
        organisation_pk=organisation.pk,
        to=get_admins_mails(crige=True),
        username=user.username)


# Pour informer l'utilisateur de la demande de rattachement à un territoire de compétence
def send_jurisdiction_attachment_mail(user, jurisdiction, organisation):
    return sender(
        get_template_mail('ask_for_jurisdiction_attachment_copy_to_user'),
        full_name=user.get_full_name(),
        user_email=user.email,
        jurisdiction=jurisdiction.name,
        jurisdiction_pk=jurisdiction.code,
        organisation=organisation.legal_name,
        organisation_pk=organisation.pk,
        to=[user.email],
        username=user.username)


# Pour informer l'utilisateur de la demande de création d'un territoire de compétence
def send_jurisdiction_creation_mail(user, jurisdiction, organisation):
    JurisdictionCommune = apps.get_model(
        app_label='idgo_admin', model_name='JurisdictionCommune')
    communes = [
        instance.commune for instance
        in JurisdictionCommune.objects.filter(jurisdiction=jurisdiction)]
    return sender(
        'ask_for_jurisdiction_creation_copy_to_user',
        full_name=user.get_full_name(),
        name=jurisdiction.name,
        code=jurisdiction.code,
        communes=','.join([commune.code for commune in communes]),
        user_email=user.email,
        organisation=organisation.legal_name,
        organisation_pk=organisation.pk,
        to=[user.email],
        username=user.username)


# Pour demander un partenariat avec le CRIGE
def send_mail_asking_for_crige_partnership(user, organisation):
    return sender(
        get_template_mail('ask_for_crige_partnership'),
        full_name=user.get_full_name(),
        user_email=user.email,
        organisation=organisation.legal_name,
        organisation_pk=organisation.pk,
        to=get_admins_mails(crige=True),
        )


# Pour retourner le résultat d'une extraction
def send_extraction_successfully_mail(user, instance):
    return sender(
        get_template_mail('data_extraction_successfully'),
        full_name=user.get_full_name(),
        title=instance.target_object.__str__(),
        to=[user.email],
        url=urljoin(EXTRACTOR_URL, 'jobs/{}/download'.format(instance.uuid)),
        username=user.username)


# Pour informer de l'échec d'une extraction
def send_extraction_failure_mail(user, instance):
    return sender(
        get_template_mail('data_extraction_failure'),
        full_name=user.get_full_name(),
        title=instance.target_object.__str__(),
        to=[user.email],
        username=user.username)


# Pour contacter les utilisateur depuis le site d'administration django
def send_from_admin_site(template, bcc):
    return sender(template, bcc=bcc)
