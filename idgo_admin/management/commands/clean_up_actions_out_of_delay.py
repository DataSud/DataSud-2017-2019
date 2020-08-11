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


from django.core.management.base import BaseCommand
from django.utils import timezone
from idgo_admin.models import AccountActions
from idgo_admin.models import LiaisonsContributeurs
from idgo_admin.models import LiaisonsReferents


class Command(BaseCommand):

    help = 'Nettoyer les demandes obsolètes.'

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

    def n_days_ago(self, n):
        return timezone.now() - timezone.timedelta(days=n)

    def handle(self, *args, **options):

        del_org = []
        del_profile = []
        old_actions = AccountActions.objects.filter(
            closed=None, created_on__lte=self.n_days_ago(2))

        for act in old_actions:
            pro_name, org_name = 'N/A', 'N/A'

            if act.profile.user:
                pro_name = act.profile.user.username
            if act.profile.organisation:
                org_name = act.profile.organisation.legal_name

            if act.action == 'confirm_rattachement':
                print("clean_up_action Rattachement: {0}".format(pro_name))

            if act.action == 'confirm_mail':
                print("clean_up_action Profile: {0}".format(pro_name))
                del_profile.append(act.profile)

            if act.action == 'confirm_new_organisation':
                print("clean_up_action - New Orga: {0}".format(org_name))
                del_org.append(act.profile.organisation)

            if act.action == 'confirm_contribution':
                liaison = LiaisonsContributeurs.objects.get(
                    profile=act.profile, organisation=act.organisation)
                print("clean_up_action contribution: {0}-{1}".format(
                    pro_name, act.organisation.legal_name))
                liaison.delete()

            if act.action == 'confirm_referent':
                liaison = LiaisonsReferents.objects.get(
                    profile=act.profile, organisation=act.organisation)
                print("clean_up_action referent: {0}-{1}".format(
                    pro_name, act.organisation.legal_name))
                liaison.delete()

            if act.action == 'reset_password':
                print("clean_up_action Reset Password: {0}".format(act))

            act.delete()

        # Fait en second pour ne pas 'casser' la boucle précédente,
        # à cause des cascade_on_delete
        for p in del_profile:

            print("clean_up db - Profile: {0}".format(p.user.username))
            u = p.user
            p.delete()
            print("clean_up db - User: {0}".format(u.username))
            u.delete()

        for o in del_org:
            print("clean_up db - New Orga: {0}".format(o.name))
            o.delete()
