from rest_framework import serializers
from .models import Song, Like, Download, Comment, CommentReaction, MusicEvent


class CommentSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    is_user_comment = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ['id', 'song', 'user', 'content', 'created_at', 'is_user_comment']

    def get_is_user_comment(self, obj):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            return obj.user == request.user
        return False


class SongSerializer(serializers.ModelSerializer):
    likes_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    uploaded_by = serializers.StringRelatedField(read_only=True)
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Song
        fields = [
            'id', 'title', 'artist', 'genre', 'file', 'image',
            'duration',  # <-- nuevo campo
            'likes_count', 'comments_count', 'comments', 'is_owner',
            'created_at', 'uploaded_by'
        ]
        extra_kwargs = {
            'file': {'required': True},
            'image': {'required': False}
        }

    def get_likes_count(self, obj):
        return getattr(obj, 'likes_count_dynamic', obj.likes_count)

    def get_comments_count(self, obj):
        return getattr(obj, 'comments_count', obj.comments.count())

    def get_comments(self, obj):
        if hasattr(obj, 'prefetched_comments'):
            comments = obj.prefetched_comments
        else:
            comments = obj.comments.all()
        return CommentSerializer(comments, many=True, context=self.context).data

    def get_image(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None

    def get_is_owner(self, obj):
        request = self.context.get('request')
        return request.user == obj.uploaded_by if request and hasattr(request, "user") else False

class LikeSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Like
        fields = ['user', 'song', 'created_at']
        read_only_fields = ['user', 'created_at']


class DownloadSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Download
        fields = ['user', 'song', 'downloaded_at']
        read_only_fields = ['user', 'downloaded_at']


class CommentReactionSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = CommentReaction
        fields = ['id', 'comment', 'user', 'created_at']
        read_only_fields = ['user', 'created_at']


class MusicEventSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = MusicEvent
        fields = [
            'id', 'title', 'description', 'event_date',
            'location', 'image', 'is_active', 'created_at'
        ]

    def get_image(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None
# This code defines serializers for the models in the music application.
# Each serializer converts model instances into JSON format for API responses.