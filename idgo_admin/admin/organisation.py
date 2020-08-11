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


from django.contrib import admin
from django.contrib.gis import admin as geo_admin
from django import forms
from idgo_admin.models.mail import sender as mail_sender
from idgo_admin.models import Organisation
from idgo_admin.models import OrganisationType


geo_admin.GeoModelAdmin.default_lon = 160595
geo_admin.GeoModelAdmin.default_lat = 5404331
geo_admin.GeoModelAdmin.default_zoom = 14


def send_email_to_crige_membership(modeladmin, request, queryset):
    for organisation in queryset:
        if not organisation.is_crige_partner:
            continue
        for user in organisation.get_crige_membership():
            mail_sender(
                'inform_user_he_is_crige',
                to=[user.email],
                full_name=user.get_full_name(),
                username=user.username)


class OrganisationForm(forms.ModelForm):

    class Meta(object):
        model = Organisation
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['is_active'].initial = True

    def clean(self):
        for k, v in self.cleaned_data.items():
            if v == '':
                self.cleaned_data[k] = None
        return self.cleaned_data


class OrganisationAdmin(geo_admin.OSMGeoAdmin):
    list_display = ['legal_name', 'organisation_type']
    search_fields = ['legal_name']
    list_filter = ['organisation_type']
    ordering = ['legal_name']
    readonly_fields = ['slug']
    form = OrganisationForm
    actions = (
        send_email_to_crige_membership,
        )

    send_email_to_crige_membership.short_description = \
        'Envoyer e-mail aux utilisateurs CRIGE'

    def get_form(self, request, obj=None, **kwargs):
        if not request.user.is_superuser and not request.user.profile.is_crige_admin:
            self.form._meta.exclude = ['is_crige_partner']
        return super().get_form(request, obj, **kwargs)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions


class OrganisationTypeAdmin(admin.ModelAdmin):
    ordering = ['name']
    search_fields = ['name', 'code']


admin.site.register(Organisation, OrganisationAdmin)
admin.site.register(OrganisationType, OrganisationTypeAdmin)
