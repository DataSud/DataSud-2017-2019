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
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db import transaction
from django.http import Http404
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from functools import reduce
from idgo_admin.ckan_module import CkanHandler
from idgo_admin.exceptions import CkanBaseError
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.exceptions import ProfileHttp404
from idgo_admin.forms.dataset import DatasetForm as Form
from idgo_admin.models import Category
from idgo_admin.models import Dataset
from idgo_admin.models import LiaisonsContributeurs
from idgo_admin.models import LiaisonsReferents
from idgo_admin.models import License
from idgo_admin.models.mail import send_dataset_creation_mail
from idgo_admin.models.mail import send_dataset_delete_mail
from idgo_admin.models.mail import send_dataset_update_mail
from idgo_admin.models import Organisation
from idgo_admin.models import Resource
from idgo_admin.models import ResourceFormats
from idgo_admin.models import Support
from idgo_admin.shortcuts import get_object_or_404_extended
from idgo_admin.shortcuts import on_profile_http404
from idgo_admin.shortcuts import render_with_info_profile
from idgo_admin.shortcuts import user_and_profile
import json
from math import ceil
from operator import ior


CKAN_URL = settings.CKAN_URL


def target(dataset, user):
    # Permet uniquement de gérer le lien dans le breadcrumb
    if not dataset:
        return 'mine'
    # else:
    if hasattr(dataset, 'remote_csw_dataset') and dataset.remote_csw_dataset:
        return 'csw_harvested'
    elif hasattr(dataset, 'remote_ckan_dataset') and dataset.remote_ckan_dataset:
        return 'ckan_harvested'
    elif hasattr(dataset, 'remote_dcat_dataset') and dataset.remote_dcat_dataset:
        return 'dcat_harvested'
    elif hasattr(dataset, 'editor') and dataset.editor == user:
        return 'mine'
    return 'all'


def get_filtered_datasets(QuerySet, params, profile=None):
    filters = {}

    organisation = params.get('organisation', None)
    if organisation:
        filters['organisation__in'] = Organisation.objects.filter(slug=organisation)

    q = params.get('q', None)
    if q:
        filters['title__icontains'] = q
        # filters['description__icontains'] = q

    private = {'true': True, 'false': False}.get(params.get('private', '').lower())
    if private:
        filters['published'] = not private

    category = params.get('category', None)
    if category:
        filters['categories__in'] = Category.objects.filter(slug=category)

    license = params.get('license', None)
    if license:
        filters['license__id'] = license

    synchronisation = {'true': True, 'false': False}.get(params.get('sync', '').lower())
    if synchronisation:
        filters['resource__synchronisation'] = synchronisation

    sync_frequency = params.get('syncfrequency', None)
    if synchronisation and sync_frequency:
        filters['resource__sync_frequency'] = sync_frequency

    resource_format = params.get('resourceformat', None)
    if resource_format:
        filters['resource__format_type__slug'] = resource_format

    return QuerySet.filter(**filters)


