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


from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


TERMS_URL = settings.TERMS_URL


class TermsRequired(object):

    IGNORE_PATH = (
        # IMPORTANT, sinon le service redirige en boucle sur cette page
        reverse(settings.TERMS_URL),
        # Un utilisateur doit pouvoir se connecter et se déconnecter
        reverse(settings.LOGIN_URL),
        reverse(settings.LOGOUT_URL),
        )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user

        # L'utilisateur doit avoir un profil associé
        # Les administrateurs ne sont pas concernés
        # Les utilisateurs ayant déjà validés les conditions ne sont pas concernés
        if request.path not in self.IGNORE_PATH \
                and hasattr(user, 'profile') \
                and not user.profile.is_admin \
                and not user.profile.is_agree_with_terms:
            return redirect(reverse(settings.TERMS_URL))

        response = self.get_response(request)
        return response
