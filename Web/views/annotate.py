from flask import Blueprint, render_template, current_app, request, redirect, url_for, session
from flask_login import login_required
from Web.views.pipeline import SingleCellPipeline
import os

bp = Blueprint('annotate', __name__)

MODEL_DIR = os.environ.get("CELLTYPIST_MODEL_DIR", os.path.expanduser("~/.celltypist/data/models"))

@bp.route('/', methods=['GET', 'POST'])
@login_required
def annotate_index():
    pipeline = current_app.pipeline

    # 模型列表
    all_models = [f for f in os.listdir(MODEL_DIR) if f.endswith(".pkl")]

    # 确保 error_msg 在任何情况下都有定义
    error_msg = None

    if request.method == 'POST':
        model_name = request.form.get("model", "Immune_All_High.pkl")
        method = request.form.get("method", "umap")

        # 3) 运行注释和绘图
        full_model_path = os.path.join(MODEL_DIR, model_name)
        try:
            pipeline.annotate.run(model=full_model_path)
            # 假设 .plot() 会把图保存为 statics/annotate/<method>_annotate.png
            out_fname = pipeline.annotate.plot(method=method)

            plots = session.get("annotate_plot_list", [])
            plots.insert(0, out_fname)  # 最新图放最前
            session["annotate_plot_list"] = plots[:10]  # 最多保留 10 张

            # 5) 跳回 GET 展示
            return redirect(url_for('annotate.annotate_index'))
        except ValueError as e:
            # 捕获模型不匹配等错误，展示给用户
            error_msg = "OMG, Sorry! No features overlap with the model. Please choose another model."


    # GET 请求：读取 session 中保存的图列表
    plot_list = session.get("annotate_plot_list", [])

    return render_template(
        "annotate.html",
        model_list=all_models,
        plot_list=plot_list,
        error_msg=error_msg
    )