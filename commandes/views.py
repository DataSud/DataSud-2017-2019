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


from commandes.forms import OrderForm
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from idgo_admin.models.mail import sender as mail_sender
from idgo_admin.models import Organisation
from idgo_admin.models import Profile
from idgo_admin.shortcuts import user_and_profile


# CKAN_URL = settings.CKAN_URL

decorators = [login_required(login_url=settings.LOGIN_URL)]

TODAY = timezone.now().date()

CADASTRE_CONTACT_EMAIL = settings.CADASTRE_CONTACT_EMAIL


@login_required(login_url=settings.LOGIN_URL)
def upload_file(request):

    user = request.user
    user, profile = user_and_profile(request)
    if not profile.crige_membership:
        raise Http404

    if request.method == 'POST':
        # crée une instance formulaire et la peuple avec des données provenant de la requête
        form = OrderForm(request.POST, request.FILES, user=request.user)

        if form.is_valid():
            order = form.save(commit=False)
            # peuplement de l'instance applicant du modèle form (= user_id)
            order.applicant = request.user
            order.organisation = Organisation.objects.get(id=Profile.objects.get(user_id=request.user).organisation_id)
            order.save()

            attach_files = [
                order.dpo_cnil.file.name,
                order.acte_engagement.file.name]

            mail_kwargs = {
                'attach_files': attach_files,
                'full_name': user.get_full_name(),
                'last_name': user.last_name,
                'first_name': user.first_name,
                'date': TODAY.strftime('%d/%m/%Y'),
                'email': user.email}

            mail_sender('cadastre_order', to=[user.email], **mail_kwargs)
            mail_sender(
                'confirm_cadastre_order',
                to=[CADASTRE_CONTACT_EMAIL],
                url=request.build_absolute_uri(
                    reverse('admin:commandes_order_change', args=(order.id,))),
                **mail_kwargs)

            # page de confirmation
            messageOrder = ("Votre commande de fichiers fonciers "
                            'a bien été envoyée.'
                            ' Vous recevrez un e-mail récapitulatif '
                            "d'ici quelques minutes. ")

            return render(request, 'idgo_admin/message.html',
                          {'message': messageOrder})

    # si on reçoit un GET (ou autre méthode) un formulaire vide est renvoyé
    else:
        form = OrderForm(user=request.user)
    return render(request, 'commandes/commandes.html', {'form': form})
