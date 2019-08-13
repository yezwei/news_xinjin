from flask import request, render_template, current_app, session, redirect, url_for, g, abort, jsonify
from info.models import User, News, Category
from info.response_code import RET
from info.utils.pic_store import pic_store
from . import admin_bp
from info.utils.common import get_user_info
import time
from datetime import datetime, timedelta
from info import constants, db


# /admin/type_edit
@admin_bp.route('/type_edit', methods=["POST"])
def type_edit():
    """新增分类编辑分类"""
    """
    1.获取参数
        1.1 category_name: 分类的名称， category_id: 分类的id
    2.校验参数
        2.1 非空判断
    3.逻辑处理
        3.0 根据category_id判断是否有值
        有值：编辑分类：先查询出分类对象，再修改其分类名称
        无值：新增分类：创建分类对象，并赋值
        3.1 保存回数据库
    4.返回值
    """
    # 1.1 category_name: 分类的名称， category_id: 分类的id
    category_name = request.json.get("category_name")
    category_id = request.json.get("category_id")

    # 2.1 非空判断
    if not category_name:
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")

    #  3.0 根据category_id判断是否有值
    if category_id:
        #  有值：编辑分类：先查询出分类对象，再修改其分类名称
        try:
            category = Category.query.get(category_id)
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="查询分类对象异常")

        if not category:
            return jsonify(errno=RET.NODATA, errmsg="分类不存在不能编辑")

        # 编辑分类的名称
        category.name = category_name

    else:
        #  无值：新增分类：创建分类对象，并赋值
        category = Category()
        category.name = category_name
        db.session.add(category)

    #  3.1 保存回数据库
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存分类对象异常")

    return jsonify(errno=RET.OK, errmsg="分类操作完成")


# /admin/news_type
@admin_bp.route('/news_type')
def news_type():
    """展示分类数据页面"""
    # 查询所有分类数据
    # 获取分类数据
    try:
        categories = Category.query.all()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询分类异常")

    # 对象列表转字典列表
    # 模型列表转换字典列表
    category_dict_list = []
    for category in categories if categories else []:
        category_dict = category.to_dict()
        category_dict_list.append(category_dict)

    # 移除最新分类
    category_dict_list.pop(0)

    data = {
        "categories": category_dict_list
    }

    return render_template("admin/news_type.html", data=data)


