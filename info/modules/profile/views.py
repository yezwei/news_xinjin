from info import db
from info.response_code import RET
from . import profile_bp
from flask import render_template, g, request, jsonify, session, current_app
from info.utils.common import get_user_info
from info.utils.pic_store import pic_store
from info import constants
from info.models import Category, News


@profile_bp.route('/user_follow')
@get_user_info
def user_follow():
    # 获取页数
    p = request.args.get("p", 1)
    try:
        p = int(p)
    except Exception as e:
        current_app.logger.error(e)
        p = 1

    user = g.user

    follows = []
    current_page = 1
    total_page = 1
    try:
        # user.followed : 当前登录用户的关注列表的查询对象
        paginate = user.followed.paginate(p, constants.USER_FOLLOWED_MAX_COUNT, False)
        # 获取当前页数据
        follows = paginate.items
        # 获取当前页
        current_page = paginate.page
        # 获取总页数
        total_page = paginate.pages
    except Exception as e:
        current_app.logger.error(e)

    user_dict_li = []

    for follow_user in follows:
        user_dict_li.append(follow_user.to_dict())
    data = {"users": user_dict_li, "total_page": total_page, "current_page": current_page}


    return render_template('user/user_follow.html', data=data)


# 127.0.0.1:5000/user/news_list?p=页码
@profile_bp.route('/news_list', methods=["GET"])
@get_user_info
def news_list():
    """`查询` 当前用户发布的新闻列表数据"""
    """
    1.获取参数
        1.1 p:当前页码， user:当前登录用户
    2.校验参数
        2.1 非空判断
    3.逻辑处理
        3.0 News.query.filter(查询条件).order_by(新闻时间排序).paginate(当前页码，每页数量，False)
            查询条件：News.user_id = user.id 表示是当前用户发布的新闻
        3.1 将对象列表转字典列表
    4.返回值
    """

    # 1.1 p:当前页码， user:当前登录用户
    p = request.args.get('p', 1)
    user = g.user

    # 2.1 非空判断
    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")

    try:
        p = int(p)
    except Exception as e:
        current_app.logger.error(e)
        p = 1

    news_list = []
    current_page = 1
    total_page = 1
    #  3.0 News.query.filter(查询条件).order_by(新闻时间排序).paginate(当前页码，每页数量，False)
    #  查询条件：News.user_id = user.id 表示是当前用户发布的新闻
    try:
        paginate = News.query.filter(News.user_id == user.id).order_by(News.create_time.desc())\
         .paginate(p, constants.USER_NEWS_PAGE_MAX_COUNT, False)
        news_list = paginate.items
        current_page = paginate.page
        total_page = paginate.pages
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询新闻列表数据异常")

    #  3.1 将对象列表转字典列表
    news_dict_list = []
    for news in news_list if news_list else []:
        news_dict_list.append(news.to_review_dict())

    data = {
        "news_list": news_list,
        "current_page": current_page,
        "total_page": total_page
    }

    return render_template("user/user_news_list.html", data=data)


