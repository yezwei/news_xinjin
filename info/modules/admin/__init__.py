from flask import Blueprint, redirect, url_for

# 后台管理模块：访问前缀 /admin
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# 导入views文件中的视图函数
from .views import *


@admin_bp.before_request
def is_admin():
    """是否是管理员用户权限判断"""

    # 获取用户id
    user_id = session.get("user_id")
    # 获取is_admin
    is_admin = session.get("is_admin", False)

    # 对于/admin/login这个url是不需要拦截处理的
    if request.url.endswith("/admin/login"):
        # 管理员第一次登录是不需要拦截处理
        pass
    else:
        # 用户未登录 `或者` 不是管理员
        # is_admin == False 普通用户
        if not user_id or is_admin == False:
            # 如果不是管理员用户，需要拦截处理，引导进入新闻首页
            return redirect(url_for("index.index"))
        else:
            # 如果是管理员用户，不需要拦截处理，直接进入views文件执行对应视图函数
            # 不拦截
            pass