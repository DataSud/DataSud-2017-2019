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

from datetime import datetime
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import Http404
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.exceptions import ProfileHttp404
from idgo_admin.geonet_module import GeonetUserHandler as geonet
from idgo_admin.models import Category
from idgo_admin.models.category import MDEDIT_CONFIG_PATH
from idgo_admin.models.category import MDEDIT_DATASET_MODEL
from idgo_admin.models.category import MDEDIT_HTML_PATH
from idgo_admin.models.category import MDEDIT_LOCALES
from idgo_admin.models.category import MDEDIT_SERVICE_MODEL
from idgo_admin.models import Dataset
from idgo_admin.models import Organisation
from idgo_admin.models import Resource
from idgo_admin.shortcuts import get_object_or_404
from idgo_admin.shortcuts import on_profile_http404
from idgo_admin.shortcuts import render_with_info_profile
from idgo_admin.shortcuts import user_and_profile
from idgo_admin.utils import clean_my_obj
from idgo_admin.utils import open_json_staticfile
from idgo_admin.views.dataset import target
import os
import re
from urllib.parse import urljoin
import xml.etree.ElementTree as ET


STATIC_URL = settings.STATIC_URL
GEONETWORK_URL = settings.GEONETWORK_URL
CKAN_URL = settings.CKAN_URL
DOMAIN_NAME = settings.DOMAIN_NAME
READTHEDOC_URL_INSPIRE = settings.READTHEDOC_URL_INSPIRE


def join_url(filename, path=MDEDIT_CONFIG_PATH):
    return urljoin(urljoin(STATIC_URL, path), filename)


def prefill_dataset_model(dataset):

    model = open_json_staticfile(
        os.path.join(MDEDIT_CONFIG_PATH, MDEDIT_DATASET_MODEL))

    data = model.copy()
    editor = dataset.editor
    organisation = dataset.organisation

    default_contact = {
        'individualName': editor.get_full_name(),
        'organisationName': organisation.legal_name,
        'email': organisation.email,
        'phoneVoice': organisation.phone,
        'deliveryPoint': organisation.address,
        'postalCode': organisation.postcode,
        'city': organisation.city}

    md_contacts = {**default_contact, **{'role': 'author'}}
    md_data_point_of_contacts = {**default_contact, **{'role': 'owner'}}

    try:
        organisation_logo = {
            'logoDescription': 'logo',
            'logoUrl': urljoin(DOMAIN_NAME, organisation.logo.url)}
    except Exception:
        pass
    else:
        md_contacts.update(organisation_logo)
        md_data_point_of_contacts.update(organisation_logo)

    data['mdContacts'].insert(0, md_contacts)
    data['dataPointOfContacts'].insert(0, md_data_point_of_contacts)

    data['dataTitle'] = dataset.title
    data['dataAbstract'] = dataset.description

    if dataset.date_creation:
        data['dataDates'].insert(0, {
            'date': dataset.date_creation.isoformat(),
            'dateType': 'creation'})
    if dataset.date_publication:
        data['dataDates'].insert(1, {
            'date': dataset.date_publication.isoformat(),
            'dateType': 'publication'})
    if dataset.date_modification:
        data['dataDates'].insert(2, {
            'date': dataset.date_modification.isoformat(),
            'dateType': 'revision'})

    data['dataMaintenanceFrequency'] = {
        'never': 'notPlanned',          # [011]
        'asneeded': 'asNeeded',         # [009]
        'intermittently': 'irregular',  # [010]
        'continuously': 'continual',    # [001]
        'realtime': 'continual',        # ??? -> [001]
        'daily': 'daily',               # [002]
        'weekly': 'weekly',             # [003]
        'fortnightly': 'fortnightly',   # [004]
        'monthly': 'monthly',           # [005]
        'quarterly': 'quaterly',        # [006]
        'semiannual': 'biannually',     # [007]
        'annual': 'annually'            # [008]
        }.get(dataset.update_frequency, 'unknown')  # [012]

    if dataset.keywords:
        data['dataKeywords'].insert(0, {
            'keywords': [kw for kw in dataset.keywords.names()],
            'keywordType': 'theme'})

    for category in Category.objects.filter(dataset=dataset):
        iso_topic = category.iso_topic
        if iso_topic:
            data['dataTopicCategories'].append(iso_topic)

    try:
        data['dataBrowseGraphics'].insert(0, {
            'fileName': urljoin(DOMAIN_NAME, dataset.thumbnail.url),
            # 'fileDescription': 'Imagette',
            'fileType': dataset.thumbnail.name.split('.')[-1]})
    except Exception:
        pass

    resources = Resource.objects.filter(dataset=dataset)
    for resource in resources:
        entry = {
            'name': resource.title,
            'url': '{0}/dataset/{1}/resource/{2}'.format(
                CKAN_URL, dataset.slug, resource.ckan_id),
            'description': resource.description}
        protocol = resource.format_type and resource.format_type.protocol
        if protocol:
            entry['protocol'] = protocol
        data['dataLinkages'].insert(0, entry)

    return clean_my_obj(data)


