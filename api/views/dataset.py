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
from django.db import transaction
from django.http import Http404
from django.http import HttpResponse
from django.http import JsonResponse
from idgo_admin.exceptions import CkanBaseError
from idgo_admin.exceptions import GenericException
from idgo_admin.forms.dataset import DatasetForm as Form
from idgo_admin.geonet_module import GeonetUserHandler as geonet
from idgo_admin.models import Category
from idgo_admin.models import Dataset
from idgo_admin.models import DataType
from idgo_admin.models import License
from idgo_admin.models.mail import send_dataset_creation_mail
from idgo_admin.models.mail import send_dataset_delete_mail
from idgo_admin.models.mail import send_dataset_update_mail
from idgo_admin.models import Organisation
from rest_framework import permissions
from rest_framework.views import APIView
import xml.etree.ElementTree as ET


def serialize(dataset):

    if dataset.keywords:
        keywords = [
            keyword.name for keyword in dataset.keywords.all()]
    else:
        keywords = None

    if dataset.categories:
        categories = [
            category.slug for category in dataset.categories.all()]
    else:
        categories = None

    if dataset.organisation:
        organisation = dataset.organisation.slug
    else:
        organisation = None

    if dataset.license:
        license = dataset.license.slug
    else:
        license = None

    if dataset.data_type:
        data_type = [
            data_type.slug for data_type in dataset.data_type.all()]
    else:
        data_type = None

    if dataset.granularity:
        granularity = dataset.granularity.slug
    else:
        granularity = None

    if dataset.bbox:
        minx, miny, maxx, maxy = dataset.bbox.extent
        extent = [[miny, minx], [maxy, maxx]]
    else:
        extent = None

    return OrderedDict([
        ('name', dataset.slug),
        ('title', dataset.title),
        ('description', dataset.description),
        ('keywords', keywords),
        ('categories', categories),
        ('date_creation', dataset.date_creation),
        ('date_modification', dataset.date_modification),
        ('date_publication', dataset.date_publication),
        ('update_frequency', dataset.update_frequency),
        ('geocover', dataset.geocover),
        ('organisation', organisation),
        ('license', license),
        ('type', data_type),
        ('private', dataset.private),
        ('owner_name', dataset.owner_name),
        ('owner_email', dataset.owner_email),
        ('broadcaster_name', dataset.broadcaster_name),
        ('broadcaster_email', dataset.broadcaster_email),
        ('granularity', granularity),
        ('extent', extent),
        ])


def handler_get_request(request):
    user = request.user
    if user.profile.is_admin:
        datasets = Dataset.objects.all()
    else:
        s1 = set(Dataset.objects.filter(organisation__in=user.profile.referent_for))
        s2 = set(Dataset.objects.filter(editor=user))
        datasets = list(s1 | s2)
    return datasets


