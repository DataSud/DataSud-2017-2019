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


from api.utils import parse_request
from collections import OrderedDict
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db import transaction
from django.db.utils import IntegrityError
from django.http import Http404
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from functools import reduce
from idgo_admin.ckan_module import CkanHandler
from idgo_admin.exceptions import CkanBaseError
from idgo_admin.exceptions import GenericException
from idgo_admin.forms.account import SignUpForm
from idgo_admin.forms.account import UpdateAccountForm
from idgo_admin.models import AccountActions
from idgo_admin.models import LiaisonsContributeurs
from idgo_admin.models import LiaisonsReferents
from idgo_admin.models import Organisation
from idgo_admin.models import Profile
from operator import iand
from operator import ior
from rest_framework import permissions
from rest_framework.views import APIView


def serialize(user):

    def nullify(m):
        return m or None

    try:
        return OrderedDict([
            # Information de base sur l'utilisateur
            ('username', user.username),
            ('first_name', user.first_name),
            ('last_name', user.last_name),
            ('admin', user.profile.is_admin),
            ('crige', user.profile.crige_membership),
            # Organisation de rattachement de l'utilisateur
            ('organisation', user.profile.organisation and OrderedDict([
                ('name', user.profile.organisation.slug),
                ('legal_name', user.profile.organisation.legal_name)
                ]) or None),
            # Listes des organisations pour lesquelles l'utilisateur est référent
            ('referent', nullify([OrderedDict([
                ('name', organisation.slug),
                ('legal_name', organisation.legal_name)
                ]) for organisation in user.profile.referent_for])),
            # Listes des organisations pour lesquelles l'utilisateur est contributeur
            ('contribute', nullify([OrderedDict([
                ('name', organisation.slug),
                ('legal_name', organisation.legal_name)
                ]) for organisation in user.profile.contribute_for]))
            ])
    except Exception as e:
        if e.__class__.__name__ == 'RelatedObjectDoesNotExist':
            return None
        raise e


def user_list(order_by='last_name', or_clause=None, **and_clause):

    and_clause.update({'profile__pk__isnull': False})

    l1 = [Q(**{k: v}) for k, v in and_clause.items()]
    if or_clause:
        l2 = [Q(**{k: v}) for k, v in or_clause.items()]
        filter = ior(reduce(iand, l1), reduce(iand, l2))
    else:
        filter = reduce(iand, l1)

    return [serialize(user) for user in User.objects.filter(filter).order_by(order_by)]


def handler_get_request(request):
    qs = request.GET.dict()
    or_clause = dict()

    user = request.user
    if user.profile.is_admin:
        # Un administrateur « métiers » peut tout voir.
        pass
    elif user.profile.is_referent:
        # Un référent « métiers » peut voir les utilisateurs des
        # organisations pour lesquelles il est référent.
        qs.update({'profile__organisation__in': user.profile.referent_for})
        or_clause.update({'username': user.username})
    else:
        # L'utilisateur peut se voir lui même.
        qs.update({'username': user.username})

    return user_list(**qs)