# /admin/news_edit_detail?news_id=1
@admin_bp.route('/news_edit_detail', methods=["POST", "GET"])
def news_edit_detail():
    """新闻编辑详情页面"""

    # GET请求：展示新闻编辑详情数据
    if request.method == "GET":

        # 1.查询新闻对象数据

        # 获取新闻id
        news_id = request.args.get("news_id")

        news = None  # type: News

        # 查询数据
        if news_id:
            try:
                 news = News.query.get(news_id)
            except Exception as e:
                current_app.logger.error(e)
                return jsonify(errno=RET.DBERR, errmsg="查询用户对象异常")

        # 新闻对象转字典
        news_dict = news.to_dict() if news else None

        # 2.查询新闻分类数据
        # 获取分类数据
        try:
            categories = Category.query.all()
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="查询分类异常")

        # 对象列表转字典列表
        # 模型列表转换字典列表
        category_dict_list = []
        for category in categories if categories else []:
            category_dict = category.to_dict()
            # 任何分类都未选中
            category_dict["is_selected"] = False
            if category.id == news.category_id:
                # 选中该分类
                category_dict["is_selected"] = True
            category_dict_list.append(category_dict)

        # 移除最新分类
        category_dict_list.pop(0)

        data = {
            "news": news_dict,
            "categories": category_dict_list
        }

        # 3.渲染模板
        return render_template("admin/news_edit_detail.html", data=data)


    # POST请求：进行新闻编辑修改
    """
    1.获取参数
        1.1 title: 新闻标题，category_id: 分类id， digest：新闻摘要
            index_image:新闻主图片，content:新闻内容， news_id: 新闻id对象
    2.校验参数
        2.1 非空判断
        2.2 category_id强制数据类型转换
    3.逻辑处理
        3.0 根据id查询新闻对象，并给各个属性修改
        3.1 保存回数据库
    4.返回值
        编辑新闻成功
    """

    # 1.1 title: 新闻标题，category_id: 分类id， digest：新闻摘要
    #     index_image:新闻主图片，content:新闻内容，
    news_id = request.form.get("news_id")
    title = request.form.get("title")
    category_id = request.form.get("category_id")
    digest = request.form.get("digest")
    content = request.form.get("content")
    # 新闻主图片
    index_image = request.files.get("index_image")

    # 2.1 非空判断
    if not all([title, category_id, digest, news_id, content]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")
    # 2.2 category_id强制数据类型转换
    try:
        category_id = int(category_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR, errmsg="参数类型错误")

    image_name = ""
    if index_image:
        try:
            image_data = index_image.read()
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DATAERR, errmsg="读取图片数据异常")

        if not image_data:
            return jsonify(errno=RET.NODATA, errmsg="图片数据不能为空")

        # 3.0 将主图片上传到七牛云平台
        try:
            image_name = pic_store(image_data)
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.THIRDERR, errmsg="上传到七牛云异常")

    # 3.1 根据新闻id查询新闻对象
    news = None
    try:
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询用户对象异常")

    if not news:
        return jsonify(errno=RET.NODATA, errmsg="新闻对象不存在")

    # 新闻属性编辑
    # 新闻标题
    news.title = title
    # 新闻分类id
    news.category_id = category_id
    # 新闻摘要
    news.digest = digest
    # 新闻内容
    news.content = content
    if image_name:
        # 新闻主图片完整url
        news.index_image_url = constants.QINIU_DOMIN_PREFIX + image_name

    # 3.2 保存回数据库
    try:
        db.session.add(news)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存新闻对象异常")

    # 返回发布成功
    return jsonify(errno=RET.OK, errmsg="编辑新闻成功")


# 127.0.0.1:5000/admin/news_edit?p=1 --> 新闻编辑页面
@admin_bp.route('/news_edit')
def news_edit():
    """查询新闻编辑页面数据"""

    # 1.获取当前页码
    p = request.args.get("p", 1)
    # 搜索关键字
    keywords = request.args.get("keywords")

    # 2.当前页码的类型判断
    try:
        p = int(p)
    except Exception as e:
        current_app.logger.error(e)
        p = 1

    news_list = []
    current_page = 1
    total_page = 1

    # 定义过滤条件列表
    filter_list = []
    # 如果存在关键字，进行关键字搜索
    if keywords:
        filter_list.append(News.title.contains(keywords))

    # 3.用户数据的分页查询
    try:
        # 查询条件1：如果关键字存在，关键字过滤查询 keywords是否包含于新闻标题
        paginate = News.query.filter(*filter_list).order_by(News.create_time.desc())\
            .paginate(p, constants.ADMIN_NEWS_EDIT_PAGE_MAX_COUNT, False)

        news_list = paginate.items
        current_page = paginate.page
        total_page = paginate.pages

    except Exception as e:
        current_app.logger.error(e)
        return abort(404)

    # 4.用户对象列表转字典列表
    news_dict_list = []
    for news in news_list if news_list else []:
        news_dict_list.append(news.to_basic_dict())

    data = {
        "news_list": news_dict_list,
        "current_page": current_page,
        "total_page": total_page
    }
    # 5.返回模板
    return render_template("admin/news_edit.html", data=data)


