# project_name/urls.py

from django.contrib import admin
from django.urls import path, include 

urlpatterns = [
    # Admin panelga kirish (To'g'ri manzil: http://127.0.0.1:8000/admin/)
    path('admin/', admin.site.urls), 
    
    # Boshqa barcha URL'larimizni 'vocabulary' ilovasiga yo'naltiramiz
    path('', include('vocabulary.urls')), 
]

###########################################################


###########################################################

# project_name/urls.py

from django.contrib import admin
from django.urls import path, include # 'include' ni import qilish shart

urlpatterns = [
    # 1. Admin panel
    path('admin/', admin.site.urls),
    
    # 2. Avtorizatsiya (Login, Logout) uchun barcha URL larni ulaymiz
    path('accounts/', include('django.contrib.auth.urls')), # <-- BU QATORNI QO'SHING
    
    # 3. Bizning ilova (Dashboard)
    path('', include('vocabulary.urls')), 
]

###########################################################
