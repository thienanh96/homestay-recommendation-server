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
from .serializers import ProfileSerializer, HomestayRateSerializer, HomestaySerializer, TokenSerializer, UserSerializer, CommentSerializer, HomestaySimilaritySerializer,PostSerializer,PostLikeRefSerializer,UserInteractionSerializer
from .models import Homestay, Profile, HomestayRate, Comment, HomestaySimilarity,PostLikeRef,Post,UserInteraction
from .custom_query import search_homestay
from django.db.models import Q
from django.db import connection
from .comment_classification import classify_comment,graph
from functools import reduce
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from scipy.spatial import distance
from unidecode import unidecode
import cloudinary
from cloudinary.uploader import upload
from cloudinary.utils import cloudinary_url
from .recommendation import get_predictions,graph_recommendation,train_model
from .validation import Validation
import time;
import threading
from .utils import embed_to_vector, get_score, convert_to_text,get_response
import textdistance
from .controllers.homestay_controller import HomestayController
from .controllers.homestay_rate_controller import HomestayRateController
from .controllers.comment_controller import CommentController
from .controllers.post_controller import PostController
from .controllers.user_controller import UserController
from .controllers.post_like_ref_controller import PostLikeRefController
TIME_RETRAIN = 60*60*24
# Get the JWT settings
jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER
COUNT_USER_INTERACTION = 0
#Config Cloundinary
# cloudinary.config( 
#   cloud_name = "homestayhub", 
#   api_key = "324217692173642", 
#   api_secret = "fYCSwPmuwwhAMZDcE0ZYZREomKM" 
# )
# labels = keras_text_classifier.classify('hihi')
# print(labels)



def train_schedule():
    try:
        user_interactions = UserInteraction.objects.filter(status=0)
        user_interactions = UserInteractionSerializer(user_interactions,many=True).data
        count = len(user_interactions)
        if count >= COUNT_USER_INTERACTION:
            labels = []
            users = []
            rooms = []
            for ui in user_interactions:
                user_id = int(ui['user_id'])
                weight = float(ui['weight'])
                homestay_id = int(ui['homestay_id'])
                try:
                    _homestay = Homestay.objects.get(homestay_id=homestay_id)
                    _homestay = HomestaySerializer(_homestay).data
                    rep_id = int(_homestay['represent_id'])
                    users.append(user_id)
                    if weight > 0:
                        labels.append(1)
                    else:
                        labels.append(0)
                    rooms.append(rep_id)
                except Homestay.DoesNotExist:
                    continue
            print('check training: user',users)
            print('check training: rooms',rooms)
            print('check training: labels',labels)
            with graph_recommendation.as_default():
                if(len(users) > 0):
                    train_model(users,rooms,labels)
                    UserInteraction.objects.all().update(status=1)       
    except Exception as e:
        print(e)

def listen_for_timechange():
    starttime=time.time()
    while True:
        train_schedule()
        time.sleep(TIME_RETRAIN) 

# starttime=time.time()
# while True:
#   print('stick')
#   time.sleep(20)

t4 = threading.Thread(target = listen_for_timechange, args=())
# t4.start()

# schedule.every(1).minutes.do(train_schedule)
# while True:
#     schedule.run_pending()
#     time.sleep(1) 

# def get_profileid_from_auth_userid(me):
#     if not me.is_anonymous:
#         try:
#             profile = Profile.objects.get(email=me.email)
#             return profile.id
#         except Profile.DoesNotExist:
#             return None
#     else:
#         return None

class GetHomestayView(generics.RetrieveAPIView):
    queryset = Homestay.objects.filter(is_allowed=1,status=1)
    serializer_class = HomestaySerializer
    # authentication_classes = (authentication.BasicAuthentication,)

    def get(self,request, homestay_id):
        try:
            type_get = self.request.query_params.get('type-get', None)
            homestay_controller = HomestayController()
            homestay_with_hostinfo,status_http = homestay_controller.get_homestay(self.request.user,homestay_id,type_get)
            return get_response(_status=status_http,data_for_ok=homestay_with_hostinfo)
        except Exception as e:
            print(e)
            return get_response(_status=500)


