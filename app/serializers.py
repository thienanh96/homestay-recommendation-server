from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Profile, Homestay, HomestayRate, Post, PostLikeRef, Comment,HomestaySimilarity,UserInteraction


# class UserSerializer(serializers.HyperlinkedModelSerializer):
#     class Meta:
#         model = User
#         fields = ('url', 'username', 'email', 'groups')


# class GroupSerializer(serializers.HyperlinkedModelSerializer):
#     class Meta:
#         model = Group
#         fields = ('url', 'name')

class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ('__all__')

class HomestaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Homestay
        fields = ('__all__')

class HomestaySimilaritySerializer(serializers.ModelSerializer):
    class Meta:
        model = HomestaySimilarity
        # fields = ('first_homestay','second_homestay','score')
        fields = ('__all__')



class HomestayRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = HomestayRate
        fields = ('__all__')


class PostSerializer(serializers.ModelSerializer):
    user = ProfileSerializer()
    homestay = HomestaySerializer()
    class Meta:
        model = Post
        fields = ('__all__')


class PostLikeRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostLikeRef
        fields = ('__all__')


class CommentSerializer(serializers.ModelSerializer):
    user = ProfileSerializer()
    class Meta:
        model = Comment
        fields = ('comment_id','content','user_id','homestay_id','user','sentiment')


class TokenSerializer(serializers.Serializer):
    """
    This serializer serializes the token data
    """
    token = serializers.CharField(max_length=255)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("username", "email")


class UserInteractionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserInteraction
        fields = ('__all__')
