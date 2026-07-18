#!/bin/bash
# 后台启动项目所有服务（关闭终端后继续运行）
# 用法: ./start.sh         启动
#       ./start.sh stop     停止
#       ./start.sh status   查看状态

set -e
cd "$(dirname "$0")"

VENV=".venv/bin"
LOGDIR="logs"
PIDDIR="$LOGDIR"

# 确保日志和 PID 目录存在
mkdir -p "$LOGDIR" "$PIDDIR"

start() {
    echo "=== 启动 qingyun-aiLearn 服务 ==="

    # 1. 启动 FastAPI (uvicorn)
    if [ -f "$PIDDIR/uvicorn.pid" ] && kill -0 $(cat "$PIDDIR/uvicorn.pid") 2>/dev/null; then
        echo "[跳过] uvicorn 已在运行 (PID: $(cat "$PIDDIR/uvicorn.pid"))"
    else
        nohup "$VENV/uvicorn" app.main:app --host 0.0.0.0 --port 8000 \
            > "$LOGDIR/uvicorn.log" 2>&1 &
        echo $! > "$PIDDIR/uvicorn.pid"
        echo "[OK] uvicorn 已启动 (PID: $!) -> http://0.0.0.0:8000"
    fi

    # 2. 启动 Celery Worker
    if [ -f "$PIDDIR/celery.pid" ] && kill -0 $(cat "$PIDDIR/celery.pid") 2>/dev/null; then
        echo "[跳过] Celery Worker 已在运行 (PID: $(cat "$PIDDIR/celery.pid"))"
    else
        nohup "$VENV/celery" -A app.tasks.celery_app worker \
            --loglevel=info --concurrency=2 \
            > "$LOGDIR/celery.log" 2>&1 &
        echo $! > "$PIDDIR/celery.pid"
        echo "[OK] Celery Worker 已启动 (PID: $!)"
    fi

    echo "=== 启动完成 ==="
}

stop() {
    echo "=== 停止 qingyun-aiLearn 服务 ==="

    for svc in uvicorn celery; do
        if [ -f "$PIDDIR/$svc.pid" ]; then
            pid=$(cat "$PIDDIR/$svc.pid")
            if kill "$pid" 2>/dev/null; then
                echo "[OK] $svc 已停止 (PID: $pid)"
            else
                echo "[信息] $svc 进程不存在，清理 PID 文件"
            fi
            rm -f "$PIDDIR/$svc.pid"
        else
            echo "[跳过] $svc PID 文件不存在"
        fi
    done

    # 确保彻底清理
    pkill -f "uvicorn app.main:app" 2>/dev/null || true
    pkill -f "celery.*worker" 2>/dev/null || true
    echo "=== 停止完成 ==="
}

status() {
    echo "=== qingyun-aiLearn 服务状态 ==="
    for svc in uvicorn celery; do
        if [ -f "$PIDDIR/$svc.pid" ]; then
            pid=$(cat "$PIDDIR/$svc.pid")
            if kill -0 "$pid" 2>/dev/null; then
                echo "[运行中] $svc (PID: $pid)"
            else
                echo "[已停止] $svc (PID 文件存在但进程不存在)"
            fi
        else
            echo "[未启动] $svc"
        fi
    done
}

case "${1:-start}" in
    start)   start   ;;
    stop)    stop    ;;
    restart) stop; sleep 1; start ;;
    status)  status  ;;
    *)       echo "用法: $0 {start|stop|restart|status}" ;;
esac
