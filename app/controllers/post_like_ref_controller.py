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
from ..services.post_service import PostService
from ..services.post_like_ref_service import PostLikeRefService
import textdistance

class PostLikeRefController:
    def create_post_like_ref(self,post_like_ref,current_user):
        user_service = UserService()
        user_id = user_service.get_profileid_from_auth_userid(me=current_user)
        new_post_like_ref = PostLikeRef(user_id=user_id,post_id=post_like_ref.post_id)
        new_post_like_ref.save()
        return 'like',post_like_ref.post_id
    
    def delete_post_like_ref(self,post_id,user_id):
        try:
            post_like_ref = PostLikeRef.objects.get(post_id=post_id,user_id=user_id)
            post_like_ref.delete()
            return 'unlike',post_id
        except PostLikeRef.DoesNotExist:
            return None,None
    
    def prepare_post_like_ref(self,current_user,post_id):
        try:
            user_service = UserService()
            user_id = user_service.get_profileid_from_auth_userid(me=current_user)
            return PostLikeRef.objects.get(post_id=post_id,user_id=user_id)
        except PostLikeRef.DoesNotExist:
            return None
