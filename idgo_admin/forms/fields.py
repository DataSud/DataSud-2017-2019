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


from django.conf import settings
from django.core.exceptions import ValidationError
from django.core import validators
from django import forms
from idgo_admin.models import Jurisdiction
from idgo_admin.models import License
from idgo_admin.models import OrganisationType
import re


try:
    PHONE_REGEX = settings.PHONE_REGEX
except AttributeError:
    PHONE_REGEX = '^0\d{9}$'


class CustomCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    template_name = 'idgo_admin/widgets/checkbox_select_multiple.html'


class InputTypeahead(forms.widgets.ChoiceWidget):
    template_name = 'idgo_admin/widgets/input_typeahead.html'


class AddressField(forms.CharField):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('label', 'Adresse')
        kwargs.setdefault('required', False)
        kwargs.setdefault('widget', forms.Textarea(
            attrs={
                'placeholder': 'Numéro de voirie et rue',
                'rows': 2}))

        super().__init__(*args, **kwargs)


class CityField(forms.CharField):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('label', 'Ville')
        kwargs.setdefault('max_length', 100)
        kwargs.setdefault('required', False)
        kwargs.setdefault('widget', forms.TextInput(
            attrs={
                'placeholder': 'Ville'}))

        super().__init__(*args, **kwargs)


class ContributorField(forms.BooleanField):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('initial', False)
        kwargs.setdefault('label', "Je souhaite être <strong>contributeur</strong> de l'organisation")
        kwargs.setdefault('required', False)

        super().__init__(*args, **kwargs)


class DescriptionField(forms.CharField):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('label', 'Description')
        kwargs.setdefault('required', False)
        kwargs.setdefault('widget', forms.Textarea(
            attrs={
                'placeholder': 'Description'}))

        super().__init__(*args, **kwargs)


class EMailField(forms.CharField):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('error_messages', {
            'invalid': "L'adresse e-mail est invalide."})
        kwargs.setdefault('label', 'Adresse e-mail*')
        kwargs.setdefault('required', False)
        kwargs.setdefault('validators', [validators.validate_email])
        kwargs.setdefault('widget', forms.EmailInput(
            attrs={
                'placeholder': 'Adresse e-mail'}))

        super().__init__(*args, **kwargs)


class FirstNameField(forms.CharField):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('label', 'Prénom*')
        kwargs.setdefault('max_length', 100)
        kwargs.setdefault('min_length', 1)
        kwargs.setdefault('widget', forms.TextInput(
            attrs={
                'placeholder': 'Prénom'}))

        super().__init__(*args, **kwargs)


class JurisdictionField(forms.ModelChoiceField):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('empty_label', 'Aucun')
        kwargs.setdefault('label', 'Territoire de compétence')
        kwargs.setdefault('queryset', Jurisdiction.objects.all())
        kwargs.setdefault('required', False)

        super().__init__(*args, **kwargs)


class LicenseField(forms.ModelChoiceField):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('empty_label', 'Sélectionnez une licence par défaut')
        kwargs.setdefault('label', 'Licence par défaut pour tout nouveau jeu de données')
        kwargs.setdefault('queryset', License.objects.all())
        kwargs.setdefault('required', False)

        super().__init__(*args, **kwargs)


class LastNameField(forms.CharField):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('label', 'Nom*')
        kwargs.setdefault('max_length', 100)
        kwargs.setdefault('min_length', 1)
        kwargs.setdefault('widget', forms.TextInput(
            attrs={
                'placeholder': 'Nom'}))

        super().__init__(*args, **kwargs)


class CustomClearableFileInput(forms.ClearableFileInput):
    template_name = 'idgo_admin/widgets/file_drop_zone.html'


class OrganisationLogoField(forms.ImageField):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('label', "Logo de l'organisation")
        kwargs.setdefault('required', False)
        kwargs.setdefault('widget', CustomClearableFileInput(
            attrs={
                'value': None,
                'max_size_info': 1048576}))

        super().__init__(*args, **kwargs)


