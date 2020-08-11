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


from django.http import JsonResponse
from ihm.models import IHMSettings
from rest_framework import permissions
from rest_framework.views import APIView


class CkanIHMSettings(APIView):

    permission_classes = [
        permissions.IsAuthenticatedOrReadOnly,
        ]

    def get(self, request):
        data = dict([
            (settings.name, {
                'content': settings.contents,
                'active': settings.activate,
                }) for settings in IHMSettings.objects.filter(target='ckan')
            ])
        return JsonResponse(data, safe=False)
