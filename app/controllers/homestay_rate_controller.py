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
from ..services.user_service import UserService
from ..services.homestay_rate_service import HomestayRateService
import textdistance

class HomestayRateController:
    def __init__(self,user_id=None,homestay_id=None):
        self.user_id = user_id
        self.homestay_id = homestay_id

    def update_user_interaction(self,homestay_id,type_rate,action_type,me):
        try:
            if me is not None:
                profile = Profile.objects.get(email=me.email)
                if profile.represent_id is not None:
                    if (int(type_rate) == 1 and action_type == 'add') or (int(type_rate) == 2 and action_type == 'remove'):
                        try:
                            ui = UserInteraction.objects.get(user_id=profile.represent_id,homestay_id=homestay_id)
                            ui.weight = ui.weight + 3
                            ui.status=0
                            ui.save()
                        except UserInteraction.DoesNotExist:
                            new_user_interaction = UserInteraction(user_id=profile.represent_id,homestay_id=homestay_id,weight=3)
                            new_user_interaction.save()
                    elif (int(type_rate) == 1 and action_type == 'remove') or (int(type_rate) == 2 and action_type == 'add'):
                        try:
                            ui = UserInteraction.objects.get(user_id=profile.represent_id,homestay_id=homestay_id)
                            ui.weight = ui.weight - 3 if ui.weight >= 3 else 0 
                            ui.status=0
                            ui.save()
                        except UserInteraction.DoesNotExist:
                            new_user_interaction = UserInteraction(user_id=profile.represent_id,homestay_id=homestay_id,weight=0)
                            new_user_interaction.save()
        except Profile.DoesNotExist:
            return None
    
    def add_homestay_like(self,homestay_id,type_rate,user_id,current_user):
        user_service = UserService()
        homestay_service = HomestayRateService()
        profile_id = user_service.get_profileid_from_auth_userid(me=current_user)
        data_rate = homestay_service.add_homestay_rate(profile_id=profile_id,homestay_id=homestay_id,type_rate=1)
        action_type = None
        if data_rate is not None:
            action_type = 'remove'
        else:
            action_type = 'add'
        self.update_user_interaction(homestay_id,type_rate,action_type,me=current_user)
        return profile_id,action_type

    def add_homestay_dislike(self,homestay_id,type_rate,user_id,current_user):
        user_service = UserService()
        homestay_service = HomestayRateService()
        profile_id = user_service.get_profileid_from_auth_userid(me=current_user)
        data_rate = homestay_service.add_homestay_rate(profile_id=profile_id,homestay_id=homestay_id,type_rate=2)
        action_type = None
        if data_rate is not None:
            action_type = 'remove'
        else:
            action_type = 'add'
        self.update_user_interaction(homestay_id,type_rate,action_type,me=current_user)
        return profile_id,action_type
    
    def remove_homestay_like(self,homestay_id,type_rate,user_id,current_user):
        return None

    def remove_homestay_dislike(self,homestay_id,type_rate,user_id,current_user):
        return None
    
    def get_my_homestay_rate(self,current_user,homestay_id):
        homestay_rate_service = HomestayRateService()
        user_service = UserService()
        me_rate = None
        homestay_rate = homestay_rate_service.get_homestay_rate(user_service.get_profileid_from_auth_userid(current_user), homestay_id)
        if not(homestay_rate is None):
            homestay_rate_data = HomestayRateSerializer(homestay_rate).data
            if homestay_rate_data['isType'] == 1:
                me_rate = 'like'
            if homestay_rate_data['isType'] == 2:
                me_rate = 'dislike'
        return me_rate
    