@admin_bp.route('/news_review_detail', methods=["POST", "GET"])
def news_review_detail():
    """新闻审核的详情页面接口"""

    # GET请求：展示新闻审核详情页面数据
    if request.method == "GET":

        # 获取get请求问好后携带的新闻id值
        news_id = request.args.get("news_id")

        news = None  # type: News
        if news_id:
            # 查询当前新闻对象
            try:
                news = News.query.get(news_id)
            except Exception as e:
                current_app.logger.error(e)
                abort(404)

        # 将新闻对象转换成字典
        news_dict = news.to_dict() if news else None

        data = {
            "news": news_dict,
        }
        return render_template("admin/news_review_detail.html", data=data)

    # POST请求： 新闻审核通过&拒绝的业务逻辑处理
    """
    1.获取参数
        1.1 news_id: 新闻id， action: 审核的行为， reason:拒绝原因
    2.校验参数
        2.1 非空判断
        2.2 action in ["accept", "reject"]
    3.逻辑处理
        3.0 根据新闻id查询当前新闻对象
        3.1 判断action审核行为
        审核通过：将news对象的status属性修改为：0
        审核不通过：将news对象的status属性修改为：-1 同时设置拒绝原因
        3.2 上述修改保存回数据库
    4.返回值
        审核完毕
    """
    # 1.1 news_id: 新闻id， action: 审核的行为， reason:拒绝原因
    news_id = request.json.get("news_id")
    action = request.json.get("action")
    reason = request.json.get("reason")

    # 2.1 非空判断
    if not all([news_id, action]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")

    # 2.2 action in ["accept", "reject"]
    if action not in ["accept", "reject"]:
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    # 3.0 根据新闻id查询当前新闻对象
    news = None
    try:
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询新闻对象异常")
    if not news:
        return jsonify(errno=RET.NODATA, errmsg="新闻对象不存在")

    # 3.1 判断action审核行为
    if action == "accept":
        # 审核通过：将news对象的status属性修改为：0
        news.status = 0
    else:
        # 审核不通过：将news对象的status属性修改为：-1 同时设置拒绝原因
        if reason:
            news.status = -1
            news.reason = reason
        else:
            return jsonify(errno=RET.PARAMERR, errmsg="请填写拒绝原因")
    # 3.2 上述修改保存回数据库
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="查询用户对象异常")

    return jsonify(errno=RET.OK, errmsg="审核完毕")


@admin_bp.route('/news_review')
def news_review():
    """查询新闻审核页面数据"""

    # 1.获取当前页码
    p = request.args.get("p", 1)
    # 搜索关键字
    keywords = request.args.get("keywords")

    # 2.当前页码的类型判断
    try:
        p = int(p)
    except Exception as e:
        current_app.logger.error(e)
        p = 1

    news_list = []
    current_page = 1
    total_page = 1

    # 定义过滤条件列表
    filter_list = [News.status != 0]

    # 如果存在关键字，进行关键字搜索
    if keywords:
        filter_list.append(News.title.contains(keywords))

    # 3.用户数据的分页查询
    try:
        # 查询条件1：查询审核未通过&未审核的新闻 News.status != 0
        # 查询条件2：如果关键字存在，关键字过滤查询 keywords是否包含于新闻标题
        paginate = News.query.filter(*filter_list).order_by(News.create_time.desc())\
            .paginate(p, constants.ADMIN_NEWS_REVIEW_PAGE_MAX_COUNT, False)

        news_list = paginate.items
        current_page = paginate.page
        total_page = paginate.pages

    except Exception as e:
        current_app.logger.error(e)
        return abort(404)

    # 4.用户对象列表转字典列表
    news_dict_list = []
    for news in news_list if news_list else []:
        news_dict_list.append(news.to_review_dict())

    data = {
        "news_list": news_dict_list,
        "current_page": current_page,
        "total_page": total_page
    }
    # 5.返回模板
    return render_template("admin/news_review.html", data=data)


