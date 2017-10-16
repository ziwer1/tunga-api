import json
import re
from operator import itemgetter

import requests
from django.utils import six
from rest_framework import viewsets, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from tunga_profiles.models import Skill
from tunga_utils.models import ContactRequest
from tunga_utils.serializers import SkillSerializer, ContactRequestSerializer


class SkillViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Skills Resource
    """
    queryset = Skill.objects.all()
    serializer_class = SkillSerializer
    permission_classes = [AllowAny]
    search_fields = ('name', )


class ContactRequestView(generics.CreateAPIView):
    """
    Contact Request Resource
    """
    queryset = ContactRequest.objects.all()
    serializer_class = ContactRequestSerializer
    permission_classes = [AllowAny]


@api_view(http_method_names=['GET'])
@permission_classes([AllowAny])
def get_medium_posts(request):
    r = requests.get('https://medium.com/@tunga_io/latest?format=json')
    posts = []
    if r.status_code == 200:
        try:
            response = json.loads(re.sub(r'^[^{]*\{', '{', r.text))
            posts = [
                dict(
                    title=post['title'],
                    url='https://blog.tunga.io/{}-{}'.format(post['slug'], post['id']),
                    slug=post['slug'], created_at=post['createdAt'],
                    id=post['id'],
                    latestVersion=post['latestVersion']
                )
                for key, post in six.iteritems(response['payload']['references']['Post'])
                ]
            # Sort latest first
            posts = sorted(posts, key=itemgetter('created_at'), reverse=True)
        except:
            pass
    return Response(posts)
