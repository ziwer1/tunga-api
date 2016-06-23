from actstream.models import Action

from tunga_utils.serializers import ContentTypeAnnotatedModelSerializer


class ActionSerializer(ContentTypeAnnotatedModelSerializer):

    class Meta:
        model = Action
        #exclude = ('created_at',)
