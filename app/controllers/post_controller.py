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

class PostController:
    def update_user_interaction(self,homestay_id,me):
        try:
            if me is not None:
                profile = Profile.objects.get(email=me.email)
                if profile.represent_id is not None:
                    try:
                        ui = UserInteraction.objects.get(user_id=profile.represent_id,homestay_id=homestay_id)
                        ui.weight = ui.weight + 2.5
                        ui.status=0
                        ui.save()
                    except UserInteraction.DoesNotExist:
                        new_user_interaction = UserInteraction(user_id=profile.represent_id,homestay_id=homestay_id,weight=2.5)
                        new_user_interaction.save()
        except Profile.DoesNotExist:
            return None
    def get_posts(self,limit,offset,order_by,current_user):
        user_service = UserService()
        post_like_ref_service = PostLikeRefService()
        post_service  = PostService()
        profile_id = user_service.get_profileid_from_auth_userid(me=current_user)
        posts = post_service.get_list_post_with_filter(filter_get=order_by,profile_id=profile_id)
        posts_with_filter = posts
        posts = post_service.get_list_post_with_range(limit=limit,offset=offset,posts=posts)
        posts = PostSerializer(posts,many=True).data
        posts = post_like_ref_service.append_me_like(posts=posts,current_user=current_user,user_id=profile_id)
        total = len(posts_with_filter)
        return posts,total
    
    def create_post(self,post,current_user):
        user_service = UserService()
        user_id = user_service.get_profileid_from_auth_userid(me=current_user)
        new_post = Post(homestay_id=post.homestay_id,user_id=user_id, content=post.content)
        new_post.save()
        self.update_user_interaction(post.homestay_id,me=current_user)
        return PostSerializer(new_post).data
    
    def delete_post(self,post_id,current_user):
        user_service = UserService()
        post_service = PostService()
        my_id = user_service.get_profileid_from_auth_userid(current_user)
        post = post_service.get_post_by_id(post_id=post_id)
        if post is None:
            return None,404
        if not post_service.is_author(post,my_id):
            return None,401
        post.delete()
        return PostSerializer(post).data,200