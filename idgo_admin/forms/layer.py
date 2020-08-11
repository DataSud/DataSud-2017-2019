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
from idgo_admin.forms.fields import DescriptionField
from idgo_admin.models import Layer


class LayerForm(forms.ModelForm):

    class Meta(object):
        model = Layer
        fields = '__all__'

    title = forms.CharField(
        label="Titre (tel qu'il apparaîtra sur le service cartographique OGC)")

    abstract = DescriptionField(
        label='Description du jeu de données')

    def __init__(self, *args, **kwargs):
        include = kwargs.pop('include', {})
        super().__init__(*args, **kwargs)

        self.fields['title'].initial = self.instance.title
        self.fields['abstract'].initial = self.instance.abstract

    def clean(self):
        return self.cleaned_data
