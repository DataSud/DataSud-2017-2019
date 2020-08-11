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
from django.db import transaction
from django.http import Http404
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.exceptions import CkanBaseError
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.exceptions import MraBaseError
from idgo_admin.exceptions import ProfileHttp404
from idgo_admin.forms.resource import ResourceForm as Form
from idgo_admin.models import Dataset
from idgo_admin.models.mail import send_resource_creation_mail
from idgo_admin.models.mail import send_resource_delete_mail
from idgo_admin.models.mail import send_resource_update_mail
from idgo_admin.models import Resource
from idgo_admin.shortcuts import get_object_or_404_extended
from idgo_admin.shortcuts import on_profile_http404
from idgo_admin.shortcuts import render_with_info_profile
from idgo_admin.shortcuts import user_and_profile
from idgo_admin.views.dataset import target as datasets_target
import json
import os


CKAN_URL = settings.CKAN_URL

FTP_DIR = settings.FTP_DIR
try:
    FTP_UPLOADS_DIR = settings.FTP_UPLOADS_DIR
except AttributeError:
    FTP_UPLOADS_DIR = 'uploads'


decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def resource(request, dataset_id=None, *args, **kwargs):
    user, profile = user_and_profile(request)

    id = request.GET.get('id', request.GET.get('ckan_id'))
    if not id:
        raise Http404()

    kvp = {}
    try:
        id = int(id)
    except ValueError:
        kvp['ckan_id'] = id
    else:
        kvp['id'] = id
    finally:
        resource = get_object_or_404(Resource, **kvp)

    # TODO:
    # return redirect(reverse('idgo_admin:resource_editor', kwargs={
    #     'dataset_id': resource.dataset.id, 'resource_id': resource.id}))
    return redirect(
        '{}?id={}'.format(
            reverse(
                'idgo_admin:resource', kwargs={'dataset_id': resource.dataset.id}),
            resource.id))


