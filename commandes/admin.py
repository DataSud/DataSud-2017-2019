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


from commandes.actions import email_cadastre_habilitation
from commandes.actions import email_cadastre_wrong_files
from commandes.actions import export_as_csv_action
from commandes.models import Order
from datetime import datetime
from django.contrib import admin
from django.utils.html import format_html
# from django_admin_listfilter_dropdown.filters import DropdownFilter
# from django_admin_listfilter_dropdown.filters import RelatedDropdownFilter


# def send_email(modeladmin, request, queryset):
#     queryset.update(status='p')
# send_email.short_description = "Mark selected stories as published"

# filtre des commandes par année
class YearListFilter(admin.SimpleListFilter):

    title = ("année de la demande",)
    parameter_name = 'year'

    def lookups(self, _request, _model_admin):
        year = 2018
        years = []
        while datetime(year, 1, 1) < datetime.now():
            years.append(year)
            year += 1

        return [(year, str(year)) for year in years]

    def queryset(self, request, queryset):
        if self.value() is not None:
            return queryset.filter(date__year=self.value())


class OrderAdmin(admin.ModelAdmin):

    list_display = ('user_full_name', 'orga', 'email', 'date', 'terr', 'status',)
    raw_id_fields = ('applicant',)
    readonly_fields = ('orga',)
    list_filter = (YearListFilter, 'status',)

    # ajout de l'email de l'utilisateur
    def email(self, obj):
        return format_html('<a href=\"mailto:{0}\">{0}</a>'.format(obj.applicant.email))
    email.short_description = "E-mail"

    # ajout du nom du territoire de compétences

    def terr(self, obj):
        if obj:
            return obj.applicant.profile.organisation.jurisdiction
    terr.short_description = "Territoire de compétences"

    def orga(self, obj):
        if obj:
            return obj.applicant.profile.organisation
    orga.short_description = 'Organisation'
    orga.admin_order_field = 'applicant__profile__organisation'

    def user_full_name(self, obj):
        if obj:
            return obj.applicant.first_name + ' ' + obj.applicant.last_name
    user_full_name.short_description = 'Demandeur'
    user_full_name.admin_order_field = 'applicant__last_name'
    # action d'export en csv
    actions = [
        export_as_csv_action("Export CSV"),
        email_cadastre_wrong_files,
        email_cadastre_habilitation]

    export_as_csv_action.short_description = "Exporter en CSV"
    email_cadastre_wrong_files.short_description = "E-mail documents invalides"
    email_cadastre_habilitation.short_description = "E-mail pas d'habilitation"
    ordering = ('applicant__profile__organisation', 'applicant__last_name',)


admin.site.register(Order, OrderAdmin)
