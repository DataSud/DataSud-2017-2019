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
from django.conf.urls.static import static
from django.conf.urls import url
from idgo_admin.views.account import create_sftp_account
from idgo_admin.views.account import delete_account
from idgo_admin.views.account import delete_sftp_account
from idgo_admin.views.account import PasswordManager
from idgo_admin.views.account import ReferentAccountManager
from idgo_admin.views.account import SignUp
from idgo_admin.views.account import UpdateAccount
from idgo_admin.views.action import ActionsManager
from idgo_admin.views.dataset import DatasetManager
from idgo_admin.views.dataset import list_all_ckan_harvested_datasets
from idgo_admin.views.dataset import list_all_csw_harvested_datasets
from idgo_admin.views.dataset import list_all_dcat_harvested_datasets
from idgo_admin.views.dataset import list_all_datasets
from idgo_admin.views.dataset import list_dataset
from idgo_admin.views.dataset import list_my_datasets
from idgo_admin.views.export import Export
from idgo_admin.views.extractor import Extractor
from idgo_admin.views.extractor import extractor_task
from idgo_admin.views.extractor import ExtractorDashboard
from idgo_admin.views.gdpr import GdprView
from idgo_admin.views import home
from idgo_admin.views.jurisdiction import jurisdiction
from idgo_admin.views.jurisdiction import jurisdictions
from idgo_admin.views.jurisdiction import JurisdictionView
from idgo_admin.views.layer import layer_style
from idgo_admin.views.layer import LayerStyleEditorView
from idgo_admin.views.layer import LayerView
from idgo_admin.views.mailer import confirm_contribution
from idgo_admin.views.mailer import confirm_new_orga
from idgo_admin.views.mailer import confirm_rattachement
from idgo_admin.views.mailer import confirm_referent
from idgo_admin.views.mailer import confirmation_mail
from idgo_admin.views.mdedit import DatasetMDEdit
from idgo_admin.views.mdedit import DatasetMDEditTplEdit
from idgo_admin.views.mdedit import mdhandler
from idgo_admin.views.mdedit import ServiceMDEdit
from idgo_admin.views.mdedit import ServiceMDEditTplEdit
from idgo_admin.views.organisation import CreateOrganisation
from idgo_admin.views.organisation import crige_partnership
from idgo_admin.views.organisation import DeleteRemoteCkanLinked
from idgo_admin.views.organisation import DeleteRemoteCswLinked
from idgo_admin.views.organisation import DeleteRemoteDcatLinked
from idgo_admin.views.organisation import handle_show_organisation
from idgo_admin.views.organisation import OrganisationOWS
from idgo_admin.views.organisation import RemoteCkanEditor
from idgo_admin.views.organisation import RemoteCswEditor
from idgo_admin.views.organisation import RemoteDcatEditor
from idgo_admin.views.organisation import show_organisation
from idgo_admin.views.organisation import Subscription
from idgo_admin.views.organisation import UpdateOrganisation
from idgo_admin.views.resource import resource
from idgo_admin.views.resource import ResourceManager
from idgo_admin.views.sld_preview import SLDPreviewGetter
from idgo_admin.views.sld_preview import SLDPreviewSetter
from idgo_admin.views.stuffs import DisplayLicenses
from idgo_admin.views.stuffs import ows_preview


