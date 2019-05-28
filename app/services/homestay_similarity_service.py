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

class HomestaySimilarityService:
    def get_id(self,homestay_sim,current_homestay_id):
        first = str(homestay_sim['first_homestay_id'])
        second = str(homestay_sim['second_homestay_id'])
        if (current_homestay_id == first):
            return second
        else:
            return first
    
    def get_similarity_by_homestayid(self,homestay_id):
        return HomestaySimilarity.objects.filter(Q(first_homestay_id=homestay_id) | Q(second_homestay_id=homestay_id)).order_by('-score')
    
    def get_list_remaining_homestayid(self,homestay_id,homestays):
        ids = list(map(lambda x : (x['first_homestay_id'] if x['first_homestay_id'] != int(homestay_id) else x['second_homestay_id']),homestays))
        ids = list(map(lambda x: int(x),ids))
        return ids
    
    def get_list_homestay_sims_with_range(self,limit,offset,homestay_sims):
        homestays = []
        if((limit is not None) and (offset is not None)):
            homestays = homestay_sims[int(offset):int(limit) + int(offset)]
        else:
            homestays = homestay_sims[0:8]
        return homestays
    
    def create_list_scores(self,current_homestay,other_homestays):
        arr_score = []
        vector_1 = embed_to_vector(current_homestay)
        print('def create_list_scores(self,current_homestay,other_homestays): ======> vector_1',vector_1)
        for other_homestay in other_homestays:
            check_id = other_homestay['homestay_id']
            vector_2 = embed_to_vector(other_homestay)
            score = get_score(vector_1, vector_2)
            if(check_id in [3196, 175, 745, 4078, 177, 3475, 4427, 3627]):
                print('def create_list_scores(self,current_homestay,other_homestays): ==============> score11111',vector_2[0],score)
            if(vector_2[0]['city'] == 'ninhbinh'):
                print('def create_list_scores(self,current_homestay,other_homestays): ==============> score2222',vector_2[0],score)
            arr_score.append(score)
        return arr_score

    def add_list_scores_to_db(self,list_scores):
        connection.cursor().execute("INSERT INTO app_homestaysimilarity (first_homestay_id,second_homestay_id,score) VALUES " +convert_to_text(list_scores)+';')
    
    def update_list_scores_to_db(self,list_scores,current_homestay):
        connection.cursor().execute("DELETE FROM app_homestaysimilarity WHERE first_homestay_id=" + str(current_homestay['homestay_id']) + " OR second_homestay_id=" + str(current_homestay['homestay_id']))
        print('_____________________________________________________________________')
        connection.cursor().execute("INSERT INTO app_homestaysimilarity (first_homestay_id,second_homestay_id,score) VALUES " + convert_to_text(list_scores)+';')
        return True
    
    def delete_scores_from_fb(self,homestay_id):
        main_query = Q()
        main_query.add(Q(first_homestay_id=homestay_id), Q.OR)
        main_query.add(Q(second_homestay_id=homestay_id), Q.OR)
        homestay_similarities = HomestaySimilarity.objects.filter(main_query)
        homestay_similarities.delete()
        return True