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


from collections import OrderedDict
import csv
from django.conf import settings
from django.contrib.postgres.aggregates import StringAgg
from django.db.models import Case
from django.db.models import CharField
from django.db.models import Count
from django.db.models import F
from django.db.models import Func
from django.db.models.functions import Concat
from django.db.models import Q
from django.db.models import Value
from django.db.models import When
from django.http import Http404
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.ckan_module import CkanHandler
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.exceptions import ProfileHttp404
from idgo_admin.models import Dataset
from idgo_admin.models import LiaisonsReferents
from idgo_admin.models import Profile
from idgo_admin.shortcuts import on_profile_http404
from idgo_admin.views.dataset import get_filtered_datasets
from operator import ior
import unicodecsv
from urllib.parse import urljoin
from uuid import UUID


# Définition des champs ODL :
COLL_NOM = F('organisation__legal_name')
COLL_SIRET = Value('', output_field=CharField())
ID = F('ckan_id')
TITRE = F('title')
DESCRIPTION = F('description')
THEME = StringAgg('categories__name', distinct=True, delimiter=';')
DIFFUSEUR = Case(
    When(
        Q(broadcaster_name__isnull=False) & ~Q(broadcaster_name=''),
        then=F('broadcaster_name')),
    When(
        (Q(broadcaster_name__isnull=True) | Q(broadcaster_name='')) & Q(support__isnull=False),
        then=F('support__name')),
    default=Value(settings.DEFAULT_PLATFORM_NAME),
    output_field=CharField())
PRODUCTEUR_NOM = F('organisation__legal_name')
PRODUCTEUR_SIRET = COLL_SIRET
COUV_SPAT_MAILLE = F('granularity')
COUV_SPAT_NOM = F('geocover')
COUV_TEMP_DEBUT = Value('', output_field=CharField())
COUV_TEMP_FIN = Value('', output_field=CharField())
DATE_PUBL = F('date_publication')
FREQ_MAJ = Case(*[
    When(Q(update_frequency=kvp[0]), then=Value(kvp[1]))
    for kvp in Dataset._meta.get_field('update_frequency').flatchoices],
    default=Value(''),
    output_field=CharField())
DATE_MAJ = F('date_modification')
MOTS_CLES = StringAgg('keywords__name', distinct=True, delimiter=';')
LICENCE = F('license__title')
NOMBRE_RESSOURCES = Count('resource')
FORMAT_RESSOURCES = Func(
    StringAgg('resource__format_type__extension', distinct=True, delimiter=';'),
    function='LOWER')
PROJECTION = StringAgg('resource__crs__auth_code', distinct=True, delimiter=';')
LANG = Value('FR', output_field=CharField())  # StringAgg('resource__lang', distinct=True, delimiter=';')
URL = Concat(
    Value(urljoin(settings.CKAN_URL, 'dataset/')), F('slug'),
    output_field=CharField())

# Définition des champs DATASUD :
DATASUD_ID = F('slug')
DATASUD_ORGA_ID = F('organisation__slug')
DATASUD_ORGA_URL = F('organisation__website')
DATASUD_PRODUCTEUR_NOM = F('owner_name')
DATASUD_PRODUCTEUR_EMAIL = F('owner_email')
DATASUD_DIFFUSEUR_NOM = F('broadcaster_name')
DATASUD_DIFFUSEUR_EMAIL = F('broadcaster_email')
DATASUD_COUV_TERR = F('granularity')
# DATASUD_INSPIRE =
# DATASUD_DATASET_URL =
# DATASUD_INSPIRE_URL =
# ..un ou plusieurs champs liens vers les APIs à précider.
# ..un ou plusieurs champs statistique à précider.
DATASUD_DATE_CREATION = F('date_creation')
# ..champs import/export (catalogue source, dernier moissonage, etc.)
# DATASUD_RESSOURCE_URLS =
# DATASUD_RESSOURCE_TAILLE =
DATASUD_RESSOURCE_TYPES = FORMAT_RESSOURCES  # ???

