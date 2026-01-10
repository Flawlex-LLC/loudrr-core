from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404

from posts.models import Post
from core.services.engagements import record_engagement


def redirect_view(request, token):
    """
    Handle redirect links for engagement tracking.

    URL format: /r/{token}/?u={encrypted_user_id}

    1. Look up post by token
    2. Decrypt user ID from query param
    3. Validate and record engagement
    4. Redirect to original X link
    """
    post = get_object_or_404(Post, redirect_token=token, status="active")

    encrypted_user_id = request.GET.get("u")
    if encrypted_user_id:
        # Record engagement (async-safe)
        record_engagement(encrypted_user_id, post)

    return HttpResponseRedirect(post.x_link)
