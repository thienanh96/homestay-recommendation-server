import ast
import schedule
import _thread
import re
from django.shortcuts import render
from rest_framework import generics
from rest_framework import permissions, authentication, pagination
from rest_framework.response import Response
from rest_framework.views import status
from rest_framework_jwt.settings import api_settings
from ..serializers import ProfileSerializer, HomestayRateSerializer, HomestaySerializer, TokenSerializer, UserSerializer, CommentSerializer, HomestaySimilaritySerializer,PostSerializer,PostLikeRefSerializer,UserInteractionSerializer
from ..models import Homestay, Profile, HomestayRate, Comment, HomestaySimilarity,PostLikeRef,Post,UserInteraction
from ..custom_query import search_homestay
from django.db.models import Q
from django.db import connection
from ..comment_classification import classify_comment,graph
from functools import reduce
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from scipy.spatial import distance
from unidecode import unidecode
import cloudinary
from cloudinary.uploader import upload
from cloudinary.utils import cloudinary_url
from ..recommendation import get_predictions,graph_recommendation,train_model
from ..validation import Validation
import time;
import threading
from ..utils import embed_to_vector, get_score, convert_to_text
import textdistance
EMAIL_ADMIN = 'admin@gmail.com'

class UserService:
    def __init__(self):
        self.user = None
        self.users = None
    
    def authorize_user(self,user,type_get):
        if type_get == 'admin':
            if user is None:
                return False
            if user.email != 'admin@gmail.com':
                return False
            return True
        else:
            return True
    
    def check_anonymous(self,user):
        return user.is_anonymous
    
    def authorize_me(self,user_id,me):
        my_id = self.get_profileid_from_auth_userid(me=me)
        print(user_id,my_id)
        if my_id is not None and user_id is not None and int(my_id) == int(user_id):
            return True
        return False
    
    
    def get_profileid_from_auth_userid(self,me):
        if me is None:
            return None
        if not me.is_anonymous:
            try:
                profile = Profile.objects.get(email=me.email)
                return profile.id
            except Profile.DoesNotExist:
                return None
        else:
            return None
    
    def get_profile_host(self, host_id):
        try:
            queryset_profile = Profile.objects.all()
            current_profile = queryset_profile.get(id=int(host_id))
            return current_profile
        except Profile.DoesNotExist:
            return None
    
    def get_profile_by_email(self,email):
        return Profile.objects.get(email=email)
    
    def set_password(self,new_password,email):
        me_auth = User.objects.get(email=email)
        if me_auth is not None and new_password is not None:
            me_auth.set_password(new_password)
            me_auth.save()
    
    def get_profile_by_id(self,id):
        return Profile.objects.get(id=int(id))
    
    def get_count_profiles(self):
        return Profile.objects.count()
    
    def search_list_profile_by_name(self,text_search):
        return Profile.objects.filter(user_name__icontains=text_search).order_by('created_at')
    
    def get_list_profile_by_range(self, limit, offset):
        return Profile.objects.filter(~Q(user_type='admin')).order_by('created_at')[int(offset):int(offset)+int(limit)]
    
    def get_user_by_id(self,id):
        return User.objects.get(id=int(id))

    def is_admin(self,my_email):
        return my_email == EMAIL_ADMIN