DATASUD_DATASET_VUES = Value('', output_field=CharField())
DATASUD_RESSOURCES_TELECHARGEMENT = Value('', output_field=CharField())
EXTRAS_TELECHARGEMENT = Value('', output_field=CharField())
DATASUD_DATASET_NOTE = Value('', output_field=CharField())
DATASUD_DATASET_NB_NOTES = Value('', output_field=CharField())


@method_decorator([csrf_exempt], name='dispatch')
class Export(View):

    def handle(self, request, *args, **kwargs):

        user = request.user
        if user.is_anonymous:
            profile = None
        else:
            try:
                profile = get_object_or_404(Profile, user=user)
            except Exception:
                raise ProfileHttp404

        qs = request.POST or request.GET

        outputformat = qs.get('format')
        if not outputformat or outputformat not in ('odl', 'datasud'):
            raise Http404()

        if outputformat == 'odl':
            annotate = OrderedDict((
                ('COLL_NOM', COLL_NOM),
                ('COLL_SIRET', COLL_SIRET),
                ('ID', ID),
                ('TITRE', TITRE),
                ('DESCRIPTION', DESCRIPTION),
                ('THEME', THEME),
                # ('DIFFUSEUR', DIFFUSEUR),
                ('PRODUCTEUR_NOM', PRODUCTEUR_NOM),
                ('PRODUCTEUR_SIRET', PRODUCTEUR_SIRET),
                ('COUV_SPAT_MAILLE', COUV_SPAT_MAILLE),
                ('COUV_SPAT_NOM', COUV_SPAT_NOM),
                ('COUV_TEMP_DEBUT', COUV_TEMP_DEBUT),
                ('COUV_TEMP_FIN', COUV_TEMP_DEBUT),
                ('DATE_PUBL', DATE_PUBL),
                ('FREQ_MAJ', FREQ_MAJ),
                ('DATE_MAJ', DATE_MAJ),
                ('MOTS_CLES', MOTS_CLES),
                ('LICENCE', LICENCE),
                ('NOMBRE_RESSOURCES', NOMBRE_RESSOURCES),
                ('FORMAT_RESSOURCES', FORMAT_RESSOURCES),
                # ('PROJECTION', PROJECTION),
                # ('LANG', LANG),
                ('URL', URL)
                ))
        else:
            annotate = OrderedDict((
                ('COLL_NOM', COLL_NOM),
                ('COLL_SIRET', COLL_SIRET),
                ('ID', ID),
                ('TITRE', TITRE),
                ('DESCRIPTION', DESCRIPTION),
                ('THEME', THEME),
                ('PRODUCTEUR_NOM', PRODUCTEUR_NOM),
                ('PRODUCTEUR_SIRET', PRODUCTEUR_SIRET),
                ('COUV_SPAT_MAILLE', COUV_SPAT_MAILLE),
                ('COUV_SPAT_NOM', COUV_SPAT_NOM),
                ('COUV_TEMP_DEBUT', COUV_TEMP_DEBUT),
                ('COUV_TEMP_FIN', COUV_TEMP_DEBUT),
                ('DATE_PUBL', DATE_PUBL),
                ('FREQ_MAJ', FREQ_MAJ),
                ('DATE_MAJ', DATE_MAJ),
                ('MOTS_CLES', MOTS_CLES),
                ('LICENCE', LICENCE),
                ('NOMBRE_RESSOURCES', NOMBRE_RESSOURCES),
                ('FORMAT_RESSOURCES', FORMAT_RESSOURCES),
                ('URL', URL),
                ('DATASUD_ID', DATASUD_ID),
                # ('DATASUD_MOT_CLES', DATASUD_MOT_CLES),
                # ('DATASUD_ORGA', DATASUD_ORGA),
                ('DATASUD_ORGA_ID', DATASUD_ORGA_ID),
                ('DATASUD_ORGA_URL', DATASUD_ORGA_URL),
                ('DATASUD_PRODUCTEUR_NOM', DATASUD_PRODUCTEUR_NOM),
                # ('DATASUD_PRODUCTEUR_EMAIL', DATASUD_PRODUCTEUR_EMAIL),
                ('DATASUD_DIFFUSEUR_NOM', DATASUD_DIFFUSEUR_NOM),
                # ('DATASUD_DIFFUSEUR_EMAIL', DATASUD_DIFFUSEUR_EMAIL),
                ('DATASUD_COUV_TERR', DATASUD_COUV_TERR),
                # ('DATASUD_INSPIRE', DATASUD_INSPIRE),
                # ('DATASUD_DATASET_URL', DATASUD_DATASET_URL),
                # ('DATASUD_INSPIRE_URL', DATASUD_INSPIRE_URL),
                ('DATASUD_DATE_CREATION', DATASUD_DATE_CREATION),
                # ('DATASUD_RESSOURCE_URLS', DATASUD_RESSOURCE_URLS),
                # ('DATASUD_RESSOURCE_TAILLE', DATASUD_RESSOURCE_TAILLE),
                ('DATASUD_RESSOURCE_TYPES', DATASUD_RESSOURCE_TYPES),
                ('DATASUD_DATASET_VUES', DATASUD_DATASET_VUES),
                ('DATASUD_RESSOURCES_TELECHARGEMENT', DATASUD_RESSOURCES_TELECHARGEMENT),
                ('DATASUD_DATASET_NOTE', DATASUD_DATASET_NOTE),
                ('DATASUD_DATASET_NB_NOTES', DATASUD_DATASET_NB_NOTES),
                ('DIFFUSEUR', DIFFUSEUR),
                ('PROJECTION', PROJECTION),
                ('LANG', LANG),
                ))

        values = list(annotate.keys())

        if not profile:
            ids = qs.get('ids', '').split(',')
            datasets = Dataset.objects.filter(ckan_id__in=[UUID(id) for id in ids])
        elif 'mode' in qs:
            mode = qs.get('mode')
            if mode == 'all':
                roles = profile.get_roles()
                if roles['is_admin']:
                    QuerySet = Dataset.default.all()
                elif roles['is_referent']:
                    kwargs = {'profile': profile, 'validated_on__isnull': False}
                    organisation__in = set(
                        instance.organisation for instance
                        in LiaisonsReferents.objects.filter(**kwargs))
                    filter = ior(Q(editor=user), Q(organisation__in=organisation__in))
                    QuerySet = Dataset.default.filter(filter)
            elif mode == 'mine':
                QuerySet = Dataset.default.filter(editor=user)
            elif mode == 'ckan_harvested':
                QuerySet = Dataset.harvested_ckan
            elif mode == 'csw_harvested':
                QuerySet = Dataset.harvested_csw
            else:
                raise Http404()
            datasets = get_filtered_datasets(QuerySet, qs)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=dataset_export.csv'
        response['Cache-Control'] = 'no-cache'

        writer = unicodecsv.writer(response, encoding='utf-8', quoting=csv.QUOTE_ALL, delimiter=',', quotechar='"')
        writer.writerow(values)
        for row in datasets.annotate(**annotate).values(*values):
            if not outputformat == 'odl':
                package = CkanHandler.get_package(str(row['ID']), include_tracking=True)

                dataset_view = 0
                if 'tracking_summary' in package:
                    dataset_view = package['tracking_summary'].get('total')
                row['DATASUD_DATASET_VUES'] = dataset_view

                resources_dl = 0
                for resource in package.get('resources'):
                    if 'tracking_summary' in resource:
                        resources_dl += int(resource['tracking_summary'].get('total'))
                row['DATASUD_RESSOURCES_TELECHARGEMENT'] = resources_dl
                row['DATASUD_DATASET_NOTE'] = package.get('rating')
                row['DATASUD_DATASET_NB_NOTES'] = package.get('ratings_count')

            writer.writerow([row[value] for value in values])

        return response

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, *args, **kwargs):
        return self.handle(request, *args, **kwargs)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def post(self, request, *args, **kwargs):
        return self.handle(request, *args, **kwargs)
