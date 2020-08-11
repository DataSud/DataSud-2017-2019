from django.conf.urls import url
from server_cas.views import SignIn
from server_cas.views import SignOut

urlpatterns = [
            url('^cas/login/?$', SignIn.as_view(), name='signIn'),
            url('^cas/logout/?$', SignOut.as_view(), name='signOut'),
            url('^signin/?$', SignIn.as_view(), name='signIn'),
            url('^signout/?$', SignOut.as_view(), name='signOut'),
        ]
