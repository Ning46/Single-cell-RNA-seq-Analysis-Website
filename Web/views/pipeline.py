import io
import os
import shutil
import scanpy as sc
import numpy as np
import pandas as pd
import gseapy as gp
from gseapy.plot import gseaplot
import matplotlib.pyplot as plt
from flask import current_app, session
from gseapy import Msigdb, enrichr, prerank
import celltypist
from celltypist import models
import seaborn as sns
import gseapy as gp
from gseapy.plot import barplot, dotplot
from flask_login import UserMixin
from werkzeug.security import check_password_hash

class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id             = id
        self.username       = username
        self.password_hash  = password_hash

    def get_id(self):
        # Flask-Login 会把这个字符串存到 session['_user_id']
        # 必须是 str
        return str(self.id)

    @staticmethod
    def get(user_id):
        """
        被 user_loader 调用。
        user_id 是上次 get_id() 存进去的 str(self.id)。
        """
        row = current_app.db.fetchone(
            "SELECT id, username, password_hash FROM users WHERE id = %s",
            int(user_id)
        )
        if not row:
            return None
        # row 比如 (1, 'alice', 'pbkdf2:...')
        return User(id=row[0], username=row[1], password_hash=row[2])

    def validate(username, password):
        """
        登录时用：按用户名查一行，再校验 hash。
        """
        row = current_app.db.fetchone(
            "SELECT id, username, password_hash FROM users WHERE username = %s",
            username
        )
        if not row or not check_password_hash(row[2], password):
            return None
        return User(id=row[0], username=row[1], password_hash=row[2])

class SingleCellPipeline:
    """
    Pipeline for single-cell data analysis. Maintains an AnnData object across methods.
    Methods accept user-specified parameters at call time.
    """

    def __init__(self):
        """Load 10X data from folder into self.adata."""
        self.adata = None
        self._qc = None
        self._cluster = None
        self._annotate = None
        self._score = None
        self._enrich = None

    def load_data(self, archive_path):
        # 1. 解压到 input/<basename>/
        basename = os.path.splitext(os.path.basename(archive_path))[0]
        extract_root = os.path.join(current_app.root_path, "input", basename)
        # 清理旧目录
        if os.path.exists(extract_root):
            shutil.rmtree(extract_root)
        shutil.unpack_archive(archive_path, extract_root)

        # 2. 在 extract_root 下递归寻找 matrix.mtx 或 matrix.mtx.gz
        data_dir = None
        for root, dirs, files in os.walk(extract_root):
            if any(fname in files for fname in ("matrix.mtx", "matrix.mtx.gz")):
                data_dir = root
                break
        if data_dir is None:
            raise FileNotFoundError(
                f"在 {extract_root} 及其子目录中找不到 matrix.mtx 或 matrix.mtx.gz"
            )

        # 3. 读取 10X 数据
        adata = sc.read_10x_mtx(data_dir, var_names='gene_symbols', cache=True)
        adata.var_names_make_unique()
        self.adata = adata
        return self

    @property
    def qc(self):
        """懒加载 QC 模块"""
        if self._qc is None:
            self._qc = QC(self)
        return self._qc

    @property
    def cluster(self):
        """懒加载 降维+聚类 模块"""
        if self._cluster is None:
            self._cluster = Cluster(self)
        return self._cluster

    @property
    def annotate(self):
        """懒加载 注释 模块"""
        if self._annotate is None:
            self._annotate = Annotate(self)
        return self._annotate

    @property
    def score(self):
        """懒加载 富集 模块"""
        if self._score is None:
            self._score = Score(self)
        return self._score

    # @property
    # def enrich(self):
    #     """懒加载 富集 模块"""
    #     if self._enrich is None:
    #         self._enrich = Enrich(self)
    #     return self._enrich


class QC:
    def __init__(self, pipeline: SingleCellPipeline):
        self.pl = pipeline

    def plot(self):
        """
        根据当前 adata 生成 QC 小提琴图，并保存到 static。
        不再返回 BytesIO，而是直接写入文件，最后返回 self。
        """
        adata = self.pl.adata

        # 标准的 QC 计算
        sc.pp.filter_cells(adata, min_genes=200)
        sc.pp.filter_genes(adata, min_cells=3)
        adata.var['mt'] = adata.var_names.str.startswith('MT-')
        sc.pp.calculate_qc_metrics(
            adata,
            qc_vars=['mt'],
            log1p=False,
            percent_top=None,
            inplace=True
        )

        img_path = os.path.join(current_app.root_path,"statics", "qc_plot.png")

        # 绘图并保存
        sc.pl.violin(
            adata,
            ["n_genes_by_counts", "total_counts", "pct_counts_mt"],
            jitter=0.4,
            multi_panel=True,
            show=False
        )
        plt.savefig(img_path, bbox_inches="tight")
        plt.close()

        session["qc_done"] = True
        return self

    def filter(self, min_genes=200, max_genes=2500, qc_percent=5):
        adata = self.pl.adata
        adata = adata[adata.obs['n_genes_by_counts'].between(min_genes, max_genes)]
        adata = adata[adata.obs['pct_counts_mt'] < qc_percent]
        self.pl.adata = adata.copy()
        session["filter_done"] = True
        return self