# 127.0.0.1:5000/user/news_release ---> 发布新闻
@profile_bp.route('/news_release', methods=["GET", "POST"])
@get_user_info
def news_release():
    """发布新闻接口"""

    # GET请求：查询新闻分类数据，展示发布新闻的模板
    if request.method == "GET":
        # 1.查询新闻分类数据
        try:
            categories = Category.query.all()
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="查询用户对象异常")
        # 2.对象列表转字典列表
        category_dict_list = []
        for category in categories if categories else []:
            category_dict_list.append(category.to_dict())

        # 3.移除`最新`分类
        category_dict_list.pop(0)

        data = {
            "categories": category_dict_list
        }
        return render_template("user/user_news_release.html", data=data)

    # POST请求：发布新闻

    """
    1.获取参数
        1.1 title: 新闻标题，category_id: 分类id， digest：新闻摘要
            index_image:新闻主图片，content:新闻内容， user：当前登录用户  source:个人发布
    2.校验参数
        2.1 非空判断
        2.2 category_id强制数据类型转换
    3.逻辑处理
        3.0 创建新闻对象，并给各个属性赋值
        3.1 保存回数据库
    4.返回值
        发布新闻成功
    """

    # 1.1 title: 新闻标题，category_id: 分类id， digest：新闻摘要
    #     index_image:新闻主图片，content:新闻内容， user：当前登录用户  source:个人发布
    title = request.form.get("title")
    category_id = request.form.get("cid")
    digest = request.form.get("digest")
    content = request.form.get("content")
    # 新闻主图片
    index_image = request.files.get("index_image")
    user = g.user
    source = "个人发布"

    # 2.1 非空判断
    if not all([title, category_id, digest, index_image, content]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")
    # 2.2 category_id强制数据类型转换
    try:
        category_id = int(category_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR, errmsg="参数类型错误")

    try:
        image_data = index_image.read()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DATAERR, errmsg="读取图片数据异常")

    if not image_data:
        return jsonify(errno=RET.NODATA, errmsg="图片数据不能为空")

    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")

    # 3.0 将主图片上传到七牛云平台
    try:
        image_name = pic_store(image_data)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR, errmsg="上传到七牛云异常")

    # 3.1 创建新闻对象，并给各个属性赋值
    news = News()
    # 新闻标题
    news.title = title
    # 新闻分类id
    news.category_id = category_id
    # 新闻摘要
    news.digest = digest
    # 新闻内容
    news.content = content
    # 新闻主图片完整url
    news.index_image_url = constants.QINIU_DOMIN_PREFIX + image_name

    # 新闻来源
    news.source = source
    # 那个用户发布的新闻
    news.user_id = user.id
    # 默认发布的新闻未审核中：1
    news.status = 1

    # 3.2 保存回数据库
    try:
        db.session.add(news)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存新闻对象异常")

    # 返回发布成功
    return jsonify(errno=RET.OK, errmsg="发布新闻成功")


# 127.0.0.1:5000/user/user_collection?p=页码
@profile_bp.route('/user_collection', methods=["GET"])
@get_user_info
def user_collection():
    """当前用户的新闻收藏列表数据查询"""

    """
    1.获取参数
        1.1 p: 当前页码， user: 当前登录的用户
    2.校验参数
        2.1 非空判断
    3.逻辑处理
        3.0 user.collection_news是一个查询对象，在查询对象上调用paginate进行分页处理即可
        3.1 对象列表转换成字典列表
    4.返回值
        登录成功
    """

    # 1.1 p: 当前页码， user: 当前登录的用户
    # 默认查询第一页
    p = request.args.get("p", 1)
    user = g.user

    # 2.1 参数格式判断
    try:
        p = int(p)
    except Exception as e:
        current_app.logger.error(e)
        p = 1

    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")

    news_list = []
    current_page = 1
    total_page = 1
    # 3.0 user.collection_news是一个查询对象，在查询对象上调用paginate进行分页处理即可
    # 用于user.collection_news使用了lazy="dynamic"修饰
    # 如果真正用到数据：user.collection_news是一个列表
    # 如果用于查询：user.collection_news是一个查询对象
    try:
        paginate = user.collection_news.paginate(p, constants.USER_COLLECTION_MAX_NEWS, False)
        news_list = paginate.items
        current_page = paginate.page
        total_page = paginate.pages
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询用户对象异常")

    # 3.1 对象列表转换成字典列表
    news_dict_list = []
    for news in news_list if news_list else []:
        news_dict_list.append(news.to_dict())

    data = {
        "collections": news_dict_list,
        "current_page": current_page,
        "total_page": total_page
    }

    return render_template("user/user_collection.html", data=data)


