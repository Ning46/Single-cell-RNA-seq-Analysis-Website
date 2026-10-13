import os
# save_libraries.py

import gseapy as gp
import pandas as pd
from sqlalchemy import create_engine, text


def save_enrichr_libraries_to_db(db_uri: str):
    """
    从 gseapy 获取 Enrichr 支持的库名称列表，并保存到 MySQL 数据库表 library_info 中。
    已有同名表时会被替换。

    参数:
      db_uri: SQLAlchemy 连接字符串，如 "mysql+pymysql://user:pwd@host/dbname"
    """
    # 1) 读取所有库名
    libs = gp.get_library_name()  # 返回一个列表 of str

    # 2) 构造 DataFrame
    df = pd.DataFrame({"library_name": libs})

    # 3) 建立数据库连接
    engine = create_engine(db_uri)

    # 4) 保存到数据库
    #    如果表已存在：替换；否则新建
    # 省略 dtype 参数
    df.to_sql(
        name="library_info",
        con=engine,
        if_exists="replace",
        index=False,
    )

    print(f"已存入 {len(df)} 条库名到表 library_info")


if __name__ == "__main__":
    # 把下面的 URI 换成你的实际 MySQL 连接
    DATABASE_URI = os.environ["DATABASE_URI"]
    save_enrichr_libraries_to_db(DATABASE_URI)
