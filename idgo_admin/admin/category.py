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
from django import forms
from idgo_admin.models import Category


class CategoryAdminForm(forms.ModelForm):

    class Meta(object):
        model = Category
        fields = '__all__'
        widgets = {
            'alternate_titles': forms.Textarea(),
            }


class CategoryAdmin(admin.ModelAdmin):
    form = CategoryAdminForm
    model = Category
    list_display = ('name', 'iso_topic', 'alternate_titles',)
    readonly_fields = ('slug',)
    ordering = ('name',)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions


admin.site.register(Category, CategoryAdmin)
