# Biological_Database/Web/views/score.py
from flask import Blueprint, render_template, request, current_app, session, redirect, url_for, flash
from flask_login import login_required
from Web.views.pipeline import Score
import Web.views.SqlHelper as db

bp = Blueprint('score', __name__)

@bp.route('/', methods=['GET', 'POST'])
@login_required
def score_index():
    pipeline = current_app.pipeline
    # 1) 获取可选 gene_set 列表，改用 SqlHelper.fetchall
    rows = current_app.db.fetchall(
        "SELECT DISTINCT gene_set FROM gene_set_info ORDER BY gene_set"
    )
    # fetchall 返回 list of tuples，所以取 [0]
    gene_sets = [r[0] for r in rows]
    species_list = ['human', 'mouse']

    if request.method == 'POST':
        # 2) 读取用户新选择
        gene_set = request.form.get('gene_set')
        species = request.form.get('species', 'human')

        # 3) 保存下来，下次渲染时能 mark selected
        session['selected_gene_set'] = gene_set
        session['selected_species'] = species

        # 4) 清掉上次跑图的 flag，保证真正“重新跑”
        for k in ['score_done', 'group_done', 'dotplot_done', 'volcano_done',
                  'deg_csv', 'deg_table']:
            session.pop(k, None)

        try:
            # 使用 Score 类并传入 engine
            scorer = Score(pipeline)
            scorer.run(gene_set, species)
            scorer.group_byscore()
            scorer.diff_bygroup()

        except ValueError:
            flash("You might choose wrong gene set or species. Please choose other one~~~(^v^)~~~.", "danger")
        except Exception as e:
            current_app.logger.exception("Unexpected error in scoring")
            flash("Unexpected error, please try again.", "danger")
        # 6) 一律重定向回 GET，让用户看页面
        return redirect(url_for('score.score_index'))


    # GET 请求，读取 session 中的结果状态和路径
    # —— GET 分支 ——
    # 拿 session 里上次保存的 selection，没的话就用列表第一个

    selected_gs = session.get('selected_gene_set', gene_sets[0])
    selected_sp = session.get('selected_species', species_list[0])
    score_done = session.get("score_done", False)
    group_done = session.get("group_done", False)
    dotplot_done = session.get("dotplot_done", False)
    volcano_done = session.get("volcano_done", False)

    score_plot = session.get("score_plot")
    group_plot = session.get("group_plot")
    dotplot = session.get("dotplot")
    volcano = session.get("volcano")
    deg_table = session.get('deg_table')
    deg_csv = session.get('deg_csv')  # ← 新增
    selected_gene_set = session.get('selected_gene_set')
    selected_species = session.get('selected_species')

    return render_template('score.html',
                           gene_sets=gene_sets,
                           species_list=species_list,
                           selected_gene_set=selected_gene_set,
                           selected_species=selected_species,
                           score_done=score_done,
                           group_done=group_done,
                           dotplot_done=dotplot_done,
                           volcano_done=volcano_done,
                           score_plot=score_plot,
                           group_plot=group_plot,
                           dotplot=dotplot,
                           volcano=volcano,
                           deg_table=deg_table,
                           deg_csv=deg_csv)
