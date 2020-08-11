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


from django import forms
from django.utils.text import slugify
from idgo_admin.ckan_module import CkanBaseHandler
from idgo_admin.csw_module import CswBaseHandler
from idgo_admin.dcat_module import DcatBaseHandler
from idgo_admin.exceptions import CkanBaseError
from idgo_admin.exceptions import CswBaseError
from idgo_admin.exceptions import DcatBaseError
from idgo_admin.forms.fields import AddressField
from idgo_admin.forms.fields import CityField
from idgo_admin.forms.fields import ContributorField
from idgo_admin.forms.fields import CustomCheckboxSelectMultiple
from idgo_admin.forms.fields import DescriptionField
from idgo_admin.forms.fields import EMailField
from idgo_admin.forms.fields import JurisdictionField
from idgo_admin.forms.fields import LicenseField
from idgo_admin.forms.fields import MemberField
from idgo_admin.forms.fields import OrganisatioLegalNameField
from idgo_admin.forms.fields import OrganisationLogoField
from idgo_admin.forms.fields import OrganisationTypeField
from idgo_admin.forms.fields import PhoneField
from idgo_admin.forms.fields import PostcodeField
from idgo_admin.forms.fields import ReferentField
from idgo_admin.forms.fields import WebsiteField
from idgo_admin import logger
from idgo_admin.models import Category
from idgo_admin.models import Jurisdiction
from idgo_admin.models import License
from idgo_admin.models import MappingCategory
from idgo_admin.models import MappingLicence
from idgo_admin.models import Organisation
from idgo_admin.models import RemoteCkan
from idgo_admin.models import RemoteCsw
from idgo_admin.models import RemoteDcat


class OrganisationForm(forms.ModelForm):

    class Meta(object):
        model = Organisation

        organisation_fields = (
            'address',
            'city',
            'description',
            'email',
            'jurisdiction',
            'license',
            'logo',
            'legal_name',
            'organisation_type',
            'phone',
            'postcode',
            'website',
            )

        extended_fields = (
            'contributor_process',
            'rattachement_process',
            'referent_process',
            )

        fields = organisation_fields + extended_fields

    # Organisation fields
    legal_name = OrganisatioLegalNameField(required=True)
    logo = OrganisationLogoField()
    address = AddressField()
    city = CityField()
    postcode = PostcodeField()
    org_phone = PhoneField()
    email = EMailField()
    website = WebsiteField()
    description = DescriptionField()
    jurisdiction = JurisdictionField()
    organisation_type = OrganisationTypeField()
    license = LicenseField()

    # Extended fields
    rattachement_process = MemberField()
    contributor_process = ContributorField()
    referent_process = ReferentField()

    def __init__(self, *args, **kwargs):
        self.include_args = kwargs.pop('include', {})
        self.extended = self.include_args.get('extended', False)
        self.instance = kwargs.get('instance', None)
        self.user = self.include_args.get('user')

        super().__init__(*args, **kwargs)

        if not self.extended:
            for item in self.Meta.extended_fields:
                self.fields[item].widget = forms.HiddenInput()

        if self.instance and self.instance.logo:
            self.fields['logo'].widget.attrs['value'] = self.instance.logo.url

        if self.instance and not self.user.profile.is_crige_admin:
            self.fields['jurisdiction'].queryset = \
                Jurisdiction.objects.filter(pk__in=self.instance.jurisdiction and [self.instance.jurisdiction.pk] or [])
            self.fields['jurisdiction'].widget.attrs['disabled'] = 'disabled'
            self.fields['jurisdiction'].widget.attrs['class'] = 'disabled'

    def clean(self):
        if not self.instance:
            legal_name = self.cleaned_data.get('legal_name')
            if Organisation.objects.filter(slug=slugify(legal_name)).count() > 0:
                self.add_error('legal_name', 'Une organisation portant le même nom existe déjà.')
        if self.instance and not self.user.profile.is_crige_admin:
            self.cleaned_data['jurisdiction'] = self.instance.jurisdiction
        return self.cleaned_data


# ======================================
# FORMULAIRE DE MOISSONNAGE DE SITE CKAN
# ======================================


