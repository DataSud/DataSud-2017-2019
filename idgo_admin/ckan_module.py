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


import ast
from ckanapi import errors as CkanError
from ckanapi import RemoteCKAN
from datetime import datetime
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from functools import wraps
from idgo_admin.exceptions import CkanBaseError
from idgo_admin import logger
from idgo_admin.utils import Singleton
import inspect
import os
import timeout_decorator
import unicodedata
from urllib.parse import urljoin


CKAN_URL = settings.CKAN_URL
CKAN_API_KEY = settings.CKAN_API_KEY
try:
    CKAN_TIMEOUT = settings.GEONET_TIMEOUT
except AttributeError:
    CKAN_TIMEOUT = 36000


def timeout(fun):
    t = CKAN_TIMEOUT  # in seconds

    @timeout_decorator.timeout(t, use_signals=False)
    def return_with_timeout(fun, args=tuple(), kwargs=dict()):
        return fun(*args, **kwargs)

    @wraps(fun)
    def wrapper(*args, **kwargs):
        return return_with_timeout(fun, args=args, kwargs=kwargs)

    return wrapper


class CkanReadError(CkanBaseError):
    message = "L'url ne semble pas indiquer un site CKAN."


class CkanApiError(CkanBaseError):
    message = "L'API CKAN n'est pas accessible."


class CkanTimeoutError(CkanBaseError):
    message = 'Le site CKAN met du temps à répondre, celui-ci est peut-être temporairement inaccessible.'


class CkanNotFoundError(CkanBaseError):
    message = 'La ressource CKAN ne semble pas exister.'


class CkanConflictError(CkanBaseError):
    message = 'La ressource CKAN existe déjà.'


class CkanSyncingError(CkanBaseError):
    message = "Une erreur de synchronisation avec l'instance de CKAN est survenue."

    def __init__(self, *args, **kwargs):
        for item in self.args:
            try:
                m = ast.literal_eval(item)
            except Exception:
                continue
            if isinstance(m, dict):
                kwargs.update(**m)
        super().__init__(*args, **kwargs)

    def __str__(self):
        try:
            return '{} {}'.format(self.message, ' '.join(self.name))
        except AttributeError:
            return super().__str__()


class CkanExceptionsHandler(object):

    def __init__(self, ignore=None):
        self.ignore = ignore or []

    def __call__(self, f):
        @wraps(f)
        def wrapper(*args, **kwargs):

            root_dir = os.path.dirname(os.path.abspath(__file__))
            info = inspect.getframeinfo(inspect.stack()[1][0])
            logger.debug(
                'Run {} (called by file "{}", line {}, in {})'.format(
                    f.__qualname__,
                    info.filename.replace(root_dir, '.'),
                    info.lineno,
                    info.function))

            try:
                return f(*args, **kwargs)
            except Exception as e:
                logger.exception(e)
                if isinstance(e, timeout_decorator.TimeoutError):
                    raise CkanTimeoutError
                if self.is_ignored(e):
                    return f(*args, **kwargs)
                if e.__class__.__qualname__ == 'ValidationError':
                    try:
                        err = e.error_dict
                        del err['__type']
                        msg = ', '.join([
                            '"{0}" {1}'.format(k, isinstance(v, list) and ', '.join(v) or v)
                            for k, v in err.items()])
                    except Exception as e:
                        msg = e.__str__()
                    raise ValidationError(msg)
                if e.__str__() in ('Indisponible', 'Not Found'):
                    raise CkanNotFoundError
                raise CkanSyncingError(e.__str__())
        return wrapper

    def is_ignored(self, exception):
        return type(exception) in self.ignore


