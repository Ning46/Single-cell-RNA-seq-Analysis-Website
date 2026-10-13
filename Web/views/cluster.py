import os
from flask import Blueprint, render_template, session, current_app, request, redirect, url_for
from flask_login import login_required, current_user

bp = Blueprint("cluster", __name__)

@bp.route("/", methods=["GET", "POST"])
@login_required
def cluster_index():
    # 1) 前置：必须完成上传和 QC
    if not session.get("upload_done", False) or not session.get("qc_done", False):
        return "Please upload and complete QC first.", 400

    pipeline = current_app.pipeline
    if pipeline is None or pipeline.adata is None:
        return "Pipeline missing data. Please re-upload and QC.", 400

    # 2) POST：用户点击 Run
    if request.method == "POST":
        method = request.form.get("method", "umap")
        # 执行聚类
        pipeline.cluster.run()

        pipeline.cluster.plot(method=method)

        # 标记完成并记录用的方法
        session["cluster_method"] = method
        return redirect(url_for("cluster.cluster_index"))

    # 3) GET：渲染页面
    cluster_done = session.get("cluster_done", False)
    cluster_plot = session.get("cluster_plot", False)
    method = session.get("cluster_method", "umap")
    plot_url = url_for("static", filename="cluster_plot.png") if cluster_done else None

    return render_template(
        "cluster_index.html",
        cluster_done=cluster_done,
        cluster_plot=cluster_plot,
        method=method,
        cluster_plot_url=plot_url
    )
