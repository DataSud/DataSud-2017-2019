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
from django.contrib.sites.models import Site
from django.http import Http404
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.ckan_module import CkanHandler
from idgo_admin.datagis import intersect
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.exceptions import ProfileHttp404
from idgo_admin.models import AsyncExtractorTask
from idgo_admin.models import BaseMaps
from idgo_admin.models import Commune
from idgo_admin.models import Dataset
from idgo_admin.models import ExtractorSupportedFormat
from idgo_admin.models import Layer
from idgo_admin.models import Organisation
from idgo_admin.models import Resource
from idgo_admin.models import SupportedCrs
from idgo_admin.shortcuts import on_profile_http404
from idgo_admin.shortcuts import render_with_info_profile
from idgo_admin.shortcuts import user_and_profile
import json
from math import ceil
import re
import requests
from uuid import UUID


EXTRACTOR_URL = settings.EXTRACTOR_URL
try:
    BOUNDS = settings.EXTRACTOR_BOUNDS
except AttributeError:
    BOUNDS = [[40, -14], [55, 28]]

DB_SETTINGS = settings.DATABASES[settings.DATAGIS_DB]

decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


@ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def extractor_task(request, *args, **kwargs):
    user, profile = user_and_profile(request)
    instance = get_object_or_404(AsyncExtractorTask, uuid=request.GET.get('id'))
    query = instance.query or instance.details.get['query']

    extract_params = {}
    format_raster, format_vector = None, None

    for data_extraction in query['data_extractions']:
        for format in ExtractorSupportedFormat.objects.all():
            if format.details.get('dst_format') == data_extraction.get('dst_format'):
                if format.type == 'raster':
                    format_raster = format
                if format.type == 'vector':
                    format_vector = format
        extract_params = data_extraction

    auth_name, auth_code = extract_params.get('dst_srs').split(':')
    crs = SupportedCrs.objects.get(auth_name=auth_name, auth_code=auth_code)

    if instance.model == 'Dataset':
        dataset = instance.target_object
        bounds = dataset.bbox.extent
        layers = [layer for layer in dataset.get_layers()]
    elif instance.model == 'Resource':
        resource = instance.target_object
        bounds = resource.bbox.extent
        layers = [layer for layer in resource.get_layers()]
    elif instance.model == 'Layer':
        layer = instance.target_object
        bounds = layer.bbox.extent
        layers = [instance.target_object]

    data = {
        'bounds': bounds,
        'crs': crs.description,
        'footprint': extract_params.get('footprint'),
        'format_raster': format_raster and format_raster.description or '-',
        'format_vector': format_vector and format_vector.description or '-',
        'layer': [l.name for l in layers],
        'start': instance.start_datetime,
        'stop': instance.stop_datetime,
        'target': '{} : {}'.format(
            instance.target_object._meta.verbose_name,
            instance.target_object.__str__()),
        'target_value': instance.foreign_value,
        'target_field': instance.foreign_field,
        'target_model': instance.model.lower(),
        'submission': instance.details.get('submission_datetime'),
        'user': instance.user.get_full_name()}

    if instance.success is False:
        data['error'] = instance.details.get('exception', 'Une erreur est survenu.')

    return JsonResponse(data=data)


@method_decorator(decorators, name='dispatch')
class ExtractorDashboard(View):

    def get(self, request, *args, **kwargs):

        user, profile = user_and_profile(request)
        if not profile.crige_membership:
            raise Http404()

        order_by = request.GET.get('sortby', '-submission')

        if order_by:
            if order_by.endswith('submission'):
                order_by = '{}submission_datetime'.format(
                    order_by.startswith('-') and '-' or '')
            elif order_by.endswith('status'):
                order_by = '{}success'.format(
                    order_by.startswith('-') and '-' or '')
            else:
                order_by = None

        # Pagination
        page_number = int(request.GET.get('page', 1))
        items_per_page = int(request.GET.get('count', 10))

        x = items_per_page * page_number - items_per_page
        y = x + items_per_page

        if profile.is_admin and profile.crige_membership:
            tasks = AsyncExtractorTask.objects.all()
        else:
            tasks = AsyncExtractorTask.objects.filter(user=user)

        tasks = order_by and tasks.order_by(order_by) or tasks
        number_of_pages = ceil(len(tasks) / items_per_page)

        context = {
            'bounds': BOUNDS,
            'basemaps': BaseMaps.objects.all(),
            'pagination': {
                'current': page_number,
                'total': number_of_pages},
            'supported_crs': SupportedCrs.objects.all(),
            'supported_format': ExtractorSupportedFormat.objects.all(),
            'tasks': tasks[x:y]}

        return render_with_info_profile(
            request, 'idgo_admin/extractor/dashboard.html', context=context)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def post(self, request, *args, **kwargs):

        user, profile = user_and_profile(request)
        if not profile.crige_membership:
            raise Http404()

        if 'revoke' in request.POST:
            task = get_object_or_404(
                AsyncExtractorTask, uuid=UUID(request.POST.get('task')))
            if task.success is True:
                messages.error(request, (
                    'La demande de révocation ne peut aboutir car '
                    "l'extraction a déjà été executée avec succès."))
            else:
                if 'abort' in list(task.details.get('possible_requests').keys()):
                    abort = task.details['possible_requests']['abort']
                    r = requests.request(abort['verb'], abort['url'], json=abort['payload'])

                    if r.status_code in (201, 202):
                        messages.success(
                            request, 'La demande de révocation est envoyée avec succès.')
                    else:
                        messages.error(request, r.json().get('detail'))

        return HttpResponseRedirect(reverse('idgo_admin:extractor_dashboard'))