class CkanBaseHandler(object):

    def __init__(self, url, apikey=None):

        self.apikey = apikey
        self.remote = RemoteCKAN(url, apikey=self.apikey)
        try:
            res = self.call_action('site_read')
        except Exception:
            raise CkanReadError()
        # else:
        logger.info('Open CKAN connection with api key: {}'.format(apikey))
        if not res:
            self.close()
            raise CkanApiError()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def close(self):
        self.remote.close()
        logger.info('Close CKAN connection')

    # @timeout
    def call_action(self, action, **kwargs):
        return self.remote.call_action(action, kwargs)

    @CkanExceptionsHandler()
    def get_all_categories(self, *args, **kwargs):
        kwargs.setdefault('order_by', 'name')
        return [
            category for category
            in self.call_action('group_list', **kwargs)]

    @CkanExceptionsHandler()
    def get_all_licenses(self, *args, **kwargs):
        try:
            action_result = self.call_action('license_list', **kwargs)
        except CkanError.CKANAPIError:
            action_result = self.call_action('licence_list', **kwargs)
        return [license for license in action_result]

    @CkanExceptionsHandler()
    def get_all_organisations(self, *args, **kwargs):
        return [
            organisation for organisation
            in self.call_action('organization_list', **kwargs)]

    @CkanExceptionsHandler(ignore=[CkanError.NotFound])
    def get_organisation(self, id, **kwargs):
        try:
            return self.call_action('organization_show', id=id, **kwargs)
        except CkanError.NotFound:
            return None

    @CkanExceptionsHandler(ignore=[CkanError.NotFound])
    def get_package(self, id, **kwargs):
        kwargs.setdefault('include_tracking', True)
        try:
            return self.call_action(
                'package_show', id=id, **kwargs)
        except CkanError.NotFound:
            return False

    def is_package_exists(self, id):
        return self.get_package(id) and True or False

    def is_package_name_already_used(self, name):
        return self.get_package(name) and True or False

    @CkanExceptionsHandler()
    # @timeout
    def push_resource(self, package, **kwargs):
        kwargs['package_id'] = package['id']
        kwargs['created'] = datetime.now().isoformat()
        for resource in package['resources']:
            if resource['id'] == kwargs['id']:
                kwargs['last_modified'] = kwargs['created']
                del kwargs['created']
                if 'url' in kwargs and not kwargs['url']:
                    del kwargs['url']
                resource.update(kwargs)
                del resource['tracking_summary']
                # Moche pour tester
                # if resource['datastore_active']:
                #     self.remote.action.resource_update(**resource)
                #     if 'upload' in resource:
                #         del resource['upload']
                # Fin de 'Moche pour tester'
                datastore_active = resource.get('datastore_active')
                if datastore_active and type(datastore_active) == str:
                    resource['datastore_active'] = ast.literal_eval(datastore_active)
                return self.remote.action.resource_update(**resource)
        return self.remote.action.resource_create(**kwargs)

    @CkanExceptionsHandler()
    def push_resource_view(self, **kwargs):
        kwargs['title'] = kwargs['title'] if 'title' in kwargs else 'Aperçu'
        kwargs['description'] = kwargs['description'] \
            if 'description' in kwargs else 'Aperçu du jeu de données'

        views = self.call_action(
            'resource_view_list', id=kwargs['resource_id'])
        for view in views:
            if view['view_type'] == kwargs['view_type']:
                return self.call_action(
                    'resource_view_update', id=view['id'], **kwargs)
        return self.call_action('resource_view_create', **kwargs)

    @CkanExceptionsHandler()
    def update_resource(self, id, **kwargs):
        resource = self.call_action('resource_show', id=id)
        resource.update(kwargs)
        return self.call_action('resource_update', **resource)

    def check_dataset_integrity(self, name):
        if self.is_package_name_already_used(name):
            raise CkanConflictError('Dataset already exists')

    @CkanExceptionsHandler()
    def publish_dataset(self, id=None, resources=None, **kwargs):
        if id and self.is_package_exists(id):
            package = self.call_action(
                'package_update', **{**self.get_package(id), **kwargs})
        else:
            package = self.call_action('package_create', **kwargs)
        return package

    @CkanExceptionsHandler()
    def publish_resource(self, package, **kwargs):
        resource_view_type = kwargs.pop('view_type')
        resource = self.push_resource(package, **kwargs)

        view = None
        if resource_view_type:
            view = self.push_resource_view(
                resource_id=resource['id'], view_type=resource_view_type)

        return resource, view

    @CkanExceptionsHandler(ignore=[CkanError.NotFound])
    def delete_resource(self, id):
        try:
            return self.call_action('resource_delete', id=id, force=True)
        except CkanError.NotFound:
            return None

    @CkanExceptionsHandler(ignore=[CkanError.NotFound])
    def delete_dataset(self, id):
        try:
            return self.call_action('package_delete', id=id)
        except CkanError.NotFound:
            return None


class CkanUserHandler(CkanBaseHandler):

    def __init__(self, apikey):
        super().__init__(CKAN_URL, apikey=apikey)


