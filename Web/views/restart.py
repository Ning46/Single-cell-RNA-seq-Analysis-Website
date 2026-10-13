# Web/views/restart.py
from flask import Blueprint, session, redirect, url_for

bp = Blueprint('restart', __name__)  # 注意名称必须是 'restart'

@bp.route('/')
def index():
    # Flask-Login 在 session 里存的 key 是 '_user_id'、'_fresh' 以及 '_id'
    keep = {'_user_id', '_fresh', '_id'}
    # 你自己存的 pipeline/session 标志，都一并清掉
    for key in list(session.keys()):
        if key not in keep:
            session.pop(key)
    # 跳回上传页面，开始新一轮分析
    return redirect(url_for('upload.upload'))
