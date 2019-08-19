from . import passport_bp
from flask import request, abort, make_response, jsonify, current_app
from info.utils.captcha.captcha import captcha
from info import redis_store, constants
from info.response_code import RET
from info.models import User
from info.lib.yuntongxun.sms import CCP
import re
import random


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