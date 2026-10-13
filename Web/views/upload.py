from flask import Blueprint, request, render_template, redirect, url_for, session, current_app
from flask_login import login_required, current_user
import os
from Web.views.pipeline import SingleCellPipeline

bp = Blueprint("upload", __name__)

@bp.route("/", methods=["GET", "POST"])
@login_required
def upload():
    # GET: 渲染上传页面，并告诉模板是否已经上传过
    if request.method == "GET":
        return render_template(
            "upload.html",
            upload_done=session.get("upload_done", False)
        )

    # POST: 处理新文件上传
    file = request.files.get("file")
    if not file:
        return "No file uploaded", 400

    # 保存到 input/ 目录
    upload_dir = os.path.join(current_app.root_path, "input")
    save_path = os.path.join(upload_dir, file.filename)
    file.save(save_path)

    # 加载到 pipeline
    pipeline = current_app.pipeline
    pipeline.load_data(save_path)

    # 标记本次会话已完成上传
    session["upload_done"] = True

    # 跳转到 QC 页面
    return redirect(url_for("qc.qc_index"))