class Cluster:
    def __init__(self, pipeline: SingleCellPipeline):
        self.pl = pipeline

    def run(self, target_sum=1e4, log_transform=True):
        adata = self.pl.adata
        if adata is None:
            raise RuntimeError("请先 load_data() 并做 QC_filter()")
        # Normalize and log
        sc.pp.normalize_total(adata, target_sum=target_sum)
        sc.pp.log1p(adata)
        sc.pp.highly_variable_genes(adata, n_top_genes=2000, subset=True)

        adata.raw = adata.copy()

        # Scale, PCA, neighbors, clustering
        sc.pp.scale(adata)
        sc.pp.pca(adata)
        sc.pp.neighbors(adata, n_pcs=15)
        sc.tl.leiden(adata, resolution=0.5)
        session["cluster_done"] = True
        return self

    def plot(self, method="umap"):
        """
        根据 method 绘制聚类图，并保存到 static/cluster_plot.png
        """
        adata = self.pl.adata
        img_path = os.path.join(current_app.root_path, "statics", "cluster_plot.png")

        # 执行降维并画图
        if method == "umap":
            sc.tl.umap(adata)
            sc.pl.umap(adata, color='leiden', show=False)
        elif method == "tsne":
            sc.tl.tsne(adata)
            sc.pl.tsne(adata, color='leiden', show=False)
        else:
            raise ValueError(f"Unsupported method: {method}")

        # 保存到文件
        plt.savefig(img_path, bbox_inches="tight")
        plt.close()
        session["cluster_plot"] = method
        return self

class Annotate:
    """celltypist Annotate"""
    def __init__(self, pipeline: SingleCellPipeline):
        self.pl = pipeline
        self.annotated = None

    def run(self, model='Immune_All_High.pkl'):
        adata = self.pl.adata

        # 记录模型名，用于后续文件命名
        self.model_name = os.path.splitext(os.path.basename(model))[0]

        model = models.Model.load(model=model)
        predictions = celltypist.annotate(adata, model=model, majority_voting=True)
        adata2 = predictions.to_adata()

        adata2.obs.majority_voting = adata2.obs.majority_voting.str.replace(' cells','')
        adata2.obs.majority_voting = adata2.obs.majority_voting.str.replace(' monocytes',' Mono')

        self.annotated = adata2
        session["annotate_done"] = True
        return self

    def plot(self,method = "umap"):
        if self.annotated is None:
            raise RuntimeError("please use run() to generate annotated obj")

        adata2 = self.annotated

        out_dir = os.path.join(current_app.root_path, "statics", "annotate")
        os.makedirs(out_dir, exist_ok=True)

        # 组合文件名：模型名_方法.png
        fname = f"{self.model_name}_{method}.png"
        fullpath = os.path.join(out_dir, fname)

        # 先做降维
        if method == "umap":
            sc.tl.umap(adata2)
            sc.pl.umap(adata2,color="majority_voting",legend_loc='right margin',show=False)
        elif method == "tsne":
            sc.tl.tsne(adata2)
            sc.pl.tsne(adata2,color="majority_voting",legend_loc='right margin',show=False)
        else:
            raise ValueError(f"Unsupported method: {method}")

        # 再统一保存图像
        plt.savefig(fullpath, bbox_inches="tight")
        plt.close()

        # 返回相对于 static 的子路径
        return f"annotate/{fname}"

