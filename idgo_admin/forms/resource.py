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
from django.db.models import BooleanField
from django.db.models import Case
from django.db.models import Value
from django.db.models import When
from django import forms
from django.forms.models import ModelChoiceIterator
from idgo_admin.forms.fields import CustomCheckboxSelectMultiple
from idgo_admin.models import Organisation
from idgo_admin.models import Profile
from idgo_admin.models import Resource
from idgo_admin.models import ResourceFormats
from idgo_admin.models import SupportedCrs
from idgo_admin.utils import readable_file_size
import os


try:
    DOWNLOAD_SIZE_LIMIT = settings.DOWNLOAD_SIZE_LIMIT
except AttributeError:
    DOWNLOAD_SIZE_LIMIT = 104857600  # 100Mio


FTP_DIR = settings.FTP_DIR
try:
    FTP_UPLOADS_DIR = settings.FTP_UPLOADS_DIR
except AttributeError:
    FTP_UPLOADS_DIR = 'uploads'


def file_size(value):
    size_limit = DOWNLOAD_SIZE_LIMIT
    if value.size > size_limit:
        message = \
            'Le fichier {0} ({1}) dépasse la limite de taille autorisée {2}.'.format(
                value.name, readable_file_size(value.size), readable_file_size(size_limit))
        raise ValidationError(message)


class FormatTypeSelect(forms.Select):

    @staticmethod
    def _choice_has_empty_value(choice):
        """Return True if the choice's value is empty string or None."""
        value, _, extension = choice
        return value is None or value == ''

    def optgroups(self, name, value, attrs=None):
        """Return a list of optgroups for this widget."""
        groups = []
        has_selected = False

        for index, (option_value, option_label, option_extension) in enumerate(self.choices):
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
                choices = [(option_value, option_label, option_extension)]
            groups.append((group_name, subgroup, index))

            for subvalue, sublabel, subextra in choices:
                selected = (
                    str(subvalue) in value and
                    (not has_selected or self.allow_multiple_selected))

                has_selected |= selected
                subgroup.append(
                    self.create_option(
                        name, subvalue, sublabel, selected, index,
                        subindex=subindex, extension=option_extension))
                if subindex is not None:
                    subindex += 1
        return groups

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None, extension=None):
        result = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        if extension:
            result['attrs']['extension'] = extension
        return result


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
            obj.extension.lower() == obj.ckan_format.lower() and obj.extension or '')


class ModelFormatTypeField(forms.ModelChoiceField):
    iterator = ModelOrganisationIterator


