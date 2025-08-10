"""Example Django URLs file with direct code (no functions or classes)."""

from django.urls import path

# Direct variable assignment
app_name = 'example'

# URL patterns configuration
urlpatterns = [
    path('admin/', 'admin.site.urls'),
    path('api/', 'api.urls'),
    path('home/', 'views.home'),
]

# Additional configuration
handler404 = 'views.page_not_found'
handler500 = 'views.server_error'