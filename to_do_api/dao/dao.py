import os

import psycopg2
import psycopg2.extras


# register uuid
psycopg2.extras.register_uuid()

class DAO:
    DB_HOST = "DB_HOST"
    DB_PORT = "DB_PORT"
    DB_USER = "DB_USER"
    DB_PASSWORD = "DB_PASSWORD"
    DB_DATABASE = "DB_DATABASE"

    def __init__(self):
        self.__connection = None
        try:
            self.__connection = psycopg2.connect(user=os.getenv(DAO.DB_USER, "postgres"),
                                    password=os.getenv(DAO.DB_PASSWORD, "example"),
                                    host=os.getenv(DAO.DB_HOST, "db"),
                                    port=os.getenv(DAO.DB_PORT, "5432"),
                                    database=os.getenv(DAO.DB_DATABASE, "todo"))
        except:
            pass
    
    def execute(self, sql: str, parameters: tuple) -> int:
        try:
            self.__cursor = self.__connection.cursor()
            self.__cursor.execute(sql, parameters)

            self.__connection.commit()

            return self.__cursor.rowcount
        except Exception as ex:
            raise ex
        finally:
            self.__cursor.close
    
    def fetch_all(self, sql: str) -> list:
        try:
            self.__cursor = self.__connection.cursor()
            self.__cursor.execute(sql, ())

            return self.__cursor.fetchall()
        except Exception as ex:
            raise ex
        finally:
            self.__cursor.close

    def __del__(self):
        if self.__connection:
            self.__connection.close()