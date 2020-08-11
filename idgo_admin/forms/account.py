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

from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django import forms
from django.forms.models import ModelChoiceIterator
from idgo_admin.ckan_module import CkanHandler
from idgo_admin.forms.fields import AddressField
from idgo_admin.forms.fields import CityField
from idgo_admin.forms.fields import ContributorField
from idgo_admin.forms.fields import DescriptionField
from idgo_admin.forms.fields import EMailField
from idgo_admin.forms.fields import FirstNameField
from idgo_admin.forms.fields import JurisdictionField
from idgo_admin.forms.fields import LastNameField
from idgo_admin.forms.fields import LicenseField
from idgo_admin.forms.fields import OrganisatioLegalNameField
from idgo_admin.forms.fields import OrganisationLogoField
from idgo_admin.forms.fields import OrganisationTypeField
from idgo_admin.forms.fields import PasswordField
from idgo_admin.forms.fields import PhoneField
from idgo_admin.forms.fields import PostcodeField
from idgo_admin.forms.fields import ReferentField
from idgo_admin.forms.fields import UsernameField
from idgo_admin.forms.fields import WebsiteField
from idgo_admin.models import Dataset
from idgo_admin.models import Gdpr
from idgo_admin.models import Organisation
from mama_cas.forms import LoginForm as MamaLoginForm


class UserForgetPassword(forms.Form):

    class Meta(object):
        model = User
        fields = (
            'email',)

    email = EMailField()


class UserResetPassword(forms.Form):

    class Meta(object):
        model = User
        fields = (
            'username',
            'password')

    username = UsernameField()
    password1 = PasswordField()
    password2 = PasswordField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs['placeholder'] = 'Nouveau mot de passe'
        self.fields['password2'].widget.attrs['placeholder'] = 'Confirmez le nouveau mot de passe'

    def clean(self):
        if self.cleaned_data.get('password1') != self.cleaned_data.get('password2'):
            self.add_error('password1', 'Vérifiez les mots de passe')
            self.add_error('password2', '')
            raise ValidationError('Les mots de passe ne sont pas identiques.')
        return self.cleaned_data

    def save(self, request, user):
        password = self.cleaned_data.get('password1')
        if password:
            user.set_password(password)
            user.save()
            logout(request)
            login(request, user,
                  backend='django.contrib.auth.backends.ModelBackend')

        user.save()
        return user


class SignInForm(MamaLoginForm):

    username = UsernameField(required=True)
    password = PasswordField(required=True)

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        if username and password:
            try:
                self.user = authenticate(
                    request=self.request, username=username, password=password)
            except Exception as e:
                raise ValidationError(e.__str__())

            if self.user is None:
                self.add_error('username', "Vérifiez votre nom d'utilisateur")
                self.add_error('password', 'Vérifiez votre mot de passe')
                raise ValidationError('User is not found')
            else:
                ckan_user = CkanHandler.get_user(username)
                if ckan_user and ckan_user['state'] == 'deleted':
                    self.add_error('username', "Erreur interne d'authentification")
                    raise ValidationError('CKAN user is deleted')
                if not self.user.is_active:
                    self.add_error('username', "Ce compte n'est pas activé")
                    raise ValidationError('User is not activate')

        return self.cleaned_data


class UserDeleteForm(AuthenticationForm):

    class Meta(object):
        model = User
        fields = (
            'username',
            'password')

    username = UsernameField()
    password = PasswordField()


class DeleteAdminForm(forms.Form):

    new_user = forms.ModelChoiceField(
        User.objects.all().order_by('username'),
        empty_label="Selectionnez un utilisateur",
        label="Compte utilisateur pour réaffecter les jeux de donnés orphelins",
        required=False,
        widget=None,
        initial=None,
        help_text="Choisissez un nouvel utilisateur auquel seront affectés les jeux de données de l'utilisateur supprimé.",
        to_field_name=None,
        limit_choices_to=None)

    confirm = forms.BooleanField(
        label="Cocher pour confirmer la suppression de ce compte. ",
        required=True, initial=False)

    def __init__(self, *args, **kwargs):
        self.included = kwargs.pop('include', {})
        super().__init__(*args, **kwargs)
        if self.included['user_id']:
            self.fields['new_user'].queryset = User.objects.exclude(id=self.included['user_id']).exclude(is_active=False).order_by('username')
        else:
            self.fields['new_user'].queryset = User.objects.filter(is_active=True).order_by('username')

    def delete_controller(self, deleted_user, new_user, related_datasets):
        if related_datasets:
            if not new_user:
                Dataset.objects.filter(editor=deleted_user).delete()
            else:
                Dataset.objects.filter(editor=deleted_user).update(editor=new_user)
        # Profil supprimé en cascade
        deleted_user.delete()


