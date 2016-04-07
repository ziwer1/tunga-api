from actstream.models import Action

from tunga_utils.serializers import ContentTypeAnnotatedSerializer


class ActionSerializer(ContentTypeAnnotatedSerializer):

    class Meta:
        model = Action
        #exclude = ('created_at',)
