from flask import Blueprint

# 登录注册模块：访问前缀 /passport
passport_bp = Blueprint("passport", __name__, url_prefix="/passport")

# 导入views文件中的视图函数
from .views import *