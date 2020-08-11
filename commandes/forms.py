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


from commandes.models import Order
from django import forms
from django.utils import timezone
from idgo_admin.models import Organisation
from idgo_admin.models import Profile


class CustomClearableFileInput(forms.ClearableFileInput):
    template_name = 'idgo_admin/widgets/file_drop_zone.html'


class OrderForm(forms.ModelForm):

    dpo_cnil = forms.FileField(
        label="Déclaration CNIL désignant le DPO de l'organisation *",
        required=True,
        widget=CustomClearableFileInput(attrs={'value': None}))

    acte_engagement = forms.FileField(
        label="Acte d'engagement DGFIP*",
        required=True,
        widget=CustomClearableFileInput(attrs={'value': None}))

    class Meta(object):
        model = Order
        fields = [
            'dpo_cnil',
            'acte_engagement']

    def __init__(self, *args, **kwargs):
        """
        recupere l'identifiant du user depuis view.py récuperer
        l'organisation
        """
        self.user = kwargs.pop('user', None)
        super(OrderForm, self).__init__(*args, **kwargs)

    def clean(self):
        """
        checks if the user has already ordered files
        (order status = 'validée') in the current year
        """
        cleaned_data = super(OrderForm, self).clean()

        year = timezone.now().date().year

        organisation = Organisation.objects.get(id=Profile.objects.get(user_id=self.user).organisation_id)

        match = Order.objects.filter(
                date__year=year,
                organisation=organisation,
                status=1
                )

        er_mess = ("Une demande a déjà été approuvée pour cette organisation"
                    " dans l'année civile en cours.")

        if (match):
            # self.add_error('__all__',er_mess)
            raise forms.ValidationError(er_mess)
        else:
            return cleaned_data
