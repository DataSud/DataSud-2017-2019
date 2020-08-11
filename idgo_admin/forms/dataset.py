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
from django import forms
from django.forms.models import ModelChoiceIterator
from django.utils import timezone
from idgo_admin.models import Category
from idgo_admin.models import Dataset
from idgo_admin.models import DataType
from idgo_admin.models import Granularity
from idgo_admin.models import License
from idgo_admin.models import Organisation
from idgo_admin.models import Support
import re
from taggit.forms import TagField
from taggit.forms import TagWidget


CKAN_URL = settings.CKAN_URL
DEFAULT_CONTACT_EMAIL = settings.DEFAULT_CONTACT_EMAIL
DEFAULT_PLATFORM_NAME = settings.DEFAULT_PLATFORM_NAME
DOMAIN_NAME = settings.DOMAIN_NAME
GEONETWORK_URL = settings.GEONETWORK_URL
TODAY = timezone.now().date().strftime('%d/%m/%Y')


# Définition de DatatypeField
# ===========================


class DatatypeModelIterator(ModelChoiceIterator):
    def __iter__(self):
        if self.field.empty_label is not None:
            yield ("", self.field.empty_label)
        queryset = self.queryset
        if not queryset._prefetch_related_lookups:
            queryset = queryset.iterator()
        for obj in queryset:
            if obj.slug == 'donnees-moissonnees':
                continue
            yield self.choice(obj)


class DatatypeModelMultipleChoiceField(forms.ModelMultipleChoiceField):
    iterator = DatatypeModelIterator


