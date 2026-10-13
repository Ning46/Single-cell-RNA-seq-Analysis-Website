import os
import  pymysql
from dbutils.pooled_db import PooledDB
class SqlHelper:
    def __init__(self):
        self.pool = PooledDB(
            creator=pymysql,
            maxconnections=6,
            mincached =2,
            blocking = True,
            host = os.environ.get("DB_HOST", "127.0.0.1"),
            port = int(os.environ.get("DB_PORT", "3306")),
            user = os.environ.get("DB_USER", "root"),
            password = os.environ["DB_PASSWORD"],
            database = os.environ.get("DB_NAME", "scrnaweb"),
            charset='utf8'
        )
    def open(self):
        conn = self.pool.connection()
        cursor = conn.cursor()
        return conn, cursor

    def close(self, cursor, conn):
        cursor.close()
        conn.close()

    def fetchall(self, sql, *args):
        """get all data"""
        conn, cursor = self.open()
        cursor.execute(sql, args)
        result = cursor.fetchall()
        self.close(cursor, conn)
        return result

    def fetchone(self, sql, *args):
        """get one data"""
        conn, cursor = self.open()
        cursor.execute(sql, args)
        result = cursor.fetchone()
        self.close(cursor, conn)
        return result

    def execute(self, sql, *args):
        conn, cursor = self.open()
        try:
            count = cursor.execute(sql, args)
            conn.commit()
            return count
        except Exception as e:
            conn.rollback()
            raise
        finally:
            self.close(cursor, conn)

    def executemany(self, sql, params_list):
        conn, cursor = self.open()
        try:
            count = cursor.executemany(sql, params_list)
            conn.commit()
            return count
        except Exception as e:
            conn.rollback()
            raise
        finally:
            self.close(cursor, conn)

    def df_to_sql(self, df, table_name):
        """
        每次先清空表，再批量插入 DataFrame。
        用法：db.df_to_sql(df, 'differential_genes')
        """
        # 1) 清空旧数据
        self.execute(f"TRUNCATE TABLE `{table_name}`")
        # 2) 拼装插入语句
        cols = ", ".join(f"`{c}`" for c in df.columns)
        placeholders = ", ".join(["%s"] * len(df.columns))
        sql = f"INSERT INTO `{table_name}` ({cols}) VALUES ({placeholders})"
        # 3) 一行代码把所有数据转换成列表
        params = df.values.tolist()
        # 4) 批量写入
        self.executemany(sql, params)



sql_db = SqlHelper()