def prefill_service_model(organisation):

    model = open_json_staticfile(
        os.path.join(MDEDIT_CONFIG_PATH, MDEDIT_SERVICE_MODEL))

    data = model.copy()
    # editor = None  # qui est l'éditeur ?

    default_contact = {
        # 'individualName': editor.get_full_name(),
        'organisationName': organisation.legal_name,
        'email': organisation.email,
        'phoneVoice': organisation.phone,
        'deliveryPoint': organisation.address,
        'postalCode': organisation.postcode,
        'city': organisation.city}

    md_contacts = {**default_contact, **{'role': 'author'}}
    md_data_point_of_contacts = {**default_contact, **{'role': 'owner'}}

    try:
        logo = {
            'logoDescription': 'logo',
            'logoUrl': urljoin(DOMAIN_NAME, organisation.logo.url)}
    except Exception:
        pass
    else:
        md_contacts.update(logo)
        md_data_point_of_contacts.update(logo)

    data['mdContacts'].insert(0, md_contacts)
    data['dataPointOfContacts'].insert(0, md_data_point_of_contacts)

    return clean_my_obj(data)


decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


@method_decorator(decorators, name='dispatch')
class DatasetMDEditTplEdit(View):

    template = 'idgo_admin/mdedit/template_dataset_edit.html'

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, id, *args, **kwargs):
        user, profile = user_and_profile(request)
        get_object_or_404(Dataset, id=id)
        return render(request, self.template)


