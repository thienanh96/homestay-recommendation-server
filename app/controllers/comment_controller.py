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
from ..services.comment_service import CommentService
from ..services.user_service import UserService
import textdistance

class CommentController:
    def __init__(self):
        self.comments = None
    
    def update_user_interaction(self,homestay_id,comment_label,me):
        try:
            if me is not None:
                profile = Profile.objects.get(email=me.email)
                if profile.represent_id is not None:
                    if comment_label == 0:
                        try:
                            ui = UserInteraction.objects.get(user_id=profile.represent_id,homestay_id=homestay_id)
                            ui.weight = ui.weight + 1.5
                            ui.status=0
                            ui.save()
                        except UserInteraction.DoesNotExist:
                            new_user_interaction = UserInteraction(user_id=profile.represent_id,homestay_id=homestay_id,weight=1.5)
                            new_user_interaction.save()
                    elif comment_label == 1:
                        try:
                            ui = UserInteraction.objects.get(user_id=profile.represent_id,homestay_id=homestay_id)
                            ui.weight = ui.weight + 3
                            ui.status=0
                            ui.save()
                        except UserInteraction.DoesNotExist:
                            new_user_interaction = UserInteraction(user_id=profile.represent_id,homestay_id=homestay_id,weight=3)
                            new_user_interaction.save()
                    elif comment_label == 2:
                        try:
                            ui = UserInteraction.objects.get(user_id=profile.represent_id,homestay_id=homestay_id)
                            ui.weight = ui.weight - 2 if ui.weight >= 2 else 0 
                            ui.status=0
                            ui.save()
                        except UserInteraction.DoesNotExist:
                            new_user_interaction = UserInteraction(user_id=profile.represent_id,homestay_id=homestay_id,weight=0)
                            new_user_interaction.save()
        except Profile.DoesNotExist:
            return None
    
    def get_comments(self,limit,offset,homestay_id):
        comment_service = CommentService()
        comments = comment_service.get_comments_with_userinfo(homestay_id=homestay_id,limit=limit,offset=offset)
        if not(comments is None):
            comments_data = CommentSerializer(comments, many=True).data
            return comments_data
        else:
            return []
    
    def add_comment(self,comment,current_user):
        user_service = UserService()
        text_ = []
        text = re.split('tuy|nhưng',comment.content)
        user_id = user_service.get_profileid_from_auth_userid(current_user)
        for txt in text:
            txt = txt.split('.')
            for t in txt:
                text_.append(t)
        final_label = 0
        with graph.as_default():
            final_label = classify_comment(text_)
        self.update_user_interaction(comment.homestay_id,int(final_label),me=current_user)
        new_comment = Comment(homestay_id=comment.homestay_id,user_id=user_id, content=comment.content,sentiment=final_label)
        new_comment.save()
        new_comment_raw = CommentSerializer(new_comment).data
        return new_comment_raw