def handle_pust_request(request, username=None):

    user = None
    if username:
        user = get_object_or_404(User, username=username)

    query_data = getattr(request, request.method)  # QueryDict

    # `first_name` est obligatoire
    first_name = query_data.pop('first_name', user and [user.first_name])
    if first_name:
        query_data.__setitem__('first_name', first_name[-1])

    # `last_name` est obligatoire
    last_name = query_data.pop('last_name', user and [user.last_name])
    if last_name:
        query_data.__setitem__('last_name', last_name[-1])

    # `email` est obligatoire
    email = query_data.pop('email', user and [user.email])
    if email:
        query_data.__setitem__('email', email[-1])

    # organisation
    organisation_slug = query_data.pop('organisation', None)
    if organisation_slug:
        try:
            organisation = Organisation.objects.get(slug=organisation_slug[-1])
        except Organisation.DoesNotExist as e:
            raise GenericException(details=e.__str__())
    elif user and user.profile:
        organisation = user.profile.organisation
    else:
        organisation = None
    if organisation:
        query_data.__setitem__('organisation', organisation.pk)

    password = query_data.pop('password', None)
    if password:
        query_data.__setitem__('password1', password[-1])
        query_data.__setitem__('password2', password[-1])

    if user:
        form = UpdateAccountForm(query_data, instance=user)
    else:
        form = SignUpForm(query_data, unlock_terms=True)
    if not form.is_valid():
        raise GenericException(details=form._errors)
    try:
        with transaction.atomic():
            if user:
                phone = form.cleaned_data.pop('phone', None)
                for k, v in form.cleaned_data.items():
                    if k == 'password':
                        # user.set_password(v)
                        pass
                    else:
                        setattr(user, k, v)
                user.save()
                if phone:
                    user.profile.phone = phone
                    user.profile.save
                CkanHandler.update_user(user)
            else:
                user = User.objects.create_user(**form.cleaned_user_data)
                profile_data = {**form.cleaned_profile_data, **{'user': user, 'is_active': True}}
                Profile.objects.create(**profile_data)
                CkanHandler.add_user(user, form.cleaned_user_data['password'], state='active')
    except (ValidationError, CkanBaseError) as e:
        raise GenericException(details=e.__str__())

    if organisation:
        user.profile.membership = True
        user.profile.save(update_fields=['membership'])

    # contribute
    contribute_for = None
    contribute_for_slugs = query_data.pop('contribute', [])
    if contribute_for_slugs:
        try:
            contribute_for = Organisation.objects.filter(slug__in=contribute_for_slugs)
        except Organisation.DoesNotExist as e:
            raise GenericException(details=e.__str__())

    # referent
    referent_for = None
    referent_for_slugs = query_data.pop('referent', None)
    if referent_for_slugs:
        try:
            referent_for = Organisation.objects.filter(slug__in=referent_for_slugs)
        except Organisation.DoesNotExist as e:
            raise GenericException(details=e.__str__())

    if contribute_for:
        for organisation in contribute_for:
            try:
                LiaisonsContributeurs.objects.get_or_create(
                    profile=user.profile, organisation=organisation,
                    defaults={'validated_on': timezone.now()}
                )
            except IntegrityError:
                pass
            else:
                AccountActions.objects.get_or_create(
                    action='confirm_contribution', organisation=organisation,
                    profile=user.profile, defaults={'closed': timezone.now()}
                )

    if referent_for:
        for organisation in referent_for:
            try:
                LiaisonsReferents.objects.get_or_create(
                    profile=user.profile, organisation=organisation,
                    defaults={'validated_on': timezone.now()})
            except IntegrityError:
                pass
            else:
                AccountActions.objects.get_or_create(
                    action='confirm_referent', organisation=organisation,
                    profile=user.profile, defaults={'closed': timezone.now()}
                )

    return user


class UserShow(APIView):

    permission_classes = [
        permissions.IsAuthenticated,
        ]

    def get(self, request, username):
        data = handler_get_request(request)
        for item in data:
            if item['username'] == username:
                return JsonResponse(item, safe=True)
        raise Http404()

    def put(self, request, username):
        """Mettre à jour un utilisateur."""
        request.PUT, request._files = parse_request(request)
        request.PUT._mutable = True
        if not request.user.profile.is_admin:
            raise Http404()
        try:
            handle_pust_request(request, username=username)
        except Http404:
            raise Http404()
        except GenericException as e:
            return JsonResponse({'error': e.details}, status=400)
        return HttpResponse(status=204)


class UserList(APIView):

    permission_classes = [
        permissions.IsAuthenticated,
        ]

    def get(self, request):
        if not hasattr(request.user, 'profile'):
            raise Http404()
        data = handler_get_request(request)
        return JsonResponse(data, safe=False)

    def post(self, request):
        """Créer un utilisateur."""
        request.POST._mutable = True
        if not request.user.profile.is_admin:
            raise Http404()
        try:
            user = handle_pust_request(request)
        except Http404:
            raise Http404()
        except GenericException as e:
            return JsonResponse({'error': e.details}, status=400)
        response = HttpResponse(status=201)
        response['Content-Location'] = user.profile.api_location
        return response
