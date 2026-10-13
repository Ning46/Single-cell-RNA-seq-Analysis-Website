from flask import Blueprint, request, redirect, url_for, render_template, send_file, session, current_app,send_from_directory
from flask_login import login_required, current_user
import scanpy as sc
import io
import os
import time

bp = Blueprint("qc", __name__)

@bp.route("/", methods=["GET", "POST"])
@login_required
def qc_index():
    pipeline = current_app.pipeline
    if pipeline is None or pipeline.adata is None:
        return "Please upload data first.", 400

    # 直接调用 plot()，内部会把图保存到 static/qc_plot.png
    if not session.get("filter_done", False):
        pipeline.qc.plot()

    qc_plot_url = url_for("static", filename="qc_plot.png")

    return render_template(
        "qc_index.html",
        qc_done=True,
        filter_done=session.get("filter_done", False),
        qc_plot_url=qc_plot_url,
    )

@bp.route("/filter", methods=["POST"])
@login_required
def qc_filter():
    pipeline = current_app.pipeline
    if pipeline is None or pipeline.adata is None:
        return "Please upload data first.", 400

    # 读取表单参数并过滤
    min_genes = int(request.form.get("min_genes", 200))
    max_genes = int(request.form.get("max_genes", 2500))
    qc_percent = float(request.form.get("qc_percent", 5.0))
    pipeline.qc.filter(min_genes, max_genes, qc_percent)

    # 重新渲染 QC 页面，显示“Proceed to Clustering”按钮
    return redirect(url_for("qc.qc_index"))