class Score:
    def __init__(self, pipeline):
        self.pl = pipeline
        # statics/ 下的相对目录
        self.out_dir = os.path.join(current_app.root_path, "statics")

    def run(self, gene_set, species="human"):
        adata = self.pl.adata
        sql = """
        SELECT gsg.gene
          FROM gene_set_genes AS gsg
          JOIN gene_set_info AS gsi
            ON gsg.info_id = gsi.id
         WHERE gsi.gene_set = %s
           AND gsi.species = %s
        """
        rows = current_app.db.fetchall(sql, gene_set, species)
        genes = [row[0] for row in rows]
        if not genes:
            raise ValueError(f"No genes for {gene_set}/{species}")

        # =======================
        # ← 1) 计算 score，不要 inplace=True
        sc.tl.score_genes(adata, gene_list=genes, score_name="score")

        # 2) UMAP 并保存
        sc.tl.umap(adata)
        sc.pl.umap(adata, color="score", show=False)
        fn = "score_umap.png"
        plt.savefig(os.path.join(self.out_dir, fn), bbox_inches="tight")
        plt.close()

        session["score_done"] = True
        session["score_plot"] = fn
        return self

    def group_byscore(self):
        adata = self.pl.adata
        med = adata.obs["score"].median()
        adata.obs["group"] = np.where(adata.obs["score"] > med, "high", "low")

        sc.pl.umap(adata, color="group", show=False)
        fn = "score_group_umap.png"
        plt.savefig(os.path.join(self.out_dir, fn), bbox_inches="tight")
        plt.close()

        session["group_done"] = True
        session["group_plot"] = fn
        return self

    def diff_bygroup(self):
        adata = self.pl.adata
        sc.tl.rank_genes_groups(adata, groupby="group",
                                reference="low", method="wilcoxon", pts=True)

        # 点图
        sc.pl.rank_genes_groups_dotplot(adata,
                                       standard_scale="var",
                                       n_genes=10, show=False)
        fn_dot = "dotplot_rank_genes_groups.png"
        plt.savefig(os.path.join(self.out_dir, fn_dot), bbox_inches="tight")
        plt.close()
        session["dotplot_done"] = True
        session["dotplot"] = fn_dot

        # 提取差异表
        res = adata.uns["rank_genes_groups"]
        df = pd.DataFrame({
            "gene":      res["names"]["high"],
            "log2FC":    res["logfoldchanges"]["high"],
            "pval":      res["pvals"]["high"],
            "pvals_adj": res["pvals_adj"]["high"],
        })
        df["-log10(pval)"] = -np.log10(df["pval"])
        pts = pd.DataFrame(res["pts"])[["high","low"]].reset_index()\
               .rename(columns={"index":"gene","high":"pct.high","low":"pct.low"})
        df = df.merge(pts, on="gene")

        # ← 修正这里：嵌套 np.where
        k1 = (df["log2FC"]>1) & (df["pval"]<0.05)
        k2 = (df["log2FC"]<-1) & (df["pval"]<0.05)
        df["change"] = np.where(k1, "up", np.where(k2, "down", "stable"))

        # 写表
        current_app.db.df_to_sql(df, "differential_genes")
        session["deg_table"] = "differential_genes"

        # —— 新增：写成 CSV 供前端下载 ——
        csv_fn = "differential_genes.csv"
        csv_path = os.path.join(self.out_dir, csv_fn)
        df.to_csv(csv_path, index=False)
        session["deg_csv"] = csv_fn

        # 火山图
        plt.figure(figsize=(10,6))
        sns.scatterplot(data=df, x="log2FC", y="-log10(pval)",
                        hue="change", alpha=0.7, s=40)
        plt.axhline(-np.log10(0.05), linestyle="--", color="black")
        plt.axvline(1, linestyle="--", color="black")
        plt.axvline(-1, linestyle="--", color="black")
        plt.tight_layout()
        fn_vol = "volcano_plot.png"
        plt.savefig(os.path.join(self.out_dir, fn_vol), bbox_inches="tight")
        plt.close()
        session["volcano_done"] = True
        session["volcano"] = fn_vol

        return self

    def compare_gene_expression(self, gene: str):
        """
        Generate a violin plot comparing expression of `gene` in high vs low score groups
        """
        adata = self.pl.adata
        if gene not in adata.var_names:
            raise ValueError(f"Gene '{gene}' not found in AnnData.")

        # Make sure group labels exist
        if 'group' not in adata.obs:
            raise RuntimeError("Score groups not defined. Call group_byscore() first.")

        # Plot violin
        sc.pl.violin(
            adata,
            keys=gene,
            groupby='group',
            jitter=0.4,
            show=False
        )
        fn = f"violin_{gene}.png"
        out_path = os.path.join(self.out_dir, fn)
        plt.savefig(out_path, bbox_inches='tight')
        plt.close()

        # Save session info for frontend
        session['gene_compare_done'] = True
        session['gene_compare_plot'] = fn
        session['gene_compare_name'] = gene
        return self