class ResourceForm(forms.ModelForm):

    class Meta(object):
        model = Resource
        fields = (
            'crs',
            'data_type',
            'description',
            'dl_url',
            'encoding',
            'extractable',
            'format_type',
            'ftp_file',
            'geo_restriction',
            'lang',
            'title',
            'ogc_services',
            'organisations_allowed',
            'profiles_allowed',
            'referenced_url',
            'restricted_level',
            'sync_frequency',
            'synchronisation',
            'up_file',
            )
        fake = (
            'sync_frequency_dl',
            'sync_frequency_ftp',
            'synchronisation_dl',
            'synchronisation_ftp',
            )

    class CustomClearableFileInput(forms.ClearableFileInput):
        template_name = 'idgo_admin/widgets/file_drop_zone.html'

    up_file = forms.FileField(
        required=False,
        validators=[file_size],
        widget=CustomClearableFileInput(
            attrs={
                'value': '',  # IMPORTANT
                'max_size_info': DOWNLOAD_SIZE_LIMIT,
                },
            ),
        )

    dl_url = forms.CharField(
        label="Veuillez indiquer l'URL d'un fichier à télécharger :",
        required=False,
        widget=forms.TextInput(
            attrs={
                'value': '',  # IMPORTANT
                'placeholder': "https://...",
                },
            ),
        )

    referenced_url = forms.CharField(
        label="Veuillez indiquer l'URL d'un jeu de données à référencer :",
        required=False,
        widget=forms.TextInput(
            attrs={
                'value': '',  # IMPORTANT
                'placeholder': "https://...",
                },
            ),
        )

    ftp_file = forms.ChoiceField(
        label="Les fichiers que vous avez déposés sur votre compte FTP apparaîssent dans la liste ci-dessous :",
        required=False,
        choices=[],
        )

    synchronisation_dl = forms.BooleanField(
        label="Synchroniser les données",
        required=False,
        initial=False,
        )

    sync_frequency_dl = forms.ChoiceField(
        label="Fréquence de synchronisation",
        required=False,
        initial='never',
        choices=Meta.model.FREQUENCY_CHOICES,
        widget=forms.Select(
            attrs={
                'class': 'disabled',
                'disabled': True,
                },
            ),
        )

    synchronisation_ftp = forms.BooleanField(
        label="Synchroniser les données",
        required=False,
        initial=False,
        )

    sync_frequency_ftp = forms.ChoiceField(
        label="Fréquence de synchronisation",
        required=False,
        initial='never',
        choices=Meta.model.FREQUENCY_CHOICES,
        widget=forms.Select(
            attrs={
                'class': 'disabled',
                'disabled': True,
                },
            ),
        )

    title = forms.CharField(
        label='Titre*',
        required=True,
        widget=forms.TextInput(
            attrs={
                'placeholder': "Titre",
                },
            ),
        )

    description = forms.CharField(
        label="Description",
        required=False,
        widget=forms.Textarea(
            attrs={
                'placeholder': "Vous pouvez utiliser le langage Markdown ici",
                },
            ),
        )

    data_type = forms.ChoiceField(
        label="Type",
        required=True,
        choices=Meta.model.TYPE_CHOICES,
        )

    format_type = ModelFormatTypeField(
        label="Format*",
        empty_label="Sélectionnez un format",
        required=True,
        queryset=ResourceFormats.objects.all().order_by('extension'),
        widget=FormatTypeSelect(),
        )

    crs = forms.ModelChoiceField(
        label="Système de coordonnées du jeu de données géographiques",
        required=False,
        queryset=SupportedCrs.objects.all(),
        to_field_name='auth_code',
        )

    encoding = forms.CharField(
        label="Encodage des données (« UTF-8 » par défaut)",
        required=False,
        widget=forms.TextInput(
            attrs={
                'placeholder': "Par exemple: Latin1, ISO_8859-1, etc.",
                },
            ),
        )

    restricted_level = forms.ChoiceField(
        label="Restriction d'accès",
        required=True,
        choices=Meta.model.LEVEL_CHOICES,
        )

    profiles_allowed = forms.ModelMultipleChoiceField(
        label="Utilisateurs autorisés",
        required=False,
        queryset=Profile.objects.filter(is_active=True).order_by('user__last_name'),
        to_field_name='pk',
        widget=CustomCheckboxSelectMultiple(
            attrs={
                'class': "list-group-checkbox",
                },
            ),
        )

    organisations_allowed = forms.ModelMultipleChoiceField(
        label="Organisations autorisées",
        required=False,
        queryset=Organisation.objects.filter(is_active=True).order_by('slug'),
        to_field_name='pk',
        widget=CustomCheckboxSelectMultiple(
            attrs={
                'class': "list-group-checkbox",
                },
            ),
        )

    geo_restriction = forms.BooleanField(
        label="Restreindre l'accès au territoire de compétence",
        required=False,
        # initial=False,
        )

    extractable = forms.BooleanField(
        label="Activer le service d'extraction des données géographiques",
        required=False,
        # initial=True,
        )

    ogc_services = forms.BooleanField(
        label="Activer les services OGC associés",
        required=False,
        # initial=True,
        )

    def __init__(self, *args, **kwargs):
        self.include_args = kwargs.pop('include', {})
        self._dataset = kwargs.pop('dataset', None)
        instance = kwargs.get('instance', None)
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        dir = os.path.join(FTP_DIR, user.username, FTP_UPLOADS_DIR)
        choices = [(None, 'Veuillez sélectionner un fichier')]
        for path, subdirs, files in os.walk(dir):
            for name in files:
                filename = os.path.join(path, name)
                choices.append((filename, filename[len(dir) + 1:]))
        self.fields['ftp_file'].choices = choices

        if user.profile.is_admin:
            choices = self.Meta.model.EXTRA_FREQUENCY_CHOICES + self.Meta.model.FREQUENCY_CHOICES
            self.fields['sync_frequency_ftp'].choices = choices
            self.fields['sync_frequency_dl'].choices = choices

        if instance:

            related_profiles = Case(
                When(pk__in=[m.pk for m in instance.profiles_allowed.all()], then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
                )
            self.fields['profiles_allowed'].queryset = \
                Profile.objects.annotate(related=related_profiles).order_by('-related', 'user__username')

            related_organisations = Case(
                When(pk__in=[m.pk for m in instance.organisations_allowed.all()], then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
                )
            self.fields['organisations_allowed'].queryset = \
                Organisation.objects.annotate(related=related_organisations).order_by('-related', 'slug')

            if instance.up_file:
                self.fields['up_file'].widget.attrs['value'] = instance.up_file
            elif instance.ftp_file:
                self.fields['synchronisation_ftp'].initial = instance.synchronisation
                self.fields['sync_frequency_ftp'].initial = instance.sync_frequency
                try:
                    instance.ftp_file.file
                except FileNotFoundError:
                    self.fields['ftp_file'] = forms.CharField(
                        label="Fichier initialement déposé sur votre compte FTP (ce fichier n'est plus détecté) :",
                        required=False,
                        widget=forms.TextInput(
                            attrs={
                                'class': 'disabled',
                                'disabled': True,
                                },
                            ),
                        )
            elif instance.dl_url:
                self.fields['synchronisation_dl'].initial = instance.synchronisation
                self.fields['sync_frequency_dl'].initial = instance.sync_frequency

    def clean(self):

        res_l = {
            'up_file': self.cleaned_data.get('up_file') or None,
            'dl_url': self.cleaned_data.get('dl_url') or None,
            'referenced_url': self.cleaned_data.get('referenced_url') or None,
            'ftp_file': self.cleaned_data.get('ftp_file') or None,
            }

        self.cleaned_data['synchronisation'] = \
            self.cleaned_data.get('synchronisation_ftp') or self.cleaned_data['synchronisation_dl']
        self.cleaned_data['sync_frequency'] = \
            self.cleaned_data['sync_frequency_ftp'] or self.cleaned_data['sync_frequency_dl']
        del self.cleaned_data['synchronisation_dl']
        del self.cleaned_data['synchronisation_ftp']
        del self.cleaned_data['sync_frequency_dl']
        del self.cleaned_data['sync_frequency_ftp']

        if all(v is None for v in list(res_l.values())):
            for field in list(res_l.keys()):
                self.add_error(field, 'Ce champ est obligatoire.')

        if sum(v is not None for v in list(res_l.values())) > 1:
            error_msg = "Un seul type de ressource n'est autorisé."
            for k, v in res_l.items():
                if v:
                    self.add_error(k, error_msg)

        return self.cleaned_data