class GetHomestayWithPaginationView(generics.RetrieveAPIView):
    queryset = Homestay.objects.filter(is_allowed=1,status=1)
    authentication_classes = (authentication.BasicAuthentication,)

    def get(self, request):
        try:
            limit = self.request.query_params.get('limit', None)
            offset = self.request.query_params.get('offset', None)
            homestay_controller = HomestayController()
            responses = homestay_controller.get_many_homestays(limit=limit,offset=offset)
            return Response({'status': 200, 'data': responses}, 200)
        except Exception as e:
            return Response({'status': 500, 'message': e}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SearchHomestayView(generics.ListCreateAPIView):
    queryset = Homestay.objects.filter(is_allowed=1,status=1)
    # authentication_classes = (authentication.BasicAuthentication,)

    def get(self, request):
        try:
            host_id = self.request.query_params.get('host_id',None)
            name = self.request.query_params.get('name', None)
            ids = self.request.query_params.get('ids', None)
            offset = self.request.query_params.get('offset', None)
            limit = self.request.query_params.get('limit', None)
            city = self.request.query_params.get('city', None)
            price_range = self.request.query_params.get('price_range', None)
            order_by = self.request.query_params.get('order_by', None)
            homestay_controller = HomestayController()
            response_data,total = homestay_controller.search_homestay(current_user=request.user,host_id=host_id,name=name,ids=ids,offset=offset,limit=limit,city=city,price_range=price_range,order_by=order_by)
            return Response({'status': 200, 'data': response_data, 'total': len(total)}, 200)
        except Exception as e:
            print(e)
            return Response({'status': 500, 'message': 'loi'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LoginView(generics.CreateAPIView):
    """
    POST auth/login/
    """

    # This permission class will over ride the global permission
    # class setting
    permission_classes = (permissions.AllowAny,)

    queryset = User.objects.all()

    def post(self, request, *args, **kwargs):
        try:
            email = request.data.get("email", "")
            password = request.data.get("password", "")
            user = authenticate(request, email=email, password=password)

            if user is not None:
                # login saves the user’s ID in the session,
                # using Django’s session framework.
                login(request, user)
                profile = Profile.objects.get(email=user.email)
                serializer = TokenSerializer(data={
                    # using drf jwt utility functions to generate a token
                    "token": jwt_encode_handler(
                        jwt_payload_handler(profile)
                    )})
                serializer.is_valid()
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response({'status': 200, 'message': 'User Not Found'}, status=status.HTTP_200_OK)
        except Exception as e:
            print('Loi', e)
            return Response({'status': 500, 'message': 'Something went wrong'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RegisterUsers(generics.CreateAPIView):
    """
    POST auth/register/
    """
    permission_classes = (permissions.AllowAny,)

    def post(self, request, *args, **kwargs):
        try:
            username = request.data.get("fullname", "Ẩn danh")
            print('username: ',username)
            password = request.data.get("password", "")
            gender = request.data.get("gender", None)
            birthday = request.data.get("birthday", None)
            address = request.data.get("address", None)
            email = request.data.get("email", "")
            avatar= request.data.get('avatar',"")
            join_date = request.data.get('joinDate','')
            last = Profile.objects.latest()
            rep_id = int(ProfileSerializer(last).data['represent_id'] + 1)
            if not username and not password and not email:
                return Response(
                    data={
                        "message": "username, password and email is required to register a user"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            new_user = User.objects.create_user(
                username=username, password=password, email=email
            )
            new_profile = Profile(user_name=username,email=email,represent_id=rep_id,avatar = avatar,join_date=join_date)
            new_profile.save()
            return Response(
                data=UserSerializer(new_user).data,
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            print('Loi', e)
            return Response({'fullname': 'Tên đăng nhập đã tồn tại'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RateHomestayView(generics.CreateAPIView):
    queryset = HomestayRate.objects.all()
    serializer_class = HomestayRateSerializer
    permission_classes = (permissions.IsAuthenticated,)
    # authentication_classes = (authentication.,)

    
    def post(self, request, *args, **kwargs):
        try:
            homestay_id = request.data.get("homestay_id", "")
            type_rate = request.data.get("type_rate", "")
            homestay_rate_controller = HomestayRateController()
            profile_id,action_type = None,None
            if type_rate == 1 or type_rate == '1':
                profile_id,action_type = homestay_rate_controller.add_homestay_like(homestay_id=homestay_id,type_rate=1,current_user=request.user,user_id=None)
            elif type_rate == 2 or type_rate == '2':
                profile_id,action_type = homestay_rate_controller.add_homestay_dislike(homestay_id=homestay_id,type_rate=type_rate,current_user=request.user,user_id=None)
            return Response(
                data={'type_rate': type_rate, 'homestay_id': homestay_id,
                        'user_id': profile_id, 'status': 200, 'action_type': action_type},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            print('eeeee: ',e)
            return Response({'status': 500, 'message': e}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetMyHomestayRateView(generics.RetrieveAPIView):
    queryset = HomestayRate.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        try:
            if request.user is None:
                return Response(data={}, status=status.HTTP_401_UNAUTHORIZED)
            homestay_rate_controller = HomestayRateController()
            homestay_id = self.request.query_params.get('homestay_id', None)
            me_rate = None
            if(homestay_id is not None):
                me_rate = homestay_rate_controller.get_my_homestay_rate(current_user=request.user,homestay_id=homestay_id)
                return Response(data={'me_rate': me_rate},status=status.HTTP_200_OK)
            else:
                return Response({}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({'status': 500, 'message': e}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetCommentWithPaginationView(generics.RetrieveAPIView):
    queryset = Comment.objects.all()
    authentication_classes = (authentication.BasicAuthentication,)

    def get(self, request, *args, **kwargs):
        try:
            homestay_id = self.request.query_params.get('homestay_id', None)
            limit = self.request.query_params.get('limit', None)
            offset = self.request.query_params.get('offset', None)
            comment_controller = CommentController()
            comments_data = comment_controller.get_comments(limit,offset,homestay_id)
            return Response(data=comments_data, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response({'message': 'loi roi'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CreateCommentView(generics.CreateAPIView):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        try:
            homestay_id = request.data.get("homestay_id", None)
            content = request.data.get("content", '')
            comment = Comment(homestay_id=homestay_id,content=content)
            comment_controller = CommentController()
            new_comment_raw = comment_controller.add_comment(comment=comment,current_user=request.user)
            return Response(data=new_comment_raw, status=status.HTTP_200_OK)
        except Exception as e:
            print('loi', e)
            return Response({'message': 'loi roi'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetHomestaySimilarityView(generics.ListCreateAPIView):
    queryset = HomestaySimilarity.objects.all()
    serializer_class = HomestaySimilaritySerializer
    # authentication_classes = (authentication.BasicAuthentication,)

    def get(self, request):
        try:
            limit = self.request.query_params.get('limit', None)
            offset = self.request.query_params.get('offset', None)
            homestay_id = self.request.query_params.get('homestay_id', None)
            homestay_controller = HomestayController()
            homestays = homestay_controller.get_similars(homestay_id=homestay_id,limit=limit,offset=offset)
            return Response(data=homestays, status=status.HTTP_200_OK)
        except Exception as e:
            print('loi', e)
            return Response({'message': 'loi roi'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class UpdateHomestaySimilarityView(generics.UpdateAPIView):
    queryset = HomestaySimilarity.objects.all()
    serializer_class = HomestaySimilaritySerializer
    permission_classes = (permissions.IsAuthenticated,)
    # authentication_classes = (authentication.BasicAuthentication,)

    def put(self, request, *args, **kwargs):
        try:
            homestay_id = request.data.get("homestay_id", None)
            homestay_controller = HomestayController()
            homestay_controller.update_similars(homestay_id=homestay_id)
            return Response(data={'msg': 'ok'}, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response({'msg': 'fail'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CreateHomestaySimilarityView(generics.ListCreateAPIView):
    queryset = HomestaySimilarity.objects.all()
    serializer_class = HomestaySimilaritySerializer
    permission_classes = (permissions.IsAuthenticated,)
    # authentication_classes = (authentication.BasicAuthentication,)

    def post(self, request, *args, **kwargs):
        try:
            homestay_id = request.data.get("homestay_id", None)
            homestay_controller = HomestayController()
            homestay_controller.create_similars(homestay_id=homestay_id)
            return Response(data={'msg': 'ok'}, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response({'msg': 'fail'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DeleteHomestaySimilarityView(generics.DestroyAPIView):
    queryset = HomestaySimilarity.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def delete(self,request,homestay_id):
        try:
            homestay_controller = HomestayController()
            homestay_controller.delete_similars(homestay_id=homestay_id)
            return Response(data={'msg': 'ok'}, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response({'msg': 'fail'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetPostsView(generics.RetrieveAPIView):
    queryset = Post.objects.all()
    count = Post.objects.count()
    # authentication_classes = (authentication.BasicAuthentication,)
    
    def get(self, request, *args, **kwargs):
        try:
            filter_get = self.request.query_params.get('filter', 'newest')
            limit = self.request.query_params.get('limit', None)
            offset = self.request.query_params.get('offset', None)
            post_controller = PostController()
            posts,total = post_controller.get_posts(limit=limit,offset=offset,order_by=filter_get,current_user=request.user)
            return Response(data={'data': posts,'total': total},status=status.HTTP_200_OK)            
        except Exception as e:
            print(e)
            return Response({'msg': 'fail'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CreatePostView(generics.ListCreateAPIView):
    queryset = Post.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        try:
            post_controller = PostController()
            homestay_id = request.data.get("homestay_id", None)
            content = request.data.get('content','')     
            if(homestay_id is None):
                return Response({'msg': 'fail'}, status=status.HTTP_400_BAD_REQUEST)
            post = Post(homestay_id=homestay_id,content=content)
            new_post = post_controller.create_post(post=post,current_user=request.user)
            return Response(data=new_post, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response({'msg': 'fail'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetConformHomestay(generics.RetrieveAPIView):
    queryset = Homestay.objects.filter(is_allowed=1,status=1)
    homestay_count = Homestay.objects.count()
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        try:
            limit = self.request.query_params.get('limit', None)
            offset = self.request.query_params.get('offset', None)
            homestay_controller = HomestayController()
            homestays = homestay_controller.get_top_relates(limit=limit,offset=offset,current_user=request.user)
            return Response(data=homestays, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response(data={}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UploadPhotoView(generics.ListCreateAPIView):
    queryset = Homestay.objects.filter(is_allowed=1)
    # permission_classes = (permissions.NOT,)
    def post(self, request, *args, **kwargs):
        try:
            homestay_controller = HomestayController()
            url = homestay_controller.upload_homestay_photo(request.FILES['img'])
            print('urlll: ',url)
            return Response(data={'url':url}, status=status.HTTP_200_OK)
        except Exception as e:
            print('loi upload: ',e)
            return Response(data={}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CreateHomestayView(generics.ListCreateAPIView):
    queryset = Homestay.objects.latest()
    permission_classes = (permissions.IsAuthenticated,)

    # def get_next_rep_id(self):
    #     last = self.get_queryset()
    #     try:
    #         if last is not None:
    #             return int(HomestaySerializer(last).data['represent_id'] + 1)
    #         else:
    #             return  0
    #     except Exception as e:
    #         return 0

    def post(self, request, *args, **kwargs):
        try:
            desc = request.data.get('descriptions')
            highlight = request.data.get('highlight')
            city =  request.data.get('city')
            district =  request.data.get('district')
            name =  request.data.get('name')
            main_price =  request.data.get('main_price')
            detail_price =  request.data.get('price_detail')
            amenities =  request.data.get('amenities')
            amenities_around = request.data.get('amenities_around')
            images = request.data.get('images')
            homestay_controller = HomestayController()
            new_homestay = Homestay(main_price=main_price,price_detail=detail_price,amenities=amenities,amenities_around=amenities_around,name=name,descriptions=desc,highlight=highlight,images=images,city=city,district=district)
            new_homestay = homestay_controller.create_homestay(homestay=new_homestay,current_user=request.user)
            return Response(data=new_homestay, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response(data={}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UpdateProfileView(generics.UpdateAPIView):
    queryset = Profile.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def put(self, request, *args, **kwargs):
        try:
            address = request.data.get('address')
            phone = request.data.get('phone')
            prefix = request.data.get('prefix')
            password =  request.data.get('password')
            username =  request.data.get('username')
            avatar = request.data.get('avatar')
            user_controller = UserController()
            new_user = Profile(address=address,phone=str(prefix + phone),user_name=username,avatar=avatar)
            update_result,new_token = user_controller.update_user(user=new_user,user_id=None,current_user=request.user,password=password)
            if(update_result is not None):
                return get_response(_status=200,data_for_ok={'new_profile': update_result, 'new_token': new_token})
            else:
                return Response(data={}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print('class UpdateProfileView(generics.UpdateAPIView): ===> e',e)
            return Response(data={}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetProfileView(generics.ListCreateAPIView):
    queryset = Profile.objects.all()
    # permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        try:
            me = self.request.query_params.get('me', None)
            user_id = self.request.query_params.get('user_id', None)
            user_controller = UserController()
            my_profile = None
            if me is not None:
                my_profile = user_controller.get_me(request.user)
            else:
                my_profile = user_controller.get_one_user(user_id)
            if my_profile is not None:
                return Response(data=ProfileSerializer(my_profile).data, status=status.HTTP_200_OK)
            return Response(data={}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(e)
            return Response(data={}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetListProfileView(generics.ListCreateAPIView):
    queryset = Profile.objects.filter(~Q(user_type='admin'))
    # permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        try:
            limit = self.request.query_params.get('limit', 8)
            offset = self.request.query_params.get('offset', 0)
            name = self.request.query_params.get('name', None)
            user_id = self.request.query_params.get('user_id', None)
            user_controller = UserController()
            count, list_profiles = user_controller.get_many_users(limit=limit,offset=offset,name=name,user_id=user_id)
            return Response(data={'dt': list_profiles, 'total': count}, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response(data={}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DeleteProfileView(generics.DestroyAPIView):
    queryset = Profile.objects.all()
    permission_classes = (permissions.IsAuthenticated,)


    def delete(self,request,profile_id):
        try:
            my_profile = request.user
            user_controller = UserController()
            msg = user_controller.delete_user(user_id=profile_id,current_user=my_profile)
            _status = int(msg['status'])
            response = get_response(_status=_status)
            return response
        except Exception as e:
            print(e)
            return get_response(_status=500)

class DeleteHomestayView(generics.DestroyAPIView):
    queryset = Homestay.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def delete(self,request,homestay_id):
        try:
            my_profile = request.user
            homestay_controller = HomestayController()
            msg = homestay_controller.delete_homestay(homestay_id=homestay_id,current_user=my_profile)
            _status = int(msg['status'])
            response = get_response(_status=_status)
            return response
        except Exception as e:
            print(e)
            return get_response(_status=500)


class UpdateHomestayView(generics.UpdateAPIView):
    queryset = Homestay.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    def put(self, request, homestay_id):
        try:
            homestay_controller = HomestayController()
            desc = request.data.get('descriptions')
            highlight = request.data.get('highlight')
            city =  request.data.get('city')
            district =  request.data.get('district')
            name =  request.data.get('name')
            main_price =  request.data.get('main_price')
            price_detail =  request.data.get('price_detail')
            amenities =  request.data.get('amenities')
            amenities_around = request.data.get('amenities_around')
            images = request.data.get('images')
            new_homestay = Homestay(descriptions=desc,name=name,highlight=highlight,city=city,district=district,main_price=main_price,price_detail=price_detail,amenities=amenities,amenities_around=amenities_around,images=images)
            updated_homestay = homestay_controller.update_homestay(homestay_id=homestay_id,homestay=new_homestay)
            if updated_homestay is not None:
                return get_response(_status=200,data_for_ok=updated_homestay)
            return get_response(_status=204)
        except Exception as e:
            print(e)
            return get_response(_status=500)

class DeletePostView(generics.DestroyAPIView):
    queryset = Post.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def delete(self,request,post_id):
        try:
            post_controller = PostController()
            post,_status = post_controller.delete_post(post_id=post_id,current_user=request.user)
            response = get_response(_status=_status,data_for_ok=post)
            return response
        except Exception as e:
            print(e)
            return get_response(_status=500)

class GetHomestaysByAdmin(generics.RetrieveAPIView):
    queryset = Homestay.objects.filter(is_allowed=0,status=1)
    permission_classes = (permissions.IsAuthenticated,)
    def get(self,request):
        try:
            homestay_controller = HomestayController()
            limit = self.request.query_params.get('limit', 8)
            offset = self.request.query_params.get('offset', 0)
            is_allowed = self.request.query_params.get('is_allowed', 1)
            ids = self.request.query_params.get('ids', None)
            name = self.request.query_params.get('name', None)
            homestays,total,_status = homestay_controller.get_list_homestays_by_admin(current_user=request.user,limit=limit,offset=offset,is_allowed=is_allowed,ids=ids,name=name)
            return get_response(_status=_status,data_for_ok={'data': homestays,'total': total})
        except Exception as e:
            print('eeee: ',e)
            return get_response(_status=500)

class LockHomestayView(generics.UpdateAPIView):
    queryset = Homestay.objects.all()

    def put(self, request, homestay_id):
        try:
            homestay_controller = HomestayController()
            new_status,_status_http = homestay_controller.lock_homestay(homestay_id=homestay_id,current_user=request.user)
            return get_response(_status=_status_http,data_for_ok={'new_status': new_status})
        except Exception as e:
            return get_response(_status=500)

class ApproveHomestayView(generics.UpdateAPIView):
    queryset = Homestay.objects.all()
    serializer_class = HomestaySimilaritySerializer
    permission_classes = (permissions.IsAuthenticated,)

    def put(self, request, homestay_id):
        try:
            homestay_controller = HomestayController()
            status_http = homestay_controller.approve_homestay(homestay_id=homestay_id,current_user=request.user)
            return get_response(_status=status_http)
        except Exception as e:               
            print(e)
            return get_response(_status=500)

class GetDetailHomestayAdminView(GetHomestayView):
    queryset = Homestay.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

class RatePostView(generics.ListCreateAPIView):
    queryset = Post.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        try:
            post_id = request.data.get('post_id')
            post_id = request.data.get('post_id')
            action = request.data.get('action')
            post_like_ref_controller = PostLikeRefController()
            post_like_ref = post_like_ref_controller.prepare_post_like_ref(current_user=request.user,post_id=post_id)
            if post_like_ref is not None:
                type_rate,post_id = post_like_ref_controller.delete_post_like_ref(post_id=post_like_ref.post_id,user_id=post_like_ref.user_id)
                return get_response(_status=200,data_for_ok={'type_rate': 'unlike','post_id': post_id})
            else:
                type_rate,post_id = post_like_ref_controller.create_post_like_ref(post_like_ref=PostLikeRef(post_id=post_id),current_user=request.user)
                return get_response(_status=200,data_for_ok={'type_rate': 'like','post_id': post_id})
        except Exception as e:
            print(e)
            return get_response(_status=500)


















# dict_phongngu = [('toida22khach', 0), ('5phongngu', 1), ('7giuong', 2), ('toida6khach', 3), ('2phongngu', 4), ('2giuong', 5), ('toida4khach', 6), ('toida2khach', 12), ('1phongngu', 13), ('1giuong', 14), ('toida3khach', 18), ('toida12khach', 24), ('3phongngu', 25), ('3giuong', 26), ('0phongngu', 28), ('toida10khach', 39), ('4phongngu', 40), ('5giuong', 41), ('toida5khach', 42), ('toida8khach', 63), ('4giuong', 77), ('6giuong', 149), ('toida13khach', 321), ('toida7khach', 357), ('28giuong', 440), ('toida32khach', 483), ('8phongngu', 484), ('8giuong', 485), ('toida16khach', 489), ('toida9khach', 495), ('toida15khach', 510), ('toida20khach', 567), ('7phongngu', 568), ('10giuong', 569), ('toida14khach', 573), ('12giuong', 590), ('toida30khach', 630), ('9phongngu', 631), ('phongngu', 877), ('giuong', 878), ('toida19khach', 936), ('9giuong', 938), ('toida35khach', 1083), ('11giuong', 1085), ('toida25khach', 1125), ('toida24khach', 1371), ('toida1khach', 1653), ('44giuong', 2345), ('toida18khach', 2391), ('6phongngu', 2578), ('16giuong', 2762), ('toida28khach', 2955), ('10phongngu', 2956), ('13giuong', 2957), ('toida40khach', 3153), ('18giuong', 3377), ('toida26khach', 3714), ('20giuong', 4313), ('toida23khach', 4452), ('toida11khach', 4746), ('11phongngu', 4921), ('toida17khach', 4950), ('17giuong', 4952), ('toida50khach', 5391), ('toida103khach', 5775), ('19phongngu', 5776), ('38giuong', 5777), ('30giuong', 5891), ('15giuong', 6254), ('14giuong', 6383), ('24giuong', 7019), ('27giuong', 7022), ('17phongngu', 7336), ('25giuong', 7337), ('toida100khach', 7341), ('20phongngu', 7513), ('19giuong', 8591), ('toida55khach', 8997), ('14phongngu', 10222)]

# dict_phongtam = [('5phongtam', 0), ('2phongtam', 1), ('1phongtam', 2), ('3phongtam', 8), ('4phongtam', 45), ('1.5phongtam', 76), ('2.5phongtam', 131), ('8phongtam', 161), ('6phongtam', 191), ('9phongtam', 210), ('phongtam', 292), ('7phongtam', 485), ('10phongtam', 985), ('11phongtam', 1925), ('0phongtam', 2255), ('17phongtam', 2445), ('13phongtam', 2777), ('14phongtam', 3407), ('12phongtam', 3643)]

# # dict cho gia dinh
# dict_chogiadinh = [('phuhopvoitrenho', 0),
#                    ('dembosung', 1), ('khonghutthuoc', 2)]


# # dict tien ich bep
# dict_tienichbep = [('bepdien', 0), ('lovisong', 1),
#                    ('tulanh', 2), ('bepga', 3)]

# # dict hoat dong giai tri
# dict_hoatdonggiaitri = [('bbq', 0), ('canhquandep', 1), ('gansangolf', 2),
#                         ('beboi', 3), ('huongbien', 5), ('chothucung', 19), ('cauca', 97)]

# # dict tien ich phong
# dict_tienichphong = [('bancong', 0)]

# # dict tien tich chung
# dict_tienich = [('wifi', 0), ('tv', 1), ('dieuhoa', 2), ('maygiat', 3), ('daugoi,dauxa', 4), ('giayvesinh', 5), ('giayan', 6), ('nuockhoang', 7),
#                 ('khantam', 8), ('kemdanhrang', 9), ('xaphongtam', 10), ('thangmay', 72), ('staircase', 218), ('thangbo', 219), ('maysay', 922)]

# cities = ['hagiang','laocai','huubang','sonla','hoabinh','thainguyen','haiphong','quangninh','bacninh','hungyen','hanoi','vinhphuc','ninhbinh','thanhhoa','nghean','quangbinh','danang','thuathienhue','quangnam','quangngai','binhdinh','gialai','phuyen','daklak','daknong','lamdong','ninhthuan','binhthuan','khanhhoa','vungtau','bariavungtau','tiengiang','vinhlong','hochiminh','tayninh','longan','kiengiang','cantho','bangkok','chuacapnhat','thailand','maidich']

# def get_cities_similarity(city_1,city_2):
#     index=0
#     index1 = 0
#     index2 = 0
#     for city in cities:
#         if(city == city_1):
#             index1 = index
#         elif city == city_2:
#             index2 = index
#         index = index + 1
#     return  1 - (abs(index1 - index2)/len(cities))

# def get_price_similarity(price_1,price_2):
#     return  1 - (abs(price_1 - price_2)/max(price_1,price_2))

# def check_includes(arr, el):
#     index = 0
#     for ell in arr:
#         if ell[0] == el:
#             return (True, index)
#         index = index + 1
#     return (False,)


# def create_array(length):
#     final = []
#     for i in range(length):
#         final.append(0)
#     return final


# def adjust_arr(arr):
#     final = []
#     for el in arr:
#         final.append(unidecode(el).replace(' ', '').lower())
#     return final


# def similarity_by_fields(first_homestay, second_homestay):
#     index = 0
#     similarity = []
#     try:
#         for key, value in first_homestay.items():
#             if index == 0:
#                 score = get_price_similarity(value, second_homestay[key])
#                 similarity.append(score)
#             elif index == 1:
#                 score = get_cities_similarity(value, second_homestay[key])
#                 similarity.append(score)
#             elif index == 2:
#                 score = 1 if value == second_homestay[key] else 0
#                 similarity.append(score)
#             else:
#                 score = 0
#                 if all(i == 0 for i in value) or all(i == 0 for i in second_homestay[key]):
#                     score = 0
#                 else:
#                     score = 1- distance.cosine(value, second_homestay[key])
#                 similarity.append(score)
#             index = index + 1
#     except RuntimeWarning as e:
#         print('loii: ',e)
#     # dist_cos = distance.cosine(similarity, [1,1,1,1,1,1,1,1,1,1],[2,4,5,2,2,2,2,2,2,2])
#     # return 1 - distance.cosine(similarity, [1,1,1,1,1,1,1,1,1,1],[2,4,5,2,2,2,2,2,2,2])
#     return 1 - distance.cosine(similarity, [1,1,1,1,1,1,1,1,1,1],[2,4,5,2,2,2,2,2,2,2])

# queryset = Homestay.objects.filter(is_allowed=0)
# homestay_data = HomestaySerializer(queryset, many=True).data
# vectors = []
# index = 0
# for homestay in homestay_data:
#     homestay['district'] = homestay['district'] if homestay['district'] is not None else ''
#     homestay['city'] = homestay['city'] if homestay['city'] is not None else ''
#     field_names = homestay['amenities']['data']
#     main_price = 0
#     try:
#         main_price = int(homestay['main_price'])
#     except ValueError as e:
#         main_price = 0
#     vector = {
#         'gia': main_price,  # 2
#         'city': unidecode(homestay['city']).replace(' ', '').lower(),  # 3
#         # 2
#         'district': unidecode(homestay['district']).replace(' ', '').lower(),
#         'phongngu': None,
#         'phongtam': None,
#         'chogiadinh': create_array(len(dict_chogiadinh)),
#         'tienichbep': create_array(len(dict_tienichbep)),
#         'hoatdonggiaitri': create_array(len(dict_hoatdonggiaitri)),
#         'tienichphong': create_array(len(dict_tienichphong)),
#         'tienich': create_array(len(dict_tienich))
#     }
#     for field_name in field_names:
#         for key, value in field_name.items():
#             key = unidecode(key).replace(' ', '').lower()
#             value = adjust_arr(value)
#             if((key == 'phongngu')):
#                 intData = []
#                 try:
#                     max_tourist = int(value[0].replace(
#                         'toida', '').replace('khach', ''))
#                 except ValueError as e:
#                     max_tourist = 0
#                 intData.append(max_tourist)
#                 try:
#                     bedrooms = int(value[1].replace('phongngu', ''))
#                 except ValueError as e:
#                     bedrooms = 0
#                 intData.append(bedrooms)
#                 try:
#                     bed = int(value[2].replace('giuong', ''))
#                 except ValueError as e:
#                     bed = 0
#                 intData.append(bed)
#                 vector['phongngu'] = intData
#                 continue
#             if(key == 'phongtam'):
#                 phongtam = 0
#                 try:
#                     phongtam = int(value[0].replace('phongtam', ''))
#                 except ValueError as e:
#                     phongtam = 0
#                 vector['phongtam'] = [phongtam]
#                 continue
#             picked_dict = []
#             if key == 'chogiadinh':
#                 picked_dict = dict_chogiadinh
#             if key == 'tienichbep':
#                 picked_dict = dict_tienichbep
#             if key == 'hoatdonggiaitri':
#                 picked_dict = dict_hoatdonggiaitri
#             if key == 'tienichphong':
#                 picked_dict = dict_tienichphong
#             if key == 'tienich':
#                 picked_dict = dict_tienich
#             for val in value:
#                 check_dt = check_includes(picked_dict, val)
#                 if(check_dt[0] == True):
#                     vector[key][check_dt[1]] = 1
#     vectors.append((vector,homestay['homestay_id']))

#     # print(vectors)

# def convert_to_text(arr):
#     text = ''
#     for el in arr:
#         text = text + ',' + el
#     return text[1:]

# for index, vector in enumerate(vectors, start=0):
#     arr_score = []
#     print('hihi')
#     for indexx,vectorr in enumerate(vectors[index + 1:],start=0):
#         si_vector = similarity_by_fields(vector[0], vectorr[0])
#         arr_score.append("(0,"+str(vector[1])+","+str(vectorr[1])+","+str(si_vector)+")")
#     connection.cursor().execute("INSERT INTO app_homestaysimilarity (id,first_homestay_id,second_homestay_id,score) VALUES " + convert_to_text(arr_score)+';')