class RemoteCkanForm(forms.ModelForm):

    class Meta(object):
        model = RemoteCkan
        fields = (
            'url',
            'sync_with',
            'sync_frequency',
            )
        mapping = tuple()

    url = forms.URLField(
        label="URL du catalogue CKAN*",
        required=True,
        max_length=200,
        error_messages={
            'invalid': "L'adresse URL est erronée.",
            },
        widget=forms.TextInput(
            attrs={
                'placeholder': "https://demo.ckan.org",
                },
            ),
        )

    sync_with = forms.MultipleChoiceField(
        label="Organisations à synchroniser*",
        required=False,
        choices=(),  # ckan api -> list_organisations
        widget=CustomCheckboxSelectMultiple(
            attrs={
                'class': 'list-group-checkbox',
                },
            ),
        )

    sync_frequency = forms.ChoiceField(
        label="Fréquence de synchronisation*",
        required=True,
        choices=Meta.model.FREQUENCY_CHOICES,
        initial='never',
        )

    def __init__(self, *args, **kwargs):
        self.cleaned_data = {}
        super().__init__(*args, **kwargs)

        instance = kwargs.get('instance', None)
        if instance and instance.url:
            self.fields['url'].widget.attrs['readonly'] = True
            # Récupérer la liste des organisations
            try:
                with CkanBaseHandler(instance.url) as ckan:
                    organisations = ckan.get_all_organisations(
                        all_fields=True, include_dataset_count=True)
            except CkanBaseError as e:
                self.add_error('url', e.message)
            else:
                self.fields['sync_with'].choices = (
                    (organisation['name'], '{} ({})'.format(
                        organisation['display_name'],
                        organisation.get(
                            'package_count',
                            organisation.get('packages', None))))
                    for organisation in organisations)

            mapping = []

            # Initialize categories mapping
            # =============================
            try:
                with CkanBaseHandler(instance.url) as ckan:
                    remote_categories = ckan.get_all_categories(all_fields=True)
            except CkanBaseError as e:
                logger.error(e)
            else:
                fields_name = []
                for remote_category in remote_categories:
                    field_name = ''.join(['cat_', remote_category['name']])
                    fields_name.append(field_name)
                    try:
                        filter = {'remote_ckan': instance, 'slug': field_name[4:]}
                        initial = MappingCategory.objects.filter(**filter).first().category
                    except Exception as e:
                        logger.warning(e)
                        try:
                            initial = Category.objects.get(slug=field_name[4:])
                        except Exception as e:
                            logger.warning(e)
                            initial = None

                    self.fields[field_name] = forms.ModelChoiceField(
                        label=remote_category['title'],
                        empty_label="Sélectionnez une valeur",
                        required=False,
                        queryset=Category.objects.all(),
                        initial=initial,
                        )

                mapping.append({
                    'name': 'Category',
                    'title': 'Categories',
                    'fields_name': fields_name,
                    })

            # Initialize licences mapping
            # ===========================
            try:
                with CkanBaseHandler(instance.url) as ckan:
                    remote_licenses = ckan.get_all_licenses(all_fields=True)
            except CkanBaseError as e:
                logger.error(e)
            else:
                fields_name = []
                for remote_license in remote_licenses:
                    field_name = ''.join(['lic_', remote_license['id']])
                    fields_name.append(field_name)
                    try:
                        filter = {'remote_ckan': instance, 'slug': field_name[4:]}
                        initial = MappingLicence.objects.filter(**filter).first().licence
                    except Exception as e:
                        logger.warning(e)
                        try:
                            initial = License.objects.get(slug=field_name[4:])
                        except Exception as e:
                            logger.warning(e)
                            initial = None

                    self.fields[field_name] = forms.ModelChoiceField(
                        label=remote_license['title'],
                        empty_label="Sélectionnez une valeur",
                        required=False,
                        queryset=License.objects.all(),
                        initial=initial,
                        )

                mapping.append({
                    'name': 'License',
                    'title': 'Licences',
                    'fields_name': fields_name,
                    })

        else:
            self.fields['sync_with'].widget = forms.HiddenInput()
            self.fields['sync_frequency'].widget = forms.HiddenInput()

    def get_category_fields(self):
        return [self[val] for val in self.fields if val.startswith('cat')]

    def get_licence_fields(self):
        return [self[val] for val in self.fields if val.startswith('lic')]


# ================================
# FORMULAIRE DE MOISSONNAGE DE CSW
# ================================


