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
from django.contrib.auth.models import User
from django.http import HttpResponse
from idgo_admin.models.mail import sender as mail_sender
import unicodecsv
import webbrowser


try:
    CC_EMAIL = settings.CC_EMAIL
except AttributeError:
    CC_EMAIL = ['support.cadastre@crige-paca.org']


def export_as_csv_action(description="Export selected objects as CSV file",
                         fields=None, exclude=None, header=True):
    """Return an export csv action.

    'fields' and 'exclude' work like in django ModelForm.
    'header' is whether or not to output the column names as the first row.
    """
    def export_as_csv_cadastre(modeladmin, request, queryset):
        opts = modeladmin.model._meta

        if not fields:
            field_names = [field.name for field in opts.fields]
        else:
            field_names = fields
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=%s.csv' % str(opts).replace('.', '_')

        writer = unicodecsv.writer(response, encoding='utf-8')
        if header:
            custom_fild_names = field_names.copy()
            custom_fild_names.append('email')
            custom_fild_names.append('territoire')
            custom_fild_names.append('communes')
            writer.writerow(custom_fild_names)
        for obj in queryset:
            row = [getattr(obj, field)() if callable(getattr(obj, field)) else getattr(obj, field) for field in field_names]
            email = User.objects.get(username=row[3]).email
            row.append(email)
            jurisdiction = obj.organisation.jurisdiction
            if jurisdiction:
                row.append(jurisdiction.name)
                row.append(', '.join(x.code for x in jurisdiction.communes.all()))
            # else:
            #     row.append('')
            #     row.append('')
            writer.writerow(row)
        return response
    export_as_csv_cadastre.short_description = description
    return export_as_csv_cadastre


def mail_list(modeladmin, request, queryset):
    mailList = []
    for obj in queryset:
        user = getattr(obj, 'applicant')
        email = User.objects.get(username=user).email
        mailList.append(email)
    return(mailList)


def mail_date_organisation(modeladmin, request, queryset, obj):
    user = getattr(obj, 'applicant')
    emailInfo = dict(
        email=User.objects.get(username=user).email,
        organisation=getattr(obj, 'organisation'),
        date=getattr(obj, 'date'))
    return emailInfo


def send_multiple_emails(modeladmin, request, queryset):
    mailList = mail_list(modeladmin, request, queryset)
    return webbrowser.open('mailto:?to={0}, &subject={1}'.format(','.join(mailList), 'Commande fichiers fonciers'))
    send_multiple_emails.short_description = "Envoyer un email"


def email_cadastre_wrong_files(modeladmin, request, queryset):

    for obj in queryset:
        emailInfo = mail_date_organisation(modeladmin, request, queryset, obj)
        mail_sender(
            'cadastre_wrong_file',
            to=[emailInfo["email"]],
            cc=CC_EMAIL,
            date=emailInfo["date"],
            organisation=emailInfo["organisation"])


def email_cadastre_habilitation(modeladmin, request, queryset):

    for obj in queryset:
        emailInfo = mail_date_organisation(modeladmin, request, queryset, obj)
        mail_sender(
            'cadastre_no_habilitation',
            to=[emailInfo["email"]],
            cc=CC_EMAIL,
            date=emailInfo["date"],
            organisation=emailInfo["organisation"])
