# Procédure d'installation

#### Installer les dépendances

```shell
> apt-get install python3.5-dev python3.5-venv
> apt-get install binutils libproj-dev gdal-bin
> apt-get install git
```

#### Mettre en place l'environnement virtuel Python 3.5

```shell
> cd /
/> mkdir idgo_venv
/> cd idgo_venv
/idgo_venv> pyvenv-3.5 ./
/idgo_venv> source bin/activate
(idgo_venv) /idgo_venv> pip install --upgrade pip
(idgo_venv) /idgo_venv> pip install --upgrade setuptools
(idgo_venv) /idgo_venv> pip install psycopg2
(idgo_venv) /idgo_venv> pip install 'django=>1.11,<1.12'
(idgo_venv) /idgo_venv> pip install django-taggit
(idgo_venv) /idgo_venv> pip install django-bootstrap3
(idgo_venv) /idgo_venv> pip install django-mama-cas
(idgo_venv) /idgo_venv> pip install pillow
(idgo_venv) /idgo_venv> pip install timeout-decorator
(idgo_venv) /idgo_venv> pip install requests
(idgo_venv) /idgo_venv> pip install ckanapi
(idgo_venv) /idgo_venv> pip install owslib
(idgo_venv) /idgo_venv> pip install django-queryset-csv
(idgo_venv) /idgo_venv> pip install django-admin-list-filter-dropdown
(idgo_venv) /idgo_venv> pip install django-extensions
(idgo_venv) /idgo_venv> pip install djangorestframework
(idgo_venv) /idgo_venv> pip install markdown
```

#### Récupérer les codes sources

```shell
> cd /
/> mkdir apps
/> cd apps
/apps> git clone https://github.com/neogeo-technologies/idgo idgo
/apps> git clone https://github.com/neogeo-technologies/mdedit mdedit
```
IDGO doit être installé à la racine de l'environnement virtuel.

MDedit doit être installé dans le répertoire `static/libs/` du projet IDGO.

```shell
> ln -s /apps/idgo/idgo_admin /idgo_venv/
> ln -s /apps/mdedit /apps/idgo/idgo_admin/static/libs/
```

#### Initialiser Django

```shell
> cd /idgo_venv
/idgo_venv> source bin/activate
(idgo_venv) django-admin startproject config .
```

#### Éditer les fichiers de configuration Django

D'abord :

```shell
> vim /idgo_venv/config/settings.py
```

```python
import os


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = 'abcdefghijklmnopqrstuvwxyz0123456789'

DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

DOMAIN_NAME = 'http://localhost'

INSTALLED_APPS = [
    'django_admin_listfilter_dropdown',
    'django.contrib.sites'
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
    'django_extensions',
    'taggit',
    'bootstrap3',
    'mama_cas',
    'idgo_admin',
    'commandes']

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware']

ROOT_URLCONF = 'config.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages']}}]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'dbname',
        'USER': 'username',
        'PASSWORD': 'password',
        'HOST':'hostname',
        'PORT':'5432'},
    'datagis': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'dbname_datagis',
        'USER': 'username',
        'PASSWORD': 'password',
        'HOST': 'hostname',
        'PORT': '5432'}}

DATAGIS_DB = 'datagis'

MRA = {
    'URL': 'http://127.0.0.1/mra',
    'USERNAME': 'username',
    'PASSWORD': 'password',
    'DATAGIS_DB_USER': 'username'}

OWS_URL_PATTERN = 'http://127.0.0.1/ows/{organisation}?'
OWS_PREVIEW_URL = 'http://127.0.0.1/preview?'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'}]

LANGUAGE_CODE = 'FR-fr'

TIME_ZONE = 'Europe/Paris'

USE_I18N = True

USE_L10N = True

USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = '/var/www/html/static/'

MEDIA_URL = '/media/'
MEDIA_ROOT = '/var/www/html/media/'

FTP_URL = 'http://ftp.dev.idgo.neogeo.fr/cgi-bin/ftp.cgi?'
FTP_DIR = '/var/ftp/'

CKAN_URL = 'http://ckan'
CKAN_API_KEY = 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'
CKAN_TIMEOUT = 36000

WORDPRESS_URL = 'http://wordpress'

DOWNLOAD_SIZE_LIMIT = 104857600  # octets (e.g. 100Mio)

GEONETWORK_URL = 'http://geonetwork'
GEONETWORK_LOGIN = 'username'
GEONETWORK_PASSWORD = 'password'

READTHEDOC_URL = 'http://datasud.readthedocs.io/fr/latest/producteurs.html#comment-renseigner-les-metadonnees-sur-datasud'
READTHEDOC_URL_INSPIRE = 'http://datasud.readthedocs.io/fr/latest/producteurs.html#comment-renseigner-les-metadonnees-inspire-sur-datasud'

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp-domaine.abc'
EMAIL_HOST_USER = 'username@your-domaine.abc'
EMAIL_HOST_PASSWORD = 'password'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = 'username@your-domaine.abc'

LOGIN_URL = 'idgo_admin:signIn'

MAMA_CAS_SERVICES = [{
    'SERVICE': '^http://ckan',
    'CALLBACKS': [
        'mama_cas.callbacks.user_name_attributes',
        'mama_cas.callbacks.user_model_attributes'],
    'LOGOUT_ALLOW': True,
    'LOGOUT_URL': 'http://localhost/signout'}]

DEFAULTS_VALUES = {
    'JURISDICTION': 93,  # Code INSEE -> Région SUD
}

SUPPORTED_VSI_PROTOCOLES = {
    'geojson': None,
    'shapezip': 'vsizip',
    'tab': 'vsizip',
    'mif/mid': 'vsizip',
    'tar': 'vsitar',
    'zip': 'vsizip'}

EXTRACTOR_BOUNDS = [[42.4, 3.3], [46.1, 10.8]]

DEFAULT_PLATFORM_NAME = 'my website'
DEFAULT_CONTACT_EMAIL = 'contact@mywebsite.org'

SITE_ID = 1

```

