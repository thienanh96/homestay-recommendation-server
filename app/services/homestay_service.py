import ast
import schedule
import _thread
import re
from django.shortcuts import render
from rest_framework import generics
from rest_framework import permissions, authentication, pagination
from rest_framework.response import Response
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

class HomestayService:
    def get_homestays(self,limit,offset):
        return Homestay.objects.filter(is_allowed=1,status=1).order_by('created_at')[offset:offset+limit]
    
    def get_detail_homestay(self,homestay_id,mode=None):
        if mode == 'admin' or mode == 'host':
            return Homestay.objects.filter(~Q(status=-1)).get(homestay_id=homestay_id) 
        if mode == 'anonymous':
            return Homestay.objects.filter(is_allowed=1,status=1).get(homestay_id=homestay_id)
        return Homestay.objects.filter(is_allowed=1,status=1).get(homestay_id=homestay_id)
    
    def is_owner(self,user_id,homestay_id):
        try:
            if user_id is None or homestay_id is None:
                return False
            hs = Homestay.objects.get(homestay_id=homestay_id)
            if int(user_id) == int(hs.host_id):
                return True
            return False
        except Homestay.DoesNotExist:
            return False
    
    def search_homestay(self, query, order_by):
        if order_by == 'main_price_desc':
            return Homestay.objects.filter(query).order_by('-main_price')
        elif order_by == 'main_price_asc':
            return Homestay.objects.filter(query).order_by('main_price')
        elif order_by == 'likes':
            return Homestay.objects.filter(query).order_by('-likes')
        return Homestay.objects.filter(query).order_by('-created_at')
    
    
    def get_list_homestay_with_ids(self,ids):
        ordering = 'FIELD(`homestay_id`, %s)' % ','.join(str(idd) for idd in ids)
        homestays = Homestay.objects.filter(homestay_id__in=ids,is_allowed=1,status=1).extra(select={'ordering': ordering}, order_by=('ordering',))
        # homestays = HomestaySerializer(homestays,many=True).data
        return homestays
    
    def get_list_homestays_with_ids_and_range(self,ids,limit,offset):
        final_limit = 10
        final_offset = 0
        if((limit is not None) and (offset is not None)):
            final_limit = int(limit)
            final_offset = int(offset)
        homestays = []
        ordering = 'FIELD(`represent_id`, %s)' % ','.join(str(idd) for idd in ids)
        homestays = Homestay.objects.filter(represent_id__in=ids).extra(select={'ordering': ordering}, order_by=('ordering',))
        homestays = homestays[final_offset:final_limit + final_offset]
        homestays = HomestaySerializer(homestays,many=True).data
        return homestays

    def get_list_represent_id(self,homestays):
        ids = map(lambda x : x['represent_id'],homestays)
        return list(ids)
    
    def get_list_homestay_by_permission(self,is_allowed,status):
        query = Q()
        if status is None:
            print('check status: ',status)
            query.add(~Q(status=-1),Q.AND)
            query.add(Q(is_allowed=is_allowed),Q.AND)
        else:
            query.add(Q(status=status),Q.AND)
            query.add(Q(is_allowed=is_allowed),Q.AND)
        return Homestay.objects.filter(query)
    
    def get_next_represent_id(self):
        last = Homestay.objects.latest()
        try:
            if last is not None:
                return int(HomestaySerializer(last).data['represent_id'] + 1)
            else:
                return  0
        except Exception as e:
            return 0
    
    def get_query_search_homestay(self,name,host_id,city,price_range,ids,admin_mode,host_mode,is_allowed=1):
        main_query = Q()
        if admin_mode is not None:
            main_query.add(Q(is_allowed=is_allowed),Q.AND)
            main_query.add(~Q(status=-1),Q.AND)
        elif host_mode is True:
            main_query.add(~Q(status=-1),Q.AND)
        else:
            main_query.add(Q(is_allowed=1),Q.AND)
            main_query.add(Q(status=1),Q.AND)
        if(name is not None):
            main_query.add(Q(name__icontains=name), Q.AND)
        elif(ids is not None):
            ids = ids.split(',')
            main_query.add(Q(homestay_id__in=ids),Q.AND)
        if(host_id is not None):
            main_query.add(Q(host_id=host_id),Q.AND)
        else:
            if(city is not None):
                main_query.add(Q(city__icontains=city), Q.AND)
            if(price_range is not None):
                price_range = price_range.split(',')
                start_price = float(price_range[0])
                end_price = float(price_range[1])
                main_query.add(Q(main_price__gte=start_price), Q.AND)
                main_query.add(Q(main_price__lte=end_price), Q.AND)
        return main_query
    
    def get_list_homestays_with_range(self,limit,offset,homestays):
        new_homestays = []
        if(limit is not None and offset is not None):
            new_homestays = homestays[int(offset):int(offset) + int(limit)]
        else:
            new_homestays = homestays[0:9]
        return new_homestays
    
    def get_homestay_by_id(self,homestay_id):
        try:
            return Homestay.objects.get(homestay_id=homestay_id)
        except Homestay.DoesNotExist:
            return None
        
    
    def get_list_other_homestays(self,homestay_id):
        return Homestay.objects.filter(~Q(homestay_id=homestay_id))
    
    def update_status_homestay(self,homestay_id,status):
        homestay = Homestay.objects.get(homestay_id=homestay_id)
        homestay.status = status
        homestay.save()
        return homestay
