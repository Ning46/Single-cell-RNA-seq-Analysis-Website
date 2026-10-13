import os
from flask import Flask, session, redirect, url_for
from flask_login import LoginManager
from Web.views.pipeline import User
from Web.views.pipeline import SingleCellPipeline
from Web.views.SqlHelper import sql_db as db

def create_app():
    app = Flask(__name__, static_folder='statics', static_url_path='/statics')
    app.secret_key = os.environ["FLASK_SECRET_KEY"]

    app.db = db

    # 初始化 Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'  # 未登录时重定向到登录页面

    @login_manager.user_loader
    def load_user(user_id):
        # 定义从数据库加载用户的方法（Flask-Login会根据session中存的用户ID调用此函数）
        return User.get(user_id)

    # 全局唯一的 SingleCellPipeline 实例
    app.pipeline = SingleCellPipeline()

    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    # 注册各个蓝图（包括后文定义的 auth 和 enrich 蓝图）
    from .views import auth, upload, qc, cluster, annotate , score,enrich,restart
    app.register_blueprint(auth.bp)  # 用户认证相关，无前缀，路径直接为 /login 等
    app.register_blueprint(upload.bp, url_prefix="/upload")
    app.register_blueprint(qc.bp, url_prefix="/qc")
    app.register_blueprint(cluster.bp, url_prefix="/cluster")
    app.register_blueprint(annotate.bp, url_prefix="/annotate")
    app.register_blueprint(score.bp, url_prefix='/score')
    app.register_blueprint(enrich.bp,url_prefix='/enrich')
    app.register_blueprint(restart.bp,url_prefix='/restart')


    return app
