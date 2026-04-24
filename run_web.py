"""生产 Web 服务入口。

Gunicorn 只需要加载本文件中的 application，不会启动 APScheduler。
数据库初始化不放在导入阶段，避免 Gunicorn 多 worker 导入时重复执行初始化逻辑。
"""

from config import WEB_AUTO_RELOAD, WEB_HOST, WEB_PORT
from database import init_db
from web_ui.app import app

# Gunicorn 默认查找 application；这里仅暴露 Flask app，不启动 scheduler。
application = app


def main():
    """本地直接运行 Web 调试入口，不启动调度器。"""
    # 仅在直接 python run_web.py 时初始化数据库；Gunicorn 导入时不会执行。
    init_db()
    app.run(
        host=WEB_HOST,
        port=WEB_PORT,
        debug=WEB_AUTO_RELOAD,
        use_reloader=WEB_AUTO_RELOAD,
    )


if __name__ == "__main__":
    main()