def handle_pust_request(request, dataset_name=None):
    # name -> slug
    # type -> data_type
    # categories/category -> categories
    # private -> published

    user = request.user
    dataset = None
    if dataset_name:
        for instance in handler_get_request(request):
            if instance.slug == dataset_name:
                dataset = instance
                break
        if not instance:
            raise Http404()

    query_data = getattr(request, request.method)  # QueryDict

    # Forcer l'éditeur (attention privilège d'admin)
    editor = None
    if user.profile.is_admin:
        editor = query_data.pop('editor', None)
        if editor:
            try:
                editor = User.objects.get(username=editor[-1])
            except User.DoesNotExist as e:
                raise GenericException(details={'editor': e.__str__()})

    # slug/name
    slug = query_data.pop('name', dataset and [dataset.slug])
    if slug:
        query_data.__setitem__('slug', slug[-1])

    # `title` est obligatoire
    title = query_data.pop('title', dataset and [dataset.title])
    if title:
        query_data.__setitem__('title', title[-1])

    # `organisation`
    organisation_slug = query_data.pop('organisation', None)
    if organisation_slug:
        try:
            organisation = Organisation.objects.get(slug=organisation_slug[-1])
        except Organisation.DoesNotExist as e:
            raise GenericException(details=e.__str__())
    elif dataset:
        organisation = dataset.organisation
    else:
        organisation = None
    if organisation:
        query_data.__setitem__('organisation', organisation.pk)

    # `licence`
    license_slug = query_data.pop('license', None)
    if license_slug:
        try:
            license = License.objects.get(slug=license_slug[-1])
        except License.DoesNotExist as e:
            raise GenericException(details=e.__str__())
    elif dataset:
        license = dataset.license
    else:
        license = None
    if license:
        query_data.__setitem__('license', license.pk)

    # `categories`
    category_slugs = query_data.pop('categories', query_data.pop('category', None))
    if category_slugs:
        try:
            categories = Category.objects.filter(slug__in=category_slugs)
        except Category.DoesNotExist as e:
            raise GenericException(details=e.__str__())
    elif dataset:
        categories = dataset.categories.all()
    else:
        categories = None
    if categories:
        query_data.setlist('categories', [instance.pk for instance in categories])

    # `data_type`
    data_type_slugs = query_data.pop('types', query_data.pop('type', query_data.pop('data_type', None)))
    if data_type_slugs:
        try:
            data_type = DataType.objects.filter(slug__in=data_type_slugs)
        except DataType.DoesNotExist as e:
            raise GenericException(details=e.__str__())
    elif dataset:
        data_type = dataset.data_type.all()
    else:
        data_type = None
    if data_type:
        query_data.setlist('data_type', [instance.pk for instance in data_type])

    # `keywords`
    keyword_tags = query_data.pop('keywords', query_data.pop('keyword', None))
    if keyword_tags:
        query_data.__setitem__('keywords', ','.join(keyword_tags))

    # `published` or `private`
    published = query_data.pop('published', None)
    private = query_data.pop('private', None)
    if (published and published[-1].lower() in ('on', 'true',)) or \
            (private and private[-1].lower() in ('off', 'false',)):
        query_data.__setitem__('published', True)
    elif (published and published[-1].lower() in ('off', 'false',)) or \
            (private and private[-1].lower() in ('on', 'true',)):
        query_data.__setitem__('published', False)

    pk = dataset and dataset.pk or None
    include = {'user': editor or user, 'id': pk, 'identification': pk and True or False}

    # TODO: Extent
    extent = query_data.pop('extent', None)

    form = Form(query_data, request.FILES, instance=dataset, include=include)
    if not form.is_valid():
        raise GenericException(details=form._errors)

    data = form.cleaned_data
    kvp = {
        'title': data['title'],
        'slug': data['slug'],
        'description': data['description'],
        'thumbnail': data['thumbnail'],
        # keywords
        # categories
        'date_creation': data['date_creation'],
        'date_modification': data['date_modification'],
        'date_publication': data['date_publication'],
        'update_frequency': data['update_frequency'],
        'geocover': data['geocover'],
        'granularity': data['granularity'],
        'organisation': data['organisation'],
        'license': data['license'],
        'support': data['support'],
        # data_type
        'owner_email': data['owner_email'],
        'owner_name': data['owner_name'],
        'broadcaster_name': data['broadcaster_name'],
        'broadcaster_email': data['broadcaster_email'],
        'published': data['published'],
        }

    try:
        with transaction.atomic():
            if dataset:
                for k, v in kvp.items():
                    setattr(dataset, k, v)
            else:
                kvp['editor'] = editor or user
                save_opts = {'current_user': user, 'synchronize': False}
                dataset = Dataset.default.create(save_opts=save_opts, **kvp)
            # categories
            categories = Category.objects.filter(pk__in=data.get('categories'))
            dataset.categories.set(categories, clear=True)
            # data_type
            data_type = DataType.objects.filter(pk__in=data.get('data_type'))
            dataset.data_type.set(data_type, clear=True)
            # keywords
            keywords = data.get('keywords')
            if keywords:
                dataset.keywords.clear()
                for k in keywords:
                    dataset.keywords.add(k)
            dataset.save(current_user=user, synchronize=True)
    except ValidationError as e:
        form.add_error('__all__', e.__str__())
    except CkanBaseError as e:
        form.add_error('__all__', e.__str__())
    else:
        if dataset_name:
            send_dataset_update_mail(user, dataset)
        else:
            send_dataset_creation_mail(user, dataset)
        return dataset
    raise GenericException(details=form.__str__())


