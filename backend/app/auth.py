import jwt
from datetime import datetime, timedelta
from django.http import JsonResponse
from functools import wraps
from .models import User

SECRET_KEY = "Kamil is cool"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24


def create_access_token(user_id: int, username: str, role: str):
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"user_id": user_id, "username": username, "role": role, "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_current_user(request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split(" ")[1]
    payload = decode_token(token)
    if not payload:
        return None

    try:
        user = User.objects.get(id=payload["user_id"])
        return user
    except User.DoesNotExist:
        return None


def login_required(f):
    @wraps(f)
    def decorated_function(request, *args, **kwargs):
        user = get_current_user(request)
        if not user:
            return JsonResponse({"error": "Требуется авторизация"}, status=401)
        request.user = user
        return f(request, *args, **kwargs)

    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(request, *args, **kwargs):
        user = get_current_user(request)
        if not user:
            return JsonResponse({"error": "Требуется авторизация"}, status=401)
        if user.role != "admin":
            return JsonResponse({"error": "Требуются права администратора"}, status=403)
        request.user = user
        return f(request, *args, **kwargs)

    return decorated_function
