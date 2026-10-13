import os
import gseapy as gp
from sqlalchemy import create_engine, text

# —— 1. 配置 ——
# 请改成你的连接串
DB_URI = os.environ["DATABASE_URI"]
engine = create_engine(DB_URI)

# —— 2. MSigDB 客户端 ——
msig = gp.Msigdb()

# —— 3. 定义要处理的基因集列表 ——
human_cats = [
    "h.all",      # Hallmark
    "c1.all",     # 染色体位置
    "c2.cp.kegg", # KEGG 通路
    "c5.go.bp",   # GO 生物过程
    "c7.all",     # 免疫相关
]
mouse_cats = [
    "mh.all",      # Hallmark (mouse)
    "m1.all",      # 染色体位置 (mouse)
    "m2.cp.kegg",  # KEGG 通路 (mouse)
    "m5.go.bp",    # GO 生物过程 (mouse)
    "m7.all",      # 免疫相关 (mouse)
]

# —— 4. 开始事务，一次性写入 ——
with engine.begin() as conn:
    # 4.1 插入基因集元信息（忽略已存在的）
    for cat in human_cats:
        conn.execute(text("""
            INSERT IGNORE INTO gene_set_info (gene_set, species, description)
            VALUES (:gs, 'human', :desc)
        """), {"gs": cat, "desc": f"{cat} (human gene set)"})
    for cat in mouse_cats:
        conn.execute(text("""
            INSERT IGNORE INTO gene_set_info (gene_set, species, description)
            VALUES (:gs, 'mouse', :desc)
        """), {"gs": cat, "desc": f"{cat} (mouse gene set)"})

    # 4.2 读取所有 gene_set_info，构建映射 (gene_set, species) → id
    rows = conn.execute(text("SELECT id, gene_set, species FROM gene_set_info")).all()
    info_map = {(r.gene_set, r.species): r.id for r in rows}

    # 4.3 下载并插入基因列表
    #    - human 用 dbver="2024.1.Hs"
    #    - mouse 用 dbver="2024.1.Mm"
    for cat in human_cats:
        # 下载人类基因集
        gmt = msig.get_gmt(category=cat, dbver="2024.1.Hs") or {}
        genes = set().union(*gmt.values())
        info_id = info_map[(cat, "human")]
        for gene in genes:
            conn.execute(text("""
                INSERT IGNORE INTO gene_set_genes (info_id, gene)
                VALUES (:info_id, :gene)
            """), {"info_id": info_id, "gene": gene})

    for cat in mouse_cats:
        # 下载小鼠基因集
        gmt = msig.get_gmt(category=cat, dbver="2024.1.Mm") or {}
        genes = set().union(*gmt.values())
        info_id = info_map[(cat, "mouse")]
        for gene in genes:
            conn.execute(text("""
                INSERT IGNORE INTO gene_set_genes (info_id, gene)
                VALUES (:info_id, :gene)
            """), {"info_id": info_id, "gene": gene})

print("全部基因集及基因列表已导入完成！")
