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

class PostService:
    def get_list_post_with_range(self,limit,offset,posts):
        _posts = []
        if((limit is not None) and (offset is not None)):
            _posts = posts[int(offset):int(limit) + int(offset)]
        else:
            _posts = posts[0:3]
        return _posts
    
    def get_list_post_with_filter(self,filter_get,profile_id):
        posts = []
        if filter_get == 'newest':
            posts = Post.objects.all().order_by('-created_at')
        elif filter_get == 'like':
            posts = Post.objects.all().order_by('-count_like')
        elif (filter_get == 'by-me') and (profile_id is not None):
            posts = Post.objects.filter(user_id=profile_id).order_by('-created_at')
        else:
            posts = Post.objects.filter(user_id=int(filter_get)).order_by('-created_at')
        return posts
    
    def get_count_post(self):
        return Post.objects.all().count()
    
    def get_post_by_id(self,post_id):
        try:
            return Post.objects.get(post_id=post_id)
        except Post.DoesNotExist:
            return None
    
    def is_author(self,post,my_id):
        return post.user_id == int(my_id)
        