class RemoteCswForm(forms.ModelForm):

    class Meta(object):
        model = RemoteCsw
        fields = (
            'url',
            'getrecords',
            'sync_frequency',
            )

    url = forms.URLField(
        label="URL du CSW*",
        required=True,
        max_length=200,
        error_messages={
            'invalid': "L'adresse URL est erronée.",
            },
        widget=forms.TextInput(
            attrs={
                # 'placeholder': "https://demo.ckan.org",
                },
            ),
        )

    getrecords = forms.CharField(
        label="GetRecords*",
        required=False,
        widget=forms.Textarea(
            attrs={
                'class': 'code',
                'placeholder': '''<csw:GetRecords ...''',
                'rows': 24,
                },
            ),
        )

    sync_frequency = forms.ChoiceField(
        label="Fréquence de synchronisation*",
        required=False,
        choices=Meta.model.FREQUENCY_CHOICES,
        initial='never',
        )

    def __init__(self, *args, **kwargs):
        self.cleaned_data = {}
        super().__init__(*args, **kwargs)

        instance = kwargs.get('instance', None)
        if instance and instance.url:
            self.fields['url'].widget.attrs['readonly'] = True
            try:
                with CswBaseHandler(instance.url) as csw:
                    pass
            except CswBaseError as e:
                self.add_error('url', e.__str__())
        else:
            self.fields['getrecords'].widget = forms.HiddenInput()
            self.fields['sync_frequency'].widget = forms.HiddenInput()


# =================================
# FORMULAIRE DE MOISSONNAGE DE DCAT
# =================================


class RemoteDcatForm(forms.ModelForm):

    class Meta(object):
        model = RemoteDcat
        fields = (
            'url',
            'sync_frequency',
            )
        mapping = tuple()

    url = forms.URLField(
        label="URL du catalogue DCAT*",
        required=True,
        max_length=200,
        error_messages={
            'invalid': "L'adresse URL est erronée.",
            },
        widget=forms.TextInput(
            attrs={
                'placeholder': "",
                },
            ),
        )

    sync_frequency = forms.ChoiceField(
        label="Fréquence de synchronisation*",
        required=True,
        choices=Meta.model.FREQUENCY_CHOICES,
        initial='never',
        )

    def __init__(self, *args, **kwargs):
        self.cleaned_data = {}
        super().__init__(*args, **kwargs)

        instance = kwargs.get('instance', None)
        if instance and instance.url:
            self.fields['url'].widget.attrs['readonly'] = True

            # mapping = []
            #
            # Initialize categories mapping
            # =============================
            # try:
            #     with DcatBaseHandler(instance.url) as dcat:
            #         remote_categories = dcat.get_all_categories(all_fields=True)
            # except DcatBaseError as e:
            #     logger.error(e)
            # else:
            #     fields_name = []
            #     for remote_category in remote_categories:
            #         field_name = ''.join(['cat_', remote_category['name']])
            #         fields_name.append(field_name)
            #         try:
            #             filter = {'remote_ckan': instance, 'slug': field_name[4:]}
            #             initial = MappingCategory.objects.filter(**filter).first().category
            #         except Exception as e:
            #             logger.warning(e)
            #             try:
            #                 initial = Category.objects.get(slug=field_name[4:])
            #             except Exception as e:
            #                 logger.warning(e)
            #                 initial = None
            #
            #         self.fields[field_name] = forms.ModelChoiceField(
            #             label=remote_category['title'],
            #             empty_label="Sélectionnez une valeur",
            #             required=False,
            #             queryset=Category.objects.all(),
            #             initial=initial,
            #             )
            #
            #     mapping.append({
            #         'name': 'Category',
            #         'title': 'Categories',
            #         'fields_name': fields_name,
            #         })
            #
            # Initialize licences mapping
            # ===========================
            # try:
            #     with DcatBaseHandler(instance.url) as dcat:
            #         remote_licenses = dcat.get_all_licenses(all_fields=True)
            # except DcatBaseError as e:
            #     logger.error(e)
            # else:
            #     fields_name = []
            #     for remote_license in remote_licenses:
            #         field_name = ''.join(['lic_', remote_license['id']])
            #         fields_name.append(field_name)
            #         try:
            #             filter = {'remote_ckan': instance, 'slug': field_name[4:]}
            #             initial = MappingLicence.objects.filter(**filter).first().licence
            #         except Exception as e:
            #             logger.warning(e)
            #             try:
            #                 initial = License.objects.get(slug=field_name[4:])
            #             except Exception as e:
            #                 logger.warning(e)
            #                 initial = None
            #
            #         self.fields[field_name] = forms.ModelChoiceField(
            #             label=remote_license['title'],
            #             empty_label="Sélectionnez une valeur",
            #             required=False,
            #             queryset=License.objects.all(),
            #             initial=initial,
            #             )
            #
            #     mapping.append({
            #         'name': 'License',
            #         'title': 'Licences',
            #         'fields_name': fields_name,
            #         })

        else:
            self.fields['sync_frequency'].widget = forms.HiddenInput()

    # def get_category_fields(self):
    #     return [self[val] for val in self.fields if val.startswith('cat')]

    # def get_licence_fields(self):
    #     return [self[val] for val in self.fields if val.startswith('lic')]