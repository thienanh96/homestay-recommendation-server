from django.urls import path
from .views import GetHomestayView, GetHomestayWithPaginationView
from .views import SearchHomestayView, LoginView, RegisterUsers,RateHomestayView,GetCommentWithPaginationView,CreateCommentView,UpdateHomestaySimilarityView,CreateHomestaySimilarityView,GetHomestaySimilarityView,GetPostsView,GetMyHomestayRateView,CreatePostView,GetConformHomestay,UploadPhotoView,CreateHomestayView,UpdateProfileView,GetProfileView,UpdateHomestayView,DeletePostView,GetListProfileView,DeleteProfileView,GetHomestaysByAdmin,ApproveHomestayView,GetDetailHomestayAdminView,RatePostView,DeleteHomestayView,DeleteHomestaySimilarityView,LockHomestayView

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
    path('homestay-similarity/delete/<int:homestay_id>',DeleteHomestaySimilarityView.as_view(),name='delete-homestay_sim'),
    path('homestay-similarity/get',GetHomestaySimilarityView.as_view(),name='get-homestay_sim'),
    path('posts/get',GetPostsView.as_view(),name='get-posts'),
    path('homestay/get/myrate',GetMyHomestayRateView.as_view(),name='get-myrate'),
    path('post/create',CreatePostView.as_view(),name='create-post'),
    path('conform-homestays/get',GetConformHomestay.as_view(),name='get-conform-homestay'),
    path('homestay/upload-image',UploadPhotoView.as_view(),name='upload-image-homestay'),
    path('homestay/create',CreateHomestayView.as_view(),name='create-homestay'),
    path('profile/update',UpdateProfileView.as_view(),name='update-profile'),
    path('profile/get',GetProfileView.as_view(),name='get-profile'),
    path('homestay/update/<int:homestay_id>',UpdateHomestayView.as_view(),name='update-homestay'),
    path('post/delete/<int:post_id>',DeletePostView.as_view(),name='delete-post'),
    path('profile/getlist',GetListProfileView.as_view(),name='get-list-profile'),
    path('profile/delete/<int:profile_id>',DeleteProfileView.as_view(),name='delete-profile'),
    path('admin/homestays/get',GetHomestaysByAdmin.as_view(),name='admin-get-homestays-notallowed'),
    path('admin/homestay/approve/<int:homestay_id>',ApproveHomestayView.as_view(),name='admin-approve-homestays'),
    path('admin/homestay/lock/<int:homestay_id>',LockHomestayView.as_view(),name='admin-lock-homestays'),
    path('admin/homestay/get/<int:homestay_id>',GetDetailHomestayAdminView.as_view(),name='admin-get-homestay'),
    path('admin/homestay/delete/<int:homestay_id>',DeleteHomestayView.as_view(),name='delete-homestay'),
    path('post/rate',RatePostView.as_view(),name='rate-post')
]
