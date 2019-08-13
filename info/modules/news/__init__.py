from flask import Blueprint

# 新闻模块：访问前缀 /news
news_bp = Blueprint("news", __name__, url_prefix="/news")

# 导入views文件中的视图函数
from .views import *