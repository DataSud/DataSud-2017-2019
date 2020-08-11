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
from idgo_admin.models import Granularity


class GranularityAdmin(admin.ModelAdmin):
    # actions = None
    # list_display = ('slug', 'name')
    # readonly_fields = ('slug', 'name')
    # list_display_links = None

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    # def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
    #     extra_context = extra_context or {}
    #     extra_context['show_save_and_continue'] = False
    #     extra_context['show_save'] = False
    #     return super().changeform_view(request, object_id, extra_context=extra_context)


admin.site.register(Granularity, GranularityAdmin)
