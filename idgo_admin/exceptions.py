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


from django.http import Http404
from functools import wraps


# Définition des exceptions
# =========================


class GenericException(Exception):

    # TODO: Logger __dict__

    message = (
        "Une erreur s'est produite, si le problème persiste "
        "veuillez contacter l'administrateur du site.")

    def __init__(self, *args, **kwargs):
        self.args = args
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __str__(self):
        return self.error or self.message

    @property
    def error(self):
        return ' '.join(self.args)


class ConflictError(GenericException):
    pass


class CkanBaseError(GenericException):
    pass


class CriticalError(GenericException):
    pass


class CswBaseError(GenericException):
    pass


class DatagisBaseError(GenericException):
    pass


class DcatBaseError(GenericException):
    pass


class FakeError(GenericException):
    message = "Ceci n'est pas une erreur."


class ExceedsMaximumLayerNumberFixedError(GenericException):
    message = "Votre ficher contient plus de jeux de données que ne l'autorise l'application."

    def __str__(self):
        try:
            sentences = [
                "Le fichier contient {} jeu{} de données géographiques.".format(
                    self.count, self.count > 1 and 'x' or ''),
                "Vous ne pouvez pas ajouter plus de {} jeu{} de données.".format(
                    self.maximum, self.maximum > 1 and 'x' or '')]
        except Exception:
            return super().__str__()
        return ' '.join(sentences)


class MraBaseError(GenericException):
    pass


class ProfileHttp404(Http404):
    pass


class SizeLimitExceededError(GenericException):
    message = 'La taille de la pièce jointe dépasse la limite autorisée.'

    def __init__(self, *args, **kwargs):
        self.message = \
            kwargs.get('max_size') \
            and '{0} La taille est limité à {1}o'.format(
                self.message, kwargs['max_size'])
        super().__init__(*args, **kwargs)


# Utilitaires
# ===========


class ExceptionsHandler(object):

    def __init__(self, ignore=None, actions=None):
        self.ignore = ignore or []
        self.actions = actions or {}

    def __call__(self, f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # request = None
            args = list(args)
            # for arg in args:
            #     if isinstance(arg, WSGIRequest):
            #         request = arg
            try:
                return f(*args, **kwargs)
            except Exception as e:
                for exception, callback in self.actions.items():
                    if isinstance(e, exception):
                        return callback()

                if self.is_ignored(e):
                    return f(*args, **kwargs)
                raise e
        return wrapper

    def is_ignored(self, exception):
        return type(exception) in self.ignore
