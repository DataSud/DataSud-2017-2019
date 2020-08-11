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


from decimal import Decimal
from django.conf import settings
from django.utils.functional import keep_lazy
from django.utils.safestring import mark_safe
from django.utils.safestring import SafeText
from idgo_admin.exceptions import SizeLimitExceededError
from idgo_admin import logger
import json
import os
import re
import requests
import shutil
import string
import unicodedata
from urllib.parse import urlparse
from uuid import uuid4
from zipfile import ZipFile


STATIC_ROOT = settings.STATIC_ROOT
STATICFILES_DIRS = settings.STATICFILES_DIRS


# Metaclasses:


class StaticClass(type):
    def __call__(cls):
        raise TypeError(
            "'{0}' static class is not callable.".format(cls.__qualname__))


class Singleton(type):

    __instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls.__instances:
            cls.__instances[cls] = super().__call__(*args, **kwargs)
        # else:
        #     cls._instances[cls].__init__(*args, **kwargs)
        return cls.__instances[cls]


# Others stuffs


def create_dir(media_root):
    directory = os.path.join(media_root, str(uuid4())[:7])
    if not os.path.exists(directory):
        os.makedirs(directory)
        return directory
    return create_dir(media_root)


def remove_dir(directory):
    if not os.path.exists(directory):
        return
    shutil.rmtree(directory)


def remove_file(filename):
    if not os.path.exists(filename):
        return
    os.remove(filename)


def download(url, media_root, **kwargs):

    def get_content_header_param(txt, param):
        try:
            found = re.search('{0}="?([^;"\n\r\t\0\s\X\R\v]+)"?'.format(param), txt)
        except Exception as e:
            logger.exception(e)
            return None
        else:
            if found:
                return found.groups()[0]

    max_size = kwargs.get('max_size')

    for i in range(0, 10):  # Try at least ten times before raise
        try:
            r = requests.get(url, stream=True)
        except Exception as e:
            logger.exception(e)
            error = e
            continue
        else:
            break
    else:
        raise error
    r.raise_for_status()

    if int(r.headers.get('Content-Length', 0)) > max_size:
        raise SizeLimitExceededError(max_size=max_size)

    directory = create_dir(media_root)
    filename = os.path.join(
        directory,
        get_content_header_param(r.headers.get('Content-Disposition'), 'filename')
        or urlparse(url).path.split('/')[-1]
        or 'file')

    # TODO(@m431m) -> https://github.com/django/django/blob/3c447b108ac70757001171f7a4791f493880bf5b/docs/topics/files.txt#L120

    with open(filename, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
            if os.fstat(f.fileno()).st_size > max_size:
                remove_dir(directory)
                raise SizeLimitExceededError(max_size=max_size)

    return directory, filename, r.headers.get('Content-Type')


class PartialFormatter(string.Formatter):
    def __init__(self, missing='~~', bad_fmt='!!'):
        self.missing, self.bad_fmt = missing, bad_fmt

    def get_field(self, field_name, args, kwargs):
        # Handle a key not found
        try:
            val = super(PartialFormatter, self).get_field(field_name, args, kwargs)
            # Python 3, 'super().get_field(field_name, args, kwargs)' works
        except (KeyError, AttributeError):
            val = None, field_name
        return val

    def format_field(self, value, spec):
        # handle an invalid format
        if not value:
            return self.missing
        try:
            return super(PartialFormatter, self).format_field(value, spec)
        except ValueError:
            if self.bad_fmt:
                return self.bad_fmt
            else:
                raise


def three_suspension_points(val, max_len=29):
    return (len(val)) > max_len and val[0:max_len - 3] + '...' or val


def readable_file_size(val):
    l = len(str(val))
    if l > 6:
        return '{0} mo'.format(Decimal(int(val) / 1024 / 1024))
    elif l > 3:
        return '{0} ko'.format(Decimal(int(val) / 1024))
    else:
        return '{0} octets'.format(int(val))


def open_json_staticfile(filename):
    def open_json(root):
        with open(os.path.join(root, filename), encoding='utf-8') as f:
            return json.load(f)

    if STATIC_ROOT:
        return open_json(STATIC_ROOT)
    elif STATICFILES_DIRS:
        for staticfiles_dir in STATICFILES_DIRS:
            return open_json(staticfiles_dir)
    else:
        raise AttributeError('Neither STATIC_ROOT nor STATICFILES_DIRS are found in this context.')


def clean_my_obj(obj):
    if obj and isinstance(obj, (list, tuple, set)):
        return type(obj)(clean_my_obj(x) for x in obj if x)
    elif obj and isinstance(obj, dict):
        return type(obj)(
            (clean_my_obj(k), clean_my_obj(v)) for k, v in obj.items() if k and v)
    else:
        return obj


@keep_lazy(str, SafeText)
def slugify(value, allow_unicode=False, exclude_dot=True):
    # Réécriture du slugify (ajouté le paramètre `exclude_dot`)
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')

    value = re.sub(
        exclude_dot and r'[^\w\s-]' or r'[^\.\w\s-]', '', value).strip().lower()

    return mark_safe(re.sub(r'[-\s]+', '-', value))


@keep_lazy(str, SafeText)
def kill_all_special_characters(value):
    return unicodedata.normalize('NFKD', str(value)).encode('ascii', 'ignore').decode('ascii')


def unzip_zipped(zipped, target_dir=None):
    with ZipFile(zipped) as zf:
        print(zf)
        # return zf.extractall(target_dir)