# 127.0.0.1:5000/admin/user_list?p=1
@admin_bp.route('/user_list')
def user_list():
    """查询用户列表数据"""

    # 1.获取当前页码
    p = request.args.get("p", 1)

    # 2.当前页码的类型判断
    try:
        p = int(p)
    except Exception as e:
        current_app.logger.error(e)
        p = 1

    user_list = []
    current_page = 1
    total_page = 1
    # 3.用户数据的分页查询
    try:
        # 查询条件1：普通用户 时间降序排序
        paginate = User.query.filter(User.is_admin == False).order_by(User.create_time.desc()).\
            paginate(p, constants.ADMIN_USER_PAGE_MAX_COUNT, False)
        user_list = paginate.items
        current_page = paginate.page
        total_page = paginate.pages

    except Exception as e:
        current_app.logger.error(e)
        return abort(404)

    # 4.用户对象列表转字典列表
    user_dict_list = []
    for user in user_list if user_list else []:
        user_dict_list.append(user.to_admin_dict())

    data = {
        "users": user_dict_list,
        "current_page": current_page,
        "total_page": total_page
    }
    # 5.返回模板
    return render_template("admin/user_list.html", data=data)



@admin_bp.route('/user_count')
def user_count():

    # 查询总人数
    total_count = 0
    try:
        total_count = User.query.filter(User.is_admin == False).count()
    except Exception as e:
        current_app.logger.error(e)


    # 查询月新增数
    """
    time.struct_time(tm_year=2019, tm_mon=1, tm_mday=27, tm_hour=15, tm_min=50, tm_sec=59, tm_wday=6, tm_yday=27, tm_isdst=0)
    月起始时间： 2019-01-01  -- 今天
    月起始时间： 2019-02-01  -- xxx
    月起始时间： 2018-12-01  -- xxx
    """
    mon_count = 0
    try:
        # 获取当前系统时间
        now = time.localtime()
        # 每一个月的起始时间, 字符串数据
        mon_begin = '%d-%02d-01' % (now.tm_year, now.tm_mon)
        # strptime(): 将字符串转换成时间格式
        mon_begin_date = datetime.strptime(mon_begin, '%Y-%m-%d')
        #  用户创建时间 >= 每一个月的起始时间  ： 表示月新增人数
        mon_count = User.query.filter(User.is_admin == False, User.create_time >= mon_begin_date).count()
    except Exception as e:
        current_app.logger.error(e)


    # 查询日新增数
    """
     日起始时间： 2019-01-27 00：00
     日起始时间： 2019-01-28 00：00
    """
    day_count = 0
    try:
        day_begin = '%d-%02d-%02d' % (now.tm_year, now.tm_mon, now.tm_mday)
        day_begin_date = datetime.strptime(day_begin, '%Y-%m-%d')
        #  用户的创建时间 >  今天的起始时间 ： 表示日新增人数
        day_count = User.query.filter(User.is_admin == False, User.create_time > day_begin_date).count()
    except Exception as e:
        current_app.logger.error(e)

    # 查询图表信息
    # 获取到当天00:00:00时间
    now_date = datetime.strptime(datetime.now().strftime('%Y-%m-%d'), '%Y-%m-%d')
    # 定义空数组，保存数据
    active_date = []
    active_count = []

    """
    begin_date = now_date - timedelta(days=i)
    
    当前时间： 2019-01-27 00：00  
    
    一天的起始时间：  2019-01-27 00：00  - 0天
    结束时间 ：   2019-01-27 00：00 +  1天 ==  2019-01-27 23：59
    
    一天的起始时间：  2019-01-27 00：00  - 1天
    结束时间 ：   2019-01-26 00：00 +  1天 ==  2019-01-26 23：59
    
     一天的起始时间： 2019-01-27 00：00  - 2天 
    结束时间 ：   2019-01-25 00：00 +  1天 ==  2019-01-25 23：59
        ....
        
    一天的起始时间： 2019-01-27 00：00  - 30天 = 2018-12-28 
    结束时间 ：   2018-12-28 00：00 +  1天 ==  2018-12-28 23：59
 
    结束时间  ==  起始时间 + 1天
    """

    # 依次添加数据，再反转
    for i in range(0, 31):  # 0 1 2...30
        # 01-27 00：00  = 01-27  -  0天
        # 每一天的起始时间
        begin_date = now_date - timedelta(days=i)
        # 每一天的结束时间 ==  起始时间 + 1天
        # end_date = now_date - timedelta(i) + timedelta(days=1)
        # end_date =  begin_date +  timedelta(days=1)
        end_date = begin_date + timedelta(days=1)

        # 将每一天的时间添加到列表中
        active_date.append(begin_date.strftime('%Y-%m-%d'))
        count = 0
        try:
            #  每一天的起始时间 <= 当前登录的用户时间 < 每一天的结束时间
            count = User.query.filter(User.is_admin == False, User.last_login >= begin_date,
                                      User.last_login < end_date).count()
        except Exception as e:
            current_app.logger.error(e)
        # 添加每一天的用户活跃量
        active_count.append(count)

    # 将数据反转
    active_date.reverse()
    active_count.reverse()

    data = {"total_count": total_count, "mon_count": mon_count, "day_count": day_count, "active_date": active_date,
            "active_count": active_count}

    return render_template('admin/user_count.html', data=data)


