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
from ..utils import embed_to_vector, get_score, convert_to_text,get_cropped_size_image
from ..services.user_service import UserService
from ..services.homestay_rate_service import HomestayRateService
from ..services.homestay_service import HomestayService
from ..services.homestay_similarity_service import HomestaySimilarityService
import textdistance

class HomestayController:
    def __init__(self):
        self.homestay = None
        self.homestays = None


    def update_user_interaction(self,me,homestay_id):
        try:
            if me is not None:
                profile = Profile.objects.get(email=me.email)
                if profile.represent_id is not None:
                    try:
                        ui = UserInteraction.objects.get(user_id=profile.represent_id,homestay_id=homestay_id)
                        ui.weight = ui.weight + 1
                        ui.status = 0
                        ui.save()
                        print('ui',ui)
                    except UserInteraction.DoesNotExist:
                        new_user_interaction = UserInteraction(user_id=profile.represent_id,homestay_id=homestay_id,weight=1)
                        new_user_interaction.save()
                        print('new_user_interaction: ',new_user_interaction)
        except Profile.DoesNotExist:
            print('DCM')
            return None

    def get_homestay(self,current_user,homestay_id,type_get):
        user_service = UserService()
        homestay_rate_service = HomestayRateService()
        homestay_service = HomestayService()
        authorize = user_service.authorize_user(current_user,type_get)
        print('def get_homestay(self,current_user,homestay_id,type_get):__ ============>',authorize)
        if authorize == False:
            return None,401
        mode = None
        profile_id = user_service.get_profileid_from_auth_userid(current_user)
        if user_service.check_anonymous(current_user):
            mode = 'anonymous'
        elif user_service.is_admin(my_email=current_user.email):
            mode = 'admin'
        elif homestay_service.is_owner(user_id=profile_id,homestay_id=homestay_id):
            mode = 'host'
        homestay_obj = homestay_service.get_detail_homestay(homestay_id=homestay_id,mode=mode)
        if homestay_obj is None:
            return None,204
        homestay = HomestaySerializer(homestay_obj).data
        host_id = homestay['host_id']
        host_profile = user_service.get_profile_host(host_id=host_id)
        homestay_rate = homestay_rate_service.get_homestay_rate(profile_id, homestay_id)
        homestay_with_hostinfo = {
            'homestay_info': homestay,
            'host_info': None,
            'me_rate': None
        }            
        if not (host_profile is None):
            host_profile = ProfileSerializer(host_profile).data
            homestay_with_hostinfo['host_info'] = host_profile

        if not(homestay_rate is None):
            homestay_rate_data = HomestayRateSerializer(homestay_rate).data
            if homestay_rate_data['isType'] == 1:
                homestay_with_hostinfo['me_rate'] = 'like'
            if homestay_rate_data['isType'] == 2:
                homestay_with_hostinfo['me_rate'] = 'dislike'
        self.update_user_interaction(current_user,homestay_id)
        return homestay_with_hostinfo,200
    
    def get_many_homestays(self,limit,offset):
        homestay_service = HomestayService()
        user_service = UserService()
        queryset_homestays = homestay_service.get_homestays(limit=int(limit), offset=int(offset))
        homestay_serializer = HomestaySerializer(
            queryset_homestays, many=True)
        homestays_data = homestay_serializer.data
        responses = []
        for homestay in homestays_data:
            host_id = homestay['host_id']
            host_profile = user_service.get_profile_host(host_id=host_id)
            homestay_with_hostinfo = {
                'homestay_info': homestay,
                'host_info': None
            }
            if not (host_profile is None):
                host_profile = ProfileSerializer(host_profile).data
                homestay_with_hostinfo['host_info'] = host_profile
            responses.append(homestay_with_hostinfo)
        return responses
    
    def search_homestay(self,current_user=None,host_id=None,name=None,ids=None,offset=None,limit=None,city=None,price_range=None,order_by=None,admin_mode=None,is_allowed=1):
        homestay_service = HomestayService()
        user_service = UserService()
        host_mode = None
        if user_service.authorize_me(user_id=host_id,me=current_user) == False:
            host_mode = False
        else:
            host_mode = True
        main_query = homestay_service.get_query_search_homestay(name=name,host_id=host_id,city=city,price_range=price_range,ids=ids,admin_mode=admin_mode,is_allowed=is_allowed,host_mode=host_mode)
        queryset = homestay_service.search_homestay(main_query, order_by)
        response_data = None
        total = HomestaySerializer(queryset, many=True).data
        response_data = homestay_service.get_list_homestays_with_range(limit=limit,offset=offset,homestays=total)
        return response_data,total
    
    def get_similars(self,homestay_id,limit,offset):
        if limit is None:
            limit = 8
        if offset is None:
            offset = 0
        homestay_similarity_service = HomestaySimilarityService()
        homestay_service = HomestayService()
        homestay_sims = homestay_similarity_service.get_similarity_by_homestayid(homestay_id=homestay_id)
        homestay_sims = HomestaySimilaritySerializer(homestay_sims,many=True).data
        start_limit = int(limit)
        end_limit = 0
        adjusted_limit = int(limit)
        homestays = []
        while start_limit - end_limit > 0:
            homestays = homestay_similarity_service.get_list_homestay_sims_with_range(limit=adjusted_limit,offset=offset,homestay_sims=homestay_sims)
            ids = homestay_similarity_service.get_list_remaining_homestayid(homestay_id=homestay_id,homestays=homestays)
            homestays = homestay_service.get_list_homestay_with_ids(ids)
            end_limit = len(homestays)
            adjusted_limit += start_limit - end_limit
        return HomestaySerializer(homestays,many=True).data

    def get_top_relates(self,limit,offset,current_user):
        user_service = UserService()
        homestay_service = HomestayService()
        my_profile = user_service.get_profile_by_email(email=current_user.email)
        allowed_list_homestays = homestay_service.get_list_homestay_by_permission(is_allowed=1,status=1)
        allowed_list_homestays = HomestaySerializer(allowed_list_homestays,many=True).data
        represent_list = homestay_service.get_list_represent_id(homestays=allowed_list_homestays)
        my_represent_id = ProfileSerializer(my_profile).data['represent_id']
        predictions = []
        with graph_recommendation.as_default():
            predictions = get_predictions(my_represent_id,represent_list)
        predictions = sorted(predictions,key=lambda x: x[1],reverse=True)
        ids = map(lambda x : x[0],predictions)
        ids = list(ids)
        print('get_top_relates ==========> ids',ids[0:20])
        homestays = homestay_service.get_list_homestays_with_ids_and_range(ids=ids,limit=limit,offset=offset)
        return homestays

    def create_homestay(self,homestay,current_user):
        homestay_service = HomestayService()
        user_service = UserService()
        host_id = user_service.get_profileid_from_auth_userid(current_user)
        represent_id = homestay_service.get_next_represent_id()
        new_homestay = Homestay(represent_id=represent_id,main_price=homestay.main_price,price_detail=homestay.price_detail,amenities=homestay.amenities,amenities_around=homestay.amenities_around,name=homestay.name,descriptions=homestay.descriptions,highlight=homestay.highlight,images=homestay.images,city=homestay.city,district=homestay.district,host_id=host_id)
        new_homestay.save()
        return HomestaySerializer(new_homestay).data
    
    def delete_homestay(self,homestay_id,current_user):
        homestay_service = HomestayService()
        user_service = UserService()
        if not current_user.is_anonymous:
            my_email = current_user.email
            if user_service.is_admin(my_email=my_email):
                homestay_service.update_status_homestay(homestay_id=homestay_id,status=-1)
                return {'msg': '200'}
            else:
                return {'msg': '401'}
        else:
            return {'msg': '401'}
    
    def update_homestay(self,homestay_id,homestay):
        old_homestay = Homestay.objects.get(homestay_id=homestay_id)
        if(old_homestay):
            old_homestay.name = homestay.name if homestay.name is not None else old_homestay.name
            old_homestay.descriptions = homestay.descriptions if homestay.descriptions is not None else old_homestay.descriptions
            old_homestay.highlight = homestay.highlight if homestay.highlight is not None else old_homestay.highlight
            old_homestay.city = homestay.city if homestay.city is not None else old_homestay.city
            old_homestay.district = homestay.district if homestay.district is not None else old_homestay.district
            old_homestay.main_price = homestay.main_price if homestay.main_price is not None else old_homestay.main_price
            old_homestay.price_detail = homestay.price_detail if homestay.price_detail is not None else old_homestay.price_detail
            old_homestay.amenities = homestay.amenities if homestay.amenities is not None else old_homestay.amenities
            old_homestay.amenities_around = homestay.amenities_around if homestay.amenities_around is not None else old_homestay.amenities_around
            old_homestay.images = homestay.images if homestay.images is not None else old_homestay.images
            update_result = old_homestay.save()
            return HomestaySerializer(old_homestay).data
        return None
    
    def approve_homestay(self,homestay_id,current_user):
        user_service = UserService()
        homestay_service = HomestayService()
        my_email = current_user.email
        if not user_service.is_admin(my_email=my_email):
            return 401
        homestay = homestay_service.get_homestay_by_id(homestay_id=homestay_id)
        if homestay is not None:
            homestay.is_allowed = 1
            homestay.save()
            return 200
        else:
            return 204

    def upload_homestay_photo(self,_file):
        url_image = get_cropped_size_image(_file=_file)
        return url_image
   
    def update_similars(self,homestay_id):
        homestay_service = HomestayService()
        homestay_similarity_service = HomestaySimilarityService()
        current_homestay = homestay_service.get_homestay_by_id(homestay_id=homestay_id)
        other_homestays = homestay_service.get_list_other_homestays(homestay_id=homestay_id)
        other_homestays = HomestaySerializer(
            other_homestays, many=True).data
        current_homestay = HomestaySerializer(current_homestay).data
        arr_score = homestay_similarity_service.create_list_scores(current_homestay=current_homestay,other_homestays=other_homestays)
        homestay_similarity_service.update_list_scores_to_db(list_scores=arr_score,current_homestay=current_homestay)
        return True
    def create_similars(self,homestay_id):
        homestay_service = HomestayService()
        homestay_similarity_service = HomestaySimilarityService()
        current_homestay = homestay_service.get_homestay_by_id(homestay_id=homestay_id)
        other_homestays = homestay_service.get_list_other_homestays(homestay_id=homestay_id)
        other_homestays = HomestaySerializer(
            other_homestays, many=True).data
        current_homestay = HomestaySerializer(current_homestay).data
        arr_score = homestay_similarity_service.create_list_scores(current_homestay=current_homestay,other_homestays=other_homestays)
        homestay_similarity_service.add_list_scores_to_db(list_scores=arr_score)
        return True
    
    def delete_similars(self,homestay_id):
        homestay_similarity_service = HomestaySimilarityService()
        homestay_similarity_service.delete_scores_from_fb(homestay_id=homestay_id)
        return True
    
    def get_list_homestays_by_admin(self,current_user,limit,offset,is_allowed,ids=None,name=None):
        user_service = UserService()
        homestay_service = HomestayService()
        my_email = current_user.email
        if not user_service.is_admin(my_email=my_email):
            return None,0, 401
        if ids is None and name is None:
            homestays = homestay_service.get_list_homestay_by_permission(is_allowed=is_allowed,status=None)
            homestays = HomestaySerializer(homestays,many=True).data
            _homestays = homestay_service.get_list_homestays_with_range(limit=limit,offset=offset,homestays=homestays)
            return _homestays,len(homestays), 200
        else:
            _homestays,total = self.search_homestay(ids=ids,admin_mode=True,name=name,is_allowed=is_allowed)
            return _homestays,total,200
    
    def lock_homestay(self,homestay_id,current_user):
        user_service = UserService()
        homestay_service = HomestayService()
        my_email = current_user.email
        if not user_service.is_admin(my_email=my_email):
            return None,401
        homestay = homestay_service.get_homestay_by_id(homestay_id=homestay_id)
        if homestay is None:
            return None,404
        new_status = None
        if homestay.status == 1:
            new_status = -2
        elif homestay.status == -2:
            new_status = 1
        homestay_service.update_status_homestay(homestay_id=homestay_id,status=new_status)
        return new_status,200