class DatatypeField(DatatypeModelMultipleChoiceField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('label', "Type de données")
        kwargs.setdefault('required', False)
        kwargs.setdefault('widget', forms.CheckboxSelectMultiple())
        kwargs.setdefault('queryset', DataType.objects.all())
        super().__init__(*args, **kwargs)


# ========================================
# Formulaire d'édition d'un jeu de données
# ========================================


class DatasetForm(forms.ModelForm):

    class Meta(object):
        model = Dataset
        fields = (
            'broadcaster_email',
            'broadcaster_name',
            'categories',
            'data_type',
            'date_creation',
            'date_modification',
            'date_publication',
            'description',
            'geocover',
            'granularity',
            'keywords',
            'license',
            'organisation',
            'owner_email',
            'owner_name',
            'published',
            'support',
            'thumbnail',
            'update_frequency',
            'title',
            'slug')

    title = forms.CharField(
        label="Titre*",
        required=True,
        widget=forms.Textarea(
            attrs={
                'placeholder': "Titre de votre jeu de données",
                'rows': 1,
                },
            ),
        )

    slug = forms.CharField(
        label="URL du jeu de données",
        required=False,
        max_length=100,
        widget=forms.TextInput(
            attrs={
                'addon_before': '{}/dataset/'.format(CKAN_URL),
                'addon_before_class': 'input-group-addon',
                'addon_after': '<button class="btn btn-default" type="button" />',
                'addon_after_class': 'input-group-btn',
                'autocomplete': 'off',
                'readonly': True,
                'placeholder': '',
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

    class CustomClearableFileInput(forms.ClearableFileInput):
        template_name = 'idgo_admin/widgets/file_drop_zone.html'

    thumbnail = forms.FileField(
        label="Illustration",
        required=False,
        widget=CustomClearableFileInput(
            attrs={
                'value': None,
                'max_size_info': 1048576,
                },
            ),
        )

    keywords = TagField(
        label="Liste de mots-clés",
        required=False,
        widget=TagWidget(
            attrs={
                'autocomplete': 'off',
                'class': 'typeahead',
                'placeholder': "Utilisez la virgule comme séparateur",
                },
            ),
        )

    categories = forms.ModelMultipleChoiceField(
        label="Catégories (sélectionnez dans la liste ci-dessous une ou plusieurs catégories)",
        required=False,
        queryset=Category.objects.all(),
        widget=forms.CheckboxSelectMultiple(),
        )

    date_creation = forms.DateField(
        label="Date de création",
        required=False,
        widget=forms.DateInput(
            attrs={
                'autocomplete': 'off',
                'class': 'datepicker',
                'placeholder': "{0} (par défaut)".format(TODAY),
                },
            ),
        )

    date_modification = forms.DateField(
        label="Date de dernière modification",
        required=False,
        widget=forms.DateInput(
            attrs={
                'autocomplete': 'off',
                'class': 'datepicker',
                'placeholder': "{0} (par défaut)".format(TODAY),
                },
            ),
        )

    date_publication = forms.DateField(
        label="Date de publication",
        required=False,
        widget=forms.DateInput(
            attrs={
                'autocomplete': 'off',
                'class': 'datepicker',
                'placeholder': "{0} (par défaut)".format(TODAY),
                },
            ),
        )

    update_frequency = forms.ChoiceField(
        label="Fréquence de mise à jour",
        required=False,
        choices=Dataset.FREQUENCY_CHOICES,
        )

    geocover = forms.ChoiceField(
        label="Couverture géographique",
        required=False,
        choices=Dataset.GEOCOVER_CHOICES,
        )

    granularity = forms.ModelChoiceField(
        label="Granularité de la couverture territoriale",
        empty_label="Sélectionnez une valeur",
        required=False,
        queryset=Granularity.objects.all().order_by('order'),
        )

    organisation = forms.ModelChoiceField(
        label="Organisation à laquelle est rattaché ce jeu de données*",
        empty_label="Sélectionnez une organisation",
        required=True,
        queryset=Organisation.objects.all(),
        )

    license = forms.ModelChoiceField(
        label="Licence*",
        empty_label="Sélectionnez une licence",
        required=True,
        queryset=License.objects.all(),
        )

    support = forms.ModelChoiceField(
        label="Support technique",
        empty_label="Aucun",
        required=False,
        queryset=Support.objects.all(),
        )

    data_type = DatatypeField(
        # Cf. définition plus haut
        )

    owner_name = forms.CharField(
        label="Nom du producteur",
        required=False,
        )

    owner_email = forms.EmailField(
        label="Adresse e-mail du producteur",
        required=False,
        error_messages={
            'invalid': "L'adresse e-mail est invalide.",
            },
        )

    broadcaster_name = forms.CharField(
        label="Nom du diffuseur",
        required=False,
        )

    broadcaster_email = forms.EmailField(
        label="Adresse e-mail du diffuseur",
        required=False,
        error_messages={
            'invalid': "L'adresse e-mail est invalide.",
            },
        )

    published = forms.BooleanField(
        label="Publier le jeu de données",
        required=False,
        initial=True,
        )

    def __init__(self, *args, **kwargs):
        self.include_args = kwargs.pop('include', {})
        super().__init__(*args, **kwargs)

        instance = kwargs.get('instance', None)
        owner = instance \
            and instance.editor or self.include_args.get('user')

        self.fields['organisation'].queryset = Organisation.objects.filter(
            liaisonscontributeurs__profile=owner.profile,
            liaisonscontributeurs__validated_on__isnull=False)

        self.fields['owner_name'].initial = owner.get_full_name()
        self.fields['owner_name'].widget.attrs['placeholder'] = \
            '{} (valeur par défaut)'.format(owner.get_full_name())

        self.fields['owner_email'].initial = owner.email
        self.fields['owner_email'].widget.attrs['placeholder'] = \
            '{} (valeur par défaut)'.format(owner.email)

        self.fields['broadcaster_name'].widget.attrs['placeholder'] = \
            instance and instance.support and instance.support.name or DEFAULT_PLATFORM_NAME
        self.fields['broadcaster_email'].widget.attrs['placeholder'] = \
            instance and instance.support and instance.support.email or DEFAULT_CONTACT_EMAIL

        if instance and instance.thumbnail:
            self.fields['thumbnail'].widget.attrs['value'] = instance.thumbnail.url

        if not instance:
            self.fields['granularity'].initial = 'indefinie'

    def clean(self):

        title = self.cleaned_data.get('title')

        if self.cleaned_data.get('slug') \
                and not re.match('^[a-z0-9\-]{1,100}$', self.cleaned_data.get('slug')):
            self.add_error('slug', (
                "Seuls les caractères alphanumériques et le tiret sont "
                "autorisés (100 caractères maximum)."))
            raise ValidationError('KeywordsError')

        if self.include_args['identification']:
            dataset = Dataset.objects.get(id=self.include_args['id'])
            if title != dataset.title and Dataset.objects.filter(title=title).exists():
                self.add_error('title', 'Ce nom est réservé.')
                raise ValidationError("Dataset '{0}' already exists".format(title))

        if not self.include_args['identification'] \
                and Dataset.objects.filter(title=title).exists():
            self.add_error('title', 'Le jeu de données "{0}" existe déjà'.format(title))
            raise ValidationError("Dataset '{0}' already exists".format(title))

        kwords = self.cleaned_data.get('keywords')
        if kwords:
            for w in kwords:
                if len(w) < 2:
                    self.add_error('keywords', "La taille minimum pour un mot clé est de 2 caractères. ")
                    raise ValidationError("KeywordsError")
                regex = '^[a-zA-Z0-9áàâäãåçéèêëíìîïñóòôöõúùûüýÿæœÁÀÂÄÃÅÇÉÈÊËÍÌÎÏÑÓÒÔÖÕÚÙÛÜÝŸÆŒ\._\-\s]*$'
                if not re.match(regex, w):
                    self.add_error('keywords', "Les mots-clés ne peuvent pas contenir de caractères spéciaux. ")
                    raise ValidationError('KeywordsError')

        return self.cleaned_data
