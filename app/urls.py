from django.urls import path
from .views import GetHomestayView, GetHomestayWithPaginationView
from .views import SearchHomestayView, LoginView, RegisterUsers,RateHomestayView,GetCommentWithPaginationView,CreateCommentView,UpdateHomestaySimilarityView,CreateHomestaySimilarityView,GetHomestaySimilarityView,GetPostsView,GetMyHomestayRateView,CreatePostView,GetConformHomestay,UploadPhotoView,CreateHomestayView,UpdateProfileView,GetProfileView

urlpatterns = [
    path('homestays/<int:homestay_id>/',
         GetHomestayView.as_view(), name="homestays-one"),
    # path('homestays/', GetHomestayWithPaginationView.as_view(), name="homestays-pagination"),
    path('homestays', SearchHomestayView.as_view(), name="search-homestays"),
    path('auth/login', LoginView.as_view(), name="auth-login"),
    path('auth/register', RegisterUsers.as_view(), name="auth-register"),
    path('homestay/rate', RateHomestayView.as_view(), name="rate-homestay"),
    path('comments',GetCommentWithPaginationView.as_view(),name='get-comments'),
    path('comment',CreateCommentView.as_view(),name='create-comment'),
    path('homestay-similarity/update',UpdateHomestaySimilarityView.as_view(),name='update-homestay_sim'),
    path('homestay-similarity/create',CreateHomestaySimilarityView.as_view(),name='create-homestay_sim'),
    path('homestay-similarity/get',GetHomestaySimilarityView.as_view(),name='get-homestay_sim'),
    path('posts/get',GetPostsView.as_view(),name='get-posts'),
    path('homestay/get/myrate',GetMyHomestayRateView.as_view(),name='get-myrate'),
    path('post/create',CreatePostView.as_view(),name='create-post'),
    path('conform-homestays/get',GetConformHomestay.as_view(),name='get-conform-homestay'),
    path('homestay/upload-image',UploadPhotoView.as_view(),name='upload-image-homestay'),
    path('homestay/create',CreateHomestayView.as_view(),name='create-homestay'),
    path('profile/update',UpdateProfileView.as_view(),name='update-profile'),
    path('profile/get',GetProfileView.as_view(),name='get-profile')
]