@method_decorator(decorators, name='dispatch')
class ResourceManager(View):

    template = 'idgo_admin/dataset/resource/resource.html'
    namespace = 'idgo_admin:resource'

    def get_context(self, form, user, dataset, resource=None):

        mode = None
        if resource:
            if resource.up_file:
                mode = 'up_file'
            elif resource.dl_url:
                mode = 'dl_url'
            elif resource.referenced_url:
                mode = 'referenced_url'
            elif resource.ftp_file:
                mode = 'ftp_file'
        elif form:
            if form.files.get('up_file'):
                mode = 'up_file'
            elif form.data.get('dl_url'):
                mode = 'dl_url'
            elif form.data.get('referenced_url'):
                mode = 'referenced_url'
            elif form.data.get('ftp_file'):
                mode = 'ftp_file'

        return {
            'target': datasets_target(dataset, user),
            'dataset': dataset,
            'resource': resource,
            'form': form,
            'mode': mode,
            }

    @ExceptionsHandler(actions={ProfileHttp404: on_profile_http404})
    def get(self, request, dataset_id=None, *args, **kwargs):

        user, profile = user_and_profile(request)

        dataset = get_object_or_404_extended(
            Dataset, user, include={'id': dataset_id})

        # Redirect to layer
        _resource = request.GET.get('resource')
        _layer = request.GET.get('layer')
        if _resource and _layer:
            return redirect(
                reverse('idgo_admin:layer_editor', kwargs={
                    'dataset_id': dataset.id,
                    'resource_id': _resource,
                    'layer_id': _layer}))

        resource = None
        id = request.GET.get('id')
        if id:
            include = {'id': id, 'dataset_id': dataset.id}
            resource = get_object_or_404_extended(Resource, user, include=include)

        form = Form(instance=resource, user=user)
        context = self.get_context(form, user, dataset, resource=resource)

        return render_with_info_profile(request, self.template, context)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    @transaction.atomic
    def post(self, request, dataset_id=None, *args, **kwargs):

        # Vider systèmatiquement les messages
        storage = messages.get_messages(request)
        storage.used = True

        user, profile = user_and_profile(request)

        dataset = get_object_or_404_extended(
            Dataset, user, include={'id': dataset_id})

        resource = None
        id = request.POST.get('id', request.GET.get('id'))
        if id:
            include = {'id': id, 'dataset': dataset}
            resource = get_object_or_404_extended(Resource, user, include=include)

        form = Form(request.POST, request.FILES,
                    instance=resource, dataset=dataset, user=user)

        context = self.get_context(form, user, dataset, resource)

        ajax = 'ajax' in request.POST
        save_and_continue = 'continue' in request.POST

        if not form.is_valid():
            if ajax:
                error = dict([(k, [str(m) for m in v]) for k, v in form.errors.items()])
                msg = 'Veuillez corriger le formulaire.'
                if '__all__' in error:
                    error['__all__'].prepend(msg)
                else:
                    error['__all__'] = [msg]
                return JsonResponse(json.dumps({'error': error}), safe=False)

            return render_with_info_profile(request, self.template, context)

        data = form.cleaned_data

        kvp = {
            'dataset': dataset,
            'title': data['title'],
            'description': data['description'],
            'lang': data['lang'],
            'data_type': data['data_type'],
            'format_type': data['format_type'],
            'last_update': data.get('last_update'),
            'restricted_level': data['restricted_level'],
            'up_file': data['up_file'],
            'dl_url': data['dl_url'],
            'synchronisation': data['synchronisation'],
            'sync_frequency': data['sync_frequency'],
            'referenced_url': data['referenced_url'],
            'ftp_file': data['ftp_file'] and os.path.join(FTP_DIR, user.username, data['ftp_file']) or None,
            'crs': data['crs'],
            'encoding': data.get('encoding') or None,
            'extractable': data['extractable'],
            'ogc_services': data['ogc_services'],
            'geo_restriction': data['geo_restriction'],
            }

        profiles_allowed = None
        organisations_allowed = None
        if data['restricted_level'] == 'only_allowed_users':
            profiles_allowed = data['profiles_allowed']
        elif data['restricted_level'] == 'same_organization':
            organisations_allowed = [form._dataset.organisation]
        elif data['restricted_level'] == 'any_organization':
            organisations_allowed = data['organisations_allowed']

        memory_up_file = request.FILES.get('up_file')
        file_extras = memory_up_file and {
            'mimetype': memory_up_file.content_type,
            'resource_type': memory_up_file.name,
            'size': memory_up_file.size} or None

        try:
            with transaction.atomic():
                save_opts = {
                    'current_user': user,
                    'file_extras': file_extras,
                    'synchronize': True,
                    }
                if not id:
                    resource = Resource.default.create(save_opts=save_opts, **kvp)
                    save_opts['skip_download'] = True  # IMPORTANT
                    save_opts['file_extras'] = None  # IMPORTANT
                else:
                    resource = Resource.objects.get(pk=id)
                    for k, v in kvp.items():
                        setattr(resource, k, v)
                if organisations_allowed:
                    resource.organisations_allowed = organisations_allowed
                if profiles_allowed:
                    resource.profiles_allowed = profiles_allowed
                save_opts['synchronize'] = True
                resource.save(**save_opts)
        except ValidationError as e:
            if e.code == 'crs':
                form.add_error(e.code, '')
                form.add_error('__all__', e.message)
            elif e.code == 'encoding':
                form.add_error(e.code, '')
                form.add_error('__all__', e.message)
            else:
                form.add_error(e.code, e.message)
            messages.error(request, ' '.join(e))
            error = dict(
                [(k, [str(m) for m in v]) for k, v in form.errors.items()])
        except CkanBaseError as e:
            error = {'__all__': [e.__str__()]}
            form.add_error('__all__', e.__str__())
            messages.error(request, e.__str__())
        except MraBaseError as e:
            error = {'__all__': [e.__str__()]}
            form.add_error('__all__', e.__str__())
            messages.error(request, e.__str__())
        else:
            if id:
                send_resource_update_mail(user, resource)
            else:
                send_resource_creation_mail(user, resource)

            dataset_href = reverse(
                self.namespace, kwargs={'dataset_id': dataset_id})
            messages.success(request, (
                'La ressource a été {0} avec succès. Souhaitez-vous '
                '<a href="{1}">ajouter une nouvelle ressource</a> ? ou bien '
                '<a href="{2}/dataset/{3}/resource/{4}" target="_blank">'
                'voir la ressource dans CKAN</a> ?').format(
                id and 'mise à jour' or 'créée', dataset_href,
                CKAN_URL, dataset.slug, resource.ckan_id))

            if ajax:
                response = HttpResponse(status=201)  # Ugly hack
                if save_and_continue:
                    href = '{0}?id={1}'.format(dataset_href, resource.id)
                else:
                    href = '{0}?id={1}#resources/{2}'.format(
                        reverse('idgo_admin:dataset'), dataset_id, resource.id)
                response['Content-Location'] = href
                return response
            else:
                if save_and_continue:
                    url = '{0}?id={1}'.format(dataset_href, resource.id)
                    return HttpResponseRedirect(url)
                # else:
                url = '{0}?id={1}#resources/{2}'.format(
                    reverse('idgo_admin:dataset'), dataset_id, resource.id)
                return HttpResponseRedirect(url)

        if ajax:
            form._errors = None
            return JsonResponse(json.dumps({'error': error}), safe=False)
        return render_with_info_profile(request, self.template, context)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def delete(self, request, dataset_id=None, *args, **kwargs):

        user, profile = user_and_profile(request)

        dataset = get_object_or_404_extended(
            Dataset, user, include={'id': dataset_id})

        id = request.POST.get('id', request.GET.get('id'))
        if not id:
            raise Http404()
        include = {'id': id, 'dataset': dataset}
        resource = get_object_or_404_extended(Resource, user, include=include)

        try:
            resource.delete(current_user=user)
        except Exception as e:
            status = 500
            message = e.__str__()
            messages.error(request, message)
        else:
            status = 200
            message = 'La ressource a été supprimée avec succès.'
            messages.success(request, message)
            send_resource_delete_mail(user, resource)

        return HttpResponse(status=status)
