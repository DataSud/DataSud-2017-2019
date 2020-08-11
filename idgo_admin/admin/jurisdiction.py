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
from idgo_admin.models import Jurisdiction
from idgo_admin.models import JurisdictionCommune


class JurisdictionCommuneTabularInline(admin.TabularInline):
    model = JurisdictionCommune
    can_delete = True
    can_order = True
    extra = 0
    verbose_name_plural = 'Communes rattachées au territoire de compétence'
    verbose_name = 'Commune rattachée au territoire de compétence'

    def name(self, obj):
        return obj.commune.name

    name.short_description = 'Nom'

    def code_insee(self, obj):
        return obj.commune.pk

    code_insee.short_description = 'Code INSEE'

    fields = ('commune', 'name', 'code_insee', )
    readonly_fields = ('name', 'code_insee', )


class JurisdictionCommuneTabularInlineReader(JurisdictionCommuneTabularInline):
    fields = ('name', 'code_insee', )
    readonly_fields = ('name', 'code_insee', )
    classes = ('collapse', )

    def has_add_permission(self, request, obj=None):
        return False


class JurisdictionCommuneTabularInlineAdder(JurisdictionCommuneTabularInline):
    extra = 1
    fields = ('commune', )

    def has_change_permission(self, request, obj=None):
        return False


class JurisdictionAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', )
    ordering = ('name', )
    search_fields = ('name', 'commune', )
    search_fields = ('name', 'code', )
    inlines = (JurisdictionCommuneTabularInlineReader,
               JurisdictionCommuneTabularInlineAdder, )


admin.site.register(Jurisdiction, JurisdictionAdmin)