class OrganisatioLegalNameField(forms.CharField):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('label', "Dénomination sociale*")
        kwargs.setdefault('max_length', 100)
        kwargs.setdefault('required', False)
        kwargs.setdefault('widget', forms.TextInput(
            attrs={
                'placeholder': "Dénomination sociale"}))

        super().__init__(*args, **kwargs)


class OrganisationTypeField(forms.ModelChoiceField):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('empty_label', "Sélectionnez un type d'organisation")
        kwargs.setdefault('label', "Type d'organisation")
        kwargs.setdefault('queryset', OrganisationType.objects.all())
        kwargs.setdefault('required', False)

        super().__init__(*args, **kwargs)


class MemberField(forms.BooleanField):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('initial', False)
        kwargs.setdefault('label', "Je souhaite être <strong>membre</strong> de l'organisation")
        kwargs.setdefault('required', False)

        super().__init__(*args, **kwargs)


class PasswordField(forms.CharField):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('label', 'Mot de passe*')
        kwargs.setdefault('max_length', 150)
        kwargs.setdefault('min_length', 6)
        kwargs.setdefault('required', False)
        kwargs.setdefault('widget', forms.PasswordInput(
            attrs={
                'placeholder': 'Mot de passe'}))

        super().__init__(*args, **kwargs)


class PhoneField(forms.CharField):

    def validator(self, value):
        if not re.match(PHONE_REGEX, value):
            raise ValidationError(
                'Erreur de validation du numéro de téléphone', code='invalid')

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('error_messages', {
            'invalid': 'Le numéro est invalide.'})
        kwargs.setdefault('label', "Numéro de téléphone")
        kwargs.setdefault('max_length', 30)
        kwargs.setdefault('min_length', 10)
        kwargs.setdefault('required', False)
        kwargs.setdefault('validators', [self.validator])
        kwargs.setdefault('widget', forms.TextInput(
            attrs={
                'type': 'tel',
                'class': 'phone',
                'placeholder': 'Numéro de téléphone'}))

        super().__init__(*args, **kwargs)


class PostcodeField(forms.CharField):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('error_messages', {
            'invalid': 'Le numéro est invalide.'})
        kwargs.setdefault('label', 'Code postal')
        kwargs.setdefault('max_length', 100)
        kwargs.setdefault('required', False)
        kwargs.setdefault('widget', forms.TextInput(
            attrs={
                'placeholder': 'Code postal'}))

        super().__init__(*args, **kwargs)


class ReferentField(forms.BooleanField):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('initial', False)
        kwargs.setdefault('label', "Je souhaite être <strong>référent technique</strong> de l'organisation")
        kwargs.setdefault('required', False)

        super().__init__(*args, **kwargs)


class UsernameField(forms.CharField):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('error_messages', {
            'invalid': 'Seuls les caractères alpha-numériques et le caractère « _ » sont autorisés.'})
        kwargs.setdefault('label', "Nom d'utilisateur*")
        kwargs.setdefault('max_length', 100)
        kwargs.setdefault('min_length', 3)
        kwargs.setdefault('required', True)
        kwargs.setdefault('validators', [validators.validate_slug])
        # TODO Le validateur ne voit pas les MAJ (à corriger..)
        kwargs.setdefault('widget', forms.TextInput(
            attrs={
                'placeholder': "Nom d'utilisateur"}))

        super().__init__(*args, **kwargs)


class WebsiteField(forms.URLField):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('error_messages', {
            'invalid': "L'adresse URL est erronée."})
        kwargs.setdefault('label', "URL du site internet de l'organisation")
        kwargs.setdefault('required', False)
        kwargs.setdefault('widget', forms.TextInput(
            attrs={
                'placeholder': "Site internet"}))

        super().__init__(*args, **kwargs)