def handle_context(QuerySet, qs, user=None, target='mine'):

    datasets = get_filtered_datasets(QuerySet, qs)

    # Contrôle du tri :

    order_by = qs.get('sortby', None)
    if order_by:
        if order_by.endswith('organisation'):
            # Trier par le nom de l'organisation
            order_by = '{}__slug'.format(order_by)
        if order_by.endswith('editor'):
            # Trier par le nom de famille de l'utilisateur
            order_by = '{}__last_name'.format(order_by)
        order_by = {
            '-private': 'published',
            'private': '-published'}.get(order_by, order_by)
        datasets = datasets.order_by(order_by)

    # Contrôle de la pagination :

    page_number = int(qs.get('page', 1))
    items_per_page = int(qs.get('count', 10))
    number_of_pages = ceil(len(datasets) / items_per_page)
    if number_of_pages < page_number:
        page_number = 1
    x = items_per_page * page_number - items_per_page
    y = x + items_per_page

    # Définition du contexte :

    all_datasets = [
        {'id': instance.slug, 'title': instance.title}
        for instance in QuerySet.all()]

    pk__in = set([
        x.pk for y in [m.categories.all() for m in QuerySet.all()] for x in y])
    all_categories = [
        {'id': instance.slug, 'name': instance.name}
        for instance in Category.objects.filter(pk__in=pk__in)]

    pk__in = set([m.license.pk for m in QuerySet.all() if m.license])
    all_licenses = [
        {'id': instance.pk, 'name': instance.title}
        for instance in License.objects.filter(pk__in=pk__in)]

    pk__in = set([m.organisation.pk for m in QuerySet.all() if m.organisation])
    all_organisations = [
        {'id': instance.slug, 'legal_name': instance.legal_name}
        for instance in Organisation.objects.filter(pk__in=pk__in)]

    pk__in = set([
        x.format_type.pk for y in [m.get_resources() for m in QuerySet.all()]
        for x in y if x.format_type])
    all_resourceformats = [
        {'id': instance.slug, 'name': instance.description}
        for instance in ResourceFormats.objects.filter(pk__in=pk__in)]

    all_update_frequencies = [
        {'id': choice[0], 'name': choice[1]}
        for choice in Resource.FREQUENCY_CHOICES]

    return {
        'target': target,
        'datasets': datasets[x:y],
        'all_datasets': all_datasets,
        'all_organisations': all_organisations,
        'all_categories': all_categories,
        'all_licenses': all_licenses,
        'all_update_frequencies': all_update_frequencies,
        'all_resourceformats': all_resourceformats,
        'pagination': {
            'count': len(datasets),
            'current': page_number,
            'total': number_of_pages,
            },
        }


@ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def list_dataset(request, *args, **kwargs):
    user, profile = user_and_profile(request)

    id = request.GET.get('id', request.GET.get('slug'))
    if not id:
        return redirect(reverse('idgo_admin:list_my_datasets'))
    kvp = {}
    try:
        id = int(id)
    except ValueError:
        kvp['slug'] = id
    else:
        kvp['id'] = id
    # finally:
    instance = get_object_or_404(Dataset, **kvp)
    return redirect(reverse('idgo_admin:dataset_editor', kwargs={'id': instance.id}))


@ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def list_my_datasets(request, *args, **kwargs):
    user, profile = user_and_profile(request)
    context = handle_context(
        Dataset.default.filter(editor=user), request.GET, target='mine')
    return render_with_info_profile(
        request, 'idgo_admin/dataset/datasets.html', status=200, context=context)


@ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def list_all_datasets(request, *args, **kwargs):
    user, profile = user_and_profile(request)
    # Réservé aux référents ou administrateurs IDGO
    roles = profile.get_roles()
    if roles['is_admin']:
        QuerySet = Dataset.default.all()
    elif roles['is_referent']:
        kwargs = {'profile': profile, 'validated_on__isnull': False}
        organisation__in = set(instance.organisation for instance
                               in LiaisonsReferents.objects.filter(**kwargs))
        filter = ior(Q(editor=user), Q(organisation__in=organisation__in))
        QuerySet = Dataset.default.filter(filter)
    else:
        raise Http404()
    context = handle_context(
        QuerySet, request.GET, target='all')
    return render_with_info_profile(
        request, 'idgo_admin/dataset/datasets.html', status=200, context=context)


@ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def list_all_ckan_harvested_datasets(request, *args, **kwargs):
    user, profile = user_and_profile(request)

    # Réservé aux référents ou administrateurs IDGO
    roles = profile.get_roles()
    if not roles['is_referent'] and not roles['is_admin']:
        raise Http404()
    context = handle_context(
        Dataset.harvested_ckan, request.GET, target='ckan_harvested')
    return render_with_info_profile(
        request, 'idgo_admin/dataset/datasets.html', status=200, context=context)


@ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def list_all_csw_harvested_datasets(request, *args, **kwargs):
    user, profile = user_and_profile(request)

    # Réservé aux référents ou administrateurs IDGO
    roles = profile.get_roles()
    if not roles['is_referent'] and not roles['is_admin']:
        raise Http404()
    context = handle_context(
        Dataset.harvested_csw, request.GET, target='csw_harvested')
    return render_with_info_profile(
        request, 'idgo_admin/dataset/datasets.html', status=200, context=context)


@ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def list_all_dcat_harvested_datasets(request, *args, **kwargs):
    user, profile = user_and_profile(request)

    # Réservé aux référents ou administrateurs IDGO
    roles = profile.get_roles()
    if not roles['is_referent'] and not roles['is_admin']:
        raise Http404()
    context = handle_context(
        Dataset.harvested_dcat, request.GET, target='dcat_harvested')
    return render_with_info_profile(
        request, 'idgo_admin/dataset/datasets.html', status=200, context=context)


@method_decorator([csrf_exempt, login_required(login_url=settings.LOGIN_URL)], name='dispatch')
class DatasetManager(View):

    def get_context(self, form, user, dataset):

        layer_rows = []
        resource_rows = []
        if dataset:
            for resource in Resource.objects.filter(dataset=dataset):
                resource_row_data = (
                    resource.pk,
                    resource.title,
                    resource.format_type.description if resource.format_type else None,
                    resource.get_data_type_display(),
                    resource.created_on.isoformat() if resource.created_on else None,
                    resource.last_update.isoformat() if resource.last_update else None,
                    resource.get_restricted_level_display(),
                    str(resource.ckan_id),
                    [layer.pk for layer in resource.get_layers()],
                    resource.ogc_services,
                    resource.extractable,
                    )
                resource_rows.append(resource_row_data)

                common = [
                    resource.pk,
                    resource.title,
                    resource.get_data_type_display(),
                    resource.get_restricted_level_display(),
                    resource.geo_restriction,
                    resource.extractable,
                    resource.ogc_services,
                    ]

                layers = resource.get_layers()
                if layers:
                    for layer in resource.get_layers():
                        layer_row_data = common.copy()
                        layer_row_data.extend((
                            layer.pk,
                            layer.mra_info['name'],
                            layer.mra_info['title'],
                            layer.mra_info['type'],
                            layer.mra_info['enabled'],
                            layer.mra_info['bbox'],
                            layer.mra_info['attributes'],
                            layer.mra_info['styles'],
                            ))
                        layer_rows.append(layer_row_data)

        licenses = [
            (m.pk, m.license.pk) for m
            in LiaisonsContributeurs.get_contribs(profile=user.profile) if m.license]

        supports = [
            (m.pk, {'name': m.name, 'email': m.email})
            for m in Support.objects.all()]

        tags = CkanHandler.get_tags()

        return {
            'target': target(dataset, user),
            'dataset': dataset,
            'form': form,
            'licenses': dict(licenses),
            'layer_rows': json.dumps(layer_rows),
            'resource_rows': json.dumps(resource_rows),
            'supports': json.dumps(dict(supports)),
            'tags': json.dumps(tags),
            }

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, id, *args, **kwargs):
        user, profile = user_and_profile(request)

        if not LiaisonsContributeurs.objects.filter(
                profile=profile, validated_on__isnull=False).exists():
            raise Http404()

        if id != 'new':
            instance = get_object_or_404_extended(Dataset, user, include={'id': id})
        else:
            instance = None
            id = None

        include = {
            'user': user,
            'id': id,
            'identification': id and True or False,
            }
        form = Form(instance=instance, include=include)
        context = self.get_context(form, user, instance)

        return render_with_info_profile(
            request, 'idgo_admin/dataset/dataset.html', context=context)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    @transaction.atomic
    def post(self, request, id, *args, **kwargs):

        user, profile = user_and_profile(request)

        if not LiaisonsContributeurs.objects.filter(
                profile=profile, validated_on__isnull=False).exists():
            raise Http404()

        if id != 'new':
            instance = get_object_or_404_extended(Dataset, user, include={'id': id})
        else:
            instance = None
            id = None

        include = {
            'user': user,
            'id': id,
            'identification': id and True or False,
            }
        form = Form(request.POST, request.FILES, instance=instance, include=include)
        context = self.get_context(form, user, instance)

        if not form.is_valid():
            errors = form._errors.get('__all__', [])
            errors and messages.error(request, ' '.join(errors))
            return render_with_info_profile(
                request, 'idgo_admin/dataset/dataset.html', context)

        data = form.cleaned_data
        kvp = {
            'broadcaster_name': data['broadcaster_name'],
            'broadcaster_email': data['broadcaster_email'],
            'slug': data['slug'],
            'date_creation': data['date_creation'],
            'date_modification': data['date_modification'],
            'date_publication': data['date_publication'],
            'description': data['description'],
            'geocover': data['geocover'],
            'granularity': data['granularity'],
            'license': data['license'],
            'title': data['title'],
            'organisation': data['organisation'],
            'owner_email': data['owner_email'],
            'owner_name': data['owner_name'],
            'update_frequency': data['update_frequency'],
            'published': data['published'],
            'support': data['support'],
            'thumbnail': data['thumbnail'],
            }

        try:
            with transaction.atomic():
                if id:
                    instance = Dataset.objects.get(pk=id)
                    for k, v in kvp.items():
                        setattr(instance, k, v)
                else:
                    kvp['editor'] = user
                    save_opts = {'current_user': user, 'synchronize': False}
                    instance = Dataset.default.create(save_opts=save_opts, **kvp)

                instance.categories.set(data.get('categories', []), clear=True)
                keywords = data.get('keywords')
                if keywords:
                    instance.keywords.clear()
                    for k in keywords:
                        instance.keywords.add(k)
                instance.data_type.set(data.get('data_type', []), clear=True)
                instance.save(current_user=user, synchronize=True)

        except ValidationError as e:
            messages.error(request, ' '.join(e))
        except CkanBaseError as e:
            form.add_error('__all__', e.__str__())
            messages.error(request, e.__str__())
        else:
            if id:
                send_dataset_update_mail(user, instance)
            else:
                send_dataset_creation_mail(user, instance)

            if id:
                messages.success(request, 'Le jeu de données a été mis à jour avec succès.')
            else:
                messages.success(request, (
                    'Le jeu de données a été créé avec succès. Souhaitez-vous '
                    '<a href="{0}">créer un nouveau jeu de données</a> ? ou '
                    '<a href="{1}">ajouter une ressource</a> ? ou bien '
                    '<a href="{2}/dataset/{3}" target="_blank">voir le jeu '
                    'de données dans CKAN</a> ?').format(
                        reverse('idgo_admin:dataset_editor', kwargs={'id': 'new'}),
                        reverse('idgo_admin:resource', kwargs={'dataset_id': instance.id}),
                        CKAN_URL, instance.slug))

            if 'continue' in request.POST:
                return HttpResponseRedirect(
                    reverse('idgo_admin:dataset_editor', kwargs={'id': instance.id}))

            target = instance.editor == profile.user and 'my' or 'all'
            url = reverse('idgo_admin:list_{target}_datasets'.format(target=target))
            return HttpResponseRedirect('{url}#{hash}'.format(url=url, hash=instance.slug))

        return render_with_info_profile(request, 'idgo_admin/dataset/dataset.html', context)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def delete(self, request, id, *args, **kwargs):

        if id == 'new':
            raise Http404()

        user, profile = user_and_profile(request)

        if not LiaisonsContributeurs.objects.filter(
                profile=profile, validated_on__isnull=False).exists():
            raise Http404()

        dataset = get_object_or_404_extended(Dataset, user, include={'id': id})

        try:
            dataset.delete(current_user=user)
        except Exception as e:
            status = 500
            message = e.__str__()
            messages.error(request, message)
        else:
            status = 200
            message = 'Le jeu de données a été supprimé avec succès.'
            messages.success(request, message)

            send_dataset_delete_mail(user, dataset)

        return HttpResponse(status=status)