@method_decorator(decorators, name='dispatch')
class Extractor(View):

    template = 'idgo_admin/extractor/extractor.html'
    namespace = 'idgo_admin:extractor'

    def get_instance(self, ModelObj, value):
        m = re.match('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', value)
        if m:
            key = 'ckan_id'
            value = UUID(m.group(0))
        if isinstance(value, str):
            if ModelObj.__name__ == 'Layer':
                key = 'name'
            else:
                key = 'slug'
        if isinstance(value, int):
            key = 'id'
        try:
            return ModelObj.objects.get(**{key: value})
        except (ModelObj.DoesNotExist, ValueError):
            raise Http404()

    def _context(self, user, organisation=None, dataset=None,
                 resource=None, layer=None, task=None):

        context = {
            'organisations': None,
            'organisation': None,
            'datasets': None,
            'dataset': None,
            'resources': None,
            'resource': None,
            'layer': None,
            'task': None,
            'communes': Commune.objects.all().transform(srid=4326),
            'supported_crs': SupportedCrs.objects.all(),
            'supported_format': ExtractorSupportedFormat.objects.all(),
            'format_raster': None,
            'format_vector': None}

        if task:
            try:
                task = AsyncExtractorTask.objects.get(uuid=UUID(task))
            except AsyncExtractorTask.DoesNotExist:
                pass
            else:
                if task.model == 'Layer':
                    context['task'] = task
                    context['layer'] = task.target_object
                    context['resource'] = task.target_object.resource
                    context['dataset'] = task.target_object.resource.dataset
                    context['organisation'] = task.target_object.resource.dataset.organisation
                elif task.model == 'Resource':
                    context['task'] = task
                    context['layer'] = task.target_object.get_layers()[0]  # Dans la version actuelle relation 1-1
                    context['resource'] = task.target_object
                    context['dataset'] = task.target_object.dataset
                    context['organisation'] = task.target_object.dataset.organisation
                elif task.model == 'Dataset':
                    context['dataset'] = task.target_object
                    context['organisation'] = task.target_object.organisation

                data_extractions = task.query['data_extractions']
                for entry in data_extractions:
                    context['footprint'] = entry.get('footprint')
                    context['crs'] = entry.get('dst_srs')

                    for format in ExtractorSupportedFormat.objects.all():
                        if format.details.get('dst_format') == entry.get('dst_format'):
                            if format.type == 'raster':
                                context['format_raster'] = format.name
                            if format.type == 'vector':
                                context['format_vector'] = format.name

        # Les paramètres Layer Resource Dataset et Organisation écrase Task
        if layer:
            layer = self.get_instance(Layer, layer)
            context['layer'] = layer
            context['resource'] = layer.resource
            context['dataset'] = layer.resource.dataset
            context['organisation'] = layer.resource.dataset.organisation
        elif resource:
            resource = self.get_instance(Resource, resource)
            context['resource'] = resource
            context['dataset'] = resource.dataset
            context['organisation'] = resource.dataset.organisation
        elif dataset:
            dataset = self.get_instance(Dataset, dataset)
            context['dataset'] = dataset
            context['organisation'] = dataset.organisation
        elif organisation:
            organisation = self.get_instance(Organisation, organisation)
            context['organisation'] = organisation

        context['organisations'] = Organisation.objects.filter(
            dataset__resource__in=Resource.objects.filter(extractable=True).exclude(layer=None)
            ).distinct()

        context['datasets'] = Dataset.objects.filter(
            organisation=context['organisation'],
            resource__in=Resource.objects.filter(extractable=True).exclude(layer=None)
            ).distinct()

        context['resources'] = Resource.objects.filter(
            dataset=context['dataset'],
            extractable=True
            ).exclude(layer=None)

        if len(context['resources']) == 1 and not context['resource']:
            context['resource'] = context['resources'][0]

        layers = Layer.objects.filter(resource=context['resource'])

        if not context['layer'] and layers:
            context['layer'] = layers[0]

        return context

    def get_context(self, request, user):

        context = self._context(
            user,
            organisation=request.GET.get('organisation'),
            dataset=request.GET.get('dataset'),
            resource=request.GET.get('resource'),
            layer=request.GET.get('layer'),
            task=request.GET.get('task'))

        context['basemaps'] = BaseMaps.objects.all()

        bbox = request.GET.get('bbox')
        if bbox:
            minx, miny, maxx, maxy = bbox.split(',')
            context['bounds'] = [[miny, minx], [maxy, maxx]]
        else:
            context['bounds'] = BOUNDS

        try:
            default_crs = \
                SupportedCrs.objects.get(auth_name='EPSG', auth_code=2154).authority
        except SupportedCrs.DoesNotExist:
            default_crs = None

        context['crs'] = request.GET.get('crs', default_crs)

        try:
            default_vector_format = \
                ExtractorSupportedFormat.objects.get(
                    name='shapefile', type='vector').name
        except ExtractorSupportedFormat.DoesNotExist:
            default_vector_format = None
        context['format_vector'] = request.GET.get('format_vector', context['format_vector'] or default_vector_format)

        try:
            default_raster_format = \
                ExtractorSupportedFormat.objects.get(
                    name='geotiff_no_compressed', type='raster').details
        except ExtractorSupportedFormat.DoesNotExist:
            default_raster_format = None
        context['format_raster'] = request.GET.get('format_raster', context['format_raster'] or default_raster_format)

        if bool(request.GET.get('jurisdiction')):
            context['jurisdiction'] = True
            if user.profile.organisation and user.profile.organisation.jurisdiction:
                context['footprint'] = json.loads(user.profile.organisation.jurisdiction.geom.geojson)
            else:
                context['footprint'] = None
        else:
            context['jurisdiction'] = False
            # footprint = request.GET.get('footprint')
            # if footprint:
            #     context['footprint'] = json.loads(footprint)
            # else:
            context['footprint'] = context.get('footprint')

        context['format'] = request.GET.get('format', context.get('format'))

        return context

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, *args, **kwargs):
        user, profile = user_and_profile(request)
        if not profile.crige_membership:
            raise Http404()

        return render_with_info_profile(
            request, self.template,
            context=self.get_context(request, user))

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def post(self, request, *args, **kwargs):
        user, profile = user_and_profile(request)
        if not profile.crige_membership:
            raise Http404()

        context = self.get_context(request, user)
        footprint = request.POST.get('footprint') or None
        footprint = footprint and json.loads(footprint)
        layer_name = request.POST.get('layer')
        resource_name = request.POST.get('resource')
        dataset_name = request.POST.get('dataset')
        dst_crs = request.POST.get('crs')

        format_vector = request.POST.get('format-vector') or None
        if format_vector:
            dst_format_vector = ExtractorSupportedFormat.objects.get(
                name=format_vector, type='vector').details

        format_raster = request.POST.get('format-raster') or None
        if format_raster:
            dst_format_raster = ExtractorSupportedFormat.objects.get(
                name=format_raster, type='raster').details

        data_extractions = []
        additional_files = []

        if layer_name or resource_name:
            if layer_name:
                model = 'Layer'
                foreign_field = 'name'
                foreign_value = layer_name
                layer = get_object_or_404(Layer, name=layer_name)
                resource = layer.resource

            if resource_name:
                model = 'Resource'
                foreign_field = 'ckan_id'
                foreign_value = resource_name
                resource = get_object_or_404(Resource, ckan_id=resource_name)
                layer = resource.get_layers()[0]  # Car relation 1-1

            if layer.type == 'raster':
                data_extraction = {**{
                    'source': layer.filename,
                    }, **dst_format_raster}
            elif layer.type == 'vector':
                data_extraction = {
                    **{
                        'layer': layer.name,
                        'source': 'PG:host={host} port={port} dbname={database} user={user} password={password}'.format(
                            host=DB_SETTINGS['HOST'],
                            port=DB_SETTINGS['PORT'],
                            database=DB_SETTINGS['NAME'],
                            user=DB_SETTINGS['USER'],
                            password=DB_SETTINGS['PASSWORD'],
                            ),
                        },
                    **dst_format_vector
                    }

            data_extraction['dst_srs'] = dst_crs or 'EPSG:2154'

            if resource.geo_restriction:
                footprint_restriction = \
                    json.loads(user.profile.organisation.jurisdiction.geom.geojson)
                if footprint:
                    try:
                        data_extraction['footprint'] = intersect(json.dumps(footprint), json.dumps(footprint_restriction))
                    except Exception as e:
                        msg = "La zone d'extraction génère une erreur"
                        messages.error(request, msg)
                        return render_with_info_profile(request, self.template, context=context)
                else:
                    data_extraction['footprint'] = footprint_restriction
                data_extraction['footprint_srs'] = 'EPSG:4326'
            elif footprint:
                data_extraction['footprint'] = footprint
                data_extraction['footprint_srs'] = 'EPSG:4326'

            data_extractions.append(data_extraction)
            # Pas d'`additional_files` dans le cas présent.

        elif dataset_name:
            model = 'Dataset'
            foreign_field = 'slug'
            foreign_value = dataset_name
            dataset = get_object_or_404(Dataset, slug=dataset_name)

            for resource in dataset.get_resources():
                for layer in resource.get_layers():
                    if layer.type == 'raster':
                        data_extraction = {**{
                            'source': layer.filename,
                            }, **dst_format_raster}
                    elif layer.type == 'vector':
                        data_extraction = {**{
                            'layer': layer.name,
                            'source': 'PG:host=postgis-master user=datagis dbname=datagis',
                            }, **dst_format_vector}
                    data_extraction['dst_srs'] = dst_crs or 'EPSG:2154'

                    if resource.geo_restriction:
                        footprint_restriction = \
                            json.loads(user.profile.organisation.jurisdiction.geom.geojson)
                        if footprint:
                            data_extraction['footprint'] = intersect(json.dumps(footprint), json.dumps(footprint_restriction))
                        else:
                            data_extraction['footprint'] = footprint_restriction
                        data_extraction['footprint_srs'] = 'EPSG:4326'
                    elif footprint:
                        data_extraction['footprint'] = footprint
                        data_extraction['footprint_srs'] = 'EPSG:4326'

                    data_extractions.append(data_extraction)

                if resource.data_type == 'annexe':
                    additional_files.append({
                        'file_name': resource.filename,
                        'dir_name': 'Documentation associée',
                        'file_location': CkanHandler.get_resource(
                            str(resource.ckan_id)).get('url')})

        query = {
            'user_id': user.username,
            'user_email_address': user.email,
            'user_name': user.last_name,
            'user_first_name': user.first_name,
            'user_company': user.profile.organisation and user.profile.organisation.legal_name or '',
            'user_address': user.profile.organisation and user.profile.organisation.full_address or '',
            'data_extractions': data_extractions,
            'additional_files': additional_files}

        r = requests.post(EXTRACTOR_URL, json=query)

        if r.status_code == 201:
            details = r.json()

            AsyncExtractorTask.objects.create(
                details=details,
                foreign_field=foreign_field,
                foreign_value=foreign_value,
                model=model,
                query=query,
                submission_datetime=details.get('submission_datetime'),
                uuid=UUID(details.get('task_id')),
                user=user)

            messages.success(request, (
                "L'extraction a été ajoutée à la liste de tâche. "
                "Vous allez recevoir un e-mail une fois l'extraction réalisée."))

            domain = Site.objects.get(name='extractor').domain
            url = 'http{secure}://{domain}{path}'.format(
                secure=request.is_secure and 's' or '',
                domain=domain,
                path=reverse('idgo_admin:extractor_dashboard'))
            return HttpResponseRedirect(url)
        else:
            if r.status_code == 400:
                details = r.json().get('detail')
                msg = '{}: {}'.format(details.get('title', 'Error'),
                                      ' '.join(details.get('list', 'Error')))
            else:
                msg = "L'extracteur n'est pas disponible pour le moment."
            messages.error(request, msg)
            return render_with_info_profile(request, self.template, context=context)