class Enrich:
    def __init__(self, gene_file: str):
        """
        gene_file: 上传的 gene_list 文件路径（txt，一行一个基因）
        """
        self.gene_file = gene_file
        self.out_dir = os.path.join(current_app.root_path, "statics", "enrich")
        os.makedirs(self.out_dir, exist_ok=True)

    def run(self,
            method,
            gene_file,
            library_name,
            organism = "Human",
            gene_setstr = "c1.all"):
        """
        统一入口：根据 method 路由到 ORA 或 GSEA
        method: 'ora' 或 'gsea'
        gene_file: 上传后的文件路径
        library_name: Enrichr 库名
        organism: 'Human'/'Mouse'
        """
        if method == "ora":
            self.run_ora(gene_file, library_name, organism)
        elif method == "gsea":
            self.run_gsea(gene_file, organism, gene_setstr)
        else:
            raise ValueError(f"Unknown method: {method}")
        session["method"] = method
        return self

    def run_ora(self, gene_file, library_name, organism):
        # 1) 读取一行一个基因的列表
        with open(gene_file) as f:
            genes = [g.strip() for g in f if g.strip()]
        if not genes:
            raise ValueError("Uploaded gene list is empty.")

        # 2) 调用 Enrichr
        enr = gp.enrichr(
            gene_list=genes,
            gene_sets=library_name,
            organism=organism,
            outdir=None,
            cutoff=0.05
        )

        # 3) 画图并保存
        bar_fn = os.path.join(self.out_dir, f"bar_{library_name}.png")
        dot_fn = os.path.join(self.out_dir, f"dot_{library_name}.png")
        barplot(enr.res2d, ofname=bar_fn)
        dotplot(enr.res2d, ofname=dot_fn, size=5)

        # 4) 写 session 以供前端渲染
        session["enrich_done"]         = True
        session["bar_plot"]            = f"enrich/bar_{library_name}.png"
        session["dot_plot"]            = f"enrich/dot_{library_name}.png"

        # 5) 可选：保存结果表
        csv_fn = os.path.join(self.out_dir, f"enrich_result_{library_name}.csv")
        enr.res2d.to_csv(csv_fn, index=False)
        session["enrich_result_csv"]   = f"enrich/enrich_result_{library_name}.csv"

    def run_gsea(self, gene_file, organism,gene_setstr):
        # 1) 读取带有 gene & log2FC 列的表格
        df = pd.read_csv(gene_file, sep=None, engine='python')
        if "gene" not in df.columns or "log2FC" not in df.columns:
            raise ValueError("Uploaded file must contain 'gene' and 'log2FC' columns.")

        # —— 从数据库加载 gene_setstr 对应的基因集到 dict ——

        sql = """
        SELECT gsi.gene_set, gsg.gene
        FROM gene_set_genes AS gsg
        JOIN gene_set_info AS gsi
        ON gsg.info_id = gsi.id
        WHERE gsi.category = %s   -- 或者 WHERE gsi.gene_set = %s
        AND gsi.species = %s
        """

        rows = current_app.db.fetchall(sql, gene_setstr, organism.lower())
        # rows 是一个 list of (gene_set, gene)
        # 把它转换成 { gene_set: [gene,…], … }
        from collections import defaultdict
        gmt_dict = defaultdict(list)
        for gs, gene in rows:
            gmt_dict[gs].append(gene)

        # 2) 提取并重命名
        rnk = (
            df[["gene", "log2FC"]]
            .dropna()
            .rename(columns={"log2FC": "score"})
        )
        #
        # if organism == "Human":
        #     msig = gp.Msigdb()
        #     gmt = msig.get_gmt(category=gene_setstr, dbver="2024.1.Hs")
        # else:
        #     msig = gp.Msigdb()
        #     gmt = msig.get_gmt(category=gene_setstr, dbver="2024.1.Mm")

        gsea_dir = os.path.join(self.out_dir, "gsea")
        os.makedirs(gsea_dir, exist_ok=True)

        # 3) 运行 prerank GSEA
        pre_res = gp.prerank(
            rnk=rnk,
            gene_sets=gmt_dict,  #gmt
            processes=4,
            outdir=gsea_dir,
            format='png',
            seed=6
        )

        # # 4) 画第一条 term 的 GSEA 曲线
        # top = pre_res.res2d.index[0]
        # stat = pre_res.results[top]
        #
        # gsea_fn = os.path.join(gsea_dir, f"gsea_{gene_setstr}.png")
        # os.makedirs(gsea_fn, exist_ok=True)
        # gseaplot(
        #     pre_res.ranking,
        #     top,
        #     stat['hits'],  # list of hit positions
        #     stat['nes'],  # normalized enrichment score
        #     stat['pval'],  # nominal p-value
        #     stat['fdr'],  # FDR q-value
        #     stat['RES'],  # full enrichment score vector
        #     ofname=gsea_fn,
        # )

        # 5) 写 session 以供前端渲染
        session["enrich_done"] = True
        session["gsea_plot"]   = "enrich/gsea/prerank/HALLMARK_G2M_CHECKPOINT.png"



