import ast
from django.shortcuts import render
from rest_framework import generics
from rest_framework import permissions, authentication, pagination
from rest_framework.response import Response
from rest_framework.views import status
from rest_framework_jwt.settings import api_settings
from .serializers import ProfileSerializer, HomestayRateSerializer, HomestaySerializer, TokenSerializer, UserSerializer, CommentSerializer, HomestaySimilaritySerializer,PostSerializer,PostLikeRefSerializer
from .models import Homestay, Profile, HomestayRate, Comment, HomestaySimilarity,PostLikeRef,Post
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
from .recommendation import get_predictions
from .validation import Validation
import time;
from .utils import embed_to_vector, get_score, convert_to_text
import textdistance

# Get the JWT settings
jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER

#Config Cloundinary
cloudinary.config( 
  cloud_name = "homestayhub", 
  api_key = "324217692173642", 
  api_secret = "fYCSwPmuwwhAMZDcE0ZYZREomKM" 
)
# labels = keras_text_classifier.classify('hihi')
# print(labels)

class GetHomestayView(generics.RetrieveAPIView):
    queryset = Homestay.objects.filter(is_allowed=1)
    serializer_class = HomestaySerializer
    # authentication_classes = (authentication.BasicAuthentication,)

    def get_profile_host(self, host_id):
        try:
            queryset_profile = Profile.objects.all()
            current_profile = queryset_profile.get(id=int(host_id))
            return current_profile
        except Profile.DoesNotExist:
            return None

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
    def authorize_user(self,type_get):
        user = self.request.user
        if type_get == 'admin':
            if user is None:
                return False
            if user.email != 'supportcustomer1554737792398@gmail.com':
                return False
            return True
        else:
            return True


    def get(self, request, homestay_id):
        type_get = self.request.query_params.get('type-get', None)
        authorize = self.authorize_user(type_get)
        if authorize == False:
            return Response(data={},status=status.HTTP_401_UNAUTHORIZED)
        queryset = self.get_queryset()
        homestay_obj = queryset.get(homestay_id=homestay_id)
        serializer_class = self.get_serializer_class()
        homestay = serializer_class(homestay_obj).data
        host_id = homestay['host_id']
        host_profile = self.get_profile_host(host_id=host_id)
        homestay_rate = self.get_homestay_rate(request.user.id, homestay_id)
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

        return Response(homestay_with_hostinfo, 200)


