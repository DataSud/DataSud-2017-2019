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
from idgo_admin.forms.fields import CustomCheckboxSelectMultiple
from idgo_admin.forms.fields import InputTypeahead
from idgo_admin.models import Commune
from idgo_admin.models import Jurisdiction


class JurisdictionForm(forms.ModelForm):

    class Meta(object):
        model = Jurisdiction
        property_fields = ('name', 'code',)
        fields = property_fields + ('communes',)

    name = forms.CharField(
        label="Nom*",
        widget=forms.TextInput(
            attrs={
                'placeholder': "Le nom du territoire",
                },
            )
        )

    code = forms.CharField(
        label="Code d'identification*",
        widget=forms.TextInput(
            attrs={
                'placeholder': "Par exemple le code INSEE",
                },
            )
        )

    communes = forms.ModelMultipleChoiceField(
        label="Communes",
        queryset=Commune.objects.all(),
        required=False,
        to_field_name='code',
        widget=CustomCheckboxSelectMultiple(
            attrs={
                'class': 'list-group-checkbox',
                },
            )
        )

    jurisdiction = forms.ModelChoiceField(
        label="Rechercher un territoire existant",
        queryset=Jurisdiction.objects.all(),
        required=False,
        empty_label=None,
        widget=InputTypeahead(
            attrs={
                'placeholder': "Aucun",
                }
            ),
        )

    prefill = forms.BooleanField(
        label=None,
        initial=False,
        required=False,
        widget=forms.HiddenInput(),
        )

    def __init__(self, *args, **kwargs):
        include = kwargs.pop('include', {})
        super().__init__(*args, **kwargs)

        if self.instance.pk:
            del self.fields['jurisdiction']
            del self.fields['prefill']
        else:
            self.fields['name'].required = False
            self.fields['code'].required = False

    def clean(self):
        if self.cleaned_data.get('jurisdiction'):
            self.cleaned_data['prefill'] = True
        return self.cleaned_data