Puis :

```shell
> vim /idgo_venv/config/urls.py
```

``` python
from django.conf.urls import include
from django.conf.urls import url
from django.contrib import admin


urlpatterns = [
    url('^', include('idgo_admin.urls', namespace='idgo_admin')),
    url('^admin/', admin.site.urls),
    url(r'^cas/', include('mama_cas.urls'))]

```

#### Créer les répertoires `static`, `media` et `logos`

```shell
> cd /var/www/html
/var/www/html> mkdir static
/var/www/html> mkdir media
/var/www/html> cd media
/var/www/html/media> mkdir logos
```

Apache doit pouvoir écrire dans les sous répertoires de `media`.


#### Vérifier l'installation

```shell
> cd /idgo_venv
/idgo_venv> source bin/activate
(idgo_venv) /idgo_venv> python manage.py check
```

#### Déployer les bases de données

```shell
> cd /idgo_venv
/idgo_venv> source bin/activate
(idgo_venv) /idgo_venv> python manage.py migrate
```

#### Créer le super utilisateur Django

```shell
> cd /idgo_venv
/idgo_venv> source bin/activate
(idgo_venv) /idgo_venv> python manage.py createsuperuser
```

#### Déployer les fichiers `static`

```shell
> cd /idgo_venv
/idgo_venv> source bin/activate
(idgo_venv) /idgo_venv> python manage.py collectstatic
```

#### Charger les lexiques de données en base

```shell
> cd /idgo_venv
/idgo_venv> source bin/activate
(idgo_venv) /idgo_venv> python manage.py loaddata idgo_admin/data/support.json
(idgo_venv) /idgo_venv> python manage.py loaddata idgo_admin/data/commune.json
(idgo_venv) /idgo_venv> python manage.py loaddata idgo_admin/data/mail.json
(idgo_venv) /idgo_venv> python manage.py loaddata idgo_admin/data/resourceformats.json
(idgo_venv) /idgo_venv> python manage.py loaddata idgo_admin/data/jurisdiction.json
(idgo_venv) /idgo_venv> python manage.py loaddata idgo_admin/data/jurisdictioncommune.json
(idgo_venv) /idgo_venv> python manage.py loaddata idgo_admin/data/datatype.json
(idgo_venv) /idgo_venv> python manage.py loaddata idgo_admin/data/granularity.json
(idgo_venv) /idgo_venv> python manage.py loaddata idgo_admin/data/supportedcrs.json
```

#### CRON

```shell
cd /idgo_venv
/idgo_venv> source bin/activate
(idgo_venv) /idgo_venv> python manage.py clean_up_actions_out_of_delay.py
(idgo_venv) /idgo_venv> python manage.py sync_ckan_allowed_users_by_resource
```

#### (Synchroniser les catégories avec CKAN)

```shell
cd /idgo_venv
/idgo_venv> source bin/activate
(idgo_venv) /idgo_venv> python manage.py sync_ckan_categories
```


#### Utiliser le service d'autorisation d'accès à mapserver

Configurer Apache, ajouter dans le VirtualHost :
```
    RewriteEngine On
    RewriteMap anonymous_access "prg:/idgo_venv/idgo_admin/auth_ogc.py"

    RewriteCond %{HTTP:Authorization} ^$
    # ALORS ON VA VERS LE RESULTAT RENVOYE PAR REMAP
    RewriteRule (.*) ${anonymous_access:$1?%{QUERY_STRING}} [last,P,QSA]
    RewriteRule (.*) http://localhost/private$1 [P,QSA]
```

Ca redirige vers http://localhost/public quand la ressource est accéssible aux
utilisateurs anonymes et qu'il n'y a pas de login/mot de passe en BasicAuth.
Sinon ça redirige vers http://localhost/private, qui vérifiera les droits
d'authentification et les autorisations.

Ensuite rajouter cette section:
```
<VirtualHost *:80>
    ServerName localhost

    ProxyRequests Off
    <Location /private>
        WSGIAuthUserScript /idgo_venv/idgo_admin/auth_ogc.py application-group=idgo.com
        WSGIApplicationGroup auth
        AuthType Basic
        AuthName "DataSud authentification"
        AuthBasicProvider wsgi
        Require valid-user

        ProxyPass http://mapserver/
        ProxyPassReverse http://mapserver/
    </Location>
    <Location /public>
        ProxyPass http://mapserver/
        ProxyPassReverse http://mapserver/
    </Location>
</VirtualHost>

```

Utiliser le fichier auth\_ogc.py

Tester avec pyresttest (peut se faire à distance):

```
pip install pyresttest
pyresttest  test/test_auth_ogc.yml --url=https://ocs.dev.idgo.neogeo.fr
```