class GetHomestayWithPaginationView(generics.RetrieveAPIView):
    queryset = Homestay.objects.filter(is_allowed=1)
    authentication_classes = (authentication.BasicAuthentication,)

    def get_homestay_queryset(self, limit, offset):
        return Homestay.objects.filter(is_allowed=1).order_by('created_at')[offset:offset+limit]

    def get_profile_queryset(self, limit=0, offset=0):
        return Profile.objects.all()[limit:limit+offset]

    def get_profile_host(self, host_id):
        try:
            queryset_profile = Profile.objects.all()
            current_profile = queryset_profile.get(id=int(host_id))
            return current_profile
        except Profile.DoesNotExist:
            return None

    def get(self, request):
        try:
            limit = self.request.query_params.get('limit', None)
            offset = self.request.query_params.get('offset', None)
            queryset_homestays = self.get_homestay_queryset(
                limit=int(limit), offset=int(offset))
            homestay_serializer = HomestaySerializer(
                queryset_homestays, many=True)
            homestays_data = homestay_serializer.data
            responses = []
            for homestay in homestays_data:
                host_id = homestay['host_id']
                host_profile = self.get_profile_host(host_id=host_id)
                homestay_with_hostinfo = {
                    'homestay_info': homestay,
                    'host_info': None
                }
                if not (host_profile is None):
                    host_profile = ProfileSerializer(host_profile).data
                    homestay_with_hostinfo['host_info'] = host_profile
                responses.append(homestay_with_hostinfo)
            return Response({'status': 200, 'data': responses}, 200)
        except Exception as e:
            return Response({'status': 500, 'message': e}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SearchHomestayView(generics.ListCreateAPIView):
    queryset = Homestay.objects.filter(is_allowed=1)
    serializer_class = HomestaySerializer
    authentication_classes = (authentication.BasicAuthentication,)

    def search_homestay(self, query, order_by):
        if order_by == 'main_price_desc':
            return Homestay.objects.filter(query).order_by('-main_price')
        elif order_by == 'main_price_asc':
            return Homestay.objects.filter(query).order_by('main_price')
        elif order_by == 'likes':
            return Homestay.objects.filter(query).order_by('-likes')
        return Homestay.objects.filter(query).order_by('-created_at')

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
            main_query = Q()
            main_query.add(Q(is_allowed=1),Q.AND)
            if(name is not None):
                main_query.add(Q(name__icontains=name), Q.AND)
            elif(ids is not None):
                ids = ids.split(',')
                for ind in ids:
                    main_query.add(Q(homestay_id=ind), Q.AND)
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
            queryset = self.search_homestay(main_query, order_by)
            response_data = None
            total = HomestaySerializer(queryset, many=True).data
            if(limit is not None and offset is not None):
                response_data = total[int(offset):int(offset) + int(limit)]
            else:
                response_data = total[0:9]
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
            username = request.data.get("username", "")
            password = request.data.get("password", "")
            gender = request.data.get("gender", "")
            birthday = request.data.get("birthday", "")
            address = request.data.get("address", "")
            email = request.data.get("email", "")
            rep_id = request.data.get('repId',"")
            avatar= request.data.get('avatar',"")
            join_date = request.data.get('joinDate','')
            id = request.data.get('id',"")
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
            new_profile = Profile(user_name=username,email=email,represent_id=rep_id,id=id,avatar = avatar,join_date=join_date)
            new_profile.save()
            return Response(
                data=UserSerializer(new_user).data,
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            print('Loi', e)
            return Response({'status': 500, 'message': 'Something went wrong'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RateHomestayView(generics.CreateAPIView):
    queryset = HomestayRate.objects.all()
    serializer_class = HomestayRateSerializer
    permission_classes = (permissions.IsAuthenticated,)
    # authentication_classes = (authentication.,)

    def post(self, request, *args, **kwargs):
        try:
            homestay_id = request.data.get("homestay_id", "")
            type_rate = request.data.get("type_rate", "")
            cursor = connection.cursor()
            print('called: ', type_rate)
            try:
                cursor.callproc('rate_homestay', [
                                int(request.user.id), int(homestay_id), int(type_rate)])
                action_type = None
                if cursor.fetchall()[0][0] is not None:
                    action_type = 'remove'
                else:
                    action_type = 'add'
                print('acyion: ',action_type)
                return Response(
                    data={'type_rate': type_rate, 'homestay_id': homestay_id,
                          'user_id': request.user.id, 'status': 200, 'action_type': action_type},
                    status=status.HTTP_200_OK
                )
            except Exception as e:
                print('loi', e)
                return Response({'status': 500, 'message': e}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({'status': 500, 'message': e}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetMyHomestayRateView(generics.RetrieveAPIView):
    queryset = HomestayRate.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

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

    def get(self, request, *args, **kwargs):
        try:
            if request.user is None:
                return Response(data={}, status=status.HTTP_401_UNAUTHORIZED)
            homestay_id = self.request.query_params.get('homestay_id', None)
            me_rate = None
            if(homestay_id is not None):
                homestay_rate = self.get_homestay_rate(request.user.id, homestay_id)
                if not(homestay_rate is None):
                    homestay_rate_data = HomestayRateSerializer(homestay_rate).data
                    if homestay_rate_data['isType'] == 1:
                        me_rate = 'like'
                    if homestay_rate_data['isType'] == 2:
                        me_rate = 'dislike'
                return Response(data={'me_rate': me_rate},status=status.HTTP_200_OK)
            else:
                return Response({}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({'status': 500, 'message': e}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetCommentWithPaginationView(generics.RetrieveAPIView):
    queryset = Comment.objects.all()
    authentication_classes = (authentication.BasicAuthentication,)

    def get_comments(self, homestay_id, offset, limit):
        try:
            if (limit is None) or (offset is None):
                return Comment.get_comments_with_userinfo(homestay_id, 9, 0)
            else:
                return Comment.get_comments_with_userinfo(homestay_id, limit, offset)
        except Comment.DoesNotExist:
            return None

    def get(self, request, *args, **kwargs):
        try:
            homestay_id = self.request.query_params.get('homestay_id', None)
            limit = self.request.query_params.get('limit', None)
            offset = self.request.query_params.get('offset', None)
            comments = self.get_comments(homestay_id, offset, limit)
            if not(comments is None):
                comments_data = CommentSerializer(comments, many=True).data
                return Response(data=comments_data, status=status.HTTP_200_OK)
            else:
                return Response(data=[], status=status.HTTP_200_OK)
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
            content = request.data.get("content", None)
            user_id = request.user.id
            text = [content]
            final_label = 0
            print('__________________: ',text)
            with graph.as_default():
                final_label = classify_comment(text)
                print('final: ',final_label)
            new_comment = Comment(homestay_id=homestay_id,user_id=user_id, content=content,sentiment=final_label)
            new_comment.save()
            new_comment_raw = CommentSerializer(new_comment).data
            return Response(data=new_comment_raw, status=status.HTTP_200_OK)
        except Exception as e:
            print('loi', e)
            return Response({'message': 'loi roi'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetHomestaySimilarityView(generics.ListCreateAPIView):
    queryset = HomestaySimilarity.objects.all()
    serializer_class = HomestaySimilaritySerializer
    # authentication_classes = (authentication.BasicAuthentication,)

    def get_id(self,homestay_sim,current_homestay_id):
        first = str(homestay_sim['first_homestay_id'])
        second = str(homestay_sim['second_homestay_id'])
        if (current_homestay_id == first):
            return second
        else:
            return first

    def get_list_homestay_with_ids(self,ids):
        ordering = 'FIELD(`homestay_id`, %s)' % ','.join(str(idd) for idd in ids)
        homestays = Homestay.objects.filter(homestay_id__in=ids).extra(select={'ordering': ordering}, order_by=('ordering',))
        homestays = HomestaySerializer(homestays,many=True).data
        return homestays

    def get(self, request):
        try:
            f1 = time.time()
            limit = self.request.query_params.get('limit', None)
            offset = self.request.query_params.get('offset', None)
            homestay_id = self.request.query_params.get('homestay_id', None)
            homestay_sims = HomestaySimilarity.objects.filter(
                Q(first_homestay_id=homestay_id) | Q(second_homestay_id=homestay_id)).order_by('-score')
            f2 = time.time()
            print('first: ',f2-f1)
            homestay_sims = HomestaySimilaritySerializer(homestay_sims,many=True).data
            f3 = time.time() 
            print('third: ',f3 - f2)
            # homestays = map(lambda homestay_sim: (homestay_sim['second_homestay_id'],homestay_sim['score']) if str(homestay_sim['first_homestay_id']) == homestay_id else (homestay_sim['first_homestay_id'],homestay_sim['score']),homestay_sims)
            f4 = time.time()
            print('fourth: ',f4 - f3)
            homestays = []
            if((limit is not None) and (offset is not None)):
                homestays = homestay_sims[int(limit):int(limit) + int(offset)]
            else:
                homestays = homestay_sims[0:8]
            ids = list(map(lambda x : (x['first_homestay_id'] if x['first_homestay_id'] != int(homestay_id) else x['second_homestay_id']),homestays))
            ids = list(map(lambda x: int(x),ids))
            homestays = self.get_list_homestay_with_ids(ids)
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
            current_homestay = Homestay.objects.get(homestay_id=homestay_id)
            other_homestays = Homestay.objects.filter(
                ~Q(homestay_id=homestay_id))
            other_homestays = HomestaySerializer(
                other_homestays, many=True).data
            current_homestay = HomestaySerializer(current_homestay).data
            arr_score = []
            for other_homestay in other_homestays:
                vector_1 = embed_to_vector(current_homestay)
                vector_2 = embed_to_vector(other_homestay)
                score = get_score(vector_1, vector_2)
                arr_score.append(score)
            connection.cursor().execute("DELETE FROM app_homestaysimilarity WHERE first_homestay_id=" +
                                        str(current_homestay['homestay_id']) + " OR second_homestay_id=" + str(current_homestay['homestay_id']))
            print('_____________________________________________________________________')
            connection.cursor().execute("INSERT INTO app_homestaysimilarity (first_homestay_id,second_homestay_id,score) VALUES " +
                                        convert_to_text(arr_score)+';')
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
            current_homestay = Homestay.objects.get(homestay_id=homestay_id)
            other_homestays = Homestay.objects.filter(
                ~Q(homestay_id=homestay_id))
            other_homestays = HomestaySerializer(
                other_homestays, many=True).data
            current_homestay = HomestaySerializer(current_homestay).data
            arr_score = []
            for other_homestay in other_homestays:
                vector_1 = embed_to_vector(current_homestay)
                vector_2 = embed_to_vector(other_homestay)
                score = get_score(vector_1, vector_2)
                arr_score.append(score)
            connection.cursor().execute("INSERT INTO app_homestaysimilarity (first_homestay_id,second_homestay_id,score) VALUES " +convert_to_text(arr_score)+';')
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
            posts = self.queryset
            if filter_get == 'newest':
                posts = self.queryset.order_by('-created_at')
            elif filter_get == 'like':
                posts = self.queryset.order_by('-count_like')
            elif (filter_get == 'by-me') and (request.user.id is not None):
                posts = Post.objects.filter(user_id=request.user.id)
            else:
                print('postsssss: ',filter_get)
                posts = Post.objects.filter(user_id=int(filter_get))
                print('postQQ: ',posts)
            posts_without_slice = posts
            if((limit is not None) and (offset is not None)):
                posts = posts[int(offset):int(limit) + int(offset)]
            else:
                posts = posts[0:3]
            return Response(data={'data': PostSerializer(posts,many=True).data,'total': len(posts_without_slice)},status=status.HTTP_200_OK)            
        except Exception as e:
            print(e)
            return Response({'msg': 'fail'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CreatePostView(generics.ListCreateAPIView):
    queryset = Post.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    
    def post(self, request, *args, **kwargs):
        try:
            homestay_id = request.data.get("homestay_id", None)
            content = request.data.get('content','')     
            if(homestay_id is None):
                return Response({'msg': 'fail'}, status=status.HTTP_400_BAD_REQUEST)
            user_id = request.user.id
            new_post = Post(homestay_id=homestay_id,user_id=user_id, content=content)
            new_post.save()
            return Response(data=PostSerializer(new_post).data, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response({'msg': 'fail'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetConformHomestay(generics.RetrieveAPIView):
    queryset = Homestay.objects.filter(is_allowed=True)
    homestay_count = Homestay.objects.count()
    permission_classes = (permissions.IsAuthenticated,)

    def get_list_represent_id(self):
        homestays = HomestaySerializer(self.get_queryset(),many=True).data
        ids = map(lambda x : x['represent_id'],homestays)
        return list(ids)

    def get_list_homestay_with_ids(self,ids):
        ordering = 'FIELD(`represent_id`, %s)' % ','.join(str(idd) for idd in ids)
        homestays = Homestay.objects.filter(represent_id__in=ids).extra(select={'ordering': ordering}, order_by=('ordering',))
        homestays = HomestaySerializer(homestays,many=True).data
        return homestays


    def get(self, request, *args, **kwargs):
        try:
            my_user_email = request.user.email
            my_profile= Profile.objects.get(email=my_user_email)

            limit = self.request.query_params.get('limit', None)
            offset = self.request.query_params.get('offset', None)
            represent_list = self.get_list_represent_id()
            my_represent_id = ProfileSerializer(my_profile).data['represent_id']
            print(my_represent_id)
            predictions = get_predictions(my_represent_id,represent_list)
            predictions = sorted(predictions,key=lambda x: x[1],reverse=True)
            print(predictions)
            if((limit is not None) and (offset is not None)):
                predictions = predictions[int(offset):int(limit) + int(offset)]
            else:
                predictions = predictions[0:10]
            ids = map(lambda x : x[0],predictions)
            homestays = self.get_list_homestay_with_ids(list(ids))
            return Response(data=homestays, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response(data={}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UploadPhotoView(generics.ListCreateAPIView):
    queryset = Homestay.objects.filter(is_allowed=True)
    # permission_classes = (permissions.NOT,)
    def post(self, request, *args, **kwargs):
        try:
            response = upload(request.FILES['img'])
            cropped_width = 0
            cropped_height = 0
            width_image = int(response['width'])
            height_image = int(response['height'])
            if width_image/height_image >= 1.5:
                cropped_height = height_image
                cropped_width = cropped_height * 1.5
            else:
                cropped_width = width_image
                cropped_height = cropped_width / 1.5
                
            url, options = cloudinary_url(
                response['public_id'],
                format=response['format'],
                width=int(cropped_width),
                height=int(cropped_height),
                crop="crop"
            )
            return Response(data={'url':url}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(data={}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CreateHomestayView(generics.ListCreateAPIView):
    queryset = Homestay.objects.latest()
    permission_classes = (permissions.IsAuthenticated,)

    def get_next_rep_id(self):
        last = self.get_queryset()
        try:
            if last is not None:
                return int(HomestaySerializer(last).data['represent_id'] + 1)
            else:
                return  0
        except Exception as e:
            return 0

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
            represent_id = self.get_next_rep_id()
            new_homestay = Homestay(represent_id=represent_id,main_price=main_price,price_detail=detail_price,amenities=amenities,amenities_around=amenities_around,name=name,descriptions=desc,highlight=highlight,images=images,city=city,district=district,host_id=request.user.id)
            new_homestay.save()
            return Response(data=HomestaySerializer(new_homestay).data, status=status.HTTP_200_OK)
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
            me_queryset = Profile.objects.filter(id=request.user.id)
            me_auth = User.objects.get(id=request.user.id)
            if me_auth is not None and password is not None:
                me_auth.set_password(password)
                me_auth.save()
            me = ProfileSerializer(me_queryset,many=True).data[0]
            address = address if address is not None else me['address']
            phone = str(prefix + phone) if phone is not None else me['phone']
            username = username if username is not None else me['user_name']
            if(me is not None):
                update_result = me_queryset.update(address=address,phone=phone,user_name=username)
                return Response(data=update_result, status=status.HTTP_200_OK)
            else:
                return Response(data={}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(data={}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetProfileView(generics.ListCreateAPIView):
    queryset = Profile.objects.all()
    # permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        try:
            me = self.request.query_params.get('me', None)
            user_id = self.request.query_params.get('user_id', None)
            print(me,user_id)
            if me is not None:
                user_id = request.user.id
                print(user_id)
            my_profile = Profile.objects.get(id=int(user_id))
            if my_profile is not None:
                return Response(data=ProfileSerializer(my_profile).data, status=status.HTTP_200_OK)
            else:
                return Response(data={}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(e)
            return Response(data={}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetListProfileView(generics.ListCreateAPIView):
    queryset = Profile.objects.all()
    count = Profile.objects.count()
    # permission_classes = (permissions.IsAuthenticated,)

    def get_list_profile_queryset(self, limit, offset):
        return self.get_queryset().order_by('created_at')[int(offset):int(offset)+int(limit)]

    def get(self, request, *args, **kwargs):
        try:
            limit = self.request.query_params.get('limit', 8)
            offset = self.request.query_params.get('offset', 0)
            list_profiles = self.get_list_profile_queryset(limit,offset)
            return Response(data={'dt': ProfileSerializer(list_profiles,many=True).data, 'total': self.count}, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response(data={}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DeleteProfileView(generics.DestroyAPIView):
    queryset = Profile.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def delete(self,request,profile_id):
        try:
            my_profile = request.user
            if(my_profile is not None):
                my_email = my_profile.email
                if my_email == 'supportcustomer1554737792398@gmail.com':
                    profile = Profile.objects.get(id=profile_id)
                    if(profile):
                        profile.delete()
                    auth_profile = User.objects.get(id=profile_id)
                    if(auth_profile):
                        auth_profile.delete()
                    return Response(data={},status=status.HTTP_200_OK)
                else:
                    return Response(data={},status=status.HTTP_401_UNAUTHORIZED)
            else:
                return Response(data={},status=status.HTTP_401_UNAUTHORIZED)
        except expression as identifier:
            return Response(data={}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UpdateHomestayView(generics.UpdateAPIView):
    queryset = Homestay.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    def put(self, request, homestay_id):
        try:
            # data = Validation().validate_post(request.data)
            # print(data.items())
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
            homestay = Homestay.objects.get(homestay_id=homestay_id)
            if(homestay):
                homestay.name = name if name is not None else homestay.name
                homestay.descriptions = desc if desc is not None else homestay.descriptions
                homestay.highlight = highlight if highlight is not None else homestay.highlight
                homestay.city = city if city is not None else homestay.city
                homestay.district = district if district is not None else homestay.district
                homestay.main_price = main_price if main_price is not None else homestay.main_price
                homestay.price_detail = price_detail if price_detail is not None else homestay.price_detail
                homestay.amenities = amenities if amenities is not None else homestay.amenities
                homestay.amenities_around = amenities_around if amenities_around is not None else homestay.amenities_around
                homestay.images = images if images is not None else homestay.images
                update_result = homestay.save()
                return Response(data=HomestaySerializer(homestay).data, status=status.HTTP_200_OK)
            else:
                return Response(data={},status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            print(e)
            return Response(data={}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DeletePostView(generics.DestroyAPIView):
    queryset = Post.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def delete(self,request,post_id):
        try:
            my_id = request.user.id
            post = Post.objects.get(post_id=post_id)
            if post.user_id != int(my_id):
                return Response(data={},status=status.HTTP_401_UNAUTHORIZED)  
            post.delete()
            return Response(data=PostSerializer(post).data, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response(data={}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetNotAllowedHomestays(generics.RetrieveAPIView):
    queryset = Homestay.objects.filter(is_allowed=0)
    permission_classes = (permissions.IsAuthenticated,)
    def get(self,request):
        try:
            my_email = request.user.email
            if(my_email != 'supportcustomer1554737792398@gmail.com'):
                return Response(data={},status=status.HTTP_401_UNAUTHORIZED)
            homestays = self.get_queryset()
            homestays = HomestaySerializer(homestays,many=True).data
            return Response(data={'data': homestays,'total': len(homestays)},status=status.HTTP_200_OK)
        except expression as e:
            return Response(data={}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ApproveHomestayView(generics.UpdateAPIView):
    queryset = Homestay.objects.all()
    serializer_class = HomestaySimilaritySerializer
    permission_classes = (permissions.IsAuthenticated,)

    def put(self, request, homestay_id):
        try:
            my_email = request.user.email
            if(my_email != 'supportcustomer1554737792398@gmail.com'):
                return Response(data={},status=status.HTTP_401_UNAUTHORIZED)
            homestay = Homestay.objects.get(homestay_id=homestay_id)
            if homestay is not None:
                homestay.is_allowed = 1
                homestay.save()
                return Response(data={}, status=status.HTTP_200_OK)
            else:
                return Response(data={}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            print(e)
            return Response({'msg': 'fail'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetDetailHomestayAdminView(GetHomestayView):
    queryset = Homestay.objects.all()
    permission_classes = (permissions.IsAuthenticated,)


















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
