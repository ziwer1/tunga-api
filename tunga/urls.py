"""tunga URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.9/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from allauth.account.views import ConfirmEmailView
from django.conf.urls import url, include
from django.contrib import admin
from django.contrib.auth.views import password_reset_confirm
from rest_auth.views import UserDetailsView
from rest_framework.routers import DefaultRouter
from rest_framework_jwt.views import obtain_jwt_token, refresh_jwt_token, verify_jwt_token

from tunga_auth.views import VerifyUserView, AccountInfoView, UserViewSet
from tunga_comments.views import CommentViewSet
from tunga_messages.views import MessageViewSet, ReplyViewSet
from tunga_profiles.views import ProfileView, EducationViewSet, WorkViewSet, ConnectionViewSet, SocialLinkViewSet, \
    NotificationView, CountryListView
from tunga_settings.views import UserSettingsView
from tunga_tasks.views import TaskViewSet, ApplicationViewSet, ParticipationViewSet, TaskRequestViewSet, \
    SavedTaskViewSet, task_web_view
from tunga_activity.views import ActionViewSet
from tunga_utils.views import SkillViewSet, ContactRequestView

router = DefaultRouter()
router.register(r'user', UserViewSet)
router.register(r'task', TaskViewSet)
router.register(r'application', ApplicationViewSet)
router.register(r'participation', ParticipationViewSet)
router.register(r'task-request', TaskRequestViewSet)
router.register(r'saved-task', SavedTaskViewSet)
router.register(r'me/social-link', SocialLinkViewSet)
router.register(r'me/education', EducationViewSet)
router.register(r'me/work', WorkViewSet)
router.register(r'connection', ConnectionViewSet)
router.register(r'comment', CommentViewSet)
router.register(r'message', MessageViewSet)
router.register(r'reply', ReplyViewSet)
router.register(r'activity', ActionViewSet)
router.register(r'skill', SkillViewSet)

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^accounts/', include('allauth.urls')),
    url(r'api/', include(router.urls)),
    url(r'^api/auth/register/account-confirm-email/(?P<key>\w+)/$', ConfirmEmailView.as_view(),
        name='account_confirm_email'),
    url(r'^api/auth/register/', include('rest_auth.registration.urls')),
    url(r'^api/auth/verify/', VerifyUserView.as_view(), name='auth-verify'),
    url(r'^api/auth/jwt/token/', obtain_jwt_token),
    url(r'^api/auth/jwt/refresh/', refresh_jwt_token),
    url(r'^api/auth/jwt/verify/', verify_jwt_token),
    url(r'^api/oauth/', include('oauth2_provider.urls', namespace='oauth2_provider')),
    url(r'^api/me/account/', AccountInfoView.as_view(), name='account-info'),
    url(r'^api/me/user/', UserDetailsView.as_view(), name='user-info'),
    url(r'^api/me/profile/', ProfileView.as_view(), name='profile-info'),
    url(r'^api/me/settings/', UserSettingsView.as_view(), name='user-settings'),
    url(r'^api/me/notification/', NotificationView.as_view(), name='user-notifications'),
    url(r'^api/auth/', include('rest_auth.urls')),
    url(r'api/', include('rest_framework.urls', namespace='rest_framework')),
    url(r'^api/countries/', CountryListView.as_view(), name='countries'),
    url(r'^api/contact-request/', ContactRequestView.as_view(), name='contact-request'),
    url(r'^api/docs/', include('rest_framework_swagger.urls')),
    url(r'^task/(?P<pk>\d+)/$', task_web_view, name="task-web"),
    url(r'^reset-password/confirm/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/$',
        password_reset_confirm, name='password_reset_confirm'),
    url(r'^$', router.get_api_root_view(), name='backend-root')
]