# 127.0.0.1:5000/admin/index  --> 后台管理首页
@admin_bp.route('/index')
@get_user_info
def admin_index():
    """后台首页"""
    # 管理员用户对象
    user = g.user
    data = {
        "user_info": user.to_dict() if user else None
    }
    return render_template("admin/index.html", data=data)


# 127.0.0.1:5000/admin/login  --> 后台管理登录页面
@admin_bp.route('/login', methods=["GET", "POST"])
def admin_login():
    """后台管理员登录接口"""
    # GET请求：展示管理员登录页面
    # 需求：当管理员用户已经登录成功，我们就可以直接将其引导到管理员首页即可
    if request.method == "GET":

        # 获取用户id
        user_id = session.get("user_id")
        # 获取is_admin字段
        is_admin = session.get("is_admin", False)

        # 判断是否登录，以及是否是管理员
        if user_id and is_admin == True:
            # 是管理员-直接引导到管理员首页
            return redirect(url_for("admin.admin_index"))
        else:
            # 不是管理员-返回登录页面
            return render_template("admin/login.html")

    # POST请求：管理员登录逻辑实现
    """
    1.获取参数
        1.1 username手机号码，password未加密密码
    2.校验参数
        2.1 非空判断
    3.逻辑处理
        3.0 查询用户是否存在
        3.1 验证密码是否一致
        3.2 不一致： 提示密码填写错误
        3.3 一致：记录用户登录信息
    4.返回值
        登录成功
    """

    # 1.1 mobile手机号码，password未加密密码
    username = request.form.get("username")
    password = request.form.get("password")

    # 2.1 非空判断
    if not all([username, password]):
        return render_template("admin/login.html", errmsg="参数不足")

    admin_user = None  # type: User
    # 3.0 查询用户是否存在
    try:
        admin_user = User.query.filter(User.is_admin == True, User.mobile == username).first()
    except Exception as e:
        current_app.logger.error(e)
        return render_template("admin/login.html", errmsg="查询用户对象异常")

    if not admin_user:
        return render_template("admin/login.html", errmsg="管理员用户不存在")

    # 3.1 验证密码是否一致
    if not admin_user.check_password(password):
        # 3.2 不一致： 提示密码填写错误
        return render_template("admin/login.html", errmsg="密码填写错误")

    # 3.3 一致：记录用户登录信息
    session["user_id"] = admin_user.id
    session["nick_name"] = admin_user.nick_name
    session["mobile"] = admin_user.mobile
    # 记录用户是管理员
    session["is_admin"] = True

    # TODO: 跳转到管理员首页
    return redirect(url_for("admin.admin_index"))