urlpatterns = [
    url('^$', home, name='home'),

    url('^account/create/?$', SignUp.as_view(), name='sign_up'),
    url('^account/update/?$', UpdateAccount.as_view(), name='update_account'),
    url('^account/delete/?$', delete_account, name='deleteAccount'),

    url('^account/sftp/create/?$', create_sftp_account, name='create_sftp_account'),
    url('^account/sftp/delete/?$', delete_sftp_account, name='delete_sftp_account'),

    url('^dataset/?$', list_dataset, name='dataset'),  # ?id=[<dataset.pk>|<dataset.slug>]
    url('^dataset/mine/?$', list_my_datasets, name='list_my_datasets'),
    url('^dataset/all/?$', list_all_datasets, name='list_all_datasets'),
    url('^dataset/harvested/ckan/?$', list_all_ckan_harvested_datasets, name='list_all_ckan_harvested_datasets'),
    url('^dataset/harvested/csw/?$', list_all_csw_harvested_datasets, name='list_all_csw_harvested_datasets'),
    url('^dataset/harvested/dcat/?$', list_all_dcat_harvested_datasets, name='list_all_dcat_harvested_datasets'),
    url('^dataset/(?P<id>(new|(\d+)))/edit/?$', DatasetManager.as_view(), name='dataset_editor'),

    url('^resource/?$', resource, name='resources'),
    url('^dataset/(?P<dataset_id>(\d+))/resource/?$', ResourceManager.as_view(), name='resource'),
    url('^dataset/(?P<dataset_id>(\d+))/resource/(?P<resource_id>(\d+))/layer/(?P<layer_id>([a-z0-9_]*))/edit/?$', LayerView.as_view(), name='layer_editor'),
    url('^dataset/(?P<dataset_id>(\d+))/resource/(?P<resource_id>(\d+))/layer/(?P<layer_id>([a-z0-9_]*))/style/?$', layer_style, name='layer_style'),
    url('^dataset/(?P<dataset_id>(\d+))/resource/(?P<resource_id>(\d+))/layer/(?P<layer_id>([a-z0-9_]*))/style/default/edit/?$', LayerStyleEditorView.as_view(), name='layer_style_editor'),

    url('^dataset/export/?$', Export.as_view(), name='export'),

    url('^extractor/?$', Extractor.as_view(), name='extractor'),
    url('^extractor/task/?$', extractor_task, name='extractor_task'),
    url('^extractor/dashboard/?$', ExtractorDashboard.as_view(), name='extractor_dashboard'),

    url('^terms/?$', GdprView.as_view(), name='terms_agreement'),

    url('^jurisdiction/?$', jurisdiction, name='jurisdiction'),
    url('^jurisdiction/all/?$', jurisdictions, name='jurisdictions'),
    url('^jurisdiction/(?P<code>(for|new|(.+)))/edit/?$', JurisdictionView.as_view(), name='jurisdiction_editor'),

    url('^mdedit/(?P<type>(dataset|service))/?$', mdhandler, name='mdhandler'),
    url('^mdedit/dataset/(?P<id>(\d+))/?$', DatasetMDEdit.as_view(), name='dataset_mdedit'),
    url('^mdedit/dataset/(?P<id>(\d+))/edit/?$', DatasetMDEditTplEdit.as_view(), name='dataset_mdedit_tpl_edit'),
    url('^mdedit/service/(?P<id>(\d+))/?$', ServiceMDEdit.as_view(), name='service_mdedit'),
    url('^mdedit/service/(?P<id>(\d+))/edit/?$', ServiceMDEditTplEdit.as_view(), name='service_mdedit_tpl_edit'),

    url('^member/all/?$', ReferentAccountManager.as_view(), name='all_members'),

    url('^organisation(/all)?/?$', handle_show_organisation, name='handle_show_organisation'),
    url('^organisation/(?P<id>(\d+))/show/?$', show_organisation, name='show_organisation'),
    url('^organisation/new/edit/?$', CreateOrganisation.as_view(), name='create_organisation'),
    url('^organisation/(?P<id>(\d+))/edit/?$', UpdateOrganisation.as_view(), name='update_organisation'),

    url('^organisation/ows/?$', OrganisationOWS.as_view(), name='organisation_ows'),
    url('^organisation/(?P<status>(member|contributor|referent))/(?P<subscription>(subscribe|unsubscribe))?$', Subscription.as_view(), name='subscription'),

    url('^organisation/crige/?$', crige_partnership, name='crige_partnership'),

    url('^organisation/(?P<id>(\d+))/remoteckan/edit/?$', RemoteCkanEditor.as_view(), name='edit_remote_ckan_link'),
    url('^organisation/(?P<id>(\d+))/remoteckan/delete/?$', DeleteRemoteCkanLinked.as_view(), name='delete_remote_ckan_link'),
    url('^organisation/(?P<id>(\d+))/remotecsw/edit/?$', RemoteCswEditor.as_view(), name='edit_remote_csw_link'),
    url('^organisation/(?P<id>(\d+))/remotecsw/delete/?$', DeleteRemoteCswLinked.as_view(), name='delete_remote_csw_link'),
    url('^organisation/(?P<id>(\d+))/remotedcat/edit/?$', RemoteDcatEditor.as_view(), name='edit_remote_dcat_link'),
    url('^organisation/(?P<id>(\d+))/remotedcat/delete/?$', DeleteRemoteDcatLinked.as_view(), name='delete_remote_dcat_link'),

    url('^password/(?P<process>(forget))/?$', PasswordManager.as_view(), name='password_manager'),
    url('^password/(?P<process>(initiate|reset))/(?P<key>(.+))/?$', PasswordManager.as_view(), name='password_manager'),

    url('^confirmation/email/(?P<key>.+)/?$', confirmation_mail, name='confirmation_mail'),
    url('^confirmation/createorganisation/(?P<key>.+)/?$', confirm_new_orga, name='confirm_new_orga'),
    url('^confirmation/rattachment/(?P<key>.+)/?$', confirm_rattachement, name='confirm_rattachement'),
    url('^confirmation/contribute/(?P<key>.+)/?$', confirm_contribution, name='confirm_contribution'),
    url('^confirmation/referent/(?P<key>.+)/?$', confirm_referent, name='confirm_referent'),

    url('^action/?$', ActionsManager.as_view(), name='action'),
    url('^licences/?$', DisplayLicenses.as_view(), name='licences'),

    url('^owspreview/?$', ows_preview, name='ows_preview'),
    url('^sldpreview/?$', SLDPreviewSetter.as_view(), name='sld_preview_setter'),
    url('^sldpreview/(?P<key>.+)\.sld$', SLDPreviewGetter.as_view(), name='sld_preview_getter'),
    ]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
