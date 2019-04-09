from django.db import models
from django_mysql.models import JSONField
from django.contrib.auth.models import User
# Create your models here.
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.timezone import now
from django.core import serializers


# Create your models here.


class Profile(models.Model):
    id = models.AutoField(primary_key=True)
    represent_id = models.IntegerField(default=0)
    user_type = models.CharField(max_length=200)
    user_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=200)
    email = models.EmailField(
        max_length=70, blank=True, null=True, unique=True)
    address = models.CharField(max_length=500)
    birthday = models.CharField(max_length=200)
    gender = models.CharField(max_length=200)
    created_at = models.DateTimeField('created_at', auto_now_add=True)
    updated_at = models.DateTimeField('updated_at', auto_now=True)
    own_homestays = models.TextField(default=None, null=True)
    avatar = models.TextField(default='')
    join_date = models.CharField(max_length=200)


class Homestay(models.Model):
    homestay_id = models.AutoField(primary_key=True)
    # host = models.ForeignKey(Profile, on_delete=models.CASCADE)
    host_id = models.IntegerField(default=0)
    represent_id = models.IntegerField(default=0)
    main_price = models.FloatField(default=0)
    price_detail = JSONField()
    amenities = JSONField()
    amenities_around = JSONField()
    name = models.TextField(default='')
    descriptions = models.TextField(default='')
    highlight = models.TextField(default='')
    images = models.TextField(default='')
    likes = models.IntegerField(default=0)
    dislikes = models.IntegerField(default=0)
    shares = models.IntegerField(default=0)
    city = models.CharField(max_length=200)
    district = models.CharField(max_length=200)
    is_allowed = models.IntegerField(default=0)
    created_at = models.DateTimeField('created_at', auto_now_add=True)
    updated_at = models.DateTimeField('updated_at', auto_now=True)

    class Meta:
        get_latest_by = 'represent_id'


class HomestayRate(models.Model):
    homestay_rate_id = models.AutoField(primary_key=True)
    homestay_id = models.IntegerField(default=0)
    user_id = models.IntegerField(default=0)
    isType = models.IntegerField(default=0)
    created_at = models.DateTimeField('created_at', auto_now_add=True)
    updated_at = models.DateTimeField('updated_at', auto_now=True)


class Comment(models.Model):
    comment_id = models.AutoField(primary_key=True)
    # user_id = models.IntegerField(default=0)
    user = models.ForeignKey(Profile, on_delete=models.CASCADE)
    homestay_id = models.IntegerField(default=0)
    content = models.TextField()
    sentiment = models.IntegerField(default=0)
    created_at = models.DateTimeField('created_at', auto_now_add=True)
    updated_at = models.DateTimeField('updated_at', auto_now=True)

    def get_comments_with_userinfo(homestay_id, limit, offset):
        return Comment.objects.filter(homestay_id=int(homestay_id)).order_by('-created_at')[int(offset):int(offset) + int(limit)]


class Post(models.Model):
    post_id = models.AutoField(primary_key=True)
    # user_id = models.IntegerField(default=0)
    # homestay_id = models.IntegerField(default=0)
    user = models.ForeignKey(Profile, on_delete=models.CASCADE)
    homestay = models.ForeignKey(Homestay, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField('created_at', auto_now_add=True)
    updated_at = models.DateTimeField('updated_at', auto_now=True)
    count_like = models.IntegerField(default=0)


class PostLikeRef(models.Model):
    post_like_ref_id = models.AutoField(primary_key=True)
    user_id = models.IntegerField(default=0)
    post_id = models.IntegerField(default=0)
    created_at = models.DateTimeField('created_at', auto_now_add=True)
    updated_at = models.DateTimeField('updated_at', auto_now=True)


class HomestaySimilarity(models.Model):
    first_homestay_id = models.IntegerField(default=0)
    second_homestay_id = models.IntegerField(default=0)
    score = models.FloatField(default=0)
