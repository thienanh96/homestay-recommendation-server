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

class HomestayRateService:
    def __init__(self):
        self.user_id = None
        self.post_id = None
    
    def get_homestay_rate(self, user_id, homestay_id):
        try:
            if(user_id is None or homestay_id is None):
                return None
            queryset_homestayrate = HomestayRate.objects.all()
            current_homestayrate = queryset_homestayrate.get(
                user_id=int(user_id), homestay_id=int(homestay_id))
            return current_homestayrate
        except HomestayRate.DoesNotExist:
            return None
    
    def add_homestay_rate(self,profile_id,homestay_id,type_rate):
        cursor = connection.cursor()
        cursor.callproc('rate_homestay', [int(profile_id), int(homestay_id), int(type_rate)])
        return cursor.fetchall()[0][0]
