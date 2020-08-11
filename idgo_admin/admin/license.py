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
from django.contrib.admin.utils import get_deleted_objects
from django.db import router
from django import forms
from idgo_admin.models import License


class LicenseAdminForm(forms.ModelForm):

    class Meta(object):
        model = License
        fields = '__all__'
        widgets = {
            'alternate_titles': forms.Textarea(),
            'alternate_urls': forms.Textarea(),
            }


class LicenseAdmin(admin.ModelAdmin):
    form = LicenseAdminForm
    list_display = ('title', 'alternate_titles',)
    ordering = ('title',)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def has_delete_permission(self, request, obj=None):
        if obj:
            # Ici on récupere brutalement les objets suscebtibles d'etre supprimés
            # si on aurai supprimé l'instance courante
            opts = self.model._meta
            using = router.db_for_write(self.model)
            (deleted_objects, model_count, perms_needed, protected) = get_deleted_objects(
                [obj], opts, request.user, self.admin_site, using)
            # Si on ne retrouve uniquement que l'instance courante parmis
            # les objets a supprimés alors on autorise.
            if len(deleted_objects) == 1:
                return True

        return False


admin.site.register(License, LicenseAdmin)