class CkanManagerHandler(CkanBaseHandler, metaclass=Singleton):

    def __init__(self):
        super().__init__(CKAN_URL, apikey=CKAN_API_KEY)

    def get_all_users(self):
        return [(user['name'], user['display_name'])
                for user in self.call_action('user_list')
                if user['state'] == 'active']

    @CkanExceptionsHandler(ignore=[CkanError.NotFound])
    def get_user(self, username):
        try:
            return self.call_action('user_show', id=username)
        except CkanError.NotFound:
            return None

    def is_user_exists(self, username):
        return self.get_user(username) and True or False

    @CkanExceptionsHandler()
    def add_user(self, user, password, state='deleted'):

        # CKAN retourne une erreur 500
        fullname = unicodedata.normalize(
            'NFKD', user.get_full_name()).encode(
                'ascii', 'ignore').decode('ascii')

        params = {'email': user.email,
                  'fullname': fullname,
                  'name': user.username,
                  'password': password,
                  'activity_streams_email_notifications': True,
                  'state': state}
        user = self.call_action('user_create', **params)

    @CkanExceptionsHandler()
    def del_user(self, username):
        # self.del_user_from_groups(username)
        self.del_user_from_organisations(username)
        self.call_action('user_delete', id=username)

    @CkanExceptionsHandler()
    def update_user(self, user):
        if not self.is_user_exists:
            raise IntegrityError(
                'User {0} does not exists'.format(user.username))

        ckan_user = self.get_user(user.username)
        ckan_user.update({'email': user.email,
                          'fullname': user.get_full_name()})
        self.call_action('user_update', **ckan_user)

    @CkanExceptionsHandler()
    def activate_user(self, username):
        ckan_user = self.get_user(username)
        ckan_user.update({'state': 'active'})
        self.call_action('user_update', **ckan_user)

    def is_organisation_exists(self, id):
        return self.get_organisation(id) and True or False

    @CkanExceptionsHandler(ignore=[ValueError])
    def add_organisation(self, organisation):
        params = {
            'id': str(organisation.ckan_id),
            'name': organisation.slug,
            'title': organisation.legal_name,
            'description': organisation.description,
            'extras': [
                {'key': 'email', 'value': organisation.email or ''},
                {'key': 'phone', 'value': organisation.phone or ''},
                {'key': 'website', 'value': organisation.website or ''},
                {'key': 'address', 'value': organisation.address or ''},
                {'key': 'postcode', 'value': organisation.postcode or ''},
                {'key': 'city', 'value': organisation.city or ''}],
            'state': 'active'}
        try:
            params['image_url'] = \
                urljoin(settings.DOMAIN_NAME, organisation.logo.url)
        except ValueError:
            pass
        self.call_action('organization_create', **params)

    @CkanExceptionsHandler()
    def update_organisation(self, organisation):
        ckan_organisation = self.get_organisation(
            str(organisation.ckan_id), include_datasets=True)

        ckan_organisation.update({
            'title': organisation.legal_name,
            'name': organisation.slug,
            'description': organisation.description,
            'extras': [
                {'key': 'email', 'value': organisation.email or ''},
                {'key': 'phone', 'value': organisation.phone or ''},
                {'key': 'website', 'value': organisation.website or ''},
                {'key': 'address', 'value': organisation.address or ''},
                {'key': 'postcode', 'value': organisation.postcode or ''},
                {'key': 'city', 'value': organisation.city or ''}]})

        try:
            if organisation.logo:
                ckan_organisation['image_url'] = \
                    urljoin(settings.DOMAIN_NAME, organisation.logo.url)
        except ValueError:
            pass

        self.call_action('organization_update', **ckan_organisation)

        for package in ckan_organisation['packages']:
            self.call_action('package_owner_org_update', id=package['id'],
                             organization_id=ckan_organisation['id'])

    @CkanExceptionsHandler()
    def purge_organisation(self, id):
        return self.call_action('organization_purge', id=id)

    @CkanExceptionsHandler()
    def activate_organisation(self, id):
        self.call_action('organization_update', id=id, state='active')

    @CkanExceptionsHandler()
    def deactivate_organisation(self, id):
        # self.call_action('organization_delete', id=id)
        pass

    def deactivate_ckan_organisation_if_empty(self, id):
        organisation = self.get_organisation(id)
        if organisation and int(organisation.get('package_count')) < 1:
            self.deactivate_organisation(id)

    @CkanExceptionsHandler()
    def get_organisations_which_user_belongs(
            self, username, permission='manage_group'):
        # permission=read|create_dataset|manage_group
        res = self.call_action(
            'organization_list_for_user', id=username, permission=permission)
        return [d['name'] for d in res if d['is_organization']]

    @CkanExceptionsHandler()
    def add_user_to_organisation(
            self, username, organisation_id, role='editor'):
        # role=member|editor|admin
        self.call_action(
            'organization_member_create',
            id=str(organisation_id), username=username, role=role)

    @CkanExceptionsHandler()
    def del_user_from_organisation(self, username, organisation_id):
        self.call_action(
            'organization_member_delete',
            id=str(organisation_id), username=username)

    @CkanExceptionsHandler()
    def del_user_from_organisations(self, username):
        organisations = self.get_organisations_which_user_belongs(username)
        if not organisations:
            return
        for organisation_name in organisations:
            self.del_user_from_organisation(username, organisation_name)

    @CkanExceptionsHandler(ignore=[CkanError.NotFound])
    def get_group(self, id, **kwargs):
        try:
            return self.call_action('group_show', id=str(id), **kwargs)
        except CkanError.NotFound:
            return None

    def is_group_exists(self, id):
        b = self.get_group(str(id)) and True or False
        if not b:
            logger.warning("CKAN group '{id}' does not exists.".format(id=str(id)))
        return b

    @CkanExceptionsHandler()
    def create_partner_group(self, name):
        return self.call_action('group_create', type='partner', name=name)

    @CkanExceptionsHandler()
    def add_user_to_partner_group(self, username, name):
        ckan_group = self.get_group(name) or self.create_partner_group(name)

        users = ckan_group.pop('users', [])
        ckan_group['users'] = [
            {'id': user['id'], 'name': user['name']} for user in users]

        if username not in [user['name'] for user in ckan_group['users']]:
            ckan_group['users'].append({'name': username})

        self.call_action('group_update', **ckan_group)

    @CkanExceptionsHandler()
    def del_user_from_partner_group(self, username, id):
        if self.is_group_exists(id):
            self.call_action('group_member_delete', id=id, username=username)

    @CkanExceptionsHandler()
    def add_group(self, group, type=None):
        ckan_group = {
            'id': str(group.ckan_id),
            'type': type,
            'title': group.name,
            'name': group.slug,
            'description': group.description}
        try:
            ckan_group['image_url'] = \
                urljoin(settings.DOMAIN_NAME, group.picto.url)
        except ValueError:
            pass
        return self.call_action('group_create', **ckan_group)

    @CkanExceptionsHandler()
    def update_group(self, group):
        ckan_group = self.get_group(str(group.ckan_id), include_datasets=True)
        ckan_group.update({
            'title': group.name,
            'name': group.slug,
            'description': group.description})

        for val in ('packages', 'tags', 'groups'):
            lst = ckan_group.get(val, [])
            if lst:
                del ckan_group[val]
            ckan_group[val] = [{'id': e['id'], 'name': e['name']} for e in lst]

        try:
            ckan_group['image_url'] = \
                urljoin(settings.DOMAIN_NAME, group.picto.url)
        except ValueError:
            pass
        try:
            return self.call_action('group_update', **ckan_group)
        except CkanError.NotFound:
            return None

    @CkanExceptionsHandler()
    def del_group(self, id):
        self.call_action('group_purge', id=str(id))

    @CkanExceptionsHandler()
    def add_user_to_group(self, username, group_id):
        ckan_group = self.get_group(str(group_id), include_datasets=True)
        if not ckan_group:
            raise Exception("The group '{0}' does not exists".format(str(group_id)))

        packages = ckan_group.get('packages', [])
        if packages:
            del ckan_group['packages']
        ckan_group['packages'] = \
            [{'id': package['id'], 'name': package['name']} for package in packages]

        users = ckan_group.get('users', [])
        if users:
            del ckan_group['users']
        ckan_group['users'] = \
            [{'id': user['id'], 'name': user['name'], 'capacity': 'admin'} for user in users]

        if username not in [user['name'] for user in ckan_group['users']]:
            ckan_group['users'].append({'name': username, 'capacity': 'admin'})

        self.call_action('group_update', **ckan_group)

    @CkanExceptionsHandler()
    def purge_dataset(self, id):
        try:
            return self.call_action('dataset_purge', id=id)
        except CkanError.NotFound:
            return None

    @CkanExceptionsHandler()
    def get_tags(self, query=None, all_fields=False, vocabulary_id=None):
        return self.call_action('tag_list', vocabulary_id=vocabulary_id,
                                all_fields=all_fields, query=query)

    def is_tag_exists(self, name, vocabulary_id=None):
        try:
            return name in self.get_tags(vocabulary_id=vocabulary_id)
        except Exception:
            return False

    @CkanExceptionsHandler()
    def add_tag(self, name, vocabulary_id=None):
        return self.call_action(
            'tag_create', name=name, vocabulary_id=vocabulary_id)

    @CkanExceptionsHandler()
    def add_vocabulary(self, name, tags):
        return self.call_action('vocabulary_create', name=name,
                                tags=[{'name': tag} for tag in tags])

    @CkanExceptionsHandler()
    def get_vocabulary(self, id):
        try:
            return self.call_action('vocabulary_show', id=id)
        except CkanError.NotFound:
            return None

    @CkanExceptionsHandler()
    def get_licenses(self):
        return self.call_action('license_list')

    @CkanExceptionsHandler()
    def get_resource(self, id):
        return self.call_action('resource_show', id=id)


CkanHandler = CkanManagerHandler()
