

"""
# 过滤器本质是函数
自定义过滤器步骤：
1.自定义一个python的函数去实现对应业务逻辑
2.通过app对象将函数添加到系统过滤器中
3.使用自定义过滤器

"""


# 1.自定义一个python的函数去实现对应业务逻辑
from flask import session, current_app, jsonify, g


from info.response_code import RET


def do_ranklist_class(index):

    if index == 0:
        return "first"
    elif index == 1:
        return "second"
    elif index == 2:
        return "third"
    else:
        return ""


import functools

# 需求：查询当前登录用户对象的代码在多个视图函数中都需要使用，我们可以使用装饰器将其封装
# view_func： 被装饰的函数名称
# 问题： 装饰器会改变被装饰的视图函数名称
# 方案：@functools.wraps(视图函数名称)


def get_user_info(view_func):

    @functools.wraps(view_func)
    def wrapper(*args, **kwargs):

        # 1.装饰视图函数新增的需求
        # 1.获取session中的用户id
        user_id = session.get("user_id")

        # 延迟导入解决db循环导入的问题
        from info.models import User

        # 2.根据user_id查询当前用户对象
        user = None  # type: User
        if user_id:
            try:
                user = User.query.get(user_id)
            except Exception as e:
                current_app.logger.error(e)
                return jsonify(errno=RET.DBERR, errmsg="查询用户对象异常")

        # 3.将用户对象保存起来提供给视图函数使用
        # 全局的临时变量保存用户对象，只要请求未结束，g变量中的值就不会改变
        g.user = user

        # 2.被装饰的视图函数原有功能实现
        result = view_func(*args, **kwargs)
        return result

    return wrapper















