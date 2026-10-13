import os
import pandas as pd
import pymysql

# ———— 配置区 ————
HOST = os.environ.get("DB_HOST", "127.0.0.1")
USER = os.environ.get("DB_USER", "root")
PASSWORD = os.environ["DB_PASSWORD"]
DB_NAME = os.environ.get("DB_NAME", "scrnaweb")
CSV_INFO = "gene_set_info.csv"
CSV_GENES= "gene_set_genes.csv"
# ——————————

# 1) 建立连接
conn = pymysql.connect(
    host=HOST, user=USER, password=PASSWORD, db=DB_NAME,
    charset="utf8mb4", autocommit=False
)
cur = conn.cursor()

# 2) 清空旧表
cur.execute("TRUNCATE TABLE gene_set_genes;")
cur.execute("TRUNCATE TABLE gene_set_info;")
conn.commit()

# 3) 读 gene_set_info.csv 并导入
df_info = pd.read_csv(CSV_INFO)
info_rows = [
    (row["gene_set"], row["species"], row["description"])
    for _, row in df_info.iterrows()
]
cur.executemany(
    "INSERT INTO gene_set_info (gene_set, species, description) VALUES (%s,%s,%s)",
    info_rows
)
conn.commit()

# 4) 取回刚插入的 id ↔ gene_set 映射
cur.execute("SELECT id, gene_set FROM gene_set_info;")
mapping = { gene_set: idx for idx, gene_set in cur.fetchall() }

# 5) 读 gene_set_genes.csv 并关联 info_id，然后导入
df_genes = pd.read_csv(CSV_GENES)
gene_rows = []
for _, row in df_genes.iterrows():
    gs = row["gene_set"]
    gid = mapping.get(gs)
    if gid is not None:
        gene_rows.append((gid, row["gene"]))

cur.executemany(
    "INSERT IGNORE INTO gene_set_genes (info_id, gene) VALUES (%s,%s)",
    gene_rows
)
conn.commit()

# 6) 关闭
cur.close()
conn.close()

print("✅ 已清空并重新导入 gene_set_info 和 gene_set_genes 表！")
