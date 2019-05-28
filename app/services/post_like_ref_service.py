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

class PostLikeRefService:
    def append_me_like(self,posts,current_user,user_id):
        new_posts = []
        for post in posts:
            try:
                if current_user is not None:
                    post_like_ref = PostLikeRef.objects.get(post_id=post['post_id'],user_id=user_id)
                    new_posts.append({
                        'post': post,
                        'me_like': 1
                    })
                else:
                    new_posts.append({
                        'post': post,
                        'me_like': 0
                    })
            except PostLikeRef.DoesNotExist:
                new_posts.append({
                    'post': post,
                    'me_like': 0
                })
        return new_posts
        