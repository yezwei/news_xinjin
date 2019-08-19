from flask import current_app, render_template
from info.modules.index import index_bp
from info import redis_store
# 注意：需要在别的文件中导入models中的类，让项目和models有关联
from info.models import User


# 2.使用蓝图对象装饰视图函数
# 127.0.0.1:5000/ --> 项目首页
@index_bp.route('/')
def index():
    # 往redis数据库存储键值对
    redis_store.set("name", "curry")
    # Flask中记录日志的方式[使用]
    current_app.logger.debug("Flask 记录debug log")
    return render_template("news/index.html")


# 这个视图函数是浏览器自己调用的方法，返回网站图标
@index_bp.route('/favicon.ico')
def get_faviconico():
    """返回网站的图标"""
    """
    Function used internally to send static files from the static
        folder to the browser
    内部用来发送静态文件到浏览器的方法： send_static_file
    """
    return current_app.send_static_file("news/favicon.ico")