@method_decorator(decorators, name='dispatch')
class DatasetMDEdit(View):

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, id, *args, **kwargs):
        user, profile = user_and_profile(request)
        instance = get_object_or_404(Dataset, id=id)

        config = {
            'app_name': 'mdEdit',
            'app_title': 'mdEdit',
            'app_version': '0.14.9',
            'app_copyrights': '(c) CIGAL 2016',
            'languages': {'locales': ['fr']},
            'defaultLanguage': 'fr',
            'server_url_md': GEONETWORK_URL,
            'views': {
                'list': [{
                    # 'path': '{id}/edit/'.format(id=id),
                    'path': reverse('idgo_admin:dataset_mdedit_tpl_edit', kwargs={'id': instance.id}),
                    'values': {'fr': 'Edition'},
                    'locales': {'fr': join_url('views/edit/tpl-edit_fr.json')}
                    }, {
                    'path': join_url('tpl-view.html', path=MDEDIT_HTML_PATH),
                    'values': {'fr': 'Vue'},
                    'locales': {'fr': join_url('views/view/tpl-view_fr.json')}
                    }]},
            'models': {
                'list': [{
                    'path': join_url(MDEDIT_DATASET_MODEL),
                    'value': 'Modèle de fiche vierge'
                    }]},
            'locales': MDEDIT_LOCALES,
            'locales_path': join_url('locales/'),
            'geographicextents_list': join_url('list_geographicextents.json'),
            'referencesystems_list': join_url('list_referencesystems.json'),
            'static_root': join_url('libs/mdedit/', path=STATIC_URL),
            'modal_template': {
                'help': join_url('modal-help.html', path=MDEDIT_HTML_PATH)}}

        context = {
            'dataset': instance,
            'doc_url': READTHEDOC_URL_INSPIRE,
            'config': config,
            'target': target(instance, user),
            }

        record = instance.geonet_id and geonet.get_record(str(instance.geonet_id)) or None

        if record:
            xml = record.xml.decode(encoding='utf-8')
            context['record_xml'] = re.sub('\n', '', xml).replace("'", "\\'")  # C'est moche
        else:
            context['record_obj'] = prefill_dataset_model(instance)

        return render_with_info_profile(request, 'idgo_admin/mdedit/dataset.html', context=context)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def post(self, request, id, *args, **kwargs):

        user, profile = user_and_profile(request)
        dataset = get_object_or_404(Dataset, id=id)

        delete = 'delete' in request.POST
        save = 'save' in request.POST
        save_and_continue = 'continue' in request.POST

        if delete and dataset.geonet_id:
            try:
                geonet.delete_record(dataset.geonet_id)
                dataset.geonet_id = None
                dataset.save(current_user=None)
            except Exception:
                messages.error(
                    request, "La fiche de metadonnées a été supprimée avec succès.")
            else:
                messages.success(
                    request, "La fiche de metadonnées a été supprimée avec succès.")
            # finally:
            return HttpResponseRedirect(
                reverse('idgo_admin:dataset_mdedit', kwargs={'id': id}))

        if save or save_and_continue:
            data = dict(request.POST)

            dataset.title = data['dataTitle'][0] or dataset.title
            dataset.description = data['dataAbstract'][0] or None

            date_creation = data['dataDateCreation'][0] or None
            if date_creation:
                dataset.date_creation = datetime.strptime(date_creation, "%Y-%m-%d").date()

            date_modification = data['dataDateRevision'][0] or None
            if date_modification:
                dataset.date_modification = datetime.strptime(date_modification, "%Y-%m-%d").date()

            date_publication = data['dataDatePublication'][0] or None
            if date_publication:
                dataset.date_publication = datetime.strptime(date_publication, "%Y-%m-%d").date()

            dataset.update_frequency = {
                'notPlanned': 'never',          # [011]
                'asNeeded': 'asneeded',         # [009]
                'irregular': 'intermittently',  # [010]
                'continual': 'continuously',    # [001]
                'daily': 'daily',               # [002]
                'weekly': 'weekly',             # [003]
                'fortnightly': 'fortnightly',   # [004]
                'monthly': 'monthly',           # [005]
                'quarterly': 'quaterly',        # [006]
                'semiannual': 'biannually',     # [007]
                'annual': 'annually'            # [008]
                }.get(data['dataMaintenanceFrequency'][0], 'unknown')  # [012]

            keywords = [k.strip() for l in [s.split(',') for s in data['keyword']] for k in l if k]
            if keywords:
                dataset.keywords.clear()
                for k in keywords:
                    dataset.keywords.add(k)

            root = ET.fromstring(request.POST.get('xml'))
            ns = {'gmd': 'http://www.isotc211.org/2005/gmd',
                  'gco': 'http://www.isotc211.org/2005/gco'}
            geonet_id = root.find('gmd:fileIdentifier/gco:CharacterString', ns).text

            record = ET.tostring(
                root, encoding='utf-8', method='xml', short_empty_elements=True)

            error = False
            if not geonet.get_record(geonet_id):
                try:
                    geonet.create_record(geonet_id, record)
                except Exception:
                    error = True
                    messages.error(
                        request, "La création de la fiche de métadonnées a échoué.")
                else:
                    # Toujours publier la fiche
                    geonet.publish(geonet_id)
                    dataset.geonet_id = geonet_id
                    messages.success(
                        request, "La fiche de metadonnées a été créée avec succès.")
            else:
                try:
                    geonet.update_record(geonet_id, record)
                except Exception:
                    error = True
                    messages.error(
                        request, "La mise à jour de la fiche de métadonnées a échoué.")
                else:
                    messages.success(
                        request, "La fiche de metadonnées a été mise à jour avec succès.")
            if not error:
                dataset.save(current_user=user, synchronize=True)

        if save_and_continue:
            reverse_to = reverse('idgo_admin:dataset_mdedit', kwargs={'id': id})
        else:
            reverse_to = reverse('idgo_admin:list_my_datasets')

        return HttpResponseRedirect(reverse_to)


@method_decorator(decorators, name='dispatch')
class ServiceMDEditTplEdit(View):

    template = 'idgo_admin/mdedit/template_service_edit.html'

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, id, *args, **kwargs):
        user, profile = user_and_profile(request)
        get_object_or_404(Organisation, id=id, is_active=True)
        return render(request, self.template)


