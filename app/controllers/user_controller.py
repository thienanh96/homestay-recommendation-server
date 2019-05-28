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
from ..utils import embed_to_vector, get_score, convert_to_text,get_new_token
from ..services.user_service import UserService
import textdistance

class UserController:
    def update_user(self,user,user_id,current_user,password):
        user_service = UserService()
        me = Profile.objects.filter(email=current_user.email)
        if(me is not None):
            _me = ProfileSerializer(me,many=True).data[0]
            user_service.set_password(new_password=password,email=current_user.email)
            address = user.address if user.address is not None else _me['address']
            phone = user.phone if user.phone is not None else _me['phone']
            username = user.user_name if user.user_name is not None else _me['user_name']
            update_result = me.update(address=address,phone=phone,user_name=username)
            new_token = get_new_token(profile=Profile.objects.get(email=current_user.email))
            return update_result,new_token
        else:
            return None,None
    
    def get_me(self,current_user):
        user_service = UserService()
        _user_id = user_service.get_profileid_from_auth_userid(current_user)
        try:
            my_profile = user_service.get_profile_by_id(_user_id)
            return ProfileSerializer(my_profile).data
        except Profile.DoesNotExist:
            return None
    
    def get_one_user(self,user_id):
        user_service = UserService()
        try:
            my_profile = user_service.get_profile_by_id(user_id)
            return ProfileSerializer(my_profile).data
        except Profile.DoesNotExist:
            return None      
    
    def get_many_users(self,limit,offset,name,user_id):
        user_service = UserService()
        list_profiles = None
        if name is not None:
            list_profiles = user_service.search_list_profile_by_name(text_search=name)
        elif user_id is not None:
            list_profiles = [user_service.get_profile_by_id(id=user_id)]
        else: 
            list_profiles = user_service.get_list_profile_by_range(limit=limit,offset=offset)
        count = user_service.get_count_profiles()
        return count, ProfileSerializer(list_profiles,many=True).data
    
    def delete_user(self,user_id,current_user):
        user_service = UserService()
        if not current_user.is_anonymous:
            my_email = current_user.email
            if user_service.is_admin(my_email=my_email):
                profile = user_service.get_profile_by_id(id=user_id)
                if profile is not None and profile.user_type != 'admin':
                    profile.delete()
                    auth_profile = user_service.get_user_by_id(id=user_id)
                    auth_profile.delete()
                else:
                    return {'status': '401'}
                return {'status': '200'}
            else:
                return {'status': '401'}
        else:
            return {'status': '401'}
    
    