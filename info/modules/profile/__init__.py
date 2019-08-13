from flask import Blueprint

# 登录注册模块：访问前缀 /user
profile_bp = Blueprint("profile", __name__, url_prefix="/user")

# 导入views文件中的视图函数
from .views import *