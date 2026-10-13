# Web/views/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from Web.views.pipeline import User
import Web.views.SqlHelper as db

bp = Blueprint('auth', __name__)

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')
    # POST 提交注册表单
    username = request.form.get('username')
    password = request.form.get('password')

    # 简单检查：用户名是否已存在
    if not username or not password:
        flash('username and password are required')
        return render_template('register.html')

    sql_check = "SELECT 1 FROM users WHERE username = %s"
    exists = current_app.db.fetchone(sql_check, username)
    if exists:
        flash("username already exists, please choose another one.")
        return redirect(url_for('auth.register'))

    # 2) 插入新用户
    password_hash = generate_password_hash(password)
    sql_insert = "INSERT INTO users (username, password_hash) VALUES (%s, %s)"
    try:
        current_app.db.execute(sql_insert, username, password_hash)
    except Exception as e:
        current_app.logger.error(f"Database error when register: {e}")
        flash("Register failed. Please try again later.")
        return render_template('register.html')

    flash("Register succeeded! Please log in.", 'success')
    return redirect(url_for('auth.login'))


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    username = request.form.get('username')
    password = request.form.get('password')

    # validate() 会按 username 查出 (id,username,hash) 并验密
    user = User.validate(username, password)
    if not user:
        flash("Username or password incorrect, please try again.")
        return redirect(url_for('auth.login'))

    # 清空旧 session，避免保留上次的 upload_done/qc_done 等
    session.clear()
    login_user(user)

    # 初始化会话状态：从上传开始
    session['upload_done'] = False
    session['qc_done'] = False
    session['cluster_done'] = False

    return redirect(url_for('upload.upload'))

@bp.route('/logout')
@login_required
def logout():
    # 清除当前用户的内存pipeline缓存
    current_app.pipelines.pop(current_user.id, None)
    # 登出用户，清除登录状态
    logout_user()
    # 清除会话信息
    session.clear()
    # 返回登录页面
    return redirect(url_for('auth.login'))
