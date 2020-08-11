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
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.shortcuts import reverse
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.exceptions import ProfileHttp404
from idgo_admin.models import AccountActions
from idgo_admin.models import LiaisonsContributeurs
from idgo_admin.models import LiaisonsReferents
from idgo_admin.models import Profile
from idgo_admin.models import Resource


CKAN_URL = settings.CKAN_URL
CRIGE_URL = settings.CRIGE_URL
WORDPRESS_URL = settings.WORDPRESS_URL
READTHEDOC_URL = settings.READTHEDOC_URL
DEFAULT_CONTACT_EMAIL = settings.DEFAULT_CONTACT_EMAIL
DEFAULT_PLATFORM_NAME = settings.DEFAULT_PLATFORM_NAME
FTP_URL = settings.FTP_URL


def on_profile_http404():
    return HttpResponseRedirect(reverse('server_cas:signIn'))


@ExceptionsHandler(actions={ProfileHttp404: on_profile_http404})
def render_with_info_profile(
        request, template_name, context=None,
        content_type=None, status=None, using=None, *args, **kwargs):

    user, profile = user_and_profile(request)

    if not context:
        context = {}

    # organisation = (profile.organisation and profile.membership) and profile.organisation

    # try:
    #     action = AccountActions.objects.get(
    #         action='confirm_rattachement', profile=profile, closed__isnull=True)
    # except Exception:
    #     awaiting_member_status = []
    # else:
    #     awaiting_member_status = action.organisation \
    #         and [action.organisation.id, action.organisation.legal_name]

    contributor = [
        [c.id, c.legal_name] for c
        in LiaisonsContributeurs.get_contribs(profile=profile)]

    # awaiting_contributor_status = [
    #     [c.id, c.legal_name] for c
    #     in LiaisonsContributeurs.get_pending(profile=profile)]

    referent = [
        [c.id, c.legal_name] for c
        in LiaisonsReferents.get_subordinated_organisations(profile=profile)]

    # awaiting_referent_statut = [
    #     [c.id, c.legal_name] for c
    #     in LiaisonsReferents.get_pending(profile=profile)]

    context.update({
        'contact_email': DEFAULT_CONTACT_EMAIL,
        'platform_name': DEFAULT_PLATFORM_NAME,
        'ftp_url': FTP_URL,
        'doc_url': READTHEDOC_URL,
        'wordpress_url': WORDPRESS_URL,
        'crige_url': CRIGE_URL,
        'ckan_url': CKAN_URL,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'is_crige': profile.crige_membership,
        'is_membership': profile.membership,
        'is_referent': profile.get_roles()['is_referent'],
        'is_contributor': len(contributor) > 0,
        'is_admin': profile.is_admin,
        # 'organisation': organisation,
        # 'awaiting_member_status': awaiting_member_status,
        'contributor': contributor,
        # 'awaiting_contributor_status': awaiting_contributor_status,
        'referent': referent,
        # 'awaiting_referent_statut': awaiting_referent_statut,
        })

    return render(request, template_name, context=context,
                  content_type=content_type, status=status, using=using)


def get_object_or_404_extended(MyModel, user, include):
    res = None
    profile = get_object_or_404(Profile, user=user)
    instance = get_object_or_404(MyModel, **include)

    i_am_resource = (MyModel.__name__ == Resource.__name__)
    dataset = instance.dataset if i_am_resource else instance

    is_referent = dataset.is_referent(profile)
    is_contributor = dataset.is_contributor(profile)
    is_editor = dataset.editor == profile.user

    if profile.is_admin or is_referent:
        res = instance
    if is_contributor and is_editor:
        res = instance

    if not res:
        raise PermissionDenied
    return res


def user_and_profile(request):
    user = request.user
    res = None, None
    if user.is_anonymous:
        raise ProfileHttp404
    try:
        profile = get_object_or_404(Profile, user=user)
    except Exception:
        raise ProfileHttp404
    else:
        res = user, profile
    return res