class DatasetShow(APIView):

    permission_classes = [
        permissions.IsAuthenticated,
        ]

    def get(self, request, dataset_name):
        """Voir le jeu de données."""
        datasets = handler_get_request(request)
        for dataset in datasets:
            if dataset.slug == dataset_name:
                return JsonResponse(serialize(dataset), safe=True)
        raise Http404()

    def put(self, request, dataset_name):
        """Modifier le jeu de données."""
        request.PUT, request._files = parse_request(request)
        request.PUT._mutable = True
        try:
            handle_pust_request(request, dataset_name=dataset_name)
        except Http404:
            raise Http404()
        except GenericException as e:
            return JsonResponse({'error': e.details}, status=400)
        return HttpResponse(status=204)

    def delete(self, request, dataset_name):
        """Supprimer le jeu de données."""
        instance = None
        for dataset in handler_get_request(request):
            if dataset.slug == dataset_name:
                instance = dataset
                break
        if not instance:
            raise Http404()
        instance.delete(current_user=request.user)
        send_dataset_delete_mail(request.user, instance)
        return HttpResponse(status=204)


class DatasetList(APIView):

    permission_classes = [
        permissions.IsAuthenticated,
        ]

    def get(self, request):
        """Voir les jeux de données."""

        datasets = handler_get_request(request)
        return JsonResponse(
            [serialize(dataset) for dataset in datasets], safe=False)

    def post(self, request):
        """Créer un nouveau jeu de données."""
        request.POST._mutable = True
        try:
            dataset = handle_pust_request(request)
        except Http404:
            raise Http404()
        except GenericException as e:
            return JsonResponse({'error': e.details}, status=400)
        response = HttpResponse(status=201)
        response['Content-Location'] = dataset.api_location
        return response


class DatasetMDShow(APIView):

    permission_classes = [
        permissions.IsAuthenticated,
        ]

    def get(self, request, dataset_name):
        """Voir la fiche de metadonnées du jeu de données."""
        instance = None
        for dataset in handler_get_request(request):
            if dataset.slug == dataset_name:
                instance = dataset
                break
        if not instance or (instance and not instance.geonet_id):
            raise Http404()
        try:
            record = geonet.get_record(str(instance.geonet_id))
        except Exception as e:
            return JsonResponse({'error': e.__str__()}, status=400)
        else:
            return HttpResponse(record.xml, content_type='application/xml')

    def put(self, request, dataset_name):
        """Enregistrer la ficher de métadonnées du jeu de données."""
        request.PUT, _ = parse_request(request)
        request.PUT._mutable = True

        instance = None
        for dataset in handler_get_request(request):
            if dataset.slug == dataset_name:
                instance = dataset
                break
        if not instance:
            raise Http404()

        root = ET.fromstring(request.PUT.get('xml'))
        ns = {'gmd': 'http://www.isotc211.org/2005/gmd',
              'gco': 'http://www.isotc211.org/2005/gco'}
        geonet_id = root.find('gmd:fileIdentifier/gco:CharacterString', ns).text
        if not geonet_id:
            return JsonResponse({'error': 'fileIdentifier not found'}, status=400)

        record = ET.tostring(
            root, encoding='utf-8', method='xml', short_empty_elements=True)
        try:
            if not geonet.get_record(geonet_id):
                try:
                    geonet.create_record(geonet_id, record)
                except Exception as e:
                    return JsonResponse({'error': e.__str__()}, status=400)
                else:
                    geonet.publish(geonet_id)
                    dataset.geonet_id = geonet_id
            else:
                try:
                    geonet.update_record(geonet_id, record)
                except Exception as e:
                    return JsonResponse({'error': e.__str__()}, status=400)
            dataset.save(synchronize=True)

        except GenericException as e:
            return JsonResponse({'error': e.details}, status=400)

        return HttpResponse(status=204)
