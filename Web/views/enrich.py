# File: Web/views/enrich.py
import os
from flask import Blueprint, render_template, request, current_app, session, redirect, url_for, flash
from flask_login import login_required
from Web.views.pipeline import Enrich  # 原来的 Enrich 类

bp = Blueprint('enrich', __name__)

@bp.route('/', methods=['GET', 'POST'])
@login_required
def enrich_index():
    # 1) 决定模式：ora 或 gsea，默认 ora
    method = request.args.get('method', 'ora').lower()
    if method not in ('ora', 'gsea'):
        method = 'ora'

    # 2) 读取所有库名
    rows = current_app.db.fetchall(
        "SELECT library_name FROM library_info ORDER BY library_name"
    )
    libs = [r[0] for r in rows]

    # 1) 获取可选 gene_set 列表，改用 SqlHelper.fetchall
    rows = current_app.db.fetchall(
        "SELECT DISTINCT gene_set FROM gene_set_info ORDER BY gene_set"
    )
    # fetchall 返回 list of tuples，所以取 [0]
    gene_sets = [r[0] for r in rows]

    # 3) POST：接收上传 & 运行
    if request.method == 'POST':
        lib = request.form.get('library')
        org = request.form.get('organism', 'Human')
        gene_file = request.files.get('gene_file')
        gene_setstr = request.form.get('gene_set')

        if not gene_file or not gene_file.filename.strip():
            flash("请上传基因列表文件 (.txt)", "danger")
            return redirect(url_for('enrich.enrich_index', method=method))

        upload_dir = os.path.join(current_app.root_path, 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, gene_file.filename)
        gene_file.save(filepath)

        try:
        # 当前假设你已将 Enrich 改为：run(method, gene_file, library_name, organism)
            Enrich(filepath).run(method, filepath, lib, org,gene_setstr)
        # 记录 GSEA 选中的 gene_set 到 session
            if method == 'gsea':
                session['selected_gene_set'] = gene_setstr
            flash("Enrich Completed！", "success")
        except Exception as e:
            flash(f"Enrich Failed：{e}", "danger")

        return redirect(url_for('enrich.enrich_index', method=method))

    tmpl = f"enrich_{method}.html"

    return render_template(
    tmpl,
    libs=libs,
    gene_sets=gene_sets,
    selected_library = session.get("selected_library", libs[0] if libs else ""),
    selected_gene_set=session.get("selected_gene_set", gene_sets[0] if gene_sets else ""),
    selected_organism = session.get("selected_organism", "Human"),
    enrich_done = session.get("enrich_done", False),
    bar_plot = session.get("bar_plot"),
    dot_plot = session.get("dot_plot"),
    result_csv = session.get("enrich_result_csv"),
    gsea_plot = session.get("gsea_plot"),
    )
