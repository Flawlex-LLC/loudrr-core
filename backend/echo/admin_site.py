"""
Custom Loudrr Admin Site.

Provides a separate admin interface at /loudrr-admin/ with:
- Custom branding
- Stricter permission checks
- All registered models in one place
"""
from django.contrib.admin import AdminSite


class LoudrrAdminSite(AdminSite):
    """
    Custom admin site for Loudrr.

    Accessible at /loudrr-admin/ with custom branding.
    """
    site_header = 'Loudrr Admin'
    site_title = 'Loudrr Admin Portal'
    index_title = 'Dashboard'

    def has_permission(self, request):
        """
        Only allow staff users to access the admin.

        Checks:
        - User is authenticated
        - User is active
        - User has is_staff=True
        """
        return (
            request.user.is_active and
            request.user.is_authenticated and
            request.user.is_staff
        )


# Create the custom admin site instance
loudrr_admin = LoudrrAdminSite(name='loudrr_admin')
