from . import passport_bp
from flask import request, abort, make_response, jsonify, current_app, session
from info.utils.captcha.captcha import captcha
from info import redis_store, constants, db
from info.response_code import RET
from info.models import User
from info.lib.yuntongxun.sms import CCP
import re
import random
from datetime import datetime


# 127.0.0.1：5000/passport/login_out ，没有参数
@passport_bp.route('/login_out', methods=["POST"])
def login_out():
    """退出登录"""

    # 1.删除session中的键值对数据
    session.pop("user_id", None)
    session.pop("nick_name", None)
    session.pop("mobile", None)
    # 注意： 退出登录时候如果是管理员用户需要清除is_admin字段内容
    session.pop("is_admin", None)
    # 2.返回退出登录成功
    return jsonify(errno=RET.OK, errmsg="退出登录成功")


# 127.0.0.1：5000/passport/login  参数是借助请求体携带
@passport_bp.route('/login', methods=["POST"])
def login():
    """登录的后端接口"""
    """
    1.获取参数
        1.1 mobile:手机号码 ， password:密码
    2.参数校验
        2.1 非空判断
        2.2 手机号码格式判断
    3.逻辑处理
        3.1 根据手机号码查询当前用户对象
        3.2 用户存在，进行密码对比
        3.2.1 修改最后一次登录时间
        3.3 登录成功记录用户信息
    4.返回值
        4.1 登录成功
    """

    # 1.1 mobile:手机号码 ， password:密码
    mobile = request.json.get("mobile")
    password = request.json.get("password")

    # 2.1 非空判断
    if not all([mobile, password]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")

    # 2.2 手机号码格式校验
    if not re.match(r"1[3546789][0-9]{9}", mobile):
        return jsonify(errno=RET.PARAMERR, errmsg="手机号码格式错误")

    # 3.1 根据手机号码查询当前用户对象
    user = None
    try:
        user = User.query.filter(User.mobile == mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询用户对象异常")
    if not user:
        # 用户不存在
        return jsonify(errno=RET.USERERR, errmsg="用户不存在")

    # 3.2 用户存在，进行密码对比
    if not user.check_password(password):
        # 密码填写错误
        return jsonify(errno=RET.DATAERR, errmsg="密码填写错误")

    # 3.2.1 修改最后一次登录时间
    user.last_login = datetime.now()
    # 将用户修改操作提交到数据库
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        # 数据库回滚
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="用户属性异常")

    # 3.3 登录成功记录用户信息
    session["nick_name"] = user.nick_name
    session["mobile"] = user.mobile
    session["user_id"] = user.id

    # 4.1 登录成功
    return jsonify(errno=RET.OK, errmsg="登录成功")


# 127.0.0.1：5000/passport/register  参数是借助请求体携带： {"mobile"： 18622222， ...}
@passport_bp.route('/register', methods=["POST"])
def register():
    """注册的后端接口"""

    """
    1.获取参数
        1.1 mobile: 手机号码， sms_code:用户填写的短信验证码， password:未加密的密码
    2.参数校验
        2.1 非空判断
        2.2 手机号码格式判断
    3.逻辑处理
        3.1 根据手机号码作为key去redis数据库获取真实的短信验证码值
            有值：将真实的短信验证码值从redis数据库删除
            没有值：短信验证码过期了
        3.2 对比用户填写的短信验证码值和真实的短信验证码值是否一致
            相等：注册
            不相等：填写的短信验证码错误
        3.3 注册：创建用户对象，并给各个属性赋值
        3.4 注册成功一般要求登录成功，使用session记录用户登录信息
    4.返回值
        4.1 返回注册成功
    """

    # 1.1 mobile: 手机号码， sms_code:用户填写的短信验证码， password:未加密的密码
    param_dict = request.json
    mobile = param_dict.get("mobile")
    sms_code = param_dict.get("sms_code")
    password = param_dict.get("password")

    # 2.1 非空判断
    if not all([mobile, sms_code, password]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")

    # 2.2 手机号码格式校验
    if not re.match(r"1[3546789][0-9]{9}", mobile):
        return jsonify(errno=RET.PARAMERR, errmsg="手机号码格式错误")

    #  3.1 根据手机号码作为key去redis数据库获取真实的短信验证码值
    try:
        real_sms_code = redis_store.get("SMS_%s" % mobile)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询短信验证码异常")

    #  有值：将真实的短信验证码值从redis数据库删除
    if real_sms_code:
        redis_store.delete("SMS_%s" % mobile)
    #  没有值：短信验证码过期了
    else:
        return jsonify(errno=RET.NODATA, errmsg="短信验证码过期")

    #  3.2 对比用户填写的短信验证码值和真实的短信验证码值是否一致
    if sms_code != real_sms_code:
        # 不相等：填写的短信验证码错误
        return jsonify(errno=RET.DATAERR, errmsg="短信验证码填写错误")

    #  3.3 注册：创建用户对象，并给各个属性赋值
    user = User()
    # 昵称
    user.nick_name = mobile
    # 账号
    user.mobile = mobile
    # TODO：密码加密
    # user.set_password_hash(password)
    # 给属性赋值：触发的是属性的set方法
    user.password = password

    # # 提取属性的值：触发的是属性的get方法
    # print(user.password)

    # 最后一次登录时间
    user.last_login = datetime.now()

    try:
        # 保存回数据库
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        # 回滚
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存用户对象异常")

    # 3.4 注册成功一般要求登录成功，使用session记录用户登录信息
    session["nick_name"] = user.nick_name
    session["mobile"] = user.mobile
    session["user_id"] = user.id

    # 4.1 返回注册成功
    return jsonify(errno=RET.OK, errmsg="注册成功")


# 127.0.0.1：5000/passport/sms_code   参数是借助请求体携带： {"mobile"： 18622222， ...}
@passport_bp.route('/sms_code', methods=["POST"])
def send_sms_code():
    """发送短信验证码的后端接口"""

    """
    1.获取参数
        1.1 mobile: 手机号码， image_code:用户填写的图片验证码值， image_code_id: UUID编号
    2.校验参数
        2.1 非空判断
        2.2 手机号码格式校验
    3.逻辑处理
        3.1 根据image_code_id编号去redis中获取正确真实的图片验证码值
            3.1.1 真实的图片验证码有值：将值从redis数据库删除 [避免拿着这个值多次判断]
            3.1.2 真实的图片验证码没有值：图片验证码值过期了
        3.2 比对用户填写的图片验证码值 & 正确的图片验证码真实值
        3.3 不相等：返回错误状态码，提示图片验证码填写错误
        TODO: 提前判断手机号码是否注册过，数据库查询 [提高用户体验]
        3.4 发送短信验证码
        3.4.1 生成6位的随机短信验证码值
        3.4.2 调用CCP类发送短信验证码
        3.4.3 发送短信验证码成功后，保存6位的短信验证码值到redis数据库
    4.返回值
        4.1 发送短信验证码成功
    """
    # 1.1 mobile: 手机号码， image_code:用户填写的图片验证码值， image_code_id: UUID编号
    # 自动将json数据转换成字典
    param_dict = request.json
    mobile = param_dict.get("mobile")
    image_code = param_dict.get("image_code")
    image_code_id = param_dict.get("image_code_id")

    # 2.1 非空判断
    if not all([mobile, image_code, image_code_id]):

        # 参数不足 并且返回json格式数据
        # return jsonify({"errno": RET.PARAMERR, "errmsg": "参数不足"})
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")

    # 2.2 手机号码格式校验
    if not re.match(r"1[3546789][0-9]{9}", mobile):
        return jsonify(errno=RET.PARAMERR, errmsg="手机号码格式错误")

    # 3.1 根据image_code_id编号去redis中获取正确真实的图片验证码值
    try:
        real_image_code = redis_store.get("imageCode_%s" % image_code_id)
    except Exception as e:
        # 使用flask方式记录日志
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询图片验证码真实值数据异常")

    # 3.1.1 真实的图片验证码有值：将值从redis数据库删除 [避免拿着这个值多次判断]
    if real_image_code:
        redis_store.delete("imageCode_%s" % image_code_id)
    # 3.1.2 真实的图片验证码没有值：图片验证码值过期了
    else:
        return jsonify(errno=RET.NODATA, errmsg="图片验证码值过期了")

    # 3.2 比对用户填写的图片验证码值 & 正确的图片验证码真实值
    # 注意：忽略大小写 设置decode_responses=True
    if image_code.lower() != real_image_code.lower():
        # 4004 错误状态码，前端获取到后，需要重新生成一张图片
        # 3.3 不相等：返回错误状态码，提示图片验证码填写错误
        return jsonify(errno=RET.DATAERR, errmsg="图片验证码填写错误")

    # TODO: 提前判断手机号码是否注册过，数据库查询 [提高用户体验]
    try:
        user = User.query.filter(User.mobile == mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询用户对象异常")

    if user:
        # 用户已经注册
        return jsonify(errno=RET.DATAEXIST, errmsg="用户手机号码已经注册")

    # 3.4 发送短信验证码
    # 3.4.1 生成6位的随机短信验证码值
    real_sms_code = random.randint(0, 999999)
    # 不足6位前面补零
    real_sms_code = "%06d" % real_sms_code
    # 3.4.2 调用CCP类发送短信验证码
    ccp = CCP()
    try:
        result = ccp.send_template_sms(mobile, [real_sms_code, constants.SMS_CODE_REDIS_EXPIRES / 60], 1)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR, errmsg="云通信发送短信验证码异常")

    if result == -1:
        return jsonify(errno=RET.THIRDERR, errmsg="云通信发送短信验证码异常")

    # 3.4.3 发送短信验证码成功后，保存6位的短信验证码值到redis数据库[方便注册接口使用]
    try:
        redis_store.setex("SMS_%s" % mobile, constants.SMS_CODE_REDIS_EXPIRES, real_sms_code)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="保存短信验证码值异常")

    # 4.1 发送短信验证码成功
    return jsonify(errno=RET.OK, errmsg="发送短信验证码成功")


# 使用蓝图对象
# 127.0.0.1：5000/passport/image_code?code_id=UUID编号
@passport_bp.route('/image_code')
def get_image_code():
    """生成图形验证码的后端接口"""
    """
    1.获取参数
        1.1 code_id: UUID唯一编号 
    2.校验参数
        2.1 非空判断
    3.逻辑处理
        3.1 调用工具类，生成图形验证码图片，图形验证码的真实值
        3.2 以code_id作为key图形验证码的真实值，存储到redis数据库
    4.返回值
        4.1 将图片数据返回
    """

    # 1.1 获取参数 code_id: UUID唯一编号
    code_id = request.args.get("code_id")

    # 2.1 非空判断
    if not code_id:
        return abort(404)

    # 3.1 调用工具类，生成图形验证码图片，图形验证码的真实值
    image_name, real_image_code, image_data = captcha.generate_captcha()

    # 3.2 以code_id作为key图形验证码的真实值，存储到redis数据库
    redis_store.setex("imageCode_%s" % code_id, constants.IMAGE_CODE_REDIS_EXPIRES ,real_image_code)

    #  4.1 将图片数据返回
    # 注意：如果不设置响应数据格式，返回的就是普通文件数据，不能兼容所有浏览器
    response = make_response(image_data)
    # 将响应数据格式设置为：图片的png格式
    response.headers["Content-Type"] = "png/image"
    return response