# 127.0.0.1:5000/user/pass_info ---> 修改密码
@profile_bp.route('/pass_info', methods=["GET", "POST"])
@get_user_info
def pass_info():
    """修改密码接口实现"""
    # 查询当前登录用户对象
    user = g.user  # type:User

    # GET请求展示修改密码页面
    if request.method == "GET":
        return render_template("user/user_pass_info.html")

    # POST请求：修改密码
    """
    1.获取参数
        1.1 old_password:旧密码， news_password:新密码， user:当前登录的用户
    2.校验参数
        2.1 非空判断
    3.逻辑处理
        3.0 判断旧密码是否正确
        3.1 修改密码
        3.2 保存回数据库
    4.返回值
    """
    # 1.1 old_password:旧密码， news_password:新密码， user:当前登录的用户
    old_password = request.json.get("old_password")
    new_password = request.json.get("new_password")
    # 2.1 非空判断
    if not all([old_password, new_password]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")
    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")

    # 3.0 判断旧密码是否正确
    if not user.check_password(old_password):
        return jsonify(errno=RET.DATAERR, errmsg="旧密码填写错误")

    # 3.1 修改密码
    user.password = new_password
    # 3.2 保存回数据库
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存用户密码异常")

    return jsonify(errno=RET.OK, errmsg="修改密码成功")


# 127.0.0.1:5000/user/pic_info ---> 进入修改用户头像页面
@profile_bp.route('/pic_info', methods=["GET", "POST"])
@get_user_info
def pic_info():
    # 展示修改用户头像页面
    user = g.user

    # GET请求展示用户基本资料
    if request.method == "GET":
        return render_template("user/user_pic_info.html")

    # POST请求：修改用户头像数据
    """
    1.获取参数
        1.1 avatar:上传的图片对象， user:当前用户对象
    2.校验参数
        2.1 非空判断
    3.逻辑处理
        3.0 借助封装好的pic_store方法将图片数据上传到七牛云
        3.1 将图片名字保存到用户对象上
        3.2 将完整的图片url组织好，并返回
    4.返回值
    """

    # 1.1 avatar:上传的图片文件对象， user:当前用户对象
    avatar = request.files.get("avatar")

    # 2.1 非空判断
    # 读取二进制数据
    try:
        avatar_data = avatar.read()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="读取图片数据异常")

    if not avatar_data:
        return jsonify(errno=RET.NODATA, errmsg="图片二进制数据为空")

    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")

    # 3.0 借助封装好的pic_store方法将图片数据上传到七牛云
    try:
        pic_name = pic_store(avatar_data)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR, errmsg="上传图片到七牛云异常")

    # 3.1 将图片名字保存到用户对象上
    if pic_name:
        user.avatar_url = pic_name

    # 3.2 将完整的图片url组织好，并返回
    avatar_url = constants.QINIU_DOMIN_PREFIX + pic_name

    data = {
        "avatar_url": avatar_url
    }
    return jsonify(errno=RET.OK, errmsg="上传图片到七牛云成功", data=data)


# 127.0.0.1:5000/user/base_info ---> 进入个人中心基本数据页面
@profile_bp.route('/base_info', methods=["GET", "POST"])
@get_user_info
def base_info():
    # 获取登录用户个人信息传入模板显示
    user = g.user

    # GET请求展示用户基本资料
    if request.method == "GET":

        data = {
            "user_info": user.to_dict() if user else None
        }

        return render_template("user/user_base_info.html", data=data)

    # POST请求用户基本资料修改
    """
    1.获取参数
        1.1 user:当前登录用户对象，signature:个性签名，nick_name:昵称， gender:性别
    2.参数校验
        2.1 非空判断
        2.2 gender in ["MAN", "WOMAN"]
    3.逻辑处理
        3.1 修改用户对象各个属性
        3.2 保存回数据库
    4.返回值
    """
    # 1.1 user:当前登录用户对象，signature:个性签名，nick_name:昵称， gender:性别
    signature = request.json.get('signature')
    nick_name = request.json.get('nick_name')
    gender = request.json.get('gender')

    # 2.1 非空判断
    if not all([signature, nick_name, gender]):
        return jsonify(errno=RET.DBERR, errmsg="参数不足")

    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")
    # 2.2 gender in ["MAN", "WOMAN"]
    if gender not in ["MAN", "WOMAN"]:
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")
    # 3.1 修改用户对象各个属性
    user.signature = signature
    user.nick_name = nick_name
    user.gender = gender
    # 细节：修改session中的nick_name
    session["nick_name"] = user.nick_name

    # 3.2 保存回数据库
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存用户对象异常")

    return jsonify(errno=RET.OK, errmsg="修改用户基本资料成功")


# 127.0.0.1:5000/user/info ---> 进入个人中心
@profile_bp.route('/info')
@get_user_info
def user_info():
    """展示个人中心数据"""
    # 获取登录用户个人信息传入模板显示
    user = g.user

    data = {
        "user_info": user.to_dict() if user else None
    }
    return render_template("user/user.html", data=data)