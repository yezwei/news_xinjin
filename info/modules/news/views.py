from info import constants, db
from info.models import User, News, Comment, CommentLike
from info.response_code import RET
from info.utils.common import get_user_info
from . import news_bp
from flask import render_template, session, current_app, jsonify, g, request


# 127.0.0.1:5000/news/followed_user
@news_bp.route('/followed_user', methods=['POST'])
@get_user_info
def user_followed():
    """关注、取消管制后端接口"""
    """
    1.获取参数
        1.1 user_id:作者id， user:当前登录的用户对象， action:关注&取消关注的行为
    2.参数校验
        2.1 非空判断
        2.2 action in ["follow", "unfollow"]
    3.逻辑处理
        3.1 根据user_id查询当前作者对象
        3.2 根据action判断是否关注
        关注：
        1. 将作者添加到用户的关注列表中：user.followed.append(author)
        2. 将用户添加到作者的粉丝列表中：author.followers.append(user)
        取消关注：
        1. 将作者从用户的关注列表中移除：user.followed.remove(author)
        2. 将用户从作者的粉丝列表中移除：author.followers.remove(user)
        3.3 保存回数据库
    4.返回值
    """
    # 1.1 user_id:作者id， user:当前登录的用户对象， action:关注&取消关注的行为
    user_id = request.json.get("user_id")
    action = request.json.get("action")
    user = g.user

    # 2.1 非空判断
    if not all([user_id, action]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")
    # 2.2 action in ["follow", "unfollow"]
    if action not in ["follow", "unfollow"]:
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")

    # 3.1 根据user_id查询当前作者对象
    author = None
    try:
        author = User.query.get(user_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询用户对象异常")
    if not author:
        return jsonify(errno=RET.NODATA, errmsg="作者不存在")

    # 3.2 根据action判断是否关注
    if action == "follow":
        # 关注：
        # 1. 将作者添加到用户的关注列表中：user.followed.append(author)
        # 2. 将用户添加到作者的粉丝列表中：author.followers.append(user)
        if author in user.followed:
            return jsonify(errno=RET.DATAEXIST, errmsg="不能重复关注")
        else:
            # 将作者添加到用户关注列表中
            user.followed.append(author)
    else:
        # 取消关注：
        # 1. 将作者从用户的关注列表中移除：user.followed.remove(author)
        # 2. 将用户从作者的粉丝列表中移除：author.followers.remove(user)
        if author not in user.followed:
            return jsonify(errno=RET.NODATA, errmsg="用户未关注，请先关注")
        else:
            # 将作者从到用户关注列表中移除
            user.followed.remove(author)

    # 3.3 保存回数据库
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存关注信息异常")

    return jsonify(errno=RET.OK, errmsg="OK")


# 127.0.0.1:5000/news/comment_like
@news_bp.route('/comment_like', methods=['POST'])
@get_user_info
def comment_like():
    """点赞&取消点赞后端接口"""
    """
    1.获取参数
        1.1 comment_id:评论id， user:当前登录的用户对象， action:点赞&取消点赞的行为
    2.参数校验
        2.1 非空判断
        2.2 action in ["add", "remove"]
    3.逻辑处理
        3.1 根据comment_id查询当前评论对象
        3.2 查询CommentLike模型对应的对象是否存在
        3.3 根据action行为判别点赞&取消点赞
        点赞：不存在，创建CommentLike类的对象，并给各个属性赋值，
        对应评论对象上的点赞数量加一
        
        取消点赞：存在，移除CommentLike类的对象
        对应评论对象上的点赞数量减一
    
    4.返回值
    
    """
    # 1.1 comment_id:评论id， user:当前登录的用户对象， action:点赞&取消点赞的行为
    comment_id = request.json.get("comment_id")
    action = request.json.get("action")
    user = g.user

    # 2.1 非空判断
    if not all([comment_id, action]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")
    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")
    # 2.2 action in ["add", "remove"]
    if action not in ["add", "remove"]:
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    # 3.1 根据comment_id查询当前评论对象
    try:
        comment = Comment.query.get(comment_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询评论对象异常")
    if not comment:
        return jsonify(errno=RET.NODATA, errmsg="评论对象不存在，不能点赞")

    # 3.2 查询CommentLike模型对应的对象是否存在
    comment_like = None
    try:
        # 查询条件：
        # 1. 上传的 `评论id` 必须是等于`评论点赞模型`中的评论id
        # 2. 当前登录的用户id 等于 `评论点赞模型`中的用户id
        comment_like = CommentLike.query.filter(CommentLike.comment_id == comment_id,
                                 CommentLike.user_id == user.id).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询用户对象异常")
    # 3.3 根据action行为判别点赞&取消点赞
    if action == "add":
        # `评论点赞对象` 不存在的情况我们需要创建`评论点赞对象`并保存到数据库
        if not comment_like:
            # 点赞：不存在，创建CommentLike类的对象，并给各个属性赋值，
            comment_like_obj = CommentLike()
            comment_like_obj.user_id = user.id
            comment_like_obj.comment_id = comment_id
            # 对应`评论对象`上的点赞数量加一
            comment.like_count += 1

            # 将新创建的评论点赞对象添加到数据库会话对象中
            db.session.add(comment_like_obj)
    else:
        # 只有评论点赞对象存在的情况才有资格取消点赞
        if comment_like:
            # 取消点赞：存在，移除CommentLike类的对象
            db.session.delete(comment_like)
            # 对应评论对象上的点赞数量减一
            comment.like_count -= 1
    # 对应上述修改操作需要提交到数据库
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存评论点赞对象异常")

    # 返回点赞、取消点赞成功
    return jsonify(errno=RET.OK, errmsg="OK")


# 127.0.0.1:5000/news/news_comment  参数通过请求体携带
@news_bp.route('/news_comment', methods=['POST'])
@get_user_info
def news_comment():
    """发布主/子评论后端接口"""
    """
    1.获取参数
        1.1 news_id:新闻id，user:当前登录的用户，comment:评论的内容，parent_id:区分主评论和子评论字段【非必传】
    2.参数校验
        2.1 非空判断
    3.逻辑处理
        3.1 根据news_id获取新闻对象，新闻对象存在才能发布评论
        3.2 创建评论对象
        3.3 parent_id没有值： 创建主评论对象
        3.4 parent_id有值：创建子评论对象
        3.5 将评论对象保存回数据库
    4.返回值
        4.1 发布评论成功
    """
    # 1.1 news_id:新闻id，user:当前登录的用户，comment:评论的内容，parent_id:区分主评论和子评论字段【非必传】
    news_id = request.json.get("news_id")
    content = request.json.get("comment")
    parent_id = request.json.get("parent_id")
    user = g.user

    # 2.1 非空判断
    if not all([news_id, content]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")
    # 用户未登录
    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")

    # 3.1 根据news_id获取新闻对象，新闻对象存在才能发布评论
    try:
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询新闻对象异常")
    if not news:
        return jsonify(errno=RET.NODATA, errmsg="新闻不存在不能发布评论")

    # 3.2 创建评论对象
    comment = Comment()
    # 给各个属性赋值
    comment.user_id = user.id
    comment.news_id = news.id
    comment.content = content
    # 3.3 parent_id没有值： 创建主评论对象
    # 3.4 parent_id有值：创建子评论对象
    if parent_id:
        comment.parent_id = parent_id

    # 3.5 将评论对象保存回数据库
    try:
        db.session.add(comment)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        # 数据回滚
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存评论对象异常")

    # 考虑到前端发布完评论后，页面需要局部刷新数据，所以需要将评论数据返回
    comment_dic = comment.to_dict() if comment else None
    data = {
        "comment": comment_dic
    }
    return jsonify(errno=RET.OK, errmsg="发布评论成功", data=data)


# 127.0.0.1:5000/news/news_collect  参数通过请求体携带
@news_bp.route('/news_collect', methods=['POST'])
@get_user_info
def news_collect():
    """收藏&取消收藏的后端接口"""
    """
    1.获取参数
        1.1 news_id: 当前新闻id值， action:收藏&取消收藏的行为， user:当前登录的用户
    2.校验参数
        2.1 非空判断
        2.2 action in ["collect", "cancel_collect"]
    3.逻辑处理
        3.1 根据新闻id查询新闻对象
        
        3.2 根据action判断是收藏还是取消收藏的行为
        收藏：将新闻对象news添加到user.collection_news列表中
        取消收藏：将新闻对象news从user.collection_news列表中移除
        
        3.3 将上述修改操作保存回数据库
    4.返回值
    """

    # 1.1 news_id: 当前新闻id值， action:收藏&取消收藏的行为， user:当前登录的用户
    news_id = request.json.get("news_id")
    action = request.json.get("action")
    user = g.user

    # 2.1 非空判断
    if not all([news_id, action]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")

    if not user:
        # 用户未登录
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")

    # 2.2 action in ["collect", "cancel_collect"]
    if action not in ["collect", "cancel_collect"]:
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    # 3.1 根据新闻id查询新闻对象
    try:
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询新闻对象异常")
    if not news:
        # 新闻对象不存在，不允许收藏
        return jsonify(errno=RET.NODATA, errmsg="新闻对象不存在")

    # 3.2 根据action判断是收藏还是取消收藏的行为
    if action == "collect":
        # 收藏：将新闻对象news添加到user.collection_news列表中
        # 当前新闻不在当前用户的收藏列表中，我们才添加收藏
        if news not in user.collection_news:
            user.collection_news.append(news)
    else:
        # 取消收藏：将新闻对象news从user.collection_news列表中移除

        # 只有新闻在用户的收藏列表中，我们才有资格移除新闻对象，表示取消收藏
        if news in user.collection_news:
            user.collection_news.remove(news)

    # 3.3 将上述修改操作保存回数据库
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        # 数据回滚
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存新闻收藏数据异常")

    return jsonify(errno=RET.OK, errmsg="OK")


# 127.0.0.1:5000/news/新闻id
@news_bp.route('/<int:news_id>')
@get_user_info
def news_detail(news_id):
    """新闻详情接口"""
    # -----------------------1.查询当前登录用户的信息展示-----------------------------
    user = g.user

    # 3.将用户对象转换成字典
    # if user:
    #     user_dict = user.to_dict()
    user_dict = user.to_dict() if user else None

    # -----------------------2.查询新闻的点击排行数据-----------------------------
    # news_rank_list = [news_obj1, news_obj2, ....]
    try:
        # 1.新闻点击量降序排序
        # 2.限制新闻条数为6条
        news_rank_list = News.query.order_by(News.clicks.desc()).limit(constants.CLICK_RANK_MAX_NEWS)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询点击排行新闻对象异常")

    # 将新闻对象列表数据转换成字典列表数据
    """
        if news_rank_list:
        for news in news_rank_list:
            news_dict = news.to_dict()
            newsrank_dict_list.append(news_dict)
    """
    newsrank_dict_list = []
    for news in news_rank_list if news_rank_list else []:
        # 将新闻对象转换成字典装入列表中
        newsrank_dict_list.append(news.to_dict())

    # -----------------------3.查询新闻详情数据-----------------------------
    try:
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询新闻详情对象异常")

    # 新闻详情对象转换成字典
    news_detail_dict = news.to_dict() if news else None

    # -----------------------4.查询当前用户是否收藏当前新闻-----------------------------
    # 定义一个标志位 默认值False：当前用户未收藏该新闻，反之
    is_collected = False

    # 当前用户已经登录才去进行查询数据
    if user:
        # 当前新闻在用户的新闻收藏列表中：表示收藏过该新闻
        if news in user.collection_news:
            is_collected = True
    # -----------------------5.查询当前新闻对应的评论列表数据-----------------------------
    # 查询条件：评论的新闻id == 当前新闻的id，代表查询的是当前新闻下面的所有评论数据
    try:
        comment_list = Comment.query.filter(Comment.news_id == news_id).order_by(Comment.create_time.desc()).all()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询评论数据异常")

    # -----------------------6.查询当前登录用户具体对那几条评论点赞-----------------------------

    # 1. 查询出当前新闻的所有评论，取得所有评论的id —>  list[1,2,3,4,5,6]
    comment_id_list = [comment.id for comment in comment_list]

    commentlike_id_list = []
    # 只有当前用户处于登录状态才需要查询
    if user:
        # 2.再通过评论点赞模型(CommentLike)查询当前用户点赞了那几条评论  —>[模型1,模型2...]
        # 查询条件1： 1  in [1,2,3,4,5,6]
        # 查询条件2： 1 == 1 当前登录的用户id和点赞的用户id保持一致
        # 返回值：commentlike_list = [评论点赞对象1， 评论点赞对象2....]
        try:
            commentlike_list = CommentLike.query.filter(CommentLike.comment_id.in_(comment_id_list),
                                     CommentLike.user_id == user.id).all()
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="查询用户对象异常")

        # 3. 遍历上一步的评论点赞模型列表，获取所以点赞过的评论id（comment_like.comment_id）
        # [1, 3, 5]
        commentlike_id_list = [commentlike_obj.comment_id for commentlike_obj in commentlike_list]


    # 评论对象列表转字典列表
    comment_dict_list = []
    for comment in comment_list if comment_list else []:
        # 评论对象转字典
        comment_dict = comment.to_dict()
        # 给每一个评论字典添加一个标志位,默认值：False 表示未点赞
        comment_dict["is_like"] = False
        # comment.id = 1  in [1, 3, 5] comment_dict["is_like"] = True
        # comment.id = 2  in [1, 3, 5]  comment_dict["is_like"] = False
        # comment.id = 3  in [1, 3, 5]  comment_dict["is_like"] = True
        if comment.id in commentlike_id_list:
            # 表示点赞
            comment_dict["is_like"] = True
        comment_dict_list.append(comment_dict)

    # -----------------------7.查询当前`登录用户`是否关注当前`新闻的作者`-----------------------------

    """
    登录用户：user
    新闻的作者: author
    关注关系[两种表示]：
        1.当前用户在作者的粉丝列表中：表示当前用户关注了作者
        user in author.followers
        2.作者在用户的关注列表中： 表示当前用户关注了作者
        author in user.followed
    """
    # 是否关注的标志位
    is_followed = False
    # 查询新闻作者
    author = User.query.filter(User.id == news.user_id).first()

    if user and author:
        # user.followed: 用户的关注列表
        if author in user.followed:
            is_followed = True


    # 4.组织返回数据
    """
    数据格式：
        data = {
            "user_info" : resp_dict = {
                "id": self.id,
                "nick_name": self.nick_name,
            }
        }

    使用： resp.data.user_info.nick_name
    """
    data = {
        "user_info": user_dict,
        "click_news_list": newsrank_dict_list,
        "news": news_detail_dict,
        "is_collected": is_collected,
        "comment_list": comment_dict_list,
        "is_followed": is_followed
    }

    return render_template("news/detail.html", data=data)