# Re-définition de forms.Select pour le CRIGE


class ModelOrganisationIterator(ModelChoiceIterator):

    def __iter__(self):
        if self.field.empty_label is not None:
            yield ("", self.field.empty_label, "")
        queryset = self.queryset
        if not queryset._prefetch_related_lookups:
            queryset = queryset.iterator()
        for obj in queryset:
            yield self.choice(obj)

    def choice(self, obj):
        return (
            self.field.prepare_value(obj),
            self.field.label_from_instance(obj),
            obj.is_crige_partner)  # l'organisation est partenaire du CRIGE


class OrganisationSelect(forms.Select):

    @staticmethod
    def _choice_has_empty_value(choice):
        """Return True if the choice's value is empty string or None."""
        value, _, crige = choice
        return value is None or value == ''

    def optgroups(self, name, value, attrs=None):
        """Return a list of optgroups for this widget."""
        groups = []
        has_selected = False

        for index, (option_value, option_label, option_crige) in enumerate(self.choices):
            if option_value is None:
                option_value = ''

            subgroup = []
            if isinstance(option_label, (list, tuple)):
                group_name = option_value
                subindex = 0
                choices = option_label
            else:
                group_name = None
                subindex = None
                choices = [(option_value, option_label, option_crige)]
            groups.append((group_name, subgroup, index))

            for subvalue, sublabel, subextra in choices:
                selected = (
                    str(subvalue) in value and
                    (not has_selected or self.allow_multiple_selected))

                has_selected |= selected
                subgroup.append(
                    self.create_option(
                        name, subvalue, sublabel, selected, index,
                        subindex=subindex, crige=option_crige))
                if subindex is not None:
                    subindex += 1
        return groups

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None, crige=None):
        result = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        if crige:
            result['attrs']['crige'] = True
        return result


class ModelOrganisationField(forms.ModelChoiceField):
    iterator = ModelOrganisationIterator