@method_decorator(decorators, name='dispatch')
class ServiceMDEdit(View):

    template = 'idgo_admin/mdedit/service.html'
    namespace = 'idgo_admin:service_mdedit'

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, id, *args, **kwargs):
        user, profile = user_and_profile(request)
        instance = get_object_or_404(Organisation, id=id, is_active=True)

        config = {
            'app_name': 'mdEdit',
            'app_title': 'mdEdit',
            'app_version': '0.14.9',
            'app_copyrights': '(c) CIGAL 2016',
            'languages': {'locales': ['fr']},
            'defaultLanguage': 'fr',
            'server_url_md': GEONETWORK_URL,
            'views': {
                'list': [{
                    'path': reverse('idgo_admin:service_mdedit_tpl_edit', kwargs={'id': instance.id}),
                    'values': {'fr': 'Edition'},
                    'locales': {'fr': join_url('views/edit/tpl-edit_fr.json')}
                    }, {
                    'path': join_url('tpl-view.html', path=MDEDIT_HTML_PATH),
                    'values': {'fr': 'Vue'},
                    'locales': {'fr': join_url('views/view/tpl-view_fr.json')}
                    }]},
            'models': {
                'list': [{
                    'path': join_url(MDEDIT_SERVICE_MODEL),
                    'value': 'Modèle de fiche vierge'
                    }]},
            'locales': MDEDIT_LOCALES,
            'locales_path': join_url('locales/'),
            'geographicextents_list': join_url('list_geographicextents.json'),
            'referencesystems_list': join_url('list_referencesystems.json'),
            'static_root': join_url('libs/mdedit/', path=STATIC_URL),
            'modal_template': {
                'help': join_url('modal-help.html', path=MDEDIT_HTML_PATH)}}

        context = {'organisation': instance,
                   'doc_url': READTHEDOC_URL_INSPIRE,
                   'config': config}

        record = instance.geonet_id and geonet.get_record(str(instance.geonet_id)) or None

        if record:
            xml = record.xml.decode(encoding='utf-8')
            context['record_xml'] = re.sub('\n', '', xml).replace("'", "\\'")  # C'est moche
        else:
            context['record_obj'] = prefill_service_model(instance)

        return render_with_info_profile(request, self.template, context=context)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def post(self, request, id, *args, **kwargs):

        user, profile = user_and_profile(request)

        instance = get_object_or_404(Organisation, id=id, is_active=True)

        if not request.is_ajax():
            if 'delete' in request.POST and instance.geonet_id:
                try:
                    geonet.delete_record(instance.geonet_id)
                    instance.geonet_id = None
                    instance.save()
                except Exception as e:
                    messages.error(
                        request, "La fiche de metadonnées a été supprimée avec succès.")
                else:
                    messages.success(
                        request, "La fiche de metadonnées a été supprimée avec succès.")
            return HttpResponseRedirect(
                reverse(self.namespace, kwargs={'id': instance.id}))

        root = ET.fromstring(request.body)
        ns = {'gmd': 'http://www.isotc211.org/2005/gmd',
              'gco': 'http://www.isotc211.org/2005/gco'}
        id = root.find('gmd:fileIdentifier/gco:CharacterString', ns).text

        record = ET.tostring(
            root, encoding='utf-8', method='xml', short_empty_elements=True)

        if not geonet.is_record_exists(id):
            try:
                geonet.create_record(id, record)
            except Exception:
                messages.error(request, 'La création de la fiche de métadonnées a échoué.')
            else:
                geonet.publish(id)  # Toujours publier la fiche
                instance.geonet_id = id
                instance.save()
                messages.success(
                    request, 'La fiche de metadonnées a été créée avec succès.')
        else:
            try:
                geonet.update_record(id, record)
            except Exception:
                messages.error(request, 'La mise à jour de la fiche de métadonnées a échoué.')
            else:
                messages.success(
                    request, 'La fiche de metadonnées a été créée avec succès.')

        return HttpResponse()


@ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def mdhandler(request, type, *args, **kwargs):
    user, profile = user_and_profile(request)

    if type == 'dataset':
        target = Dataset
        namespace = 'idgo_admin:dataset_mdedit'
    elif type == 'service':
        target = Organisation
        namespace = 'idgo_admin:service_mdedit'

    instance = get_object_or_404(target, id=request.GET.get('id'))
    return redirect(reverse(namespace, kwargs={'id': instance.id}))
