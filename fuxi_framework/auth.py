#!/usr/bin/env python
# -*- coding: utf-8 -*-
########################################################################
# 
# 
########################################################################
 
"""
File: auth.py
Date: 2017/05/10 15:47:48
"""
import os
import sys
import re
import urllib2
import urllib
import traceback
from suds.client import Client
from suds.sax.element import Element
from django.db import connection
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from common_lib import util
from common_lib import baassw
from fuxi_framework.common_lib import config_parser_wrapper
from fuxi_framework.models import FuxiPermissionInfo
from fuxi_framework.models import FuxiRoleInfo
from fuxi_framework.models import FuxiUserInfo

CUR_DIR = os.path.abspath(os.path.dirname(__file__))
conf = config_parser_wrapper.ConfigParserWrapper("%s/conf/auth.conf" % CUR_DIR)

class CSRFMiddleware(object):
    """
    csrf
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        setattr(request, '_dont_enforce_csrf_checks', True)
        response = self.get_response(request)

        return response

class UserLoginAuthentication(object):
    """
    用户登录验证，未登录用户跳转至登录界面
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        username = str(request.user)
        cred = request.META.get("HTTP_CRED", "")
        path = str(request.path)
        patten_login = re.compile(r"/accounts/login")
        match_login = patten_login.match(path)
        patten_api = re.compile(r"/api/")
        match_api = patten_api.match(path)
        
        if username != "AnonymousUser":
            pass
        elif cred != "":
            pass
        elif match_login:
            pass
        elif match_api:
            pass
        else:
            return HttpResponseRedirect("/accounts/login/")

        response = self.get_response(request)

        return response


def get_username(request):
    """
    获取当前登录用户的用户名

    :param request: HttpRequest对象
    :return username: 用户名，字符串类型
    :raise util.EFailedRequest: 获取失败抛出请求异常
    """
    try:
        if str(request.user) != "AnonymousUser":
            return str(request.user)
    
        url = request.get_raw_uri()
        if "ticket=" in url:
            match = re.match(r"(.*)\?ticket=(.*)$", url)
            return __validate_ticket(request, match.group(1), match.group(2))
    
        #baas user
        remote_addr = request.META.get("REMOTE_ADDR", "")
        cred = request.META.get("HTTP_CRED", "")
        if cred == "" or remote_addr == "":
            raise util.EFailedRequest("get cred or remote_addr failed")
        return __get_username_by_cred(cred, remote_addr)
    except Exception as e:
        raise util.EFailedRequest(cred + str(e) + str(traceback.format_exc()))


def is_authenticated(username, _permission, _product, _module, _fuxi_app):
    """
    判断用户是否拥有对应产品线、模块的某个角色

    :param user: 用户名
    :param permission: 要鉴权的权限类型
    :param product: 产品线
    :param module: 模块名
    :return result: True/False 布尔类型的鉴权结果
    :raise util.EFailedRequest: 请求失败
    """
    try:
        roles = FuxiRoleInfo.objects.filter(permission=_permission)
        user_infos = FuxiUserInfo.objects.filter(product=_product, module=_module, 
                                                fuxi_app=_fuxi_app, role__in=roles)
        product_admin_users = FuxiUserInfo.objects.filter(product=_product, role="product_admin")
        platform_admin_users = FuxiUserInfo.objects.filter(role="platform_admin")
        connection.close()
    
        if _permission == "admin":
            return __varify_user(username, platform_admin_users)
        else:
            all_users = user_infos | product_admin_users | platform_admin_users
            return __varify_user(username, all_users)
    except Exception as e:
        raise util.EFailedRequest(str(e))


def __varify_user(username, user_infos):
    """
    验证一个用户是否在一个用户集合中
    
    :param username: 用户名邮箱前缀
    :param user_infos: 用户信息表的一个queryset集合
    :return result: True/False 布尔型的鉴权结果
    """
    for user_info in user_infos:
        if user_info.user_type == 0 and user_info.user == username:
            return True
        elif user_info.user_type == 1 and username in __get_user_by_email(user_info.user):
            return True
    return False


def __get_user_by_email(email):
    """
    通过邮件组获取邮件组中的用户名

    :param email: 邮箱前缀
    :return user_list: 邮箱中包含的所有用户名
    """
    user_list = []
    url = conf.get_option_value("global", "uic_url")
    app_key = conf.get_option_value("global", "uuap_app_key")
    client = Client(url)
    app_key = Element('appKey').setText(app_key)
    client.set_options(soapheaders=app_key)
    for user in user_info:
        user_list.append(user['username'])
    return user_list


def __validate_ticket(request, base_url, ticket):
    """
    校验ticket

    :param request: http请求对象
    :param base_url: 请求的url前缀
    :param ticket: uuap票据
    :return username: 用户名
    """
    uuap_validate_url = conf.get_option_value("global", "uuap_validate_url")
    uuap_validate_data = urllib.urlencode(
            {'service': base_url, 'ticket': ticket})
    uuap_validate_req = urllib2.Request(uuap_validate_url, uuap_validate_data)
    uuap_validate_rep = urllib2.urlopen(uuap_validate_req).read()
    m = re.findall(r"<cas:user>(.*)</cas:user>", uuap_validate_rep, re.M)
    if not m:
        raise util.EFailedRequest("validate ticket failed")
    else:
        username = m[0]
        #request.set_cookie('user', username)
        return username


def __get_username_by_cred(cred, remote_addr):
    """
    根据cred获取用户名
    
    :param cred: baas生成的credential code
    :param remote_addr: 生成cred的ip
    :return username: 用户名
    """
    baassw.BAAS_Init()
    # 创建验证器
    ctx_verify = baassw.CredentialContext_p()
    verifier = baassw.ServerUtility.CreateCredentialVerifier()

    # 验证 ip+cred
    ret_verify = verifier.Verify(cred, remote_addr, ctx_verify.cast())
    if (ret_verify != 0):
        raise util.EFailedRequest("Verify client cred fail! err:" + ret_verify)
    
    # 如果客户cred中登录的是uid+role，则name为uid
    # 反之如果是service，则name为service
    # 可以用ctx.IsService()判断是否为service
    name = baassw.string_p()
    ctx_verify.value().GetName(name.cast())
    return name.value()