class TermsAndConditionsCheckBoxInput(forms.CheckboxInput):
    template_name = 'idgo_admin/widgets/terms_and_conditions.html'

    def __init__(self, attrs=None, check_test=None, modal=None):
        self.modal = modal
        super().__init__(attrs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['modal'] = self.modal
        return context


class SignUpForm(forms.Form):

    class Meta(object):

        user_fields = (
            'username',
            'first_name',
            'last_name',
            'email',
            'password',
            )

        profile_fields = (
            'phone',
            'organisation',
            )

        organisation_fields = (
            'address',
            'city',
            'description',
            'org_email',
            'jurisdiction',
            'license',
            'logo',
            'new_orga',
            'organisation_type',
            'org_phone',
            'postcode',
            'website',
            )

        extended_fields = (
            'contributor',
            'referent',
            )

        fields = user_fields + profile_fields + organisation_fields + extended_fields

    # User fields
    username = UsernameField(required=True)
    first_name = FirstNameField(required=True)
    last_name = LastNameField(required=True)
    email = EMailField(required=True)
    password1 = PasswordField(required=True)
    password2 = PasswordField(required=True)

    # Profile fields
    phone = PhoneField(required=False)

    organisation = ModelOrganisationField(
        required=False,
        label='Organisation',
        queryset=Organisation.objects.filter(is_active=True),
        empty_label="Je ne suis rattaché à aucune organisation",
        widget=OrganisationSelect(attrs={"crige": False}))

    # Organisation fields
    new_orga = OrganisatioLegalNameField()
    logo = OrganisationLogoField()
    address = AddressField()
    city = CityField()
    postcode = PostcodeField()
    org_phone = PhoneField()
    org_email = EMailField()
    website = WebsiteField()
    description = DescriptionField()
    jurisdiction = JurisdictionField()
    organisation_type = OrganisationTypeField()
    license = LicenseField()

    # Extended fields
    contributor = ContributorField()
    referent = ReferentField()

    terms_and_conditions = forms.BooleanField(
        label=(
            '<a data-toggle="modal" data-target="#modal-terms">'
            "J'ai lu et j'accepte les conditions générales d'utilisation du service."
            '<a>'),
        initial=False,
        required=True,
        widget=TermsAndConditionsCheckBoxInput(
            attrs={
                'oninvalid': "this.setCustomValidity('Vous devez accepter les conditions générales d'utilisation.')",
                'oninput': "setCustomValidity('')",
                },
            modal={
                'id': 'modal-terms',
                'title': '',
                'body': '',
                },
            )
        )

    def __init__(self, *args, **kwargs):
        self.unlock_terms = kwargs.pop('unlock_terms', False)

        super().__init__(*args, **kwargs)

        gdpr = Gdpr.objects.latest('issue_date')
        self.fields['terms_and_conditions'].widget.modal['title'] = gdpr.title
        self.fields['terms_and_conditions'].widget.modal['body'] = gdpr.description_as_html
        self.fields['terms_and_conditions'].required = not self.unlock_terms

        self.fields['password1'].widget.attrs['placeholder'] = 'Mot de passe'
        self.fields['password2'].widget.attrs['placeholder'] = 'Confirmez le mot de passe'

    def clean(self):

        if not self.unlock_terms and not self.cleaned_data.get('terms_and_conditions'):
            self.add_error('terms_and_conditions', "Vous devez accepter les conditions générales d'utilisation.")

        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists() or CkanHandler.is_user_exists(username):
            self.add_error('username', "Ce nom d'utilisateur est reservé.")

        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            self.add_error('email', 'Ce courriel est reservé.')

        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'Vérifiez les mots de passes.')
        self.cleaned_data['password'] = self.cleaned_data.pop('password1')

        return self.cleaned_data

    @property
    def is_member(self):
        select_organisation = self.cleaned_data.get('organisation') or None
        create_organisation = self.cleaned_data.get('new_orga') or None
        return (select_organisation or create_organisation) and True or False

    @property
    def is_contributor(self):
        return self.cleaned_data.get('contributor', False)

    @property
    def is_referent(self):
        return self.cleaned_data.get('referent', False)

    @property
    def create_organisation(self):
        return self.cleaned_data.get('new_orga')

    @property
    def cleaned_organisation_data(self):
        data = dict((item, self.cleaned_data.get(item))
                    for item in self.Meta.organisation_fields)
        data['legal_name'] = data.pop('new_orga')
        return data

    @property
    def cleaned_user_data(self):
        return dict((item, self.cleaned_data.get(item))
                    for item in self.Meta.user_fields)

    @property
    def cleaned_profile_data(self):
        return dict((item, self.cleaned_data.get(item))
                    for item in self.Meta.profile_fields)


class UpdateAccountForm(forms.ModelForm):

    class Meta(object):
        model = User

        user_fields = (
            'first_name',
            'last_name',
            'email')

        profile_fields = (
            'phone',)

        fields = user_fields + profile_fields

    _instance = None

    # User fields
    first_name = FirstNameField()
    last_name = LastNameField()
    email = EMailField()
    password1 = PasswordField()
    password2 = PasswordField()

    # Profile fields
    phone = PhoneField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['password1'].widget.attrs['placeholder'] = 'Nouveau mot de passe'
        self.fields['password2'].widget.attrs['placeholder'] = 'Confirmez le nouveau mot de passe'

        if 'instance' in kwargs:
            self._instance = kwargs['instance']
            self.fields['phone'].initial = self._instance.profile.phone
        # else:
        #     raise Exception()

    def clean(self):
        email = self.cleaned_data.get('email')
        if email != self._instance.email and User.objects.filter(email=email).exists():
            self.add_error('email', 'Ce courriel est reservé.')

        password = self.cleaned_data.pop('password1')
        if password != self.cleaned_data.pop('password2'):
            self.add_error('password1', '')
            self.add_error('password2', 'Vérifiez les mots de passe')
        else:
            self.cleaned_data['password'] = password
        if not password:
            del self.cleaned_data['password']

        return self.cleaned_data

    @property
    def new_password(self):
        return self.cleaned_data.get('password')
